# Incremental YOLOv8n Development Test Result

## Status
PASS

## Purpose
This experiment validates the incremental YOLO training workflow for OB/FVG detection.

## Model
- Model: YOLOv8n
- Role: Temporary development baseline
- Training device: CPU
- Dataset: incremental_yolo
- Final evaluation split: final_test_2025

## Training Chain
- base_2020
- inc_2021
- inc_2022
- inc_2023
- inc_2024
- final_test_2025

## Final Test 2025 Result

| Class | Images | Instances | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|---:|---:|
| all | 150 | 150 | 0.447 | 0.576 | 0.501 | 0.345 |
| order_block | 63 | 75 | 0.485 | 0.478 | 0.457 | 0.305 |
| fair_value_gap | 63 | 75 | 0.409 | 0.675 | 0.545 | 0.384 |

## Interpretation
The incremental training workflow successfully completed all stages and produced valid final evaluation results on unseen 2025 data.

The result is acceptable as a development baseline, but not yet sufficient as a final benchmark result.

Fair Value Gap detection performs better than Order Block detection, likely because FVG has a clearer visual structure. Order Block detection remains more difficult because it depends more heavily on candle context and impulse confirmation.

## Limitations
- YOLOv8n is only a temporary baseline.
- Dataset size is still limited.
- Labels are generated using rule-based semi-automatic annotation.
- OB/FVG bounding boxes are visually small.
- Exact candle-index alignment is not yet fully integrated into training labels.
- Final benchmark models have not been tested yet.

## Next Steps
- Build cumulative baseline dataset.
- Train cumulative YOLOv8n baseline.
- Compare incremental vs cumulative performance on 2025 unseen test.
- Improve dataset and annotation quality.
- Run final benchmark using YOLOv9, YOLOv11, and YOLOv26.
