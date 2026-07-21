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

## Decision #012

| Item | Description |
|------|-------------|
| Date | 21-07-2026 |
| Decision | Kandidat plot-aware mapping E2.2 dibekukan untuk tepat satu paired comparison GBPUSD 2025; full-image tetap menjadi default produksi sampai hasil final diinterpretasikan |
| Reason | A/B development 2024 dengan 165 chart memiliki lineage identik dan nol request failure. Error indeks berpasangan membaik, sedangkan seluruh perubahan keputusan dapat dijelaskan oleh hilangnya blocker `LOW_MAPPING_CONFIDENCE` tanpa perubahan detector, pairing, atau threshold eksekusi |
| Impact | Konstanta geometry, seed, threshold, context size, dan aturan interpretasi dikunci dalam kontrak machine-readable. Kedua run 2025 harus identik kecuali flag plot-aware, hanya boleh diselesaikan sekali per mode, dan hasilnya tidak boleh digunakan untuk tuning ulang E2.2 |

---

## Decision #013

| Item | Description |
|------|-------------|
| Date | 21-07-2026 |
| Decision | Plot-aware mapping dipromosikan untuk chart kanonis dan menjadi policy mapping E2.3; full-image tetap menjadi default API untuk screenshot pengguna umum dan fallback saat geometry tidak pasti |
| Reason | Frozen comparison GBPUSD 2025 menyelesaikan 165/165 request per mode dengan lineage identik dan upstream coverage yang sama. Pada 35 match kanonis, mean error OB turun dari 2,714 ke 0 dan FVG dari 2,771 ke 0,971. Review tujuh kasus per mode memverifikasi 14 PNG dan menunjukkan box identik; perubahan keputusan terbatas pada banner. Variasi screenshot TradingView/MT5 eksternal belum termasuk scope validasi |
| Impact | E2.3 wajib menjalankan kedua policy arm dengan plot-aware mapping yang sama serta full-image fallback. Konstanta E2.2 tidak dituning ulang. Default upload umum baru boleh dipertimbangkan setelah validasi lintas tema, chrome, crop, perangkat, dan aspect ratio; satu kandidat SELL yang muncul belum boleh diklaim akurat atau profitable tanpa outcome terverifikasi |

---

## Decision #014

| Item | Description |
|------|-------------|
| Date | 21-07-2026 |
| Decision | Populasi E2.3 dibentuk dari dua target UTC per observed GBPUSD trading day pada 2020–2024; timestamp MT5 diperlakukan sebagai bar-open dan hanya candle yang telah close boleh masuk manifest. Final 2025 tetap terkunci |
| Reason | Audit 165 gambar bukan populasi harian lengkap. Selain itu, memakai bar yang baru membuka pada waktu target akan menyebabkan look-ahead, sedangkan memakai timestamp buka H4 sebagai waktu sesi dapat salah mengklasifikasikan target London atau overlap |
| Impact | Manifest menyimpan analysis target dan cutoff OHLCV secara terpisah, mewajibkan M5/M15/H1/H4 lengkap, mencatat hash sumber, menandai duplicate window, dan membutuhkan session-target override pada runner berikutnya. Tahap ini tidak melakukan inference, training, atau perubahan keputusan produksi |

---

## Decision #015

| Item | Description |
|------|-------------|
| Date | 21-07-2026 |
| Decision | Manifest E2.3 GBPUSD 2020–2024 dinyatakan valid untuk rendering; hanya 10.230 row `READY` yang boleh dirender, sedangkan 178 row non-ready tetap dipertahankan dalam denominator |
| Reason | Review 10.408 row memverifikasi digest, 20 hash sumber, empat timeframe per event, nol look-ahead, nol duplicate window, dan tidak ada target 2025. Pemisahan cutoff candle dari analysis target diperlukan karena seluruh 2.602 event membutuhkan clock target agar klasifikasi sesi konsisten, terutama pada H4 |
| Impact | Renderer wajib deterministik, resumable, memverifikasi lineage, dan tidak menjalankan inference/training. Endpoint menerima clock target opsional hanya untuk session evaluation; request upload yang tidak mengirimkannya mempertahankan perilaku lama. High-risk policy dan 2025 tetap terkunci |

---
