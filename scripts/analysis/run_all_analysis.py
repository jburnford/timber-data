#!/usr/bin/env python3
"""
Orchestrator for Timber Shipment Data Quality Analysis

Runs all analysis scripts and generates a combined final report.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from data_quality_analyzer import DataQualityAnalyzer
from duplicate_detector import DuplicateDetector
from port_parsing_errors import PortParsingErrorsAnalyzer
from field_contamination_detector import FieldContaminationDetector
from cargo_quality_analyzer import CargoQualityAnalyzer


class AnalysisOrchestrator:
    """Orchestrates all data quality analysis and generates combined report."""

    def __init__(self, parsed_dir: str, output_dir: str, reference_dir: str):
        self.parsed_dir = Path(parsed_dir)
        self.output_dir = Path(output_dir)
        self.reference_dir = Path(reference_dir)

        # Ensure directories exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.reference_dir.mkdir(parents=True, exist_ok=True)

        # Store all reports
        self.reports = {}

    def run_all_analyses(self, verbose: bool = True) -> Dict[str, Any]:
        """Run all analysis scripts."""
        print("=" * 70)
        print("TIMBER SHIPMENT DATA QUALITY ANALYSIS")
        print("=" * 70)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Parsed directory: {self.parsed_dir}")
        print()

        # 1. Data Quality Analysis
        print("-" * 50)
        print("1/5 Running Data Quality Analysis...")
        print("-" * 50)
        analyzer = DataQualityAnalyzer(str(self.parsed_dir), str(self.output_dir))
        self.reports['data_quality'] = analyzer.analyze_all(verbose=verbose)
        analyzer.save_report(self.reports['data_quality'])
        print()

        # 2. Duplicate Detection
        print("-" * 50)
        print("2/5 Running Duplicate Detection...")
        print("-" * 50)
        detector = DuplicateDetector(str(self.parsed_dir), str(self.output_dir))
        self.reports['duplicates'] = detector.analyze_all(verbose=verbose)
        detector.save_report(self.reports['duplicates'])
        print()

        # 3. Port Parsing Errors
        print("-" * 50)
        print("3/5 Running Port Parsing Error Analysis...")
        print("-" * 50)
        port_analyzer = PortParsingErrorsAnalyzer(
            str(self.parsed_dir), str(self.output_dir), str(self.reference_dir)
        )
        self.reports['port_errors'] = port_analyzer.analyze_all(verbose=verbose)
        port_analyzer.save_report(self.reports['port_errors'])
        print()

        # 4. Field Contamination
        print("-" * 50)
        print("4/5 Running Field Contamination Detection...")
        print("-" * 50)
        contam_detector = FieldContaminationDetector(str(self.parsed_dir), str(self.output_dir))
        self.reports['contamination'] = contam_detector.analyze_all(verbose=verbose)
        contam_detector.save_report(self.reports['contamination'])
        print()

        # 5. Cargo Quality
        print("-" * 50)
        print("5/5 Running Cargo Quality Analysis...")
        print("-" * 50)
        cargo_analyzer = CargoQualityAnalyzer(str(self.parsed_dir), str(self.output_dir))
        self.reports['cargo'] = cargo_analyzer.analyze_all(verbose=verbose)
        cargo_analyzer.save_report(self.reports['cargo'])
        print()

        return self.reports

    def generate_final_report(self) -> str:
        """Generate the combined final Markdown report."""
        dq = self.reports.get('data_quality', {})
        dup = self.reports.get('duplicates', {})
        port = self.reports.get('port_errors', {})
        contam = self.reports.get('contamination', {})
        cargo = self.reports.get('cargo', {})

        # Calculate totals
        total_shipments = dq.get('summary', {}).get('total_shipments', 0)
        total_files = dq.get('summary', {}).get('total_files', 0)

        report = []
        report.append("# Timber Shipment Data Quality Report")
        report.append("")
        report.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"**Total Files**: {total_files:,}")
        report.append(f"**Total Shipments**: {total_shipments:,}")
        report.append("")

        # Executive Summary
        report.append("## Executive Summary")
        report.append("")
        report.append("| Issue Category | Count | % of Total | Priority |")
        report.append("|----------------|-------|------------|----------|")

        issues = [
            ("Empty origin ports", dq.get('empty_fields', {}).get('origin_port', 0), "HIGH"),
            ("Empty cargo arrays", dq.get('empty_fields', {}).get('cargo', 0), "HIGH"),
            ("Low confidence records", dq.get('confidence_distribution', {}).get('low', 0), "HIGH"),
            ("Exact duplicate records", dup.get('summary', {}).get('exact_duplicate_records', 0), "HIGH"),
            ("Hallucination loops", dup.get('summary', {}).get('hallucination_loop_records', 0), "HIGH"),
            ("Port+cargo combined", port.get('summary', {}).get('port_cargo_combined', 0), "MEDIUM"),
            ("Truncated ports", port.get('summary', {}).get('truncated_ports', 0), "MEDIUM"),
            ("Headers as ports", port.get('summary', {}).get('headers_as_ports', 0), "MEDIUM"),
            ("Cargo in ship_name", contam.get('cargo_in_ship_name', {}).get('total', 0), "MEDIUM"),
            ("Quantity anomalies", cargo.get('summary', {}).get('quantity_anomalies', 0), "LOW"),
            ("Missing units", cargo.get('summary', {}).get('missing_units', 0), "LOW"),
        ]

        for name, count, priority in sorted(issues, key=lambda x: -x[1]):
            pct = count / max(total_shipments, 1) * 100
            report.append(f"| {name} | {count:,} | {pct:.1f}% | {priority} |")

        report.append("")

        # Section 1: Confidence Distribution
        report.append("## 1. Parse Confidence Distribution")
        report.append("")
        conf = dq.get('confidence_distribution', {})
        report.append("| Confidence | Count | Percentage |")
        report.append("|------------|-------|------------|")
        for level in ['high', 'medium', 'low', 'unknown']:
            count = conf.get(level, 0)
            pct = count / max(total_shipments, 1) * 100
            report.append(f"| {level.capitalize()} | {count:,} | {pct:.1f}% |")
        report.append("")

        # Section 2: Empty Fields
        report.append("## 2. Empty/Missing Fields")
        report.append("")
        report.append("| Field | Count | Percentage |")
        report.append("|-------|-------|------------|")
        for field, count in sorted(dq.get('empty_fields', {}).items(), key=lambda x: -x[1]):
            pct = count / max(total_shipments, 1) * 100
            report.append(f"| {field} | {count:,} | {pct:.1f}% |")
        report.append("")

        # Section 3: Duplicates
        report.append("## 3. Duplicate Records")
        report.append("")
        dup_summary = dup.get('summary', {})
        report.append(f"- **Exact duplicates**: {dup_summary.get('exact_duplicate_records', 0):,} records")
        report.append(f"- **Key duplicates** (same ship+date+port): {dup_summary.get('key_duplicate_records', 0):,} records")
        report.append(f"- **Hallucination loops** (5+ repetitions): {dup_summary.get('hallucination_loop_incidents', 0):,} incidents ({dup_summary.get('hallucination_loop_records', 0):,} records)")
        report.append(f"- **Files affected**: {dup_summary.get('files_with_duplicates', 0):,}")
        report.append("")

        if dup.get('hallucination_loops', {}).get('samples'):
            report.append("### Top Hallucination Loops")
            report.append("")
            report.append("| File | Raw Text (truncated) | Count |")
            report.append("|------|----------------------|-------|")
            for loop in dup.get('hallucination_loops', {}).get('samples', [])[:10]:
                text = loop.get('raw_text', '')[:60].replace('|', '\\|')
                report.append(f"| {loop.get('file', '')[:40]} | {text}... | {loop.get('count', 0)} |")
            report.append("")

        # Section 4: Port Parsing Errors
        report.append("## 4. Port Parsing Errors")
        report.append("")
        port_summary = port.get('summary', {})
        report.append(f"- **Port+cargo combined**: {port_summary.get('port_cargo_combined', 0):,}")
        report.append(f"- **Truncated ports**: {port_summary.get('truncated_ports', 0):,}")
        report.append(f"- **Headers as ports**: {port_summary.get('headers_as_ports', 0):,}")
        report.append(f"- **OCR variants detected**: {port_summary.get('ocr_variants', 0):,}")
        report.append("")

        # Top port+cargo patterns
        if port.get('port_cargo_combined', {}).get('top_patterns'):
            report.append("### Top Port+Cargo Combined Patterns")
            report.append("")
            report.append("| Pattern | Count |")
            report.append("|---------|-------|")
            for pattern, count in port.get('port_cargo_combined', {}).get('top_patterns', [])[:15]:
                pattern_safe = pattern.replace('|', '\\|')
                report.append(f"| {pattern_safe} | {count:,} |")
            report.append("")

        # Section 5: Field Contamination
        report.append("## 5. Field Contamination")
        report.append("")
        contam_summary = contam.get('summary', {})
        report.append(f"- **Total contaminated records**: {contam_summary.get('total_contaminated_records', 0):,}")
        report.append(f"- **Cargo keywords in ship_name**: {contam.get('cargo_in_ship_name', {}).get('total', 0):,}")
        report.append(f"- **Date patterns in ship_name**: {contam.get('date_in_ship_name', {}).get('total', 0):,}")
        report.append(f"- **Quantity patterns in ship_name**: {contam.get('quantity_in_ship_name', {}).get('total', 0):,}")
        report.append(f"- **Consignee in origin port**: {contam.get('consignee_in_port', {}).get('total_origin', 0):,}")
        report.append(f"- **Consignee in destination port**: {contam.get('consignee_in_port', {}).get('total_destination', 0):,}")
        report.append("")

        # Section 6: Cargo Quality
        report.append("## 6. Cargo Quality")
        report.append("")
        cargo_summary = cargo.get('summary', {})
        report.append(f"- **Total cargo items**: {cargo_summary.get('total_cargo_items', 0):,}")
        report.append(f"- **Empty cargo shipments**: {cargo_summary.get('empty_cargo_shipments', 0):,} ({cargo_summary.get('empty_cargo_rate', 0)}%)")
        report.append(f"- **Quantity anomalies**: {cargo_summary.get('quantity_anomalies', 0):,}")
        report.append(f"- **Missing units**: {cargo_summary.get('missing_units', 0):,}")
        report.append(f"- **Missing commodities**: {cargo_summary.get('missing_commodities', 0):,}")
        report.append(f"- **Unique commodities**: {cargo.get('commodity_catalog', {}).get('total_unique', 0):,}")
        report.append(f"- **Unique units**: {cargo.get('unit_catalog', {}).get('total_unique', 0):,}")
        report.append("")

        # Section 7: By Year
        report.append("## 7. Issues by Year")
        report.append("")
        report.append("| Year | Shipments | Empty Origin | Empty Dest | Empty Cargo | Low Conf |")
        report.append("|------|-----------|--------------|------------|-------------|----------|")
        for year, stats in sorted(dq.get('by_year', {}).items()):
            report.append(
                f"| {year} | {stats.get('shipments', 0):,} | "
                f"{stats.get('empty_origin', 0):,} | "
                f"{stats.get('empty_destination', 0):,} | "
                f"{stats.get('empty_cargo', 0):,} | "
                f"{stats.get('low_confidence', 0):,} |"
            )
        report.append("")

        # Section 8: Recommendations
        report.append("## 8. Recommendations")
        report.append("")
        report.append("### High Priority (Immediate Action)")
        report.append("")
        report.append("1. **Remove duplicate records**: ~{:,} exact duplicates identified".format(
            dup_summary.get('exact_duplicate_records', 0)
        ))
        report.append("2. **Fix hallucination loops**: Review files with repeated text patterns")
        report.append("3. **Handle empty cargo**: {:,} shipments have no cargo data".format(
            cargo_summary.get('empty_cargo_shipments', 0)
        ))
        report.append("")
        report.append("### Medium Priority (Data Enrichment)")
        report.append("")
        report.append("4. **Split port+cargo combinations**: Apply rules from `port_parsing_fixes.json`")
        report.append("5. **Complete truncated ports**: Apply known fixes (BO → Bo'ness, etc.)")
        report.append("6. **Normalize OCR variants**: Map variant spellings to canonical forms")
        report.append("7. **Fix field contamination**: Cargo data in ship_name fields")
        report.append("")
        report.append("### Generated Fix Files")
        report.append("")
        report.append("- `reference_data/port_parsing_fixes.json` - Programmatic port fixes")
        report.append("- `reports/duplicate_records.csv` - Records to review/remove")
        report.append("- `reports/contaminated_records.csv` - Field contamination cases")
        report.append("")

        # Footer
        report.append("---")
        report.append("")
        report.append("*Report generated by timber shipment data quality analysis pipeline*")

        return "\n".join(report)

    def save_final_report(self):
        """Save the final combined report."""
        report_text = self.generate_final_report()

        # Save Markdown
        md_path = self.output_dir / 'FINAL_DATA_QUALITY_REPORT.md'
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(report_text)

        # Save combined JSON
        json_path = self.output_dir / 'combined_analysis.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                'generated_at': datetime.now().isoformat(),
                'reports': self.reports
            }, f, indent=2, default=str)

        print("=" * 70)
        print("FINAL REPORTS SAVED")
        print("=" * 70)
        print(f"  - {md_path}")
        print(f"  - {json_path}")

        return md_path, json_path


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Run all data quality analyses')
    parser.add_argument('--parsed-dir', default='/home/jic823/timber_data/parsed',
                        help='Directory containing parsed JSON files')
    parser.add_argument('--output-dir', default='/home/jic823/timber_data/reports',
                        help='Directory for output reports')
    parser.add_argument('--reference-dir', default='/home/jic823/timber_data/reference_data',
                        help='Directory for reference data files')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show progress during analysis')

    args = parser.parse_args()

    orchestrator = AnalysisOrchestrator(
        args.parsed_dir, args.output_dir, args.reference_dir
    )
    orchestrator.run_all_analyses(verbose=args.verbose)
    orchestrator.save_final_report()

    print()
    print("=" * 70)
    print("ALL ANALYSES COMPLETE")
    print("=" * 70)
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main()
