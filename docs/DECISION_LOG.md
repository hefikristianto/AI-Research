# Decision Log - AI-TDSS

---

# DEC-002 - Dataset Engineering Source and Structure

Date   : 2026-07-04
Sprint : Sprint 2 - Dataset Engineering
Status : Accepted

## Decision

AI-TDSS menggunakan raw OHLCV dataset yang diekspor dari MetaTrader 5 yang terhubung ke broker Valetax.

Dataset disusun berdasarkan struktur:

ai/datasets/raw/ohlcv/{PAIR}/{TIMEFRAME}/{YEAR}/

Pair yang digunakan:

- XAUUSD
- GBPUSD

Timeframe yang digunakan:

- M5
- M15
- H1
- H4

Tahun dataset:

- 2020
- 2021
- 2022
- 2023
- 2024
- 2025

## Reason

Struktur berbasis tahun dipilih karena:

- Export historical data dari MetaTrader 5 dapat terkena batasan jumlah bar.
- File per tahun lebih ringan dan mudah divalidasi.
- Struktur tahunan mendukung konsep incremental learning.
- Dataset dapat dievaluasi berdasarkan perubahan kondisi market setiap tahun.

## Impact

Dataset raw OHLCV tidak disimpan langsung ke GitHub karena ukuran file dapat membesar.

File yang disimpan ke GitHub:

- Metadata dataset
- Validation report
- Distribution report
- Dataset scripts
- Documentation

Raw CSV dan generated chart PNG disimpan secara lokal atau storage eksternal.

## Incremental Learning Strategy

Training awal menggunakan dataset tahun 2020.

Fine-tuning dilakukan secara bertahap menggunakan dataset tahun berikutnya:

- 2021
- 2022
- 2023
- 2024
- 2025

Strategi fine-tuning menggunakan replay sample dari tahun sebelumnya untuk mengurangi risiko catastrophic forgetting.
