# YOLO11n Cumulative Final Test 2025 Result

## Status
PASS

## Purpose
This experiment evaluates YOLO11n on the cumulative OB/FVG dataset using unseen 2025 test data.

## Model
- Model: YOLO11n
- Method: Cumulative training
- Dataset: cumulative_yolo_2020_2024
- Training years: 2020-2024
- Final test year: 2025
- Epochs: 50
- Image size: 640
- Device: CPU

## Final Test 2025 Result

| Class | Images | Instances | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|---:|---:|
| all | 150 | 150 | 0.537 | 0.668 | 0.583 | 0.449 |
| order_block | 63 | 75 | 0.528 | 0.642 | 0.533 | 0.406 |
| fair_value_gap | 63 | 75 | 0.546 | 0.693 | 0.634 | 0.492 |

## Comparison Against YOLOv8n Cumulative Baseline

| Model | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| YOLOv8n cumulative | 0.515 | 0.595 | 0.543 | 0.408 |
| YOLO11n cumulative | 0.537 | 0.668 | 0.583 | 0.449 |
| Difference | +0.022 | +0.073 | +0.040 | +0.041 |

## Interpretation
YOLO11n outperformed the YOLOv8n cumulative baseline on unseen 2025 data.

The largest improvement appears in recall, which indicates that YOLO11n detects more true OB/FVG instances than YOLOv8n. The increase in mAP50-95 also indicates improved localization quality.

Fair Value Gap detection remains stronger than Order Block detection, but YOLO11n improves both classes compared to the YOLOv8n cumulative baseline.

## Conclusion
YOLO11n is currently the best completed cumulative benchmark model.

This result should be preserved as the first final benchmark candidate.
