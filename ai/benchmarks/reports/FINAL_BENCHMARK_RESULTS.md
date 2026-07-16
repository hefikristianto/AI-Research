# Final Benchmark Result Table

## Status
IN_PROGRESS

## Detection Benchmark

| Model | Method | Precision | Recall | mAP50 | mAP50-95 | Status |
|---|---|---:|---:|---:|---:|---|
| YOLOv8n | Cumulative 2020-2024 | 0.515 | 0.595 | 0.543 | 0.408 | Baseline |
| YOLO11n 50e | Cumulative 2020-2024 | 0.537 | 0.668 | 0.583 | 0.449 | Best recall |
| YOLO11n 100e | Cumulative 2020-2024 | 0.529 | 0.640 | 0.566 | 0.424 | Lower than 50e |
| YOLO11s 50e | Cumulative 2020-2024 | 0.591 | 0.593 | 0.590 | 0.452 | Best detection mAP |

## Setup Pipeline Benchmark

| Model | Predict Conf | Pairs | OHLCV Loaded | Direction Matches | Match Rate |
|---|---:|---:|---:|---:|---:|
| YOLOv8n old medium | 0.35 | 20 | 20 | 18 | 90.00% |
| YOLO11s 50e | 0.25 | 24 | 24 | 23 | 95.83% |

## Current Best Detection Model
YOLO11s cumulative 50e.

## Current Best Setup Candidate Model
YOLO11s cumulative 50e with prediction confidence 0.25.

## Important Finding
The previous pairing v2 quality labels are too conservative for YOLO11s.

Most YOLO11s pairs were classified as LOW by confidence-based scoring, but OHLCV validation confirmed 23 of 24 candidate directions.

Future setup quality scoring should integrate OHLCV structural validation rather than relying mainly on model confidence and spatial distance.

## Remaining Final Benchmark Targets

| Model | Method | Precision | Recall | mAP50 | mAP50-95 | Status |
|---|---|---:|---:|---:|---:|---|
| YOLOv9 | Cumulative 2020-2024 | TBD | TBD | TBD | TBD | Not started |
| YOLOv26 | Cumulative 2020-2024 | TBD | TBD | TBD | TBD | Not started |
