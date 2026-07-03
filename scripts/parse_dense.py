#!/usr/bin/env python3
"""
Parser A: Dense format (1874-1876)

Pattern: Multiple ships per paragraph, semicolon-separated cargo
Format: Date. Ship (s) @ Origin,—Cargo, Merchant; Cargo, Merchant. NextShip @ Origin,—...

Uses Gemini for tokenization since structure is too complex for regex alone.
All extracted tokens are verified to exist verbatim in original text.
"""

import os
import re
import json
import uuid
import time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import google.generativeai as genai

# Configuration
OCR_DIR = Path("/home/jic823/timber_data/ocr_results/gemini_full")
CLASSIFICATION_DIR = Path("/home/jic823/timber_data/classification")
OUTPUT_DIR = Path("/home/jic823/timber_data/parsed")
OUTPUT_DIR.mkdir(exist_ok=True)

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY not set")

genai.configure(api_key=API_KEY)

TOKENIZE_PROMPT = """You are parsing 19th century timber shipping records.

For the line below, identify ALL ships and their cargo. Return a JSON structure.

CRITICAL RULES:
1. Every text value MUST be copied EXACTLY from the original - no rewording
2. Multiple ships may appear in one line, separated by periods or new ship names
3. Each ship has: name, origin port, and one or more cargo items
4. Each cargo item has: quantity (optional), unit (optional), commodity, merchant
5. Ship names often have (s) for steamship
6. @ or — separates ship name from origin port
7. Semicolons often separate cargo items within same ship
8. "Order" means no specific merchant named

Return JSON format:
{
  "ships": [
    {
      "ship_name": "exact text from line",
      "origin_port": "exact text from line",
      "cargo": [
        {
          "quantity": "exact text or null",
          "unit": "exact text or null",
          "commodity": "exact text",
          "merchant": "exact text or null"
        }
      ]
    }
  ],
  "unparseable_segments": ["any text that doesn't fit ship/cargo pattern"],
  "parse_confidence": "high/medium/low"
}

LINE TO PARSE:
"""


@dataclass
class CargoItem:
    quantity: Optional[str]
    unit: Optional[str]
    commodity: str
    merchant: Optional[str]
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
    cargo: List[CargoItem]
    parse_confidence: str
    verified_tokens: int
    total_tokens: int


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


def verify_tokens_in_original(result: dict, original_line: str) -> Dict:
    """Check that all extracted tokens exist verbatim in the original line."""
    verification = {
        "total_tokens": 0,
        "verified_tokens": 0,
        "failed_tokens": []
    }

    for ship in result.get("ships", []):
        if ship.get("ship_name"):
            verification["total_tokens"] += 1
            if ship["ship_name"] in original_line:
                verification["verified_tokens"] += 1
            else:
                verification["failed_tokens"].append(("ship_name", ship["ship_name"]))

        if ship.get("origin_port"):
            verification["total_tokens"] += 1
            if ship["origin_port"] in original_line:
                verification["verified_tokens"] += 1
            else:
                verification["failed_tokens"].append(("origin_port", ship["origin_port"]))

        for cargo in ship.get("cargo", []):
            for field in ["quantity", "unit", "commodity", "merchant"]:
                if cargo.get(field):
                    verification["total_tokens"] += 1
                    if cargo[field] in original_line:
                        verification["verified_tokens"] += 1
                    else:
                        verification["failed_tokens"].append((field, cargo[field]))

    return verification


def tokenize_dense_line(model, line: str) -> Optional[Dict]:
    """Use Gemini to tokenize a dense shipping line."""
    prompt = TOKENIZE_PROMPT + line

    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # Clean JSON from markdown code blocks
        if response_text.startswith("```"):
            response_text = re.sub(r'^```\w*\n?', '', response_text)
            response_text = re.sub(r'\n?```$', '', response_text)

        result = json.loads(response_text)
        return result

    except Exception as e:
        return None


def extract_date_from_line(line: str) -> Optional[str]:
    """Extract date from start of dense line."""
    # Pattern: "April 16." or "April 16th." or "May 2nd."
    date_match = re.match(r'^((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?\.?)', line)
    return date_match.group(1) if date_match else None


