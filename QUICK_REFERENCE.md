# TTJ Parsing - Quick Reference

## Run Classification
```bash
cd /home/jic823/timber_data
export GEMINI_API_KEY="your-key"
python3 scripts/classify_ocr.py
```

## Key Findings

1. **2,041 OCR files** spanning 1874-1900
2. **1877 LONDON uses aggregated format** (no individual ships)
3. **Classification accuracy verified** - works well across all eras
4. **Corrupted OCR lines** correctly flagged as UNCLEAR

## Format Patterns

### Dense (1874-1876)
```
April 17th. Ship (s) @ Port,—cargo, Merchant; cargo, Merchant.
```

### Tabular (1885-1900)
```
Dec. 24 Ship-Origin-cargo qty type-Merchant
```

## Classification Types
- SHIPPING_DATA - target data (ship arrivals)
- PORT_HEADER - LONDON, CARDIFF, etc.
- AGGREGATED_DATA - country-level totals (1877 LONDON)
- EDITORIAL, ADVERTISEMENT, BUSINESS_NEWS - skip
- UNCLEAR - OCR errors

## Validation Files
- `London Timber imports data ttj.xlsx` (1883: 5,403 | 1889: 5,831 | 1897: 5,435 rows)
- `Timber Trades Journal Data.xlsx` (Eng&Wales: 3,374 | Scotland: 697 ships)

## Output Locations
- Classifications: `/home/jic823/timber_data/classification/`
- Parsed data: `/home/jic823/timber_data/parsed/` (to create)
- Full docs: `/home/jic823/timber_data/PROJECT_STATUS.md`
- Plan: `/home/jic823/.claude/plans/luminous-wiggling-scott.md`
