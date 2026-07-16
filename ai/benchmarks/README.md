# AI-TDSS Final YOLO Benchmark Framework

## Status
PREPARED

## Purpose
This folder contains the final benchmark framework for comparing YOLO-based object detection models for OB/FVG detection.

## Detection Classes
- 0: order_block
- 1: fair_value_gap

## Benchmark Target Models
- YOLOv9
- YOLOv11
- YOLOv26

## Development Baseline
YOLOv8n has already been used as a temporary development baseline.

Best YOLOv8n development result:
- Method: Cumulative training
- Final test year: 2025
- Precision: 0.515
- Recall: 0.595
- mAP50: 0.543
- mAP50-95: 0.408

## Main Dataset
Cumulative benchmark dataset:
- ai/datasets/annotation/exports/cumulative_yolo_2020_2024/

Split:
- train: 2020-2024
- valid: 2020-2024 validation split
- test: 2025 unseen test

## Incremental Dataset
Incremental learning dataset:
- ai/datasets/annotation/exports/incremental_yolo/

Stages:
- base_2020
- inc_2021
- inc_2022
- inc_2023
- inc_2024
- final_test_2025

## Benchmark Metrics
Each model should be evaluated using:
- Precision
- Recall
- mAP50
- mAP50-95
- Per-class performance
- Confusion matrix
- Prediction visual samples

## Benchmark Rule
All final benchmark models must be evaluated on the same 2025 unseen test data.

## Important Note
YOLOv8n is not part of the final benchmark target. It is only used as a baseline reference.
