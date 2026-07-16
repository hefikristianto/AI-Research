# OB-FVG Direction Validation v2

## Purpose

This report validates visual OB-FVG direction estimates using local OHLCV OB-FVG structure search.

## Method

- Match prediction filename to auto-label metadata.
- Load the corresponding OHLCV window.
- Convert YOLO normalized x-coordinate into approximate candle index.
- Search local candles around the predicted OB location.
- Validate bullish/bearish OB-FVG structure using three-candle logic.

## Result

- Total pairs: 20
- OHLCV windows loaded successfully: 20
- Direction matches: 18
- Direction match rate: 90.00%
- Bullish candidates by OHLCV: 11
- Bearish candidates by OHLCV: 7
- Uncertain candidates: 2

## Notes

This v2 validation improves v1 by searching for a complete local OB-FVG structure around the YOLO-predicted region instead of checking only the nearest candle and the next impulse candle.

## Output

- CSV: ai\detection\validation\reports\ob_fvg_direction_validation_v2.csv