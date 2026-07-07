#!/usr/bin/env python3
"""Phase 2 statistics: Canada in the UK timber trade, TTJ microdata.

Sections:
  A. Species-aware square-vs-sawn classification of Canadian shipments,
     compared with official decennial loads shares and JHG Fig3 (loads-adj).
  C. Calibrated annual volume shares 1874-1899 (count shares reweighted by
     country loads-per-shipment at decennial anchors) + validation vs the
     JHG Fig3 annual Canada series.
  D. Within-Canada port decomposition (Quebec/Montreal/Saint John/Miramichi).
  E. Seasonality: arrival-month mix as coverage-bias check (1891 dip).
  F. Cluster-bootstrap trend test for Canada's count share.

Coverage note (per Clifford & Castonguay 2022, pp. 128, 131-132): JHG Fig3
covers the LAURENTIAN VALLEY ONLY (Quebec/Montreal exports, NB/NS excluded),
from Canadian export records with piece-based cu-ft conversions. Official
"British North America" loads include the Maritimes. Fig3 square matches
official hewn x50 because square timber was almost entirely a Quebec trade;
Fig3 sawn is ~35% of official BNA sawn (the Maritimes shipped the rest).
The kf rescaling below (~17.6 cu ft per official sawn load) therefore
embeds the assumption that the Laurentian share of BNA sawn volume was
constant (34.8%/35.8% at the 1881/1891 anchors). Official loads are the
level anchor; Fig3 supplies annual timing. Laurentian-restricted
comparisons live in canada_laurentian.py.
"""
import csv
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from canada_country_analysis import COUNTRY, VALID_YEARS, year_of, NORM, doc_group

BASE = Path('/home/jic823/timber_data')
UKGOV = Path('/mnt/c/Users/jic823/Dropbox/2026/Full British Imports Database.xlsx - Sheet1.csv')
JHG = '/mnt/c/Users/jic823/Dropbox/2026/JHG-data2022.xlsx'

EIGHT = ['Canada', 'Sweden', 'Norway', 'Russia', 'Finland', 'Germany', 'USA', 'France']

SQ_FORMS = {'timber', 'squares', 'logs', 'masts', 'spars', 'balks'}
SAWN_FORMS = {'deals', 'battens', 'boards', 'deal ends', 'ends', 'scantlings',
              'lumber', 'planks', 'palings'}
HARDWOOD_SP = {'oak', 'elm', 'birch', 'ash', 'maple', 'walnut', 'hickory',
               'waney pine'}
MONTHS = {m: i + 1 for i, m in enumerate(
    ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct',
     'nov', 'dec'])}


def month_of(date_str):
    if not date_str:
        return None
    m = re.match(r'([A-Za-z]+)', date_str)
    return MONTHS.get(m.group(1)[:3].lower()) if m else None


def load_shipments():
    ships = []
    for f in sorted(NORM.glob('*.json')):
        y = year_of(f.stem)
        if y not in VALID_YEARS:
            continue
        grp = doc_group(f.stem)
        for s in json.load(open(f)).get('shipments', []):
            origin = s.get('origin_port_normalized') or ''
            sq = sawn = False
            for c in s.get('cargo', []):
                forms = set(c.get('commodity_forms', []))
                species = set(c.get('commodity_species', []))
                if forms & SAWN_FORMS:
                    sawn = True
                elif forms & SQ_FORMS:
                    sq = True
                elif species & HARDWOOD_SP:
                    sq = True
            ships.append({
                'year': y, 'group': grp, 'origin': origin,
                'country': COUNTRY.get(origin),
                'dest': s.get('destination_port_normalized') or '',
                'steam': bool(s.get('is_steamship')),
                'month': month_of(s.get('arrival_date')),
                'sq': sq, 'sawn': sawn,
            })
    return ships


