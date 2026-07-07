#!/usr/bin/env python3
"""Prototype statistics for Canada's position in the UK timber import trade.

Sources:
  1. TTJ microdata (normalized/*.json): shipment counts by origin country,
     commodity form, destination, steam flag. Valid years only (odd-year
     photography design + 1874/1875).
  2. UK Gov decennial imports (Full British Imports Database): quantity (Loads)
     and value shares by source country, 1861-1901 — the calibration anchor.

Outputs: printed report + exports/country_shares_year.csv

Statistical design notes:
  - Unit = shipment count (OCR quantities untrustworthy). Shares within a year
    are comparable across years; raw counts are NOT (coverage varies).
  - Bootstrap CIs cluster-resample document groups (journal issues), not
    individual shipments, because shipments within an issue are correlated.
"""
import csv
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path('/home/jic823/timber_data')
NORM = BASE / 'normalized'
UKGOV = Path('/mnt/c/Users/jic823/Dropbox/2026') / 'Full British Imports Database.xlsx - Sheet1.csv'

VALID_YEARS = [1874, 1875, 1879, 1881, 1883, 1885, 1887, 1889, 1891, 1893, 1895, 1897, 1899]

# ---------------------------------------------------------------- country map
SWEDEN = """Gothenburg Göteborg Sundswall Gefle Soderhamn Hernosand Stockholm
Halmstad Skutskar Hudikswall Hudiksvall Oscarshamn Skelleftea Lulea Uddevalla
Falkenberg Ljusne Pitea Nederkalix Svartvik Kalmar Sandarne Norrkoping Skonvik
Ornskjoldsvik Kramfors Karlskrona Timrå Iggesund Holmsund Varberg Bergkvara
Hallsta Husum Domsjo Umea Mönsterås Mem Harnas Nordmaling Haparanda Stugsund
Stocka Karlshamn Bollsta Gamleby Munksund Oxelosund Finnklippan Nyland Torefors
Djupvik Kalix Slite Pataholm Malmo Asbacka Byske Visby Timmernabben Skeppsvik
Sikea Norrsundet Salsaker Figeholm Nyhamn Langror Sandvik Ronneby Ahus Sundsvall
Vivstavarv Vifstavarf Söråker Utansjo Ramvik Bureå Ortviken Kubikenborg Essvik
Tunadal Alnö Johannedal Nacka Halsingborg Helsingborg Landskrona Solvesborg
Sölvesborg Vastervik Obbola Rundvik Hörnefors Lögdeå Rönnskär Töre Båtskärsnäs
Seskarö Karlsborg Storvik Bergvik Vallvik Marma Söderala Askersund Köping
Västerås Gävle Härnösand""".split()
SWEDEN += ['Västervik (Westerwik)', 'Göteborg']

NORWAY = """Christiania Kristiania Drammen Porsgrund Arendal Laurvig Halden
Christiansand Kragero Skien Brevig Trondheim Risoer Fredrikstad Fredrikshald
Tvedestrand Holmestrand Hommelvik Moss Mandal Sandefjord Grimstad Tonsberg
Namsos Langesund Lillesand Drobak Sarpsborg Vefsn Bergen Kristiansund
Fredriksvern Sannesund Stavanger Larvik Horten Skudeneshavn Farsund Flekkefjord
Egersund Haugesund Aalesund Molde Namsen Mosjoen Levanger Steinkjer Soon
Svelvik Holmsbu Krageroe Osterrisor Lyngor""".split()
NORWAY += ['Trondheim (Drontheim)']

RUSSIA = """Riga Cronstadt Archangel Ventspils Narva Onega Soroka Kem Pernau
Reval Odessa Libau Windau Petersburg Mezen Kovda Uma Kereth Poti Batoum
Taganrog Nicolaieff Kherson""".split()
RUSSIA += ['St. Petersburg', 'Liepāja']

