#!/usr/bin/env python3
"""Triangulate the NEW annual official UK import series (uk_trade_db Tier 2,
grade-A/B verified country cells, 1873-1898) against:
  - TTJ shipment-count shares (count + calibrated volume, 1874-99 odd years)
  - JHG-2022 Laurentian export volumes (square/sawn cu ft, annual)
  - the decennial gold anchors (1871/1881/1891)

The prior triangulation had only 5 decennial anchor years of official data;
this fills in the annual trajectory. 1 load = 50 cu ft.

Writes exports/canada_annual_triangulation.csv and
reports/triangulation_annual.md.
"""
import csv
from collections import defaultdict
from pathlib import Path

import pandas as pd

TD = Path('/home/jic823/timber_data')
WOOD = Path('/home/jic823/uk_trade_db/exports/wood_country_year.csv')
JHG = '/mnt/c/Users/jic823/Dropbox/2026/JHG-data2022.xlsx'
CUFT_PER_LOAD = 50.0
HEWN = {'wood-hewn-fir', 'wood-hewn-oak', 'wood-hewn-teak',
        'wood-hewn-unenumerated'}
SAWN = {'wood-sawn-fir', 'wood-sawn-unenumerated'}
MAJORS = ['canada', 'sweden', 'norway', 'russia']


def load_official():
    """(year, country) -> {'hewn': loads, 'sawn': loads, 'c_cells': n}
    Grade A/B cells only; grade-C noted so share-years can be screened."""
    out = defaultdict(lambda: {'hewn': 0.0, 'sawn': 0.0, 'c_cells': 0})
    for r in csv.DictReader(open(WOOD)):
        if r['unit'] != 'loads':
            continue
        cat = ('hewn' if r['commodity'] in HEWN
               else 'sawn' if r['commodity'] in SAWN else None)
        if not cat:
            continue
        y, c = int(r['year']), r['country']
        if r['grade'] == 'C':
            out[(y, c)]['c_cells'] += 1
            continue
        out[(y, c)][cat] += float(r['quantity'])
    return out


def main():
    off = load_official()
    years = sorted({y for y, c in off})

    # UK-total loads per year (A/B cells, all origins)
    tot = defaultdict(float)
    for (y, c), d in off.items():
        tot[y] += d['hewn'] + d['sawn']

    # screening: a share-year is clean only when every major origin has
    # BOTH hewn and sawn A/B coverage and lost nothing to grade C — a
    # missing sawn side (pre-1877 labels, 1897+ consolidation) or a
    # C-excluded cell makes the share denominator wrong, not just noisy
    def clean_major(y, m):
        d = off.get((y, m))
        return (d is not None and d['c_cells'] == 0
                and d['hewn'] > 0 and d['sawn'] > 0)

    dirty = {y for y in years if not all(clean_major(y, m) for m in MAJORS)}

    # ---- TTJ shares
    ttj = {}
    for r in csv.DictReader(open(TD / 'exports' /
                                 'country_shares_calibrated.csv')):
        ttj[(int(r['year']), r['country'].lower())] = (
            float(r['count_share']), float(r['calibrated_volume_share']))

    # ---- JHG Laurentian series (cu ft -> loads-equivalent)
    fig3 = pd.read_excel(JHG, sheet_name='Figure 3', index_col=0)
    jhg_sq = {int(y): v / CUFT_PER_LOAD for y, v in fig3.iloc[0].items()
              if isinstance(y, (int, float)) and pd.notna(v)}
    jhg_sawn = {int(y): v / CUFT_PER_LOAD for y, v in fig3.iloc[1].items()
                if isinstance(y, (int, float)) and pd.notna(v)}

    # ---- combined table
    out_rows = []
    for y in years:
        can = off.get((y, 'canada'), {'hewn': 0, 'sawn': 0, 'c_cells': 0})
        can_tot = can['hewn'] + can['sawn']
        row = {
            'year': y,
            'uk_total_loads': round(tot[y]),
            'canada_hewn_loads': round(can['hewn']),
            'canada_sawn_loads': round(can['sawn']),
            'canada_share': round(can_tot / tot[y], 4) if tot[y] else '',
            'share_year_clean': int(y not in dirty),
            'canada_sawn_share_own': round(can['sawn'] / can_tot, 4)
            if can_tot else '',
        }
        for m in ('sweden', 'norway', 'russia', 'france'):
            d = off.get((y, m), {'hewn': 0, 'sawn': 0})
            row[f'{m}_share'] = round(
                (d['hewn'] + d['sawn']) / tot[y], 4) if tot[y] else ''
        t = ttj.get((y, 'canada'))
        row['ttj_canada_count_share'] = t[0] if t else ''
        row['ttj_canada_calibrated_share'] = t[1] if t else ''
        row['jhg_square_loads'] = round(jhg_sq.get(y, float('nan'))) \
            if y in jhg_sq else ''
        row['jhg_sawn_loads'] = round(jhg_sawn.get(y, float('nan'))) \
            if y in jhg_sawn else ''
        # annual reconciliation ratios (JHG = Laurentian only); only when
        # Canada's official cells are complete (no C exclusions)
        can_clean = can['c_cells'] == 0
        row['jhg_sq_over_official_hewn'] = round(
            jhg_sq[y] / can['hewn'], 3) \
            if y in jhg_sq and can['hewn'] and can_clean else ''
        row['jhg_sawn_over_official_sawn'] = round(
            jhg_sawn[y] / can['sawn'], 3) \
            if y in jhg_sawn and can['sawn'] and can_clean else ''
        out_rows.append(row)

    outcsv = TD / 'exports' / 'canada_annual_triangulation.csv'
    with open(outcsv, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)
    print(f'-> {outcsv}')

    # ---- agreement stats: TTJ calibrated vs official annual share
    pairs = [(r['canada_share'], r['ttj_canada_calibrated_share'], r['year'])
             for r in out_rows
             if r['canada_share'] != '' and r['ttj_canada_calibrated_share']
             != '' and r['share_year_clean']]
    if pairs:
        mae = sum(abs(a - b) for a, b, _ in pairs) / len(pairs)
        print(f'\nTTJ calibrated vs official annual share '
              f'({len(pairs)} clean overlap years): MAE {mae:.3f}')
        for a, b, y in pairs:
            print(f'  {y}: official {a:.1%}  ttj-calibrated {b:.1%}  '
                  f'diff {b - a:+.1%}')

    print('\nJHG sawn / official BNA sawn (annual Laurentian share of BNA):')
    for r in out_rows:
        if r['jhg_sawn_over_official_sawn'] != '':
            print(f"  {r['year']}: {r['jhg_sawn_over_official_sawn']:.2f}"
                  f"   (square ratio "
                  f"{r['jhg_sq_over_official_hewn'] or float('nan')})")


if __name__ == '__main__':
    main()