# ---------------------------------------------------------------- official UK
def official_tables():
    """year -> country -> loads, plus Canada hewn/sawn split per year."""
    rows = list(csv.DictReader(open(UKGOV)))

    def is_timber(c):
        cl = c.lower()
        if any(k in cl for k in ['dye', 'pulp', 'paper', 'bark', 'pipe', 'gun',
                                 'stone', 'marble', 'pitch', 'furniture']):
            return False
        return any(k in cl for k in ['timber', 'deal', 'batten', 'stave',
                                     'lath', 'wainscot', 'fir', 'oak', 'hewn',
                                     'sawn'])

    def kind(c):
        cl = c.lower()
        if 'sawn' in cl or 'deal' in cl or 'batten' in cl:
            return 'sawn'
        if 'hewn' in cl or 'fir oak' in cl or 'not sawn' in cl:
            return 'hewn'
        return 'other'

    def src_country(s):
        s = s.strip()
        if s in ('British North America', 'Canada', 'New Brunswick',
                 'Nova Scotia', 'British America'):
            return 'Canada'
        for c in ['Russia', 'Sweden', 'Norway', 'France']:
            if s.startswith(c):
                return c
        if s.startswith('United States'):
            return 'USA'
        if s in ('Germany', 'Prussia'):
            return 'Germany'
        return None if s in ('World', 'Total') else 'Other'

    loads = defaultdict(Counter)
    can_split = defaultdict(Counter)
    for r in rows:
        y = int(r['YEAR'])
        if y < 1861 or not is_timber(r['COMMODITY_NAME']):
            continue
        if r['UNIT_NAME'] != 'Loads':
            continue
        c = src_country(r['SOURCE_LOCATION_NAME'])
        if c is None:
            continue
        amt = float(r['AMOUNT'] or 0)
        loads[y][c] += amt
        if c == 'Canada':
            can_split[y][kind(r['COMMODITY_NAME'])] += amt
    return loads, can_split


def interp(anchors, year):
    """Piecewise-linear interpolation; flat extrapolation."""
    ys = sorted(anchors)
    if year <= ys[0]:
        return anchors[ys[0]]
    if year >= ys[-1]:
        return anchors[ys[-1]]
    for a, b in zip(ys, ys[1:]):
        if a <= year <= b:
            w = (year - a) / (b - a)
            return anchors[a] * (1 - w) + anchors[b] * w


def pearson(a, b):
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den


def detrend(years, vals):
    n = len(years)
    mx, my = sum(years) / n, sum(vals) / n
    slope = (sum((x - mx) * (y - my) for x, y in zip(years, vals))
             / sum((x - mx) ** 2 for x in years))
    return [y - (my + slope * (x - mx)) for x, y in zip(years, vals)]


