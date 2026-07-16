# YOLO26n Cumulative Final Test 2025 Result

## Status
COMPLETED

## Model
- Model: YOLO26n
- Method: Cumulative training
- Training years: 2020-2024
- Final test year: 2025
- Epochs: 50
- Image size: 640
- Device: CPU

## Final Result

| Class | Images | Instances | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|---:|---:|
| all | 150 | 150 | 0.502 | 0.567 | 0.515 | 0.392 |
| order_block | 63 | 75 | 0.514 | 0.507 | 0.433 | 0.324 |
| fair_value_gap | 63 | 75 | 0.490 | 0.628 | 0.596 | 0.460 |

## Comparison

| Model | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| YOLO11s 50e | 0.591 | 0.593 | 0.590 | 0.452 |
| YOLO26n 50e | 0.502 | 0.567 | 0.515 | 0.392 |

## Interpretation
YOLO26n performed below YOLO11s on all overall detection metrics.

YOLO26n retained reasonable Fair Value Gap performance, but Order Block detection was substantially weaker.

YOLO11s remains the strongest completed benchmark model.

## Conclusion
YOLO26n is accepted as a completed benchmark result, but is not selected as the best model.
