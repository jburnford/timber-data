#!/usr/bin/env python3
"""Normalize cargo commodity strings in deduped/*.json (in place).

Adds to each cargo item:
  commodity_normalized  cleaned string
  commodity_forms       list of product-form categories (deals, battens, ...)
  commodity_species     list of wood species mentioned (fir, oak, pitch pine, ...)
  commodity_status      ok | merchant_leak | empty | unclassified

Counting "shipments per cargo type" should use commodity_forms (a compound
item like "deals and battens" yields both forms).
"""

import json
import re
import glob
from collections import Counter
from pathlib import Path

BASE = Path('/home/jic823/timber_data')

FOLDS = [
    (re.compile(r'\bpit-?props?\b'), 'pit props'),
    (re.compile(r'\bprops?\b'), 'pit props'),
    (re.compile(r'\bmatch-? ?boards?\b'), 'matchboards'),
    (re.compile(r'\bbox-? ?boards?\b'), 'boxboards'),
    (re.compile(r'\btim\b\.?'), 'timber'),
    (re.compile(r'\bbats\b'), 'battens'),
    (re.compile(r'\bhalf-? ?sleepers?\b'), 'half sleepers'),
    (re.compile(r'\briek?ers?\b|\brickers?\b'), 'rickers'),
    (re.compile(r'^and\s+'), ''),
    (re.compile(r'^c\.\s+'), ''),
    (re.compile(r'\b&c\.?\b'), ''),
    (re.compile(r'\bditto\b|\bdo\.\b'), ''),
]

FORMS = [
    ('deal ends', r'\bdeal ends?\b'),
    ('batten ends', r'\bbatten ends?\b'),
    ('deals', r'\bdeals?\b'),
    ('battens', r'\bbattens?\b'),
    ('ends', r'(?<!deal )(?<!batten )\bends?\b'),
    ('matchboards', r'\bmatchboards?\b'),
    ('boxboards', r'\bboxboards?\b'),
    ('flooring', r'\bfloorings?\b'),
    ('boards', r'\bboards?\b'),
    ('staves', r'\bstaves?\b'),
    ('headings', r'\bheadings?\b'),
    ('laths', r'\blaths?\b'),
    ('lathwood', r'\blathwood\b'),
    ('pit props', r'\bpit props\b'),
    ('pitwood', r'\bpitwood\b'),
    ('mining timber', r'\bmining timber\b'),
    ('firewood', r'\bfirewood\b|\bfire wood\b'),
    ('sleepers', r'\bsleepers?\b|\bsleeper blocks?\b|\bhalf sleepers\b|\bcrossings?\b'),
    ('timber', r'(?<!mining )\btimber\b'),
    ('logs', r'\blogs?\b'),
    ('planks', r'\bplanks?\b'),
    ('scantlings', r'\bscantlings?\b'),
    ('spars', r'\bspars?\b'),
    ('poles', r'\bpoles?\b'),
    ('rickers', r'\brickers\b'),
    ('palings', r'\bpalings?\b'),
    ('hoops', r'\bhoops?\b'),
    ('oars', r'\boars?\b'),
    ('doors', r'\bdoors?\b'),
    ('mouldings', r'\bmouldings?\b'),
    ('lumber', r'\blumber\b'),
    ('wood pulp', r'\bpulp\b'),
    ('shooks', r'\bshooks?\b'),
    ('spokes', r'\bspokes?\b'),
    ('handles', r'\bhandles?\b'),
    ('splints', r'\bsplints?\b'),
    ('joinery', r'\bjoinery\b'),
    ('woodware', r'\bwoodware\b|\bturned wood\b|\bwood turnery\b'),
    ('blocks', r'(?<!sleeper )(?<!maple )\bblocks?\b'),
    ('treenails', r'\btree ?nails?\b'),
    ('boathooks', r'\bboat ?hooks?\b'),
    ('crowntrees', r'\bcrown ?trees?\b'),
    ('gun stocks', r'\bgun-? ?stocks?\b'),
    ('bobbins', r'\bbobbins?\b'),
    ('trellis', r'\btrellis\b'),
    ('rails', r'\brails?\b'),
    ('splits', r'\bsplits?\b'),
    ('squares', r'\bsquares?\b'),
    ('spoolwood', r'\bspool ?wood\b'),
    ('posts', r'\bposts?\b'),
    ('balks', r'\bbalks?\b|\bbaulks?\b'),
    ('timber', r'^(?:sawn|hewn)$|^(?:sawn and hewn|hewn and sawn)$'),
    ('wood', r'\bwood\b'),
]
FORMS = [(name, re.compile(rx)) for name, rx in FORMS]

