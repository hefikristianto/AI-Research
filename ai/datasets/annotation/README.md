# AI-TDSS Annotation System

Sprint: Annotation and Detection
Status: Production Scope Locked; Quality Improvement In Progress

---

# Overview

Folder ini berisi guideline, template, dan struktur export untuk proses anotasi dataset chart image AI-TDSS.

Dataset anotasi digunakan untuk training object detection model berbasis YOLO.

---

# Folder Structure

annotation/
+-- guidelines/
   +-- annotation_guideline.md
   +-- bounding_box_guideline.md
   +-- label_specification.md
   +-- yolo_label_format.md
   +-- annotation_split_plan.md
+-- examples/
+-- exports/
   +-- yolo/
       +-- dataset.yaml
       +-- images/
          +-- train/
          +-- valid/
          +-- test/
       +-- labels/
           +-- train/
           +-- valid/
           +-- test/
+-- tools/

---

# Supported Classes

| ID | Class Name |
|----|------------|
| 0 | order_block |
| 1 | fair_value_gap |

Liquidity, BOS/CHOCH, EQH/EQL, candle pattern, dan mitigation state dihitung dari canonical OHLCV dan bukan class YOLO produksi.

---

# Export Format

Annotation export menggunakan format YOLO:

class_id x_center y_center width height

Semua koordinat dinormalisasi dari 0 sampai 1.

---

# Current Status

Annotation guideline, export structure, semi-automatic labeling, cumulative/incremental dataset workflow, dan benchmark dua kelas sudah tersedia.

Pekerjaan aktif berikutnya adalah meningkatkan kualitas/review label OB/FVG dan menjaga hubungan box dengan candle index/time.
