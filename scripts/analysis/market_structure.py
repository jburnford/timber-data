#!/usr/bin/env python3
"""Market-structure analyses of the TTJ shipment data, 1874-1899.

  A. Value-added transition: raw / sawn / components / machined+finished
     wood goods — who shipped finished goods, and when did they grow?
  B. The American trade by sub-region: Northeast vs South Atlantic vs Gulf,
     with commodity profiles (incl. the Portland, Maine winter-outlet caveat).
  C. European competition: Sweden / Russia / Finland / Norway / Germany —
     commodity profiles, pairwise convergence, UK coastal market segmentation,
     and head-to-head segment shares (London deals, Bristol Channel pitwood,
     east-coast boards).

Counts of shipments only; within-year shares comparable across years.
"""
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from canada_country_analysis import COUNTRY, VALID_YEARS, year_of, NORM

BASE = Path('/home/jic823/timber_data')

# ---------------------------------------------------------------- categories
RAW = {'timber', 'logs', 'balks', 'squares', 'spars', 'poles', 'rickers',
       'firewood', 'lathwood', 'pitwood', 'pit props', 'mining timber', 'wood'}
SAWN = {'deals', 'battens', 'boards', 'deal ends', 'batten ends', 'ends',
        'planks', 'scantlings', 'lumber', 'laths', 'splits', 'posts', 'rails',
        'palings', 'sleepers', 'crowntrees', 'treenails'}
COMPONENTS = {'staves', 'headings', 'shooks', 'hoops', 'spokes', 'blocks',
              'splints', 'spoolwood', 'boxboards'}
FINISHED = {'flooring', 'matchboards', 'doors', 'mouldings', 'joinery',
            'woodware', 'oars', 'boathooks', 'bobbins', 'trellis', 'handles',
            'gun stocks'}
PULP = {'wood pulp'}

US_NE = {'New York', 'Boston', 'Portland', 'Philadelphia', 'Baltimore',
         'Bangor', 'Calais', 'Eastport', 'Machias', 'Perth Amboy'}
US_SOUTH = {'Norfolk', 'Newport News', 'Wilmington', 'Charleston', 'Savannah',
            'Darien', 'Brunswick', 'Doboy', 'Sapelo', 'Fernandina', 'Satilla',
            'Bucksville', 'Georgetown', 'Beaufort', 'Port Royal', 'Tybee',
            'Jacksonville', 'St. Marys'}
US_GULF = {'Pensacola', 'Mobile', 'New Orleans', 'Pascagoula', 'Apalachicola',
           'Galveston', 'Ship', 'Punta Gorda', 'Key West'}

COAST = {}
for ports, region in [
    (['London', 'Rochester', 'Rochford'], 'Thames'),
    (['Hull', 'Grimsby', 'Goole', 'Tyne Ports', 'Newcastle upon Tyne',
      'Sunderland', 'Hartlepool (West)', 'Hartlepool', 'Middlesbrough',
      'Yarmouth', "King's Lynn", 'WISBECH', 'LOWESTOFT', 'Ipswich', 'Boston',
      'Blyth', 'Seaham', 'Stockton', 'Whitby', 'Scarborough', 'Colchester',
      'Harwich'], 'English East Coast'),
    (['Leith', 'Grangemouth', 'Borrowstounness', 'Alloa', 'Granton', 'Dundee',
      'Aberdeen', 'Kirkcaldy', 'Montrose', 'Peterhead', 'Inverness', 'Wick',
      'Fraserburgh', 'Arbroath', 'Banff', 'Burntisland', 'Methil', 'Kincardine',
      'Charlestown', 'Perth', 'Stonehaven', 'Findhorn', 'Lossiemouth',
      'Buckie'], 'Scottish East Coast'),
    (['Liverpool', 'MANCHESTER', 'Garston', 'Fleetwood', 'Preston',
      'Barrow-in-Furness', 'Whitehaven', 'Maryport', 'Workington',
      'Runcorn'], 'Mersey/NW England'),
    (['Glasgow', 'Greenock', 'Ardrossan', 'Ayr', 'Troon', 'Irvine',
      'Port Glasgow', 'Campbeltown', 'Oban'], 'Clyde'),
    (['Cardiff', 'Newport', 'Swansea', 'Bristol', 'Gloucester', 'Sharpness',
      'Port Talbot', 'Llanelly', 'Neath', 'Burry Port', 'Milford',
      'Cardigan', 'Carmarthen', 'Bridgwater', 'Penarth', 'Barry'],
     'Bristol Channel'),
    (['Southampton', 'Portsmouth', 'Plymouth', 'Poole', 'NEWHAVEN',
      'Shoreham', 'Dover', 'Folkestone', 'Rye', 'Littlehampton', 'Exeter',
      'Falmouth', 'Fowey', 'Penzance', 'Teignmouth', 'Dartmouth', 'Weymouth',
      'Chichester', 'Cowes', 'Guernsey', 'Jersey'], 'South Coast'),
    (['Belfast', 'Dublin', 'Cork', 'Waterford', 'Limerick', 'Londonderry',
      'Newry', 'Drogheda', 'Dundalk', 'Sligo', 'Galway', 'Wexford',
      'Coleraine'], 'Ireland'),
]:
    for p in ports:
        COAST[p] = region


