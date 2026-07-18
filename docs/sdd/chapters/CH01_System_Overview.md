# Chapter 1 — System Overview

## 1.1 Purpose

AI-TDSS adalah sistem pendukung keputusan trading berbasis web yang membantu pengguna mengevaluasi peluang entry dari screenshot market. Sistem memberikan rekomendasi, parameter risiko, penjelasan, dan visualisasi zona; sistem tidak mengeksekusi transaksi otomatis.

Pair penelitian utama adalah **GBPUSD** dengan timeframe M5, M15, H1, dan H4. XAUUSD dipertahankan sebagai pair penelitian sekunder dan hasilnya harus dilaporkan terpisah dari klaim utama GBPUSD.

## 1.2 User Goal

Pengguna dapat:

1. mengunggah screenshot chart;
2. memilih pair dan timeframe serta memberikan waktu chart;
3. menerima status `BUY`, `SELL`, `WATCHLIST`, atau `NO_TRADE`;
4. melihat entry, stop loss, take profit, risk-reward, blockers, warnings, dan alasan;
5. melihat ulang gambar dengan bounding box OB/FVG;
6. menyimpan hasil ke journal;
7. mengisi outcome trade;
8. mengunduh journal dalam workbook Excel.

## 1.3 Product Boundary

AI-TDSS merupakan decision support system. Pengguna tetap menjadi pengambil keputusan akhir. Sistem tidak:

- membuka atau menutup order broker;
- menjamin profit;
- menerbitkan entry siap digunakan tanpa pasangan OHLCV kanonis;
- melatih model langsung dari prediksi yang belum diverifikasi;
- menggunakan GitHub Actions untuk training model berat.

## 1.4 Core Capabilities

| Capability | Ringkasan |
|---|---|
| Visual analysis | CNN ensemble membaca regime; YOLO mendeteksi OB/FVG |
| Market context | OHLCV menghitung structure, liquidity, candle pattern, HTF, volatility, dan session |
| Decision support | Trade Decision Engine menerapkan fusion, scoring, risk, dan execution gate |
| Explainability | Annotated chart dan reason codes menjelaskan rekomendasi |
| Journal | Semua analisis dan outcome disimpan per pengguna |
| Adaptation | Drift monitoring dan offline batch incremental learning dengan champion–challenger |

## 1.5 Success Definition

Keberhasilan proyek tidak hanya diukur dari accuracy CNN atau mAP YOLO. Sistem dinyatakan siap ketika:

- hasil model pada temporal holdout dapat direproduksi;
- entry end-to-end memiliki evaluation report yang lengkap;
- setiap rekomendasi dapat ditelusuri ke input, model version, rules version, dan alasan;
- annotated image selalu tersedia saat deteksi berhasil;
- journal dan Excel menjaga integritas record;
- incremental candidate tidak dipromosikan bila merusak performa atau risk metric.

Kontrak kanonis berada di [`config/project_contract.json`](../../../config/project_contract.json), sedangkan metodologi penelitian berada di [`AI_TDSS_RESEARCH_SYNTHESIS.md`](../../research/AI_TDSS_RESEARCH_SYNTHESIS.md).
