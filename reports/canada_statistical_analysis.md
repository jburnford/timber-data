# Canada in the UK Timber Trade, 1809–1901: Statistical Analysis

*Generated 2026-07-03. Scripts: `scripts/analysis/canada_country_analysis.py`,
`canada_breakpoints.py`, `canada_ttj_phase2.py`. All deterministic and
re-runnable.*

## Question

Canada lost its position as Britain's top timber supplier after the end of
colonial preference and reciprocity in the 1860s, yet its exports did not
collapse. What happened instead, when, and through what mechanism?

## Data

| Source | Period | Resolution | Role |
|---|---|---|---|
| JHG 2022 article data (Figs 2–4; Zenodo 10.5281/zenodo.6324227) | 1809–1900 | annual; **Laurentian Valley only** (Quebec/Montreal exports, excl. NB/NS); Fig 3 = square vs sawn | long-run timing |
| UK Gov "Full British Imports Database" | 1861–1901 | decennial, loads + £ by country | level anchor |
| TTJ microdata (this pipeline) | 1874–1899 (13 valid years) | shipment-level: port, commodity, destination, steam | mechanism |

TTJ quantities are untrustworthy (OCR); the unit of analysis is the
**shipment count**. Counts are comparable across years only as within-year
shares. Uncertainty is estimated by **cluster bootstrap over journal issues**
(shipments within an issue are correlated).

## Headline findings

### 1. No collapse — a flat line hiding two crossing curves

Official Canada → UK timber, 50-cu-ft loads:

| | 1861 | 1871 | 1881 | 1891 | 1901 |
|---|---|---|---|---|---|
| share of UK imports | 45.2% | 26.1% | 23.1% | 15.5% | 17.5% |
| absolute loads | 1.52M | 1.20M | 1.31M | 1.05M | 1.61M |
| hewn (square) loads | 628k | 463k | 303k | 152k | 89k |
| sawn loads | 850k | 710k | 999k | 891k | 1,517k |
| sawn share | 57.5% | 60.5% | 76.7% | 85.4% | 94.5% |

Canada's aggregate volume was flat while the UK market grew 2.7×; within
that flat total, square timber fell 86% and sawn lumber grew 79%.

### 2. Break dates (piecewise-linear segmented regression, BIC-selected, on JHG Fig 3 — the Laurentian trade)

**Square timber** — breaks at 1830, 1854, **1865**, **1877** (1%-SSR
confidence sets are ±0–2 years):
growth accelerating to +1.28M cu ft/yr in 1855–65 → **growth stops dead in
1865** (end of Reciprocity era) → plateau 1866–77 → **sustained decline from
1877** (−0.46M cu ft/yr). The end of preference stopped growth; the actual
collapse began a decade later, with the post-1873 depression.

**Sawn lumber** — breaks at **1842** [1841–42] and **1890** [1890]:
takeoff coincides with Peel's 1842 tariff reductions; slope triples after
1890 (+2.17M cu ft/yr), peaking in 1899 (highest Canadian volume of any
product in the century).

**Total** — breaks at 1865 and 1885 [1885–92]: rise, twenty-year stagnation,
renewed growth. "Decline" is the wrong word for the aggregate; it was a
twenty-year pause during product transition.

### 3. TTJ validation: the microdata track the official series

- Species-aware square-vs-sawn classification (forms + hardwood/waney
  species): TTJ square count-share ≈ official hewn volume-share at the 1881
  anchor (24.4% vs 23.3%), detrended annual correlation r = 0.89 with the
  JHG series at the all-Canada level — improved to **r = 0.90 on the
  matched Laurentian-only population** (see the Laurentian section below).
- Late-period divergence (TTJ square share stays ~24% while official volume
  share falls to ~6%) is expected: liner-era mixed cargoes include small
  hardwood parcels that count as "square" shipments but carry little volume.

### 4. Calibrated annual volume shares, 1874–1899

Count shares are biased against Canada because Canadian cargoes were large
(count-to-volume weight ≈ 2.0–2.3, i.e. **the average Canadian cargo carried
roughly twice the trade-wide average, ~3–4× a Norwegian one**). Reweighting
count shares by country loads-per-shipment at the 1881/1891/1901 anchors
(interpolated between, Finland merged into Russia as in official statistics)
gives annual volume-share estimates. Validation against the JHG annual
Canada series: **MAE 2.9 percentage points** (raw counts: 12.1), detrended
r = 0.79. Output: `exports/country_shares_calibrated.csv`.

Calibrated Canada share: ~32% (1874) → ~23% (1881–83) → 16–20% (1890s).
The trend is statistically significant in count terms: −3.2 pp/decade
(95% CI −4.6 to −1.8) over 1874–99; still negative at −1.5 pp/decade
(CI −2.6 to −0.4, P(decline) = 0.99) over 1879–99.

Divergence note: JHG Fig 3 shows a strong 1897–99 boom (Canada implied
27–28%) that the calibration (anchored to official 1901 = 18%) misses —
consistent with 1899 being a genuine one-year peak.

### 5. The mechanism: the trade moved from Quebec to Montreal

Share of Canadian shipments by origin port (TTJ):

| year | Quebec City | Montreal | St. John | Miramichi | Halifax |
|---|---|---|---|---|---|
| 1874 | 56% | 1% | 14% | 6% | 2% |
| 1885 | 35% | 16% | 15% | 8% | 2% |
| 1899 | 12% | 40% | 11% | 8% | 7% |

