# Market Structure of the UK Timber Import Trade, 1874–1899 (TTJ)

*Generated 2026-07-03. Script: `scripts/analysis/market_structure.py`.
Companion to `canada_statistical_analysis.md`. Shipment counts only; shares
within year.*

## A. The value-added transition

Share of all shipments carrying finished wood goods (doors, mouldings,
joinery, flooring, matchboards, woodware, handles, oars, bobbins, trellis):
**1.6–1.8% (1874–75) → 6.1% (1899)** — a steady climb through the whole
period. Components (staves, headings, shooks, hoops, spokes) peaked at
17–19% mid-1880s and fell back to ~11%.

Who moved up the value chain (finished share of own shipments, 1874 → 1899):
- **USA: 7% → 20.5%** — the clear leader; handles (428 late-period
  shipments), doors (381), mouldings, oars.
- **Sweden: 4% → 6–8%** — doors (555), mouldings (473), joinery (135),
  trellis (134), woodware; the widest finished portfolio.
- **Norway: 2% → 8%** — dominates planed flooring (623 of 1,013 late
  flooring shipments).
- **Germany: ~0% → 5–14%** — mouldings specialist (248 late shipments).
- **Canada: 0.6% → 5.5%** — a late riser, from a near-zero base.
- **Russia: never above 1.5%** — remained a pure commodity supplier
  (deals, battens, sleepers, lathwood) to the end.

## B. The American trade by sub-region

US share of all mapped shipments: 6–7.6% (1874–75) → 11–15% (1880s–90s),
peaking 1891. The apparent 1879 collapse (1.5%) is largely a
venue-coverage artifact (see caveat below). Within the US trade:

| | 1874–75 | 1887–99 |
|---|---|---|
| Northeast (NY, Boston, Baltimore, Phila.) | ~46% | 61–70% |
| Gulf (Pensacola, Mobile, N.O.) | 36–40% | 21–26% |
| South Atlantic (Savannah, Darien, ...) | 13–18% | 7–12% |

Profiles: Northeast = **staves 57%**, lumber 26%, hardwood logs (walnut),
handles, doors; South Atlantic & Gulf = pitch-pine deals and hewn timber.
NE port shifts: New York 61%→49%, Boston 19%→23%, Baltimore 10%→17%.

**Rise and decline within the Northeast**: the stave (cooperage) trade
carried the boom — 36–44% of NE shipments in 1874–75, peaking at **70–75%
in 1883–89, then falling to 40–48% in the 1890s** (consistent with bulk
oil transport displacing the barrel trade). Handles spike 1885–89 (10–13%)
then fade. What replaced staves: sawn lumber (12% → 45% of NE shipments by
1897–99), doors (10–12% in 1897–99), and a persistent walnut-log trade
(~15–20% of NE shipments from 1881). Baltimore's rise tracks the
walnut/oak hardwood trade.

Portland, Maine (n=254, deals/lumber-dominated) is the Grand Trunk winter
outlet for Canadian product — a small but conceptually important
contamination of "US" totals.

## C. European competition

Commodity-profile shifts (share of own shipments, early → late):
- **Sweden**: deals 44%→32%, pit props 23%→**32%**, battens ~30%, boards
  17%→22% — diversified into pitwood while holding sawn.
- **Russia**: deals 49%→44%, battens 16%→**28%**, sleepers, lathwood — grew
  inside the bulk-sawn segments.
- **Norway**: pit props 38%→34%, boards 15%→19%, flooring niche — the
  small-cargo/short-sea specialist (lowest loads-per-shipment weight, 0.55).
- **Germany**: sleepers 20%→18%, staves, hewn timber, + new pit props (16%)
  and mouldings (5%) — the railway/cooperage niche, distinct from everyone.
- Profile convergence (cosine similarity early→late): Sweden–Russia
  0.76→0.83, Sweden–Norway 0.72→0.84, Russia–Finland 0.81→0.89 — the
  northern European suppliers **converged** on similar commodity mixes,
  while **Sweden–Canada diverged (0.73→0.62)**: Canada differentiated
  (deals specialization) rather than compete across the board.

**Two-coast market segmentation** (late-period destination mix): the Baltic
suppliers ship overwhelmingly to the east coast (Sweden 67% to
English+Scottish east coast; Russia 66%, Finland 67%, Germany 67%), while
the Atlantic suppliers own the west: Canada 47% to Mersey+Clyde plus 16%
Ireland; USA 60% Mersey+Clyde. France is a one-segment supplier: 86%
Bristol Channel (pit props for the coalfields). The UK was two largely
separate markets joined at London.

Segment head-to-heads (share of segment shipments):
- **London deals**: Sweden 30–40% throughout; Canada holds 13–25% with no
  downward trend — London was Canada's defended metropolitan market;
  Russia surges mid-1880s (26% in 1885–91) then eases.
- **Bristol Channel pitwood**: France 69–82% dominant all period; Norway
  5–10%; Sweden entering late (0.6%→5.5%).
- **East-coast boards+battens**: Sweden slips 40–44%→31%, **Russia rises
  13→24–25%** — this, plus battens, is where Russian expansion actually
  happened; Finland steady 10–15%.

## Venue-coverage caveat (affects all cross-year share comparisons)

Destination coverage varies by year: Cardiff is essentially absent from the
1874–75 volumes (France's raw share jumps 0.5%→10.4% in 1879 purely as
Cardiff enters), and 1879 under-covers Liverpool (6% of records vs 9–12%)
while over-covering London (21%). Because supplier countries are strongly
coast-segmented, this venue mix contaminates raw year-to-year country
shares. Fixed-venue-mix reweighting (country shares computed within each
destination coast, averaged with pooled coast weights) shows:

- Canada: raw 15.1/15.1/12.6/10.6% (1874/75/79/81) becomes
  **16.7/15.7/16.4/10.6%** — Canada's count share was *stable through
  1879* and fell sharply between 1879 and 1881, matching the 1877
  structural break in the square-timber series (decline visible after the
  1878–79 trade trough, in the 1880–81 boom that Canada did not share).
- France's "absence" before 1879 is entirely venue coverage.

Recommendation: for any published year-over-year share series from the TTJ,
use venue-reweighted (or at minimum coast-stratified) shares; raw shares
are fine within a single year.

## Follow-ups worth doing

1. Venue-reweighted versions of the calibrated country-share series
   (combine the two corrections).
2. Stave trade deep-dive: NE staves by destination (Liverpool cooperage,
   petroleum barrels) and the 1890s decline; German vs American staves.
3. Doors/mouldings destination analysis: which UK cities imported
   American vs Swedish joinery (building-boom geography).
4. Walnut: Baltimore/NY logs as the furniture-veneer trade; exhaustion
   timing.
