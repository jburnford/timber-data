# Timber Trades Journal Parsing Project - Status Document

**Last Updated**: January 14, 2026
**Project Location**: `/home/jic823/timber_data/`

## Project Goal

Extract structured shipping import data from OCR'd Timber Trades Journal (1874-1900) using LLM-guided classification followed by deterministic Python parsing.

## Key Approach

**LLM for LOCATION, Python for EXTRACTION**:
1. Use Gemini 3 Flash to classify each line (SHIPPING_DATA, EDITORIAL, etc.)
2. Use Python parsers to extract structured data from classified shipping lines
3. This avoids hallucination - LLM never generates/transcribes content

## Data Overview

### Source Files
- **Location**: `/home/jic823/timber_data/ocr_results/gemini_full/`
- **Count**: 2,041 OCR files (txt + json pairs)
- **Years**: 1874-1900 (26 years)
- **Source**: Timber Trades Journal (British trade publication)

### File Counts by Year
| Year | Files | Year | Files | Year | Files |
|------|-------|------|-------|------|-------|
| 1874 | 57 | 1881 | 124 | 1891 | 179 |
| 1875 | 63 | 1882 | 2 | 1892 | 15 |
| 1876 | 2 | 1883 | 153 | 1893 | 171 |
| 1877 | 84 | 1884 | 9 | 1895 | 166 |
| 1878 | 2 | 1885 | 141 | 1896 | 7 |
| 1879 | 43 | 1886 | 4 | 1897 | 197 |
| 1880 | 3 | 1887 | 130 | 1898 | 20 |
| | | 1888 | 4 | 1899 | 237 |
| | | 1889 | 203 | 1900 | 16 |
| | | 1890 | 9 | | |

### Format Eras

| Era | Years | Format Description |
|-----|-------|-------------------|
| **Dense** | 1874-1876 | Multiple ships per paragraph, semicolon-separated cargo |
| **Transitional** | 1877-1884 | Mix of dense and line-per-ship |
| **Tabular** | 1885-1900 | One ship per line, clear port sections |

### Critical Finding: 1877 LONDON

**LONDON port uses AGGREGATED format in 1877** - no individual ship names:
```
LONDON.—From December 21st, 1876, to January 3rd, 1877.
Hewn Timber (loads).
Russia— 305 G. Russell & Co.
Prussia— 528 P. Rolt & Co.
```

Other ports (BRISTOL, LIVERPOOL, NEWCASTLE) still have individual ships in 1877.

## Validation Data

### Human-Produced Reference Files

**File 1**: `London Timber imports data ttj.xlsx`
| Sheet | Rows | Notes |
|-------|------|-------|
| London imports 1883 | 5,403 | Cargo-level records |
| Lon imp. 1889 | 5,831 | Cargo-level records |
| Lon imp.1897 | 5,435 | Cargo-level records |

**File 2**: `Timber Trades Journal Data.xlsx`
| Sheet | Rows | Notes |
|-------|------|-------|
| England & Wales | 3,374 | Ship arrivals |
| Scotland | 697 | Ship arrivals |
| Canada | 995 | Ships from Canada |

**Important**: Reference data has one row per commodity per ship (not per ship).
Some sheets focus on Quebec season only - may miss European ships.

## Classification Pipeline

### Script Location
`/home/jic823/timber_data/scripts/classify_ocr.py`

### LLM Configuration
- **Model**: Gemini 3 Flash Preview (`gemini-2.0-flash` in code)
- **API Key**: Stored in environment variable `GEMINI_API_KEY`

### Classification Types
| Type | Description | Example |
|------|-------------|---------|
| SHIPPING_DATA | Ship arrivals with cargo | `Dec. 24 Cleveland-Mobile-474 pcs. hewn pitch pine...` |
| PORT_HEADER | British port names | `LONDON`, `CARDIFF`, `HULL` |
| DOCK_HEADER | Sub-locations | `SURREY COMMERCIAL DOCKS`, `MILLWALL DOCKS` |
| EDITORIAL | Market commentary | Correspondent reports, trade analysis |
| ADVERTISEMENT | Product/service ads | Company listings, price lists |
| STATISTICAL | Numerical tables | Stock statistics, comparative figures |
| BUSINESS_NEWS | Bankruptcy notices | `GAZETTE`, `FAILURES` |
| PAGE_MARKER | Headers/footers | `THE TIMBER TRADES JOURNAL`, page numbers |
| AGGREGATED_DATA | Country-level totals | `Russia— 305 G. Russell & Co.` |
| BLANK | Empty lines | |
| UNCLEAR | Cannot determine | OCR errors, corrupted text |

### Classification Test Results (9 samples)

| File | Year | SHIPPING_DATA | AGGREGATED | PORT_HEADER | Notes |
|------|------|---------------|------------|-------------|-------|
| May 1 1875 | 1875 | 9 | 0 | 4 | Mixed editorial |
| Dec 11 1875 | 1875 | 1 | 125 | 3 | Statistical page |
| Aug 21 1875 | 1875 | 66 | 0 | 2 | Good coverage |
| Jan 6 1877 | 1877 | 0 | 101 | 5 | **LONDON aggregated** |
| Dec 22 1877 | 1877 | 0 | 0 | 0 | Minimal content |
| Aug 18 1877 | 1877 | 36 | 0 | 7 | Individual ships |
| Jan 3 1885 | 1885 | 133 | 0 | 25 | Excellent coverage |
| Nov 12 1887 | 1887 | 138 | 0 | 19 | Excellent coverage |
| Jul 25 1885 | 1885 | 85 | 0 | 16 | Mixed with gazette |

### Classification Accuracy Spot-Checks

