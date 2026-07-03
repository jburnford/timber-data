#!/usr/bin/env python3
"""Unified shipment parser (v2) — replaces parse_tabular.py output.

Handles both line formats found in the OCR corpus:
  - dash format (1879-1900):  [Date] Ship [(s)]-Origin-cargo[, cargo...]-Merchant
  - @ format (1874-1878):     [Date.] Ship [(s)] @ Origin,—cargo, cargo, Merchant.
                              (multiple ship units per line in the dense era)

Fixes over parse_tabular.py:
  1. thousands-separator commas no longer split cargo items ("26,744 pcs.")
  2. spaced separators (" - ") and en-dashes recognized
  3. lowercase commodity after hyphen splits origin from cargo ("Riga-deals")
     without breaking compound commodities ("pit-props")
  4. consignee defaults to None, never fabricated as "Order"
  5. date extraction handles Sept./full month names/months without periods
  6. merchant suffix detection instead of merchant-becomes-commodity
  7. PORT_HEADER regex keeps apostrophes/periods (BO'NESS, NEWPORT (MON.))
  8. shipping lines before any port header are kept (destination_port = "")

Output schema is identical to parse_tabular.py (parsed/*_parsed.json).
"""

import re
import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

OCR_DIR = Path("/home/jic823/timber_data/ocr_results/gemini_full")
CLASSIFICATION_DIR = Path("/home/jic823/timber_data/classification")
OUTPUT_DIR = Path("/home/jic823/timber_data/parsed")
OUTPUT_DIR.mkdir(exist_ok=True)


@dataclass
class CargoItem:
    quantity: Optional[str]
    unit: Optional[str]
    commodity: str
    raw_text: str


@dataclass
class Shipment:
    record_id: str
    line_number: int
    raw_text: str
    arrival_date: Optional[str]
    ship_name: str
    is_steamship: bool
    origin_port: str
    destination_port: str
    consignee: Optional[str]
    cargo: List[CargoItem]
    parse_confidence: str


# ---------------------------------------------------------------- lexicons

UNITS = (r'pcs|pieces|bdls|bundles|fms|fathoms|fm|lds|loads|ld|stds|standards|'
         r'doz|dozen|bxs|boxes|cs|cases|crts|crates|pkgs|packages|prs|pairs|'
         r'bgs|bags|no|t|tons|logs|planks|pipes|keels|cords|sticks|hhds')
UNIT_RE = re.compile(rf'^({UNITS})\.?\s+(.+)$', re.I)

# lowercase words that begin a cargo phrase (used to split "Riga-deals")
CARGO_START = (
    'deals', 'deal', 'battens', 'batten', 'boards', 'board', 'staves',
    'lathwood', 'laths', 'lath', 'firewood', 'pitwood', 'props', 'sleepers',
    'timber', 'tim', 'spars', 'poles', 'logs', 'ends', 'oak', 'fir', 'pine',
    'birch', 'ash', 'elm', 'beech', 'teak', 'mahogany', 'walnut', 'hewn',
    'sawn', 'mining', 'palings', 'hoops', 'mouldings', 'doors', 'flooring',
    'matchboards', 'wood', 'woodgoods', 'quantity', 'qty', 'sundry', 'sundries',
    'pit',  # pit props / pitwood — see PIT exception below
)
# ...but never split X-props / X-wood style compounds where X is lowercase
CARGO_START_RE = re.compile(
    r'^(?:' + '|'.join(CARGO_START) + r')\b', re.I)

MERCHANT_HINT = re.compile(
    r'(?:&|\bCo\b\.?|\bCos\b\.?|\bBros?\b\.?|\bSons?\b|Ltd|Order\b|Nil\b|Captain\b|Messrs|consignees)')
CARGO_WORD = re.compile(
    r'\b(?:' + '|'.join(w for w in CARGO_START if w != 'pit') +
    rf'|{UNITS}|pit ?-?props?|firs?|redwood|boxwood|ebony|cedar|treenails|'
    r'oars|pulp|gun-?stocks|crossings|riekers|boathooks|&c)\b\.?', re.I)

