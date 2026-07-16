# YOLO11s Cumulative Final Test 2025 Result

## Status
PASS

## Purpose
This experiment evaluates YOLO11s on the cumulative OB/FVG dataset using unseen 2025 test data.

## Model
- Model: YOLO11s
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
| all | 150 | 150 | 0.591 | 0.593 | 0.590 | 0.452 |
| order_block | 63 | 75 | 0.525 | 0.559 | 0.544 | 0.418 |
| fair_value_gap | 63 | 75 | 0.658 | 0.627 | 0.635 | 0.485 |

## Comparison Against YOLO11n 50 Epoch

| Model | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| YOLO11n 50e | 0.537 | 0.668 | 0.583 | 0.449 |
| YOLO11s 50e | 0.591 | 0.593 | 0.590 | 0.452 |
| Difference | +0.054 | -0.075 | +0.007 | +0.003 |

## Interpretation
YOLO11s achieved higher precision, mAP50, and mAP50-95 than YOLO11n, but lower recall.

This suggests that YOLO11s produces more selective and more precise detections, while YOLO11n detects more objects overall.

YOLO11s is currently the best completed model by mAP50 and mAP50-95, while YOLO11n remains better by recall.

## Conclusion
YOLO11s 50e is currently the best completed benchmark model based on mAP50 and mAP50-95.
