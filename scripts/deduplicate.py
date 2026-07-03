#!/usr/bin/env python3
"""Deduplicate parsed shipments (parsed/ -> deduped/).

Duplicates = identical normalized raw_text + destination within the same
document group (filename minus _pNNN page suffix). Catches:
  - Gemini hallucination repetition loops (same line emitted 100s of times)
  - photographic page-overlap duplicates across _p001/_p002 files
Keeps the first occurrence (page order, then line order). Cross-issue
recurrences are NOT touched — identical short lines in different weekly
issues are legitimate.

Also drops empty husk records (no ship, no origin, no cargo).
"""

import json
import re
import glob
from collections import defaultdict
from pathlib import Path

BASE = Path('/home/jic823/timber_data')
IN_DIR = BASE / 'parsed'
OUT_DIR = BASE / 'deduped'
OUT_DIR.mkdir(exist_ok=True)


def doc_group(stem: str) -> str:
    return re.sub(r'_p\d{3}$', '', stem)


def page_no(stem: str) -> int:
    m = re.search(r'_p(\d{3})$', stem)
    return int(m.group(1)) if m else 0


def signature(s: dict):
    raw = re.sub(r'\s+', ' ', (s.get('raw_text') or '')).strip().lower()
    return (raw, s.get('destination_port') or '')


def main():
    files = sorted(glob.glob(str(IN_DIR / '*_parsed.json')))
    groups = defaultdict(list)
    for f in files:
        stem = Path(f).name.replace('_parsed.json', '')
        groups[doc_group(stem)].append((page_no(stem), stem, f))

    total = kept = dups = husks = 0
    per_file_dups = {}

    for g, members in groups.items():
        seen = set()
        for _, stem, f in sorted(members):
            d = json.load(open(f))
            out = dict(d)
            if d.get('status') == 'success':
                new = []
                file_dups = 0
                for s in d['shipments']:
                    total += 1
                    if not s.get('ship_name') and not s.get('origin_port') and not s.get('cargo'):
                        husks += 1
                        continue
                    sig = signature(s)
                    if sig in seen:
                        dups += 1
                        file_dups += 1
                        continue
                    seen.add(sig)
                    new.append(s)
                    kept += 1
                out['shipments'] = new
                out['shipment_count'] = len(new)
                out['dedup'] = {'removed_duplicates': file_dups}
                if file_dups:
                    per_file_dups[stem] = file_dups
            with open(OUT_DIR / f'{stem}_deduped.json', 'w') as fh:
                json.dump(out, fh, indent=1)

    report = {
        'total_records': total, 'kept': kept,
        'removed_duplicates': dups, 'removed_empty_husks': husks,
        'files_with_duplicates': len(per_file_dups),
        'worst_files': dict(sorted(per_file_dups.items(), key=lambda x: -x[1])[:20]),
    }
    (BASE / 'reports').mkdir(exist_ok=True)
    with open(BASE / 'reports' / 'dedup_report.json', 'w') as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps(report, indent=2)[:1200])


if __name__ == '__main__':
    main()
