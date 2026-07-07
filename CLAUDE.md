# Timber Data Parsing & Normalization Pipeline

## Project Overview

Extracts structured shipping-import data from OCR'd Timber Trades Journal pages
(1874–1900), normalizes ports and commodities, and produces analysis-ready
counts of shipments by port and cargo type.

**Analytical stance**: OCR'd *quantities are not trustworthy* (earlier
validation vs. human-transcribed 1883 London data: only 37.6% exact, ~75% of
errors wrong in the first digit). Ports, commodities, ship names, and dates
ARE reliable. The supported unit of analysis is **counts of shipments** by
port/commodity/year — never summed quantities.

## Data Sources

| Source | Location | Content |
|--------|----------|---------|
| OCR text | `ocr_results/gemini_full/` | 2,041 files (Gemini 2.5 Pro, hand-held photos) |
| Line classification | `classification/*.json` | Gemini line labels (SHIPPING_DATA, PORT_HEADER, ...) |
| Manual matches | `/home/jic823/TTJ Forest of Numbers/reference_data/manual_port_matches.json` | 109 OCR→canonical rules |
| Authority mappings | `/home/jic823/TTJ Forest of Numbers/final_output/authority_normalized/ports_completed.csv` | 228 MAP + 105 ACCEPT rules |
| Coordinates | `/home/jic823/TTJ Forest of Numbers/Ports_Master.geojson` | 558 ports with lat/lon |

## Pipeline (July 2026 rebuild)

```
ocr_results/gemini_full/*.txt + classification/*.json
     │
     ▼
1. scripts/parse_shipments.py          → parsed/*_parsed.json
     unified parser, all eras: dash format (1879-1900) AND
     @ format (1874-1878, multi-ship paragraphs); stitches wrapped
     column lines; handles commodity section headers (PITWOOD.—);
     gazetteer rescue for separator-free lines and dock-list rows
     ("Black Eagle Sheerness Lavender yard")
     │
     ▼
2. scripts/deduplicate.py              → deduped/*_deduped.json
     removes Gemini hallucination loops + page-overlap dups
     (scope: within document group only — cross-issue repeats are legit)
     │
     ▼
3. scripts/normalize_commodities.py    (updates deduped/ in place)
     adds commodity_normalized, commodity_forms[], commodity_species[],
     commodity_status to every cargo item
     │
     ▼
3b. scripts/normalize_merchants.py     (updates deduped/ in place)
     adds consignee_normalized + consignee_type (named|order|master|none);
     squash + conservative fuzzy variant clustering; Ditto propagation;
     writes reference_data/merchant_authority.json
     │
     ▼
4. scripts/build_port_authority.py     → reference_data/port_authority.json
   scripts/build_geocoding_db.py       → reference_data/port_coordinates.json
     │
     ▼
5. scripts/normalize_ports.py          → normalized/*_normalized.json
     punctuation-insensitive lookup ("St. John, N.B" == "St. John, N.B.")
     │
     ▼
6. scripts/generate_port_report.py     → reference_data/port_coverage_report.*
   scripts/export_cargo_counts.py      → exports/*.csv (headline deliverable)
     │
     ▼
7. scripts/build_knowledge_graph.py    → kg/timber.lbdb + kg/timber_kg.json
     Ladybug graph DB (shipment-level, Cypher) + aggregate JSON graph;
     schema, sample queries, and sharing notes in kg/README.md
```

Run everything:
```bash
cd /home/jic823/timber_data
python3 scripts/parse_shipments.py
python3 scripts/deduplicate.py
python3 scripts/normalize_commodities.py
python3 scripts/normalize_merchants.py
python3 scripts/build_port_authority.py && python3 scripts/build_geocoding_db.py
python3 scripts/normalize_ports.py
python3 scripts/generate_port_report.py && python3 scripts/export_cargo_counts.py
python3 scripts/build_knowledge_graph.py
```
All stages are deterministic and re-runnable (no LLM calls).

## Coverage (2026-07-03, after parser rebuild)

158,918 shipments (165,941 parsed − 7,023 in-document duplicates).

