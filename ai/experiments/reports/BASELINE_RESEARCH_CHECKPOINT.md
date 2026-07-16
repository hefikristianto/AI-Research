# AI-TDSS Baseline Research Checkpoint

## Status
BASELINE CHECKPOINT COMPLETED

## Date
2026-07-08

## Project
AI-TDSS - AI Trading Decision Support System

## Scope
This checkpoint records the completed baseline experiments for OB/FVG detection using YOLOv8n.

YOLOv8n is used only as a temporary development baseline. It is not the final benchmark model.

---

# 1. Completed Pipeline

## Detection Target
The current detection pipeline focuses on:
- Order Block
- Fair Value Gap

Class mapping:
- 0: order_block
- 1: fair_value_gap

## Current Pipeline Flow
Chart image
?
YOLO OB/FVG detection
?
Confidence filtering
?
OB-FVG pairing
?
Top setup selection
?
Visual direction estimate
?
OHLCV direction validation
?
Validated setup candidate

---

# 2. Dataset Status

## Auto-label Source
Path:
- ai/datasets/annotation/auto_labels_v5_medium/

Summary:
- Total windows: 900
- Total pairs: 365
- Total objects: 730
- Order blocks: 365
- Fair value gaps: 365

## YOLO Medium Dataset
Path:
- ai/datasets/annotation/exports/yolo_v5_medium/

Summary:
- Total images: 462
- Total objects: 730
- Train: 323
- Valid: 92
- Test: 47

## Incremental Dataset
Path:
- ai/datasets/annotation/exports/incremental_yolo/

Stages:
- base_2020
- inc_2021
- inc_2022
- inc_2023
- inc_2024
- final_test_2025

Validation:
- PASS
- Total errors: 0

## Cumulative Dataset
Path:
- ai/datasets/annotation/exports/cumulative_yolo_2020_2024/

Split:
- Train: 600 images, 488 objects
- Valid: 150 images, 92 objects
- Test: 150 images, 150 objects

Validation:
- PASS
- Total errors: 0

---

# 3. YOLOv8n Medium Baseline Result

## Training
Model:
- YOLOv8n

Dataset:
- yolo_v5_medium

Training setting:
- Epochs: 50
- Image size: 640
- Batch: 4
- Device: CPU

Approximate result:
- Precision: 0.65-0.68
- Recall: 0.65-0.68
- mAP50: 0.66-0.68
- mAP50-95: 0.50-0.52

Status:
- PASS

---

# 4. Post-processing Result

## OB/FVG Pairing v2
Report:
- ai/detection/postprocessing/reports/ob_fvg_pairing_summary_v2.md

Summary:
- Files processed: 31
- Detections kept: 60
- Top pairs generated: 20
- HIGH: 4
- MEDIUM: 11
- LOW: 5

Status:
- PASS

## OHLCV Direction Validation v2
Report:
- ai/detection/validation/reports/ob_fvg_direction_validation_summary_v2.md

Summary:
- Total pairs: 20
- OHLCV ok: 20
- Direction matches: 18
- Match rate: 90.00%

Status:
- PASS

---

# 5. Incremental YOLOv8n Result

## Training Chain
- base_2020
- inc_2021
- inc_2022
- inc_2023
- inc_2024
- final_test_2025

Final test:
- Dataset: final_test_2025
- Images: 150
- Instances: 150

## Final 2025 Result

| Class | Images | Instances | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|---:|---:|
| all | 150 | 150 | 0.447 | 0.576 | 0.501 | 0.345 |
| order_block | 63 | 75 | 0.485 | 0.478 | 0.457 | 0.305 |
| fair_value_gap | 63 | 75 | 0.409 | 0.675 | 0.545 | 0.384 |

Status:
- PASS as workflow validation
- Not final benchmark quality

---

# 6. Cumulative YOLOv8n Result

## Training
Training years:
- 2020
- 2021
- 2022
- 2023
- 2024

Final test:
- 2025

## Final 2025 Result

| Class | Images | Instances | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|---:|---:|
| all | 150 | 150 | 0.515 | 0.595 | 0.543 | 0.408 |
| order_block | 63 | 75 | 0.496 | 0.589 | 0.515 | 0.380 |
| fair_value_gap | 63 | 75 | 0.534 | 0.600 | 0.571 | 0.436 |

Status:
- PASS
- Best YOLOv8n development baseline so far

---

# 7. Incremental vs Cumulative Comparison

| Method | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| Incremental YOLOv8n | 0.447 | 0.576 | 0.501 | 0.345 |
| Cumulative YOLOv8n | 0.515 | 0.595 | 0.543 | 0.408 |

## Result
Cumulative YOLOv8n outperformed incremental YOLOv8n on unseen 2025 data.

## Interpretation
The incremental workflow is valid as a continual-learning experiment, but the current replay strategy is not yet better than direct cumulative training.

Cumulative training likely performs better because the model sees broader historical variation together during training.

---

# 8. Current Limitations

- YOLOv8n is only a temporary baseline.
- Dataset size is still limited.
- Labels are generated through rule-based semi-automatic annotation.
- Order Block detection remains more difficult than FVG detection.
- Exact candle-index alignment is not yet fully integrated into model labels.
- Current benchmark only covers XAUUSD and GBPUSD.
- Final benchmark models have not been tested yet.

---

# 9. Final Benchmark Direction

Final benchmark target models:
- YOLOv9
- YOLOv11
- YOLOv26

Recommended benchmark design:
- Use cumulative dataset as first benchmark baseline.
- Use incremental dataset as continual-learning experiment.
- Evaluate all models on the same final_test_2025 data.
- Compare Precision, Recall, mAP50, and mAP50-95.
- Preserve YOLOv8n as development baseline only.

---

# 10. Baseline Checkpoint Conclusion

The baseline detection research stage is complete.

Completed:
- Dataset generation
- Dataset validation
- YOLOv8n baseline training
- OB/FVG post-processing
- OHLCV validation
- Incremental training workflow
- Cumulative baseline workflow
- Incremental vs cumulative comparison

Next stage:
- Prepare final benchmark framework for YOLOv9, YOLOv11, and YOLOv26.