MONTHS = {'jan': 'Jan.', 'feb': 'Feb.', 'mar': 'Mar.', 'apr': 'Apr.',
          'may': 'May', 'jun': 'Jun.', 'jul': 'Jul.', 'aug': 'Aug.',
          'sep': 'Sep.', 'oct': 'Oct.', 'nov': 'Nov.', 'dec': 'Dec.'}
DATE_RE = re.compile(
    r'^\s*((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
    r'Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|'
    r'Dec(?:ember)?)\.?)\s+(\d{1,2})(?:st|nd|rd|th)?\.?\s+(.*)$')
DAY_RE = re.compile(r'^\s*(\d{1,2})(?:st|nd|rd|th)?\.?\s+([^\d].*)$')

THOUSANDS = re.compile(r'(?<=\d),(?=\d{3}\b)')
SENTINEL = '\x00'


# ---------------------------------------------------------------- helpers

def clean_ocr_line(line: str) -> str:
    return re.sub(r'^\s*\d+→', '', line)


def load_ocr_lines(ocr_path: Path) -> List[str]:
    raw = ocr_path.read_text(encoding='utf-8', errors='replace')
    return [clean_ocr_line(line) for line in raw.split('\n')]


def protect_thousands(text: str) -> str:
    return THOUSANDS.sub(SENTINEL, text)


def restore_thousands(text: str) -> str:
    return text.replace(SENTINEL, ',')


def extract_date(text: str, prev_month: Optional[str]) -> Tuple[Optional[str], str, Optional[str]]:
    """Return (date_str, remaining_text, updated_prev_month)."""
    m = DATE_RE.match(text)
    if m:
        month = MONTHS[m.group(1)[:3].lower()]
        return f"{month} {m.group(2)}", m.group(3), month
    m = DAY_RE.match(text)
    if m and prev_month:
        return f"{prev_month} {m.group(1)}", m.group(2), prev_month
    return None, text, prev_month


def looks_like_merchant(token: str) -> bool:
    """A comma-token that is a consignee name, not cargo."""
    t = token.strip().rstrip('.')
    if not t or re.search(r'\d', t):
        return False
    if CARGO_WORD.search(t) and not MERCHANT_HINT.search(t):
        return False
    if t.lower() in ('order', 'nil', 'ditto', 'do'):
        return True
    # name-like: starts with capital (or '&' continuation), short-ish
    return bool(re.match(r'^[A-Z&]', t)) and len(t) < 60


def parse_cargo_string(cargo_str: str) -> Tuple[List[CargoItem], Optional[str]]:
    """Parse 'qty unit commodity, qty unit commodity, Merchant; ...' string.

    Returns (cargo_items, merchant). Merchant is the maximal suffix of
    comma-tokens (in the final ;-segment) that looks like a name.
    """
    cargo_items: List[CargoItem] = []
    merchant: Optional[str] = None

    protected = protect_thousands(cargo_str)
    segments = re.split(r'\s*;\s*', protected)

    for seg_idx, segment in enumerate(segments):
        segment = segment.strip().strip('—–').strip()
        if not segment:
            continue
        # drop trailing editorial sentence after a merchant terminator
        tokens = [t.strip() for t in re.split(r',\s*', segment) if t.strip()]

        # peel merchant tokens off the end
        m_tokens: List[str] = []
        while tokens:
            cand = tokens[-1]
            # token like "Order. A quantity of sapanwood was brought..." —
            # truncate at a sentence break, but only after a lowercase word
            # so initials ("R. Goodman", "T. B. & S. Batchelor") survive
            head = re.split(r'(?<=[a-z)])\.\s+(?=[A-Z(])', cand, maxsplit=1)[0]
            if looks_like_merchant(head):
                head = restore_thousands(head).strip()
                if head.rstrip('.').lower() in ('order', 'nil'):
                    head = head.rstrip('.')
                m_tokens.insert(0, head)
                tokens.pop()
                if head != cand.strip():
                    break  # rest was editorial; stop peeling
            else:
                break
        seg_merchant = ', '.join(m_tokens) if m_tokens else None
        if seg_merchant:
            merchant = merchant or seg_merchant  # keep first named merchant

        for tok in tokens:
            tok_r = restore_thousands(tok).strip()
            if not tok_r or tok_r in ('&c.', '&c'):
                continue
            item = parse_cargo_token(tok_r)
            if item:
                cargo_items.append(item)

    return cargo_items, merchant


