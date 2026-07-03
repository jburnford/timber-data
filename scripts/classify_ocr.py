#!/usr/bin/env python3
"""
LLM-based line classification for Timber Trades Journal OCR files.

Uses Gemini 3 Flash to classify each line as:
- SHIPPING_DATA: Ship arrivals with cargo
- PORT_HEADER: Section headers (LONDON, CARDIFF, etc.)
- DOCK_HEADER: Sub-sections (SURREY COMMERCIAL DOCKS, etc.)
- EDITORIAL: Market commentary, correspondent reports
- ADVERTISEMENT: Product/service ads
- STATISTICAL: Tables, statistics, dock deliveries
- BUSINESS_NEWS: Failures, legal cases, gazette
- PAGE_MARKER: Page numbers, journal headers
- AGGREGATED_DATA: Country-level import totals (1877-style)
"""

import os
import re
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
import google.generativeai as genai

# Configuration
OCR_DIR = Path("/home/jic823/timber_data/ocr_results/gemini_full")
OUTPUT_DIR = Path("/home/jic823/timber_data/classification")
OUTPUT_DIR.mkdir(exist_ok=True)

# Get API key from environment
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set")

# Configure Gemini
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

def clean_ocr_text(text: str) -> List[str]:
    """Remove line number prefixes from Gemini OCR output."""
    lines = []
    for line in text.split('\n'):
        # Remove "   123→" prefix
        cleaned = re.sub(r'^\s*\d+→', '', line)
        lines.append(cleaned)
    return lines


def classify_file(filepath: Path, model) -> Dict:
    """Classify a single OCR file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    # Clean the text
    lines = clean_ocr_text(raw_text)

    # Prepare text with line numbers for classification
    numbered_text = "\n".join(f"{i+1}: {line}" for i, line in enumerate(lines))

    # Send to Gemini
    prompt = CLASSIFICATION_PROMPT + numbered_text

    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # Parse JSON response
        # Sometimes the model wraps in ```json ... ```
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


def classify_sample_files(sample_files: List[Path], model) -> List[Dict]:
    """Classify a sample of files."""
    results = []

    for i, filepath in enumerate(sample_files):
        print(f"  [{i+1}/{len(sample_files)}] Classifying {filepath.name[:50]}...")

        result = classify_file(filepath, model)
        results.append(result)

        # Save individual result
        output_path = OUTPUT_DIR / f"{filepath.stem}_classification.json"
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)

        # Rate limiting
        time.sleep(1)

    return results


def get_sample_files_by_era() -> Dict[str, List[Path]]:
    """Get sample files from each era."""
    files_by_era = {
        "dense_1874_1876": [],
        "transitional_1877_1884": [],
        "tabular_1885_1900": []
    }

    for filepath in sorted(OCR_DIR.glob("*.txt")):
        if "Zone.Identifier" in filepath.name:
            continue

        # Extract year
        year_match = re.search(r'\b(18\d{2})\b', filepath.name)
        if not year_match:
            continue

        year = int(year_match.group(1))

        if 1874 <= year <= 1876:
            files_by_era["dense_1874_1876"].append(filepath)
        elif 1877 <= year <= 1884:
            files_by_era["transitional_1877_1884"].append(filepath)
        elif 1885 <= year <= 1900:
            files_by_era["tabular_1885_1900"].append(filepath)

    return files_by_era


def get_already_classified() -> set:
    """Get set of already classified file stems."""
    classified = set()
    for f in OUTPUT_DIR.glob("*_classification.json"):
        # Extract original filename stem from classification filename
        stem = f.stem.replace("_classification", "")
        classified.add(stem)
    return classified


def classify_all_files(model, year_filter: Optional[int] = None, limit: Optional[int] = None):
    """Classify all OCR files with resume capability."""
    already_done = get_already_classified()
    print(f"Already classified: {len(already_done)} files")

    # Get all files
    all_files = sorted(OCR_DIR.glob("*.txt"))
    all_files = [f for f in all_files if "Zone.Identifier" not in f.name]

    # Apply year filter if specified
    if year_filter:
        filtered = []
        for f in all_files:
            year_match = re.search(r'\b(18\d{2})\b', f.name)
            if year_match and int(year_match.group(1)) == year_filter:
                filtered.append(f)
        all_files = filtered
        print(f"Filtering to year {year_filter}: {len(all_files)} files")

    # Skip already classified
    to_process = [f for f in all_files if f.stem not in already_done]
    print(f"Files to process: {len(to_process)}")

    if limit:
        to_process = to_process[:limit]
        print(f"Limited to: {limit} files")

    if not to_process:
        print("Nothing to process!")
        return

    # Process files
    success_count = 0
    error_count = 0
    start_time = time.time()

    for i, filepath in enumerate(to_process):
        elapsed = time.time() - start_time
        rate = (i + 1) / elapsed if elapsed > 0 else 0
        remaining = (len(to_process) - i - 1) / rate / 60 if rate > 0 else 0

        print(f"[{i+1}/{len(to_process)}] {filepath.name[:50]}... (est. {remaining:.1f}m remaining)")

        result = classify_file(filepath, model)

        # Save result
        output_path = OUTPUT_DIR / f"{filepath.stem}_classification.json"
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)

        if result['status'] == 'success':
            success_count += 1
        else:
            error_count += 1
            print(f"  ERROR: {result.get('error', 'unknown')}")

        # Rate limiting
        time.sleep(0.5)

    # Final summary
    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"CLASSIFICATION COMPLETE")
    print(f"{'='*60}")
    print(f"Processed: {len(to_process)} files in {elapsed/60:.1f} minutes")
    print(f"Success: {success_count}, Errors: {error_count}")


def main():
    """Main function."""
    import sys

    print("Initializing Gemini 3 Flash...")
    model = genai.GenerativeModel('gemini-2.0-flash')

    # Check for command line args
    if len(sys.argv) > 1:
        if sys.argv[1] == "--all":
            # Full run
            classify_all_files(model)
            return
        elif sys.argv[1] == "--year":
            # Single year
            year = int(sys.argv[2]) if len(sys.argv) > 2 else 1885
            classify_all_files(model, year_filter=year)
            return
        elif sys.argv[1] == "--test":
            # Test batch
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            classify_all_files(model, limit=limit)
            return

    # Default: sample mode
    print("\nGetting sample files by era...")
    files_by_era = get_sample_files_by_era()

    for era, files in files_by_era.items():
        print(f"  {era}: {len(files)} files")

    # Select 3 samples from each era
    samples = []
    for era, files in files_by_era.items():
        if len(files) >= 3:
            # First, middle, last
            sample = [files[0], files[len(files)//2], files[-1]]
        else:
            sample = files[:3]
        samples.extend(sample)
        print(f"\n{era} samples:")
        for s in sample:
            print(f"  - {s.name[:60]}")

    print(f"\nTotal samples to classify: {len(samples)}")

    # Classify samples
    print("\nStarting classification...")
    results = classify_sample_files(samples, model)

    # Summary
    print("\n" + "="*60)
    print("CLASSIFICATION SUMMARY")
    print("="*60)

    for result in results:
        print(f"\n{result['source_file'][:50]}...")
        print(f"  Status: {result['status']}")
        if result['status'] == 'success':
            # Count types
            type_counts = {}
            for c in result['classifications']:
                t = c.get('type', 'UNKNOWN')
                type_counts[t] = type_counts.get(t, 0) + 1
            for t, count in sorted(type_counts.items()):
                print(f"    {t}: {count}")


if __name__ == "__main__":
    main()
