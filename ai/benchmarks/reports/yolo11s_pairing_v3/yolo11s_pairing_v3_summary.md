# YOLO11s OB-FVG Pairing Scoring v3

## Status

COMPLETED

## Purpose

Scoring v3 combines YOLO confidence, spatial proximity, OHLCV direction validation, local structural strength, and candle-index alignment.

## Scoring Weights

- YOLO confidence: 20%
- Spatial proximity: 15%
- OHLCV direction validation: 30%
- Local OB-FVG structure: 25%
- Candle alignment: 10%

## Result

- Total pairs: 24
- Direction matches: 23
- Average final score: 0.7706
- Highest final score: 0.8314
- Lowest final score: 0.6135

## Quality Distribution

- HIGH: 11
- MEDIUM: 12
- LOW: 1
- REJECTED: 0

## Decision Distribution

- ACCEPT: 11
- REVIEW: 12
- WATCHLIST: 1
- REJECT: 0

## Top 10 Ranked Pairs

| Rank | File | Final Score | Quality | Decision | Direction Match | Structure Score |
|---:|---|---:|---|---|---|---:|
| 1 | gbpusd_m5_2025_20250103_010000_0004.txt | 0.8314 | HIGH | ACCEPT | True | 0.9073 |
| 2 | xauusd_m5_2025_20250108_010000_0012.txt | 0.8134 | HIGH | ACCEPT | True | 0.7672 |
| 3 | xauusd_m15_2025_20250124_101500_0016.txt | 0.7976 | HIGH | ACCEPT | True | 0.7622 |
| 4 | gbpusd_m15_2025_20250128_220000_0019.txt | 0.7932 | HIGH | ACCEPT | True | 0.6561 |
| 5 | xauusd_h4_2025_20250825_160000_0011.txt | 0.7923 | MEDIUM | REVIEW | True | 0.7246 |
| 6 | xauusd_h1_2025_20250213_130000_0008.txt | 0.7914 | MEDIUM | REVIEW | True | 0.7293 |
| 7 | gbpusd_h1_2025_20250319_150000_0014.txt | 0.7911 | HIGH | ACCEPT | True | 0.8461 |
| 8 | gbpusd_h4_2025_20250522_000000_0007.txt | 0.7901 | HIGH | ACCEPT | True | 0.7511 |
| 9 | gbpusd_h4_2025_20250613_160000_0008.txt | 0.7896 | HIGH | ACCEPT | True | 0.7060 |
| 10 | gbpusd_h1_2025_20250401_010000_0016.txt | 0.7889 | HIGH | ACCEPT | True | 0.7494 |

## Quality Rules

- HIGH: strong OHLCV confirmation, strong structure, and sufficient model confidence.
- MEDIUM: valid structure with moderate overall strength.
- LOW: structurally plausible but weak confidence or alignment.
- REJECTED: failed OHLCV direction validation or weak final score.

## Output

- CSV: ai\benchmarks\reports\yolo11s_pairing_v3\yolo11s_ob_fvg_pairs_v3.csv