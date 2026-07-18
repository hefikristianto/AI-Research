# Chapter 6 — AI Architecture

## 6.1 Design Principle

AI-TDSS memakai arsitektur hibrida. Tidak ada satu model yang dianggap cukup untuk membuat keputusan entry. Computer vision menghasilkan bukti visual, OHLCV menyediakan konteks kanonis, dan decision engine menerapkan fusion serta risk gate.

## 6.2 CNN Ensemble

CNN ensemble terdiri dari VGG11, VGG16, GoogLeNet, dan ResNet18. Setiap model menghasilkan probabilitas `bearish`, `bullish`, dan `sideways`. Weighted soft voting menggunakan validation Macro F1 sebagai sumber bobot.

Output minimum:

- predicted label;
- probability per class;
- confidence;
- entropy;
- weight dan version setiap component model;
- ensemble version.

Ensemble menentukan regime context. Ia tidak menentukan entry tanpa evidence lain.

## 6.3 YOLO Detection

Model produksi adalah YOLO11s 50 epoch dengan threshold produksi awal 0.25. Kelas produksi dikunci:

| ID | Class |
|---:|---|
| 0 | order_block |
| 1 | fair_value_gap |

YOLO menghasilkan bounding box dan confidence. Detection selanjutnya dipasangkan, divalidasi terhadap OHLCV, dan digunakan untuk visual explanation. Liquidity, supply/demand umum, BOS, CHOCH, EQH/EQL, mitigation, dan candle pattern bukan kelas YOLO produksi.

## 6.4 OHLCV Rule Engine

Fitur berikut dihitung dari urutan candle:

- swing high/low;
- equal high/equal low;
- liquidity level dan sweep;
- BOS dan CHOCH;
- candle pattern;
- ATR/volatility;
- higher-timeframe alignment;
- session context;
- zone invalidation dan risk-reward.

Setiap event rule-based harus menyimpan candle index/time, parameter rule, dan rules version agar dapat direproduksi.

## 6.5 Fusion and Decision

Fusion menggunakan staged gating:

1. validasi input dan metadata;
2. regime classification;
3. OB/FVG detection dan pairing;
4. canonical OHLCV mapping;
5. structure/liquidity validation;
6. HTF, volatility, dan session scoring;
7. price/risk conversion;
8. execution gate;
9. public decision mapping.

Confidence CNN dan YOLO tidak boleh disebut probabilitas profit. Final recommendation harus disertai reasons yang berasal dari evidence/gate.

## 6.6 Explainability

Explainability memiliki dua lapisan:

- visual: OB/FVG bounding boxes serta entry/SL/TP overlay;
- textual/structured: regime probability, structure evidence, risk metrics, blockers, warnings, dan reasons.

Annotated image tidak boleh menggambar fitur yang sebenarnya tidak dihitung atau menyembunyikan status provisional.

## 6.7 Model Lifecycle

Model dan rules memakai version terpisah. Satu analysis record menyimpan:

- CNN ensemble version;
- component checkpoint hashes/versions;
- YOLO version dan threshold;
- rules version;
- decision policy version;
- code commit bila tersedia.

Lifecycle incremental dijelaskan pada Chapter 12 dan kontrak mesin berada di [`config/project_contract.json`](../../../config/project_contract.json).
