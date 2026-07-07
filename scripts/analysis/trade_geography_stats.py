#!/usr/bin/env python3
"""Statistical analysis of TTJ trade geography, 1874-1899.

Questions addressed:
  A. Partner concentration: do destination ports (especially small ones) depend
     on few origin ports? Tested against a multinomial null (each port drawing
     its N shipments from the national origin mix), which corrects for the
     mechanical concentration of small samples.
  B. Regional dependence: single-REGION (Scandinavia / British North America...)
     dependence of small ports.
  C. Commodity dominance: HHI of each commodity form across destination ports,
     location quotients (port specialisation), and time trends. Time trends are
     restricted to 1881-1899: before 1881 the journal covered only 16-38
     destination ports vs ~120 after, so pooled full-period HHI trends are a
     coverage artifact, not history.
  D. Route persistence: P(origin-dest route active in next valid year), by
     destination size; long-lived routes into small ports.
  E. Coast structure: destination coast (GB east / GB west / Ireland) x origin
     region; British North America share by coast and period.
  F. Origin-side spread: effective number of UK destinations per origin;
     steam vs sail by origin region (mechanism).

Constraints (see CLAUDE.md): unit = shipment counts, never quantities.
Valid years = 1874, 1875 + odd 1879-1899. 1877 excluded (London aggregated
format). Origin known for ~84% of shipments; analyses of origins use the
known-origin subset.

Outputs -> reports/trade_geography/*.csv + summary printed to stdout.
Deterministic (fixed RNG seed), re-runnable.
"""

import csv
import glob
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

BASE = Path('/home/jic823/timber_data')
OUT = BASE / 'reports' / 'trade_geography'
OUT.mkdir(parents=True, exist_ok=True)

VALID = sorted({1874, 1875, 1879, 1881, 1883, 1885, 1887, 1889, 1891, 1893, 1895, 1897, 1899})
VSET = set(VALID)
STABLE = [y for y in VALID if y >= 1881]  # stable journal coverage window
NSIM = 2000

def year_of(source_file):
    m = re.match(r'^(\d{4})', source_file) or re.search(r'(18\d{2}|1900)', source_file)
    return int(m.group(1)) if m else None

def hhi(counter):
    n = sum(counter.values())
    return sum((v / n) ** 2 for v in counter.values())

def load():
    region = {}
    viz = json.load(open(BASE / 'docs' / 'data.json'))
    for name, lat, lon, reg in viz['ports']:
        region[name.casefold()] = (reg, lat, lon)
    rows = []
    for f in glob.glob(str(BASE / 'normalized' / '*_normalized.json')):
        d = json.load(open(f))
        if d.get('status') != 'success':
            continue
        y = year_of(d.get('source_file', ''))
        if y not in VSET:
            continue
        for s in d['shipments']:
            dest = s.get('destination_port_normalized') if s.get('destination_port_status') in ('mapped', 'canonical') else None
            orig = s.get('origin_port_normalized') if s.get('origin_port_status') in ('mapped', 'canonical') else None
            forms = set()
            for c in s.get('cargo') or []:
                forms.update(c.get('commodity_forms') or [])
            oinfo = region.get(orig.casefold()) if orig else None
            dinfo = region.get(dest.casefold()) if dest else None
            rows.append({
                'year': y, 'dest': dest, 'orig': orig,
                'orig_region': oinfo[0] if oinfo else None,
                'dest_lat': dinfo[1] if dinfo else None,
                'dest_lon': dinfo[2] if dinfo else None,
                'forms': sorted(forms),
                'steam': bool(s.get('is_steamship')),
            })
    return rows

