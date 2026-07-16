# AI-TDSS YOLO11s Pairing Scoring v3 Milestone

## Status
PASS

## Purpose
This milestone records the completed downstream OB-FVG candidate pipeline using YOLO11s, OHLCV structural validation, and scoring v3.

## Model
- Model: YOLO11s
- Training method: cumulative 2020-2024
- Epochs: 50
- Prediction confidence: 0.25
- Final test year: 2025

## Detection Result

| Metric | Value |
|---|---:|
| Precision | 0.591 |
| Recall | 0.593 |
| mAP50 | 0.590 |
| mAP50-95 | 0.452 |

## Candidate Generation

| Metric | Value |
|---|---:|
| Detections kept | 83 |
| OB-FVG pairs generated | 24 |
| Bullish candidates | 18 |
| Bearish candidates | 6 |

## OHLCV Validation

| Metric | Value |
|---|---:|
| Total pairs | 24 |
| OHLCV windows loaded | 24 |
| Direction matches | 23 |
| Direction match rate | 95.83% |
| Bullish OHLCV candidates | 17 |
| Bearish OHLCV candidates | 6 |
| Uncertain candidates | 1 |

## Scoring v3

Scoring v3 combines:
- YOLO confidence: 20%
- Spatial proximity: 15%
- OHLCV direction validation: 30%
- Local OB-FVG structure: 25%
- Candle-index alignment: 10%

## Scoring v3 Result

| Quality | Count |
|---|---:|
| HIGH | 11 |
| MEDIUM | 12 |
| LOW | 1 |
| REJECTED | 0 |

## Decision Distribution

| Decision | Count |
|---|---:|
| ACCEPT | 11 |
| REVIEW | 12 |
| WATCHLIST | 1 |
| REJECT | 0 |

## Score Statistics

| Metric | Value |
|---|---:|
| Average final score | 0.7706 |
| Highest final score | 0.8314 |
| Lowest final score | 0.6135 |

## Main Finding
The previous pairing v2 scoring was too conservative for YOLO11s.

Pairing v2 classified most candidates as LOW because it relied heavily on YOLO confidence and spatial distance.

After integrating OHLCV direction validation, local structure strength, impulse quality, and candle alignment, scoring v3 produced a distribution that better reflects actual structural validity.

## Current Best Pipeline

Chart image
?
YOLO11s 50e
?
Prediction confidence 0.25
?
OB-FVG pairing
?
OHLCV structural validation
?
Scoring v3
?
ACCEPT / REVIEW / WATCHLIST / REJECT

## Current Best Status
- Best detection model: YOLO11s 50e
- Best candidate generation mode: YOLO11s conf 0.25
- Best OHLCV direction match rate: 95.83%
- Best downstream scoring version: v3

## Limitations
- One candidate remains uncertain or direction-mismatched.
- Exact candle-index alignment still depends on normalized YOLO x-coordinate approximation.
- Current scoring weights are manually designed and have not yet been optimized statistically.
- Dataset still covers only XAUUSD and GBPUSD.
- Final benchmark against YOLOv9 and YOLOv26 is not completed.

## Next Stage
- Inspect the unmatched candidate.
- Tighten rejection logic for direction mismatch.
- Preserve scoring v3 as the current baseline.
- Continue benchmark preparation for YOLOv9 and YOLOv26.