| Metric | old pipeline (Jan 2026) | current |
|--------|------|---------|
| Junk cargo items (digit fragments) | 27.9% | 2.6% |
| Cargo items classified to a form/species | — | 92.7% |
| Empty origin port | 16.0% | 3.8% |
| Records with arrival date | 25.0% | 46.2% |
| Origin normalized | 70.3% | 84.4% |
| Destination normalized | 88.4% | 92.1% (1.1% unmapped) |
| Both ports geocoded | 58.4% | 73.9% |
| Named consignees canonicalized | — | 17,565 raw → 15,766 canonical |

## Bugs fixed in the July 2026 rebuild (parse_tabular.py → parse_shipments.py)

1. **Thousands-comma split**: "26,744 pcs. sawn fir" became cargo items "2/6" + "744 pcs...". ~29% of all cargo items were digit junk.
2. **@ format unhandled**: 1874–78 lines (`Ship @ Origin,—cargo, Merchant`) put the whole line in ship_name. ~10.5k shipments.
3. **Spaced separators**: `Ship - Origin - cargo` (space-hyphen-space) never split; killed whole files.
4. **Lowercase cargo glued to origin**: `Riga-deals` didn't split (splitter required a capital after hyphen) → thousands of "port+cargo combined" origins.
5. **Fabricated consignee**: parse failures defaulted consignee to "Order" (41% of records; true rate 22%).
6. **Merchant-as-commodity inversion**: `deals-Simson & Mason` made the merchant the commodity.
7. **Date regex**: months without periods (May, March...) and "Sept." never matched → cascading date loss (75% missing).
8. **PORT_HEADER regex**: no apostrophe/period → `BO'NESS`→"BO", `NEWPORT (MON.)` truncated.
9. **Wrapped column lines**: continuation fragments parsed as separate garbage records; now stitched.
10. **Dedup**: hallucination loops (one file had 2,315 copies of one line) removed within document scope.

## Output record format (normalized/*.json)

```json
{
  "raw_text": "Dec. 29 Gloucester (s)-New York-50 crts., 5 cs. handles-J. G. Rollins & Co.",
  "arrival_date": "Dec. 29", "ship_name": "Gloucester", "is_steamship": true,
  "origin_port_normalized": "New York", "origin_port_status": "canonical",
  "origin_port_lat": 40.71, "origin_port_lon": -74.01,
  "destination_port_normalized": "Bristol", "destination_port_status": "mapped",
  "consignee": "J. G. Rollins & Co",
  "consignee_normalized": "J. G. Rollins & Co.", "consignee_type": "named",
  "cargo": [{"quantity": "5", "unit": "cs.", "commodity": "handles",
             "commodity_forms": ["handles"], "commodity_species": [],
             "commodity_status": "ok"}],
  "port_normalization_status": "both_geocoded"
}
```

Each document also carries a doc-level `issue_date` (ISO, from the source
filename — compact `18760108...` prefix or verbose "May 1 1875"; 100% of files).
Use it as the date when `arrival_date` is null: the 1870s @ format prints dates
as run headers so most lines carry none (only ~47% of records have arrival_date),
and 95% of dated arrivals fall within 2 weeks before the issue date.

