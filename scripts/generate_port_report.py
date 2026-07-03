#!/usr/bin/env python3
"""
Generate port normalization coverage report from normalized files.
Outputs: reference_data/port_coverage_report.txt
"""

import json
from pathlib import Path
from collections import Counter
from datetime import datetime


def generate_report(normalized_dir: Path, output_path: Path):
    """Generate comprehensive port coverage report."""

    # Collect data from all normalized files
    normalized_files = list(normalized_dir.glob("*_normalized.json"))
    print(f"Analyzing {len(normalized_files)} normalized files...")

    # Aggregate statistics
    total_shipments = 0
    origin_status_counts = Counter()
    destination_status_counts = Counter()
    geocoding_counts = Counter()

    # Track unmapped ports with frequencies
    unmapped_origins = Counter()
    unmapped_destinations = Counter()

    # Track normalized ports
    normalized_origin_ports = Counter()
    normalized_destination_ports = Counter()

    for nf in normalized_files:
        try:
            with open(nf, 'r', encoding='utf-8') as f:
                data = json.load(f)

            shipments = data.get('shipments', [])
            total_shipments += len(shipments)

            for shipment in shipments:
                # Origin stats
                origin_status = shipment.get('origin_port_status', 'unknown')
                origin_status_counts[origin_status] += 1

                if origin_status == 'unmapped':
                    unmapped_origins[shipment.get('origin_port_normalized', '')] += 1
                else:
                    normalized_origin_ports[shipment.get('origin_port_normalized', '')] += 1

                # Destination stats
                dest_status = shipment.get('destination_port_status', 'unknown')
                destination_status_counts[dest_status] += 1

                if dest_status == 'unmapped':
                    unmapped_destinations[shipment.get('destination_port_normalized', '')] += 1
                else:
                    normalized_destination_ports[shipment.get('destination_port_normalized', '')] += 1

                # Geocoding stats
                geo_status = shipment.get('port_normalization_status', 'unknown')
                geocoding_counts[geo_status] += 1

        except Exception as e:
            print(f"  Error processing {nf.name}: {e}")

    # Calculate percentages
    def pct(count, total):
        return f"{100*count/total:.1f}%" if total > 0 else "0%"

    # Generate report
    lines = []
    lines.append("=" * 70)
    lines.append("PORT NORMALIZATION COVERAGE REPORT")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 70)
    lines.append("")

    lines.append("SUMMARY")
    lines.append("-" * 40)
    lines.append(f"Total normalized files: {len(normalized_files)}")
    lines.append(f"Total shipments: {total_shipments:,}")
    lines.append("")

    # Origin port normalization
    lines.append("ORIGIN PORT NORMALIZATION")
    lines.append("-" * 40)
    origin_normalized = origin_status_counts['mapped'] + origin_status_counts['canonical']
    lines.append(f"Mapped (via authority):  {origin_status_counts['mapped']:>8,} ({pct(origin_status_counts['mapped'], total_shipments)})")
    lines.append(f"Canonical (already OK):  {origin_status_counts['canonical']:>8,} ({pct(origin_status_counts['canonical'], total_shipments)})")
    lines.append(f"Error (non-port):        {origin_status_counts['error']:>8,} ({pct(origin_status_counts['error'], total_shipments)})")
    lines.append(f"Unmapped:                {origin_status_counts['unmapped']:>8,} ({pct(origin_status_counts['unmapped'], total_shipments)})")
    lines.append(f"Empty:                   {origin_status_counts.get('empty', 0):>8,}")
    lines.append("")
    lines.append(f"TOTAL NORMALIZED:        {origin_normalized:>8,} ({pct(origin_normalized, total_shipments)})")
    lines.append("")

    # Destination port normalization
    lines.append("DESTINATION PORT NORMALIZATION")
    lines.append("-" * 40)
    dest_normalized = destination_status_counts['mapped'] + destination_status_counts['canonical']
    lines.append(f"Mapped (via authority):  {destination_status_counts['mapped']:>8,} ({pct(destination_status_counts['mapped'], total_shipments)})")
    lines.append(f"Canonical (already OK):  {destination_status_counts['canonical']:>8,} ({pct(destination_status_counts['canonical'], total_shipments)})")
    lines.append(f"Error (non-port):        {destination_status_counts['error']:>8,} ({pct(destination_status_counts['error'], total_shipments)})")
    lines.append(f"Unmapped:                {destination_status_counts['unmapped']:>8,} ({pct(destination_status_counts['unmapped'], total_shipments)})")
    lines.append(f"Empty:                   {destination_status_counts.get('empty', 0):>8,}")
    lines.append("")
    lines.append(f"TOTAL NORMALIZED:        {dest_normalized:>8,} ({pct(dest_normalized, total_shipments)})")
    lines.append("")

    # Geocoding coverage
    lines.append("GEOCODING COVERAGE")
    lines.append("-" * 40)
    lines.append(f"Both ports geocoded:     {geocoding_counts['both_geocoded']:>8,} ({pct(geocoding_counts['both_geocoded'], total_shipments)})")
    lines.append(f"Origin only:             {geocoding_counts['origin_only']:>8,} ({pct(geocoding_counts['origin_only'], total_shipments)})")
    lines.append(f"Destination only:        {geocoding_counts['destination_only']:>8,} ({pct(geocoding_counts['destination_only'], total_shipments)})")
    lines.append(f"Neither:                 {geocoding_counts['neither']:>8,} ({pct(geocoding_counts['neither'], total_shipments)})")
    lines.append("")

    # Top unmapped ports
    lines.append("TOP 50 UNMAPPED ORIGIN PORTS")
    lines.append("-" * 40)
    for port, count in unmapped_origins.most_common(50):
        lines.append(f"  {port}: {count:,}")
    lines.append("")

    lines.append("TOP 50 UNMAPPED DESTINATION PORTS")
    lines.append("-" * 40)
    for port, count in unmapped_destinations.most_common(50):
        lines.append(f"  {port}: {count:,}")
    lines.append("")

    # Top normalized ports
    lines.append("TOP 30 NORMALIZED ORIGIN PORTS")
    lines.append("-" * 40)
    for port, count in normalized_origin_ports.most_common(30):
        lines.append(f"  {port}: {count:,}")
    lines.append("")

    lines.append("TOP 30 NORMALIZED DESTINATION PORTS")
    lines.append("-" * 40)
    for port, count in normalized_destination_ports.most_common(30):
        lines.append(f"  {port}: {count:,}")
    lines.append("")

    lines.append("=" * 70)

    # Write report
    report_text = "\n".join(lines)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report_text)

    print(report_text)
    print(f"\nReport written to {output_path}")

    # Also output as JSON for programmatic use
    json_output = {
        'generated': datetime.now().isoformat(),
        'total_files': len(normalized_files),
        'total_shipments': total_shipments,
        'origin_status': dict(origin_status_counts),
        'destination_status': dict(destination_status_counts),
        'geocoding_status': dict(geocoding_counts),
        'unmapped_origins': dict(unmapped_origins.most_common(100)),
        'unmapped_destinations': dict(unmapped_destinations.most_common(100)),
        'top_origin_ports': dict(normalized_origin_ports.most_common(50)),
        'top_destination_ports': dict(normalized_destination_ports.most_common(50)),
        'coverage': {
            'origin_normalized_pct': round(100 * origin_normalized / total_shipments, 2) if total_shipments else 0,
            'destination_normalized_pct': round(100 * dest_normalized / total_shipments, 2) if total_shipments else 0,
            'both_geocoded_pct': round(100 * geocoding_counts['both_geocoded'] / total_shipments, 2) if total_shipments else 0
        }
    }

    json_path = output_path.parent / 'port_coverage_report.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_output, f, indent=2)

    print(f"JSON report written to {json_path}")

    return json_output


if __name__ == "__main__":
    base_dir = Path("/home/jic823/timber_data")
    normalized_dir = base_dir / "normalized"
    output_path = base_dir / "reference_data" / "port_coverage_report.txt"

    generate_report(normalized_dir, output_path)
