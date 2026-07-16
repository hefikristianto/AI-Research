# YOLO11 Pairing Threshold Tuning Summary

## Result

| Model | Setting | Conf | Max X | Max Y | Detections | Pairs | HIGH | MEDIUM | LOW | Avg Score | Avg OB Conf | Avg FVG Conf | Highest |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| yolo11s | strict | 0.35 | 0.08 | 0.25 | 53 | 15 | 0 | 4 | 11 | 0.6262 | 0.4808 | 0.4861 | 0.6703 |
| yolo11s | balanced | 0.3 | 0.1 | 0.28 | 53 | 15 | 0 | 6 | 9 | 0.6355 | 0.4808 | 0.4861 | 0.6802 |
| yolo11s | loose | 0.25 | 0.12 | 0.3 | 53 | 15 | 0 | 6 | 9 | 0.6413 | 0.4808 | 0.4861 | 0.6863 |
| yolo11n | strict | 0.35 | 0.08 | 0.25 | 54 | 5 | 0 | 1 | 4 | 0.6351 | 0.3959 | 0.5730 | 0.7339 |
| yolo11n | balanced | 0.3 | 0.1 | 0.28 | 54 | 5 | 0 | 1 | 4 | 0.6435 | 0.3959 | 0.5730 | 0.7431 |
| yolo11n | loose | 0.25 | 0.12 | 0.3 | 54 | 5 | 0 | 1 | 4 | 0.6487 | 0.3959 | 0.5730 | 0.7487 |

## Notes

- strict uses the original pairing threshold.
- balanced slightly relaxes confidence and distance thresholds.
- loose is used only for diagnostic analysis, not final decision.