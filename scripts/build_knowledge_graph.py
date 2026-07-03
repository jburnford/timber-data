#!/usr/bin/env python3
"""Build the timber-trade knowledge graph from normalized/*.json.

Outputs (kg/):
  kg/timber.lbdb        Ladybug graph database (single file) — full
                        shipment-level graph, Cypher-queryable
  kg/timber_kg.json     aggregate JSON graph (nodes + year-weighted edges)
                        for lightweight sharing/visualization
  kg/README.md          written separately (schema + queries + caveats)

Schema (Ladybug):
  NODE Port(name, lat, lon, shipments_out, shipments_in)
  NODE Ship(name, shipments)
  NODE Merchant(name, shipments)
  NODE Commodity(form, shipments)
  NODE Species(name, shipments)
  NODE Shipment(record_id, year, arrival_date, arrival_iso, is_steamship,
                consignee_type, parse_confidence, origin_raw, destination_raw,
                source_file, line_number, raw_text)
  REL ARRIVED_FROM(Shipment->Port)      only normalized (mapped/canonical) ports
  REL ARRIVED_AT(Shipment->Port)
  REL BY_SHIP(Shipment->Ship)
  REL CONSIGNED_TO(Shipment->Merchant)  named consignees only
  REL CARRIED(Shipment->Commodity, quantity, unit, item_raw)
  REL CARRIED_SPECIES(Shipment->Species)
  REL ROUTE(Port->Port, year, shipments)   pre-aggregated convenience edges

Quantities are carried as raw strings for provenance only — OCR digits are
unreliable; count shipments, never sum quantities.
"""

import csv
import json
import glob
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

import ladybug

BASE = Path('/home/jic823/timber_data')
KG = BASE / 'kg'
BUILD = KG / '_build_csv'
DB_PATH = KG / 'timber.lbdb'

MONTH_NUM = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
             'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}
MONTH_NAMES = {m: i for i, m in enumerate(
    ['january', 'february', 'march', 'april', 'may', 'june', 'july',
     'august', 'september', 'october', 'november', 'december'], 1)}


def issue_date(source_file: str):
    """(year, month) of the journal issue, best effort."""
    m = re.match(r'^(\d{4})(\d{2})(\d{2})', source_file)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r'(January|February|March|April|May|June|July|August|'
                  r'September|October|November|December)\s+\d{1,2},?\s+(18\d\d|1900)',
                  source_file, re.I)
    if m:
        return int(m.group(2)), MONTH_NAMES[m.group(1).lower()]
    m = re.search(r'(18\d\d|1900)', source_file)
    return (int(m.group(1)), None) if m else (None, None)


def arrival_iso(arrival_date, iss_year, iss_month):
    """ISO date from 'Dec. 24' + issue year/month; December arrivals reported
    in January issues belong to the previous year."""
    if not arrival_date or not iss_year:
        return ''
    m = re.match(r'^([A-Za-z]{3})\.?\s+(\d{1,2})$', arrival_date.strip())
    if not m:
        return ''
    mon = MONTH_NUM.get(m.group(1).lower())
    day = int(m.group(2))
    if not mon or not 1 <= day <= 31:
        return ''
    year = iss_year
    if iss_month == 1 and mon == 12:
        year -= 1
    return f'{year:04d}-{mon:02d}-{day:02d}'


def sanitize(text, maxlen=300):
    if text is None:
        return ''
    t = re.sub(r'\s+', ' ', str(text)).strip()
    return t[:maxlen]


def good_port(s, side):
    if s.get(f'{side}_port_status') in ('mapped', 'canonical'):
        return s.get(f'{side}_port_normalized') or None
    return None