def write_csv(name, fieldnames, dicts):
    with open(OUT / name, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(dicts)
    print(f'wrote {OUT / name} ({len(dicts)} rows)')

def main():
    rng = np.random.default_rng(42)
    rows = load()
    both = [r for r in rows if r['dest'] and r['orig']]
    print(f'shipments in valid years: {len(rows)}; with both ports known: {len(both)}')

    origin_region = {r['orig']: r['orig_region'] for r in both if r['orig_region']}

    # ---- A. partner concentration vs multinomial null
    origins = sorted({r['orig'] for r in both})
    oidx = {o: i for i, o in enumerate(origins)}
    gcount = np.zeros(len(origins))
    for r in both:
        gcount[oidx[r['orig']]] += 1
    gprob = gcount / gcount.sum()

    dest_orig = defaultdict(Counter)
    dest_years = defaultdict(set)
    for r in both:
        dest_orig[r['dest']][r['orig']] += 1
        dest_years[r['dest']].add(r['year'])

    conc = []
    for dest, oc in dest_orig.items():
        n = sum(oc.values())
        if n < 30:
            continue
        top_orig, top_n = oc.most_common(1)[0]
        sims = rng.multinomial(n, gprob, size=NSIM)
        sim_top = sims.max(axis=1) / n
        conc.append({
            'dest': dest, 'n': n, 'n_years': len(dest_years[dest]),
            'top_origin': top_orig,
            'top_origin_region': origin_region.get(top_orig, ''),
            'top_share': round(top_n / n, 3),
            'null_top_share': round(float(sim_top.mean()), 3),
            'excess_top': round(top_n / n - float(sim_top.mean()), 3),
            'p_top': float((sim_top >= top_n / n).mean()),
            'hhi': round(hhi(oc), 3),
            'eff_partners': round(1 / hhi(oc), 1),
            'n_partners': len(oc),
        })
    conc.sort(key=lambda x: -x['excess_top'])
    write_csv('dest_concentration.csv', list(conc[0]), conc)
    dest_n = {c['dest']: c['n'] for c in conc}

    # ---- B. regional dependence
    dest_reg = defaultdict(Counter)
    for r in both:
        if r['orig_region']:
            dest_reg[r['dest']][r['orig_region']] += 1
    regdep = []
    for dest, rc in dest_reg.items():
        n = sum(rc.values())
        if n < 30:
            continue
        top_reg, top_n = rc.most_common(1)[0]
        regdep.append({'dest': dest, 'n': n, 'top_region': top_reg,
                       'top_region_share': round(top_n / n, 3),
                       'region_hhi': round(hhi(rc), 3)})
    regdep.sort(key=lambda x: -x['n'])
    write_csv('dest_region_dependence.csv', list(regdep[0]), regdep)

    # ---- C1. commodity concentration across ports, trend on stable window
    fdy = defaultdict(lambda: defaultdict(Counter))
    form_total = Counter()
    dest_total_forms = Counter()
    grand = 0
    for r in rows:
        if not r['dest']:
            continue
        for f in r['forms']:
            fdy[f][r['year']][r['dest']] += 1
            form_total[f] += 1
            dest_total_forms[r['dest']] += 1
            grand += 1
    comm = []
    for f, _ in form_total.most_common(20):
        yrs = [y for y in STABLE if sum(fdy[f][y].values()) >= 30]
        if len(yrs) < 6:
            continue
        hh = [hhi(fdy[f][y]) for y in yrs]
        rho, p = stats.spearmanr(yrs, hh)
        ce, cl = Counter(), Counter()
        for y in yrs:
            if y <= 1885:
                ce.update(fdy[f][y])
            elif y >= 1895:
                cl.update(fdy[f][y])
        te = ce.most_common(1)[0]
        tl = cl.most_common(1)[0]
        comm.append({'form': f, 'total': form_total[f],
                     'hhi_8185': round(float(np.mean(hh[:3])), 3),
                     'hhi_9599': round(float(np.mean(hh[-3:])), 3),
                     'trend_rho': round(float(rho), 2), 'trend_p': round(float(p), 3),
                     'top_port_8185': te[0], 'top_share_8185': round(te[1] / sum(ce.values()), 3),
                     'top_port_9599': tl[0], 'top_share_9599': round(tl[1] / sum(cl.values()), 3)})
    write_csv('commodity_concentration_1881_99.csv', list(comm[0]), comm)

    # ---- C2. location quotients (pooled, min 50)
    fd = Counter()
    for f, ymap in fdy.items():
        for y, dc in ymap.items():
            for d, v in dc.items():
                fd[(f, d)] += v
    lq = []
    for (f, d), v in fd.items():
        if v < 50:
            continue
        lift = (v / form_total[f]) / (dest_total_forms[d] / grand)
        lq.append({'form': f, 'dest': d, 'n': v,
                   'share_of_form': round(v / form_total[f], 3), 'lift': round(lift, 2)})
    lq.sort(key=lambda x: -x['lift'])
    write_csv('location_quotients.csv', list(lq[0]), lq)

    # ---- D. route persistence + long-lived small-port routes
    route_years = defaultdict(set)
    for r in both:
        route_years[(r['orig'], r['dest'])].add(r['year'])
    nxt = {y: VALID[i + 1] for i, y in enumerate(VALID[:-1])}
    size_class = lambda n: 'small(<300)' if n < 300 else ('mid(300-1000)' if n < 1000 else 'large(1000+)')
    pers = defaultdict(lambda: [0, 0])
    for (o, d), ys in route_years.items():
        if d not in dest_n:
            continue
        sc = size_class(dest_n[d])
        for y in ys:
            if y in nxt:
                pers[sc][1] += 1
                pers[sc][0] += nxt[y] in ys
    print('\nroute persistence P(active next valid year | active):')
    for sc, (a, b) in sorted(pers.items()):
        print(f'  {sc}: {a / b:.3f} (n={b})')

    ll = [{'dest': d, 'origin': o, 'origin_region': origin_region.get(o, ''),
           'years_active': len(ys), 'first': min(ys), 'last': max(ys),
           'dest_total': dest_n[d]}
          for (o, d), ys in route_years.items()
          if len(ys) >= 8 and d in dest_n and dest_n[d] < 1000]
    ll.sort(key=lambda x: -x['years_active'])
    write_csv('longlived_routes_small_mid_ports.csv', list(ll[0]), ll)

    # ---- E. coast x region; BNA share by coast/size/period
    def coast(r):
        lat, lon = r['dest_lat'], r['dest_lon']
        if lat is None:
            return None
        if lon < -5.3 and 51.3 < lat < 55.5:
            return 'Ireland'
        return 'GB east' if lon > -2.8 else 'GB west'

    per = lambda y: '1874-81' if y <= 1881 else ('1883-89' if y <= 1889 else '1891-99')
    coast_rows = []
    tab = defaultdict(Counter)
    for r in both:
        c = coast(r)
        if c and r['orig_region']:
            tab[(c, per(r['year']))][r['orig_region']] += 1
    for (c, p), rc in sorted(tab.items()):
        n = sum(rc.values())
        row = {'coast': c, 'period': p, 'n': n}
        for reg in ['Scandinavia', 'Russia & Baltic', 'Germany & Prussia',
                    'British North America', 'USA & Gulf', 'France & Low Countries']:
            row[reg] = round(rc[reg] / n, 3)
        coast_rows.append(row)
    write_csv('coast_region_period.csv', list(coast_rows[0]), coast_rows)

    # ---- F. origin-side spread + steam
    orig_dest = defaultdict(Counter)
    for r in both:
        orig_dest[r['orig']][r['dest']] += 1
    spread = []
    for o, dc in orig_dest.items():
        n = sum(dc.values())
        if n < 100:
            continue
        top_d, top_n = dc.most_common(1)[0]
        spread.append({'origin': o, 'region': origin_region.get(o, ''), 'n': n,
                       'eff_dests': round(1 / hhi(dc), 1), 'n_dests': len(dc),
                       'top_dest': top_d, 'top_dest_share': round(top_n / n, 3)})
    spread.sort(key=lambda x: -x['n'])
    write_csv('origin_spread.csv', list(spread[0]), spread)

    steam_rows = []
    st = defaultdict(lambda: [0, 0])
    for r in both:
        if r['orig_region']:
            k = (r['orig_region'], per(r['year']))
            st[k][0] += r['steam']
            st[k][1] += 1
    for (reg, p), (a, b) in sorted(st.items()):
        steam_rows.append({'origin_region': reg, 'period': p,
                           'steam_share': round(a / b, 3), 'n': b})
    write_csv('steam_share_region_period.csv', list(steam_rows[0]), steam_rows)


if __name__ == '__main__':
    main()
