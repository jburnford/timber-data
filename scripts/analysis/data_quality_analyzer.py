#!/usr/bin/env python3
"""
Data Quality Analyzer for Timber Shipment Data

Generates comprehensive quality report analyzing:
- Parse confidence distribution
- Empty/missing field counts
- Field length anomalies
- Files with highest error rates
"""

import json
import os
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Tuple


class DataQualityAnalyzer:
    """Analyzes data quality across all parsed shipment files."""

    def __init__(self, parsed_dir: str, output_dir: str):
        self.parsed_dir = Path(parsed_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Counters
        self.total_files = 0
        self.total_shipments = 0
        self.failed_files = 0

        # Confidence tracking
        self.confidence_counts = defaultdict(int)

        # Missing/empty field tracking
        self.empty_fields = defaultdict(int)

        # Length anomaly tracking
        self.length_anomalies = {
            'long_ship_names': [],  # > 50 chars
            'long_ports': [],       # > 30 chars
            'long_consignees': []   # > 100 chars
        }

        # File-level error tracking
        self.file_stats = []

        # Year-based tracking
        self.by_year = defaultdict(lambda: {
            'shipments': 0,
            'empty_origin': 0,
            'empty_destination': 0,
            'empty_cargo': 0,
            'low_confidence': 0
        })

    def extract_year(self, filename: str) -> str:
        """Extract year from filename."""
        # Patterns like "1885", "1887", etc.
        import re
        match = re.search(r'(18[7-9]\d)', filename)
        return match.group(1) if match else 'unknown'

    def analyze_shipment(self, shipment: Dict[str, Any], filename: str) -> Dict[str, Any]:
        """Analyze a single shipment record."""
        issues = []

        # Check confidence
        confidence = shipment.get('parse_confidence', 'unknown')
        self.confidence_counts[confidence] += 1
        if confidence == 'low':
            issues.append('low_confidence')

        # Check empty/missing fields
        origin = shipment.get('origin_port', '')
        destination = shipment.get('destination_port', '')
        ship_name = shipment.get('ship_name', '')
        consignee = shipment.get('consignee', '')
        cargo = shipment.get('cargo', [])
        arrival_date = shipment.get('arrival_date', '')

        if not origin or origin.strip() == '':
            self.empty_fields['origin_port'] += 1
            issues.append('empty_origin')

        if not destination or destination.strip() == '':
            self.empty_fields['destination_port'] += 1
            issues.append('empty_destination')

        if not ship_name or ship_name.strip() == '':
            self.empty_fields['ship_name'] += 1
            issues.append('empty_ship_name')

        if not consignee or consignee.strip() == '':
            self.empty_fields['consignee'] += 1
            issues.append('empty_consignee')

        if not cargo or len(cargo) == 0:
            self.empty_fields['cargo'] += 1
            issues.append('empty_cargo')

        if not arrival_date or arrival_date.strip() == '':
            self.empty_fields['arrival_date'] += 1
            issues.append('empty_arrival_date')

        # Check length anomalies
        if ship_name and len(ship_name) > 50:
            self.length_anomalies['long_ship_names'].append({
                'file': filename,
                'record_id': shipment.get('record_id', 'unknown'),
                'value': ship_name,
                'length': len(ship_name)
            })
            issues.append('long_ship_name')

        if origin and len(origin) > 30:
            self.length_anomalies['long_ports'].append({
                'file': filename,
                'record_id': shipment.get('record_id', 'unknown'),
                'field': 'origin_port',
                'value': origin,
                'length': len(origin)
            })
            issues.append('long_origin_port')

        if destination and len(destination) > 30:
            self.length_anomalies['long_ports'].append({
                'file': filename,
                'record_id': shipment.get('record_id', 'unknown'),
                'field': 'destination_port',
                'value': destination,
                'length': len(destination)
            })
            issues.append('long_destination_port')

        if consignee and len(consignee) > 100:
            self.length_anomalies['long_consignees'].append({
                'file': filename,
                'record_id': shipment.get('record_id', 'unknown'),
                'value': consignee,
                'length': len(consignee)
            })
            issues.append('long_consignee')

        return {
            'issues': issues,
            'confidence': confidence
        }

    def analyze_file(self, filepath: Path) -> Dict[str, Any]:
        """Analyze a single parsed JSON file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            return {
                'filename': filepath.name,
                'error': str(e),
                'shipments': 0,
                'issues': ['parse_error']
            }

        filename = filepath.name
        year = self.extract_year(filename)

        shipments = data.get('shipments', [])
        file_issues = defaultdict(int)

        for shipment in shipments:
            result = self.analyze_shipment(shipment, filename)
            for issue in result['issues']:
                file_issues[issue] += 1

            # Track by year
            self.by_year[year]['shipments'] += 1
            if 'empty_origin' in result['issues']:
                self.by_year[year]['empty_origin'] += 1
            if 'empty_destination' in result['issues']:
                self.by_year[year]['empty_destination'] += 1
            if 'empty_cargo' in result['issues']:
                self.by_year[year]['empty_cargo'] += 1
            if result['confidence'] == 'low':
                self.by_year[year]['low_confidence'] += 1

        return {
            'filename': filename,
            'year': year,
            'shipments': len(shipments),
            'status': data.get('status', 'unknown'),
            'issues': dict(file_issues),
            'error_rate': sum(file_issues.values()) / max(len(shipments), 1)
        }

    def analyze_all(self, verbose: bool = False) -> Dict[str, Any]:
        """Analyze all parsed files."""
        json_files = list(self.parsed_dir.glob('*_parsed.json'))
        self.total_files = len(json_files)

        if verbose:
            print(f"Analyzing {self.total_files} files...")

        for i, filepath in enumerate(json_files):
            if verbose and (i + 1) % 200 == 0:
                print(f"  Processed {i + 1}/{self.total_files} files...")

            result = self.analyze_file(filepath)
            self.file_stats.append(result)
            self.total_shipments += result['shipments']

            if 'error' in result or result.get('status') == 'failed':
                self.failed_files += 1

        return self.generate_report()

    def generate_report(self) -> Dict[str, Any]:
        """Generate the final quality report."""
        # Sort files by error rate
        files_by_error = sorted(
            self.file_stats,
            key=lambda x: x.get('error_rate', 0),
            reverse=True
        )

        report = {
            'summary': {
                'total_files': self.total_files,
                'total_shipments': self.total_shipments,
                'failed_files': self.failed_files,
                'avg_shipments_per_file': round(self.total_shipments / max(self.total_files, 1), 1)
            },
            'confidence_distribution': {
                'high': self.confidence_counts.get('high', 0),
                'medium': self.confidence_counts.get('medium', 0),
                'low': self.confidence_counts.get('low', 0),
                'unknown': self.confidence_counts.get('unknown', 0)
            },
            'empty_fields': dict(self.empty_fields),
            'empty_field_percentages': {
                field: round(count / max(self.total_shipments, 1) * 100, 2)
                for field, count in self.empty_fields.items()
            },
            'length_anomalies': {
                'long_ship_names_count': len(self.length_anomalies['long_ship_names']),
                'long_ports_count': len(self.length_anomalies['long_ports']),
                'long_consignees_count': len(self.length_anomalies['long_consignees']),
                'samples': {
                    'long_ship_names': self.length_anomalies['long_ship_names'][:20],
                    'long_ports': self.length_anomalies['long_ports'][:20],
                    'long_consignees': self.length_anomalies['long_consignees'][:10]
                }
            },
            'worst_files': files_by_error[:50],
            'by_year': {
                year: dict(stats)
                for year, stats in sorted(self.by_year.items())
            }
        }

        return report

    def save_report(self, report: Dict[str, Any]):
        """Save report to JSON and text formats."""
        # Save JSON
        json_path = self.output_dir / 'data_quality_summary.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)

        # Save text summary
        txt_path = self.output_dir / 'data_quality_summary.txt'
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("TIMBER SHIPMENT DATA QUALITY REPORT\n")
            f.write("=" * 70 + "\n\n")

            f.write("SUMMARY\n")
            f.write("-" * 40 + "\n")
            f.write(f"Total Files Analyzed:    {report['summary']['total_files']:,}\n")
            f.write(f"Total Shipments:         {report['summary']['total_shipments']:,}\n")
            f.write(f"Failed Files:            {report['summary']['failed_files']:,}\n")
            f.write(f"Avg Shipments/File:      {report['summary']['avg_shipments_per_file']}\n\n")

            f.write("PARSE CONFIDENCE DISTRIBUTION\n")
            f.write("-" * 40 + "\n")
            conf = report['confidence_distribution']
            total = sum(conf.values())
            for level, count in conf.items():
                pct = round(count / max(total, 1) * 100, 1)
                f.write(f"  {level:12} {count:>8,} ({pct:>5.1f}%)\n")
            f.write("\n")

            f.write("EMPTY/MISSING FIELDS\n")
            f.write("-" * 40 + "\n")
            for field, count in sorted(report['empty_fields'].items(), key=lambda x: -x[1]):
                pct = report['empty_field_percentages'][field]
                f.write(f"  {field:20} {count:>8,} ({pct:>5.2f}%)\n")
            f.write("\n")

            f.write("LENGTH ANOMALIES\n")
            f.write("-" * 40 + "\n")
            f.write(f"  Long ship names (>50 chars):  {report['length_anomalies']['long_ship_names_count']:,}\n")
            f.write(f"  Long ports (>30 chars):       {report['length_anomalies']['long_ports_count']:,}\n")
            f.write(f"  Long consignees (>100 chars): {report['length_anomalies']['long_consignees_count']:,}\n\n")

            if report['length_anomalies']['samples']['long_ship_names']:
                f.write("  Sample long ship names:\n")
                for item in report['length_anomalies']['samples']['long_ship_names'][:5]:
                    f.write(f"    - [{item['length']} chars] {item['value'][:60]}...\n")
                f.write("\n")

            f.write("BY YEAR BREAKDOWN\n")
            f.write("-" * 40 + "\n")
            f.write(f"{'Year':<8} {'Shipments':>10} {'Empty Orig':>12} {'Empty Dest':>12} {'Empty Cargo':>12}\n")
            for year, stats in sorted(report['by_year'].items()):
                f.write(f"{year:<8} {stats['shipments']:>10,} {stats['empty_origin']:>12,} ")
                f.write(f"{stats['empty_destination']:>12,} {stats['empty_cargo']:>12,}\n")
            f.write("\n")

            f.write("TOP 10 WORST FILES (by error rate)\n")
            f.write("-" * 40 + "\n")
            for file_info in report['worst_files'][:10]:
                f.write(f"  {file_info['filename'][:50]}\n")
                f.write(f"    Shipments: {file_info['shipments']}, Error rate: {file_info['error_rate']:.2f}\n")
                if file_info.get('issues'):
                    f.write(f"    Issues: {dict(file_info['issues'])}\n")
                f.write("\n")

        print(f"Saved reports to:")
        print(f"  - {json_path}")
        print(f"  - {txt_path}")

        return json_path, txt_path


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Analyze data quality in parsed shipment files')
    parser.add_argument('--parsed-dir', default='/home/jic823/timber_data/parsed',
                        help='Directory containing parsed JSON files')
    parser.add_argument('--output-dir', default='/home/jic823/timber_data/reports',
                        help='Directory for output reports')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show progress during analysis')

    args = parser.parse_args()

    analyzer = DataQualityAnalyzer(args.parsed_dir, args.output_dir)
    report = analyzer.analyze_all(verbose=args.verbose)
    analyzer.save_report(report)

    # Print summary
    print("\n" + "=" * 50)
    print("ANALYSIS COMPLETE")
    print("=" * 50)
    print(f"Files: {report['summary']['total_files']:,}")
    print(f"Shipments: {report['summary']['total_shipments']:,}")
    print(f"Empty origin ports: {report['empty_fields'].get('origin_port', 0):,}")
    print(f"Empty cargos: {report['empty_fields'].get('cargo', 0):,}")
    print(f"Low confidence: {report['confidence_distribution'].get('low', 0):,}")


if __name__ == '__main__':
    main()
