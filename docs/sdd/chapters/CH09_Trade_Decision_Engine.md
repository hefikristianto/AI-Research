# Chapter 9
# Trade Decision Engine

## Status

| Section | Status |
|---------|--------|
| 9.1 Overview | REVIEW |
| 9.2 Objectives | TODO |
| 9.3 Design Philosophy | TODO |
| 9.4 Main Pipeline | TODO |
| 9.5 Input Module | TODO |
| 9.6 Internal Variables | TODO |
| 9.7 Decision States | TODO |
| 9.8 Trade Decision Logic | TODO |
| 9.9 Trade Validation Layer | TODO |
| 9.10 Confidence Calculation | TODO |
| 9.11 Output Structure | TODO |
| 9.12 Watchlist Decision | TODO |
| 9.13 Journal Integration | TODO |
| 9.14 Incremental Learning Feedback | TODO |
| 9.15 Performance Evaluation | TODO |
| 9.16 Chapter Summary | TODO |

---

# 9.1 Overview

## Purpose

Trade Decision Engine (TDE) merupakan modul inti pada AI-TDSS yang bertanggung jawab mengubah hasil analisis teknikal menjadi rekomendasi trading yang dapat digunakan sebagai dasar pengambilan keputusan oleh pengguna.

Berbeda dengan model object detection yang hanya mampu mengenali objek visual pada chart, TDE melakukan proses analisis lanjutan dengan mempertimbangkan berbagai informasi yang berasal dari beberapa modul lain sebelum menghasilkan keputusan akhir.

---

## Background

Model Computer Vision seperti YOLO memiliki kemampuan mendeteksi objek visual Order Block (OB) dan Fair Value Gap (FVG). Liquidity, BOS/CHOCH, serta candle pattern dihitung dari OHLCV kanonis. Seluruh bukti tersebut belum cukup secara individual untuk menghasilkan keputusan trading.

Sebuah zona yang berhasil dideteksi dengan confidence tinggi belum tentu layak dijadikan area entry karena masih dipengaruhi oleh berbagai faktor lain, seperti arah trend yang lebih besar, struktur pasar, kondisi sesi perdagangan, volatilitas akibat berita ekonomi, serta kelayakan risk-reward.

Apabila sistem hanya mengandalkan hasil deteksi visual, maka kemungkinan menghasilkan sinyal trading yang kurang akurat akan meningkat.

---

## Problem Statement

Permasalahan utama yang ingin diselesaikan oleh Trade Decision Engine adalah bagaimana mengubah hasil deteksi visual menjadi keputusan trading yang lebih objektif, konsisten, dan dapat dipertanggungjawabkan.

Tanpa adanya modul pengambilan keputusan, sistem hanya mampu menunjukkan lokasi zona tanpa memberikan informasi apakah zona tersebut layak digunakan sebagai entry, perlu dipantau lebih lanjut, atau sebaiknya diabaikan.

---

## Proposed Solution

Untuk mengatasi permasalahan tersebut, AI-TDSS mengimplementasikan Trade Decision Engine sebagai lapisan pengambilan keputusan utama.

Trade Decision Engine menggabungkan berbagai hasil analisis yang berasal dari beberapa modul, seperti:

- YOLO Detection Engine
- Market Structure Engine
- Zone Filtering Engine
- Risk Management Module
- Market Session Module
- News Condition Module
- Trading Journal Module

Seluruh informasi tersebut diproses secara bertahap sehingga menghasilkan rekomendasi trading yang lebih komprehensif dibandingkan hanya menggunakan hasil object detection.

---

## Position in System Architecture

Pada arsitektur AI-TDSS, Trade Decision Engine berada setelah proses deteksi dan analisis struktur pasar.

Diagram sederhananya adalah sebagai berikut.

```text
Screenshot
      │
      ▼
YOLO Detection
      │
      ▼
Zone Filtering
      │
      ▼
Market Structure Engine
      │
      ▼
Trade Decision Engine
      │
      ▼
Trade Validation Layer
      │
      ▼
Trading Recommendation
```

---

## 9.4 Main Pipeline

Trade Decision Engine bekerja berdasarkan pipeline analisis bertingkat sehingga keputusan tidak hanya bergantung pada hasil deteksi visual.

    Screenshot
          │
          ▼
    YOLO Detection
          │
          ▼
    Zone Filtering
          │
          ▼
    Market Structure Engine
          │
          ▼
    Trade Decision Engine
          │
          ▼
    Trade Validation Layer
          │
          ▼
    Trading Recommendation
          │
          ▼
    Trading Journal
          │
          ▼
    Incremental Learning

Pipeline tersebut memastikan bahwa setiap rekomendasi telah melewati proses validasi sebelum ditampilkan kepada pengguna.

---

## 9.5 Input Module

Trade Decision Engine menerima data dari beberapa modul lain yang telah diproses sebelumnya.

