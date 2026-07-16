# AI-TDSS Annotation Split Plan

Version : v1.0
Sprint  : Sprint 3 - Annotation System
Status  : Draft

---

# Objective

Dokumen ini menjelaskan rencana pembagian dataset anotasi untuk training YOLO.

---

# Split Ratio

Dataset akan dibagi menjadi:

- Train : 70%
- Valid : 20%
- Test  : 10%

---

# Split Strategy

Split dilakukan dengan mempertimbangkan:

- Pair
- Timeframe
- Year

Tujuan split adalah agar dataset tidak terlalu bias terhadap satu pair, satu timeframe, atau satu tahun tertentu.

---

# Recommended Strategy

## Train Set

Digunakan untuk training model.

Berisi mayoritas chart dari:

- XAUUSD
- GBPUSD
- M5
- M15
- H1
- H4
- 2020 sampai 2024

## Validation Set

Digunakan untuk evaluasi saat training.

Berisi subset chart dari berbagai pair, timeframe, dan tahun.

## Test Set

Digunakan untuk evaluasi akhir.

Test set tidak boleh digunakan selama training.

Disarankan memasukkan data tahun 2025 sebagai bagian penting test/incremental evaluation karena tahun 2025 merepresentasikan data paling baru.

---

# Notes

Karena AI-TDSS juga menargetkan incremental learning, split dataset perlu mendukung evaluasi per tahun.

Dataset dapat dibuat dalam dua mode:

1. Standard YOLO split
2. Yearly incremental split

---

# Standard YOLO Split

Digunakan untuk training awal object detection.

Format:

- train
- valid
- test

---

# Yearly Incremental Split

Digunakan untuk skenario pembelajaran bertahap.

Format:

- base_train_2020
- incremental_2021
- incremental_2022
- incremental_2023
- incremental_2024
- final_test_2025

---

# Current Status

Split belum dilakukan karena dataset belum dianotasi.
