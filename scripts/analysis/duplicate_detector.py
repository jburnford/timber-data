#!/usr/bin/env python3
"""
Duplicate Detector for Timber Shipment Data

Identifies duplicate and near-duplicate records:
- Exact raw_text duplicates within same file
- Same ship_name + arrival_date + origin_port combinations
- LLM hallucination loops (same raw_text 5+ times per file)
"""

import json
import os
import csv
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Tuple, Set


class DuplicateDetector:
    """Detects duplicate records in shipment data."""

    def __init__(self, parsed_dir: str, output_dir: str):
        self.parsed_dir = Path(parsed_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Track duplicates
        self.exact_duplicates = []  # Exact raw_text matches within a file
        self.key_duplicates = []    # Same ship+date+port combinations
        self.hallucination_loops = []  # 5+ repetitions of same raw_text

        # Summary stats
        self.total_files = 0
        self.total_shipments = 0
        self.files_with_duplicates = set()
        self.duplicate_counts = defaultdict(int)

    def analyze_file(self, filepath: Path) -> Dict[str, Any]:
        """Analyze a single file for duplicates."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            return {'error': str(e)}

        filename = filepath.name
        shipments = data.get('shipments', [])

        # Track raw_text occurrences within this file
        raw_text_counts = defaultdict(list)

        # Track key combinations
        key_combinations = defaultdict(list)

        for idx, shipment in enumerate(shipments):
            raw_text = shipment.get('raw_text', '')
            ship_name = shipment.get('ship_name', '') or ''
            arrival_date = shipment.get('arrival_date', '') or ''
            origin_port = shipment.get('origin_port', '') or ''
            record_id = shipment.get('record_id', f'idx_{idx}')

            # Track raw_text
            if raw_text:
                raw_text_counts[raw_text].append({
                    'record_id': record_id,
                    'line_number': shipment.get('line_number'),
                    'ship_name': ship_name,
                    'arrival_date': arrival_date,
                    'origin_port': origin_port
                })

            # Track key combinations
            key = f"{ship_name.lower().strip()}|{arrival_date.lower().strip()}|{origin_port.lower().strip()}"
            if ship_name and arrival_date:  # Only track if we have meaningful key
                key_combinations[key].append({
                    'record_id': record_id,
                    'raw_text': raw_text[:100] if raw_text else '',
                    'line_number': shipment.get('line_number')
                })

        file_issues = {
            'exact_duplicates': 0,
            'key_duplicates': 0,
            'hallucination_loops': 0
        }

        # Check for exact duplicates (2+ occurrences)
        for raw_text, records in raw_text_counts.items():
            if len(records) >= 2:
                file_issues['exact_duplicates'] += len(records) - 1
                self.exact_duplicates.append({
                    'file': filename,
                    'raw_text': raw_text[:150],
                    'count': len(records),
                    'records': records
                })
                self.files_with_duplicates.add(filename)

            # Check for hallucination loops (5+ occurrences)
            if len(records) >= 5:
                file_issues['hallucination_loops'] += 1
                self.hallucination_loops.append({
                    'file': filename,
                    'raw_text': raw_text[:150],
                    'count': len(records),
                    'records': records[:10]  # Limit sample
                })

        # Check for key duplicates (same ship+date+port)
        for key, records in key_combinations.items():
            if len(records) >= 2:
                # Only count if different raw_texts (not just exact dupes)
                raw_texts = set(r['raw_text'] for r in records)
                if len(raw_texts) > 1:
                    file_issues['key_duplicates'] += len(records) - 1
                    parts = key.split('|')
                    self.key_duplicates.append({
                        'file': filename,
                        'ship_name': parts[0] if len(parts) > 0 else '',
                        'arrival_date': parts[1] if len(parts) > 1 else '',
                        'origin_port': parts[2] if len(parts) > 2 else '',
                        'count': len(records),
                        'records': records
                    })
                    self.files_with_duplicates.add(filename)

        # Update counters
        for issue_type, count in file_issues.items():
            self.duplicate_counts[issue_type] += count

        return {
            'filename': filename,
            'shipments': len(shipments),
            'issues': file_issues
        }

    def analyze_all(self, verbose: bool = False) -> Dict[str, Any]:
        """Analyze all parsed files."""
        json_files = list(self.parsed_dir.glob('*_parsed.json'))
        self.total_files = len(json_files)

        if verbose:
            print(f"Analyzing {self.total_files} files for duplicates...")

        for i, filepath in enumerate(json_files):
            if verbose and (i + 1) % 200 == 0:
                print(f"  Processed {i + 1}/{self.total_files} files...")

            result = self.analyze_file(filepath)
            if 'shipments' in result:
                self.total_shipments += result['shipments']

        return self.generate_report()

    def generate_report(self) -> Dict[str, Any]:
        """Generate the duplicate detection report."""
        # Calculate total duplicate records
        total_exact = sum(d['count'] - 1 for d in self.exact_duplicates)
        total_key = sum(d['count'] - 1 for d in self.key_duplicates)
        total_hallucination_records = sum(d['count'] for d in self.hallucination_loops)

        report = {
            'summary': {
                'total_files': self.total_files,
                'total_shipments': self.total_shipments,
                'files_with_duplicates': len(self.files_with_duplicates),
                'exact_duplicate_records': total_exact,
                'key_duplicate_records': total_key,
                'hallucination_loop_incidents': len(self.hallucination_loops),
                'hallucination_loop_records': total_hallucination_records
            },
            'exact_duplicates': {
                'total_incidents': len(self.exact_duplicates),
                'total_extra_records': total_exact,
                'samples': sorted(self.exact_duplicates, key=lambda x: -x['count'])[:50]
            },
            'key_duplicates': {
                'total_incidents': len(self.key_duplicates),
                'total_extra_records': total_key,
                'samples': sorted(self.key_duplicates, key=lambda x: -x['count'])[:50]
            },
            'hallucination_loops': {
                'total_incidents': len(self.hallucination_loops),
                'total_records': total_hallucination_records,
                'samples': sorted(self.hallucination_loops, key=lambda x: -x['count'])[:30]
            },
            'affected_files': sorted(self.files_with_duplicates)
        }

        return report

    def save_report(self, report: Dict[str, Any]):
        """Save report to JSON and CSV formats."""
        # Save JSON
        json_path = self.output_dir / 'duplicates_by_file.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)

        # Save CSV of duplicate records
        csv_path = self.output_dir / 'duplicate_records.csv'
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'type', 'file', 'raw_text', 'ship_name', 'arrival_date',
                'origin_port', 'count', 'record_ids'
            ])

            # Write exact duplicates
            for dup in self.exact_duplicates:
                record_ids = ','.join(r['record_id'] for r in dup['records'])
                writer.writerow([
                    'exact_duplicate',
                    dup['file'],
                    dup['raw_text'],
                    dup['records'][0].get('ship_name', ''),
                    dup['records'][0].get('arrival_date', ''),
                    dup['records'][0].get('origin_port', ''),
                    dup['count'],
                    record_ids
                ])

            # Write key duplicates
            for dup in self.key_duplicates:
                record_ids = ','.join(r['record_id'] for r in dup['records'])
                writer.writerow([
                    'key_duplicate',
                    dup['file'],
                    '',
                    dup['ship_name'],
                    dup['arrival_date'],
                    dup['origin_port'],
                    dup['count'],
                    record_ids
                ])

            # Write hallucination loops
            for loop in self.hallucination_loops:
                record_ids = ','.join(r['record_id'] for r in loop['records'])
                writer.writerow([
                    'hallucination_loop',
                    loop['file'],
                    loop['raw_text'],
                    '',
                    '',
                    '',
                    loop['count'],
                    record_ids
                ])

        print(f"Saved reports to:")
        print(f"  - {json_path}")
        print(f"  - {csv_path}")

        return json_path, csv_path


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Detect duplicates in parsed shipment files')
    parser.add_argument('--parsed-dir', default='/home/jic823/timber_data/parsed',
                        help='Directory containing parsed JSON files')
    parser.add_argument('--output-dir', default='/home/jic823/timber_data/reports',
                        help='Directory for output reports')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show progress during analysis')

    args = parser.parse_args()

    detector = DuplicateDetector(args.parsed_dir, args.output_dir)
    report = detector.analyze_all(verbose=args.verbose)
    detector.save_report(report)

    # Print summary
    print("\n" + "=" * 50)
    print("DUPLICATE DETECTION COMPLETE")
    print("=" * 50)
    print(f"Files analyzed: {report['summary']['total_files']:,}")
    print(f"Files with duplicates: {report['summary']['files_with_duplicates']:,}")
    print(f"Exact duplicate records: {report['summary']['exact_duplicate_records']:,}")
    print(f"Key duplicate records: {report['summary']['key_duplicate_records']:,}")
    print(f"Hallucination loops: {report['summary']['hallucination_loop_incidents']:,}")
    print(f"  (affecting {report['summary']['hallucination_loop_records']:,} records)")


if __name__ == '__main__':
    main()
