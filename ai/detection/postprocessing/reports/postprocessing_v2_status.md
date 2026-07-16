# OB-FVG Post-processing v2 Status

## Status
PASS

## Summary
The v2 post-processing stage successfully converts YOLO detections into one top OB-FVG setup candidate per image.

## Input
- Model: YOLOv8n medium baseline
- Dataset: yolo_v5_medium test split
- Prediction confidence threshold: 0.35
- IoU threshold: 0.40

## Result
- Files processed: 31
- Detections kept: 60
- Top pairs generated: 20
- HIGH quality pairs: 4
- MEDIUM quality pairs: 11
- LOW quality pairs: 5
- Bullish candidates: 13
- Bearish candidates: 7
- Average score: 0.7000

## Interpretation
The result shows that YOLO OB/FVG detections can be filtered and transformed into structured setup candidates. This supports the AI-TDSS pipeline design where object detection is not treated as the final decision, but as candidate generation for later scoring.

## Limitation
Direction estimation is still based on visual coordinate position only. It must be improved using OHLCV-based validation.

## Next Step
- Visual review of top v2 pairs.
- Add OHLCV-based direction validation.
- Add duplicate/overlap removal.
- Add confluence scoring.
- Prepare yearly incremental dataset split.
