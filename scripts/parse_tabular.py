#!/usr/bin/env python3
"""
Parser C: Tabular format (1885-1900)

Pattern: One ship per line
Format: [Date] Ship[-](s)[-]Origin[-]Cargo[-]Merchant

Uses classification JSON to identify SHIPPING_DATA lines,
then extracts structure from those lines.
"""

import os
import re
import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

# Configuration
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


def clean_ocr_line(line: str) -> str:
    """Remove line number prefix from OCR text."""
    return re.sub(r'^\s*\d+→', '', line)


def load_ocr_lines(ocr_path: Path) -> List[str]:
    """Load and clean OCR file."""
    with open(ocr_path, 'r', encoding='utf-8') as f:
        raw = f.read()
    return [clean_ocr_line(line) for line in raw.split('\n')]


def load_classification(classification_path: Path) -> Dict:
    """Load classification JSON."""
    with open(classification_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_date(text: str, prev_month: str = None) -> Tuple[Optional[str], str]:
    """Extract date from start of line, return (date_str, remaining_text).

    Handles:
    - Full date: "Dec. 24 Ship..." -> ("Dec. 24", "Ship...")
    - Day only: "25 Ship..." -> ("Dec. 25", "Ship...") (uses prev_month)
    - No date: "Ship..." -> (None, "Ship...")
    """
    # Full date pattern: Month. Day
    full_date = re.match(r'^((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.\s*\d{1,2})\s+(.+)', text)
    if full_date:
        return full_date.group(1), full_date.group(2)

    # Day only pattern
    day_only = re.match(r'^(\d{1,2})\s+(.+)', text)
    if day_only and prev_month:
        return f"{prev_month} {day_only.group(1)}", day_only.group(2)

    # No date
    return None, text


def extract_month(date_str: str) -> Optional[str]:
    """Extract month part from date string."""
    match = re.match(r'^((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.)', date_str)
    return match.group(1) if match else None


def split_ship_entry(text: str) -> Tuple[str, str, str, str]:
    """Split ship entry into (ship_name, origin, cargo_str, merchant).

    Format: Ship (s)-Origin-Cargo-Merchant
    Uses em-dash or hyphen as separator.
    """
    # Normalize separators: em-dash, en-dash, or regular dash
    # The pattern is tricky because dashes appear in place names too

    # First try em-dash (—) which is more reliable
    if '—' in text:
        parts = text.split('—')
    else:
        # Fall back to hyphen, but be more careful
        # Ship name ends at first hyphen followed by capital or after (s)
        parts = re.split(r'-(?=[A-Z])', text, maxsplit=1)
        if len(parts) == 2:
            # Now split rest at hyphens
            rest_parts = re.split(r'-(?=[A-Z0-9])', parts[1])
            parts = [parts[0]] + rest_parts

    if len(parts) < 2:
        return text, "", "", ""

    ship_name = parts[0].strip()

    if len(parts) == 2:
        # Ship-Rest format - need to parse rest further
        return ship_name, parts[1].strip(), "", ""

    origin = parts[1].strip()

    if len(parts) == 3:
        # Ship-Origin-CargoAndMerchant
        return ship_name, origin, parts[2].strip(), ""

    # Ship-Origin-Cargo-Merchant (might be multiple cargo/merchant segments)
    cargo_parts = parts[2:-1]
    merchant = parts[-1].strip()
    cargo_str = '-'.join(cargo_parts) if cargo_parts else parts[2]

    return ship_name, origin, cargo_str.strip(), merchant


def parse_cargo_and_merchants(cargo_merchant_str: str) -> Tuple[List[CargoItem], str]:
    """Parse cargo items and extract final merchant.

    Patterns:
    - "474 pcs. hewn pitch pine, 219 pcs. sawn pitch pine-Price & Co."
    - "3,415 bdls. laths-H. Sheraton & Co. ; 2,500 bdls. laths-T. W. Allen"
    - "qty. boards-Order"
    """
    cargo_items = []
    final_merchant = None

    # Split on semicolons (different merchants)
    segments = re.split(r'\s*;\s*', cargo_merchant_str)

    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue

        # Try to extract merchant (at end, after last hyphen before capital name)
        # Look for pattern: cargo-Merchant Name
        merchant_match = re.search(r'-([A-Z][A-Za-z\.\s&,]+(?:Co\.|Bros\.|Order|Captain)?)$', segment)

        if merchant_match:
            merchant = merchant_match.group(1).strip()
            cargo_str = segment[:merchant_match.start()].strip()
        else:
            merchant = None
            cargo_str = segment

        if not final_merchant:
            final_merchant = merchant

        # Parse individual cargo items (comma-separated)
        cargo_parts = re.split(r',\s*', cargo_str)

        for part in cargo_parts:
            part = part.strip()
            if not part:
                continue

            # Pattern: [quantity] [unit] commodity
            # quantity: number with optional commas, or "qty."
            # unit: pcs., bdls., fms., lds., stds., doz., etc.

            qty_match = re.match(r'^([\d,]+|qty\.?)\s*(.+)', part)
            if qty_match:
                quantity = qty_match.group(1)
                rest = qty_match.group(2).strip()

                # Check for unit
                unit_match = re.match(r'^(pcs\.|bdls\.|fms\.|lds\.|stds\.|doz\.|bxs\.|cs\.|crts\.|pkgs\.|no\.|t\.|fathoms?)\s*(.+)', rest)
                if unit_match:
                    unit = unit_match.group(1)
                    commodity = unit_match.group(2).strip()
                else:
                    unit = None
                    commodity = rest
            else:
                quantity = None
                unit = None
                commodity = part

            cargo_items.append(CargoItem(
                quantity=quantity,
                unit=unit,
                commodity=commodity,
                raw_text=part
            ))

    return cargo_items, final_merchant or "Order"


def parse_shipping_line(line: str, line_num: int, current_port: str,
                        prev_month: str) -> Tuple[Optional[Shipment], str]:
    """Parse a single shipping line.

    Returns (Shipment or None, updated prev_month).
    """
    # Extract date
    date_str, remaining = extract_date(line, prev_month)

    # Update month tracker
    if date_str:
        new_month = extract_month(date_str)
        if new_month:
            prev_month = new_month

    # Split entry
    ship_name, origin, cargo_str, merchant = split_ship_entry(remaining)

    # Check for steamship marker
    is_steamship = '(s)' in ship_name
    ship_name_clean = ship_name.replace('(s)', '').strip()

    # If we couldn't parse origin, cargo might be in origin field
    if not cargo_str and origin:
        # Try to split origin as cargo-merchant
        cargo_str = origin
        origin = ""

    # Parse cargo and merchants
    if cargo_str:
        cargo_items, final_merchant = parse_cargo_and_merchants(cargo_str + ('-' + merchant if merchant else ''))
    else:
        cargo_items = []
        final_merchant = merchant or "Order"

    # Determine parse confidence
    if ship_name_clean and cargo_items:
        confidence = "high"
    elif ship_name_clean:
        confidence = "medium"
    else:
        confidence = "low"

    shipment = Shipment(
        record_id=str(uuid.uuid4()),
        line_number=line_num,
        raw_text=line,
        arrival_date=date_str,
        ship_name=ship_name_clean,
        is_steamship=is_steamship,
        origin_port=origin,
        destination_port=current_port,
        consignee=final_merchant,
        cargo=cargo_items,
        parse_confidence=confidence
    )

    return shipment, prev_month


def parse_file(ocr_path: Path, classification_path: Path) -> Dict:
    """Parse a single file using classification data."""
    lines = load_ocr_lines(ocr_path)
    classification = load_classification(classification_path)

    if classification.get('status') != 'success':
        return {
            'source_file': ocr_path.name,
            'status': 'classification_error',
            'error': classification.get('error', 'Unknown classification error')
        }

    # Build line type lookup
    line_types = {}
    for c in classification.get('classifications', []):
        line_types[c['line']] = c['type']

    # Parse
    shipments = []
    current_port = None
    prev_month = None

    for i, line in enumerate(lines):
        line_num = i + 1  # 1-indexed
        line_type = line_types.get(line_num, 'UNKNOWN')

        if line_type == 'PORT_HEADER':
            # Extract port name
            port_match = re.match(r'^([A-Z][A-Z\s\-\(\)]+)', line.strip())
            if port_match:
                current_port = port_match.group(1).strip().rstrip('.')

        elif line_type == 'SHIPPING_DATA' and current_port:
            shipment, prev_month = parse_shipping_line(
                line.strip(), line_num, current_port, prev_month
            )
            if shipment:
                shipments.append(shipment)

    return {
        'source_file': ocr_path.name,
        'status': 'success',
        'shipments': [asdict(s) for s in shipments],
        'shipment_count': len(shipments),
        'ports_found': list(set(s.destination_port for s in shipments if s.destination_port))
    }


def extract_year_from_filename(filename: str) -> Optional[int]:
    """Extract year from filename, handling multiple formats."""
    # Try YYYYMMDD format at start (e.g., 18850101p.10)
    match1 = re.match(r'^(\d{4})', filename)
    if match1:
        year = int(match1.group(1))
        if 1870 <= year <= 1910:
            return year

    # Try 'YYYY' pattern anywhere (e.g., "January 3 1885")
    match2 = re.search(r'(18\d{2})', filename)
    if match2:
        return int(match2.group(1))

    return None


def main():
    """Process all classified tabular-era files."""
    import sys

    # Check for year range argument
    if len(sys.argv) > 1 and sys.argv[1] == "--transitional":
        year_start, year_end = 1877, 1884
        era_name = "Transitional (1877-1884)"
    else:
        year_start, year_end = 1885, 1900
        era_name = "Tabular (1885-1900)"

    print(f"{era_name} Parser")
    print("=" * 60)

    # Find all classification files for the era
    classification_files = sorted(CLASSIFICATION_DIR.glob("*_classification.json"))
    tabular_files = []

    for cf in classification_files:
        year = extract_year_from_filename(cf.name)
        if year and year_start <= year <= year_end:
            tabular_files.append(cf)

    print(f"Found {len(tabular_files)} classified tabular-era files")

    if not tabular_files:
        print("No files to process. Run classification first.")
        return

    # Process files
    total_shipments = 0
    for i, cf in enumerate(tabular_files):
        # Find corresponding OCR file
        ocr_stem = cf.stem.replace('_classification', '')
        ocr_path = OCR_DIR / f"{ocr_stem}.txt"

        if not ocr_path.exists():
            print(f"[{i+1}/{len(tabular_files)}] OCR file not found: {ocr_path.name}")
            continue

        result = parse_file(ocr_path, cf)

        # Save result
        output_path = OUTPUT_DIR / f"{ocr_stem}_parsed.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)

        if result['status'] == 'success':
            total_shipments += result['shipment_count']
            print(f"[{i+1}/{len(tabular_files)}] {ocr_stem[:40]}... → {result['shipment_count']} shipments")
        else:
            print(f"[{i+1}/{len(tabular_files)}] {ocr_stem[:40]}... → ERROR: {result.get('error', 'unknown')}")

    print("\n" + "=" * 60)
    print(f"Total shipments extracted: {total_shipments}")


if __name__ == "__main__":
    main()
