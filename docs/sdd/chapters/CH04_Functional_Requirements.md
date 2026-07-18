# Chapter 4 — Functional Requirements

## 4.1 Analysis

| ID | Requirement | Priority | Acceptance summary |
|---|---|---|---|
| FR-001 | Upload chart PNG/JPG/WEBP maksimal 10 MB | P0 | Invalid type/size ditolak sebelum inference |
| FR-002 | Pair default GBPUSD | P0 | Form upload dan API menyimpan GBPUSD secara eksplisit |
| FR-003 | Metadata pair, timeframe, dan chart time tersedia | P0 | Entry diblokir bila canonical OHLCV tidak dapat dipasangkan |
| FR-004 | CNN ensemble menghasilkan regime probabilities | P0 | Label, confidence, entropy, dan model version tersedia |
| FR-005 | YOLO mendeteksi OB/FVG | P0 | Hanya dua kelas produksi dan threshold tercatat |
| FR-006 | Sistem menghitung structure/liquidity dari OHLCV | P0 | Swing, sweep, BOS/CHOCH, dan evidence candle dapat diaudit |
| FR-007 | Sistem menghasilkan keputusan publik | P0 | Salah satu BUY/SELL/WATCHLIST/NO_TRADE |
| FR-008 | BUY/SELL membawa entry/SL/TP/RR | P0 | Semua field numerik konsisten dengan arah dan risk gate |
| FR-009 | Sistem menyertakan blockers/warnings/reasons | P0 | UI tidak hanya menampilkan confidence |
| FR-010 | Sistem mengembalikan annotated chart | P0 | Bounding box OB/FVG terlihat dan sesuai response |

## 4.2 Journal and Feedback

| ID | Requirement | Priority | Acceptance summary |
|---|---|---|---|
| FR-011 | Setiap analisis disimpan per pengguna | P0 | Termasuk WATCHLIST dan NO_TRADE |
| FR-012 | Snapshot analisis bersifat immutable | P0 | Outcome baru tidak menimpa hasil inference awal |
| FR-013 | Pengguna dapat memperbarui outcome | P0 | Outcome memiliki timestamp dan source |
| FR-014 | Journal dapat difilter | P1 | Pair, timeframe, decision, tanggal, dan outcome |
| FR-015 | Journal dapat diunduh sebagai Excel | P0 | Workbook memiliki empat sheet wajib |
| FR-016 | Model lineage tersimpan | P0 | CNN, YOLO, rules, policy, dan pipeline version tersedia |
| FR-017 | Feedback memiliki eligibility status | P0 | Tidak semua upload otomatis masuk training pool |

## 4.3 Incremental Learning

| ID | Requirement | Priority | Acceptance summary |
|---|---|---|---|
| FR-018 | Drift monitoring berjalan pada prediction batch | P1 | Report memiliki sample count, score, status, dan recommendation |
| FR-019 | Trigger count/time/drift dapat dikonfigurasi | P1 | Time/drift tetap memerlukan minimum eligible batch |
| FR-020 | Training candidate hanya berjalan lokal | P0 | Tidak ada GitHub workflow yang menjalankan model training |
| FR-021 | Replay tersedia untuk mengurangi forgetting | P1 | Replay manifest dapat direproduksi |
| FR-022 | Candidate dievaluasi sebagai challenger | P0 | Champion tidak ditimpa sebelum promotion gate lulus |
| FR-023 | YOLO update membutuhkan reviewed boxes | P0 | Outcome trade tidak digunakan sebagai label bounding box |

## 4.4 Security and User Isolation

| ID | Requirement | Priority | Acceptance summary |
|---|---|---|---|
| FR-024 | Endpoint journal memerlukan authentication | P0 | Request tanpa token ditolak |
| FR-025 | Record dan export terisolasi per user | P0 | User A tidak dapat membaca export User B |
| FR-026 | Penggunaan data untuk training dapat diaudit | P0 | Consent/source dan eligibility disimpan |

Detail field output journal dijelaskan pada Chapter 11. Trigger dan promotion gate dijelaskan pada Chapter 12.
