# YOLOv9-S Cumulative Benchmark Result

## Experiment Information

| Item | Value |
|---|---|
| Model | YOLOv9-S |
| Training Strategy | Cumulative |
| Training Data | 2020-2024 |
| Final Test Data | 2025 unseen |
| Epochs | 50 |
| Image Size | 640 |
| Batch Size | 2 |
| Device | CPU |
| Classes | order_block, fair_value_gap |
| Checkpoint | best.pt |

## Validation Result

Validation dataset:

- Images: 150
- Instances: 92

| Class | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| All | 0.4810 | 0.0652 | 0.1490 | 0.0844 |
| Order Block | 0.8700 | 0.0435 | 0.2300 | 0.1310 |
| Fair Value Gap | 0.0924 | 0.0870 | 0.0680 | 0.0381 |

## Final Test 2025

Final unseen test dataset:

- Images: 150
- Instances: 150
- Order Block instances: 75
- Fair Value Gap instances: 75

| Class | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| All | 0.0315 | 0.9070 | 0.1350 | 0.0766 |
| Order Block | 0.0383 | 0.8800 | 0.1680 | 0.0938 |
| Fair Value Gap | 0.0247 | 0.9330 | 0.1020 | 0.0595 |

## Inference Speed

| Stage | Time per Image |
|---|---:|
| Pre-process | 0.4 ms |
| Inference | 148.9 ms |
| NMS | 0.6 ms |

Input shape:

2 x 3 x 640 x 640

## Analysis

YOLOv9-S produced very high recall on the 2025 unseen test dataset, but precision and mAP were extremely low.

The high recall indicates that the model detected a large proportion of available objects. However, the precision of 0.0315 indicates that most predictions were false positives.

The model also showed unstable behavior between validation and final testing:

- Validation recall was very low.
- Final test recall was very high.
- Precision remained insufficient.
- Fair Value Gap detection performed especially poorly.
- Overall mAP50 and mAP50-95 were substantially below other tested models.

The final test used the repository default confidence threshold of 0.001. This contributed to high recall and low precision, but the low average precision confirms that model quality remained inadequate across confidence thresholds.

## Decision

YOLOv9-S is not selected as the production detection model.

Status:

BENCHMARK COMPLETED
MODEL REJECTED
PAIRING TEST SKIPPED
OHLCV VALIDATION SKIPPED
SCORING V3 SKIPPED

Further downstream evaluation was skipped because detection performance was substantially below the current leading model.

## Selected Detection Model

The selected primary detection model remains:

YOLO11s 50 epochs
Prediction confidence: 0.25
OB-FVG pairing
OHLCV structural validation
Scoring v3

YOLO11s remains superior in overall precision, mAP50, mAP50-95, and downstream pipeline stability.
