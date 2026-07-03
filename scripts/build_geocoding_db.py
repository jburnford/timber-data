#!/usr/bin/env python3
"""
Build geocoding database from Ports_Master.geojson.
Outputs: reference_data/port_coordinates.json
"""

import json
from pathlib import Path


def build_geocoding_db(geojson_path: Path, output_path: Path):
    """Extract port coordinates from GeoJSON into a lookup dictionary."""

    coordinates = {}

    print(f"Loading {geojson_path}...")

    with open(geojson_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    features = data.get('features', [])
    print(f"Found {len(features)} features")

    for feature in features:
        try:
            props = feature.get('properties', {})
            name = props.get('Name', '').strip()

            geometry = feature.get('geometry', {})
            coords = geometry.get('coordinates', [])

            if name and len(coords) >= 2:
                lon, lat = coords[0], coords[1]

                # Store with original name
                coordinates[name] = {'lat': lat, 'lon': lon}

                # Also store lowercase and uppercase variants for lookups
                coordinates[name.lower()] = {'lat': lat, 'lon': lon}
                coordinates[name.upper()] = {'lat': lat, 'lon': lon}

        except Exception as e:
            print(f"Error processing feature: {e}")

    # Add some known port coordinates not in the GeoJSON
    additional_ports = {
        # Major Scandinavian ports
        'Gefle': {'lat': 60.6749, 'lon': 17.1413},
        'Gävle': {'lat': 60.6749, 'lon': 17.1413},
        'Sundsvall': {'lat': 62.3908, 'lon': 17.3069},
        'Sundswall': {'lat': 62.3908, 'lon': 17.3069},
        'Hernosand': {'lat': 62.6323, 'lon': 17.9408},
        'Härnösand': {'lat': 62.6323, 'lon': 17.9408},
        'Söderhamn': {'lat': 61.3042, 'lon': 17.0593},
        'Hudiksvall': {'lat': 61.7273, 'lon': 17.1057},
        'Örnsköldsvik': {'lat': 63.2909, 'lon': 18.7152},
        'Umeå': {'lat': 63.8258, 'lon': 20.2630},
        'Skellefteå': {'lat': 64.7507, 'lon': 20.9528},
        'Luleå': {'lat': 65.5848, 'lon': 22.1547},
        'Piteå': {'lat': 65.3174, 'lon': 21.4799},
        'Haparanda': {'lat': 65.8355, 'lon': 24.1369},
        'Karlshamn': {'lat': 56.1707, 'lon': 14.8615},
        'Karlskrona': {'lat': 56.1612, 'lon': 15.5869},
        'Kalmar': {'lat': 56.6634, 'lon': 16.3566},
        'Västervik': {'lat': 57.7584, 'lon': 16.6369},
        'Norrköping': {'lat': 58.5877, 'lon': 16.1924},
        'Stockholm': {'lat': 59.3293, 'lon': 18.0686},
        'Gothenburg': {'lat': 57.7089, 'lon': 11.9746},
        'Göteborg': {'lat': 57.7089, 'lon': 11.9746},
        'Malmö': {'lat': 55.6050, 'lon': 13.0038},

        # Norwegian ports
        'Christiania': {'lat': 59.9139, 'lon': 10.7522},
        'Kristiania': {'lat': 59.9139, 'lon': 10.7522},
        'Oslo': {'lat': 59.9139, 'lon': 10.7522},
        'Drammen': {'lat': 59.7441, 'lon': 10.2045},
        'Fredrikstad': {'lat': 59.2181, 'lon': 10.9298},
        'Fredrikshald': {'lat': 59.1260, 'lon': 11.3879},
        'Halden': {'lat': 59.1260, 'lon': 11.3879},
        'Trondhjem': {'lat': 63.4305, 'lon': 10.3951},
        'Trondheim': {'lat': 63.4305, 'lon': 10.3951},
        'Bergen': {'lat': 60.3913, 'lon': 5.3221},
        'Porsgrund': {'lat': 59.1396, 'lon': 9.6561},
        'Tonsberg': {'lat': 59.2676, 'lon': 10.4075},
        'Tønsberg': {'lat': 59.2676, 'lon': 10.4075},
        'Sandefjord': {'lat': 59.1308, 'lon': 10.2166},
        'Larvik': {'lat': 59.0533, 'lon': 10.0289},
        'Arendal': {'lat': 58.4616, 'lon': 8.7727},
        'Grimstad': {'lat': 58.3406, 'lon': 8.5937},
        'Mandal': {'lat': 58.0295, 'lon': 7.4610},
        'Stavanger': {'lat': 58.9700, 'lon': 5.7331},

        # Finnish ports
        'Helsinki': {'lat': 60.1699, 'lon': 24.9384},
        'Helsingfors': {'lat': 60.1699, 'lon': 24.9384},
        'Turku': {'lat': 60.4518, 'lon': 22.2666},
        'Åbo': {'lat': 60.4518, 'lon': 22.2666},
        'Vaasa': {'lat': 63.0960, 'lon': 21.6158},
        'Wasa': {'lat': 63.0960, 'lon': 21.6158},
        'Oulu': {'lat': 65.0121, 'lon': 25.4651},
        'Uleåborg': {'lat': 65.0121, 'lon': 25.4651},
        'Kotka': {'lat': 60.4664, 'lon': 26.9458},
        'Rauma': {'lat': 61.1273, 'lon': 21.5110},
        'Pori': {'lat': 61.4852, 'lon': 21.7958},
        'Björneborg': {'lat': 61.4852, 'lon': 21.7958},
        'Hanko': {'lat': 59.8241, 'lon': 22.9688},
        'Hangö': {'lat': 59.8241, 'lon': 22.9688},

        # Russian/Baltic ports
        'St. Petersburg': {'lat': 59.9343, 'lon': 30.3351},
        'Cronstadt': {'lat': 59.9917, 'lon': 29.7676},
        'Kronstadt': {'lat': 59.9917, 'lon': 29.7676},
        'Archangel': {'lat': 64.5399, 'lon': 40.5152},
        'Arkhangelsk': {'lat': 64.5399, 'lon': 40.5152},
        'Riga': {'lat': 56.9496, 'lon': 24.1052},
        'Libau': {'lat': 56.5047, 'lon': 21.0109},
        'Liepaja': {'lat': 56.5047, 'lon': 21.0109},
        'Liepāja': {'lat': 56.5047, 'lon': 21.0109},
        'Windau': {'lat': 57.3898, 'lon': 21.5617},
        'Ventspils': {'lat': 57.3898, 'lon': 21.5617},
        'Memel': {'lat': 55.7033, 'lon': 21.1443},
        'Klaipeda': {'lat': 55.7033, 'lon': 21.1443},
        'Wyborg': {'lat': 60.7079, 'lon': 28.7554},
        'Viborg': {'lat': 60.7079, 'lon': 28.7554},

        # German/Prussian ports
        'Danzig': {'lat': 54.3520, 'lon': 18.6466},
        'Gdańsk': {'lat': 54.3520, 'lon': 18.6466},
        'Königsberg': {'lat': 54.7104, 'lon': 20.4522},
        'Stettin': {'lat': 53.4285, 'lon': 14.5528},
        'Szczecin': {'lat': 53.4285, 'lon': 14.5528},
        'Hamburg': {'lat': 53.5511, 'lon': 9.9937},
        'Bremen': {'lat': 53.0793, 'lon': 8.8017},

        # Canadian ports
        'Quebec City': {'lat': 46.8139, 'lon': -71.2080},
        'Quebec': {'lat': 46.8139, 'lon': -71.2080},
        'Montreal': {'lat': 45.5017, 'lon': -73.5673},
        'Trois-Rivières': {'lat': 46.3432, 'lon': -72.5429},
        'Three Rivers': {'lat': 46.3432, 'lon': -72.5429},
        'St. John': {'lat': 45.2733, 'lon': -66.0633},
        'Halifax': {'lat': 44.6488, 'lon': -63.5752},
        'Chatham, N. B.': {'lat': 47.0429, 'lon': -65.4651},
        'Miramichi': {'lat': 47.0272, 'lon': -65.5052},
        'Richibucto': {'lat': 46.6833, 'lon': -64.8500},
        'Pictou': {'lat': 45.6789, 'lon': -62.7108},
        'Charlottetown': {'lat': 46.2382, 'lon': -63.1311},
        'Parrsborough': {'lat': 45.4048, 'lon': -64.3261},
        'Parrsboro': {'lat': 45.4048, 'lon': -64.3261},
        'Shediac': {'lat': 46.2195, 'lon': -64.5390},
        'Shédiac': {'lat': 46.2195, 'lon': -64.5390},
        'Pugwash': {'lat': 45.8500, 'lon': -63.6667},
        'Bathurst': {'lat': 47.6192, 'lon': -65.6515},

        # American ports
        'New York': {'lat': 40.7128, 'lon': -74.0060},
        'Boston': {'lat': 42.3601, 'lon': -71.0589},
        'Philadelphia': {'lat': 39.9526, 'lon': -75.1652},
        'Baltimore': {'lat': 39.2904, 'lon': -76.6122},
        'Norfolk': {'lat': 36.8508, 'lon': -76.2859},
        'Savannah': {'lat': 32.0809, 'lon': -81.0912},
        'Mobile': {'lat': 30.6954, 'lon': -88.0399},
        'New Orleans': {'lat': 29.9511, 'lon': -90.0715},
        'Pensacola': {'lat': 30.4213, 'lon': -87.2169},
        'Pascagoula': {'lat': 30.3658, 'lon': -88.5561},

        # French ports
        'Le Havre': {'lat': 49.4944, 'lon': 0.1079},
        'Lorient': {'lat': 47.7500, 'lon': -3.3667},
        'Saint-Brieuc': {'lat': 48.5144, 'lon': -2.7600},
        'La Roche-Bernard': {'lat': 47.5181, 'lon': -2.3031},
        'Bordeaux': {'lat': 44.8378, 'lon': -0.5792},

        # Spanish ports
        'A Coruña': {'lat': 43.3623, 'lon': -8.4115},
        'Bilbao': {'lat': 43.2627, 'lon': -2.9253},
        'Vigo': {'lat': 42.2406, 'lon': -8.7207},

        # Other
        'Constantinople': {'lat': 41.0082, 'lon': 28.9784},
        'Istanbul': {'lat': 41.0082, 'lon': 28.9784},
        'Rijeka': {'lat': 45.3271, 'lon': 14.4422},
        'Fiume': {'lat': 45.3271, 'lon': 14.4422},
        # British destination ports missing from Ports_Master.geojson
        "Bo'ness": {'lat': 56.0140, 'lon': -3.6080},
        'Borrowstounness': {'lat': 56.0140, 'lon': -3.6080},
        'Granton': {'lat': 55.9820, 'lon': -3.2290},
        'Shields': {'lat': 55.0080, 'lon': -1.4400},
        'North Shields': {'lat': 55.0087, 'lon': -1.4478},
        'South Shields': {'lat': 54.9990, 'lon': -1.4320},
        'Methil': {'lat': 56.1830, 'lon': -3.0220},
        'Fraserburgh': {'lat': 57.6930, 'lon': -2.0050},
        "King's Lynn": {'lat': 52.7520, 'lon': 0.3940},
        'Hartlepool (West)': {'lat': 54.6900, 'lon': -1.2120},
        'Shoreham': {'lat': 50.8320, 'lon': -0.2730},
        'Banff': {'lat': 57.6640, 'lon': -2.5240},
        'Ardrossan': {'lat': 55.6420, 'lon': -4.8090},
        'Charlestown': {'lat': 56.0380, 'lon': -3.5850},
        'Burntisland': {'lat': 56.0610, 'lon': -3.2330},
        'Inverness': {'lat': 57.4800, 'lon': -4.2240},
        'Wick': {'lat': 58.4410, 'lon': -3.0860},
        'Peterhead': {'lat': 57.5050, 'lon': -1.7840},
        'Sheerness': {'lat': 51.4410, 'lon': 0.7600},
        'Caernarfon': {'lat': 53.1400, 'lon': -4.2760},
        'Milford Haven': {'lat': 51.7140, 'lon': -5.0420},
        'Aberystwyth': {'lat': 52.4140, 'lon': -4.0830},
        # Scandinavian/Baltic timber-loading places (OCR-frequent)
        'Svartvik': {'lat': 62.3240, 'lon': 17.3660},
        'Uddevalla': {'lat': 58.3490, 'lon': 11.9380},
        'Jakobstad': {'lat': 63.6740, 'lon': 22.7020},
        'Kristiansund': {'lat': 63.1100, 'lon': 7.7280},
        'Fredriksvern': {'lat': 58.9980, 'lon': 10.0460},
        'Mem': {'lat': 58.4780, 'lon': 16.4160},
        'Stocka': {'lat': 61.9000, 'lon': 17.3400},
        'Sannesund': {'lat': 59.2830, 'lon': 11.1100},
        'Nyland': {'lat': 63.0070, 'lon': 17.7710},
        'Langror': {'lat': 61.4640, 'lon': 17.1280},
        'Vanevik': {'lat': 57.2080, 'lon': 16.4800},
        'Torefors': {'lat': 65.9060, 'lon': 22.6500},
        # other recurring origins
        'Dordrecht': {'lat': 51.8130, 'lon': 4.6900},
        'Sapelo': {'lat': 31.4750, 'lon': -81.2450},
        'Laguna': {'lat': 18.6500, 'lon': -91.8000},
        'Fernandina': {'lat': 30.6690, 'lon': -81.4630},
        'Galveston': {'lat': 29.3010, 'lon': -94.7980},
        'Fremantle': {'lat': -32.0560, 'lon': 115.7410},
        'Old Calabar': {'lat': 4.9580, 'lon': 8.3220},
        'St. Estephe': {'lat': 45.2630, 'lon': -0.7740},
        'Marseille': {'lat': 43.2960, 'lon': 5.3700},
        'New Richmond': {'lat': 48.1570, 'lon': -65.8670},
        'Newcastle, N.B.': {'lat': 46.9880, 'lon': -65.5680},
        'Norfolk': {'lat': 36.8500, 'lon': -76.2900},
    }

    for name, coords in additional_ports.items():
        if name not in coordinates:
            coordinates[name] = coords
        # Also add variants
        if name.lower() not in coordinates:
            coordinates[name.lower()] = coords
        if name.upper() not in coordinates:
            coordinates[name.upper()] = coords

    # Build output structure
    output = {
        'description': 'Port coordinates for timber trade geocoding',
        'source': str(geojson_path),
        'coordinates': coordinates,
        'stats': {
            'total_ports': len(set((c['lat'], c['lon']) for c in coordinates.values()))
        }
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nBuilt geocoding database with {len(coordinates)} port name variants")
    print(f"Written to {output_path}")

    return coordinates


if __name__ == "__main__":
    base_dir = Path("/home/jic823/timber_data")
    ttj_dir = Path("/home/jic823/TTJ Forest of Numbers")

    geojson_path = ttj_dir / "Ports_Master.geojson"
    output_path = base_dir / "reference_data" / "port_coordinates.json"

    build_geocoding_db(geojson_path, output_path)
