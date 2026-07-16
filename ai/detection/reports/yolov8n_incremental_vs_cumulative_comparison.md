# YOLOv8n Incremental vs Cumulative Baseline Comparison

## Status
PASS

## Purpose
This report compares the YOLOv8n incremental learning workflow against a cumulative training baseline for OB/FVG detection.

## Evaluation Setup
- Model: YOLOv8n
- Role: Temporary development baseline
- Final test year: 2025
- Test images: 150
- Test instances: 150
- Classes:
  - order_block
  - fair_value_gap

## Compared Methods

### Incremental Learning
Training chain:
- base_2020
- inc_2021
- inc_2022
- inc_2023
- inc_2024
- final_test_2025

### Cumulative Training
Training data:
- 2020
- 2021
- 2022
- 2023
- 2024

Final test:
- 2025

## Overall Result

| Method | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| Incremental YOLOv8n | 0.447 | 0.576 | 0.501 | 0.345 |
| Cumulative YOLOv8n | 0.515 | 0.595 | 0.543 | 0.408 |
| Difference | +0.068 | +0.019 | +0.042 | +0.063 |

## Per-Class Result

| Method | Class | Images | Instances | Precision | Recall | mAP50 | mAP50-95 |
|---|---|---:|---:|---:|---:|---:|---:|
| Incremental | order_block | 63 | 75 | 0.485 | 0.478 | 0.457 | 0.305 |
| Incremental | fair_value_gap | 63 | 75 | 0.409 | 0.675 | 0.545 | 0.384 |
| Cumulative | order_block | 63 | 75 | 0.496 | 0.589 | 0.515 | 0.380 |
| Cumulative | fair_value_gap | 63 | 75 | 0.534 | 0.600 | 0.571 | 0.436 |

## Interpretation
The cumulative training baseline outperformed the incremental learning workflow on the unseen 2025 test set.

Cumulative training achieved higher precision, recall, mAP50, and mAP50-95 overall. The improvement is most visible in mAP50-95, which suggests better bounding box localization quality.

The incremental model showed higher recall for Fair Value Gap detection, but lower precision. This indicates that the incremental model is more aggressive in detecting FVG zones, but also produces more false positives.

Order Block detection improved under cumulative training, especially in recall. This suggests that OB detection benefits from seeing broader historical data together during training.

## Conclusion
The incremental YOLOv8n workflow is considered successful as a pipeline validation experiment, but the cumulative YOLOv8n baseline performs better in this development-stage comparison.

This result should not be treated as the final benchmark conclusion because YOLOv8n is only a temporary baseline. Final benchmarking should be performed using YOLOv9, YOLOv11, and YOLOv26 with improved datasets and longer training settings.

## Recommended Next Steps
- Save cumulative final test result.
- Preserve both incremental and cumulative artifacts.
- Improve annotation quality.
- Test larger or final target YOLO models.
- Evaluate whether replay ratio or cumulative replay memory should be improved for incremental learning.
