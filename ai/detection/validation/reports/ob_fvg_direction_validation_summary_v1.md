# OB-FVG Direction Validation v1

## Purpose

This report validates visual OB-FVG direction estimates using OHLCV candle structure.

## Method

- Match prediction filename to auto-label metadata.
- Load the corresponding OHLCV window.
- Convert YOLO normalized x-coordinate into approximate candle index.
- Validate direction using OB candle and next impulse candle.

## Result

- Total pairs: 20
- OHLCV windows loaded successfully: 20
- Direction matches: 1
- Direction match rate: 5.00%
- Bullish candidates by OHLCV: 1
- Bearish candidates by OHLCV: 2
- Uncertain candidates: 17

## Notes

This is an initial validation method. It uses the nearest candle around the detected OB x-coordinate and the next candle as the impulse candle. Future versions should use a wider local search and validate the full OB-FVG three-candle structure.

## Output

- CSV: ai\detection\validation\reports\ob_fvg_direction_validation_v1.csv