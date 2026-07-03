#!/usr/bin/env python3
"""
Normalize ports in parsed timber shipment files.
Applies authority mappings and adds coordinates.
Outputs: normalized/*_normalized.json
"""

import json
from pathlib import Path
from typing import Optional, Tuple
import argparse


class PortNormalizer:
    """Port normalization with authority lookups and geocoding."""

    def __init__(self, authority_path: Path, coordinates_path: Path):
        # Load authority
        with open(authority_path, 'r', encoding='utf-8') as f:
            authority = json.load(f)

        self.mappings = authority.get('mappings', {})
        self.errors = set(authority.get('errors', []))

        # Build case-insensitive lookup
        self.mappings_lower = {k.lower(): v for k, v in self.mappings.items()}

        # Load coordinates
        with open(coordinates_path, 'r', encoding='utf-8') as f:
            coords_data = json.load(f)

        self.coordinates = coords_data.get('coordinates', {})
        self.coordinates_lower = {k.lower(): v for k, v in self.coordinates.items()}

        # punctuation-insensitive lookups ("St. John, N.B" == "St. John, N.B.")
        self.mappings_squash = {}
        for k, v in self.mappings.items():
            self.mappings_squash.setdefault(self._squash(k), v)
        self.coordinates_squash = {}
        for k in self.coordinates:
            self.coordinates_squash.setdefault(self._squash(k), k)

    @staticmethod
    def _squash(name: str) -> str:
        import re
        return re.sub(r"[.,'\s]+", ' ', name).strip().lower()

    def normalize_port(self, port_name: str) -> Tuple[str, Optional[str]]:
        """
        Normalize a port name and return (normalized_name, status).

        Status values:
        - 'mapped': Found in authority mappings
        - 'canonical': Already canonical (has coordinates)
        - 'error': Known error/non-port
        - 'unmapped': Could not normalize
        """
        if not port_name or not port_name.strip():
            return port_name, 'empty'

        port_name = port_name.strip()

        # Check if it's a known error
        if port_name in self.errors or port_name.lower() in [e.lower() for e in self.errors]:
            return port_name, 'error'

        # Check exact match in mappings
        if port_name in self.mappings:
            return self.mappings[port_name], 'mapped'

        # Check case-insensitive match in mappings
        port_lower = port_name.lower()
        if port_lower in self.mappings_lower:
            return self.mappings_lower[port_lower], 'mapped'

        # Check if already canonical (has coordinates)
        if port_name in self.coordinates:
            return port_name, 'canonical'

        if port_lower in self.coordinates_lower:
            # Return the properly-cased version from coordinates
            for key in self.coordinates:
                if key.lower() == port_lower:
                    return key, 'canonical'

        # punctuation-insensitive fallback (strip trailing "(s)" first)
        import re
        squashed = self._squash(re.sub(r'\s*\(s\)\s*$', '', port_name))
        if squashed in self.mappings_squash:
            return self.mappings_squash[squashed], 'mapped'
        if squashed in self.coordinates_squash:
            return self.coordinates_squash[squashed], 'canonical'

        # Could not normalize
        return port_name, 'unmapped'

    def get_coordinates(self, port_name: str) -> Tuple[Optional[float], Optional[float]]:
        """Get lat/lon for a port name."""
        if not port_name:
            return None, None

        # Try exact match
        if port_name in self.coordinates:
            coords = self.coordinates[port_name]
            return coords.get('lat'), coords.get('lon')

        # Try case-insensitive
        port_lower = port_name.lower()
        if port_lower in self.coordinates_lower:
            coords = self.coordinates_lower[port_lower]
            return coords.get('lat'), coords.get('lon')

        return None, None


