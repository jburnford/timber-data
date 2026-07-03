#!/usr/bin/env python3
"""Build compact JSON for the interactive visualizations (viz/).

Reads normalized/*.json, writes viz/data.json:
  ports:   [[name, lat, lon, region], ...]           (indexed)
  forms:   [form, ...]                               (top N + 'other')
  years:   [y0, y1]
  routes:  [[o, d, f, y, n], ...]   o/d port idx, f form idx (-1 = any cargo),
                                    both-geocoded shipments only
  imports: [[d, f, y, n], ...]      all dest-normalized shipments (f = -1 row too)
  exports: [[o, f, y, n], ...]      all origin-normalized shipments
Counts are shipments (a shipment with two forms counts once per form).
"""

import json
import glob
import re
from collections import Counter
from pathlib import Path

BASE = Path('/home/jic823/timber_data')
TOP_FORMS = None   # None = keep every commodity form; the tail (doors,
                   # mouldings, joinery...) carries the finished-goods story


def year_of(source_file):
    m = re.match(r'^(\d{4})', source_file) or re.search(r'(18\d{2}|1900)', source_file)
    return int(m.group(1)) if m else None


def region_of(name, lat, lon):
    """Coarse supply/market region for the shift view."""
    if lat is None:
        return 'Other'
    if 49.5 <= lat <= 61.5 and -11.5 <= lon <= 2.2:
        return 'Britain & Ireland'
    if lon < -30:
        if lat >= 43.5:
            return 'British North America'
        return 'USA & Gulf'
    if lat >= 54 and 4 <= lon <= 32 and not (lat < 57.5 and lon < 14):
        return 'Scandinavia'
    if 53 <= lat <= 57.6 and 8 <= lon <= 24:
        return 'Germany & Prussia'
    if lat >= 53.5 and lon > 19:
        return 'Russia & Baltic'
    if lon > 24 and lat > 40:
        return 'Russia & Baltic'
    if lat < 30:
        return 'Africa & Tropics'
    if lat < 44 and lon > -12:
        return 'Iberia & Mediterranean'
    if 42 <= lat <= 52 and -6 <= lon <= 9:
        return 'France & Low Countries'
    if 50 <= lat <= 54 and 2.2 < lon <= 8:
        return 'France & Low Countries'
    return 'Other'


# name-based fixes where lat/lon rules misfire
REGION_OVERRIDES = {
    'Memel': 'Russia & Baltic', 'Danzig': 'Germany & Prussia',
    'Konigsberg': 'Russia & Baltic', 'Riga': 'Russia & Baltic',
    'St. Petersburg': 'Russia & Baltic', 'Cronstadt': 'Russia & Baltic',
    'Archangel': 'Russia & Baltic', 'Onega': 'Russia & Baltic',
    'Narva': 'Russia & Baltic', 'Libau': 'Russia & Baltic',
    'Windau': 'Russia & Baltic', 'Pernau': 'Russia & Baltic',
    'Wyborg': 'Russia & Baltic', 'Stettin': 'Germany & Prussia',
    'Hamburg': 'Germany & Prussia', 'Bremen': 'Germany & Prussia',
}


def main():
    port_meta = {}
    form_count = Counter()
    routes = Counter()
    imports = Counter()
    exports = Counter()

    def good(s, side):
        if s.get(f'{side}_port_status') in ('mapped', 'canonical'):
            return s.get(f'{side}_port_normalized') or None
        return None

    files = sorted(glob.glob(str(BASE / 'normalized' / '*_normalized.json')))
    rows = []
    for f in files:
        d = json.load(open(f))
        if d.get('status') != 'success':
            continue
        y = year_of(d.get('source_file', ''))
        if not y:
            continue
        for s in d['shipments']:
            o, dst = good(s, 'origin'), good(s, 'destination')
            if o and o not in port_meta:
                port_meta[o] = (s.get('origin_port_lat'), s.get('origin_port_lon'))
            if dst and dst not in port_meta:
                port_meta[dst] = (s.get('destination_port_lat'), s.get('destination_port_lon'))
            forms = set()
            for c in s.get('cargo') or []:
                forms.update(c.get('commodity_forms') or [])
            for fm in forms:
                form_count[fm] += 1
            rows.append((o, dst, y, forms))

    top = [fm for fm, _ in form_count.most_common(TOP_FORMS)]
    fidx = {fm: i for i, fm in enumerate(top)}
    OTHER = len(top)   # unreachable when TOP_FORMS is None (all forms indexed)

    for o, dst, y, forms in rows:
        fset = {fidx.get(fm, OTHER) for fm in forms} or set()
        if o and dst:
            routes[(o, dst, -1, y)] += 1
            for fi in fset:
                routes[(o, dst, fi, y)] += 1
        if dst:
            imports[(dst, -1, y)] += 1
            for fi in fset:
                imports[(dst, fi, y)] += 1
        if o:
            exports[(o, -1, y)] += 1
            for fi in fset:
                exports[(o, fi, y)] += 1

    names = sorted(port_meta)
    pidx = {n: i for i, n in enumerate(names)}
    ports = []
    for n in names:
        lat, lon = port_meta[n]
        region = REGION_OVERRIDES.get(n) or region_of(n, lat, lon)
        ports.append([n, round(lat, 3) if lat is not None else None,
                      round(lon, 3) if lon is not None else None, region])

    out = {
        'forms': top + (['other'] if TOP_FORMS else []),
        'years': [1874, 1900],
        'ports': ports,
        'routes': [[pidx[o], pidx[d], fi, y, n] for (o, d, fi, y), n in sorted(routes.items())],
        'imports': [[pidx[d], fi, y, n] for (d, fi, y), n in sorted(imports.items())],
        'exports': [[pidx[o], fi, y, n] for (o, fi, y), n in sorted(exports.items())],
    }
    (BASE / 'viz').mkdir(exist_ok=True)
    with open(BASE / 'viz' / 'data.json', 'w') as fh:
        json.dump(out, fh, separators=(',', ':'))
    import os
    print(f"ports={len(ports)} routes={len(out['routes']):,} imports={len(out['imports']):,} "
          f"exports={len(out['exports']):,} size={os.path.getsize(BASE/'viz'/'data.json')//1024}KB")
    regs = Counter(p[3] for p in ports)
    print('regions:', dict(regs))


if __name__ == '__main__':
    main()