def parse_cargo_token(tok: str) -> Optional[CargoItem]:
    tok = tok.strip().strip('.').strip()
    if not tok:
        return None
    qty = None
    unit = None
    rest = tok
    m = re.match(r'^([\d,]+(?:\s+\d/\d)?|qty\.?|quantity(?:\s+of)?)\s*(.*)$', tok, re.I)
    if m:
        qty = m.group(1)
        rest = m.group(2).strip()
    um = UNIT_RE.match(rest)
    if um:
        unit = um.group(1) + ('.' if not um.group(1).endswith('.') else '')
        rest = um.group(2).strip()
    elif re.fullmatch(rf'(?:{UNITS})\.?', rest, re.I):
        # bare unit with commodity elided ("228 bdls.")
        unit = rest.rstrip('.') + '.'
        rest = ''
    commodity = rest.strip(' ,.;—–-')
    if not commodity and not qty:
        return None
    # drop name fragments that leaked past merchant peeling
    if (not qty and not unit and
            (len(commodity) <= 2 or
             (re.match(r'^[A-Z&]', commodity) and not CARGO_WORD.search(commodity)))):
        return None
    return CargoItem(quantity=qty, unit=unit, commodity=commodity, raw_text=tok)


# ---------------------------------------------------------------- gazetteer rescue

_GAZETTEER = None


def _squash_name(name: str) -> str:
    return re.sub(r"[.,'\s]+", ' ', name).strip().lower()


def gazetteer():
    """Squashed known port names from coordinates DB + authority mappings."""
    global _GAZETTEER
    if _GAZETTEER is None:
        names = set()
        ref = Path('/home/jic823/timber_data/reference_data')
        try:
            coords = json.load(open(ref / 'port_coordinates.json'))['coordinates']
            names.update(coords)
        except Exception:
            pass
        try:
            auth = json.load(open(ref / 'port_authority.json'))
            names.update(auth.get('mappings', {}))
            names.update(auth.get('mappings', {}).values())
        except Exception:
            pass
        _GAZETTEER = {_squash_name(n) for n in names
                      if len(n) >= 3 and re.search(r'[A-Za-z]{3}', n)}
        # country/word tokens that cause false port matches in dock tables
        _GAZETTEER -= {'russia', 'england', 'scotland', 'ireland', 'america',
                       'france', 'canada', 'order', 'quebec and montreal'}
    return _GAZETTEER


DOCK_TAIL = re.compile(r'\s+(\S+\s+(?:docks?|yard|wharf|basin|pond))\.?\s*$', re.I)
TRAIL_MERCHANT = re.compile(r'\s((?:[A-Z][^\s,]*\s+){0,4}(?:&\s+)?(?:Co|Cos|Sons?|Bros?|Ltd)\.?|Order)\s*$')
DITTO_TABLE = re.compile(r',,\s|\s,,')


def rescue_no_separator(text: str):
    """Recover (ship, origin, cargo_str, dock) from a line whose separators
    the OCR dropped: "Busy Bee (s) Rotterdam 1 case woodware ..." or a
    dock-list row "Black Eagle Sheerness Lavender yard". Returns None if no
    confident match."""
    if DITTO_TABLE.search(text):
        return None
    work = text.strip()
    dock = None
    dm = DOCK_TAIL.search(work)
    if dm:
        dock = dm.group(1)
        work = work[:dm.start()].strip()
    work_ns = work.replace('(s)', ' (s) ')
    tokens = work_ns.split()
    if len(tokens) < 2:
        return None
    gaz = gazetteer()

    # find port spans (prefer longer, later); span must not start at token 0
    best = None
    for span_len in (3, 2, 1):
        for start in range(len(tokens) - span_len, 0, -1):
            span = tokens[start:start + span_len]
            if any(t == '(s)' or re.search(r'\d', t) for t in span):
                continue
            if _squash_name(' '.join(span)) in gaz:
                after = tokens[start + span_len:]
                if dock is not None and not after:
                    best = (start, span_len)  # dock row: port is last
                elif after and (re.match(r'^[\d,]', after[0]) or
                                after[0].lower() in ('qty', 'qty.', 'quantity')):
                    best = (start, span_len)  # cargo follows immediately
                if best:
                    break
        if best:
            break
    if not best:
        return None
    start, span_len = best
    ship = ' '.join(t for t in tokens[:start] if t != '(s)').strip(' ,.-')
    origin = ' '.join(tokens[start:start + span_len]).strip(' ,.-')
    cargo_str = ' '.join(tokens[start + span_len:]).strip()
    if not ship:
        return None
    return ship, '(s)' in tokens[:start], origin, cargo_str, dock


