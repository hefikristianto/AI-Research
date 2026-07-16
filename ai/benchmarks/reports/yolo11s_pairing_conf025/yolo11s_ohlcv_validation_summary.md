# YOLO11s Conf025 OB-FVG OHLCV Validation

## Purpose

This report validates visual OB-FVG direction estimates using local OHLCV OB-FVG structure search.

## Method

- Match prediction filename to auto-label metadata.
- Load the corresponding OHLCV window.
- Convert YOLO normalized x-coordinate into approximate candle index.
- Search local candles around the predicted OB location.
- Validate bullish/bearish OB-FVG structure using three-candle logic.

## Result

- Total pairs: 24
- OHLCV windows loaded successfully: 24
- Direction matches: 23
- Direction match rate: 95.83%
- Bullish candidates by OHLCV: 17
- Bearish candidates by OHLCV: 6
- Uncertain candidates: 1

## Notes

This v2 validation improves v1 by searching for a complete local OB-FVG structure around the YOLO-predicted region instead of checking only the nearest candle and the next impulse candle.

## Output

- CSV: ai\benchmarks\reports\yolo11s_pairing_conf025\yolo11s_ohlcv_validation.csv