FINLAND = """Kotka Wyborg Bjorneborg Uleaborg Helsingfors Abo Kemi Tornea Borga
Vaasa Jakobstad Hango Christinestad Simo Fredrikshamn Lovisa Rauma Lappvik Attu
Trangsund Nystad Kaskö Gamlakarleby Nykarleby Brahestad Ekenäs Ijo Uleåborg
Kimito Dalsbruk Pernoviken Fagervik Raumo Mäntyluoto Kotka Rafso""".split()

GERMANY = """Danzig Stettin Konigsberg Hamburg Bremen Pillau Colberg Klaipeda
Memel Darłowo Rugenwalde Swinemunde Wolgast Barth Stralsund Rostock Wismar
Lubeck Kiel Flensburg Elbing Tilsit""".split()

CANADA = """Montreal Miramichi Halifax Richibouctou Shediac Dalhousie Matane
Bathurst Parrsboro Pugwash Buctouche Charlottetown Musquash Pictou Campbellton
Metis Chicoutimi Bersimis Weymouth Sackville Harvey Batiscan Rimouski Gaspe
Paspebiac Escuminac Cocagne Shippegan Caraquet Tracadie Tatamagouche Wallace
Amherst Moncton Dorchester Hillsborough Hopewell Salisbury Cape Tormentine
Bridgewater Lunenburg Shelburne Annapolis Digby Windsor Maitland Truro
Sherbrooke Guysborough Antigonish Baddeck Louisburg Sorel Nicolet Portneuf
Bic Cacouna Restigouche Nouvelle Carleton Bonaventure Grindstone""".split()
CANADA += ['Quebec City', 'St. John', 'Baie Verte', 'Trois-Rivières', 'Saguenay',
           'Sheet Harbour', 'New Richmond', 'Newcastle, N.B.', 'West Bay',
           'St. George', 'Three Rivers', 'St. John, N.B.', 'Port Hawkesbury',
           'River du Loup', 'St. Anne', 'St. Margarets Bay', 'Ship Harbour',
           'Port Medway', 'Port Greville', 'Two Rivers', 'Apple River',
           'Grand River', 'Little Glace Bay', 'Cow Bay']

USA = """Pensacola Mobile Norfolk Darien Pascagoula Apalachicola Savannah Doboy
Sapelo Charleston Brunswick Fernandina Galveston Boston Baltimore Philadelphia
Portland Wilmington Jacksonville Satilla Bucksville Georgetown Beaufort
Tybee Ship Bangor Machias Calais Eastport""".split()
USA += ['New York', 'New Orleans', 'Newport News', 'San Francisco',
        'Port Royal', 'St. Marys', 'Perth Amboy', 'Punta Gorda', 'Key West']

FRANCE = """Bordeaux Bayonne Hennebont Redon Auray Vannes Nantes Lorient
Pauillac Arcachon Blaye Quimper Morlaix Rochefort Brest Paimpol Marseilles
Cette Caen Rouen Dieppe Honfleur Granville Cherbourg Fecamp Boulogne Calais
Dunkirk Landerneau Douarnenez Concarneau Hennebont Tonnay-Charente Mortagne
Marans Libourne Bergerac Dax Charente""".split()
FRANCE += ['La Roche Bernard', 'Saint-Brieuc', 'St. Malo', 'La Tremblede',
           'Le Havre', 'La Rochelle', 'St. Nazaire', 'Port Launay',
           "Pont-l'Abbé", 'St. Estephe', 'St. Servan', 'Ile de Batz',
           'La Teste', 'St. Valery']

COUNTRY = {}
for names, c in [(SWEDEN, 'Sweden'), (NORWAY, 'Norway'), (RUSSIA, 'Russia'),
                 (FINLAND, 'Finland'), (GERMANY, 'Germany'), (CANADA, 'Canada'),
                 (USA, 'USA'), (FRANCE, 'France')]:
    for n in names:
        COUNTRY[n] = c


def doc_group(stem: str) -> str:
    return re.sub(r'_p\d{3}_normalized$', '', stem)


def year_of(name: str):
    m = re.match(r'^(\d{4})', name) or re.search(r'(18\d{2}|1900)', name)
    return int(m.group(1)) if m else None