# ---------------------------------------------------------------- dash format

def split_dash_fields(text: str) -> List[str]:
    """Split a dash-format line into fields.

    Separators (in one pass):
      em/en dash with any spacing;  hyphen with space(s) around it;
      hyphen immediately followed by a capital/digit;
      hyphen followed by a lowercase cargo word when preceded by a
      capitalized word (Riga-deals splits, pit-props does not).
    """
    protected = protect_thousands(text)
    parts: List[str] = []
    buf = []
    i = 0
    n = len(protected)
    while i < n:
        ch = protected[i]
        if ch in '—–':
            parts.append(''.join(buf)); buf = []
            i += 1
            while i < n and protected[i] in ' —–-':
                i += 1
            continue
        if ch == '-':
            before = ''.join(buf)
            after = protected[i + 1:]
            spaced = (before.endswith(' ') or after.startswith(' '))
            cap_next = bool(re.match(r'\s*[A-Z0-9(]', after))
            prev_word = re.findall(r'(\S+)\s*$', before)
            prev_cap = bool(prev_word and re.match(r"^[A-Z]", prev_word[0]))
            cargo_next = bool(CARGO_START_RE.match(after.lstrip()))
            if spaced or cap_next or (prev_cap and cargo_next):
                parts.append(before); buf = []
                i += 1
                while i < n and protected[i] in ' —–-':
                    i += 1
                continue
        buf.append(ch)
        i += 1
    parts.append(''.join(buf))
    return [restore_thousands(p).strip(' ,.') for p in parts if p.strip(' ,.')]


def parse_dash_line(line: str, line_num: int, current_port: str,
                    prev_month: Optional[str]) -> Tuple[List[Shipment], Optional[str]]:
    date_str, remaining, prev_month = extract_date(line, prev_month)
    if date_str is None:
        # strip orphan day number when the month context was lost
        remaining = re.sub(r'^([0-3]?\d)(?:st|nd|rd|th)?\.?\s+(?=[A-Z])', '', remaining)
    fields = split_dash_fields(remaining)

    # cargo-only line (aggregated/continuation): no ship, just cargo list
    if len(fields) <= 2 and re.match(r'^[\d,]', remaining.strip()) and CARGO_WORD.search(remaining):
        cargo_items, merchant = parse_cargo_string(remaining)
        shp = Shipment(
            record_id=str(uuid.uuid4()), line_number=line_num, raw_text=line,
            arrival_date=date_str, ship_name='', is_steamship=False,
            origin_port='', destination_port=current_port or '',
            consignee=merchant, cargo=cargo_items, parse_confidence='low')
        return [shp], prev_month

    # separator-free line: try gazetteer rescue before giving up
    if len(fields) == 1:
        r = rescue_no_separator(remaining)
        if r:
            ship, steam, origin, cargo_str, dock = r
            merchant = None
            tm = TRAIL_MERCHANT.search(' ' + cargo_str) if cargo_str else None
            if tm:
                merchant = tm.group(1).strip()
                cargo_str = cargo_str[:tm.start()].strip(' ,')
            cargo_items, m2 = parse_cargo_string(cargo_str) if cargo_str else ([], None)
            merchant = merchant or m2
            shp = Shipment(
                record_id=str(uuid.uuid4()), line_number=line_num, raw_text=line,
                arrival_date=date_str, ship_name=ship, is_steamship=steam,
                origin_port=origin, destination_port=current_port or '',
                consignee=merchant, cargo=cargo_items, parse_confidence='medium')
            return [shp], prev_month

    ship_name = fields[0] if fields else remaining.strip()
    origin = ''
    cargo_fields: List[str] = []

    if len(fields) >= 3:
        origin = fields[1]
        cargo_fields = fields[2:]
    elif len(fields) == 2:
        # Ship-X: X is cargo if it contains digits/cargo words, else origin
        x = fields[1]
        if re.search(r'\d', x) or CARGO_WORD.search(x):
            cargo_fields = [x]
        else:
            origin = x

    is_steamship = '(s)' in ship_name
    ship_clean = ship_name.replace('(s)', '').strip(' ,.-')

    cargo_items: List[CargoItem] = []
    merchant: Optional[str] = None
    if cargo_fields:
        # fields after origin: commodity strings and/or trailing merchant field
        if len(cargo_fields) > 1 and looks_like_merchant(cargo_fields[-1]):
            merchant = cargo_fields[-1]
            cargo_fields = cargo_fields[:-1]
        cargo_items, m2 = parse_cargo_string(', '.join(cargo_fields))
        merchant = merchant or m2
    if merchant is None and len(fields) == 1:
        merchant = None

    if ship_clean and origin and cargo_items:
        confidence = 'high'
    elif ship_clean and (origin or cargo_items):
        confidence = 'medium'
    else:
        confidence = 'low'

    shp = Shipment(
        record_id=str(uuid.uuid4()), line_number=line_num, raw_text=line,
        arrival_date=date_str, ship_name=ship_clean, is_steamship=is_steamship,
        origin_port=origin, destination_port=current_port or '',
        consignee=merchant, cargo=cargo_items, parse_confidence=confidence)
    return [shp], prev_month


