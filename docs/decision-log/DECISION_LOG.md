# Decision Log - AI-TDSS

## Decision #001

| Item | Description |
|------|-------------|
| Date | 30-06-2026 |
| Decision | AI-TDSS dikembangkan sebagai Decision Support System, bukan Auto Trading System |
| Reason | Membatasi ruang lingkup penelitian, mengurangi risiko implementasi, memperjelas kontribusi sistem, dan memudahkan validasi hasil |
| Impact | Sistem hanya memberikan rekomendasi trading berupa entry, stop loss, take profit, status setup, dan alasan analisis. Sistem tidak melakukan eksekusi transaksi otomatis ke broker |

---

## Decision #003

| Item | Description |
|------|-------------|
| Date | 30-06-2026 |
| Decision | MASTER_SDD diubah menjadi dokumen induk yang menghubungkan seluruh chapter SDD |
| Reason | Mempermudah pengembangan dokumentasi, mengurangi konflik revisi, serta menjaga setiap chapter tetap fokus pada satu topik utama |
| Impact | Seluruh dokumentasi SDD menggunakan pendekatan modular dan setiap chapter disimpan pada file terpisah |

---

## Decision #004

| Item | Description |
|------|-------------|
| Date | 30-06-2026 |
| Decision | Dokumentasi dipisahkan menjadi tiga dokumen utama (SDD, ADD, dan TDD) |
| Reason | Memisahkan desain sistem, alasan arsitektur, dan implementasi teknis sehingga dokumentasi lebih mudah dipelihara dan digunakan selama penelitian |
| Impact | Seluruh keputusan arsitektur akan dicatat di ADD, sedangkan implementasi dicatat di TDD |

---

## Decision #005

| Item | Description |
|------|-------------|
| Date | 30-06-2026 |
| Decision | Core roadmap dikunci dan project masuk ke fase implementasi |
| Reason | Batas waktu 12 Juli membuat penambahan fitur baru harus dihentikan agar pengembangan tetap realistis |
| Impact | Fitur baru setelah tanggal ini masuk ke Future Development, bukan roadmap utama |

---

## Decision #006

| Item | Description |
|------|-------------|
| Date | 30-06-2026 |
| Decision | Istilah Zone Scoring tidak dijadikan inti sistem dan digantikan oleh Trade Decision Engine (TDE) |
| Reason | Zone Scoring hanya menilai kualitas zona, sedangkan sistem membutuhkan modul keputusan yang mempertimbangkan hasil YOLO, struktur pasar, liquidity, risk-reward, sesi market, news, watchlist state, dan histori performa |
| Impact | Seluruh output rekomendasi trading akan berasal dari Trade Decision Engine. Zone Strength Score tetap digunakan sebagai salah satu variabel internal, bukan sebagai modul utama |

---

## Decision #007

| Item | Description |
|------|-------------|
| Date | 18-07-2026 |
| Decision | GBPUSD dikunci sebagai pair penelitian dan target produk utama; XAUUSD menjadi pair penelitian sekunder |
| Reason | Satu domain utama diperlukan agar dataset, temporal evaluation, ablation, dan klaim akademik tetap fokus dan dapat dipertanggungjawabkan |
| Impact | Default upload adalah GBPUSD. Hasil XAUUSD harus dilaporkan terpisah dan tidak dicampur ke metrik utama tanpa stratifikasi |

---

## Decision #008

| Item | Description |
|------|-------------|
| Date | 18-07-2026 |
| Decision | Peran metode dipisahkan: CNN ensemble untuk regime, YOLO untuk OB/FVG dan visual explanation, OHLCV rules untuk liquidity/structure/candle pattern, dan TDE untuk keputusan entry |
| Reason | Confidence detector bukan probabilitas profit dan fitur temporal memiliki representasi yang lebih presisi pada OHLCV dibanding bounding box screenshot |
| Impact | Kelas YOLO produksi hanya `order_block` dan `fair_value_gap`. Liquidity, BOS/CHOCH, EQH/EQL, candle pattern, serta mitigation tidak menjadi kelas detector produksi |

---

## Decision #009

| Item | Description |
|------|-------------|
| Date | 18-07-2026 |
| Decision | Incremental learning menggunakan offline batch champion–challenger di laptop lokal dengan count/time/drift trigger dan minimum eligible batch |
| Reason | Online self-training per upload dapat memperkuat kesalahan model, menimbulkan leakage, dan menyulitkan rollback serta reproduksi penelitian |
| Impact | Prediksi mentah tidak menjadi ground truth. Candidate memakai verified outcome, replay, frozen holdout, walk-forward evaluation, lineage, dan promotion gate. GitHub Actions tidak menjalankan training berat |

---

## Decision #010

| Item | Description |
|------|-------------|
| Date | 18-07-2026 |
| Decision | Semua hasil analisis, termasuk WATCHLIST dan NO_TRADE, disimpan ke user-scoped journal dan dapat diekspor sebagai workbook Excel |
| Reason | Journal diperlukan sebagai audit trail, evaluasi tanpa survivorship bias, media pembelajaran pengguna, dan sumber feedback yang dapat diverifikasi |
| Impact | Analysis snapshot bersifat immutable; outcome disimpan terpisah. Workbook wajib memiliki Analyses, Trade_Outcomes, Model_Metadata, dan Definitions |

---

## Decision #011

| Item | Description |
|------|-------------|
| Date | 18-07-2026 |
| Decision | Entry siap digunakan hanya boleh diterbitkan jika screenshot berhasil dipasangkan dengan canonical OHLCV |
| Reason | Posisi pixel screenshot tidak cukup untuk menghasilkan harga entry, SL, dan TP yang presisi serta dapat diaudit |
| Impact | Metadata/OHLCV yang tidak lengkap menghasilkan WATCHLIST atau NO_TRADE. Analisis visual boleh ditampilkan untuk edukasi tetapi tidak disebut final entry recommendation |

---
