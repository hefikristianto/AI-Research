# AI-TDSS Benchmark Command Templates

## Dataset
Cumulative dataset:
ai/datasets/annotation/exports/cumulative_yolo_2020_2024/dataset.yaml

Final test:
split=test

---

# YOLOv8n Reference Baseline

Already completed.

Result:
- Precision: 0.515
- Recall: 0.595
- mAP50: 0.543
- mAP50-95: 0.408

---

# YOLOv9 Benchmark Template

Training command placeholder:

    yolo detect train model=PATH_TO_YOLOV9_MODEL data=ai/datasets/annotation/exports/cumulative_yolo_2020_2024/dataset.yaml epochs=100 imgsz=640 batch=4 workers=0 device=cpu patience=15 project=ai/benchmarks/runs name=yolov9_cumulative_2020_2024

Final test command placeholder:

    yolo detect val model=ai/benchmarks/runs/yolov9_cumulative_2020_2024/weights/best.pt data=ai/datasets/annotation/exports/cumulative_yolo_2020_2024/dataset.yaml split=test imgsz=640 batch=4 workers=0 device=cpu project=ai/benchmarks/runs name=yolov9_final_test_2025

---

# YOLOv11 Benchmark Template

Training command placeholder:

    yolo detect train model=PATH_TO_YOLOV11_MODEL data=ai/datasets/annotation/exports/cumulative_yolo_2020_2024/dataset.yaml epochs=100 imgsz=640 batch=4 workers=0 device=cpu patience=15 project=ai/benchmarks/runs name=yolov11_cumulative_2020_2024

Final test command placeholder:

    yolo detect val model=ai/benchmarks/runs/yolov11_cumulative_2020_2024/weights/best.pt data=ai/datasets/annotation/exports/cumulative_yolo_2020_2024/dataset.yaml split=test imgsz=640 batch=4 workers=0 device=cpu project=ai/benchmarks/runs name=yolov11_final_test_2025

---

# YOLOv26 Benchmark Template

Training command placeholder:

    yolo detect train model=PATH_TO_YOLOV26_MODEL data=ai/datasets/annotation/exports/cumulative_yolo_2020_2024/dataset.yaml epochs=100 imgsz=640 batch=4 workers=0 device=cpu patience=15 project=ai/benchmarks/runs name=yolov26_cumulative_2020_2024

Final test command placeholder:

    yolo detect val model=ai/benchmarks/runs/yolov26_cumulative_2020_2024/weights/best.pt data=ai/datasets/annotation/exports/cumulative_yolo_2020_2024/dataset.yaml split=test imgsz=640 batch=4 workers=0 device=cpu project=ai/benchmarks/runs name=yolov26_final_test_2025

---

# Notes

The exact model paths depend on the implementation or repository used for each YOLO version.

Before running final benchmark:
- confirm model availability
- confirm compatible training command
- confirm package/environment
- avoid mixing different dataset versions