# ---------------------------------------------------------------- @ format

# boundary between ship units: after '.' followed by a capitalized run
# (no comma) leading to '@'
AT_UNIT_SPLIT = re.compile(r'(?<=\.)\s+(?=[A-Z][^@,;.]{0,45}@)')
AT_RE = re.compile(r'^(.*?)\s*@\s*(.*)$', re.S)
# origin ends at ',—' / '—' / ',-' / spaced '-'
AT_ORIGIN_SPLIT = re.compile(r'\s*(?:,\s*[—–-]+\s*|[—–]+\s*|,\s+(?=\d)|\s-\s|\s*;\s*)')
# commodity section prefix: "PITWOOD.—Ship @ ..." / "Lancewood Spars.—Cuban @"
AT_SECTION_RE = re.compile(r'^\s*([A-Z][A-Za-z ]{2,25})\.\s*[—–-]+\s*(?=\S)')


def parse_at_line(line: str, line_num: int, current_port: str,
                  prev_month: Optional[str]) -> Tuple[List[Shipment], Optional[str]]:
    date_str, remaining, prev_month = extract_date(line, prev_month)
    shipments: List[Shipment] = []

    # commodity section header glued to the first ship unit
    default_commodity = None
    sm = AT_SECTION_RE.match(remaining)
    if sm and '@' in remaining[sm.end():]:
        default_commodity = sm.group(1).strip().lower()
        remaining = remaining[sm.end():]

    units = AT_UNIT_SPLIT.split(remaining)
    for unit in units:
        unit = unit.strip()
        if '@' not in unit:
            continue  # editorial tail or fragment without ship data
        m = AT_RE.match(unit)
        ship_name, rest = m.group(1), m.group(2)

        # origin = up to the dash separator (or first comma before digits)
        parts = AT_ORIGIN_SPLIT.split(rest, maxsplit=1)
        origin = parts[0].strip(' ,.')
        cargo_str = parts[1].strip() if len(parts) > 1 else ''
        # strip ', &c.' from origin tail
        origin = re.sub(r',?\s*&c\.?$', '', origin).strip(' ,.')

        # garbled repeats: "(s) @ Gothenburg,—(s) @ Gothenburg,—1,135 doz."
        # keep only text after the last embedded '@' in cargo? Leave as-is;
        # cargo parser tolerates.
        is_steamship = '(s)' in ship_name or '(s)' in origin
        ship_clean = ship_name.replace('(s)', '').strip(' ,.-')
        origin = origin.replace('(s)', '').strip()

        cargo_items, merchant = parse_cargo_string(cargo_str) if cargo_str else ([], None)
        if default_commodity:
            for c in cargo_items:
                if not c.commodity:
                    c.commodity = default_commodity

        if ship_clean and origin and cargo_items:
            confidence = 'high'
        elif origin and cargo_items:
            confidence = 'medium'
        else:
            confidence = 'low'

        shipments.append(Shipment(
            record_id=str(uuid.uuid4()), line_number=line_num, raw_text=unit if len(units) > 1 else line,
            arrival_date=date_str, ship_name=ship_clean, is_steamship=is_steamship,
            origin_port=origin, destination_port=current_port or '',
            consignee=merchant, cargo=cargo_items, parse_confidence=confidence))

    return shipments, prev_month