def main():
    KG.mkdir(exist_ok=True)
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir()
    if DB_PATH.exists():
        DB_PATH.unlink()
    wal = Path(str(DB_PATH) + '.wal')
    if wal.exists():
        wal.unlink()

    ports = {}                      # name -> [lat, lon, out, in]
    ships = Counter()
    merchants = Counter()
    commodities = Counter()
    species = Counter()
    route = Counter()               # (o, d, year) -> n
    port_imports = Counter()        # (dest, form, year) -> n
    port_exports = Counter()        # (orig, form, year) -> n
    merchant_dest = Counter()       # (merchant, dest, year) -> n

    def port_entry(name, s, side):
        e = ports.setdefault(name, [None, None, 0, 0])
        lat, lon = s.get(f'{side}_port_lat'), s.get(f'{side}_port_lon')
        if e[0] is None and lat is not None:
            e[0], e[1] = lat, lon
        return e

    f_ship = open(BUILD / 'shipments.csv', 'w', newline='')
    w_ship = csv.writer(f_ship)
    rels = {}
    for name in ['arrived_from', 'arrived_at', 'by_ship', 'consigned_to',
                 'carried', 'carried_species']:
        fh = open(BUILD / f'{name}.csv', 'w', newline='')
        rels[name] = (fh, csv.writer(fh))

    n_ship = 0
    files = sorted(glob.glob(str(BASE / 'normalized' / '*_normalized.json')))
    for f in files:
        d = json.load(open(f))
        if d.get('status') != 'success':
            continue
        iy, im = issue_date(d.get('source_file', ''))
        for s in d['shipments']:
            rid = s['record_id']
            n_ship += 1
            orig = good_port(s, 'origin')
            dest = good_port(s, 'destination')
            iso = arrival_iso(s.get('arrival_date'), iy, im)
            year = int(iso[:4]) if iso else (iy or '')

            w_ship.writerow([
                rid, year, sanitize(s.get('arrival_date'), 20), iso,
                bool(s.get('is_steamship')), s.get('consignee_type') or 'none',
                s.get('parse_confidence') or '', sanitize(s.get('origin_port_raw'), 80),
                sanitize(s.get('destination_port_raw'), 80),
                sanitize(d.get('source_file'), 160), s.get('line_number') or 0,
                sanitize(s.get('raw_text'), 400)])

            if orig:
                port_entry(orig, s, 'origin')[2] += 1
                rels['arrived_from'][1].writerow([rid, orig])
            if dest:
                port_entry(dest, s, 'destination')[3] += 1
                rels['arrived_at'][1].writerow([rid, dest])
            if orig and dest and year:
                route[(orig, dest, year)] += 1

            ship_name = sanitize(s.get('ship_name'), 80)
            if ship_name and len(ship_name) >= 2:
                ships[ship_name] += 1
                rels['by_ship'][1].writerow([rid, ship_name])

            if s.get('consignee_type') == 'named' and s.get('consignee_normalized'):
                mname = sanitize(s['consignee_normalized'], 100)
                merchants[mname] += 1
                rels['consigned_to'][1].writerow([rid, mname])
                if dest and year:
                    merchant_dest[(mname, dest, year)] += 1

            forms_seen = set()
            species_seen = set()
            for c in s.get('cargo') or []:
                for fm in c.get('commodity_forms') or []:
                    rels['carried'][1].writerow([
                        rid, fm, sanitize(c.get('quantity'), 20),
                        sanitize(c.get('unit'), 15), sanitize(c.get('raw_text'), 120)])
                    commodities[fm] += 0  # ensure key exists
                    forms_seen.add(fm)
                for sp in c.get('commodity_species') or []:
                    if sp not in species_seen:
                        rels['carried_species'][1].writerow([rid, sp])
                        species_seen.add(sp)
            for fm in forms_seen:
                commodities[fm] += 1
                if dest and year:
                    port_imports[(dest, fm, year)] += 1
                if orig and year:
                    port_exports[(orig, fm, year)] += 1
            for sp in species_seen:
                species[sp] += 1

    f_ship.close()
    for fh, _ in rels.values():
        fh.close()

    # node CSVs
    with open(BUILD / 'ports.csv', 'w', newline='') as fh:
        w = csv.writer(fh)
        for name, (lat, lon, out_n, in_n) in sorted(ports.items()):
            w.writerow([name, lat if lat is not None else '', lon if lon is not None else '', out_n, in_n])
    for fname, counter in [('ships.csv', ships), ('merchants.csv', merchants),
                           ('commodities.csv', commodities), ('species.csv', species)]:
        with open(BUILD / fname, 'w', newline='') as fh:
            w = csv.writer(fh)
            for name, n in sorted(counter.items()):
                w.writerow([name, n])
    with open(BUILD / 'route.csv', 'w', newline='') as fh:
        w = csv.writer(fh)
        for (o, dst, y), n in sorted(route.items()):
            w.writerow([o, dst, y, n])

    # ---------------- Ladybug DB ----------------
    db = ladybug.Database(str(DB_PATH))
    con = ladybug.Connection(db)
    ddl = [
        "CREATE NODE TABLE Port(name STRING, lat DOUBLE, lon DOUBLE, shipments_out INT64, shipments_in INT64, PRIMARY KEY(name))",
        "CREATE NODE TABLE Ship(name STRING, shipments INT64, PRIMARY KEY(name))",
        "CREATE NODE TABLE Merchant(name STRING, shipments INT64, PRIMARY KEY(name))",
        "CREATE NODE TABLE Commodity(form STRING, shipments INT64, PRIMARY KEY(form))",
        "CREATE NODE TABLE Species(name STRING, shipments INT64, PRIMARY KEY(name))",
        "CREATE NODE TABLE Shipment(record_id STRING, year INT64, arrival_date STRING, arrival_iso STRING, is_steamship BOOLEAN, consignee_type STRING, parse_confidence STRING, origin_raw STRING, destination_raw STRING, source_file STRING, line_number INT64, raw_text STRING, PRIMARY KEY(record_id))",
        "CREATE REL TABLE ARRIVED_FROM(FROM Shipment TO Port)",
        "CREATE REL TABLE ARRIVED_AT(FROM Shipment TO Port)",
        "CREATE REL TABLE BY_SHIP(FROM Shipment TO Ship)",
        "CREATE REL TABLE CONSIGNED_TO(FROM Shipment TO Merchant)",
        "CREATE REL TABLE CARRIED(FROM Shipment TO Commodity, quantity STRING, unit STRING, item_raw STRING)",
        "CREATE REL TABLE CARRIED_SPECIES(FROM Shipment TO Species)",
        "CREATE REL TABLE ROUTE(FROM Port TO Port, year INT64, shipments INT64)",
    ]
    for q in ddl:
        con.execute(q)
    copies = [
        ('Port', 'ports.csv'), ('Ship', 'ships.csv'), ('Merchant', 'merchants.csv'),
        ('Commodity', 'commodities.csv'), ('Species', 'species.csv'),
        ('Shipment', 'shipments.csv'),
        ('ARRIVED_FROM', 'arrived_from.csv'), ('ARRIVED_AT', 'arrived_at.csv'),
        ('BY_SHIP', 'by_ship.csv'), ('CONSIGNED_TO', 'consigned_to.csv'),
        ('CARRIED', 'carried.csv'), ('CARRIED_SPECIES', 'carried_species.csv'),
        ('ROUTE', 'route.csv'),
    ]
    for table, fname in copies:
        con.execute(f"COPY {table} FROM '{BUILD / fname}' "
                    "(header=false, quote='\"', escape='\"')")
        print(f'  loaded {table}')

    # sanity queries
    for q in ["MATCH (s:Shipment) RETURN count(s)",
              "MATCH (p:Port) RETURN count(p)",
              "MATCH (:Shipment)-[c:CARRIED]->(:Commodity) RETURN count(c)",
              "MATCH (p:Port)-[i:ROUTE]->(q:Port) RETURN count(i)"]:
        r = con.execute(q)
        print(q, '->', r.get_next())
    r = con.execute("""
        MATCH (s:Shipment)-[:ARRIVED_AT]->(p:Port {name:'Cardiff'}),
              (s)-[:CARRIED]->(c:Commodity {form:'pitwood'})
        RETURN s.year, count(DISTINCT s) ORDER BY s.year LIMIT 5""")
    print('Cardiff pitwood by year (sample):')
    while r.has_next():
        print('  ', r.get_next())
    con.close()
    db.close()

    # ---------------- aggregate JSON ----------------
    nodes = []
    for name, (lat, lon, out_n, in_n) in sorted(ports.items()):
        nodes.append({'id': f'port:{name}', 'type': 'Port', 'label': name,
                      'lat': lat, 'lon': lon,
                      'shipments_out': out_n, 'shipments_in': in_n})
    for fm, n in commodities.most_common():
        nodes.append({'id': f'commodity:{fm}', 'type': 'Commodity', 'label': fm,
                      'shipments': n})
    for sp, n in species.most_common():
        nodes.append({'id': f'species:{sp}', 'type': 'Species', 'label': sp,
                      'shipments': n})
    for m, n in merchants.most_common():
        nodes.append({'id': f'merchant:{m}', 'type': 'Merchant', 'label': m,
                      'shipments': n})

    def edge_rows(counter, etype, src_fmt, tgt_fmt):
        return [{'source': src_fmt.format(*k), 'target': tgt_fmt.format(*k),
                 'type': etype, 'year': k[2], 'shipments': n}
                for k, n in sorted(counter.items())]

    edges = []
    edges += edge_rows(route, 'ROUTE', 'port:{0}', 'port:{1}')
    edges += edge_rows(port_imports, 'IMPORTED', 'port:{0}', 'commodity:{1}')
    edges += edge_rows(port_exports, 'EXPORTED', 'port:{0}', 'commodity:{1}')
    edges += edge_rows(merchant_dest, 'RECEIVED_AT', 'merchant:{0}', 'port:{1}')

    kg = {
        'meta': {
            'title': 'British Timber Trade Knowledge Graph, 1874-1900',
            'source': 'Timber Trades Journal import lists (OCR, Gemini 2.5 Pro)',
            'built': '2026-07-03',
            'shipments': n_ship,
            'caveats': [
                'Edge weights are SHIPMENT COUNTS. OCR quantity digits are unreliable and are never summed.',
                'Coverage is odd-year heavy: even years 1876-1892 are nearly absent (volumes photographed every other year).',
                '1877 LONDON used an aggregated no-ship format that is not included.',
                'Edges use normalized port/merchant/commodity names; ~15% of origin mentions remain unnormalized and are excluded from edges (full records in the Ladybug DB retain raw values).',
            ],
        },
        'node_count': len(nodes),
        'edge_count': len(edges),
        'nodes': nodes,
        'edges': edges,
    }
    with open(KG / 'timber_kg.json', 'w') as fh:
        json.dump(kg, fh, indent=1, ensure_ascii=False)

    shutil.rmtree(BUILD)
    print(f'\nJSON: {len(nodes):,} nodes, {len(edges):,} edges -> kg/timber_kg.json')
    print(f'DB:   kg/timber.lbdb ({DB_PATH.stat().st_size/1e6:.1f} MB)')


if __name__ == '__main__':
    main()