def main():
    ships = load_shipments()
    loads, can_split = official_tables()
    f3 = pd.ExcelFile(JHG).parse('Figure 3', index_col=0)

    # ================================================= A. square vs sawn
    print('== A. Canada square-vs-sawn: species-aware TTJ counts vs official ==')
    print('Official Canada loads split (50 cu ft loads, hewn vs sawn):')
    for y in sorted(can_split):
        cs = can_split[y]
        tot = cs['hewn'] + cs['sawn']
        print(f'  {y}: hewn {cs["hewn"]:>9,.0f}  sawn {cs["sawn"]:>9,.0f}'
              f'  sawn share {cs["sawn"] / tot:5.1%}')

    print('\nTTJ Canadian shipments (species-aware classification):')
    print('year   n(sq)  n(sawn)  TTJ sawn-share')
    ttj_sq_share = {}
    for y in VALID_YEARS:
        c = Counter()
        for s in ships:
            if s['country'] == 'Canada' and s['year'] == y:
                if s['sq']:
                    c['sq'] += 1
                if s['sawn']:
                    c['sawn'] += 1
        n = c['sq'] + c['sawn']
        if n:
            ttj_sq_share[y] = c['sq'] / n
            print(f'{y}  {c["sq"]:>6}  {c["sawn"]:>7}      {c["sawn"] / n:6.1%}')

    # Fig3 timing: convert to official-equivalent loads (sq/50, sawn/17.65)
    sawn_factor = {}
    for y in (1881, 1891):
        sawn_factor[y] = float(f3.loc['Sawn lumber', y]) / can_split[y]['sawn']
    kf = sum(sawn_factor.values()) / len(sawn_factor)
    print(f'\nFig3 sawn cu-ft per official sawn load: '
          + ', '.join(f'{y}: {v:.1f}' for y, v in sawn_factor.items())
          + f'  (using mean {kf:.1f})')
    fig3_sq_share = {}
    for y in VALID_YEARS:
        sq_l = float(f3.loc['Square timber', y]) / 50.0
        sw_l = float(f3.loc['Sawn lumber', y]) / kf
        fig3_sq_share[y] = sq_l / (sq_l + sw_l)
    yrs = [y for y in VALID_YEARS if y in ttj_sq_share]
    a = [ttj_sq_share[y] for y in yrs]
    b = [fig3_sq_share[y] for y in yrs]
    print('year   TTJ sq-share   Fig3 sq-share (loads-adj)')
    for y, x, z in zip(yrs, a, b):
        print(f'{y}      {x:6.1%}         {z:6.1%}')
    print(f'correlation: r={pearson(a, b):.3f};  '
          f'detrended r={pearson(detrend(yrs, a), detrend(yrs, b)):.3f}')

    # ================================================= C. calibrated shares
    # Official UK statistics count Finland under Russia, so merge for
    # calibration purposes.
    CAL = ['Canada', 'Sweden', 'Norway', 'Russia+Finland', 'Germany', 'USA',
           'France']

    def cal_country(c):
        return 'Russia+Finland' if c in ('Russia', 'Finland') else c

    print('\n== C. Calibrated annual volume shares (7 groups; Finland '
          'counted with Russia as in official statistics) ==')
    count_share = defaultdict(dict)
    for y in VALID_YEARS:
        c = Counter(cal_country(s['country']) for s in ships
                    if s['year'] == y and s['country'])
        n = sum(c.values())
        for k in CAL:
            count_share[y][k] = c[k] / n
    # official shares among the groups at anchors
    off_share = {}
    for y in (1881, 1891, 1901):
        by = Counter()
        for c in EIGHT:
            by[cal_country(c)] += loads[y][c]
        tot8 = sum(by.values())
        off_share[y] = {c: by[c] / tot8 for c in CAL}
    # weights w = official share / TTJ count share, at TTJ years 1881/1891/1899
    anchor_map = {1881: 1881, 1891: 1891, 1899: 1901}
    w_anchor = {c: {ty: off_share[oy][c] / count_share[ty][c]
                    for ty, oy in anchor_map.items()}
                for c in CAL}
    print('loads-per-shipment weight (relative), by anchor year:')
    print('country          ' + ''.join(f'{y:>8}' for y in anchor_map))
    for c in CAL:
        print(f'{c:<17}' + ''.join(f'{w_anchor[c][y]:8.2f}' for y in anchor_map))

    calibrated = {}
    for y in VALID_YEARS:
        raw = {c: count_share[y][c] * interp(w_anchor[c], y) for c in CAL}
        tot = sum(raw.values())
        calibrated[y] = {c: v / tot for c, v in raw.items()}
    print('\ncalibrated volume shares:')
    print('year  ' + ''.join(f'{c[:14]:>15}' for c in CAL))
    for y in VALID_YEARS:
        print(f'{y}  ' + ''.join(f'{calibrated[y][c]:15.1%}' for c in CAL))

    with open(BASE / 'exports' / 'country_shares_calibrated.csv', 'w',
              newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['year', 'country', 'count_share', 'calibrated_volume_share'])
        for y in VALID_YEARS:
            for c in CAL:
                w.writerow([y, c, round(count_share[y][c], 4),
                            round(calibrated[y][c], 4)])

    # validation: Fig3-derived Canada annual loads vs calibrated share
    print('\nValidation vs JHG Fig3 (Canada annual, official-equiv loads):')
    can_loads_fig3 = {y: float(f3.loc['Square timber', y]) / 50.0
                      + float(f3.loc['Sawn lumber', y]) / kf
                      for y in VALID_YEARS}
    tot8_anchor = {y: sum(loads[y][c] for c in EIGHT) for y in (1871, 1881, 1891, 1901)}
    fig3_share = {y: can_loads_fig3[y] / interp(tot8_anchor, y)
                  for y in VALID_YEARS}
    print('year   Fig3-implied  calibrated TTJ  raw count share')
    for y in VALID_YEARS:
        print(f'{y}      {fig3_share[y]:6.1%}        {calibrated[y]["Canada"]:6.1%}'
              f'          {count_share[y]["Canada"]:6.1%}')
    f = [fig3_share[y] for y in VALID_YEARS]
    cal = [calibrated[y]['Canada'] for y in VALID_YEARS]
    raw = [count_share[y]['Canada'] for y in VALID_YEARS]
    print(f'r(Fig3, calibrated) = {pearson(f, cal):.3f}   '
          f'r(Fig3, raw counts) = {pearson(f, raw):.3f}')
    print(f'detrended: r(Fig3, calibrated) = '
          f'{pearson(detrend(VALID_YEARS, f), detrend(VALID_YEARS, cal)):.3f}')
    mae_c = sum(abs(x - y) for x, y in zip(f, cal)) / len(f)
    mae_r = sum(abs(x - y) for x, y in zip(f, raw)) / len(f)
    print(f'MAE vs Fig3: calibrated {mae_c:.1%}, raw {mae_r:.1%}')

    # ================================================= D. port decomposition
    print('\n== D. Within-Canada port decomposition ==')
    PORTS = ['Quebec City', 'Montreal', 'St. John', 'Miramichi', 'Halifax']
    print('share of Canadian shipments by origin port:')
    print('year  ' + ''.join(f'{p[:9]:>10}' for p in PORTS) + f'{"other":>10}')
    for y in VALID_YEARS:
        subs = [s for s in ships if s['country'] == 'Canada' and s['year'] == y]
        if len(subs) < 50:
            continue
        c = Counter(s['origin'] for s in subs)
        n = len(subs)
        row = f'{y}  ' + ''.join(f'{c[p] / n:>10.1%}' for p in PORTS)
        other = 1 - sum(c[p] for p in PORTS) / n
        print(row + f'{other:>10.1%}')

    print('\nper-port profile, pooled early (1874-85) vs late (1887-99):')
    print(f'{"port":<12}{"period":<8}{"n":>6}{"sq-share":>10}{"steam":>8}'
          f'{"->Liverpool":>12}')
    for p in PORTS:
        for label, lo, hi in [('early', 1874, 1885), ('late', 1887, 1899)]:
            subs = [s for s in ships if s['origin'] == p and lo <= s['year'] <= hi]
            if len(subs) < 30:
                continue
            nsq = sum(1 for s in subs if s['sq'])
            nsw = sum(1 for s in subs if s['sawn'])
            sqsh = nsq / (nsq + nsw) if nsq + nsw else float('nan')
            steam = sum(1 for s in subs if s['steam']) / len(subs)
            liv = sum(1 for s in subs if s['dest'] == 'Liverpool') / len(subs)
            print(f'{p:<12}{label:<8}{len(subs):>6}{sqsh:>10.1%}{steam:>8.1%}'
                  f'{liv:>12.1%}')

    # ================================================= E. seasonality
    print('\n== E. Seasonality / coverage-bias check ==')
    dated = [s for s in ships if s['month'] and s['country']]
    print(f'records with month + mapped country: {len(dated):,} '
          f'({len(dated) / len(ships):.0%} of all)')
    pooled = defaultdict(Counter)
    for s in dated:
        pooled[s['month']][s['country']] += 1
    print('Canada share by arrival month (pooled all years):')
    print('  ' + '  '.join(f'{m}:{pooled[m]["Canada"] / sum(pooled[m].values()):.0%}'
                           for m in range(1, 13) if sum(pooled[m].values()) > 100))
    canada_by_month = {m: pooled[m]['Canada'] / sum(pooled[m].values())
                       for m in range(1, 13) if sum(pooled[m].values())}
    print('\nyear: actual Canada share vs expected-from-month-mix:')
    print('year   actual  expected  (gap = real change, not season coverage)')
    for y in VALID_YEARS:
        subs = [s for s in dated if s['year'] == y]
        if len(subs) < 200:
            continue
        act = sum(1 for s in subs if s['country'] == 'Canada') / len(subs)
        mm = Counter(s['month'] for s in subs)
        exp = sum(mm[m] * canada_by_month.get(m, 0) for m in mm) / len(subs)
        print(f'{y}    {act:6.1%}   {exp:6.1%}')

    # ================================================= F. trend test
    print('\n== F. Cluster-bootstrap trend test, Canada count share ==')
    by_year_group = defaultdict(lambda: defaultdict(Counter))
    for s in ships:
        if s['country']:
            by_year_group[s['year']][s['group']][s['country']] += 1

    def slope_of(shares_by_year):
        ys = sorted(shares_by_year)
        xs = [float(y) for y in ys]
        vs = [shares_by_year[y] for y in ys]
        mx, mv = sum(xs) / len(xs), sum(vs) / len(vs)
        return (sum((x - mx) * (v - mv) for x, v in zip(xs, vs))
                / sum((x - mx) ** 2 for x in xs))

    rng = random.Random(7)
    for label, years in [('1874-1899 (all valid)', VALID_YEARS),
                         ('1879-1899 (post-format-change)',
                          [y for y in VALID_YEARS if y >= 1879])]:
        slopes = []
        for _ in range(1000):
            shares = {}
            for y in years:
                grps = list(by_year_group[y])
                num = den = 0
                for g in (rng.choice(grps) for _ in grps):
                    num += by_year_group[y][g]['Canada']
                    den += sum(by_year_group[y][g].values())
                shares[y] = num / den if den else 0
            slopes.append(slope_of(shares) * 10)   # per decade
        slopes.sort()
        pt = {y: sum(by_year_group[y][g]['Canada'] for g in by_year_group[y])
              / sum(sum(by_year_group[y][g].values()) for g in by_year_group[y])
              for y in years}
        print(f'{label}: slope {slope_of(pt) * 10:+.2%}/decade  '
              f'95% CI [{slopes[25]:+.2%}, {slopes[975]:+.2%}]  '
              f'P(slope<0) = {sum(1 for s in slopes if s < 0) / len(slopes):.3f}')


if __name__ == '__main__':
    main()
