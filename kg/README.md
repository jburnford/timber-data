# British Timber Trade Knowledge Graph, 1874–1900

A knowledge graph of ~159,000 timber shipment arrivals at British and Irish
ports, extracted from the weekly import lists of the *Timber Trades Journal*
(1874–1900). Built from hand-photographed page images, OCR'd with Gemini 2.5
Pro, and parsed/normalized with a deterministic Python pipeline.

## Files

| File | What it is |
|------|------------|
| `timber.lbdb` | [Ladybug](https://github.com/ladybugdb/ladybug) graph database (single file, ~80 MB) — full shipment-level graph, Cypher-queryable |
| `timber_kg.json` | Aggregate JSON graph (~16 MB): port/commodity/species/merchant nodes + year-weighted edges — for visualization or loading anywhere |

## Read this first: what the data supports

- **Edge weights are shipment counts.** OCR quantity digits are unreliable
  (validated at only 37.6% exact against human transcription; most errors are
  wrong in the *first* digit). Raw quantity strings are preserved on `CARRIED`
  edges for provenance, but **never sum them**.
- **Coverage is odd-year heavy.** Even years 1876–1892 are nearly absent
  (source volumes were photographed every other year). Use odd years for
  time series.
- **1877 LONDON** used an aggregated no-ship format that is not included.
- Ports, commodities, ship names, merchants, and dates are reliable
  (~93–97% accuracy against human transcription).

## Ladybug database schema

Node tables:

```
Port(name, lat, lon, shipments_out, shipments_in)   613 ports, geocoded where known
Ship(name, shipments)                               ~29k names
Merchant(name, shipments)                           ~15.7k canonical consignees
Commodity(form, shipments)                          ~60 product forms (deals, battens, pit props, ...)
Species(name, shipments)                            ~37 wood species (fir, oak, pitch pine, ...)
Shipment(record_id, year, arrival_date, arrival_iso, is_steamship,
         consignee_type, parse_confidence, origin_raw, destination_raw,
         source_file, line_number, raw_text)        158,918 records
```

Relationship tables:

```
(Shipment)-[ARRIVED_FROM]->(Port)                    normalized origins only
(Shipment)-[ARRIVED_AT]->(Port)
(Shipment)-[BY_SHIP]->(Ship)
(Shipment)-[CONSIGNED_TO]->(Merchant)                named consignees only
(Shipment)-[CARRIED {quantity, unit, item_raw}]->(Commodity)
(Shipment)-[CARRIED_SPECIES]->(Species)
(Port)-[ROUTE {year, shipments}]->(Port)             pre-aggregated origin→destination
```

`consignee_type` distinguishes `named` firms from cargo consigned `to order`
(~21% of shipments), to the ship's `master`, or `none`. Every Shipment keeps
its `raw_text` and source file/line so any edge can be checked against the OCR.

## Querying

```python
import ladybug  # pip install ladybug
db = ladybug.Database('timber.lbdb', read_only=True)
con = ladybug.Connection(db)
r = con.execute("MATCH (s:Shipment) RETURN count(s)")
print(r.get_next())
```

Who supplied Cardiff's pitwood? (French pit-prop trade)
```cypher
MATCH (s:Shipment)-[:ARRIVED_FROM]->(o:Port),
      (s)-[:ARRIVED_AT]->(:Port {name:'Cardiff'}),
      (s)-[:CARRIED]->(:Commodity {form:'pitwood'})
RETURN o.name, count(DISTINCT s) AS n ORDER BY n DESC LIMIT 10
-- Bordeaux 1636, Bayonne 375, Redon 201, ...
```

Which merchants received Quebec timber in London?
```cypher
MATCH (s:Shipment)-[:ARRIVED_FROM]->(:Port {name:'Quebec City'}),
      (s)-[:ARRIVED_AT]->(:Port {name:'London'}),
      (s)-[:CONSIGNED_TO]->(m:Merchant)
RETURN m.name, count(s) AS n ORDER BY n DESC LIMIT 10
-- Bryant, Powis, & Co. 25, Churchill & Sim 14, ...
```

Busiest routes in 1889:
```cypher
MATCH (o:Port)-[r:ROUTE]->(d:Port) WHERE r.year = 1889
RETURN o.name, d.name, r.shipments ORDER BY r.shipments DESC LIMIT 10
```

Rise of manufactured goods (doors):
```cypher
MATCH (s:Shipment)-[:CARRIED]->(:Commodity {form:'doors'})
RETURN s.year, count(DISTINCT s) ORDER BY s.year
```

A ship's career:
```cypher
MATCH (s:Shipment)-[:BY_SHIP]->(:Ship {name:'Fatfield'})
RETURN s.arrival_iso, s.origin_raw, s.destination_raw ORDER BY s.arrival_iso
```

## JSON graph format

`timber_kg.json`:

```json
{
  "meta":  { "title": "...", "shipments": 158918, "caveats": ["..."] },
  "nodes": [ {"id": "port:London", "type": "Port", "label": "London",
              "lat": 51.5, "lon": -0.1, "shipments_in": 24000, ...} ],
  "edges": [ {"source": "port:Quebec City", "target": "port:London",
              "type": "ROUTE", "year": 1885, "shipments": 42}, ... ]
}
```

Edge types: `ROUTE` (port→port), `IMPORTED` (destination→commodity),
`EXPORTED` (origin→commodity), `RECEIVED_AT` (merchant→destination port).
All carry `year` and `shipments`. Node ids are prefixed (`port:`, `commodity:`,
`species:`, `merchant:`) so the file loads directly into d3, Gephi (via a
converter), NetworkX, etc.

## Regenerating

Built by `scripts/build_knowledge_graph.py` from the normalization pipeline in
this repository (see the project `CLAUDE.md` for the full 6-stage pipeline).
Everything is deterministic — no LLM calls at build time.

## GitHub notes

`timber.lbdb` is ~80 MB — under GitHub's 100 MB hard limit but above the 50 MB
warning threshold. If the database grows, move it to
[Git LFS](https://git-lfs.com/) (`git lfs track "*.lbdb"`), or share only
`timber_kg.json` and let users rebuild the DB from the pipeline.

## Source & citation

Data transcribed from *The Timber Trades Journal* weekly "Imports" lists,
1874–1900. OCR: Google Gemini 2.5 Pro over hand-held photographs of bound
volumes (2025). Parsing/normalization pipeline: 2026. Please cite the journal
as the primary source; transcription errors are possible in any individual
record — check `raw_text` before relying on a single shipment.
