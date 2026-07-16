# AI-TDSS Detection Pipeline Checkpoint

## Checkpoint
OB/FVG Detection, Pairing, and OHLCV Validation Baseline

## Status
PASS

## Purpose
This checkpoint documents the current working baseline for detecting Order Block and Fair Value Gap zones using YOLO, pairing the detected zones, and validating setup direction using OHLCV candle structure.

## Dataset
- Dataset version: yolo_v5_medium
- Source: auto_labels_v5_medium
- Pairs:
  - GBPUSD
  - XAUUSD
- Timeframes:
  - M5
  - M15
  - H1
  - H4
- Years:
  - 2020-2025

## Dataset Statistics
- Total images: 462
- Train images: 323
- Validation images: 92
- Test images: 47
- Total objects: 730
- Order Block objects: 365
- Fair Value Gap objects: 365
- Invalid files: 0

## Training Baseline
- Temporary model: YOLOv8n
- Purpose: smoke/medium baseline only
- Final benchmark models:
  - YOLOv9
  - YOLOv11
  - YOLOv26
- Epochs: 50
- Image size: 640
- Batch size: 4
- Device: CPU

## Training Result
Approximate result from medium baseline:
- Precision: around 0.65 - 0.68
- Recall: around 0.65 - 0.68
- mAP50: around 0.66 - 0.68
- mAP50-95: around 0.50 - 0.52

## Prediction Setting
Clean prediction setting:
- Confidence threshold: 0.35
- IoU threshold: 0.40

This setting produced cleaner OB/FVG detections and reduced low-confidence false positives.

## Post-processing v2
The post-processing stage converts raw YOLO detections into structured OB-FVG setup candidates.

### Method
- Filter YOLO detections by confidence.
- Pair nearby Order Block and Fair Value Gap detections.
- Select the top 1 setup candidate per image.
- Estimate visual direction:
  - bullish_candidate
  - bearish_candidate
- Assign quality label:
  - HIGH
  - MEDIUM
  - LOW

### Result
- Files processed: 31
- Detections kept: 60
- Top pairs generated: 20
- HIGH quality pairs: 4
- MEDIUM quality pairs: 11
- LOW quality pairs: 5
- Bullish candidates: 13
- Bearish candidates: 7
- Average score: 0.7000

## Visual Review v2
Top v2 pair candidates were visually reviewed.

### Result
- Visual review status: PASS
- HIGH quality pairs were mostly strong and structurally reasonable.
- MEDIUM quality pairs were mostly acceptable but still require OHLCV validation.
- Pairing v2 successfully reduced raw YOLO detections into cleaner setup candidates.

## OHLCV Direction Validation v2
Direction validation v2 validates visual direction estimates using local OHLCV three-candle structure search.

### Method
- Match prediction filename to auto-label metadata.
- Load the corresponding OHLCV window.
- Convert YOLO normalized x-coordinate into approximate candle index.
- Search nearby candles for a complete OB-FVG structure.
- Validate bullish/bearish candidate direction using candle data.

### Result
- Total pairs: 20
- OHLCV windows loaded successfully: 20
- Direction matches: 18
- Direction match rate: 90.00%
- Bullish candidates by OHLCV: 11
- Bearish candidates by OHLCV: 7
- Uncertain candidates: 2

## Current Pipeline
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

## Conclusion
The detection pipeline is now stable enough to be used as the baseline for the next development stage. The system can detect OB/FVG candidates, pair them into setup candidates, and validate direction using OHLCV structure.

This baseline is not the final model benchmark. YOLOv8n is used only for pipeline validation. Final benchmark training will later use YOLOv9, YOLOv11, and YOLOv26.

## Limitations
- Current dataset only uses GBPUSD and XAUUSD.
- Direction validation still depends on approximate YOLO x-coordinate mapping.
- Exact OB/FVG candle indices are not yet stored from the auto-label generator.
- Confluence scoring is not implemented yet.
- Multi-pair generalization has not been tested yet.

## Next Stage
Prepare yearly dataset splits for incremental learning.

Planned structure:
- base_2020
- inc_2021
- inc_2022
- inc_2023
- inc_2024
- final_test_2025

After incremental split preparation, the next major stages are:
1. Incremental YOLO training workflow.
2. Multi-pair dataset expansion.
3. Final benchmark with YOLOv9, YOLOv11, and YOLOv26.
4. Thesis report rewrite with separated CNN and YOLO hyperparameter sections.