**1885 January file (tabular era)** - Line-by-line verification:
```
Line 1: "JANUARY 3, 1885.] THE TIMBER TRADES JOURNAL" → PAGE_MARKER ✓
Line 3: "IMPORTS." → PORT_HEADER ✓
Line 8: "BARROW-IN-FURNESS." → PORT_HEADER ✓
Line 9: "Dec. 24 Cleveland-Mobile-474 pcs..." → SHIPPING_DATA ✓
Line 10: "BRIDGWATER." → PORT_HEADER ✓
Line 11: "Dec. 29 Fauna-Charlotte Town-16 lds..." → SHIPPING_DATA ✓
```
**Result**: 100% accuracy on verified lines.

**1875 August file (dense era)** - Correctly handles:
- Dense ship entries with dates
- Port headers (GLASGOW, GREENOCK)
- "Shipping Intelligence" section (Sound List) - flagged as different

**1885 July file** - Corrupted OCR (`[?]` markers):
- Lines 260+ correctly flagged as UNCLEAR
- These are garbled creditor names from bankruptcy section

## Directory Structure

```
/home/jic823/timber_data/
├── ocr_results/
│   ├── gemini_full/          # 2,041 OCR files (source)
│   ├── combined_full/        # Consolidated text
│   └── hybrid_recovery/      # Multi-model OCR
├── classification/           # LLM classification output (JSON)
├── parsed/                   # Extracted data (to be created)
├── scripts/
│   ├── assess_data_completeness.py
│   └── classify_ocr.py
├── data_completeness_report.json
├── London Timber imports data ttj.xlsx
├── Timber Trades Journal Data.xlsx
└── PROJECT_STATUS.md         # This file
```

## Tokenization Prototype Results

**Script**: `/home/jic823/timber_data/scripts/prototype_tokenizer.py`

Tested LLM-guided tokenization on 3 dense-format lines from 1875:

| Test | Ships | Cargo Items | Token Accuracy | Editorial Detected |
|------|-------|-------------|----------------|-------------------|
| Line 1 | 2 | 5 | 100% (24/24) | Yes (date) |
| Line 2 | 2 | 6 | 100% (28/28) | Yes (date) |
| Line 3 | 2 | 2 | 100% (12/12) | Yes (date + commentary) |

**Key Findings**:
- All extracted tokens exist VERBATIM in original text (no hallucinations)
- Multi-ship lines correctly parsed
- Editorial content correctly flagged as unparseable
- "Order" merchants handled correctly

**Sample Output** (Line 3):
```
Ships found: 2
Unparseable: ['April 20.', 'A quantity of sapanwood was brought to the docks...']

Ship 1: Caroline @ Gothenburg → 1,135 doz. deals → Order
Ship 2: Neptionus @ Sannesund → 151 t. firewood → Order
```

## Next Steps

1. **Full Classification Run**: Process all 2,041 files with Gemini
2. **Parser Development**:
   - Parser A: Dense format (1874-1876) - use tokenization approach
   - Parser B: Transitional (1877-1884)
   - Parser C: Tabular (1885-1900)
   - Parser D: Aggregated data (1877 LONDON-style)
3. **Extraction & Validation**: Compare to reference data
4. **Iterative Refinement**: Fix errors, re-run problematic files

## Key Technical Notes

### Shipping Data Patterns

**1874-1876 (Dense)**:
```
April 17th. Primrose (s) @ Riga,—5,555 sleepers, Order. Christiana @ Drammen,—146 doz. battens, C. J. Im Thurn & Co.
```
- Multiple ships per paragraph
- `@` separates ship from origin port
- `,—` separates port from cargo
- `;` separates cargo items
- Merchant name at end of each ship's cargo

**1885-1900 (Tabular)**:
```
Dec. 24 Cleveland-Mobile-474 pcs. hewn pitch pine, 219 pcs. sawn pitch pine-Price, Potter, & Co.
```
- One ship per line
- `-` or `—` separates fields
- Format: Date Ship-Origin-Cargo-Merchant

### Common Abbreviations
| Abbrev | Meaning |
|--------|---------|
| pcs. | pieces |
| doz. | dozens |
| fms. | fathoms |
| lds. | loads |
| bdls. | bundles |
| stds. | standards |
| (s) | steamship |

### Port Names
Major British ports in data: LONDON, LIVERPOOL, HULL, BRISTOL, CARDIFF, GLASGOW, NEWCASTLE, GRIMSBY, SUNDERLAND, LEITH, NEWPORT, SWANSEA, HARTLEPOOL, GOOLE, MIDDLESBROUGH, TYNE, SOUTHAMPTON, GRANGEMOUTH, GREENOCK, DUNDEE, BO'NESS, BARROW, GLOUCESTER

## API Configuration

```bash
# Set API key (never commit to git)
export GEMINI_API_KEY="your-key-here"

# Run classification
cd /home/jic823/timber_data
python3 scripts/classify_ocr.py
```

## Files Created This Session

1. `/home/jic823/timber_data/scripts/assess_data_completeness.py` - Data survey script
2. `/home/jic823/timber_data/scripts/classify_ocr.py` - LLM classification script
3. `/home/jic823/timber_data/scripts/prototype_tokenizer.py` - LLM tokenization prototype (100% verified)
4. `/home/jic823/timber_data/data_completeness_report.json` - Year-by-year analysis
5. `/home/jic823/timber_data/classification/*.json` - 9 sample classification results
6. `/home/jic823/timber_data/PROJECT_STATUS.md` - This documentation

## Plan File

Full implementation plan saved at:
`/home/jic823/.claude/plans/luminous-wiggling-scott.md`