| Module | Data |
|---------|------|
| YOLO Detection | Order Block, Fair Value Gap, Bounding Box, Confidence |
| Zone Filtering | Fresh Zone, Mitigated Zone, Overlap Result |
| Market Structure Engine | Trend, BOS, CHoCH, HH, HL, LH, LL |
| Metadata Detection | Pair, Timeframe, Device |
| Risk Module | Entry, Stop Loss, Take Profit, Risk Reward |
| Session Module | Asia, London, New York, Overlap |
| News Module | Normal, Pre-News, During-News, Post-News |
| Trading Journal | Historical Performance |

Seluruh data tersebut akan diproses secara bersamaan untuk menghasilkan keputusan trading.

---

## 9.6 Internal Variables

Trade Decision Engine menggunakan beberapa variabel internal sebagai dasar pengambilan keputusan.

| Variable | Description |
|----------|-------------|
| detection_confidence | Confidence hasil deteksi YOLO |
| zone_strength_score | Skor kualitas zona |
| trend_alignment_score | Kesesuaian trend H4, H1, dan M15 |
| structure_confirmation | Konfirmasi BOS atau CHoCH |
| liquidity_confirmation | Status Liquidity Sweep |
| risk_reward_score | Penilaian Risk Reward |
| session_score | Penilaian sesi market |
| news_risk_score | Risiko kondisi news |
| historical_score | Performa setup serupa dari Trading Journal |

Variabel-variabel tersebut akan digunakan pada proses perhitungan Trade Decision Engine sebelum menghasilkan rekomendasi akhir.

---

## End of Section 9.4 - 9.6


---

## 9.7 Decision States

Trade Decision Engine menghasilkan empat kemungkinan keputusan sebagai output akhir sistem.

| Status | Description |
|--------|-------------|
| BUY | Setup memenuhi seluruh syarat untuk membuka posisi beli. |
| SELL | Setup memenuhi seluruh syarat untuk membuka posisi jual. |
| WATCHLIST | Setup memiliki potensi, namun masih membutuhkan konfirmasi tambahan. |
| NO_TRADE | Setup tidak memenuhi syarat sehingga tidak direkomendasikan untuk melakukan transaksi. |

Keputusan tersebut akan ditampilkan kepada pengguna beserta alasan dan parameter trading yang mendukung hasil rekomendasi.

---

## 9.8 Trade Decision Logic

Trade Decision Engine melakukan evaluasi terhadap seluruh hasil analisis yang diperoleh dari modul sebelumnya.

Proses pengambilan keputusan dilakukan dengan urutan sebagai berikut.

    Valid Zone
          │
          ▼
    Trend Alignment
          │
          ▼
    BOS / CHoCH
          │
          ▼
    Liquidity Confirmation
          │
          ▼
    Risk Reward Validation
          │
          ▼
    Session Validation
          │
          ▼
    News Validation
          │
          ▼
    Trade Confidence
          │
          ▼
    Final Recommendation

Apabila salah satu proses validasi gagal memenuhi batas minimum yang telah ditentukan, maka sistem dapat mengubah rekomendasi menjadi WATCHLIST atau NO_TRADE.

---

## 9.9 Trade Validation Layer

Trade Validation Layer merupakan lapisan validasi terakhir sebelum hasil analisis diberikan kepada pengguna.

Lapisan ini bertujuan untuk mengurangi kemungkinan munculnya rekomendasi trading pada kondisi market yang memiliki risiko tinggi.

Beberapa kondisi yang diperiksa meliputi:

- High Impact News
- Trend Higher Timeframe berlawanan
- Zona sudah mitigated
- Risk Reward di bawah batas minimum
- Volatilitas market terlalu tinggi
- Spread abnormal
- Harga terlalu jauh dari zona entry

Apabila salah satu kondisi tersebut tidak memenuhi syarat, maka sistem dapat mengubah hasil rekomendasi menjadi WATCHLIST atau NO_TRADE meskipun Trade Decision Engine sebelumnya menghasilkan BUY atau SELL.

Trade Validation Layer berfungsi sebagai mekanisme keamanan agar sistem tidak hanya mengandalkan hasil deteksi visual maupun nilai confidence semata.

---

## End of Section 9.7 - 9.9


---

## 9.10 Confidence Calculation

Trade Confidence merupakan nilai yang menunjukkan tingkat keyakinan sistem terhadap rekomendasi trading yang dihasilkan.

Berbeda dengan YOLO Confidence yang hanya mengukur tingkat keyakinan model dalam mendeteksi objek visual, Trade Confidence dihitung berdasarkan kombinasi beberapa faktor analisis.

| Factor | Description |
|---------|-------------|
| YOLO Confidence | Tingkat keyakinan deteksi objek |
| Zone Strength | Kualitas zona hasil filtering |
| Trend Alignment | Kesesuaian arah trend |
| Structure Confirmation | Konfirmasi BOS atau CHoCH |
| Liquidity Confirmation | Validasi Liquidity Sweep |
| Risk Reward | Kelayakan Risk Reward |
| Session Condition | Kondisi sesi market |
| News Condition | Kondisi berita ekonomi |

Nilai Trade Confidence digunakan sebagai salah satu indikator pendukung dan tidak dijadikan satu-satunya dasar pengambilan keputusan.