# ---------------------------------------------------------------- driver

PORT_HEADER_RE = re.compile(r"^([A-Z][A-Z\s\-\(\)'\.&,]+)")

# a physical line that continues the previous entry (wrapped column)
CONT_MERCHANT = re.compile(r"^[A-Z][\w.\s,&']{0,40}(?:(?:Co\.?|Sons?|Bros?\.?)\s*[;,]|;)")
DAY_SHIP = re.compile(r'^\d{1,2}\s+[A-Z][a-z]')


def is_continuation(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    if t[0].islower() or t[0] in ')-—–;,&':
        return True
    m = re.match(r'^[\d,]+(?:\s+\d/\d)?\s+(\S+)', t)
    if m and not DAY_SHIP.match(t):
        nxt = m.group(1)
        if UNIT_RE.match(nxt + ' x') or CARGO_START_RE.match(nxt) or CARGO_WORD.match(nxt):
            return True
    if CONT_MERCHANT.match(t):
        return True
    return False


def parse_file(ocr_path: Path, classification_path: Path) -> Dict:
    lines = load_ocr_lines(ocr_path)
    classification = json.load(open(classification_path))
    if classification.get('status') != 'success':
        return {'source_file': ocr_path.name, 'status': 'classification_error',
                'error': classification.get('error', 'Unknown classification error')}

    line_types = {c['line']: c['type'] for c in classification.get('classifications', [])}

    # stitch wrapped column lines into logical lines first
    logical: List[Tuple[int, str, Optional[str]]] = []  # (line_num, text, port_at_line)
    current_port = None
    pending: Optional[Tuple[int, str, Optional[str]]] = None
    last_ship_line = -10

    for i, line in enumerate(lines):
        line_num = i + 1
        ltype = line_types.get(line_num, 'UNKNOWN')

        if ltype == 'PORT_HEADER':
            if pending:
                logical.append(pending)
                pending = None
            pm = PORT_HEADER_RE.match(line.strip())
            if pm:
                port = pm.group(1).strip().rstrip('.,')
                if port not in ('IMPORTS', 'IMPORT', 'EXPORTS'):
                    current_port = port
        elif ltype == 'SHIPPING_DATA':
            text = line.strip()
            if not text:
                continue
            if pending and line_num - last_ship_line <= 2 and is_continuation(text):
                pending = (pending[0], pending[1] + ' ' + text, pending[2])
            else:
                if pending:
                    logical.append(pending)
                pending = (line_num, text, current_port)
            last_ship_line = line_num
    if pending:
        logical.append(pending)

    shipments: List[Shipment] = []
    prev_month = None
    for line_num, text, port in logical:
        if '@' in text:
            new, prev_month = parse_at_line(text, line_num, port, prev_month)
        else:
            new, prev_month = parse_dash_line(text, line_num, port, prev_month)
        shipments.extend(new)

    return {
        'source_file': ocr_path.name,
        'status': 'success',
        'shipments': [asdict(s) for s in shipments],
        'shipment_count': len(shipments),
        'ports_found': sorted(set(s.destination_port for s in shipments if s.destination_port)),
    }


def main():
    import sys
    only = sys.argv[1] if len(sys.argv) > 1 else None
    cls_files = sorted(CLASSIFICATION_DIR.glob('*_classification.json'))
    total = 0
    done = 0
    for cf in cls_files:
        stem = cf.name.replace('_classification.json', '')
        if only and only not in stem:
            continue
        ocr_path = OCR_DIR / f'{stem}.txt'
        if not ocr_path.exists():
            continue
        result = parse_file(ocr_path, cf)
        out = OUTPUT_DIR / f'{stem}_parsed.json'
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=1)
        if result['status'] == 'success':
            total += result['shipment_count']
        done += 1
        if done % 200 == 0:
            print(f'{done} files, {total} shipments so far')
    print(f'DONE: {done} files, {total} shipments')


if __name__ == '__main__':
    main()
