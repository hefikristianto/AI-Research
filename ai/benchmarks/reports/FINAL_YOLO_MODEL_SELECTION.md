# Final YOLO Detection Benchmark Comparison

## Final Test Results

| Model | Precision | Recall | mAP50 | mAP50-95 | Status |
|---|---:|---:|---:|---:|---|
| YOLOv8n Cumulative | 0.515 | 0.595 | 0.543 | 0.408 | Baseline |
| YOLO11n 50e | 0.537 | 0.668 | 0.583 | 0.449 | Best Recall |
| YOLO11n 100e | 0.529 | 0.640 | 0.566 | 0.424 | Overfit Indication |
| YOLO11s 50e | 0.591 | 0.593 | 0.590 | 0.452 | Selected |
| YOLO26n 50e | 0.502 | 0.567 | 0.515 | 0.392 | Rejected |
| YOLOv9-S 50e | 0.0315 | 0.907 | 0.135 | 0.0766 | Rejected |

## Selected Model

YOLO11s 50 epochs

Selection reasons:

1. Highest overall precision.
2. Highest overall mAP50.
3. Highest overall mAP50-95.
4. More balanced detection behavior than YOLOv9-S.
5. Successful OB-FVG pairing at confidence 0.25.
6. Successful OHLCV structural validation.
7. Direction match rate reached 95.83%.
8. Compatible with scoring v3.
9. Easier deployment through the Ultralytics ecosystem.
10. More stable dependency and runtime environment.

## Selected Detection Pipeline

Chart Image
-> YOLO11s 50e
-> Confidence Threshold 0.25
-> OB-FVG Pairing
-> OHLCV Structural Validation
-> Scoring v3
-> ACCEPT / REVIEW / WATCHLIST / REJECT

## Downstream Result

YOLO11s prediction at confidence 0.25:

- Total detections: 83
- OB-FVG pairs: 24
- OHLCV loaded: 24
- Direction matches: 23
- Direction match rate: 95.83%

Scoring v3:

- Average score: 0.7706
- Highest score: 0.8314
- Lowest score: 0.6135
- HIGH: 11
- MEDIUM: 12
- LOW: 1
- REJECTED: 0

Final decisions:

- ACCEPT: 11
- REVIEW: 12
- WATCHLIST: 1
- REJECT: 0

## Benchmark Conclusion

The YOLO detection benchmark is complete.

YOLO11s 50e is locked as the primary detection model for the next development stage.

The next stage is market-regime classification using a CNN model with three target classes:

bullish
bearish
sideways
