#!/usr/bin/env python3
"""
Retry failed classifications by re-running them with Gemini.
"""

import os
import re
import json
import time
from pathlib import Path
import google.generativeai as genai

CLASSIFICATION_DIR = Path("/home/jic823/timber_data/classification")
OCR_DIR = Path("/home/jic823/timber_data/ocr_results/gemini_full")

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY not set")

genai.configure(api_key=API_KEY)

CLASSIFICATION_PROMPT = """You are classifying lines from an 1870s-1900s British timber trade journal.

For each line, determine its type. Return ONLY a JSON array with one object per line.

Line types:
- SHIPPING_DATA: Ship arrivals. Look for: ship names, @ or em-dash separators, ports like "Gothenburg", "Riga", "Quebec", cargo quantities like "5,403 deals", merchant names at end
- PORT_HEADER: British port names as section headers (LONDON, LIVERPOOL, HULL, CARDIFF, BRISTOL, GLASGOW, etc.)
- DOCK_HEADER: Sub-locations within ports (SURREY COMMERCIAL DOCKS, MILLWALL DOCKS, ALBERT DOCK, etc.)
- EDITORIAL: Market commentary, correspondent reports, narrative text about trade conditions
- ADVERTISEMENT: Product ads, company listings with addresses, price lists for services
- STATISTICAL: Numerical tables, stock statistics, comparative figures
- BUSINESS_NEWS: Bankruptcy notices, legal cases, company failures ("GAZETTE", "FAILURES")
- PAGE_MARKER: Page numbers, journal title headers, date headers at top of page
- AGGREGATED_DATA: Country-level totals like "Russia— 305 G. Russell & Co." (imports by country, not individual ships)
- BLANK: Empty or whitespace-only lines
- UNCLEAR: Cannot determine type

Key patterns for SHIPPING_DATA:
- Format 1 (1874-1876): "April 17th. Primrose (s) @ Riga,—5,555 sleepers, Order."
- Format 2 (1880s+): "Dec. 28 Myrtle-Alma, N.B.—13,749 deals—Taylor & Low Bros."
- Look for: dates (Dec. 28, April 17th), ship names, origin ports, cargo (deals, battens, staves, timber, props, boards), merchant names

Return JSON array:
[
  {"line": 1, "type": "PAGE_MARKER", "confidence": "high"},
  {"line": 2, "type": "BLANK", "confidence": "high"},
  {"line": 3, "type": "PORT_HEADER", "confidence": "high"},
  ...
]

Only output the JSON array, nothing else.

OCR TEXT TO CLASSIFY:
"""


def clean_ocr_text(text: str) -> list:
    """Remove line number prefixes from Gemini OCR output."""
    lines = []
    for line in text.split('\n'):
        cleaned = re.sub(r'^\s*\d+→', '', line)
        lines.append(cleaned)
    return lines


def find_failed_classifications():
    """Find all classification files with errors."""
    failed = []
    for cf in CLASSIFICATION_DIR.glob("*_classification.json"):
        with open(cf, 'r') as f:
            data = json.load(f)
        if data.get('status') in ('json_error', 'error'):
            failed.append(cf)
    return failed


def get_ocr_path(classification_path: Path) -> Path:
    """Get corresponding OCR file path."""
    stem = classification_path.stem.replace('_classification', '')
    return OCR_DIR / f"{stem}.txt"


def classify_file(filepath: Path, model) -> dict:
    """Classify a single OCR file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    lines = clean_ocr_text(raw_text)
    numbered_text = "\n".join(f"{i+1}: {line}" for i, line in enumerate(lines))
    prompt = CLASSIFICATION_PROMPT + numbered_text

    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()

        if response_text.startswith("```"):
            response_text = re.sub(r'^```\w*\n?', '', response_text)
            response_text = re.sub(r'\n?```$', '', response_text)

        classifications = json.loads(response_text)

        return {
            "source_file": filepath.name,
            "line_count": len(lines),
            "classifications": classifications,
            "status": "success"
        }

    except json.JSONDecodeError as e:
        return {
            "source_file": filepath.name,
            "line_count": len(lines),
            "classifications": [],
            "status": "json_error",
            "error": str(e),
            "raw_response": response_text[:1000] if 'response_text' in locals() else None
        }
    except Exception as e:
        return {
            "source_file": filepath.name,
            "line_count": len(lines),
            "classifications": [],
            "status": "error",
            "error": str(e)
        }


def main():
    print("Retrying failed classifications...")
    print("=" * 60)

    model = genai.GenerativeModel('gemini-2.0-flash')

    failed = find_failed_classifications()
    print(f"Found {len(failed)} failed classifications")

    success_count = 0
    still_failed = []

    for i, cf in enumerate(failed):
        ocr_path = get_ocr_path(cf)
        if not ocr_path.exists():
            print(f"[{i+1}/{len(failed)}] OCR not found: {ocr_path.name}")
            continue

        print(f"[{i+1}/{len(failed)}] Retrying {cf.stem[:50]}...")

        result = classify_file(ocr_path, model)

        # Save result
        with open(cf, 'w') as f:
            json.dump(result, f, indent=2)

        if result['status'] == 'success':
            success_count += 1
            print(f"  SUCCESS - {len(result['classifications'])} lines classified")
        else:
            still_failed.append(cf.name)
            print(f"  STILL FAILED: {result.get('error', 'unknown')[:50]}")

        time.sleep(1)

    print("\n" + "=" * 60)
    print(f"Retried: {len(failed)}")
    print(f"Now successful: {success_count}")
    print(f"Still failed: {len(still_failed)}")

    if still_failed:
        print("\nStill failing:")
        for name in still_failed[:10]:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
