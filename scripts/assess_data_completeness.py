#!/usr/bin/env python3
"""
Data Completeness Assessment for Timber Trades Journal OCR files.

This script surveys all OCR files to identify:
1. Which years are covered
2. Which ports are present in each year
3. Which ports use individual ship listings vs aggregated reporting
4. Format patterns by era
"""

import os
import re
import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple

# Directories
OCR_DIR = Path("/home/jic823/timber_data/ocr_results/gemini_full")
OUTPUT_DIR = Path("/home/jic823/timber_data")

# Known port headers (British destination ports)
MAJOR_PORTS = [
    "LONDON", "LIVERPOOL", "HULL", "BRISTOL", "CARDIFF", "GLASGOW",
    "NEWCASTLE", "GRIMSBY", "SUNDERLAND", "LEITH", "NEWPORT",
    "SWANSEA", "HARTLEPOOL", "GOOLE", "MIDDLESBROUGH", "TYNE",
    "SOUTHAMPTON", "GRANGEMOUTH", "GREENOCK", "DUNDEE", "BO'NESS",
    "BARROW", "GLOUCESTER", "ROCHESTER", "FALMOUTH", "FAVERSHAM"
]

# Patterns indicating individual ship records
SHIP_PATTERNS = [
    r'[A-Z][a-z]+\s*@\s*[A-Z]',  # Ship @ Port (1874-style)
    r'[A-Z][a-z]+-[A-Z][a-z]+',   # Ship-Origin (1880s+ style)
    r'\([s]\)',                    # Steamship indicator
    r'\d+\s+(?:pcs|doz|fms|lds|bdls|stds)\.',  # Cargo quantities
]

# Patterns indicating aggregated/statistical reporting
AGGREGATE_PATTERNS = [
    r'Russia—\s*\d+',
    r'Prussia—\s*\d+',
    r'Sweden—\s*\d+',
    r'Norway—\s*\d+',
    r'Quebec—\s*\d+',
    r'Hewn Timber \(loads\)',
    r'Sawn Timber \(loads\)',
    r'From [A-Z][a-z]+ \d+(?:st|nd|rd|th) to [A-Z][a-z]+ \d+',
]


