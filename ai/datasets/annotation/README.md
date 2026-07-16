# AI-TDSS Annotation System

Sprint: Sprint 3 - Annotation System  
Status: In Progress

---

# Overview

Folder ini berisi guideline, template, dan struktur export untuk proses anotasi dataset chart image AI-TDSS.

Dataset anotasi digunakan untuk training object detection model berbasis YOLO.

---

# Folder Structure

annotation/
+-- guidelines/
¦   +-- annotation_guideline.md
¦   +-- bounding_box_guideline.md
¦   +-- label_specification.md
¦   +-- yolo_label_format.md
¦   +-- annotation_split_plan.md
+-- examples/
+-- exports/
¦   +-- yolo/
¦       +-- dataset.yaml
¦       +-- images/
¦       ¦   +-- train/
¦       ¦   +-- valid/
¦       ¦   +-- test/
¦       +-- labels/
¦           +-- train/
¦           +-- valid/
¦           +-- test/
+-- tools/

---

# Supported Classes

| ID | Class Name |
|----|------------|
| 0 | order_block |
| 1 | fair_value_gap |
| 2 | liquidity |
| 3 | supply |
| 4 | demand |
| 5 | bos |
| 6 | choch |
| 7 | equal_high |
| 8 | equal_low |
| 9 | mitigation |

---

# Export Format

Annotation export menggunakan format YOLO:

class_id x_center y_center width height

Semua koordinat dinormalisasi dari 0 sampai 1.

---

# Current Status

Annotation guideline sudah dibuat.

Export structure untuk YOLO sudah disiapkan.

Dataset belum dianotasi.
