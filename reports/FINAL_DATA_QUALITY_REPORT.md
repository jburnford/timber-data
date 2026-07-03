# Timber Shipment Data Quality Report

**Generated**: 2026-01-19 16:37:23
**Total Files**: 2,039
**Total Shipments**: 159,939

## Executive Summary

| Issue Category | Count | % of Total | Priority |
|----------------|-------|------------|----------|
| Missing units | 276,823 | 173.1% | LOW |
| Quantity anomalies | 128,152 | 80.1% | LOW |
| Headers as ports | 27,065 | 16.9% | MEDIUM |
| Empty origin ports | 25,631 | 16.0% | HIGH |
| Cargo in ship_name | 16,959 | 10.6% | MEDIUM |
| Empty cargo arrays | 9,182 | 5.7% | HIGH |
| Truncated ports | 8,424 | 5.3% | MEDIUM |
| Exact duplicate records | 7,783 | 4.9% | HIGH |
| Hallucination loops | 5,381 | 3.4% | HIGH |
| Port+cargo combined | 4,437 | 2.8% | MEDIUM |
| Low confidence records | 936 | 0.6% | HIGH |

## 1. Parse Confidence Distribution

| Confidence | Count | Percentage |
|------------|-------|------------|
| High | 149,792 | 93.7% |
| Medium | 9,211 | 5.8% |
| Low | 936 | 0.6% |
| Unknown | 0 | 0.0% |

## 2. Empty/Missing Fields

| Field | Count | Percentage |
|-------|-------|------------|
| arrival_date | 119,899 | 75.0% |
| origin_port | 25,631 | 16.0% |
| cargo | 9,182 | 5.7% |
| consignee | 7,954 | 5.0% |
| ship_name | 808 | 0.5% |

## 3. Duplicate Records

- **Exact duplicates**: 7,783 records
- **Key duplicates** (same ship+date+port): 332 records
- **Hallucination loops** (5+ repetitions): 360 incidents (5,381 records)
- **Files affected**: 423

### Top Hallucination Loops

| File | Raw Text (truncated) | Count |
|------|----------------------|-------|
| 22. p. 535-537 - Imports - November 26 1 | 185 lds. deals-Short Bros. ;... | 893 |
| 10. p. 100-103 - Imports - August 8 1885 | Preussen-Dram-23,280 firewood-firewood-Churchill & Sim ; 4,1... | 85 |
| 10. p. 100-103 - Imports - August 8 1885 | July 30 Mayfield (s)-Cronstadt-8,666 pcs. lathwood, 969 rick... | 85 |
| 10. p. 100-103 - Imports - August 8 1885 | 31 Carmona (s) - Montreal - 24,407 deals-Bryant, Powis, & Br... | 85 |
| 10. p. 100-103 - Imports - August 8 1885 | Presto (s)-Soderhamn-11 fms. firewood-Order... | 85 |
| 10. p. 100-103 - Imports - August 8 1885 | Bjorn (s)-Gothenburg-3,500 bdls. laths-Churchill & Sim ; 180... | 85 |
| 10. p. 100-103 - Imports - August 8 1885 | Bifrost (s)-Christiania-8,084 boards-Nicks & Penton ; 372,24... | 85 |
| 10. p. 100-103 - Imports - August 8 1885 | Aug. 1 Zealous (s)-Finklippan-48,951 deals and battens-G. Lo... | 85 |
| 10. p. 100-103 - Imports - August 8 1885 | Benbrack (s)-Pierreville and Quebec-34,398 deals and ends-Br... | 85 |
| 10. p. 100-103 - Imports - August 8 1885 | Presto (s)-Soderhamn-11 fms. firewood, 26,997 deals-Foy & Co... | 85 |

## 4. Port Parsing Errors

- **Port+cargo combined**: 4,437
- **Truncated ports**: 8,424
- **Headers as ports**: 27,065
- **OCR variants detected**: 37,156

### Top Port+Cargo Combined Patterns

