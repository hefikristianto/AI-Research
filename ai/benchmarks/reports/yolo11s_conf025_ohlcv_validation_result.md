# YOLO11s Conf025 OHLCV Validation Result

## Status
PASS

## Purpose
This experiment validates YOLO11s OB-FVG candidate directions against the underlying OHLCV structure.

## Model
- Model: YOLO11s
- Training: cumulative 2020-2024
- Epochs: 50
- Prediction confidence: 0.25
- Pairing confidence: 0.25
- Final test year: 2025

## Result

| Metric | Value |
|---|---:|
| Total pairs | 24 |
| OHLCV windows loaded | 24 |
| Direction matches | 23 |
| Direction match rate | 95.83% |
| Bullish OHLCV candidates | 17 |
| Bearish OHLCV candidates | 6 |
| Uncertain candidates | 1 |

## Interpretation
YOLO11s generated 24 OB-FVG candidate pairs at a confidence threshold of 0.25.

Although the current pairing v2 quality system classified most pairs as LOW, OHLCV structural validation confirmed the predicted direction for 23 of 24 pairs.

This indicates that the existing pairing quality score is too conservative for YOLO11s and does not fully represent structural validity.

Model confidence and spatial proximity alone are insufficient for final setup scoring. OHLCV structural confirmation should be incorporated into the future scoring engine.

## Comparison

| Model | Pairs | OHLCV Direction Match Rate |
|---|---:|---:|
| YOLOv8n old medium | 20 | 90.00% |
| YOLO11s conf025 | 24 | 95.83% |

## Conclusion
YOLO11s 50e with prediction confidence 0.25 is currently the strongest completed model for the OB-FVG candidate-generation pipeline.

It provides:
- the best completed detection mAP,
- more generated candidate pairs,
- and the highest OHLCV direction match rate.

## Next Recommendation
Revise pairing scoring so that quality is based on:
- model confidence,
- spatial proximity,
- OHLCV structure confirmation,
- exact candle-index alignment,
- and later confluence factors.