Port profiles (pooled): Quebec = square timber (39–46% of classified
shipments), sail-dominated (steam 9% → 19%). Montreal = deals on steam
liners (steam 72–77%), heavily to Liverpool (34–37%). Saint John and
Miramichi = stable sawn-deal ports, Saint John converting to steam
(8% → 26%). Canada's aggregate steam share went 7% (1874) → 48% (1899),
overtaking Sweden (~32%) by 1893 — the old sail/square/Quebec staple was
replaced by a steam/deals/Montreal trade, not merely reduced.

### 6. Seasonality: real, and not a coverage artifact

Canada's share of dated arrivals by month: 2–3% Jan–May, 9% Jun, 16%
Jul–Aug, 13–14% Sep–Nov, 10% Dec — the St. Lawrence ice season, cleanly.
Reweighting each year's records by the pooled month-specific Canada share
shows annual shares are not driven by which issues were photographed:
actual ≈ expected within ~1 pp for most years. Exceptions are informative:
1874 ran 4.8 pp *above* its month-mix expectation (a real Canadian peak)
and 1891 ran 2.4 pp *below* (a real dip — coincides with the 1890–91
financial crisis), so the 1891 low is only partly explained by coverage.

## Coverage reconciliation (JHG vs Board of Trade)

Resolved after reading Clifford & Castonguay (2022), pp. 128, 131–132: the
JHG figures cover the **Laurentian Valley only** — exports via the Ports of
Quebec and Montreal, built from Canadian export records (GSE-TTN 1809–1889,
harbour commissioners 1890–1900), with New Brunswick and Nova Scotia
explicitly excluded, and piece-counts converted to cubic feet by product
dimensions (deals ~2.2–2.8 cu ft/piece; square timber per cullers' accounts).
The Board of Trade "British North America" rows include NB/NS.

The two reconcile cleanly: Fig 3 square ≈ official BNA hewn × 50 cu ft
(1881: 302,822 loads ↔ 15.12M cu ft) because square timber was almost
entirely a Quebec trade; Fig 3 sawn ≈ 35% of official BNA sawn cu ft (stable
at 34.8%/35.8% in 1881/1891) because Saint John, Miramichi and the other
Maritime ports shipped roughly two-thirds of BNA sawn volume. So:
**within the Laurentian trade** the sawn share crossed 50% around 1879
(JHG Fig 3), while for **BNA as a whole** — Maritime deals included — sawn
was already 77% by 1881 (official loads). Both statements are correct for
their populations. The calibration's Fig 3 rescaling factor (17.6 cu ft per
official sawn load) is therefore not a unit conversion but an implicit
assumption that the Laurentian share of BNA sawn volume was constant —
which the two anchors support.

## Laurentian-only validation and the spruce transition
(`canada_laurentian.py`)

Restricting the TTJ to Laurentian origins (Quebec City, Montreal,
Trois-Rivières, Saguenay/Gaspé/Lower-St-Lawrence outports — 6,462 of 11,837
Canadian shipments; the TTJ's Canada is ~55% Laurentian, ~45% Maritimes,
stable across years) and comparing square-vs-sawn mix with JHG Fig 3 — now
the same population — gives **detrended annual correlation r = 0.90**. The
TTJ reproduces the JHG series' year-to-year swings. Level paths differ in a
diagnostic way: mid-period they coincide (1887–91: TTJ 31–36% vs Fig 3
32–35%), early years Fig 3 is higher (square cargoes carried several times
the volume of deal cargoes, so count-shares understate square volume), late
years Fig 3 is lower (residual "square" shipments are increasingly small
hardwood parcels on Montreal liners).

The paper reports spruce averaging ~40% of the Canadian deal trade in the
last quarter of the century as logging moved to the spruce forests of the
Saguenay, St-Maurice and Lower St. Lawrence. The TTJ species mentions
(stated on 16% of Canadian deal shipments — selection caveat) show exactly
this transition, with timing: Laurentian deal shipments mentioning spruce
rose from 24–29% (1874–75) to ~40% (1883–85), 55–58% (1887–93), and 66–70%
(1895–99), crossing pine around 1895. Maritime deals were spruce-dominated
throughout (86–100%), consistent with New Brunswick's spruce economy — the
pine→spruce transition is specifically a Laurentian story.

## Caveats

- 79.8% of TTJ shipments map to the eight focus countries; unmapped tail is
  mostly genuinely-other trade (Netherlands entrepôt, Burma teak, mahogany).
  Shares are computed on mapped origins.
- 1874–75 use the @-format parse and different venue coverage; the trend
  test is reported with and without them.
- Calibration weights are interpolated between three anchors and held flat
  before 1881; they absorb both cargo-size and any venue-coverage bias, and
  cannot capture year-to-year cargo-size changes (see 1897–99 divergence).
- Loads-per-shipment weights conflate vessel size with cargo composition;
  they are calibration factors, not direct measurements of ship size.

## Next steps (optional)

1. Add calibrated country-share and Quebec→Montreal panels to the
   visualization site.
2. Merchant-level analysis: did Quebec square-timber consignees exit or
   follow the trade to Montreal? (`merchant_dest_year.csv` +
   `normalize_merchants.py` output.)
3. Destination-mix shift-share: how much of Canada's decline is UK demand
   composition (fewer square-timber-using ports) vs within-port share loss.
