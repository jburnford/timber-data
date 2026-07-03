#!/usr/bin/env python3
"""Normalize consignee/merchant names in deduped/*.json (in place).

Adds to each shipment:
  consignee_normalized  canonical firm name (None for placeholders)
  consignee_type        named | order | master | none

Method:
  1. clean surface form (punctuation, Messrs., "and"->"&", Co/Bros endings)
  2. classify placeholders (Order / Master / Nil / &c.); propagate Ditto
     from the previous named consignee in the same file
  3. cluster variants: exact squash-key merge (case/punctuation-insensitive),
     then a conservative fuzzy pass (difflib >= 0.90, same first letter,
     len >= 8, low-freq variant -> high-freq canonical)

Outputs reference_data/merchant_authority.json and
reports/merchant_normalization_report.json.
"""

import json
import re
import glob
import difflib
from collections import Counter
from pathlib import Path

BASE = Path('/home/jic823/timber_data')

ORDER_RE = re.compile(r'^(?:to\s+|on\s+)?order$', re.I)
MASTER_RE = re.compile(r'^(?:the\s+)?(?:master|captain)s?$', re.I)
NONE_RE = re.compile(r'^(?:nil|none|&c|etc|sundry(?:\s+consignees)?|various)\.?$', re.I)
DITTO_RE = re.compile(r'^(?:ditto|do)\.?$', re.I)


def clean(name: str) -> str:
    t = re.sub(r'\s+', ' ', name).strip()
    t = re.sub(r'^(?:Messrs\.?|Mr\.?)\s+', '', t)
    t = t.strip(' .,;:-')
    t = re.sub(r'\s+and\s+', ' & ', t)
    t = re.sub(r'\bCo$', 'Co.', t)
    t = re.sub(r'\bCos$', 'Cos.', t)
    t = re.sub(r'\bBros?$', 'Bros.', t)
    t = re.sub(r'\bLtd$', 'Ltd.', t)
    t = re.sub(r'\s*,\s*', ', ', t)
    t = re.sub(r'\s*&\s*', ' & ', t)
    return t.strip()


def squash(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', name.lower())


def classify(raw: str):
    """Return (type, cleaned) — cleaned is None for placeholders."""
    t = raw.strip()
    if not t:
        return 'none', None
    if ORDER_RE.match(t):
        return 'order', None
    if MASTER_RE.match(t):
        return 'master', None
    if NONE_RE.match(t):
        return 'none', None
    if DITTO_RE.match(t):
        return 'ditto', None
    c = clean(t)
    if not c or len(squash(c)) < 2:
        return 'none', None
    return 'named', c


def main():
    files = sorted(glob.glob(str(BASE / 'deduped' / '*_deduped.json')))

    # pass 1: frequency of cleaned named forms
    freq = Counter()
    for f in files:
        d = json.load(open(f))
        if d.get('status') != 'success':
            continue
        for s in d['shipments']:
            typ, c = classify(s.get('consignee') or '')
            if typ == 'named':
                freq[c] += 1

    # squash-key merge: canonical = most frequent surface form per key
    by_key = {}
    for name, n in freq.items():
        k = squash(name)
        if k not in by_key or freq[by_key[k]] < n:
            by_key[k] = name
    exact_map = {name: by_key[squash(name)] for name in freq}

    # fuzzy pass: low-freq canonicals -> high-freq canonicals
    canon_freq = Counter()
    for name, n in freq.items():
        canon_freq[exact_map[name]] += n
    big = [c for c, n in canon_freq.items() if n >= 100]
    big_by_letter = {}
    for c in big:
        big_by_letter.setdefault(c[0].lower(), []).append(c)
    fuzzy_map = {}
    for c, n in canon_freq.items():
        if n >= 100 or len(c) < 8:
            continue
        cands = big_by_letter.get(c[0].lower(), [])
        best, best_r = None, 0.0
        for b in cands:
            if abs(len(b) - len(c)) > max(3, len(c) // 4):
                continue
            r = difflib.SequenceMatcher(None, c.lower(), b.lower()).ratio()
            if r > best_r:
                best, best_r = b, r
        if best and best_r >= 0.90:
            fuzzy_map[c] = best

    def canonical(name):
        c = exact_map.get(name, name)
        return fuzzy_map.get(c, c)

    # pass 2: apply, with ditto propagation per file
    type_counts = Counter()
    for f in files:
        d = json.load(open(f))
        if d.get('status') != 'success':
            continue
        prev_named = None
        for s in d['shipments']:
            typ, c = classify(s.get('consignee') or '')
            if typ == 'ditto':
                if prev_named:
                    typ, c = 'named', prev_named
                else:
                    typ, c = 'none', None
            if typ == 'named':
                c = canonical(c)
                prev_named = c
            s['consignee_normalized'] = c
            s['consignee_type'] = typ
            type_counts[typ] += 1
        with open(f, 'w') as fh:
            json.dump(d, fh, indent=1)

    # authority + report
    variant_map = {}
    for name in freq:
        can = canonical(name)
        if can != name:
            variant_map[name] = can
    final_freq = Counter()
    for name, n in freq.items():
        final_freq[canonical(name)] += n

    with open(BASE / 'reference_data' / 'merchant_authority.json', 'w') as fh:
        json.dump({'variant_to_canonical': dict(sorted(variant_map.items())),
                   'canonical_frequencies': dict(final_freq.most_common())}, fh, indent=1)
    report = {
        'consignee_types': dict(type_counts),
        'unique_raw_named': len(freq),
        'unique_canonical': len(final_freq),
        'exact_merges': sum(1 for k, v in exact_map.items() if k != v),
        'fuzzy_merges': len(fuzzy_map),
        'top_merchants': dict(final_freq.most_common(40)),
    }
    with open(BASE / 'reports' / 'merchant_normalization_report.json', 'w') as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k != 'top_merchants'}, indent=2))
    print('\ntop merchants:')
    for k, v in final_freq.most_common(20):
        print(f'  {v:7,d}  {k}')
    print('\nsample fuzzy merges:')
    for i, (k, v) in enumerate(fuzzy_map.items()):
        if i >= 15:
            break
        print(f'  {k!r} -> {v!r}')


if __name__ == '__main__':
    main()