def normalize_file(
    parsed_file: Path,
    output_dir: Path,
    normalizer: PortNormalizer,
    verbose: bool = False
) -> dict:
    """Normalize ports in a single parsed JSON file."""

    with open(parsed_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    shipments = data.get('shipments', [])
    stats = {
        'total': len(shipments),
        'origin_mapped': 0,
        'origin_canonical': 0,
        'origin_error': 0,
        'origin_unmapped': 0,
        'destination_mapped': 0,
        'destination_canonical': 0,
        'destination_error': 0,
        'destination_unmapped': 0,
        'both_geocoded': 0,
        'origin_only_geocoded': 0,
        'destination_only_geocoded': 0,
        'neither_geocoded': 0
    }

    for shipment in shipments:
        # Normalize origin port
        origin = shipment.get('origin_port', '')
        origin_normalized, origin_status = normalizer.normalize_port(origin)
        origin_lat, origin_lon = normalizer.get_coordinates(origin_normalized)

        shipment['origin_port_raw'] = origin
        shipment['origin_port_normalized'] = origin_normalized
        shipment['origin_port_status'] = origin_status
        shipment['origin_port_lat'] = origin_lat
        shipment['origin_port_lon'] = origin_lon

        # Update stats
        if origin_status == 'mapped':
            stats['origin_mapped'] += 1
        elif origin_status == 'canonical':
            stats['origin_canonical'] += 1
        elif origin_status == 'error':
            stats['origin_error'] += 1
        else:
            stats['origin_unmapped'] += 1

        # Normalize destination port
        dest = shipment.get('destination_port', '')
        dest_normalized, dest_status = normalizer.normalize_port(dest)
        dest_lat, dest_lon = normalizer.get_coordinates(dest_normalized)

        shipment['destination_port_raw'] = dest
        shipment['destination_port_normalized'] = dest_normalized
        shipment['destination_port_status'] = dest_status
        shipment['destination_port_lat'] = dest_lat
        shipment['destination_port_lon'] = dest_lon

        # Update stats
        if dest_status == 'mapped':
            stats['destination_mapped'] += 1
        elif dest_status == 'canonical':
            stats['destination_canonical'] += 1
        elif dest_status == 'error':
            stats['destination_error'] += 1
        else:
            stats['destination_unmapped'] += 1

        # Geocoding status
        origin_geocoded = origin_lat is not None
        dest_geocoded = dest_lat is not None

        if origin_geocoded and dest_geocoded:
            shipment['port_normalization_status'] = 'both_geocoded'
            stats['both_geocoded'] += 1
        elif origin_geocoded:
            shipment['port_normalization_status'] = 'origin_only'
            stats['origin_only_geocoded'] += 1
        elif dest_geocoded:
            shipment['port_normalization_status'] = 'destination_only'
            stats['destination_only_geocoded'] += 1
        else:
            shipment['port_normalization_status'] = 'neither'
            stats['neither_geocoded'] += 1

    # Update data with normalization metadata
    data['normalization_stats'] = stats

    # Write output
    output_name = parsed_file.stem.replace('_deduped', '_normalized') + '.json'
    output_path = output_dir / output_name

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    if verbose:
        print(f"  {parsed_file.name} -> {output_path.name}")
        print(f"    Shipments: {stats['total']}")
        print(f"    Origin: {stats['origin_mapped']} mapped, {stats['origin_canonical']} canonical, {stats['origin_unmapped']} unmapped")
        print(f"    Dest: {stats['destination_mapped']} mapped, {stats['destination_canonical']} canonical, {stats['destination_unmapped']} unmapped")

    return stats


def normalize_all(
    parsed_dir: Path,
    output_dir: Path,
    authority_path: Path,
    coordinates_path: Path,
    sample_year: Optional[int] = None,
    verbose: bool = False
):
    """Normalize all parsed files."""

    print("Initializing port normalizer...")
    normalizer = PortNormalizer(authority_path, coordinates_path)
    print(f"  Loaded {len(normalizer.mappings)} mappings")
    print(f"  Loaded {len(normalizer.coordinates)} coordinate entries")

    # Get files to process
    parsed_files = list(parsed_dir.glob("*_deduped.json"))

    if sample_year:
        # Filter by year (look for year in filename)
        parsed_files = [f for f in parsed_files if str(sample_year) in f.name]
        print(f"\nProcessing {len(parsed_files)} files for year {sample_year}")
    else:
        print(f"\nProcessing {len(parsed_files)} parsed files")

    # Aggregate stats
    total_stats = {
        'files_processed': 0,
        'total_shipments': 0,
        'origin_mapped': 0,
        'origin_canonical': 0,
        'origin_error': 0,
        'origin_unmapped': 0,
        'destination_mapped': 0,
        'destination_canonical': 0,
        'destination_error': 0,
        'destination_unmapped': 0,
        'both_geocoded': 0,
        'origin_only_geocoded': 0,
        'destination_only_geocoded': 0,
        'neither_geocoded': 0
    }

    for i, parsed_file in enumerate(parsed_files):
        try:
            stats = normalize_file(parsed_file, output_dir, normalizer, verbose)

            total_stats['files_processed'] += 1
            total_stats['total_shipments'] += stats['total']
            total_stats['origin_mapped'] += stats['origin_mapped']
            total_stats['origin_canonical'] += stats['origin_canonical']
            total_stats['origin_error'] += stats['origin_error']
            total_stats['origin_unmapped'] += stats['origin_unmapped']
            total_stats['destination_mapped'] += stats['destination_mapped']
            total_stats['destination_canonical'] += stats['destination_canonical']
            total_stats['destination_error'] += stats['destination_error']
            total_stats['destination_unmapped'] += stats['destination_unmapped']
            total_stats['both_geocoded'] += stats['both_geocoded']
            total_stats['origin_only_geocoded'] += stats['origin_only_geocoded']
            total_stats['destination_only_geocoded'] += stats['destination_only_geocoded']
            total_stats['neither_geocoded'] += stats['neither_geocoded']

            if not verbose and (i + 1) % 100 == 0:
                print(f"  Processed {i + 1}/{len(parsed_files)} files...")

        except Exception as e:
            print(f"  Error processing {parsed_file.name}: {e}")

    # Print summary
    print(f"\n{'='*60}")
    print("NORMALIZATION SUMMARY")
    print(f"{'='*60}")
    print(f"Files processed: {total_stats['files_processed']}")
    print(f"Total shipments: {total_stats['total_shipments']}")

    total = total_stats['total_shipments']
    if total > 0:
        print(f"\nOrigin Ports:")
        print(f"  Mapped:    {total_stats['origin_mapped']:6d} ({100*total_stats['origin_mapped']/total:.1f}%)")
        print(f"  Canonical: {total_stats['origin_canonical']:6d} ({100*total_stats['origin_canonical']/total:.1f}%)")
        print(f"  Error:     {total_stats['origin_error']:6d} ({100*total_stats['origin_error']/total:.1f}%)")
        print(f"  Unmapped:  {total_stats['origin_unmapped']:6d} ({100*total_stats['origin_unmapped']/total:.1f}%)")

        origin_normalized = total_stats['origin_mapped'] + total_stats['origin_canonical']
        print(f"  TOTAL NORMALIZED: {origin_normalized:6d} ({100*origin_normalized/total:.1f}%)")

        print(f"\nDestination Ports:")
        print(f"  Mapped:    {total_stats['destination_mapped']:6d} ({100*total_stats['destination_mapped']/total:.1f}%)")
        print(f"  Canonical: {total_stats['destination_canonical']:6d} ({100*total_stats['destination_canonical']/total:.1f}%)")
        print(f"  Error:     {total_stats['destination_error']:6d} ({100*total_stats['destination_error']/total:.1f}%)")
        print(f"  Unmapped:  {total_stats['destination_unmapped']:6d} ({100*total_stats['destination_unmapped']/total:.1f}%)")

        dest_normalized = total_stats['destination_mapped'] + total_stats['destination_canonical']
        print(f"  TOTAL NORMALIZED: {dest_normalized:6d} ({100*dest_normalized/total:.1f}%)")

        print(f"\nGeocoding Coverage:")
        print(f"  Both ports:        {total_stats['both_geocoded']:6d} ({100*total_stats['both_geocoded']/total:.1f}%)")
        print(f"  Origin only:       {total_stats['origin_only_geocoded']:6d} ({100*total_stats['origin_only_geocoded']/total:.1f}%)")
        print(f"  Destination only:  {total_stats['destination_only_geocoded']:6d} ({100*total_stats['destination_only_geocoded']/total:.1f}%)")
        print(f"  Neither:           {total_stats['neither_geocoded']:6d} ({100*total_stats['neither_geocoded']/total:.1f}%)")

    return total_stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Normalize ports in parsed timber data')
    parser.add_argument('--year', type=int, help='Process only files from this year')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    args = parser.parse_args()

    base_dir = Path("/home/jic823/timber_data")
    parsed_dir = base_dir / "deduped"
    output_dir = base_dir / "normalized"
    ref_dir = base_dir / "reference_data"

    normalize_all(
        parsed_dir=parsed_dir,
        output_dir=output_dir,
        authority_path=ref_dir / "port_authority.json",
        coordinates_path=ref_dir / "port_coordinates.json",
        sample_year=args.year,
        verbose=args.verbose
    )
