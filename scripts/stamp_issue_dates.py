#!/usr/bin/env python3
"""Stamp doc-level issue_date into existing parsed/, deduped/, normalized/ files.

The weekly journal issue date is recoverable from every source filename
(compact "18760108..." prefix or verbose "May 1 1875"); it gives every
shipment a date window even where the arrival_date column is blank (the
1870s @ format prints dates as run headers, so most lines carry none).

One-off backfill for outputs produced before parse_shipments.py emitted
issue_date natively. Idempotent; future full pipeline reruns don't need it.
"""

import json
from pathlib import Path

from parse_shipments import issue_date_of

BASE = Path('/home/jic823/timber_data')

for stage in ('parsed', 'deduped', 'normalized'):
    n_done = n_missing = 0
    for f in sorted((BASE / stage).glob('*.json')):
        doc = json.load(open(f))
        if not isinstance(doc, dict) or 'source_file' not in doc:
            continue
        idate = issue_date_of(doc['source_file'])
        if doc.get('issue_date') == idate:
            continue
        doc['issue_date'] = idate
        with open(f, 'w') as fh:
            json.dump(doc, fh, indent=1)
        n_done += 1
        if idate is None:
            n_missing += 1
            print(f'  no issue date: {doc["source_file"]}')
    print(f'{stage}: stamped {n_done} files ({n_missing} unresolvable)')