def load_shipments():
    ships = []
    for f in sorted(NORM.glob('*.json')):
        y = year_of(f.stem)
        if y not in VALID_YEARS:
            continue
        grp = doc_group(f.stem)
        for s in json.load(open(f)).get('shipments', []):
            origin = s.get('origin_port_normalized') or ''
            ships.append({
                'year': y, 'group': grp,
                'origin': origin,
                'country': COUNTRY.get(origin, 'Other/Unmapped' if origin else 'NoOrigin'),
                'dest': s.get('destination_port_normalized') or '',
                'steam': bool(s.get('is_steamship')),
                'forms': tuple(sorted({fm for c in s.get('cargo', [])
                                       for fm in c.get('commodity_forms', [])})),
            })
    return ships


def boot_ci(groups_data, country, reps=800, seed=42):
    """Percentile CI for a country's share, resampling doc groups."""
    rng = random.Random(seed)
    keys = list(groups_data)
    stats = []
    for _ in range(reps):
        num = den = 0
        for k in (rng.choice(keys) for _ in keys):
            n, d = groups_data[k].get(country, 0), sum(groups_data[k].values())
            num += n
            den += d
        stats.append(num / den if den else 0.0)
    stats.sort()
    return stats[int(0.025 * reps)], stats[int(0.975 * reps)]


