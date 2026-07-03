#!/usr/bin/env python3
"""
Classify long OCR files by processing in chunks.
Handles files that exceed Gemini's output token limit.
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
- SHIPPING_DATA: Ship arrivals with cargo details
- PORT_HEADER: British port names (LONDON, LIVERPOOL, HULL, etc.)
- DOCK_HEADER: Sub-locations (SURREY COMMERCIAL DOCKS, etc.)
- EDITORIAL: Market commentary, narrative text
- ADVERTISEMENT: Product ads, company listings
- STATISTICAL: Numerical tables, statistics
- BUSINESS_NEWS: Bankruptcy notices, legal cases
- PAGE_MARKER: Page numbers, journal headers
- AGGREGATED_DATA: Country-level totals
- BLANK: Empty lines
- UNCLEAR: Cannot determine

Return JSON array like:
[{"line": 1, "type": "PAGE_MARKER", "confidence": "high"}, ...]

Only output the JSON array, nothing else.

OCR TEXT TO CLASSIFY:
"""

CHUNK_SIZE = 100  # Lines per chunk


def clean_ocr_text(text: str) -> list:
    lines = []
    for line in text.split('\n'):
        cleaned = re.sub(r'^\s*\d+→', '', line)
        lines.append(cleaned)
    return lines


def find_failed_classifications():
    failed = []
    for cf in CLASSIFICATION_DIR.glob("*_classification.json"):
        with open(cf, 'r') as f:
            data = json.load(f)
        if data.get('status') in ('json_error', 'error'):
            failed.append(cf)
    return failed


def get_ocr_path(classification_path: Path) -> Path:
    stem = classification_path.stem.replace('_classification', '')
    return OCR_DIR / f"{stem}.txt"


def classify_chunk(lines: list, start_line: int, model) -> list:
    """Classify a chunk of lines."""
    numbered_text = "\n".join(f"{start_line + i}: {line}" for i, line in enumerate(lines))
    prompt = CLASSIFICATION_PROMPT + numbered_text

    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()

        if response_text.startswith("```"):
            response_text = re.sub(r'^```\w*\n?', '', response_text)
            response_text = re.sub(r'\n?```$', '', response_text)

        return json.loads(response_text)
    except Exception as e:
        print(f"    Chunk error at line {start_line}: {e}")
        # Return basic classifications for failed chunk
        return [{"line": start_line + i, "type": "UNCLEAR", "confidence": "low"}
                for i in range(len(lines))]


def classify_file_chunked(filepath: Path, model) -> dict:
    """Classify a file by processing in chunks."""
    with open(filepath, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    lines = clean_ocr_text(raw_text)
    all_classifications = []

    # Process in chunks
    for i in range(0, len(lines), CHUNK_SIZE):
        chunk = lines[i:i + CHUNK_SIZE]
        start_line = i + 1  # 1-indexed

        print(f"    Processing lines {start_line}-{start_line + len(chunk) - 1}...")
        chunk_results = classify_chunk(chunk, start_line, model)
        all_classifications.extend(chunk_results)
        time.sleep(0.5)  # Rate limiting

    return {
        "source_file": filepath.name,
        "line_count": len(lines),
        "classifications": all_classifications,
        "status": "success"
    }


def main():
    print("Classifying long files in chunks...")
    print("=" * 60)

    model = genai.GenerativeModel('gemini-2.0-flash')

    failed = find_failed_classifications()
    print(f"Found {len(failed)} failed classifications")

    success_count = 0

    for i, cf in enumerate(failed):
        ocr_path = get_ocr_path(cf)
        if not ocr_path.exists():
            print(f"[{i+1}/{len(failed)}] OCR not found: {ocr_path.name}")
            continue

        # Check line count
        with open(cf, 'r') as f:
            data = json.load(f)
        line_count = data.get('line_count', 0)

        print(f"[{i+1}/{len(failed)}] {cf.stem[:50]}... ({line_count} lines)")

        result = classify_file_chunked(ocr_path, model)

        with open(cf, 'w') as f:
            json.dump(result, f, indent=2)

        if result['status'] == 'success':
            success_count += 1
            print(f"  SUCCESS - {len(result['classifications'])} lines classified")

    print("\n" + "=" * 60)
    print(f"Processed: {len(failed)}")
    print(f"Successful: {success_count}")

    # Verify
    remaining = len(list(CLASSIFICATION_DIR.glob("*_classification.json")))
    errors = sum(1 for cf in CLASSIFICATION_DIR.glob("*_classification.json")
                 if json.load(open(cf)).get('status') != 'success')
    print(f"Total classifications: {remaining}")
    print(f"Remaining errors: {errors}")


if __name__ == "__main__":
    main()
