# AI-TDSS Experiment Report Index

## Status
ACTIVE

## Purpose
This index records the completed AI-TDSS detection experiments, reports, datasets, and evaluation artifacts.

---

# 1. Dataset Reports

## Auto-label Dataset
Source:
- ai/datasets/annotation/auto_labels_v5_medium/

Important reports:
- ai/datasets/annotation/auto_labels_v5_medium/reports/auto_label_report.csv

Summary:
- Total windows: 900
- Total object pairs: 365
- Total objects: 730
- Classes:
  - 0: order_block
  - 1: fair_value_gap

---

## YOLO v5 Medium Dataset
Path:
- ai/datasets/annotation/exports/yolo_v5_medium/

Summary:
- Total images: 462
- Total objects: 730
- Order blocks: 365
- Fair value gaps: 365
- Split:
  - train: 323
  - valid: 92
  - test: 47

---

## Incremental YOLO Dataset
Path:
- ai/datasets/annotation/exports/incremental_yolo/

Important reports:
- ai/datasets/annotation/exports/incremental_yolo/incremental_dataset_index.md
- ai/datasets/annotation/exports/incremental_yolo/validation_reports/incremental_validation_summary.md

Stages:
- base_2020
- inc_2021
- inc_2022
- inc_2023
- inc_2024
- final_test_2025

Validation:
- Total stages: 6
- Total errors: 0

---

## Cumulative YOLO Dataset 2020-2024
Path:
- ai/datasets/annotation/exports/cumulative_yolo_2020_2024/

Important reports:
- ai/datasets/annotation/exports/cumulative_yolo_2020_2024/reports/summary.md
- ai/datasets/annotation/exports/cumulative_yolo_2020_2024/validation_reports/cumulative_validation_summary.md

Summary:
- train: 600 images, 488 objects
- valid: 150 images, 92 objects
- test: 150 images, 150 objects

Validation:
- Total errors: 0

---

# 2. Detection Pipeline Reports

## Post-processing Pairing v1
Reports:
- ai/detection/postprocessing/reports/ob_fvg_pairs_v1.csv
- ai/detection/postprocessing/reports/ob_fvg_pairing_summary_v1.md

Summary:
- Files processed: 31
- Detections kept: 60
- Pairs generated: 21

---

## Post-processing Pairing v2
Reports:
- ai/detection/postprocessing/reports/ob_fvg_pairs_v2.csv
- ai/detection/postprocessing/reports/ob_fvg_pairing_summary_v2.md
- ai/detection/postprocessing/reports/postprocessing_v2_status.md
- ai/detection/postprocessing/reports/visual_review_v2_status.md

Summary:
- Files processed: 31
- Detections kept: 60
- Top pairs generated: 20
- HIGH: 4
- MEDIUM: 11
- LOW: 5

Status:
- Visual review top pairs: PASS

---

## OHLCV Direction Validation v2
Reports:
- ai/detection/validation/reports/ob_fvg_direction_validation_v2.csv
- ai/detection/validation/reports/ob_fvg_direction_validation_summary_v2.md
- ai/detection/validation/reports/direction_validation_v2_status.md

Summary:
- Total pairs: 20
- OHLCV ok: 20
- Direction matches: 18
- Match rate: 90.00%

Status:
- PASS

---

# 3. Training Experiments

## YOLOv8n Medium Baseline
Path:
- runs/detect/ai/experiments/yolo/train_ob_fvg_v5_medium_50e/

Model:
- YOLOv8n
- Epochs: 50
- Image size: 640
- Device: CPU

Approximate result:
- Precision: 0.65-0.68
- Recall: 0.65-0.68
- mAP50: 0.66-0.68
- mAP50-95: 0.50-0.52

Status:
- PASS

---

## YOLOv8n Incremental Learning
Path:
- runs/detect/ai/experiments/incremental_yolo/

Stages:
- yolov8n_base_2020
- yolov8n_inc_2021
- yolov8n_inc_2022
- yolov8n_inc_2023
- yolov8n_inc_2024
- yolov8n_final_test_2025

Final test report:
- ai/detection/reports/incremental_yolov8n_final_test_2025_result.md

Final 2025 result:
- Precision: 0.447
- Recall: 0.576
- mAP50: 0.501
- mAP50-95: 0.345

Status:
- PASS as development workflow
- Not final benchmark

---

## YOLOv8n Cumulative Baseline
Path:
- runs/detect/ai/experiments/cumulative_yolo/

Training:
- yolov8n_cumulative_2020_2024

Final test:
- yolov8n_cumulative_final_test_2025

Final 2025 result:
- Precision: 0.515
- Recall: 0.595
- mAP50: 0.543
- mAP50-95: 0.408

Status:
- PASS
- Better than incremental YOLOv8n baseline

---

# 4. Main Comparison Reports

## Incremental vs Cumulative YOLOv8n
Report:
- ai/detection/reports/yolov8n_incremental_vs_cumulative_comparison.md

Overall result:

| Method | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| Incremental YOLOv8n | 0.447 | 0.576 | 0.501 | 0.345 |
| Cumulative YOLOv8n | 0.515 | 0.595 | 0.543 | 0.408 |

Conclusion:
- Cumulative YOLOv8n outperformed incremental YOLOv8n on unseen 2025 data.
- Incremental workflow is valid, but replay strategy and dataset quality need improvement.

---

# 5. Current Research Status

## Completed
- OB/FVG auto-labeling pipeline
- YOLO dataset generation
- YOLOv8n development training
- Post-processing pairing
- OHLCV direction validation
- Incremental yearly dataset split
- Incremental YOLOv8n training chain
- Cumulative YOLOv8n baseline
- Incremental vs cumulative comparison

## Not Final Yet
- YOLOv8n is not the final benchmark model.
- Current dataset is still small.
- Auto-label quality still needs refinement.
- Exact candle-index label alignment is not fully integrated.
- YOLOv9, YOLOv11, and YOLOv26 benchmark experiments are not started yet.

## Next Recommended Stage
Prepare the final benchmark framework for:
- YOLOv9
- YOLOv11
- YOLOv26

Before final benchmark:
- Preserve current baseline artifacts.
- Clean report index.
- Save model paths.
- Confirm dataset versions.