def main():
    ships = load_shipments()
    total = len(ships)
    print(f'shipments in valid years: {total:,}')
    unmapped = Counter(s['origin'] for s in ships if s['country'] == 'Other/Unmapped')
    mapped_n = sum(1 for s in ships if s['country'] not in ('Other/Unmapped', 'NoOrigin'))
    noorig = sum(1 for s in ships if s['country'] == 'NoOrigin')
    print(f'mapped to country: {mapped_n / total:.1%}   no origin: {noorig / total:.1%}')
    print('top unmapped origins:', unmapped.most_common(25))

    # ---------------- country share per year, with bootstrap CI for Canada
    countries = ['Canada', 'Sweden', 'Norway', 'Russia', 'Finland', 'Germany',
                 'USA', 'France']
    per_year = defaultdict(Counter)          # year -> country -> n (mapped only)
    per_year_groups = defaultdict(lambda: defaultdict(Counter))  # year -> grp -> country
    for s in ships:
        if s['country'] in ('Other/Unmapped', 'NoOrigin'):
            continue
        per_year[s['year']][s['country']] += 1
        per_year_groups[s['year']][s['group']][s['country']] += 1

    print('\n== Country shares of UK-arrival shipments (TTJ, mapped origins) ==')
    hdr = 'year    n_ship  ' + ''.join(f'{c:>8}' for c in countries) + '   Canada 95% CI'
    print(hdr)
    rows_out = []
    for y in VALID_YEARS:
        cnt = per_year[y]
        n = sum(cnt.values())
        if not n:
            continue
        lo, hi = boot_ci(per_year_groups[y], 'Canada')
        line = f'{y}  {n:8,}  ' + ''.join(f'{cnt[c] / n:8.1%}' for c in countries)
        print(line + f'   [{lo:.1%}, {hi:.1%}]')
        for c in countries:
            rows_out.append({'year': y, 'country': c, 'shipments': cnt[c],
                             'share': round(cnt[c] / n, 4)})
    with open(BASE / 'exports' / 'country_shares_year.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['year', 'country', 'shipments', 'share'])
        w.writeheader()
        w.writerows(rows_out)

    # ---------------- Canada commodity profile (RCA)
    print('\n== Canada revealed specialization (RCA by commodity form) ==')
    form_all = Counter()
    form_can = Counter()
    can_total = all_total = 0
    for s in ships:
        if s['country'] in ('Other/Unmapped', 'NoOrigin'):
            continue
        all_total += 1
        for fm in s['forms']:
            form_all[fm] += 1
        if s['country'] == 'Canada':
            can_total += 1
            for fm in s['forms']:
                form_can[fm] += 1
    print(f'{"form":<22}{"Can n":>7}{"Can %":>8}{"All %":>8}{"RCA":>6}')
    for fm, n in form_can.most_common(12):
        rca = (n / can_total) / (form_all[fm] / all_total)
        print(f'{fm:<22}{n:>7}{n / can_total:>8.1%}{form_all[fm] / all_total:>8.1%}{rca:>6.2f}')

    # Canada deals share over time vs Baltic
    print('\n== "deals" share of each country\'s shipments, by year ==')
    print('year   Canada  Sweden  Russia  Norway')
    for y in VALID_YEARS:
        row = f'{y}'
        for c in ['Canada', 'Sweden', 'Russia', 'Norway']:
            subs = [s for s in ships if s['year'] == y and s['country'] == c]
            if len(subs) < 30:
                row += '      --'
                continue
            d = sum(1 for s in subs if 'deals' in s['forms'])
            row += f'{d / len(subs):>8.1%}'
        print(row)

    # ---------------- Canada destination portfolio
    print('\n== Canada: top UK destination ports (share of Canada shipments) ==')
    half = {'early': [y for y in VALID_YEARS if y <= 1885],
            'late': [y for y in VALID_YEARS if y >= 1887]}
    for label, yrs in half.items():
        dests = Counter(s['dest'] for s in ships
                        if s['country'] == 'Canada' and s['year'] in yrs and s['dest'])
        n = sum(dests.values())
        hhi = sum((v / n) ** 2 for v in dests.values())
        top = ', '.join(f'{d} {v / n:.0%}' for d, v in dests.most_common(6))
        print(f'{label} ({yrs[0]}-{yrs[-1]}): n={n:,} HHI={hhi:.3f}  {top}')

    # ---------------- steam adoption
    print('\n== Steamship share of shipments, by country ==')
    print('year   Canada  Sweden  Russia  Norway     USA')
    for y in VALID_YEARS:
        row = f'{y}'
        for c in ['Canada', 'Sweden', 'Russia', 'Norway', 'USA']:
            subs = [s for s in ships if s['year'] == y and s['country'] == c]
            if len(subs) < 30:
                row += '      --'
                continue
            st = sum(1 for s in subs if s['steam'])
            row += f'{st / len(subs):>8.1%}'
        print(row)

    # ---------------- UK Gov decennial anchor
    print('\n== UK Gov decennial imports: timber quantity shares (Loads) ==')
    rows = list(csv.DictReader(open(UKGOV)))

    def is_timber(c):
        cl = c.lower()
        if any(k in cl for k in ['dye', 'pulp', 'paper', 'bark', 'pipe', 'gun',
                                 'stone', 'marble', 'pitch', 'furniture']):
            return False
        return any(k in cl for k in ['timber', 'deal', 'batten', 'stave',
                                     'lath', 'wainscot', 'fir', 'oak', 'hewn',
                                     'sawn'])

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
        if s in ('World', 'Total'):
            return None
        return 'Other'

    agg_q = defaultdict(Counter)
    agg_v = defaultdict(Counter)
    for r in rows:
        y = int(r['YEAR'])
        if y < 1861 or not is_timber(r['COMMODITY_NAME']):
            continue
        c = src_country(r['SOURCE_LOCATION_NAME'])
        if c is None:
            continue
        if r['UNIT_NAME'] == 'Loads':
            agg_q[y][c] += float(r['AMOUNT'] or 0)
        v = float(r['VALUE'] or 0)
        if v:
            agg_v[y][c] += v
    for name, agg in [('quantity (Loads)', agg_q), ('value (£)', agg_v)]:
        print(f'\n-- share of {name} --')
        cs = ['Canada', 'Russia', 'Sweden', 'Norway', 'Germany', 'USA', 'France', 'Other']
        print('year  ' + ''.join(f'{c:>8}' for c in cs) + f'{"total":>14}')
        for y in sorted(agg):
            tot = sum(agg[y].values())
            print(f'{y}  ' + ''.join(f'{agg[y][c] / tot:8.1%}' for c in cs)
                  + f'{tot:>14,.0f}')


if __name__ == '__main__':
    main()
