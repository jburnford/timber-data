#!/usr/bin/env python3
"""Trade dynamics: shift-share, merchants, seasonality, ships (TTJ 1874-99).

  A. Shift-share decomposition of Canada's count-share decline:
     within-market share loss vs destination-mix (market-growth) effects.
  B. Merchant (consignee) analysis: specialization by supply country,
     concentration, and the Quebec->Montreal transition at merchant level.
  C. Seasonal choreography: monthly arrival shares by country.
  D. Ship careers: liner vs tramp behaviour, steam route fidelity.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from canada_country_analysis import COUNTRY, VALID_YEARS, year_of, NORM
from canada_ttj_phase2 import month_of
from market_structure import COAST

EARLY = (1881, 1883)          # stable-coverage early anchor (Cardiff present)
LATE = (1897, 1899)


def load():
    ships = []
    for f in sorted(NORM.glob('*.json')):
        y = year_of(f.stem)
        if y not in VALID_YEARS:
            continue
        for s in json.load(open(f)).get('shipments', []):
            origin = s.get('origin_port_normalized') or ''
            dest = s.get('destination_port_normalized') or ''
            ships.append({
                'year': y, 'origin': origin, 'dest': dest,
                'country': COUNTRY.get(origin), 'coast': COAST.get(dest),
                'steam': bool(s.get('is_steamship')),
                'month': month_of(s.get('arrival_date')),
                'ship': (s.get('ship_name') or '').strip(),
                'merchant': (s.get('consignee_normalized')
                             if s.get('consignee_type') == 'named' else None),
            })
    return ships


def main():
    ships = load()

    # ================================================ A. shift-share
    print('===== A. SHIFT-SHARE: Canada 1881/83 -> 1897/99 =====')
    pools = {}
    for label, yrs in [('early', EARLY), ('late', LATE)]:
        subs = [s for s in ships if s['year'] in yrs and s['country']
                and s['coast']]
        pools[label] = subs
    coasts = sorted({s['coast'] for s in pools['early']})
    W, S = {}, {}
    for label in ('early', 'late'):
        n = len(pools[label])
        for m in coasts:
            seg = [s for s in pools[label] if s['coast'] == m]
            W[(label, m)] = len(seg) / n
            S[(label, m)] = (sum(1 for s in seg if s['country'] == 'Canada')
                             / len(seg)) if seg else 0.0
    can_e = sum(W[('early', m)] * S[('early', m)] for m in coasts)
    can_l = sum(W[('late', m)] * S[('late', m)] for m in coasts)
    within = sum(W[('early', m)] * (S[('late', m)] - S[('early', m)])
                 for m in coasts)
    between = sum((W[('late', m)] - W[('early', m)]) * S[('early', m)]
                  for m in coasts)
    inter = (can_l - can_e) - within - between
    print(f'Canada share: {can_e:.2%} (1881/83) -> {can_l:.2%} (1897/99), '
          f'change {can_l - can_e:+.2%}')
    print(f'  within-market share change:      {within:+.2%}')
    print(f'  destination-mix (market growth): {between:+.2%}')
    print(f'  interaction:                     {inter:+.2%}')
    print('\nper-coast detail (weight early->late; Canada share early->late):')
    for m in coasts:
        print(f'  {m:<20} w {W[("early", m)]:5.1%}->{W[("late", m)]:5.1%}   '
              f's {S[("early", m)]:5.1%}->{S[("late", m)]:5.1%}')

    # same decomposition for Sweden and Russia for contrast
    for c in ('Sweden', 'Russia', 'USA'):
        Sc = {}
        for label in ('early', 'late'):
            for m in coasts:
                seg = [s for s in pools[label] if s['coast'] == m]
                Sc[(label, m)] = (sum(1 for s in seg if s['country'] == c)
                                  / len(seg)) if seg else 0.0
        e = sum(W[('early', m)] * Sc[('early', m)] for m in coasts)
        l = sum(W[('late', m)] * Sc[('late', m)] for m in coasts)
        w_ = sum(W[('early', m)] * (Sc[('late', m)] - Sc[('early', m)])
                 for m in coasts)
        b_ = sum((W[('late', m)] - W[('early', m)]) * Sc[('early', m)]
                 for m in coasts)
        print(f'{c}: {e:.1%}->{l:.1%}  within {w_:+.1%}  mix {b_:+.1%}  '
              f'interaction {l - e - w_ - b_:+.1%}')

    # ================================================ B. merchants
    print('\n===== B. MERCHANTS (named consignees) =====')
    named = [s for s in ships if s['merchant']]
    print(f'shipments with named consignee: {len(named):,} '
          f'({len(named) / len(ships):.0%})')

    # specialization: merchants with >=30 shipments
    by_merchant = defaultdict(list)
    for s in named:
        by_merchant[s['merchant']].append(s)
    big = {m: v for m, v in by_merchant.items() if len(v) >= 30}
    spec = Counter()
    for m, v in big.items():
        cc = Counter(s['country'] for s in v if s['country'])
        if not cc:
            continue
        top_c, top_n = cc.most_common(1)[0]
        tot = sum(cc.values())
        spec['single-country (>80%)' if top_n / tot >= 0.8 else
             'diversified'] += 1
    print(f'merchants with >=30 shipments: {len(big):,}; '
          f'{spec["single-country (>80%)"]} single-country specialists, '
          f'{spec["diversified"]} diversified')

    print('\ntop consignees of CANADIAN cargoes (n, % Canada, main dests):')
    can_m = Counter(s['merchant'] for s in named
                    if s['country'] == 'Canada')
    for m, n in can_m.most_common(10):
        v = by_merchant[m]
        share_can = n / len(v)
        dd = Counter(s['dest'] for s in v if s['dest'])
        top_d = ', '.join(f'{k}' for k, _ in dd.most_common(2))
        print(f'  {m:<28} {n:>4}  {share_can:>5.0%} Canada   {top_d}')

    # Quebec->Montreal at merchant level
    print('\nQuebec City consignees (early) - where do they receive from late?')
    qc_early = Counter(s['merchant'] for s in named
                       if s['origin'] == 'Quebec City' and s['year'] <= 1885)
    fates = Counter()
    detail = []
    for m, n in qc_early.most_common(25):
        late_v = [s for s in by_merchant[m] if s['year'] >= 1887]
        if not late_v:
            fates['disappeared'] += 1
            detail.append((m, n, 'DISAPPEARED', ''))
            continue
        oc = Counter(s['origin'] for s in late_v)
        qc_l = oc.get('Quebec City', 0)
        mtl = oc.get('Montreal', 0)
        if qc_l >= mtl and qc_l > 0:
            fates['stayed Quebec'] += 1
            tag = 'stayed QC'
        elif mtl > 0:
            fates['moved to Montreal'] += 1
            tag = 'to Montreal'
        else:
            fates['left Canada trade'] += 1
            tag = 'other origins'
        top_o = ', '.join(f'{k} {v}' for k, v in oc.most_common(3))
        detail.append((m, n, tag, top_o))
    print(f'top-25 Quebec consignees: {dict(fates)}')
    for m, n, tag, top_o in detail[:15]:
        print(f'  {m:<28} early-QC n={n:<4} {tag:<14} late: {top_o}')

    # concentration by supply country
    print('\nconsignee concentration (HHI) among named shipments, by country:')
    for c in ('Canada', 'Sweden', 'Russia', 'Norway', 'USA', 'France'):
        for label, yrs in [('early', EARLY), ('late', LATE)]:
            subs = [s for s in named if s['country'] == c
                    and s['year'] in yrs]
            if len(subs) < 100:
                continue
            cc = Counter(s['merchant'] for s in subs)
            n = len(subs)
            hhi = sum((v / n) ** 2 for v in cc.values())
            print(f'  {c:<8}{label}: n={n:>5}  merchants={len(cc):>4}  '
                  f'HHI={hhi:.4f}  top: {cc.most_common(1)[0][0]} '
                  f'({cc.most_common(1)[0][1] / n:.0%})')

    # ================================================ C. seasonality
    print('\n===== C. SEASONAL CHOREOGRAPHY =====')
    dated = [s for s in ships if s['month'] and s['country']]
    print('country shares within each arrival month (pooled; '
          'rows = months, cols sum to ~100% of mapped):')
    CS = ['Canada', 'Sweden', 'Norway', 'Russia', 'Finland', 'Germany',
          'USA', 'France']
    print('month     n   ' + ''.join(f'{c[:6]:>8}' for c in CS))
    for m in range(1, 13):
        subs = [s for s in dated if s['month'] == m]
        n = len(subs)
        if n < 200:
            continue
        cc = Counter(s['country'] for s in subs)
        print(f'{m:>4}  {n:>6}  '
              + ''.join(f'{cc[c] / n:>8.1%}' for c in CS))

    # ================================================ D. ships
    print('\n===== D. SHIP CAREERS =====')
    voyages = defaultdict(list)
    for s in ships:
        if s['ship'] and len(s['ship']) > 2:
            voyages[(s['ship'], s['steam'])].append(s)
    multi = {k: v for k, v in voyages.items() if len(v) >= 10}
    print(f'ship-name identities with >=10 voyages: {len(multi):,}')

    def fidelity(v):
        rr = Counter((s['origin'], s['dest']) for s in v
                     if s['origin'] and s['dest'])
        return (rr.most_common(1)[0][1] / sum(rr.values())) if rr else 0

    for steam in (True, False):
        grp = [v for (nm, st), v in multi.items() if st == steam]
        if not grp:
            continue
        fids = sorted(fidelity(v) for v in grp)
        med = fids[len(fids) // 2]
        vpy = []
        for v in grp:
            per_year = Counter(s['year'] for s in v)
            vpy.extend(per_year.values())
        vpy.sort()
        print(f'  {"steam" if steam else "sail"}: n={len(grp):>4} ships  '
              f'median route-fidelity {med:.0%}  '
              f'median voyages/observed-year {vpy[len(vpy) // 2]}')

    print('\nhardest-working steamships (voyages, modal route):')
    steam_ships = sorted(((len(v), nm, v) for (nm, st), v in multi.items()
                          if st), reverse=True)[:8]
    for n, nm, v in steam_ships:
        rr = Counter((s['origin'], s['dest']) for s in v
                     if s['origin'] and s['dest'])
        (o, d), k = rr.most_common(1)[0]
        yrs = sorted({s['year'] for s in v})
        print(f'  {nm:<18} {n:>3} voyages {yrs[0]}-{yrs[-1]}  '
              f'modal {o}->{d} ({k / n:.0%})')


if __name__ == '__main__':
    main()
