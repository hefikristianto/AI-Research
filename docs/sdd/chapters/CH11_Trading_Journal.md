# Chapter 11 — Trading Journal

## 11.1 Purpose

Trading journal adalah audit trail produk dan sumber evaluasi penelitian. Setiap analisis disimpan, termasuk `WATCHLIST` dan `NO_TRADE`. Penyimpanan hanya pada trade yang diambil atau profit akan menciptakan selection/survivorship bias.

## 11.2 Data Model

Snapshot analisis awal bersifat immutable. Outcome dan feedback disimpan sebagai record terpisah yang merujuk `analysis_id`.

### Analysis snapshot

| Group | Field minimum |
|---|---|
| Identity | analysis_id, user_id, created_at_utc |
| Input | image reference/hash, pair, timeframe, chart_datetime |
| CNN | label, probabilities, confidence, entropy, ensemble_version |
| YOLO | detections, threshold, model_version, annotated_image_reference |
| Context | structure, liquidity, volatility, session, rules_version |
| Decision | decision, execution_status, entry, SL, TP, RR, order_type |
| Explanation | blockers, warnings, reasons |
| Lineage | pipeline_version, decision_policy_version, code_commit |

### Outcome/feedback

| Group | Field minimum |
|---|---|
| Identity | outcome_id, analysis_id, recorded_at_utc |
| Execution | taken/not_taken, actual_entry, actual_exit |
| Result | win/loss/breakeven/expired, pnl, pnl_r |
| Verification | source, verification_status, verified_at_utc |
| Learning | consent/status, eligibility_status, exclusion_reason, batch_id |

## 11.3 Excel Export

Workbook per pengguna wajib berisi:

| Sheet | Isi |
|---|---|
| Analyses | Seluruh analysis snapshot dalam bentuk tabular |
| Trade_Outcomes | Outcome dan feedback yang terhubung ke analysis_id |
| Model_Metadata | Versi model/rules/policy yang muncul pada export |
| Definitions | Definisi kolom, timezone, enum, dan disclaimer |

Ketentuan export:

- hanya record milik authenticated user;
- filter aktif dicantumkan pada workbook;
- timestamp diekspor dalam UTC dan format yang konsisten;
- blockers/warnings/reasons tidak dibuang;
- nomor harga tidak dibulatkan secara destruktif;
- formula Excel tidak digunakan untuk data input yang tidak dipercaya;
- file name memiliki rentang tanggal atau export timestamp.

## 11.4 Feedback Eligibility

Sebuah journal row tidak otomatis menjadi training data. Eligibility membutuhkan metadata lengkap, OHLCV match, outcome terverifikasi, deduplication, leakage check, dan quality gate. Keputusan pengguna mengikuti atau mengabaikan sinyal tidak boleh dianggap sebagai label benar/salah model.

## 11.5 Privacy and Integrity

- Row Level Security atau equivalent user filter wajib aktif.
- Original analysis snapshot tidak boleh berubah ketika outcome diperbarui.
- Export dan update outcome harus menggunakan user identity dari token, bukan user ID bebas dari client.
- Penghapusan/retention data mengikuti kebijakan yang dapat diaudit.