def extract_year_from_filename(filename: str) -> str:
    """Extract year from various filename formats."""
    # Try YYYYMMDD format at start
    if match := re.match(r'^(\d{4})\d{4}', filename):
        return match.group(1)
    # Try "Month D YYYY" format
    if match := re.search(r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+\s+(\d{4})', filename):
        return match.group(1)
    # Try just YYYY anywhere in filename
    if match := re.search(r'\b(18\d{2}|19\d{2})\b', filename):
        return match.group(1)
    return "unknown"


def find_ports_in_text(text: str) -> Set[str]:
    """Find port headers in OCR text."""
    found_ports = set()
    for port in MAJOR_PORTS:
        # Look for port name as header (standalone or with period)
        if re.search(rf'^{port}\.?\s*$', text, re.MULTILINE | re.IGNORECASE):
            found_ports.add(port)
        # Also look for port name followed by dock names
        if re.search(rf'{port}\s*\n', text, re.IGNORECASE):
            found_ports.add(port)
    return found_ports


def detect_reporting_style(text: str, port: str) -> Tuple[str, List[str]]:
    """
    Detect if a port section uses individual ships or aggregated reporting.

    Returns: (style, evidence)
        style: 'individual', 'aggregated', 'mixed', or 'unclear'
        evidence: list of example matches
    """
    individual_evidence = []
    aggregate_evidence = []

    # Extract the section for this port (rough extraction)
    port_pattern = rf'{port}\.?\s*\n(.*?)(?:^[A-Z][A-Z]+\.?\s*$|\Z)'
    port_match = re.search(port_pattern, text, re.MULTILINE | re.DOTALL | re.IGNORECASE)

    if not port_match:
        return 'not_found', []

    section = port_match.group(1)[:2000]  # First 2000 chars of section

    # Check for individual ship patterns
    for pattern in SHIP_PATTERNS:
        matches = re.findall(pattern, section)
        individual_evidence.extend(matches[:3])

    # Check for aggregate patterns
    for pattern in AGGREGATE_PATTERNS:
        matches = re.findall(pattern, section)
        aggregate_evidence.extend(matches[:3])

    # Determine style
    has_individual = len(individual_evidence) > 0
    has_aggregate = len(aggregate_evidence) > 0

    if has_individual and has_aggregate:
        return 'mixed', individual_evidence[:2] + aggregate_evidence[:2]
    elif has_individual:
        return 'individual', individual_evidence[:4]
    elif has_aggregate:
        return 'aggregated', aggregate_evidence[:4]
    else:
        return 'unclear', []


def analyze_file(filepath: Path) -> Dict:
    """Analyze a single OCR file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    # Strip line numbers from Gemini OCR output
    lines = []
    for line in text.split('\n'):
        # Remove "   123→" prefix
        cleaned = re.sub(r'^\s*\d+→', '', line)
        lines.append(cleaned)
    text = '\n'.join(lines)

    ports = find_ports_in_text(text)

    port_analysis = {}
    for port in ports:
        style, evidence = detect_reporting_style(text, port)
        port_analysis[port] = {
            'style': style,
            'evidence': evidence
        }

    return {
        'filename': filepath.name,
        'line_count': len(lines),
        'ports_found': list(ports),
        'port_analysis': port_analysis
    }


def main():
    """Main analysis function."""
    print("Scanning OCR files...")

    # Group files by year
    files_by_year = defaultdict(list)

    for filepath in sorted(OCR_DIR.glob("*.txt")):
        if "Zone.Identifier" in filepath.name:
            continue
        year = extract_year_from_filename(filepath.name)
        files_by_year[year].append(filepath)

    print(f"Found {sum(len(f) for f in files_by_year.values())} files across {len(files_by_year)} years")

    # Analyze sample files from each year
    report = {
        'summary': {
            'total_files': sum(len(f) for f in files_by_year.values()),
            'years_covered': sorted(files_by_year.keys()),
            'files_per_year': {y: len(f) for y, f in sorted(files_by_year.items())}
        },
        'by_year': {}
    }

    for year in sorted(files_by_year.keys()):
        if year == 'unknown':
            continue

        files = files_by_year[year]
        print(f"\nAnalyzing {year}: {len(files)} files")

        # Sample up to 5 files per year
        sample_files = files[:5] if len(files) <= 5 else [
            files[0],
            files[len(files)//4],
            files[len(files)//2],
            files[3*len(files)//4],
            files[-1]
        ]

        year_analysis = {
            'file_count': len(files),
            'samples_analyzed': len(sample_files),
            'ports_seen': set(),
            'port_styles': defaultdict(lambda: {'individual': 0, 'aggregated': 0, 'mixed': 0, 'unclear': 0}),
            'sample_details': []
        }

        for filepath in sample_files:
            try:
                analysis = analyze_file(filepath)
                year_analysis['sample_details'].append(analysis)
                year_analysis['ports_seen'].update(analysis['ports_found'])

                for port, data in analysis['port_analysis'].items():
                    year_analysis['port_styles'][port][data['style']] += 1
            except Exception as e:
                print(f"  Error analyzing {filepath.name}: {e}")

        # Convert sets to lists for JSON
        year_analysis['ports_seen'] = sorted(year_analysis['ports_seen'])
        year_analysis['port_styles'] = dict(year_analysis['port_styles'])

        # Determine likely style for major ports
        major_port_summary = {}
        for port in ['LONDON', 'LIVERPOOL', 'HULL', 'BRISTOL', 'CARDIFF', 'GLASGOW']:
            if port in year_analysis['port_styles']:
                styles = year_analysis['port_styles'][port]
                dominant = max(styles.keys(), key=lambda k: styles[k])
                major_port_summary[port] = dominant
            else:
                major_port_summary[port] = 'not_found'

        year_analysis['major_port_summary'] = major_port_summary
        report['by_year'][year] = year_analysis

        # Print summary
        print(f"  Ports found: {', '.join(year_analysis['ports_seen'][:10])}")
        print(f"  LONDON style: {major_port_summary.get('LONDON', 'N/A')}")

    # Save report
    output_path = OUTPUT_DIR / "data_completeness_report.json"

    # Convert defaultdicts for JSON serialization
    for year_data in report['by_year'].values():
        year_data['port_styles'] = {k: dict(v) for k, v in year_data['port_styles'].items()}

    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\n\nReport saved to: {output_path}")

    # Print findings summary
    print("\n" + "="*60)
    print("KEY FINDINGS: LONDON Reporting Style by Year")
    print("="*60)
    for year in sorted(report['by_year'].keys()):
        london_style = report['by_year'][year]['major_port_summary'].get('LONDON', 'N/A')
        file_count = report['by_year'][year]['file_count']
        print(f"  {year}: {london_style:12} ({file_count} files)")


if __name__ == "__main__":
    main()
