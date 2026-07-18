# AI-TDSS YOLO Label Specification

Version : v2.0
Sprint  : Annotation and Detection
Status  : Production Scope Locked

---

## Class List

| ID | Class Name | Description |
|----|------------|-------------|
| 0 | order_block | Area candle terakhir sebelum pergerakan impulsif yang menyebabkan break structure |
| 1 | fair_value_gap | Area imbalance antara candle yang tidak tertutup sempurna |

---

## YOLO Class Mapping

0 order_block
1 fair_value_gap

---

## Derived OHLCV Features

Feature berikut bukan class YOLO:

| Feature | Source |
|---|---|
| liquidity level/sweep | Swing dan equal level pada OHLCV |
| equal high/equal low | Perbandingan level swing dengan ATR tolerance |
| BOS/CHOCH | Urutan break structure pada candle |
| candle pattern | Relasi OHLC candle tunggal/berurutan |
| mitigation state | Interaksi harga setelah zona terbentuk |

Feature tersebut boleh digambar sebagai overlay setelah dihitung, tetapi tidak boleh dicatat sebagai hasil object detection.

---

## Notes

Label specification ini menjadi acuan dataset YOLO produksi dua kelas. Perluasan class memerlukan research question, guideline, reviewed annotations, dan benchmark baru; tidak boleh dilakukan hanya dengan mengubah `classes.txt`.