SPECIES = [
    ('pitch pine', r'\bpitch pine\b'),
    ('white pine', r'\bwhite pine\b'),
    ('red pine', r'\bred pine\b'),
    ('yellow pine', r'\byellow pine\b'),
    ('waney pine', r'\bwaney pine\b'),
    ('pine', r'(?<!pitch )(?<!white )(?<!red )(?<!yellow )(?<!waney )\bpine\b'),
    ('fir', r'\bfirs?\b'),
    ('spruce', r'\bspruce\b'),
    ('oak', r'\boak\b'),
    ('birch', r'\bbirch\b'),
    ('elm', r'\belm\b'),
    ('ash', r'\bash\b'),
    ('poplar', r'\bpoplar\b'),
    ('maple', r'\bmaple\b'),
    ('beech', r'\bbeech\b'),
    ('teak', r'\bteak\b'),
    ('mahogany', r'\bmahogany\b'),
    ('walnut', r'\bwalnut\b'),
    ('cedar', r'\bcedar\b'),
    ('ebony', r'\bebony\b'),
    ('boxwood', r'\bbox ?wood\b'),
    ('hickory', r'\bhickory\b'),
    ('whitewood', r'\bwhite ?wood\b'),
    ('greenheart', r'\bgreenheart\b'),
    ('lancewood', r'\blancewood\b'),
    ('sapanwood', r'\bsapan ?wood\b'),
    ('rosewood', r'\brosewood\b'),
    ('satinwood', r'\bsatin ?wood\b'),
    ('snakewood', r'\bsnakewood\b'),
    ('redwood', r'\bred ?wood\b'),
    ('logwood', r'\blog ?wood\b'),
    ('fustic', r'\bfustic\b'),
    ('lignum vitae', r'\blignum[ -]?vit'),
    ('jarrah', r'\bjarrah\b'),
    ('hardwood', r'\bhard ?wood\b'),
    ('fir', r'\bfirwood\b'),
]
SPECIES = [(name, re.compile(rx)) for name, rx in SPECIES]

MERCHANT_LEAK = re.compile(
    r'(?:\bco\b\.?$|\bbros?\b\.?$|\bsons?\b\.?$|\bconsignees?\b|\border\b|'
    r"^[a-z]\.\s|\bmessrs\b|&)")


def clean(text: str) -> str:
    t = text.strip().lower()
    t = re.sub(r'[()\[\]"]', ' ', t)
    for rx, rep in FOLDS:
        t = rx.sub(rep, t)
    t = re.sub(r'\s+', ' ', t).strip(' ,.;:-')
    return t


def classify(raw: str):
    norm = clean(raw)
    if not norm:
        return norm, [], [], 'empty'
    forms = [name for name, rx in FORMS if rx.search(norm)]
    species = [name for name, rx in SPECIES if rx.search(norm)]
    if forms or species:
        return norm, forms, species, 'ok'
    if re.match(r'^from\s', norm):
        return norm, [], [], 'origin_leak'
    if MERCHANT_LEAK.search(norm):
        return norm, [], [], 'merchant_leak'
    return norm, [], [], 'unclassified'


def main():
    files = sorted(glob.glob(str(BASE / 'deduped' / '*_deduped.json')))
    status_counts = Counter()
    form_counts = Counter()
    unclassified = Counter()
    items = 0
    for f in files:
        d = json.load(open(f))
        if d.get('status') != 'success':
            continue
        changed = False
        for s in d['shipments']:
            for c in s.get('cargo') or []:
                items += 1
                norm, forms, species, status = classify(c.get('commodity') or '')
                c['commodity_normalized'] = norm
                c['commodity_forms'] = forms
                c['commodity_species'] = species
                c['commodity_status'] = status
                status_counts[status] += 1
                for fm in forms:
                    form_counts[fm] += 1
                if status == 'unclassified':
                    unclassified[norm] += 1
                changed = True
        if changed:
            with open(f, 'w') as fh:
                json.dump(d, fh, indent=1)

    report = {
        'cargo_items': items,
        'status': dict(status_counts),
        'coverage_ok': status_counts['ok'] / max(1, items),
        'form_counts': dict(form_counts.most_common()),
        'top_unclassified': dict(unclassified.most_common(60)),
    }
    with open(BASE / 'reports' / 'commodity_normalization_report.json', 'w') as fh:
        json.dump(report, fh, indent=2)
    print(f"items={items:,}  ok={status_counts['ok']/max(1,items):.1%}  "
          f"unclassified={status_counts['unclassified']:,}  "
          f"merchant_leak={status_counts['merchant_leak']:,}  empty={status_counts['empty']:,}")
    print('\ntop forms:', form_counts.most_common(15))
    print('\ntop unclassified:')
    for k, v in unclassified.most_common(25):
        print(f'  {v:5d}  {k[:60]}')


if __name__ == '__main__':
    main()