Port status: `mapped | canonical | error | unmapped | empty`.
Commodity status: `ok | merchant_leak | origin_leak | empty | unclassified`.
`commodity_forms` is the counting key ("deals and battens" → both forms).
Consignee is `null` when unparsed — "Order" only when the source says so.
`consignee_type`: `named` (use consignee_normalized) | `order` (consigned "to
order") | `master` (ship's master) | `none`. "Ditto" entries inherit the
previous named consignee in the same file.

## Exports (exports/)

- `shipments_by_year.csv` — corpus is odd-year heavy (even years 1876–92 have <10 source files; volumes photographed every other year)
- `dest_commodity_year.csv`, `origin_commodity_year.csv` — shipment counts by port × commodity form × year
- `route_year.csv` — origin × destination × year counts
- `merchant_dest_year.csv` — named consignee × destination × year counts

Sanity check on all-years top pairs: London←deals, Liverpool←staves,
Cardiff←pitwood, Hartlepool (West)/Bo'ness←pit props — matches known trade
geography (cooperage in Liverpool, mining timber to coal ports).

## Known remaining issues / future work

1. **1877 LONDON aggregated format** (`Russia— 305 G. Russell & Co.`): country-level
   totals, no ships. Lines are classified AGGREGATED_DATA and currently skipped.
   A small dedicated parser could recover country→port commodity flows.
   (User has said NOT to work on this for now.)
2. **Residual unrescuable lines** (~3.7k records, 2.3%): ditto-mark departure
   tables (`Mobile ,, 7 Kentigern Liverpool`), vessels-loading tables
   (origin + date + ship + destination format), and separator-free lines whose
   ports aren't in the gazetteer. The gazetteer rescue (July 2026) recovered
   791 of the original 4.5k.
3. **Origin geocoding gap**: 84.4% of origins normalize but some lack
   coordinates; small Scandinavian loading places dominate the tail.
4. **Merchant surname-only forms**: "Love" (810) vs "Love & Stewart" (878)
   kept separate deliberately — merging truncated surnames into firms needs
   human/domain review (candidate list: reference_data/merchant_authority.json).
5. **Unmapped origin tail** (12.2%): mostly rare OCR variants; the earlier
   project found 95% coverage costs 40–60h of human review — accept and document.
6. Old parser and its output preserved in `scripts/parse_tabular.py` (unused)
   and `parsed_v1_backup/` for comparison; `parse_dense.py` was an LLM
   prototype, never used in production.

## File Inventory

```
timber_data/
├── CLAUDE.md / PROJECT_STATUS.md / QUICK_REFERENCE.md
├── scripts/
│   ├── parse_shipments.py          # unified parser (v2, all eras)
│   ├── deduplicate.py              # stage 2
│   ├── normalize_commodities.py    # stage 3
│   ├── normalize_merchants.py      # stage 3b
│   ├── build_port_authority.py     # stage 4a
│   ├── build_geocoding_db.py       # stage 4b
│   ├── normalize_ports.py          # stage 5
│   ├── generate_port_report.py     # stage 6a
│   ├── export_cargo_counts.py      # stage 6b
│   ├── build_knowledge_graph.py    # stage 7 (kg/)
│   ├── analysis/spot_check_parse.py  # raw-vs-parsed QA harness
│   └── parse_tabular.py, parse_dense.py, ...  # superseded (kept for provenance)
├── ocr_results/gemini_full/        # source OCR (do not modify)
├── classification/                 # LLM line labels (do not modify)
├── parsed/ → deduped/ → normalized/  # pipeline stages
├── parsed_v1_backup/               # pre-rebuild output (Jan 2026)
├── exports/                        # analysis-ready CSVs
├── kg/                             # knowledge graph (Ladybug DB + JSON + README)
├── reference_data/                 # authority + geocoding + reports
└── reports/                        # dedup + commodity + quality reports
```

## Version History

- **2026-07-07**: Trade-geography statistics (scripts/analysis/trade_geography_stats.py
  → reports/trade_geography/): partner-concentration null model, commodity LQs,
  route persistence, steam/sail split, seasonality. Doc-level `issue_date` added
  to parser output + backfilled into parsed/deduped/normalized
  (scripts/stamp_issue_dates.py, one-off).
- **2026-07-03 (c)**: Knowledge graph built (kg/): Ladybug DB `timber.lbdb`
  (~80 MB single file; 158,918 Shipment nodes, 613 Ports, ARRIVED_FROM/AT,
  CARRIED, CONSIGNED_TO, BY_SHIP, ROUTE rels) + aggregate `timber_kg.json`
  (16,450 nodes / 109,530 year-weighted edges). Fixed double-encoded UTF-8
  (GÃ¤vle→Gävle) and circular mappings (Gefle↔Gävle) inherited from
  ports_completed.csv.
- **2026-07-03 (b)**: Gazetteer rescue for separator-free/dock-list lines
  (791 records recovered); merchant normalization stage added
  (consignee_normalized/consignee_type, 1,481 exact + 318 fuzzy merges,
  merchant_authority.json); merchant_dest_year.csv export.
- **2026-07-03**: Parser rebuild (parse_shipments.py). Fixed 10 systematic bugs
  (see above). Junk cargo 27.9%→2.6%; origin coverage 70.3%→83.9%; destination
  92.1%; commodity controlled vocabulary added (92.7% classified); dedup stage;
  first cargo-count exports.
- **2026-01-19**: Initial pipeline (parse_tabular.py). 159,939 shipments,
  70.3%/88.4% port normalization. Superseded.