---

## 9.11 Output Structure

Setiap hasil analisis dari Trade Decision Engine menghasilkan informasi sebagai berikut.

| Output | Description |
|---------|-------------|
| Pair | XAUUSD atau GBPUSD |
| Timeframe | H4, H1, atau M15 |
| Recommendation | BUY, SELL, WATCHLIST, atau NO_TRADE |
| Entry Price | Harga entry |
| Stop Loss | Harga Stop Loss |
| Take Profit | Harga Take Profit |
| Risk Reward | Nilai Risk Reward |
| Trade Confidence | Tingkat keyakinan rekomendasi |
| Zone Strength Score | Nilai kualitas zona |
| Session | Asia, London, New York, Overlap |
| News Condition | Normal, Pre-News, During-News, Post-News |
| Recommendation Reason | Alasan rekomendasi sistem |

Output tersebut akan ditampilkan pada dashboard dan disimpan ke Trading Journal.

---

## 9.12 Watchlist Decision

Status WATCHLIST diberikan apabila setup memiliki potensi untuk menjadi peluang trading namun belum memenuhi seluruh syarat entry.

Beberapa kondisi yang dapat menghasilkan status WATCHLIST antara lain:

- Harga belum memasuki area zona.
- Belum terjadi BOS atau CHoCH.
- Belum terjadi Liquidity Sweep.
- Risk Reward belum memenuhi batas minimum.
- Menunggu sesi market yang lebih aktif.
- Menunggu kondisi news selesai.

Status WATCHLIST memungkinkan pengguna melakukan analisis lanjutan tanpa harus kehilangan peluang trading.

---

## 9.13 Journal Integration

Setiap rekomendasi yang dihasilkan oleh Trade Decision Engine akan disimpan ke Trading Journal.

Informasi yang disimpan meliputi:

- Pair
- Timeframe
- Recommendation
- Entry Price
- Stop Loss
- Take Profit
- Risk Reward
- Trade Confidence
- Session
- News Condition
- Final Result
- Profit atau Loss

Trading Journal digunakan sebagai media evaluasi performa sistem sekaligus sumber data untuk proses Incremental Learning.

---

## End of Section 9.10 - 9.13


---

## 9.14 Incremental Learning Feedback

Trade Decision Engine terhubung dengan modul Incremental Learning melalui Trading Journal.

Setiap hasil analisis yang telah memiliki outcome akan digunakan sebagai data evaluasi untuk meningkatkan performa sistem pada proses pembelajaran berikutnya.

Data yang dapat digunakan sebagai feedback meliputi:

- Pair
- Timeframe
- Screenshot Chart
- Detected Zone
- Recommendation
- Trade Confidence
- Zone Strength Score
- Final Trade Result
- Profit atau Loss
- Session
- News Condition

Proses Incremental Learning tidak dilakukan setiap kali terdapat trade baru, tetapi dilakukan secara berkala menggunakan mekanisme batch-based incremental learning agar proses pembelajaran tetap stabil dan efisien.

---

## 9.15 Performance Evaluation

Kinerja Trade Decision Engine dievaluasi menggunakan beberapa indikator performa.

| Metric | Description |
|--------|-------------|
| Win Rate | Persentase transaksi yang menghasilkan keuntungan |
| Profit Factor | Perbandingan total profit terhadap total loss |
| Average Risk Reward | Nilai rata-rata Risk Reward |
| Maximum Drawdown | Penurunan ekuitas terbesar |
| Precision | Ketepatan rekomendasi sistem |
| Recall | Kemampuan sistem mendeteksi setup yang valid |
| F1-Score | Keseimbangan Precision dan Recall |
| Total Trade | Jumlah transaksi yang dianalisis |
| No Trade Rate | Persentase kondisi yang ditolak sistem |
| Watchlist Conversion | Persentase Watchlist yang berubah menjadi BUY atau SELL |

Hasil evaluasi digunakan sebagai dasar analisis performa sistem pada penelitian serta sebagai acuan pengembangan model pada versi berikutnya.

---

## 9.16 Chapter Summary

Trade Decision Engine merupakan komponen utama pada AI-TDSS yang bertugas mengubah hasil deteksi visual menjadi rekomendasi trading yang objektif.

Melalui kombinasi hasil YOLO Detection, Zone Filtering, Market Structure Engine, Trade Validation Layer, serta evaluasi Risk Management, sistem mampu menghasilkan keputusan BUY, SELL, WATCHLIST, atau NO_TRADE yang lebih dapat dipertanggungjawabkan.

Selain menghasilkan rekomendasi trading, seluruh hasil analisis juga disimpan pada Trading Journal sebagai media evaluasi performa dan sumber data bagi mekanisme Incremental Learning.

Dengan demikian, Trade Decision Engine tidak hanya berfungsi sebagai modul pengambilan keputusan, tetapi juga sebagai penghubung antara proses analisis, evaluasi, dan pengembangan sistem secara berkelanjutan.

---

## End of Chapter 9
