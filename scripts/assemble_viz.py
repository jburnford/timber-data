#!/usr/bin/env python3
"""Inject land polygons + data into docs/template.html -> docs/index.html."""
import json
from pathlib import Path

BASE = Path('/home/jic823/timber_data')
SCRATCH = Path('/tmp/claude-1000/-home-jic823-timber-data/'
               'd52e8b24-1f20-4465-8a08-eae32a82967b/scratchpad')

tpl = (BASE / 'docs' / 'template.html').read_text()
land_path = BASE / 'docs' / 'land.json'
if not land_path.exists():
    land_path = SCRATCH / 'land.json'
land = land_path.read_text()
data = (BASE / 'docs' / 'data.json').read_text()

out = tpl.replace('/*__LAND__*/[]', land).replace('/*__DATA__*/{}', data)
(BASE / 'docs' / 'index.html').write_text(out)
print(f'docs/index.html: {len(out)/1e6:.1f} MB')
