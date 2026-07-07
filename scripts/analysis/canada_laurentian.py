#!/usr/bin/env python3
"""Laurentian-only comparisons, per Clifford & Castonguay (JHG 2022).

The JHG Figs 2-4 cover the Laurentian Valley only (exports via the Ports of
Quebec and Montreal, from Canadian export records; New Brunswick and Nova
Scotia explicitly excluded). This script therefore:

  1. splits TTJ 'Canada' into Laurentian vs Maritimes origins;
  2. validates the TTJ Laurentian square-vs-sawn mix against JHG Fig 3
     (both now the same population);
  3. tests the paper's spruce claim: spruce ~40% of the Canadian deal trade
     in the last quarter of the century, rising as the trade moved to
     spruce forests (Saguenay, St-Maurice, Lower St. Lawrence).
"""
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from canada_country_analysis import COUNTRY, VALID_YEARS, year_of, NORM
from canada_ttj_phase2 import (SQ_FORMS, SAWN_FORMS, HARDWOOD_SP, pearson,
                               detrend)

JHG = '/mnt/c/Users/jic823/Dropbox/2026/JHG-data2022.xlsx'

LAURENTIAN = {
    'Quebec City', 'Montreal', 'Trois-Rivières', 'Three Rivers', 'Batiscan',
    'Sorel', 'Nicolet', 'Portneuf', 'Saguenay', 'Chicoutimi', 'Matane',
    'Metis', 'Rimouski', 'Bic', 'Cacouna', 'Gaspe', 'Paspebiac',
    'New Richmond', 'Bersimis', 'River du Loup', 'Montmagny', 'St. Anne',
}
PINE = {'pine', 'white pine', 'red pine', 'yellow pine', 'waney pine',
        'pitch pine'}


def load():
    ships = []
    for f in sorted(NORM.glob('*.json')):
        y = year_of(f.stem)
        if y not in VALID_YEARS:
            continue
        for s in json.load(open(f)).get('shipments', []):
            origin = s.get('origin_port_normalized') or ''
            if COUNTRY.get(origin) != 'Canada':
                continue
            sq = sawn = False
            species = set()
            deal_species = set()
            for c in s.get('cargo', []):
                forms = set(c.get('commodity_forms', []))
                sp = set(c.get('commodity_species', []))
                species |= sp
                if forms & SAWN_FORMS:
                    sawn = True
                    deal_species |= sp
                elif forms & SQ_FORMS:
                    sq = True
                elif sp & HARDWOOD_SP:
                    sq = True
            ships.append({
                'year': y, 'origin': origin,
                'region': 'Laurentian' if origin in LAURENTIAN else 'Maritimes',
                'sq': sq, 'sawn': sawn, 'deal_species': deal_species,
            })
    return ships


def main():
    ships = load()
    n_by = Counter(s['region'] for s in ships)
    print(f"Canadian shipments: {len(ships):,} "
          f"(Laurentian {n_by['Laurentian']:,}, Maritimes {n_by['Maritimes']:,})")
    other = Counter(s['origin'] for s in ships if s['region'] == 'Maritimes')
    print('largest "Maritimes" origins (check none are Laurentian):',
          [f'{o} {n}' for o, n in other.most_common(8)])

    # ------------------------------------------------ 1. region split by year
    print('\nLaurentian share of Canadian shipments by year:')
    for y in VALID_YEARS:
        subs = [s for s in ships if s['year'] == y]
        if not subs:
            continue
        lau = sum(1 for s in subs if s['region'] == 'Laurentian')
        print(f'  {y}: {lau / len(subs):5.1%}  (n={len(subs):,})')

    # ------------------------------------------------ 2. Fig3 validation
    f3 = pd.ExcelFile(JHG).parse('Figure 3', index_col=0)
    print('\nTTJ Laurentian-only square-vs-sawn vs JHG Fig 3 (same population):')
    print('year   n(sq)  n(sawn)  TTJ sq-share   Fig3 sq-share (cu ft)')
    ttj, jhg, yrs = [], [], []
    for y in VALID_YEARS:
        c = Counter()
        for s in ships:
            if s['year'] == y and s['region'] == 'Laurentian':
                if s['sq']:
                    c['sq'] += 1
                if s['sawn']:
                    c['sawn'] += 1
        n = c['sq'] + c['sawn']
        if n < 30:
            continue
        sq = float(f3.loc['Square timber', y])
        sw = float(f3.loc['Sawn lumber', y])
        ttj.append(c['sq'] / n)
        jhg.append(sq / (sq + sw))
        yrs.append(y)
        print(f'{y}  {c["sq"]:>6}  {c["sawn"]:>7}      {ttj[-1]:6.1%}'
              f'         {jhg[-1]:6.1%}')
    print(f'correlation r = {pearson(ttj, jhg):.3f};  '
          f'detrended r = {pearson(detrend(yrs, ttj), detrend(yrs, jhg)):.3f}')

    # ------------------------------------------------ 3. spruce vs pine deals
    print('\nSpruce vs pine among deal shipments with species stated:')
    print('year   region       n(sp-stated)  spruce%  pine%   (of Canadian '
          'deal shipments w/ species)')
    for region in ('Laurentian', 'Maritimes'):
        for y in VALID_YEARS:
            subs = [s for s in ships
                    if s['year'] == y and s['region'] == region and s['sawn']]
            stated = [s for s in subs
                      if s['deal_species'] & (PINE | {'spruce'})]
            if len(stated) < 20:
                continue
            spr = sum(1 for s in stated if 'spruce' in s['deal_species'])
            pin = sum(1 for s in stated if s['deal_species'] & PINE)
            print(f'{y}   {region:<12}{len(stated):>8}       '
                  f'{spr / len(stated):6.1%} {pin / len(stated):6.1%}')
        print()

    # pooled coverage note
    all_deals = [s for s in ships if s['sawn']]
    stated = [s for s in all_deals if s['deal_species'] & (PINE | {'spruce'})]
    print(f'species stated on {len(stated):,} of {len(all_deals):,} Canadian '
          f'deal shipments ({len(stated) / len(all_deals):.0%})')


if __name__ == '__main__':
    main()
