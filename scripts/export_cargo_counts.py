#!/usr/bin/env python3
"""Export shipment counts by port / commodity form / year from normalized/.

A shipment carrying "deals and battens" counts once for deals and once for
battens (commodity_forms). Quantities are deliberately NOT summed — OCR
quantity digits are unreliable (37.6% exact in earlier validation); counts
of shipments are the supported unit of analysis.

Outputs (exports/):
  shipments_by_year.csv
  dest_commodity_year.csv     destination x form x year
  origin_commodity_year.csv   origin x form x year
  route_year.csv              origin x destination x year (all cargo)
"""

import csv
import json
import glob
import re
from collections import Counter
from pathlib import Path

BASE = Path('/home/jic823/timber_data')
OUT = BASE / 'exports'
OUT.mkdir(exist_ok=True)


def year_of(source_file: str):
    m = re.match(r'^(\d{4})', source_file) or re.search(r'(18\d{2}|1900)', source_file)
    return int(m.group(1)) if m else None


def main():
    by_year = Counter()
    dest_form = Counter()
    orig_form = Counter()
    route = Counter()
    merchant_year = Counter()

    for f in glob.glob(str(BASE / 'normalized' / '*_normalized.json')):
        d = json.load(open(f))
        if d.get('status') != 'success':
            continue
        y = year_of(d.get('source_file', ''))
        for s in d['shipments']:
            by_year[y] += 1
            dest = s.get('destination_port_normalized') if s.get('destination_port_status') in ('mapped', 'canonical') else None
            orig = s.get('origin_port_normalized') if s.get('origin_port_status') in ('mapped', 'canonical') else None
            if dest and orig:
                route[(orig, dest, y)] += 1
            if s.get('consignee_type') == 'named' and s.get('consignee_normalized'):
                merchant_year[(s['consignee_normalized'], dest or '', y)] += 1
            forms = set()
            for c in s.get('cargo') or []:
                forms.update(c.get('commodity_forms') or [])
            for fm in forms:
                if dest:
                    dest_form[(dest, fm, y)] += 1
                if orig:
                    orig_form[(orig, fm, y)] += 1

    def write(name, counter, headers):
        with open(OUT / name, 'w', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(headers)
            for key, n in sorted(counter.items(), key=lambda x: (-x[1],) + tuple(str(k) for k in x[0]) if isinstance(x[0], tuple) else (-x[1], str(x[0]))):
                row = list(key) if isinstance(key, tuple) else [key]
                w.writerow(row + [n])

    write('shipments_by_year.csv', by_year, ['year', 'shipments'])
    write('dest_commodity_year.csv', dest_form, ['destination', 'commodity_form', 'year', 'shipments'])
    write('origin_commodity_year.csv', orig_form, ['origin', 'commodity_form', 'year', 'shipments'])
    write('route_year.csv', route, ['origin', 'destination', 'year', 'shipments'])
    write('merchant_dest_year.csv', merchant_year, ['merchant', 'destination', 'year', 'shipments'])

    print(f'shipments total: {sum(by_year.values()):,}')
    print(f'dest x form x year rows: {len(dest_form):,}')
    print(f'origin x form x year rows: {len(orig_form):,}')
    print(f'route x year rows: {len(route):,}')
    print('\ntop destination-commodity pairs (all years):')
    pair = Counter()
    for (d_, fm, y), n in dest_form.items():
        pair[(d_, fm)] += n
    for (d_, fm), n in pair.most_common(12):
        print(f'  {n:7,d}  {d_} <- {fm}')


if __name__ == '__main__':
    main()
