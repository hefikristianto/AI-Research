# OB-FVG Direction Validation v2 Status

## Status
PASS

## Summary
The OHLCV-based direction validation v2 successfully validates OB-FVG candidate directions using local three-candle structure search around YOLO-predicted regions.

## Input
- Source pairs: ob_fvg_pairs_v2.csv
- Model: YOLOv8n medium baseline
- Dataset: yolo_v5_medium test split
- Prediction confidence threshold: 0.35
- Pairing method: OB-FVG pairing v2

## Result
- Total pairs: 20
- OHLCV windows loaded successfully: 20
- Direction matches: 18
- Direction match rate: 90.00%
- Bullish candidates by OHLCV: 11
- Bearish candidates by OHLCV: 7
- Uncertain candidates: 2

## Interpretation
The result shows that YOLO-based OB/FVG detections can be validated using OHLCV candle structure. Compared with validation v1, which only checked the nearest candle and next candle, validation v2 performs a local search for a complete three-candle OB-FVG structure and significantly improves direction validation reliability.

## Limitation
The method still depends on approximate YOLO x-coordinate mapping to candle index. Future versions should store or recover exact OB/FVG candidate candle indices from the auto-label generator.

## Next Step
- Save this stage as the accepted validation baseline.
- Add duplicate/overlap removal if needed.
- Start preparing yearly dataset split for incremental learning.
- Later, extend this validation into the confluence scoring engine.
