# Chapter 8 — Labeling System

## 8.1 Production YOLO Scope

Dataset YOLO produksi hanya memiliki dua class:

| ID | Class | Label type |
|---:|---|---|
| 0 | order_block | Bounding box |
| 1 | fair_value_gap | Bounding box |

Class mapping tersebut harus sama pada metadata, dataset YAML, training config, model output, dan backend service.

## 8.2 Non-YOLO Features

Liquidity level/sweep, equal high/low, BOS, CHOCH, candle pattern, volatility, session, dan mitigation state dihitung dari OHLCV. Fitur tersebut boleh divisualisasikan sebagai overlay, tetapi overlay tidak boleh disebut hasil object detection YOLO.

## 8.3 Annotation Source

Semi-automatic rule labeling dapat digunakan untuk menghasilkan kandidat awal. Data evaluation dan setiap batch update YOLO membutuhkan quality review. Review minimal memeriksa:

- class correctness;
- box localization;
- arah OB/FVG;
- duplikasi;
- ambiguous/low-visibility object;
- hubungan dengan candle index/time;
- split dan potensi leakage.

## 8.4 Update Policy

Outcome trade bukan label object detection. Update YOLO hanya dapat memakai screenshot dengan bounding box OB/FVG yang direview. Perubahan class list memerlukan:

1. revisi research question;
2. revisi project contract;
3. labeling guideline baru;
4. inter-annotator agreement study;
5. benchmark baru yang tidak dicampur dengan baseline dua kelas.

Guideline rinci berada di [`ai/datasets/annotation/guidelines`](../../../ai/datasets/annotation/guidelines).
