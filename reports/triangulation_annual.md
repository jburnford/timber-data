# Annual triangulation: official UK imports × TTJ × JHG (preliminary)

**2026-07-04.** First analysis joining the new annual official UK import
series (uk_trade_db Tier 2: Annual Statements country detail, double-keyed
OCR, grade-A/B verified cells, 1873–1898) with the TTJ shipment microdata
and the JHG-2022 Laurentian export volumes. Script:
`scripts/analysis/canada_annual_official.py`; data:
`exports/canada_annual_triangulation.csv`.

Until now the official quantities existed at 5 decennial anchors
(1861–1901). This adds the annual trajectory between them. "Clean" years
require every major origin (Canada, Sweden, Norway, Russia) to have both
hewn and sawn grade-A/B coverage: **1881, 1885, 1886, 1887, 1890, 1891,
1895**. Other years have a category or origin missing (pre-1877 sawn
labels, grade-C cells, the 1897+ category consolidation) and their shares
are not comparable.

## 1. The three sources agree — strongly

TTJ calibrated volume shares (shipment counts × cargo-size calibration,
built from an entirely independent source: trade-journal arrival lists)
against the official annual import shares, clean overlap years:

| year | official | TTJ calibrated | diff |
|------|---------|---------------|------|
| 1881 | 24.4% | 23.5% | −1.0pp |
| 1885 | 21.2% | 20.2% | −1.1pp |
| 1887 | 18.9% | 18.8% | −0.2pp |
| 1891 | 15.8% | 15.8% | −0.0pp |
| 1895 | 18.0% | 17.3% | −0.7pp |

**MAE 0.6 percentage points.** The prior calibration was validated against
JHG (MAE 2.9pp); against the official annual customs series it is
essentially within measurement error. Customs returns and trade-journal
shipping lists are independent records of the same flows — this
cross-validates both.

## 2. Decline without collapse, now annual

Canada's share of UK hewn+sawn imports (clean years): 24.4% (1881) →
21.2 → 20.4 → 18.9 → 19.4 → 15.8 (1891) → 18.0% (1895). Consistent with
the decennial anchors (45% in 1861 → ~17% by 1901) but showing the fall
was gradual and partly cyclical (1891 dip, 1895 recovery — the TTJ series
shows the same wiggle).

Absolute volumes tell the composition story:

| | 1881 | 1885 | 1887 | 1890 | 1891 | 1895 |
|---|---|---|---|---|---|---|
| Canada hewn (k loads) | 303 | 200 | 165 | 180 | 152 | 124 |
| Canada sawn (k loads) | 999 | 1,000 | 872 | 1,186 | 891 | 1,171 |
| sawn share of Canada's exports | 77% | 83% | 84% | 87% | 85% | 90% |

Hewn (square) timber more than halves; sawn holds ~0.9–1.2M loads. The
"decline" is entirely the square-timber category dying — Canada's sawn
trade to the UK did not decline at all in this window. Sweden meanwhile
holds 25–28% and Russia 21–26% throughout: Canada lost share to no single
rival; the market grew (UK totals 5.3M → 7.2M loads 1881→1895) and Canada
didn't grow with it.

## 3. JHG reconciliation, annual: the Laurentian share of BNA sawn ROSE

JHG-2022 covers Laurentian (Quebec/Montreal) exports only. Annual ratio of
JHG sawn to official BNA sawn (Canada-clean years):

1881: 0.35 · 1883: 0.34 · 1885: 0.38 · 1886: 0.40 · 1887: 0.37 ·
1889: 0.34 · 1890: 0.44 · 1891: 0.36 · 1895: 0.40

The static "~35%" reconciliation from the decennial work holds, and the
annual series adds a trend: the Laurentian share of BNA sawn drifts up
from ~34–35% to ~40–44% by 1890/1895 — independent confirmation of the
TTJ port-decomposition finding (Montreal 1%→40% of Canadian shipments,
steam deal liners) that the sawn trade was consolidating on the St
Lawrence while the Maritimes' share slipped.

Square timber: JHG square ≈ official BNA hewn at ratio ≈ 1.0 annually
(0.997–1.28). **Caveat for Jim**: several years match at exactly 1.000,
which suggests the JHG square series and the UK official hewn series
share a source for those years (Fig 3 built partly from UK trade
returns?). If so this row is a consistency check, not an independent one
— worth confirming against the JHG paper's source notes.

## 4. Data-quality notes / what would improve this

- Clean years are limited by specific recoverable gaps, not general noise:
  **Canada's sawn cells for 1889, 1892–94, 1896–98 are the single
  highest-value review items** in
  `~/uk_trade_db/reports/country_review_queue.csv` — clearing ~20 cells
  would roughly double the clean-year count.
- Pre-1877 sawn sits under bare-"Fir" labels awaiting block-context
  assignment (262 rows, in the wood map review file). Recovering it would
  extend the annual series back to 1873.
- 1897–99 need the late-era layout pass (category consolidation +
  dictionary format).
- All official values here are grade-A/B (block-arithmetic-proven or
  cross-engine agreed); grade-C cells are excluded, never interpolated.

## Verdict

Three independently constructed datasets — customs quantities, trade-press
shipping lists, and Canadian export records — now agree on the shape of
Canada's late-Victorian timber trade at annual resolution: a halving of
share driven almost entirely by square timber's disappearance, stable
absolute sawn volumes concentrated increasingly on the St Lawrence, in a
growing market increasingly supplied by a stable Baltic duopoly.