| Pattern | Count |
|---------|-------|
| Cronstadt-lathwood | 105 |
| Quebec-deals, &c. | 101 |
| Riga-sleepers | 95 |
| Gefle-deals, &c. | 86 |
| Archangel-deals, &c. | 66 |
| Archangel-deals | 55 |
| St. John-deals, &c. | 54 |
| Cronstadt-deals | 45 |
| Riga-deals | 44 |
| Riga-lathwood | 43 |
| Cronstadt-deals, &c. | 41 |
| Konigsberg-sleepers | 40 |
| Soderhamn-deals | 39 |
| Gefle-deals | 38 |
| Quebec-deals | 35 |

## 5. Field Contamination

- **Total contaminated records**: 35,403
- **Cargo keywords in ship_name**: 16,959
- **Date patterns in ship_name**: 3,657
- **Quantity patterns in ship_name**: 6,965
- **Consignee in origin port**: 949
- **Consignee in destination port**: 0

## 6. Cargo Quality

- **Total cargo items**: 396,369
- **Empty cargo shipments**: 9,182 (5.74%)
- **Quantity anomalies**: 128,152
- **Missing units**: 276,823
- **Missing commodities**: 200
- **Unique commodities**: 28,655
- **Unique units**: 266

## 7. Issues by Year

| Year | Shipments | Empty Origin | Empty Dest | Empty Cargo | Low Conf |
|------|-----------|--------------|------------|-------------|----------|
| 1874 | 4,029 | 123 | 0 | 41 | 44 |
| 1875 | 3,925 | 223 | 0 | 116 | 84 |
| 1877 | 3,546 | 3,215 | 0 | 635 | 22 |
| 1878 | 85 | 76 | 0 | 5 | 0 |
| 1879 | 6,874 | 439 | 0 | 6 | 1 |
| 1880 | 328 | 36 | 0 | 0 | 0 |
| 1881 | 13,178 | 1,661 | 0 | 987 | 28 |
| 1882 | 234 | 36 | 0 | 28 | 0 |
| 1883 | 14,996 | 1,805 | 0 | 505 | 61 |
| 1884 | 709 | 87 | 0 | 41 | 0 |
| 1885 | 15,110 | 1,975 | 0 | 474 | 79 |
| 1886 | 225 | 12 | 0 | 1 | 0 |
| 1887 | 13,991 | 2,164 | 0 | 347 | 39 |
| 1888 | 295 | 29 | 0 | 2 | 0 |
| 1889 | 14,078 | 1,001 | 0 | 199 | 58 |
| 1890 | 457 | 8 | 0 | 2 | 0 |
| 1891 | 13,109 | 2,396 | 0 | 838 | 76 |
| 1892 | 705 | 68 | 0 | 16 | 1 |
| 1893 | 11,370 | 1,588 | 0 | 751 | 110 |
| 1895 | 12,586 | 1,872 | 0 | 827 | 68 |
| 1896 | 430 | 126 | 0 | 67 | 4 |
| 1897 | 13,791 | 3,129 | 0 | 1,470 | 129 |
| 1898 | 808 | 211 | 0 | 107 | 3 |
| 1899 | 14,466 | 3,298 | 0 | 1,694 | 127 |
| unknown | 614 | 53 | 0 | 23 | 2 |

## 8. Recommendations

### High Priority (Immediate Action)

1. **Remove duplicate records**: ~7,783 exact duplicates identified
2. **Fix hallucination loops**: Review files with repeated text patterns
3. **Handle empty cargo**: 9,182 shipments have no cargo data

### Medium Priority (Data Enrichment)

4. **Split port+cargo combinations**: Apply rules from `port_parsing_fixes.json`
5. **Complete truncated ports**: Apply known fixes (BO → Bo'ness, etc.)
6. **Normalize OCR variants**: Map variant spellings to canonical forms
7. **Fix field contamination**: Cargo data in ship_name fields

### Generated Fix Files

- `reference_data/port_parsing_fixes.json` - Programmatic port fixes
- `reports/duplicate_records.csv` - Records to review/remove
- `reports/contaminated_records.csv` - Field contamination cases

---

*Report generated by timber shipment data quality analysis pipeline*