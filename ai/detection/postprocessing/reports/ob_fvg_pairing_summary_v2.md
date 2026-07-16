# OB-FVG Pairing Summary v2

## Purpose

This report summarizes the second post-processing experiment for selecting the top OB-FVG setup candidate per image.

## Input

- Model: YOLOv8n medium baseline
- Dataset: yolo_v5_medium test split
- Prediction confidence threshold: 0.35
- IoU threshold: 0.40
- Classes:
  - 0: order_block
  - 1: fair_value_gap

## Pairing Rule v2

- Minimum confidence: 0.35
- Maximum horizontal distance: 0.18
- Maximum vertical distance: 0.35
- Maximum pairs per image: 1
- Direction estimate:
  - bullish_candidate if FVG is visually above OB
  - bearish_candidate if FVG is visually below OB
- Quality label:
  - HIGH: score >= 0.75 and both confidences >= 0.50
  - MEDIUM: score >= 0.65 and both confidences >= 0.40
  - LOW: remaining candidates

## Result

- Files processed: 31
- Detections kept: 60
- Top pairs generated: 20
- Highest score: 0.8091
- Lowest score: 0.5776
- Average score: 0.7000
- Average OB confidence: 0.5756
- Average FVG confidence: 0.5955
- Average horizontal distance: 0.0088
- Average vertical distance: 0.0644

## Quality Distribution

- HIGH: 4
- MEDIUM: 11
- LOW: 5

## Direction Distribution

- bullish_candidate: 13
- bearish_candidate: 7

## Top 10 Pairs

| Rank | File | Score | Quality | Direction | OB Conf | FVG Conf | X Distance |
|---:|---|---:|---|---|---:|---:|---:|
| 1 | gbpusd_h4_2021_20210126_160000_0002.txt | 0.8091 | HIGH | bullish_candidate | 0.6971 | 0.8257 | 0.0103 |
| 2 | xauusd_h1_2025_20250114_170000_0003.txt | 0.8006 | HIGH | bullish_candidate | 0.6245 | 0.8711 | 0.0093 |
| 3 | gbpusd_h1_2022_20220131_200000_0006.txt | 0.7936 | HIGH | bullish_candidate | 0.5987 | 0.8562 | 0.0093 |
| 4 | gbpusd_m15_2024_20240122_140000_0015.txt | 0.7903 | HIGH | bullish_candidate | 0.6510 | 0.7970 | 0.0093 |
| 5 | gbpusd_h4_2020_20200428_040000_0006.txt | 0.7385 | MEDIUM | bearish_candidate | 0.6803 | 0.6218 | 0.0098 |
| 6 | gbpusd_h4_2024_20240312_000000_0004.txt | 0.7242 | MEDIUM | bearish_candidate | 0.7017 | 0.5357 | 0.0085 |
| 7 | gbpusd_m15_2023_20230113_154500_0010.txt | 0.7234 | MEDIUM | bullish_candidate | 0.5394 | 0.6878 | 0.0090 |
| 8 | xauusd_h1_2025_20250317_080000_0013.txt | 0.7205 | MEDIUM | bullish_candidate | 0.6456 | 0.5854 | 0.0086 |
| 9 | xauusd_m5_2020_20200106_100500_0007.txt | 0.7186 | MEDIUM | bearish_candidate | 0.7288 | 0.5217 | 0.0083 |
| 10 | xauusd_h1_2021_20210309_040000_0012.txt | 0.7133 | MEDIUM | bullish_candidate | 0.7017 | 0.5188 | 0.0081 |

## Interpretation

The v2 pairing stage reduces YOLO detections into a single top OB-FVG candidate per image. This makes the output more suitable for downstream scoring and decision-support logic.

## Next Step

- Add duplicate/overlap removal before pairing.
- Improve direction validation using OHLCV context instead of image coordinates only.
- Add confluence scoring using trend, freshness, liquidity, and risk-reward feasibility.
- Prepare yearly dataset splits for incremental learning.