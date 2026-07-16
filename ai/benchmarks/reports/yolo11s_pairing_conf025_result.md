# YOLO11s Pairing Confidence 0.25 Result

## Status
COMPLETED

## Purpose
This experiment evaluates YOLO11s pairing performance using lower prediction and pairing confidence threshold.

## Model
- Model: YOLO11s
- Training: cumulative 2020-2024
- Final test year: 2025
- Prediction confidence: 0.25
- Pairing confidence threshold: 0.25
- IoU: 0.40

## Result

| Setting | Detections Kept | Pairs Generated | HIGH | MEDIUM | LOW | Avg Score | Avg OB Conf | Avg FVG Conf |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| YOLO11s conf035 | 53 | 15 | 0 | 4 | 11 | 0.6262 | 0.4808 | 0.4861 |
| YOLO11s conf025 | 83 | 24 | 0 | 4 | 20 | 0.5985 | 0.4252 | 0.4484 |

## Interpretation
Lowering the prediction and pairing confidence threshold from 0.35 to 0.25 increased the number of detections and generated OB-FVG pairs.

However, most additional pairs are LOW quality. The average score, average OB confidence, and average FVG confidence decreased.

This indicates that YOLO11s can produce more setup candidates with a lower confidence threshold, but additional filtering and scoring are required before using these pairs for decision support.

## Conclusion
YOLO11s conf025 is useful for candidate generation, while YOLO11s conf035 is cleaner but produces fewer pairs.

For the current pipeline:
- YOLO11s 50e remains the best detection model by mAP.
- YOLO11s conf025 is better for wider candidate generation.
- YOLOv8n old medium still has stronger HIGH/MEDIUM pairing under the current pairing v2 scoring logic.
