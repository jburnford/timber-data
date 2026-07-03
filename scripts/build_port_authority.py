#!/usr/bin/env python3
"""
Build unified port authority by merging manual_port_matches.json and ports_completed.csv.
Outputs: reference_data/port_authority.json
"""

import json
import csv
from pathlib import Path


def build_port_authority(
    manual_matches_path: Path,
    ports_completed_path: Path,
    output_path: Path
):
    """Merge all port mappings into a unified authority file."""

    mappings = {}  # variant -> canonical
    errors = set()  # Known non-port entries
    sources = []

    # 1. Load manual_port_matches.json
    print("Loading manual port matches...")
    try:
        with open(manual_matches_path, 'r', encoding='utf-8') as f:
            manual_data = json.load(f)

        matches = manual_data.get('matches', {})
        for variant, canonical in matches.items():
            mappings[variant] = canonical
            # Also add case variants
            mappings[variant.upper()] = canonical
            mappings[variant.lower()] = canonical

        sources.append('manual_port_matches')
        print(f"  Loaded {len(matches)} manual mappings")

    except Exception as e:
        print(f"  Error loading manual matches: {e}")

    # 2. Load ports_completed.csv (only rows with action=MAP)
    print("\nLoading ports_completed.csv...")
    mapped_count = 0
    error_count = 0
    accepted_count = 0

    try:
        with open(ports_completed_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                action = row.get('action', '').strip().upper()
                original = row.get('original_port', '').strip()
                map_to = row.get('map_to_port', '').strip()

                if action == 'MAP' and original and map_to:
                    mappings[original] = map_to
                    # Also add case variants
                    mappings[original.upper()] = map_to
                    mappings[original.lower()] = map_to
                    mapped_count += 1

                elif action == 'ERROR' and original:
                    errors.add(original)
                    errors.add(original.upper())
                    errors.add(original.lower())
                    error_count += 1

                elif action == 'ACCEPT' and original:
                    # These are already canonical
                    accepted_count += 1

        sources.append('ports_completed')
        print(f"  Loaded {mapped_count} MAP rules, {error_count} ERROR rules, {accepted_count} ACCEPT rules")

    except Exception as e:
        print(f"  Error loading ports_completed: {e}")

    # Add common uppercase to lowercase mappings for destination ports
    # (destinations are often in ALL CAPS in the data)
    common_destinations = [
        ('LONDON', 'London'),
        ('LIVERPOOL', 'Liverpool'),
        ('HULL', 'Hull'),
        ('GLASGOW', 'Glasgow'),
        ('LEITH', 'Leith'),
        ('GRIMSBY', 'Grimsby'),
        ('GRANGEMOUTH', 'Grangemouth'),
        ('NEWCASTLE', 'Newcastle'),
        ('SUNDERLAND', 'Sunderland'),
        ('HARTLEPOOL', 'Hartlepool'),
        ('WHITBY', 'Whitby'),
        ('STOCKTON', 'Stockton'),
        ('MIDDLESBROUGH', 'Middlesbrough'),
        ('GOOLE', 'Goole'),
        ('BOSTON', 'Boston'),
        ('YARMOUTH', 'Yarmouth'),
        ('IPSWICH', 'Ipswich'),
        ('HARWICH', 'Harwich'),
        ('COLCHESTER', 'Colchester'),
        ('ROCHESTER', 'Rochester'),
        ('DOVER', 'Dover'),
        ('FOLKESTONE', 'Folkestone'),
        ('PORTSMOUTH', 'Portsmouth'),
        ('SOUTHAMPTON', 'Southampton'),
        ('POOLE', 'Poole'),
        ('WEYMOUTH', 'Weymouth'),
        ('PLYMOUTH', 'Plymouth'),
        ('FALMOUTH', 'Falmouth'),
        ('SWANSEA', 'Swansea'),
        ('CARDIFF', 'Cardiff'),
        ('BRISTOL', 'Bristol'),
        ('NEWPORT', 'Newport'),
        ('BARRY', 'Barry'),
        ('PENARTH', 'Penarth'),
        ('TRURO', 'Truro'),
        ('BRIDGWATER', 'Bridgwater'),
        ('WHITEHAVEN', 'Whitehaven'),
        ('WORKINGTON', 'Workington'),
        ('MARYPORT', 'Maryport'),
        ('BARROW-IN-FURNESS', 'Barrow-in-Furness'),
        ('FLEETWOOD', 'Fleetwood'),
        ('PRESTON', 'Preston'),
        ('BIRKENHEAD', 'Birkenhead'),
        ('CHESTER', 'Chester'),
        ('DUNDEE', 'Dundee'),
        ('ABERDEEN', 'Aberdeen'),
        ('MONTROSE', 'Montrose'),
        ('ARBROATH', 'Arbroath'),
        ('KIRKCALDY', 'Kirkcaldy'),
        ('ALLOA', 'Alloa'),
        ('STIRLING', 'Stirling'),
        ('AIRDRIE', 'Airdrie'),
        ('GREENOCK', 'Greenock'),
        ('AYR', 'Ayr'),
        ('IRVINE', 'Irvine'),
        ('TROON', 'Troon'),
        ('ARDROSSAN', 'Ardrossan'),
        ('DUMFRIES', 'Dumfries'),
        ('BELFAST', 'Belfast'),
        ('DUBLIN', 'Dublin'),
        ('CORK', 'Cork'),
        ('WATERFORD', 'Waterford'),
        ('LIMERICK', 'Limerick'),
        ('GALWAY', 'Galway'),
        ('LONDONDERRY', 'Londonderry'),
        ('NEWRY', 'Newry'),
        ('DUNDALK', 'Dundalk'),
        ('DROGHEDA', 'Drogheda'),
        ('WEXFORD', 'Wexford'),
        ('SLIGO', 'Sligo'),
        ('TRALEE', 'Tralee'),
        # quick wins from unmapped-destination analysis (2026-07)
        ('HARTLEPOOL (WEST)', 'Hartlepool (West)'),
        ('HARTLEPOOL (WEST:', 'Hartlepool (West)'),
        ('WEST HARTLEPOOL', 'Hartlepool (West)'),
        ('EAST HARTLEPOOL', 'Hartlepool'),
        ("BO'NESS", "Bo'ness"),
        ('BO', "Bo'ness"),
        ('BORROWSTOUNNESS', 'Borrowstounness'),
        ('GRANTON', 'Granton'),
        ('SHIELDS', 'Shields'),
        ('NORTH SHIELDS', 'North Shields'),
        ('SOUTH SHIELDS', 'South Shields'),
        ('LYNN', "King's Lynn"),
        ("KING'S LYNN", "King's Lynn"),
        ('KING', "King's Lynn"),
        ('BARROW', 'Barrow-in-Furness'),
        ('METHIL', 'Methil'),
        ('FRASERBURGH', 'Fraserburgh'),
        ('SHOREHAM', 'Shoreham'),
        ('BANFF', 'Banff'),
        ('GLOUCESTER', 'Gloucester'),
        ('SHARPNESS', 'Sharpness'),
        ('NEWPORT (MON', 'Newport'),
        ('NEWPORT (MON.)', 'Newport'),
        ('NEWPORT, MON', 'Newport'),
        ('TYNE', 'Newcastle'),
        ('EXMOUTH', 'Exmouth'),
        ('TEIGNMOUTH', 'Teignmouth'),
        ('PETERHEAD', 'Peterhead'),
        ('INVERNESS', 'Inverness'),
        ('WICK', 'Wick'),
        ('BURNTISLAND', 'Burntisland'),
        ('CHARLESTOWN', 'Charlestown'),
        ('ARDROSSAN', 'Ardrossan'),
        ('MIDDLESBOROUGH', 'Middlesbrough'),
        ('CARNARVON', 'Caernarfon'),
        ('MILFORD', 'Milford Haven'),
        ('MILFORD HAVEN', 'Milford Haven'),
        ('ABERYSTWITH', 'Aberystwyth'),
        ('HARTLEPOOL, WEST', 'Hartlepool (West)'),
        ('NEWPORT (MON)', 'Newport'),
        ('NEWPORT(MON)', 'Newport'),
        # origin-port OCR variants (2026-07)
        ("G'burg", 'Gothenburg'),
        ('Swartvik', 'Svartvik'),
        ('Swartwick', 'Svartvik'),
        ('Christiana', 'Christiania'),
        ('Uddewalla', 'Uddevalla'),
        ('Jacobstad', 'Jakobstad'),
        ('Christiansund', 'Kristiansund'),
        ('Fredriksvoern', 'Fredriksvern'),
        ('Dordt', 'Dordrecht'),
        ('Wanevik', 'Vanevik'),
        ('St. John, N.B.', 'St. John'),
        ("St. John's, N.B.", 'St. John'),
        ('Halifax, N.S.', 'Halifax'),
        ('Chatham, N.B.', 'Chatham, N. B.'),
        ('Bathurst, N.B.', 'Bathurst'),
        ('Norfolk, Va.', 'Norfolk'),
        ('Portland, Me.', 'Portland'),
        ('Newcastle, N.B.', 'Newcastle, N.B.'),
    ]

    for upper, canonical in common_destinations:
        if upper not in mappings:
            mappings[upper] = canonical

    # consignee/marker leakage into port fields — never ports
    errors.update(['Order', 'ORDER', 'order', '(s)', 'Ditto', 'ditto'])

    # --- repair double-encoded UTF-8 from ports_completed.csv ("GÃ¤vle") ---
    import re as _re

    def fix_enc(s):
        if isinstance(s, str) and _re.search(r'[ÃÂ]', s):
            try:
                return s.encode('latin-1').decode('utf-8')
            except (UnicodeEncodeError, UnicodeDecodeError):
                return s
        return s

    repaired = {}
    for k, v in mappings.items():
        fk, fv = fix_enc(k), fix_enc(v)
        repaired[k] = fv          # keep original (possibly mojibake) key too
        repaired[fk] = fv
    mappings = repaired

    # --- resolve transitive/circular chains (Gefle <-> Gävle) ---
    def resolve(name, seen=None):
        seen = seen or []
        if name in seen:                       # cycle: deterministic winner
            return sorted(seen)[0]
        if name in mappings and mappings[name] != name:
            return resolve(mappings[name], seen + [name])
        return name

    mappings = {k: resolve(v) if v in mappings else v
                for k, v in mappings.items()}

    # Build final authority structure
    authority = {
        'description': 'Unified port authority for timber trade normalization',
        'mappings': mappings,
        'errors': sorted(list(errors)),
        'sources': sources,
        'stats': {
            'total_mappings': len(set(mappings.values())),
            'total_variants': len(mappings),
            'total_errors': len(errors)
        }
    }

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(authority, f, indent=2, ensure_ascii=False)

    print(f"\nBuilt port authority with:")
    print(f"  {len(mappings)} variant-to-canonical mappings")
    print(f"  {len(errors)} known error entries")
    print(f"  Sources: {sources}")
    print(f"\nWritten to {output_path}")

    return authority


if __name__ == "__main__":
    base_dir = Path("/home/jic823/timber_data")
    ttj_dir = Path("/home/jic823/TTJ Forest of Numbers")

    manual_matches_path = ttj_dir / "reference_data" / "manual_port_matches.json"
    ports_completed_path = ttj_dir / "final_output" / "authority_normalized" / "ports_completed.csv"
    output_path = base_dir / "reference_data" / "port_authority.json"

    build_port_authority(manual_matches_path, ports_completed_path, output_path)