def load():
    ships = []
    for f in sorted(NORM.glob('*.json')):
        y = year_of(f.stem)
        if y not in VALID_YEARS:
            continue
        for s in json.load(open(f)).get('shipments', []):
            origin = s.get('origin_port_normalized') or ''
            forms = {fm for c in s.get('cargo', [])
                     for fm in c.get('commodity_forms', [])}
            ships.append({
                'year': y, 'origin': origin,
                'country': COUNTRY.get(origin),
                'dest': s.get('destination_port_normalized') or '',
                'coast': COAST.get(s.get('destination_port_normalized') or ''),
                'steam': bool(s.get('is_steamship')),
                'forms': forms,
                'cats': {cat for cat, fs in
                         [('raw', RAW), ('sawn', SAWN), ('comp', COMPONENTS),
                          ('fin', FINISHED), ('pulp', PULP)] if forms & fs},
            })
    return ships


def cosine(p, q):
    keys = set(p) | set(q)
    num = sum(p.get(k, 0) * q.get(k, 0) for k in keys)
    da = math.sqrt(sum(v * v for v in p.values()))
    db = math.sqrt(sum(v * v for v in q.values()))
    return num / (da * db) if da and db else float('nan')


def main():
    ships = load()
    print(f'shipments (valid years): {len(ships):,}')

    # ============================================ A. value-added transition
    print('\n===== A. VALUE-ADDED TRANSITION =====')
    print('\nshare of all shipments carrying each category:')
    print('year      raw    sawn    comp     fin    pulp')
    for y in VALID_YEARS:
        subs = [s for s in ships if s['year'] == y]
        n = len(subs)
        row = f'{y}  '
        for cat in ('raw', 'sawn', 'comp', 'fin', 'pulp'):
            row += f'{sum(1 for s in subs if cat in s["cats"]) / n:>8.1%}'
        print(row)

    print('\ntop origin countries of FINISHED-goods shipments '
          '(early 1874-85 vs late 1887-99):')
    for label, lo, hi in [('early', 1874, 1885), ('late', 1887, 1899)]:
        fin = [s for s in ships if 'fin' in s['cats'] and lo <= s['year'] <= hi]
        c = Counter(s['country'] or 'other/unmapped' for s in fin)
        n = len(fin)
        top = ', '.join(f'{k} {v / n:.0%}' for k, v in c.most_common(6))
        print(f'  {label}: n={n:,}  {top}')

    print('\nfinished forms detail (late period, count of shipments, '
          'top countries):')
    late = [s for s in ships if 1887 <= s['year'] <= 1899]
    for form in sorted(FINISHED):
        subs = [s for s in late if form in s['forms']]
        if len(subs) < 40:
            continue
        c = Counter(s['country'] or 'other' for s in subs)
        top = ', '.join(f'{k} {v}' for k, v in c.most_common(3))
        print(f'  {form:<12} n={len(subs):>5}  {top}')

    print('\nfinished-goods share within each country\'s shipments:')
    print('year    Sweden  Norway  Russia     USA  Canada Germany')
    for y in VALID_YEARS:
        row = f'{y}'
        for c in ['Sweden', 'Norway', 'Russia', 'USA', 'Canada', 'Germany']:
            subs = [s for s in ships if s['year'] == y and s['country'] == c]
            if len(subs) < 50:
                row += '      --'
                continue
            row += f'{sum(1 for s in subs if "fin" in s["cats"]) / len(subs):>8.1%}'
        print(row)

    # ============================================ B. the American trade
    print('\n===== B. THE AMERICAN TRADE BY SUB-REGION =====')

    def us_region(o):
        if o in US_NE:
            return 'Northeast'
        if o in US_SOUTH:
            return 'South Atlantic'
        if o in US_GULF:
            return 'Gulf'
        return 'Pacific/other'

    print('\nUS shipments by sub-region (share of ALL mapped shipments):')
    print('year   n(US)   Northeast  SouthAtl    Gulf   USshare')
    for y in VALID_YEARS:
        allm = [s for s in ships if s['year'] == y and s['country']]
        us = [s for s in allm if s['country'] == 'USA']
        if not us:
            continue
        c = Counter(us_region(s['origin']) for s in us)
        n = len(us)
        print(f'{y}  {n:>6}   {c["Northeast"] / n:>8.1%} {c["South Atlantic"] / n:>9.1%}'
              f' {c["Gulf"] / n:>7.1%}  {n / len(allm):>7.1%}')

    print('\ncommodity profile by US sub-region (pooled, top forms):')
    for reg in ('Northeast', 'South Atlantic', 'Gulf'):
        subs = [s for s in ships if s['country'] == 'USA'
                and us_region(s['origin']) == reg]
        c = Counter(f for s in subs for f in s['forms'])
        n = len(subs)
        top = ', '.join(f'{k} {v / n:.0%}' for k, v in c.most_common(7))
        print(f'  {reg:<15} n={n:,}  {top}')

    print('\nNortheast port detail (share of NE shipments, early vs late):')
    for label, lo, hi in [('early', 1874, 1885), ('late', 1887, 1899)]:
        subs = [s for s in ships if s['country'] == 'USA'
                and us_region(s['origin']) == 'Northeast'
                and lo <= s['year'] <= hi]
        c = Counter(s['origin'] for s in subs)
        n = len(subs)
        top = ', '.join(f'{k} {v / n:.0%}' for k, v in c.most_common(6))
        print(f'  {label}: n={n:,}  {top}')

    # Portland winter-outlet check: monthly pattern of Portland vs Boston
    # is in phase2's month data; here check Portland's commodity profile
    port = [s for s in ships if s['origin'] == 'Portland']
    c = Counter(f for s in port for f in s['forms'])
    print(f'\nPortland (Maine) profile n={len(port)}: '
          + ', '.join(f'{k} {v}' for k, v in c.most_common(6))
          + '  <- Grand Trunk winter outlet for Canadian deals')

    # ============================================ C. European competition
    print('\n===== C. EUROPEAN COMPETITION =====')
    EURO = ['Sweden', 'Russia', 'Finland', 'Norway', 'Germany']

    print('\ncommodity profile (share of country shipments, early vs late):')
    for c in EURO:
        for label, lo, hi in [('early', 1874, 1885), ('late', 1887, 1899)]:
            subs = [s for s in ships if s['country'] == c
                    and lo <= s['year'] <= hi]
            cnt = Counter(f for s in subs for f in s['forms'])
            n = len(subs)
            top = ', '.join(f'{k} {v / n:.0%}' for k, v in cnt.most_common(6))
            print(f'  {c:<8} {label}: n={n:,}  {top}')
        print()

    print('pairwise commodity-profile cosine similarity (early -> late):')
    prof = {}
    for c in EURO + ['Canada']:
        for label, lo, hi in [('early', 1874, 1885), ('late', 1887, 1899)]:
            subs = [s for s in ships if s['country'] == c
                    and lo <= s['year'] <= hi]
            cnt = Counter(f for s in subs for f in s['forms'])
            n = len(subs)
            prof[(c, label)] = {k: v / n for k, v in cnt.items()}
    pairs = [('Sweden', 'Russia'), ('Sweden', 'Norway'), ('Sweden', 'Finland'),
             ('Russia', 'Finland'), ('Sweden', 'Canada'), ('Russia', 'Canada'),
             ('Germany', 'Sweden'), ('Germany', 'Russia'),
             ('Norway', 'Germany')]
    for a, b in pairs:
        e = cosine(prof[(a, 'early')], prof[(b, 'early')])
        l = cosine(prof[(a, 'late')], prof[(b, 'late')])
        arrow = 'converging' if l > e + 0.03 else (
            'diverging' if l < e - 0.03 else 'stable')
        print(f'  {a:<8}vs {b:<8}: {e:.2f} -> {l:.2f}  {arrow}')

    print('\nUK coastal destination mix by country (late 1887-99; '
          'rows sum to 100% of coast-mapped):')
    coasts = ['Thames', 'English East Coast', 'Scottish East Coast',
              'Mersey/NW England', 'Clyde', 'Bristol Channel', 'South Coast',
              'Ireland']
    print(f'{"":<8}' + ''.join(f'{c[:9]:>10}' for c in coasts))
    for c in EURO + ['Canada', 'USA', 'France']:
        subs = [s for s in ships if s['country'] == c
                and 1887 <= s['year'] <= 1899 and s['coast']]
        n = len(subs)
        if n < 100:
            continue
        cc = Counter(s['coast'] for s in subs)
        print(f'{c:<8}' + ''.join(f'{cc[k] / n:>10.1%}' for k in coasts))

    print('\nsegment head-to-heads (share of segment shipments by year):')
    segs = [
        ('London deals', lambda s: s['dest'] == 'London' and 'deals' in s['forms']),
        ('Bristol Channel pitwood', lambda s: s['coast'] == 'Bristol Channel'
         and (s['forms'] & {'pitwood', 'pit props', 'mining timber'})),
        ('East-coast boards+battens', lambda s: s['coast'] in
         ('English East Coast', 'Scottish East Coast')
         and (s['forms'] & {'boards', 'battens'})),
    ]
    for name, pred in segs:
        print(f'\n  {name}:')
        print('  year   n     Sweden  Russia Finland  Norway Germany  Canada'
              '     USA  France')
        for y in VALID_YEARS:
            subs = [s for s in ships if s['year'] == y and pred(s)]
            n = len(subs)
            if n < 60:
                continue
            cc = Counter(s['country'] for s in subs)
            row = f'  {y} {n:>5}  '
            for c in ['Sweden', 'Russia', 'Finland', 'Norway', 'Germany',
                      'Canada', 'USA', 'France']:
                row += f'{cc[c] / n:>8.1%}'
            print(row)


if __name__ == '__main__':
    main()