def parse_dense_shipping_line(model, line: str, line_num: int, current_port: str) -> List[Shipment]:
    """Parse a dense shipping line using LLM tokenization."""
    shipments = []

    # Extract date
    arrival_date = extract_date_from_line(line)

    # Tokenize using Gemini
    result = tokenize_dense_line(model, line)
    if not result:
        return shipments

    # Verify tokens
    verification = verify_tokens_in_original(result, line)

    # Convert to shipments
    for ship_data in result.get("ships", []):
        ship_name = ship_data.get("ship_name") or ""
        is_steamship = "(s)" in ship_name
        ship_name_clean = ship_name.replace("(s)", "").strip()

        if not ship_name_clean:
            continue  # Skip ships without names

        cargo_items = []
        for cargo_data in ship_data.get("cargo", []):
            cargo_items.append(CargoItem(
                quantity=cargo_data.get("quantity"),
                unit=cargo_data.get("unit"),
                commodity=cargo_data.get("commodity", ""),
                merchant=cargo_data.get("merchant"),
                raw_text=f"{cargo_data.get('quantity', '')} {cargo_data.get('unit', '')} {cargo_data.get('commodity', '')}".strip()
            ))

        shipment = Shipment(
            record_id=str(uuid.uuid4()),
            line_number=line_num,
            raw_text=line,
            arrival_date=arrival_date,
            ship_name=ship_name_clean,
            is_steamship=is_steamship,
            origin_port=ship_data.get("origin_port", ""),
            destination_port=current_port,
            cargo=cargo_items,
            parse_confidence=result.get("parse_confidence", "medium"),
            verified_tokens=verification["verified_tokens"],
            total_tokens=verification["total_tokens"]
        )
        shipments.append(shipment)

    return shipments


def parse_file(ocr_path: Path, classification_path: Path, model) -> Dict:
    """Parse a single dense-format file."""
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

    for i, line in enumerate(lines):
        line_num = i + 1
        line_type = line_types.get(line_num, 'UNKNOWN')
        line_stripped = line.strip()

        if line_type == 'PORT_HEADER':
            port_match = re.match(r'^([A-Z][A-Z\s\-\(\)]+)', line_stripped)
            if port_match:
                current_port = port_match.group(1).strip().rstrip('.')

        elif line_type == 'SHIPPING_DATA' and current_port and line_stripped:
            line_shipments = parse_dense_shipping_line(model, line_stripped, line_num, current_port)
            shipments.extend(line_shipments)
            time.sleep(0.3)  # Rate limiting

    return {
        'source_file': ocr_path.name,
        'status': 'success',
        'shipments': [asdict(s) for s in shipments],
        'shipment_count': len(shipments),
        'ports_found': list(set(s.destination_port for s in shipments if s.destination_port))
    }


def extract_year_from_filename(filename: str) -> Optional[int]:
    """Extract year from filename, handling multiple formats."""
    # Try YYYYMMDD format at start (e.g., 18750101p.10)
    match1 = re.match(r'^(\d{4})', filename)
    if match1:
        year = int(match1.group(1))
        if 1870 <= year <= 1910:
            return year

    # Try 'YYYY' pattern anywhere (e.g., "January 3 1875")
    match2 = re.search(r'(18\d{2})', filename)
    if match2:
        return int(match2.group(1))

    return None


def main():
    """Process classified dense-era files."""
    print("Dense Parser (1874-1876)")
    print("=" * 60)

    model = genai.GenerativeModel('gemini-2.0-flash')

    # Find classification files for 1874-1876
    classification_files = sorted(CLASSIFICATION_DIR.glob("*_classification.json"))
    dense_files = []

    for cf in classification_files:
        year = extract_year_from_filename(cf.name)
        if year and 1874 <= year <= 1876:
            dense_files.append(cf)

    print(f"Found {len(dense_files)} classified dense-era files")

    if not dense_files:
        print("No files to process. Run classification first.")
        return

    # Process files
    total_shipments = 0
    for i, cf in enumerate(dense_files):
        ocr_stem = cf.stem.replace('_classification', '')
        ocr_path = OCR_DIR / f"{ocr_stem}.txt"

        if not ocr_path.exists():
            print(f"[{i+1}/{len(dense_files)}] OCR file not found: {ocr_path.name}")
            continue

        result = parse_file(ocr_path, cf, model)

        # Save result
        output_path = OUTPUT_DIR / f"{ocr_stem}_parsed.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)

        if result['status'] == 'success':
            total_shipments += result['shipment_count']
            print(f"[{i+1}/{len(dense_files)}] {ocr_stem[:40]}... → {result['shipment_count']} shipments")
        else:
            print(f"[{i+1}/{len(dense_files)}] {ocr_stem[:40]}... → ERROR")

    print("\n" + "=" * 60)
    print(f"Total shipments extracted: {total_shipments}")


if __name__ == "__main__":
    main()
