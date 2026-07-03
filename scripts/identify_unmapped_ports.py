#!/usr/bin/env python3
"""
Identify unmapped ports by comparing unique ports against the authority.
Applies fuzzy matching to suggest potential matches.
Outputs: reference_data/unmapped_ports_for_review.csv
"""

import json
import csv
from pathlib import Path
from difflib import SequenceMatcher


def similarity(a: str, b: str) -> float:
    """Calculate string similarity ratio."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def find_best_match(port_name: str, canonical_ports: list, threshold: float = 0.85):
    """Find the best fuzzy match for a port name."""
    best_match = None
    best_score = 0

    for canonical in canonical_ports:
        score = similarity(port_name, canonical)
        if score > best_score:
            best_score = score
            best_match = canonical

    if best_score >= threshold:
        return best_match, best_score
    return None, best_score


def identify_unmapped_ports(
    unique_ports_path: Path,
    authority_path: Path,
    coordinates_path: Path,
    output_path: Path,
    fuzzy_min_count: int = 10  # Only do fuzzy matching for ports with >= this count
):
    """Identify ports that need mapping and suggest matches."""

    # Load authority mappings
    print("Loading port authority...")
    with open(authority_path, 'r', encoding='utf-8') as f:
        authority = json.load(f)

    mappings = authority.get('mappings', {})
    errors = set(authority.get('errors', []))

    # Build case-insensitive lookups
    mappings_lower = {k.lower(): v for k, v in mappings.items()}
    errors_lower = {e.lower() for e in errors}

    # Get list of canonical port names (unique values from mappings)
    canonical_ports = list(set(mappings.values()))
    print(f"  {len(canonical_ports)} canonical port names in authority")

    # Load coordinates
    print("\nLoading port coordinates...")
    with open(coordinates_path, 'r', encoding='utf-8') as f:
        coords_data = json.load(f)

    coordinates = coords_data.get('coordinates', {})
    geocoded_ports = set(coordinates.keys())
    geocoded_ports_lower = {p.lower() for p in geocoded_ports}
    print(f"  {len(geocoded_ports)} port names with coordinates")

    # Build combined lookup for fuzzy matching (only do this once)
    all_known_ports = list(set(canonical_ports) | geocoded_ports)

    # Load unique ports
    print("\nLoading unique ports...")
    unique_ports = []
    with open(unique_ports_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            unique_ports.append({
                'port_type': row['port_type'],
                'port_name': row['port_name'],
                'count': int(row['count'])
            })

    print(f"  {len(unique_ports)} unique port entries")

    # Analyze each port
    unmapped = []
    mapped_count = 0
    error_count = 0
    geocoded_count = 0

    for i, port_entry in enumerate(unique_ports):
        port_name = port_entry['port_name']
        port_type = port_entry['port_type']
        count = port_entry['count']
        port_lower = port_name.lower()

        # Check if it's a known error
        if port_lower in errors_lower:
            error_count += 1
            continue

        # Check if it's already mapped (case-insensitive)
        if port_lower in mappings_lower:
            mapped_count += 1
            canonical = mappings_lower[port_lower]
            if canonical.lower() in geocoded_ports_lower:
                geocoded_count += 1
            continue

        # Check if it's directly in geocoding db (already canonical)
        if port_lower in geocoded_ports_lower:
            mapped_count += 1
            geocoded_count += 1
            continue

        # Unmapped - optionally find best fuzzy match for high-frequency ports
        best_match = ''
        score = 0.0

        if count >= fuzzy_min_count:
            best_match, score = find_best_match(port_name, all_known_ports)
            if not best_match:
                best_match = ''

        unmapped.append({
            'port_type': port_type,
            'port_name': port_name,
            'count': count,
            'suggested_match': best_match,
            'match_score': round(score, 3),
            'action': '',  # For manual review
            'map_to': '',  # For manual input
            'notes': ''
        })

        if (i + 1) % 1000 == 0:
            print(f"  Processed {i+1}/{len(unique_ports)} ports...")

    # Sort unmapped by count (most frequent first)
    unmapped.sort(key=lambda x: x['count'], reverse=True)

    # Write output
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'port_type', 'port_name', 'count', 'suggested_match',
            'match_score', 'action', 'map_to', 'notes'
        ])
        writer.writeheader()
        writer.writerows(unmapped)

    print(f"\nResults:")
    print(f"  Already mapped: {mapped_count}")
    print(f"  Known errors: {error_count}")
    print(f"  Geocodable: {geocoded_count}")
    print(f"  Unmapped (need review): {len(unmapped)}")

    # Summary of top unmapped
    if unmapped:
        print(f"\nTop 30 unmapped ports by frequency:")
        for entry in unmapped[:30]:
            match_info = f" → {entry['suggested_match']} ({entry['match_score']})" if entry['suggested_match'] else ""
            print(f"  [{entry['port_type']}] {entry['port_name']}: {entry['count']}{match_info}")

    print(f"\nWritten to {output_path}")

    return unmapped


if __name__ == "__main__":
    base_dir = Path("/home/jic823/timber_data")
    ref_dir = base_dir / "reference_data"

    identify_unmapped_ports(
        unique_ports_path=ref_dir / "unique_ports.csv",
        authority_path=ref_dir / "port_authority.json",
        coordinates_path=ref_dir / "port_coordinates.json",
        output_path=ref_dir / "unmapped_ports_for_review.csv"
    )
