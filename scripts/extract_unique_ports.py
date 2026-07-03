#!/usr/bin/env python3
"""
Extract unique ports from parsed timber shipment data.
Outputs: reference_data/unique_ports.csv
"""

import json
import csv
from pathlib import Path
from collections import Counter

def extract_unique_ports(parsed_dir: Path, output_path: Path):
    """Extract all unique origin and destination ports with counts."""

    origin_ports = Counter()
    destination_ports = Counter()

    parsed_files = list(parsed_dir.glob("*_parsed.json"))
    print(f"Found {len(parsed_files)} parsed JSON files")

    total_shipments = 0

    for json_file in parsed_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            shipments = data.get('shipments', [])
            total_shipments += len(shipments)

            for shipment in shipments:
                origin = shipment.get('origin_port') or ''
                destination = shipment.get('destination_port') or ''
                origin = origin.strip() if origin else ''
                destination = destination.strip() if destination else ''

                if origin:
                    origin_ports[origin] += 1
                if destination:
                    destination_ports[destination] += 1

        except Exception as e:
            print(f"Error processing {json_file.name}: {e}")

    print(f"\nProcessed {total_shipments} total shipments")
    print(f"Found {len(origin_ports)} unique origin ports")
    print(f"Found {len(destination_ports)} unique destination ports")

    # Write to CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['port_type', 'port_name', 'count'])

        # Write origin ports sorted by count (descending)
        for port, count in origin_ports.most_common():
            writer.writerow(['origin', port, count])

        # Write destination ports sorted by count (descending)
        for port, count in destination_ports.most_common():
            writer.writerow(['destination', port, count])

    print(f"\nWritten to {output_path}")

    # Summary statistics
    print("\nTop 20 Origin Ports:")
    for port, count in origin_ports.most_common(20):
        print(f"  {port}: {count}")

    print("\nTop 20 Destination Ports:")
    for port, count in destination_ports.most_common(20):
        print(f"  {port}: {count}")

    return origin_ports, destination_ports


if __name__ == "__main__":
    base_dir = Path("/home/jic823/timber_data")
    parsed_dir = base_dir / "parsed"
    output_path = base_dir / "reference_data" / "unique_ports.csv"

    extract_unique_ports(parsed_dir, output_path)
