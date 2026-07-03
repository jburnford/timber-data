#!/usr/bin/env python3
"""
Cargo Quality Analyzer for Timber Shipment Data

Analyzes cargo data quality:
- Empty cargo array counts by file
- Quantity anomalies (non-numeric, extremely large >1M)
- Unit catalog and standardization needs
- Commodity normalization needs
"""

import json
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple


class CargoQualityAnalyzer:
    """Analyzes cargo data quality in shipment records."""

    # Known valid units
    VALID_UNITS = {
        'pcs.', 'pcs', 'pieces',
        'lds.', 'lds', 'loads',
        'stds.', 'stds', 'standards',
        'tons', 'ton',
        'cwt.', 'cwt',
        'fathoms', 'fath.',
        'bdls.', 'bdls', 'bundles',
        'cs.', 'cs', 'cases',
        'bxs.', 'bxs', 'boxes',
        'pkgs.', 'pkgs', 'packages',
        'crts.', 'crts', 'crates',
        'brls.', 'brls', 'barrels',
        'logs',
        'spars',
        'poles',
        'ends'
    }

    # Common commodity terms for normalization
    COMMODITY_NORMALIZATIONS = {
        # Deals
        'deals': 'deals',
        'deal': 'deals',
        # Boards
        'boards': 'boards',
        'board': 'boards',
        'bds.': 'boards',
        'bds': 'boards',
        # Battens
        'battens': 'battens',
        'batten': 'battens',
        # Planks
        'planks': 'planks',
        'plank': 'planks',
        # Sleepers
        'sleepers': 'sleepers',
        'sleeper': 'sleepers',
        # Staves
        'staves': 'staves',
        'stave': 'staves',
        # Props
        'props': 'props',
        'prop': 'props',
        'pit props': 'pit props',
        'pitwood': 'pit props',
        # Laths
        'laths': 'laths',
        'lath': 'laths',
    }

    def __init__(self, parsed_dir: str, output_dir: str):
        self.parsed_dir = Path(parsed_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Track issues
        self.empty_cargo_files = []  # Files with high empty cargo rates
        self.quantity_anomalies = []
        self.unit_catalog = defaultdict(int)
        self.commodity_catalog = defaultdict(int)
        self.missing_units = []
        self.missing_commodities = []

        # Summary stats
        self.total_files = 0
        self.total_shipments = 0
        self.total_cargo_items = 0
        self.empty_cargo_shipments = 0

    def parse_quantity(self, quantity_str: str) -> Tuple[Optional[float], str]:
        """Parse quantity string to number, return (value, issue)."""
        if not quantity_str:
            return None, 'empty'

        # Remove commas and whitespace
        clean = quantity_str.replace(',', '').strip()

        # Handle ranges like "50-60"
        if '-' in clean and not clean.startswith('-'):
            parts = clean.split('-')
            try:
                # Use the first value
                return float(parts[0]), 'range'
            except ValueError:
                return None, 'non_numeric'

        # Handle fractions like "1/2"
        if '/' in clean:
            parts = clean.split('/')
            if len(parts) == 2:
                try:
                    return float(parts[0]) / float(parts[1]), 'fraction'
                except (ValueError, ZeroDivisionError):
                    return None, 'non_numeric'

        try:
            value = float(clean)
            if value > 1000000:
                return value, 'extremely_large'
            elif value < 0:
                return value, 'negative'
            return value, 'ok'
        except ValueError:
            return None, 'non_numeric'

    def analyze_cargo_item(self, cargo: Dict[str, Any], filename: str, record_id: str) -> List[Dict[str, Any]]:
        """Analyze a single cargo item."""
        issues = []

        quantity_str = cargo.get('quantity', '')
        unit = cargo.get('unit', '')
        commodity = cargo.get('commodity', '')
        raw_text = cargo.get('raw_text', '')

        # Analyze quantity
        parsed_qty, qty_issue = self.parse_quantity(quantity_str)
        if qty_issue not in ('ok', 'range', 'fraction'):
            self.quantity_anomalies.append({
                'type': f'quantity_{qty_issue}',
                'file': filename,
                'record_id': record_id,
                'quantity': quantity_str,
                'raw_text': raw_text
            })
            issues.append(qty_issue)

        # Track units
        if unit:
            unit_lower = unit.lower().strip()
            self.unit_catalog[unit_lower] += 1
        else:
            self.missing_units.append({
                'file': filename,
                'record_id': record_id,
                'raw_text': raw_text
            })
            issues.append('missing_unit')

        # Track commodities
        if commodity:
            comm_lower = commodity.lower().strip()
            self.commodity_catalog[comm_lower] += 1
        else:
            self.missing_commodities.append({
                'file': filename,
                'record_id': record_id,
                'raw_text': raw_text
            })
            issues.append('missing_commodity')

        return issues

    def analyze_file(self, filepath: Path) -> Dict[str, Any]:
        """Analyze a single file for cargo quality."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            return {'error': str(e)}

        filename = filepath.name
        shipments = data.get('shipments', [])

        empty_cargo_count = 0
        total_cargo_items = 0
        file_issues = defaultdict(int)

        for shipment in shipments:
            record_id = shipment.get('record_id', 'unknown')
            cargo = shipment.get('cargo', [])

            if not cargo or len(cargo) == 0:
                empty_cargo_count += 1
                self.empty_cargo_shipments += 1
            else:
                for item in cargo:
                    total_cargo_items += 1
                    self.total_cargo_items += 1
                    issues = self.analyze_cargo_item(item, filename, record_id)
                    for issue in issues:
                        file_issues[issue] += 1

        # Track files with high empty cargo rates
        if len(shipments) > 0:
            empty_rate = empty_cargo_count / len(shipments)
            if empty_rate > 0.2:  # More than 20% empty
                self.empty_cargo_files.append({
                    'filename': filename,
                    'shipments': len(shipments),
                    'empty_cargo': empty_cargo_count,
                    'empty_rate': round(empty_rate, 3)
                })

        return {
            'filename': filename,
            'shipments': len(shipments),
            'empty_cargo': empty_cargo_count,
            'cargo_items': total_cargo_items,
            'issues': dict(file_issues)
        }

    def analyze_all(self, verbose: bool = False) -> Dict[str, Any]:
        """Analyze all parsed files."""
        json_files = list(self.parsed_dir.glob('*_parsed.json'))
        self.total_files = len(json_files)

        if verbose:
            print(f"Analyzing {self.total_files} files for cargo quality...")

        for i, filepath in enumerate(json_files):
            if verbose and (i + 1) % 200 == 0:
                print(f"  Processed {i + 1}/{self.total_files} files...")

            result = self.analyze_file(filepath)
            if 'shipments' in result:
                self.total_shipments += result['shipments']

        return self.generate_report()

    def generate_report(self) -> Dict[str, Any]:
        """Generate the cargo quality report."""
        # Analyze unit catalog
        unknown_units = {
            unit: count for unit, count in self.unit_catalog.items()
            if unit not in self.VALID_UNITS
        }

        # Find commodities needing normalization
        raw_commodities = sorted(
            self.commodity_catalog.items(),
            key=lambda x: -x[1]
        )

        report = {
            'summary': {
                'total_files': self.total_files,
                'total_shipments': self.total_shipments,
                'total_cargo_items': self.total_cargo_items,
                'empty_cargo_shipments': self.empty_cargo_shipments,
                'empty_cargo_rate': round(
                    self.empty_cargo_shipments / max(self.total_shipments, 1) * 100, 2
                ),
                'missing_units': len(self.missing_units),
                'missing_commodities': len(self.missing_commodities),
                'quantity_anomalies': len(self.quantity_anomalies)
            },
            'empty_cargo': {
                'total_shipments': self.empty_cargo_shipments,
                'files_with_high_empty_rate': len(self.empty_cargo_files),
                'worst_files': sorted(
                    self.empty_cargo_files,
                    key=lambda x: -x['empty_rate']
                )[:30]
            },
            'quantity_anomalies': {
                'total': len(self.quantity_anomalies),
                'by_type': defaultdict(int),
                'samples': self.quantity_anomalies[:100]
            },
            'unit_catalog': {
                'total_unique': len(self.unit_catalog),
                'valid_units': len([u for u in self.unit_catalog if u in self.VALID_UNITS]),
                'unknown_units': len(unknown_units),
                'all_units': sorted(
                    self.unit_catalog.items(),
                    key=lambda x: -x[1]
                ),
                'unknown_unit_samples': sorted(
                    unknown_units.items(),
                    key=lambda x: -x[1]
                )[:50],
                'missing_unit_samples': self.missing_units[:50]
            },
            'commodity_catalog': {
                'total_unique': len(self.commodity_catalog),
                'top_50': raw_commodities[:50],
                'all_commodities': raw_commodities,
                'missing_commodity_samples': self.missing_commodities[:50]
            }
        }

        # Count quantity anomalies by type
        for anomaly in self.quantity_anomalies:
            report['quantity_anomalies']['by_type'][anomaly['type']] += 1
        report['quantity_anomalies']['by_type'] = dict(report['quantity_anomalies']['by_type'])

        return report

    def save_report(self, report: Dict[str, Any]):
        """Save report to JSON format."""
        json_path = self.output_dir / 'cargo_quality.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)

        print(f"Saved report to: {json_path}")
        return json_path


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Analyze cargo quality in shipment data')
    parser.add_argument('--parsed-dir', default='/home/jic823/timber_data/parsed',
                        help='Directory containing parsed JSON files')
    parser.add_argument('--output-dir', default='/home/jic823/timber_data/reports',
                        help='Directory for output reports')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show progress during analysis')

    args = parser.parse_args()

    analyzer = CargoQualityAnalyzer(args.parsed_dir, args.output_dir)
    report = analyzer.analyze_all(verbose=args.verbose)
    analyzer.save_report(report)

    # Print summary
    print("\n" + "=" * 50)
    print("CARGO QUALITY ANALYSIS COMPLETE")
    print("=" * 50)
    print(f"Total shipments: {report['summary']['total_shipments']:,}")
    print(f"Total cargo items: {report['summary']['total_cargo_items']:,}")
    print(f"Empty cargo shipments: {report['summary']['empty_cargo_shipments']:,} ({report['summary']['empty_cargo_rate']}%)")
    print(f"Missing units: {report['summary']['missing_units']:,}")
    print(f"Quantity anomalies: {report['summary']['quantity_anomalies']:,}")
    print(f"Unique commodities: {report['commodity_catalog']['total_unique']:,}")
    print(f"Unique units: {report['unit_catalog']['total_unique']:,}")


if __name__ == '__main__':
    main()
