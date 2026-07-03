#!/usr/bin/env python3
"""
Port Parsing Errors Analyzer for Timber Shipment Data

Categorizes port parsing errors:
1. Port+cargo combined (e.g., "Cronstadt-lathwood", "Quebec-deals, &c.")
2. Truncated ports (e.g., "BO", "KING", "NEWPORT (MON")
3. Headers as ports (e.g., "DISCHARGING LIST", "SHIPPING INTELLIGENCE")
4. OCR variants (e.g., Hernösand/Hernosand, Kragerö/Kragero)
"""

import json
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Tuple, Optional


class PortParsingErrorsAnalyzer:
    """Analyzes port parsing errors and generates fix rules."""

    # Cargo suffixes indicating port+cargo combined
    CARGO_SUFFIXES = [
        '-deals', '-sleepers', '-lathwood', '-timber', '-staves',
        '-boards', '-battens', '-props', '-pit props', '-pitwood',
        '-spars', '-poles', '-logs', '-planks', '-laths', '-oak',
        '-pine', '-fir', '-spruce', '-ash', '-elm', '-beech',
        ', &c.', ', &c', ', etc.', ', etc'
    ]

    # Known truncated ports with their fixes
    TRUNCATION_FIXES = {
        'BO': "Bo'ness",
        'KING': "King's Lynn",
        'ST': None,  # Ambiguous - could be many places
        'DON': None,  # Ambiguous
        'NSEA': None,  # Truncated
        'NEWPORT (MON': 'Newport (Monmouthshire)',
        'NEWPORT (MON.': 'Newport (Monmouthshire)',
        'HARTLEPOOL (WEST': 'Hartlepool (West)',
        'HARTLEPOOL (WEST:': 'Hartlepool (West)',
        'HARTLEPOOL (WEST)': 'Hartlepool (West)',
        'HARTLEPOOL (WEST):': 'Hartlepool (West)',
        'SOUTH SHIELDS (': 'South Shields',
        'NORTH SHIELDS (': 'North Shields',
    }

    # Headers/non-ports that appear as port values
    HEADER_PATTERNS = [
        'DISCHARGING LIST',
        'SHIPPING INTELLIGENCE',
        'IMPORTS',
        'EXPORTS',
        'ARRIVALS',
        'DEPARTURES',
        'TIMBER',
        'DEALS',
        'CONTINUED',
        'PAGE',
        '---',
        '...',
        'ERRATA',
        'PITWOOD',
        'N/A',
        'VARIOUS',
        'DITTO',
        'DO.',
        'DO',
    ]

    # Common OCR variant patterns (source -> canonical)
    OCR_VARIANTS = {
        'HERNOSAND': 'Härnösand',
        'HERNÖSAND': 'Härnösand',
        'KRAGERO': 'Kragerø',
        'KRAGERÖ': 'Kragerø',
        'GEFLE': 'Gävle',
        'SODERHAMN': 'Söderhamn',
        'SUNDSVALL': 'Sundsvall',
        'SWARTVIK': 'Svartvik',
        'SWARTWIK': 'Svartvik',
        'MALMÖ': 'Malmö',
        'MALMO': 'Malmö',
        'DRONTHEIM': 'Trondheim',
        'CHRISTIANIA': 'Oslo',
        'DANTZIC': 'Gdańsk',
        'DANZIG': 'Gdańsk',
        'DANTZIG': 'Gdańsk',
        'MEMEL': 'Klaipėda',
        'KONIGSBERG': 'Kaliningrad',
        'KÖNIGSBERG': 'Kaliningrad',
        'STETTIN': 'Szczecin',
        'LIBAU': 'Liepāja',
        'RIGA': 'Riga',
        'REVAL': 'Tallinn',
        'HELSINGFORS': 'Helsinki',
        'ABO': 'Turku',
        'ÅBO': 'Turku',
        'WIBORG': 'Vyborg',
        'WYBORG': 'Vyborg',
        'BJORNEBORG': 'Pori',
        'ST. PETERSBURG': 'Saint Petersburg',
        'ST PETERSBURG': 'Saint Petersburg',
        'CRONSTADT': 'Kronstadt',
        'ARCHANGEL': 'Arkhangelsk',
        'GOTHENBURG': 'Gothenburg',
        'GÖTEBORG': 'Gothenburg',
        'GOTEBORG': 'Gothenburg',
    }

    def __init__(self, parsed_dir: str, output_dir: str, reference_dir: str):
        self.parsed_dir = Path(parsed_dir)
        self.output_dir = Path(output_dir)
        self.reference_dir = Path(reference_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Track errors by category
        self.port_cargo_combined = defaultdict(int)
        self.truncated_ports = defaultdict(int)
        self.headers_as_ports = defaultdict(int)
        self.ocr_variants = defaultdict(int)
        self.unmatched_short = defaultdict(int)  # Short suspicious values

        # Sample records for each category
        self.samples = {
            'port_cargo_combined': [],
            'truncated': [],
            'headers': [],
            'ocr_variants': [],
            'unmatched_short': []
        }

        # Generated fix rules
        self.fix_rules = {
            'port_cargo_split': {},
            'truncation_completion': {},
            'error_exclusions': [],
            'ocr_normalization': {}
        }

        # Stats
        self.total_files = 0
        self.total_shipments = 0

    def detect_port_cargo_combined(self, port: str) -> Optional[Tuple[str, str]]:
        """Detect and split port+cargo combinations."""
        if not port:
            return None

        port_lower = port.lower()

        for suffix in self.CARGO_SUFFIXES:
            if suffix in port_lower:
                # Split at the suffix
                idx = port_lower.find(suffix)
                clean_port = port[:idx].strip()
                cargo_part = port[idx:].strip(' -,')
                return (clean_port, cargo_part)

        return None

    def detect_truncated(self, port: str) -> Optional[str]:
        """Detect truncated port names and return fix if known."""
        if not port:
            return None

        port_upper = port.upper().strip()

        # Check against known truncations
        if port_upper in self.TRUNCATION_FIXES:
            return self.TRUNCATION_FIXES[port_upper]

        # Detect potential truncations (ends with opening parenthesis)
        if port_upper.endswith('(') or port_upper.endswith(':'):
            return None  # Flag as truncated but no fix

        # Very short all-caps ports are suspicious
        if len(port_upper) <= 3 and port_upper.isupper() and port_upper.isalpha():
            return None  # Flag as potentially truncated

        return None

    def detect_header(self, port: str) -> bool:
        """Detect if a port value is actually a header/non-port."""
        if not port:
            return False

        port_upper = port.upper().strip()

        for header in self.HEADER_PATTERNS:
            if header in port_upper:
                return True

        # All digits or punctuation
        if re.match(r'^[\d\-\.\,\s]+$', port):
            return True

        return False

    def detect_ocr_variant(self, port: str) -> Optional[str]:
        """Detect OCR variant and return canonical form."""
        if not port:
            return None

        port_upper = port.upper().strip()

        if port_upper in self.OCR_VARIANTS:
            return self.OCR_VARIANTS[port_upper]

        return None

    def analyze_port(self, port: str, field: str, filename: str, record_id: str) -> Dict[str, Any]:
        """Analyze a single port value for errors."""
        if not port or not port.strip():
            return {'category': 'empty'}

        issues = []

        # Check port+cargo combined
        split_result = self.detect_port_cargo_combined(port)
        if split_result:
            clean_port, cargo = split_result
            self.port_cargo_combined[port] += 1
            self.fix_rules['port_cargo_split'][port] = clean_port

            if len(self.samples['port_cargo_combined']) < 100:
                self.samples['port_cargo_combined'].append({
                    'original': port,
                    'clean_port': clean_port,
                    'cargo_part': cargo,
                    'file': filename,
                    'field': field
                })
            issues.append('port_cargo_combined')

        # Check truncated
        port_upper = port.upper().strip()
        if port_upper in self.TRUNCATION_FIXES:
            fix = self.TRUNCATION_FIXES[port_upper]
            self.truncated_ports[port] += 1
            if fix:
                self.fix_rules['truncation_completion'][port_upper] = fix

            if len(self.samples['truncated']) < 100:
                self.samples['truncated'].append({
                    'original': port,
                    'fix': fix,
                    'file': filename,
                    'field': field
                })
            issues.append('truncated')

        elif port_upper.endswith('(') or (len(port_upper) <= 3 and port_upper.isupper() and port_upper.isalpha()):
            self.unmatched_short[port] += 1
            if len(self.samples['unmatched_short']) < 100:
                self.samples['unmatched_short'].append({
                    'value': port,
                    'file': filename,
                    'field': field
                })
            issues.append('unmatched_short')

        # Check headers
        if self.detect_header(port):
            self.headers_as_ports[port] += 1
            if port not in self.fix_rules['error_exclusions']:
                self.fix_rules['error_exclusions'].append(port)

            if len(self.samples['headers']) < 100:
                self.samples['headers'].append({
                    'value': port,
                    'file': filename,
                    'field': field
                })
            issues.append('header_as_port')

        # Check OCR variants
        canonical = self.detect_ocr_variant(port)
        if canonical:
            self.ocr_variants[port] += 1
            self.fix_rules['ocr_normalization'][port.upper()] = canonical

            if len(self.samples['ocr_variants']) < 100:
                self.samples['ocr_variants'].append({
                    'original': port,
                    'canonical': canonical,
                    'file': filename,
                    'field': field
                })
            issues.append('ocr_variant')

        return {
            'category': issues[0] if issues else 'ok',
            'issues': issues
        }

    def analyze_file(self, filepath: Path) -> Dict[str, Any]:
        """Analyze a single file for port errors."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            return {'error': str(e)}

        filename = filepath.name
        shipments = data.get('shipments', [])

        file_issues = defaultdict(int)

        for shipment in shipments:
            record_id = shipment.get('record_id', 'unknown')

            # Analyze origin port
            origin = shipment.get('origin_port', '')
            result = self.analyze_port(origin, 'origin', filename, record_id)
            for issue in result.get('issues', []):
                file_issues[f'origin_{issue}'] += 1

            # Analyze destination port
            dest = shipment.get('destination_port', '')
            result = self.analyze_port(dest, 'destination', filename, record_id)
            for issue in result.get('issues', []):
                file_issues[f'dest_{issue}'] += 1

        return {
            'filename': filename,
            'shipments': len(shipments),
            'issues': dict(file_issues)
        }

    def analyze_all(self, verbose: bool = False) -> Dict[str, Any]:
        """Analyze all parsed files."""
        json_files = list(self.parsed_dir.glob('*_parsed.json'))
        self.total_files = len(json_files)

        if verbose:
            print(f"Analyzing {self.total_files} files for port parsing errors...")

        for i, filepath in enumerate(json_files):
            if verbose and (i + 1) % 200 == 0:
                print(f"  Processed {i + 1}/{self.total_files} files...")

            result = self.analyze_file(filepath)
            if 'shipments' in result:
                self.total_shipments += result['shipments']

        return self.generate_report()

    def generate_report(self) -> Dict[str, Any]:
        """Generate the port parsing errors report."""
        report = {
            'summary': {
                'total_files': self.total_files,
                'total_shipments': self.total_shipments,
                'port_cargo_combined': sum(self.port_cargo_combined.values()),
                'truncated_ports': sum(self.truncated_ports.values()),
                'headers_as_ports': sum(self.headers_as_ports.values()),
                'ocr_variants': sum(self.ocr_variants.values()),
                'unmatched_short': sum(self.unmatched_short.values())
            },
            'port_cargo_combined': {
                'total': sum(self.port_cargo_combined.values()),
                'unique_patterns': len(self.port_cargo_combined),
                'top_patterns': sorted(
                    self.port_cargo_combined.items(),
                    key=lambda x: -x[1]
                )[:50],
                'samples': self.samples['port_cargo_combined']
            },
            'truncated_ports': {
                'total': sum(self.truncated_ports.values()),
                'unique_patterns': len(self.truncated_ports),
                'known_fixes': {
                    k: v for k, v in self.TRUNCATION_FIXES.items()
                    if v is not None
                },
                'top_patterns': sorted(
                    self.truncated_ports.items(),
                    key=lambda x: -x[1]
                )[:30],
                'samples': self.samples['truncated']
            },
            'headers_as_ports': {
                'total': sum(self.headers_as_ports.values()),
                'unique_patterns': len(self.headers_as_ports),
                'top_patterns': sorted(
                    self.headers_as_ports.items(),
                    key=lambda x: -x[1]
                )[:30],
                'samples': self.samples['headers']
            },
            'ocr_variants': {
                'total': sum(self.ocr_variants.values()),
                'unique_patterns': len(self.ocr_variants),
                'top_patterns': sorted(
                    self.ocr_variants.items(),
                    key=lambda x: -x[1]
                )[:30],
                'samples': self.samples['ocr_variants']
            },
            'unmatched_short': {
                'total': sum(self.unmatched_short.values()),
                'unique_patterns': len(self.unmatched_short),
                'top_patterns': sorted(
                    self.unmatched_short.items(),
                    key=lambda x: -x[1]
                )[:50],
                'samples': self.samples['unmatched_short']
            }
        }

        return report

    def save_report(self, report: Dict[str, Any]):
        """Save report to JSON and generate fix rules file."""
        # Save analysis report
        json_path = self.output_dir / 'port_parsing_errors.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)

        # Save fix rules
        fix_rules_path = self.reference_dir / 'port_parsing_fixes.json'
        with open(fix_rules_path, 'w', encoding='utf-8') as f:
            json.dump(self.fix_rules, f, indent=2)

        print(f"Saved reports to:")
        print(f"  - {json_path}")
        print(f"  - {fix_rules_path}")

        return json_path, fix_rules_path


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Analyze port parsing errors')
    parser.add_argument('--parsed-dir', default='/home/jic823/timber_data/parsed',
                        help='Directory containing parsed JSON files')
    parser.add_argument('--output-dir', default='/home/jic823/timber_data/reports',
                        help='Directory for output reports')
    parser.add_argument('--reference-dir', default='/home/jic823/timber_data/reference_data',
                        help='Directory for reference data files')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show progress during analysis')

    args = parser.parse_args()

    analyzer = PortParsingErrorsAnalyzer(
        args.parsed_dir, args.output_dir, args.reference_dir
    )
    report = analyzer.analyze_all(verbose=args.verbose)
    analyzer.save_report(report)

    # Print summary
    print("\n" + "=" * 50)
    print("PORT PARSING ERROR ANALYSIS COMPLETE")
    print("=" * 50)
    print(f"Port+cargo combined: {report['summary']['port_cargo_combined']:,}")
    print(f"Truncated ports: {report['summary']['truncated_ports']:,}")
    print(f"Headers as ports: {report['summary']['headers_as_ports']:,}")
    print(f"OCR variants found: {report['summary']['ocr_variants']:,}")
    print(f"Unmatched short values: {report['summary']['unmatched_short']:,}")


if __name__ == '__main__':
    main()
