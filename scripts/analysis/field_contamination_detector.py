#!/usr/bin/env python3
"""
Field Contamination Detector for Timber Shipment Data

Finds data in wrong fields:
- Cargo keywords in ship_name field
- Consignee patterns in port fields
- Multi-line fragments (ship_name starting with date or containing quantities)
"""

import json
import re
import csv
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Optional


class FieldContaminationDetector:
    """Detects field contamination in shipment data."""

    # Cargo keywords that shouldn't appear in ship_name
    CARGO_KEYWORDS = [
        'deals', 'boards', 'planks', 'staves', 'timber', 'logs',
        'battens', 'laths', 'sleepers', 'props', 'pcs.', 'lds.',
        'standards', 'loads', 'pieces', 'fathoms', 'tons', 'cwt.',
        'spars', 'poles', 'pitwood', 'oak', 'pine', 'fir', 'spruce',
        'ash', 'elm', 'beech', 'mahogany', 'teak', 'cedar', 'walnut',
        'birch', 'maple', 'poplar', 'hewn', 'sawn', 'planed'
    ]

    # Consignee patterns that shouldn't appear in port fields
    CONSIGNEE_PATTERNS = [
        r'& Co\.?',
        r'& Sons',
        r'& Son',
        r'\bOrder\b',
        r'\bBros\.?',
        r'\bLtd\.?',
        r'\bLimited\b',
        r'& Cie',
        r'& Company',
        r'\bAgent[s]?\b'
    ]

    # Date patterns that indicate multi-line contamination
    DATE_PATTERNS = [
        r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s*\d',
        r'^\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)',
        r'^\d{1,2}/\d{1,2}',
        r'^\d{1,2}\.\d{1,2}\.'
    ]

    # Quantity patterns that indicate cargo data
    QUANTITY_PATTERNS = [
        r'\d+\s*(pcs\.|lds\.|stds\.|loads|pieces|tons|cwt\.|fathoms)',
        r'\d+,\d+\s*(pcs\.|lds\.|stds\.|loads)',
        r'^\d+\s+\w+\s+deals',
        r'^\d+\s+\w+\s+boards'
    ]

    def __init__(self, parsed_dir: str, output_dir: str):
        self.parsed_dir = Path(parsed_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Track contamination by type
        self.cargo_in_ship_name = []
        self.consignee_in_port = []
        self.date_in_ship_name = []
        self.quantity_in_ship_name = []
        self.misc_contamination = []

        # Summary stats
        self.contamination_counts = defaultdict(int)
        self.total_files = 0
        self.total_shipments = 0

    def detect_cargo_in_ship_name(self, ship_name: str) -> Optional[Dict[str, Any]]:
        """Check if ship_name contains cargo keywords."""
        if not ship_name:
            return None

        ship_lower = ship_name.lower()
        found_keywords = []

        for keyword in self.CARGO_KEYWORDS:
            if keyword.lower() in ship_lower:
                found_keywords.append(keyword)

        if found_keywords:
            return {
                'value': ship_name,
                'keywords_found': found_keywords
            }
        return None

    def detect_consignee_in_port(self, port: str) -> Optional[Dict[str, Any]]:
        """Check if port field contains consignee patterns."""
        if not port:
            return None

        for pattern in self.CONSIGNEE_PATTERNS:
            if re.search(pattern, port, re.IGNORECASE):
                return {
                    'value': port,
                    'pattern_matched': pattern
                }
        return None

    def detect_date_in_ship_name(self, ship_name: str) -> Optional[Dict[str, Any]]:
        """Check if ship_name starts with a date pattern."""
        if not ship_name:
            return None

        for pattern in self.DATE_PATTERNS:
            if re.match(pattern, ship_name, re.IGNORECASE):
                return {
                    'value': ship_name,
                    'pattern_matched': pattern
                }
        return None

    def detect_quantity_in_ship_name(self, ship_name: str) -> Optional[Dict[str, Any]]:
        """Check if ship_name contains quantity patterns."""
        if not ship_name:
            return None

        for pattern in self.QUANTITY_PATTERNS:
            if re.search(pattern, ship_name, re.IGNORECASE):
                return {
                    'value': ship_name,
                    'pattern_matched': pattern
                }
        return None

    def analyze_shipment(self, shipment: Dict[str, Any], filename: str) -> List[Dict[str, Any]]:
        """Analyze a single shipment for field contamination."""
        issues = []
        record_id = shipment.get('record_id', 'unknown')
        raw_text = shipment.get('raw_text', '')

        ship_name = shipment.get('ship_name', '')
        origin_port = shipment.get('origin_port', '')
        dest_port = shipment.get('destination_port', '')

        # Check cargo in ship_name
        result = self.detect_cargo_in_ship_name(ship_name)
        if result:
            self.contamination_counts['cargo_in_ship_name'] += 1
            issue = {
                'type': 'cargo_in_ship_name',
                'file': filename,
                'record_id': record_id,
                'raw_text': raw_text[:200],
                **result
            }
            issues.append(issue)
            if len(self.cargo_in_ship_name) < 500:
                self.cargo_in_ship_name.append(issue)

        # Check date in ship_name
        result = self.detect_date_in_ship_name(ship_name)
        if result:
            self.contamination_counts['date_in_ship_name'] += 1
            issue = {
                'type': 'date_in_ship_name',
                'file': filename,
                'record_id': record_id,
                'raw_text': raw_text[:200],
                **result
            }
            issues.append(issue)
            if len(self.date_in_ship_name) < 200:
                self.date_in_ship_name.append(issue)

        # Check quantity in ship_name
        result = self.detect_quantity_in_ship_name(ship_name)
        if result:
            self.contamination_counts['quantity_in_ship_name'] += 1
            issue = {
                'type': 'quantity_in_ship_name',
                'file': filename,
                'record_id': record_id,
                'raw_text': raw_text[:200],
                **result
            }
            issues.append(issue)
            if len(self.quantity_in_ship_name) < 200:
                self.quantity_in_ship_name.append(issue)

        # Check consignee in origin port
        result = self.detect_consignee_in_port(origin_port)
        if result:
            self.contamination_counts['consignee_in_origin'] += 1
            issue = {
                'type': 'consignee_in_origin_port',
                'file': filename,
                'record_id': record_id,
                'raw_text': raw_text[:200],
                **result
            }
            issues.append(issue)
            if len(self.consignee_in_port) < 200:
                self.consignee_in_port.append(issue)

        # Check consignee in destination port
        result = self.detect_consignee_in_port(dest_port)
        if result:
            self.contamination_counts['consignee_in_destination'] += 1
            issue = {
                'type': 'consignee_in_destination_port',
                'file': filename,
                'record_id': record_id,
                'raw_text': raw_text[:200],
                **result
            }
            issues.append(issue)
            if len(self.consignee_in_port) < 200:
                self.consignee_in_port.append(issue)

        # Additional checks for unusual ship names
        if ship_name:
            # Very long ship names (likely contamination)
            if len(ship_name) > 40:
                self.contamination_counts['long_ship_name'] += 1
                issue = {
                    'type': 'long_ship_name',
                    'file': filename,
                    'record_id': record_id,
                    'value': ship_name,
                    'length': len(ship_name),
                    'raw_text': raw_text[:200]
                }
                issues.append(issue)
                if len(self.misc_contamination) < 200:
                    self.misc_contamination.append(issue)

            # Ship names with unusual characters
            if re.search(r'[<>\[\]{}|\\]', ship_name):
                self.contamination_counts['unusual_chars_in_ship_name'] += 1
                issue = {
                    'type': 'unusual_chars_in_ship_name',
                    'file': filename,
                    'record_id': record_id,
                    'value': ship_name,
                    'raw_text': raw_text[:200]
                }
                issues.append(issue)
                if len(self.misc_contamination) < 200:
                    self.misc_contamination.append(issue)

        return issues

    def analyze_file(self, filepath: Path) -> Dict[str, Any]:
        """Analyze a single file for contamination."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            return {'error': str(e)}

        filename = filepath.name
        shipments = data.get('shipments', [])

        file_issues = defaultdict(int)
        all_issues = []

        for shipment in shipments:
            issues = self.analyze_shipment(shipment, filename)
            all_issues.extend(issues)
            for issue in issues:
                file_issues[issue['type']] += 1

        return {
            'filename': filename,
            'shipments': len(shipments),
            'issues': dict(file_issues),
            'issue_count': len(all_issues)
        }

    def analyze_all(self, verbose: bool = False) -> Dict[str, Any]:
        """Analyze all parsed files."""
        json_files = list(self.parsed_dir.glob('*_parsed.json'))
        self.total_files = len(json_files)

        if verbose:
            print(f"Analyzing {self.total_files} files for field contamination...")

        for i, filepath in enumerate(json_files):
            if verbose and (i + 1) % 200 == 0:
                print(f"  Processed {i + 1}/{self.total_files} files...")

            result = self.analyze_file(filepath)
            if 'shipments' in result:
                self.total_shipments += result['shipments']

        return self.generate_report()

    def generate_report(self) -> Dict[str, Any]:
        """Generate the contamination report."""
        # Count unique contaminated values
        cargo_values = set(item['value'] for item in self.cargo_in_ship_name)
        consignee_values = set(item['value'] for item in self.consignee_in_port)

        report = {
            'summary': {
                'total_files': self.total_files,
                'total_shipments': self.total_shipments,
                'total_contaminated_records': sum(self.contamination_counts.values()),
                'contamination_by_type': dict(self.contamination_counts)
            },
            'cargo_in_ship_name': {
                'total': self.contamination_counts.get('cargo_in_ship_name', 0),
                'unique_values': len(cargo_values),
                'samples': self.cargo_in_ship_name[:100]
            },
            'date_in_ship_name': {
                'total': self.contamination_counts.get('date_in_ship_name', 0),
                'samples': self.date_in_ship_name[:50]
            },
            'quantity_in_ship_name': {
                'total': self.contamination_counts.get('quantity_in_ship_name', 0),
                'samples': self.quantity_in_ship_name[:50]
            },
            'consignee_in_port': {
                'total_origin': self.contamination_counts.get('consignee_in_origin', 0),
                'total_destination': self.contamination_counts.get('consignee_in_destination', 0),
                'unique_values': len(consignee_values),
                'samples': self.consignee_in_port[:50]
            },
            'other_issues': {
                'long_ship_names': self.contamination_counts.get('long_ship_name', 0),
                'unusual_chars': self.contamination_counts.get('unusual_chars_in_ship_name', 0),
                'samples': self.misc_contamination[:50]
            }
        }

        return report

    def save_report(self, report: Dict[str, Any]):
        """Save report to JSON and CSV formats."""
        # Save JSON
        json_path = self.output_dir / 'field_contamination.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)

        # Save CSV of contaminated records
        csv_path = self.output_dir / 'contaminated_records.csv'
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'type', 'file', 'record_id', 'contaminated_value',
                'detail', 'raw_text'
            ])

            # Write cargo in ship_name
            for item in self.cargo_in_ship_name:
                writer.writerow([
                    item['type'],
                    item['file'],
                    item['record_id'],
                    item['value'],
                    ','.join(item.get('keywords_found', [])),
                    item.get('raw_text', '')[:150]
                ])

            # Write consignee in port
            for item in self.consignee_in_port:
                writer.writerow([
                    item['type'],
                    item['file'],
                    item['record_id'],
                    item['value'],
                    item.get('pattern_matched', ''),
                    item.get('raw_text', '')[:150]
                ])

            # Write date/quantity in ship_name
            for item in self.date_in_ship_name + self.quantity_in_ship_name:
                writer.writerow([
                    item['type'],
                    item['file'],
                    item['record_id'],
                    item['value'],
                    item.get('pattern_matched', ''),
                    item.get('raw_text', '')[:150]
                ])

            # Write misc contamination
            for item in self.misc_contamination:
                detail = f"length={item.get('length', '')}" if 'length' in item else ''
                writer.writerow([
                    item['type'],
                    item['file'],
                    item['record_id'],
                    item['value'],
                    detail,
                    item.get('raw_text', '')[:150]
                ])

        print(f"Saved reports to:")
        print(f"  - {json_path}")
        print(f"  - {csv_path}")

        return json_path, csv_path


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Detect field contamination in shipment data')
    parser.add_argument('--parsed-dir', default='/home/jic823/timber_data/parsed',
                        help='Directory containing parsed JSON files')
    parser.add_argument('--output-dir', default='/home/jic823/timber_data/reports',
                        help='Directory for output reports')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show progress during analysis')

    args = parser.parse_args()

    detector = FieldContaminationDetector(args.parsed_dir, args.output_dir)
    report = detector.analyze_all(verbose=args.verbose)
    detector.save_report(report)

    # Print summary
    print("\n" + "=" * 50)
    print("FIELD CONTAMINATION DETECTION COMPLETE")
    print("=" * 50)
    print(f"Total contaminated records: {report['summary']['total_contaminated_records']:,}")
    print(f"  Cargo in ship_name: {report['cargo_in_ship_name']['total']:,}")
    print(f"  Date in ship_name: {report['date_in_ship_name']['total']:,}")
    print(f"  Quantity in ship_name: {report['quantity_in_ship_name']['total']:,}")
    print(f"  Consignee in origin: {report['consignee_in_port']['total_origin']:,}")
    print(f"  Consignee in destination: {report['consignee_in_port']['total_destination']:,}")


if __name__ == '__main__':
    main()
