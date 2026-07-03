#!/usr/bin/env python3
"""Spot-check parsed output against raw OCR + classification.

For sampled files, reports:
  - SHIPPING_DATA lines with no parsed record (missed lines)
  - runs of >=3 consecutive missed lines (parser failure chunks)
  - parsed records with suspicious fields (digits in ship_name, cargo words
    in ship_name, empty origin on tabular lines, consignee containing digits)
Prints compact per-file stats plus a limited number of examples.
"""

import json
import glob
import random
import re
import sys
from pathlib import Path

BASE = Path('/home/jic823/timber_data')
OCR = BASE / 'ocr_results' / 'gemini_full'

CARGO_WORDS = re.compile(
    r'\b(deals?|battens?|boards?|staves|lathwood|laths|firewood|pit ?-?props?|'
    r'pitwood|sleepers|timber|spars|poles|logs|ends|pcs\.|lds\.|bdls\.|fms\.|stds\.)\b', re.I)
DIGITS = re.compile(r'\d')


def check_file(stem, examples, max_ex=4):
    cls_path = BASE / 'classification' / f'{stem}_classification.json'
    par_path = BASE / 'parsed' / f'{stem}_parsed.json'
    if not cls_path.exists() or not par_path.exists():
        return None
    cls = json.load(open(cls_path))
    par = json.load(open(par_path))
    txt_path = OCR / par['source_file']
    raw_lines = txt_path.read_text(errors='replace').split('\n') if txt_path.exists() else []

    sys.path.insert(0, str(BASE / 'scripts'))
    from parse_shipments import is_continuation
    ship_lines = {c['line'] for c in cls['classifications'] if c['type'] == 'SHIPPING_DATA'}
    parsed_lines = {s.get('line_number') for s in par.get('shipments', [])}
    missed = sorted(ln for ln in ship_lines - parsed_lines
                    if not (0 < ln <= len(raw_lines) and is_continuation(raw_lines[ln - 1])))

    # runs of consecutive missed lines
    runs = []
    for ln in missed:
        if runs and ln == runs[-1][-1] + 1:
            runs[-1].append(ln)
        else:
            runs.append([ln])
    long_runs = [r for r in runs if len(r) >= 3]

    sus = []
    for s in par.get('shipments', []):
        name = s.get('ship_name') or ''
        origin = s.get('origin_port') or ''
        cons = s.get('consignee') or ''
        reasons = []
        if DIGITS.search(name):
            reasons.append('digits_in_ship_name')
        if CARGO_WORDS.search(name):
            reasons.append('cargo_in_ship_name')
        if CARGO_WORDS.search(origin):
            reasons.append('cargo_in_origin')
        if DIGITS.search(cons):
            reasons.append('digits_in_consignee')
        if len(name) > 40:
            reasons.append('long_ship_name')
        if reasons:
            sus.append((reasons, s))

    stats = dict(stem=stem[:60], ship_lines=len(ship_lines), parsed=len(parsed_lines & ship_lines),
                 missed=len(missed), long_runs=len(long_runs),
                 longest_run=max((len(r) for r in runs), default=0), suspicious=len(sus))

    # collect examples
    for r in long_runs[:1]:
        ex_lines = [raw_lines[ln - 1] if 0 < ln <= len(raw_lines) else '?' for ln in r[:3]]
        examples.append(('MISSED_RUN', stem[:50], r[0], ex_lines))
    for reasons, s in sus[:max_ex]:
        examples.append(('SUSPICIOUS ' + ','.join(reasons), stem[:50], s.get('line_number'),
                         [s.get('raw_text', '')[:160],
                          f"ship={s.get('ship_name')!r} origin={s.get('origin_port')!r} consignee={s.get('consignee')!r}"]))
    return stats


def main():
    random.seed(42)
    stems = [Path(f).name.replace('_classification.json', '')
             for f in glob.glob(str(BASE / 'classification' / '*_classification.json'))]
    # group by year mentioned in filename
    by_year = {}
    for s in stems:
        m = re.findall(r'18[789]\d', s)
        y = m[-1] if m else 'unk'
        by_year.setdefault(y, []).append(s)
    sample = []
    for y in sorted(by_year):
        random.shuffle(by_year[y])
        sample.extend(by_year[y][:int(sys.argv[1]) if len(sys.argv) > 1 else 3])

    examples = []
    print(f"{'file':<62}{'ship':>6}{'parsed':>7}{'miss':>6}{'runs':>5}{'maxrun':>7}{'susp':>6}")
    tot = dict(ship_lines=0, parsed=0, missed=0, suspicious=0)
    for stem in sample:
        st = check_file(stem, examples)
        if not st:
            continue
        print(f"{st['stem']:<62}{st['ship_lines']:>6}{st['parsed']:>7}{st['missed']:>6}"
              f"{st['long_runs']:>5}{st['longest_run']:>7}{st['suspicious']:>6}")
        for k in tot:
            tot[k] += st[k]
    print('\nTOTALS:', tot, f"coverage={tot['parsed']/max(1,tot['ship_lines']):.1%}")
    print('\n================ EXAMPLES ================')
    for kind, stem, ln, lines in examples[:40]:
        print(f'\n[{kind}] {stem} line {ln}')
        for l in lines:
            print('   |', l[:170])


if __name__ == '__main__':
    main()
