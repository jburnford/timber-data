# British Timber Trade Data, 1874–1900

Structured shipment data and a knowledge graph of ~159,000 timber cargo
arrivals at British and Irish ports, extracted from the weekly import lists of
the *Timber Trades Journal* (1874–1900).

The source pages were photographed by hand from bound volumes, OCR'd with
Gemini 2.5 Pro, then parsed and normalized with the deterministic Python
pipeline in this repository.

## What's here

| Path | Contents |
|------|----------|
| `kg/` | **Knowledge graph** — Ladybug graph DB (`timber.lbdb`, Cypher-queryable) + aggregate JSON graph + schema/query docs ([kg/README.md](kg/README.md)) |
| `docs/` | Interactive visualizations of geographic change over time |
| `exports/` | Analysis-ready CSVs: shipment counts by port × commodity × year, routes, merchants |
| `scripts/` | The full parsing/normalization/graph pipeline (deterministic, no LLM calls) |
| `reference_data/` | Port authority (variant→canonical), geocoding DB, merchant authority, coverage reports |
| `reports/` | Data-quality, dedup, and normalization reports |
| `CLAUDE.md` | Full pipeline documentation, bug history, and coverage statistics |

Intermediate pipeline outputs (`ocr_results/`, `parsed/`, `deduped/`,
`normalized/`) are not committed — they are regenerable by running the
pipeline, and the OCR corpus is distributed as a release asset.

## The one rule for using this data

**Count shipments; never sum quantities.** OCR'd quantity digits are
unreliable (37.6% exact against human transcription; most errors are wrong in
the first digit). Ports, commodities, ship names, merchants, and dates are
reliable (~93–97%). All aggregates in `exports/` and edge weights in `kg/` are
shipment counts.

Also note: coverage is **odd-year heavy** — even years 1876–1892 are nearly
absent because the volumes were photographed every other year — and 1877
LONDON used an aggregated format that is not included.

## Quick start

```python
# pip install ladybug
import ladybug
db = ladybug.Database('kg/timber.lbdb', read_only=True)
con = ladybug.Connection(db)
r = con.execute("""
    MATCH (s:Shipment)-[:ARRIVED_FROM]->(o:Port),
          (s)-[:ARRIVED_AT]->(:Port {name:'Cardiff'}),
          (s)-[:CARRIED]->(:Commodity {form:'pitwood'})
    RETURN o.name, count(DISTINCT s) AS n ORDER BY n DESC LIMIT 5""")
while r.has_next():
    print(r.get_next())
# [Bordeaux, 1636], [Bayonne, 375], ...
```

Or just open `exports/dest_commodity_year.csv` in a spreadsheet.

## Citation

Primary source: *The Timber Trades Journal*, weekly "Imports" lists,
1874–1900. Individual records can contain OCR errors — every shipment in the
graph retains its `raw_text` and source file/line for verification.

Data preparation: Jim Clifford (University of Saskatchewan), with
LLM-assisted OCR (2025) and a deterministic parsing pipeline (2026).
