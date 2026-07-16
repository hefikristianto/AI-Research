# YOLO11n 100 Epoch Final Test 2025 Result

## Status
COMPLETED

## Purpose
This experiment evaluates YOLO11n trained for 100 epochs on the cumulative OB/FVG dataset and tested on unseen 2025 data.

## Model
- Model: YOLO11n
- Method: Cumulative training
- Dataset: cumulative_yolo_2020_2024
- Training years: 2020-2024
- Final test year: 2025
- Epochs: 100
- Image size: 640
- Device: CPU

## Final Test 2025 Result

| Class | Images | Instances | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|---:|---:|
| all | 150 | 150 | 0.529 | 0.640 | 0.566 | 0.424 |
| order_block | 63 | 75 | 0.497 | 0.627 | 0.512 | 0.377 |
| fair_value_gap | 63 | 75 | 0.562 | 0.653 | 0.620 | 0.470 |

## Comparison Against YOLO11n 50 Epoch

| Model | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| YOLO11n 50e | 0.537 | 0.668 | 0.583 | 0.449 |
| YOLO11n 100e | 0.529 | 0.640 | 0.566 | 0.424 |
| Difference | -0.008 | -0.028 | -0.017 | -0.025 |

## Interpretation
YOLO11n trained for 100 epochs performed worse than YOLO11n trained for 50 epochs on the unseen 2025 test set.

The decrease in recall, mAP50, and mAP50-95 suggests that longer training does not improve generalization for the current dataset.

This may indicate overfitting, dataset limitation, or annotation noise from the rule-based semi-automatic labeling process.

## Conclusion
YOLO11n 50e remains the best YOLO11n result so far.

YOLO11n 100e is completed, but it should not be selected as the best benchmark result.
