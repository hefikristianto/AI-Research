# AI-TDSS Quick Resume for Next Chat

## Project
AI-TDSS - AI Trading Decision Support System

## Current Status
Baseline research checkpoint completed.

## Main Detection Task
Current YOLO detection task:
- order_block
- fair_value_gap

Class mapping:
- 0: order_block
- 1: fair_value_gap

## Dataset Source
Main auto-label source:
- ai/datasets/annotation/auto_labels_v5_medium/

Auto-label summary:
- Total windows: 900
- Total OB/FVG pairs: 365
- Total objects: 730
- OB: 365
- FVG: 365

## Important Dataset Exports
YOLO medium dataset:
- ai/datasets/annotation/exports/yolo_v5_medium/

Incremental dataset:
- ai/datasets/annotation/exports/incremental_yolo/

Cumulative dataset:
- ai/datasets/annotation/exports/cumulative_yolo_2020_2024/

## Completed Experiments

### YOLOv8n Medium Baseline
Path:
- runs/detect/ai/experiments/yolo/train_ob_fvg_v5_medium_50e/

Approx result:
- Precision: 0.65-0.68
- Recall: 0.65-0.68
- mAP50: 0.66-0.68
- mAP50-95: 0.50-0.52

### Incremental YOLOv8n
Path:
- runs/detect/ai/experiments/incremental_yolo/

Final 2025 result:
- Precision: 0.447
- Recall: 0.576
- mAP50: 0.501
- mAP50-95: 0.345

### Cumulative YOLOv8n
Path:
- runs/detect/ai/experiments/cumulative_yolo/

Final 2025 result:
- Precision: 0.515
- Recall: 0.595
- mAP50: 0.543
- mAP50-95: 0.408

## Main Comparison
Cumulative YOLOv8n performed better than incremental YOLOv8n on unseen 2025 test data.

## Post-processing
OB/FVG pairing v2:
- Files processed: 31
- Detections kept: 60
- Top pairs generated: 20
- HIGH: 4
- MEDIUM: 11
- LOW: 5

OHLCV direction validation v2:
- Total pairs: 20
- Direction matches: 18
- Match rate: 90%

## Important Reports
- ai/experiments/reports/EXPERIMENT_REPORT_INDEX.md
- ai/experiments/reports/MODEL_ARTIFACT_INDEX.md
- ai/experiments/reports/BASELINE_RESEARCH_CHECKPOINT.md
- ai/detection/reports/yolov8n_incremental_vs_cumulative_comparison.md
- ai/detection/reports/incremental_yolov8n_final_test_2025_result.md

## Important Note
YOLOv8n is only a temporary development baseline.

Final benchmark target models:
- YOLOv9
- YOLOv11
- YOLOv26

## Next Recommended Task
Prepare final benchmark framework for YOLOv9, YOLOv11, and YOLOv26.
