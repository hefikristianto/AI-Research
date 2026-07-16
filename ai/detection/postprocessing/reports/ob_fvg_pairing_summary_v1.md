# OB-FVG Pairing Summary v1

## Purpose

This report summarizes the first post-processing experiment for pairing YOLO-detected Order Block and Fair Value Gap candidates.

## Input

- Model: YOLOv8n medium baseline
- Dataset: yolo_v5_medium test split
- Prediction confidence threshold: 0.35
- IoU threshold: 0.40
- Classes:
  - 0: order_block
  - 1: fair_value_gap

## Pairing Rule

A valid pair is formed when an Order Block and Fair Value Gap are horizontally close enough in normalized image coordinates.

- Maximum horizontal distance: 0.18
- Maximum pairs per image: 3
- Pair score components:
  - YOLO confidence average
  - horizontal proximity
  - vertical proximity

## Result

- Total pairs generated: 21
- Files with pairs: 20
- Highest score: 0.8246
- Lowest score: 0.6092
- Average score: 0.7212
- Average OB confidence: 0.5769
- Average FVG confidence: 0.5852
- Average horizontal distance: 0.0089

## Top 10 Pairs

| Rank | File | Score | OB Conf | FVG Conf | X Distance |
|---:|---|---:|---:|---:|---:|
| 1 | gbpusd_h4_2021_20210126_160000_0002.txt | 0.8246 | 0.6971 | 0.8257 | 0.0103 |
| 2 | xauusd_h1_2025_20250114_170000_0003.txt | 0.8174 | 0.6245 | 0.8711 | 0.0093 |
| 3 | gbpusd_h1_2022_20220131_200000_0006.txt | 0.8095 | 0.5987 | 0.8562 | 0.0093 |
| 4 | gbpusd_m15_2024_20240122_140000_0015.txt | 0.8067 | 0.6510 | 0.7970 | 0.0093 |
| 5 | gbpusd_h4_2020_20200428_040000_0006.txt | 0.7596 | 0.6803 | 0.6218 | 0.0098 |
| 6 | gbpusd_h4_2024_20240312_000000_0004.txt | 0.7458 | 0.7017 | 0.5357 | 0.0085 |
| 7 | gbpusd_m15_2023_20230113_154500_0010.txt | 0.7441 | 0.5394 | 0.6878 | 0.0090 |
| 8 | xauusd_m5_2020_20200106_100500_0007.txt | 0.7429 | 0.7288 | 0.5217 | 0.0083 |
| 9 | xauusd_h1_2025_20250317_080000_0013.txt | 0.7426 | 0.6456 | 0.5854 | 0.0086 |
| 10 | xauusd_h1_2021_20210309_040000_0012.txt | 0.7372 | 0.7017 | 0.5188 | 0.0081 |

## Interpretation

The pairing result shows that YOLO detections can be converted into structured OB-FVG setup candidates. The generated pairs are not yet final trading decisions, but they provide a cleaner candidate list for the future scoring engine.

## Next Step

- Add overlap removal for duplicate detections.
- Add directional validation between OB and FVG.
- Add confluence scoring based on trend, freshness, liquidity, and risk-reward context.
- Select top 1-3 zones as final decision-support candidates.
