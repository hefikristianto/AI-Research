# Research Synthesis AI-TDSS

**Versi:** 1.4
**Tanggal:** 20 Juli 2026
**Status:** Baseline coverage terkunci; E2.2 plot-mapping calibration siap diuji; E2.3 high-risk daily coverage masuk workflow berikutnya

## 1. Ringkasan Penelitian

AI-TDSS dikembangkan sebagai sistem pendukung keputusan yang membantu pengguna memahami dan mengevaluasi peluang entry dari screenshot market. Sistem tidak hanya mengklasifikasikan gambar, tetapi menggabungkan bukti visual, konteks harga kanonis, struktur market, dan pengendalian risiko.

Kontribusi utama proyek adalah arsitektur hibrida yang memisahkan fungsi setiap metode:

1. CNN ensemble mengenali regime market.
2. YOLO mendeteksi Order Block (OB) dan Fair Value Gap (FVG), kemudian menyediakan visual explanation berbentuk bounding box.
3. Aturan OHLCV menghitung liquidity, sweep, EQH/EQL, BOS/CHOCH, candle pattern, volatilitas, dan konteks sesi secara deterministik.
4. Trade Decision Engine menggabungkan seluruh bukti untuk menghasilkan rekomendasi dan parameter risiko.
5. Trading journal menyimpan seluruh hasil analisis, outcome, dan lineage model untuk evaluasi serta incremental learning.

Pair utama penelitian adalah GBPUSD. XAUUSD hanya menjadi domain sekunder untuk pengujian generalisasi dan tidak boleh dicampur ke klaim utama tanpa pelaporan terpisah.

## 2. Rumusan Masalah

Analisis screenshot saja memiliki tiga keterbatasan penting:

- posisi pixel tidak selalu dapat diterjemahkan menjadi harga entry yang akurat;
- confidence object detector tidak sama dengan probabilitas keberhasilan trade;
- pola market berubah dari waktu ke waktu sehingga model statis dapat mengalami drift.

AI-TDSS mengatasi keterbatasan tersebut dengan memasangkan screenshot dan metadata terhadap data OHLCV kanonis. Bila pair, timeframe, waktu chart, atau OHLCV tidak tersedia, sistem tidak boleh menerbitkan entry yang dianggap siap dieksekusi. Output harus turun menjadi `WATCHLIST` atau `NO_TRADE` dengan alasan yang jelas.

## 3. Tujuan dan Pertanyaan Penelitian

### 3.1 Tujuan

- Menghasilkan rekomendasi entry GBPUSD yang transparan dan dapat diaudit.
- Mengukur kontribusi CNN ensemble, YOLO, market structure, dan risk gate terhadap kualitas keputusan.
- Menguji apakah incremental learning dengan replay dapat beradaptasi terhadap perubahan bulanan tanpa catastrophic forgetting.
- Menyediakan pengalaman belajar melalui annotated chart dan reason codes.
- Menyimpan hasil analisis dalam jurnal yang dapat diunduh sebagai Excel.

### 3.2 Pertanyaan penelitian

| ID | Pertanyaan |
|---|---|
| RQ1 | Seberapa baik CNN ensemble mengklasifikasikan regime GBPUSD dibandingkan single CNN? |
| RQ2 | Seberapa baik YOLO11s mendeteksi dan melokalisasi OB/FVG pada periode yang belum pernah dilihat? |
| RQ3 | Apakah penggabungan CNN, YOLO, struktur OHLCV, dan risk gate meningkatkan precision keputusan actionable dibandingkan pipeline yang komponennya dikurangi? |
| RQ4 | Apakah incremental learning berbasis replay menjaga atau meningkatkan performa pada data baru tanpa menurunkan performa historis secara material? |

## 4. Batas Sistem

### 4.1 Di dalam ruang lingkup

- upload screenshot melalui web Next.js/React;
- analisis utama GBPUSD pada M5, M15, H1, dan H4;
- klasifikasi regime `bearish`, `bullish`, dan `sideways`;
- deteksi YOLO untuk `order_block` dan `fair_value_gap`;
- derivasi struktur dan liquidity dari OHLCV;
- rekomendasi `BUY`, `SELL`, `WATCHLIST`, atau `NO_TRADE`;
- entry, stop loss, take profit, risk-reward, blockers, warnings, dan reasons;
- annotated image untuk menjelaskan zona visual;
- journal per pengguna dan ekspor Excel;
- monitoring drift dan offline batch incremental learning.

### 4.2 Di luar ruang lingkup

- eksekusi order otomatis ke broker;
- jaminan profit;
- menjadikan liquidity, BOS/CHOCH, atau candle pattern sebagai kelas YOLO produksi;
- training otomatis dari prediksi AI yang belum memiliki outcome terverifikasi;
- training berat di GitHub Actions;
- klaim generalisasi universal ke semua pair, broker, atau kondisi spread.

## 5. Pendekatan dan Peran Metode

### 5.1 CNN ensemble

Empat arsitektur—VGG11, VGG16, GoogLeNet, dan ResNet18—menghasilkan probabilitas untuk tiga regime. Probabilitas digabungkan dengan weighted soft voting. Bobot ditentukan dari validation Macro F1 sehingga ensemble tidak bergantung pada satu arsitektur.

CNN digunakan sebagai konteks arah/regime, bukan sumber entry tunggal. Entropy dan confidence disimpan untuk uncertainty analysis serta drift monitoring.

### 5.2 YOLO11s

YOLO11s 50 epoch adalah detector terpilih untuk dua kelas produksi:

- `order_block`;
- `fair_value_gap`.

YOLO memiliki dua fungsi: menyediakan kandidat zona bagi pipeline dan menghasilkan bounding box edukatif pada gambar. Liquidity, BOS/CHOCH, EQH/EQL, dan candlestick pattern tidak dimasukkan sebagai kelas detector karena lebih tepat dihitung dari urutan OHLCV yang memiliki koordinat harga dan waktu pasti.

### 5.3 Analisis deterministik OHLCV

OHLCV digunakan untuk:

- memetakan pixel zona ke rentang harga;
- mengidentifikasi swing high/low;
- mendeteksi equal high/equal low dan liquidity sweep;
- mengonfirmasi BOS/CHOCH;
- menghitung candle pattern;
- menghitung volatilitas dan konteks higher timeframe;
- memvalidasi entry, stop loss, take profit, dan risk-reward.

Pendekatan ini menjaga interpretabilitas karena setiap fitur memiliki definisi dan sumber candle yang dapat ditelusuri.

### 5.4 Trade Decision Engine

Trade Decision Engine tidak menganggap confidence CNN atau YOLO sebagai probabilitas profit. Engine melakukan fusion dan gating. BUY/SELL hanya boleh diterbitkan ketika metadata lengkap, OHLCV berhasil dimuat, zona valid, arah tidak berkonflik secara material, risk-reward memenuhi batas, serta tidak ada blocker kualitas.

Status internal `WAIT` perlu dipetakan pada API publik:

- `REVIEW` atau setup belum terkonfirmasi → `WATCHLIST`;
- `NO_SETUP`, `INVALID`, atau blocker keras → `NO_TRADE`.

## 6. Kontrak Input dan Output

### 6.1 Input minimum

| Field | Tujuan |
|---|---|
| `chart_image` | Inference CNN dan YOLO |
| `pair` | Memilih sumber OHLCV; default produk harus GBPUSD |
| `timeframe` | Menentukan resolusi chart dan konteks |
| `chart_datetime` | Menyelaraskan screenshot dengan OHLCV |

Input tambahan dapat mencakup jumlah candle chart, panjang context window, dan UTC offset. Session sebaiknya dihitung dari waktu kanonis, bukan dipercaya sebagai label bebas dari pengguna.

### 6.2 Output analisis

Output minimum mencakup:

- analysis ID dan timestamp;
- pair, timeframe, dan waktu chart;
- regime probabilities, confidence, entropy, serta versi ensemble;
- daftar deteksi OB/FVG, confidence, dan bounding box;
- struktur, liquidity, volatility, dan session context;
- keputusan publik, execution status, blockers, warnings, dan reasons;
- entry, stop loss, take profit, risk-reward, dan order type;
- annotated image URL atau payload;
- versi model, policy, dan pipeline.

### 6.3 Status implementasi kontrak

| Kapabilitas | Status | Catatan |
|---|---|---|
| React chart upload | Implemented | Memanggil `/api/analysis/full` dengan pair, timeframe, chart time, dan UTC offset |
| Public decision boundary | Implemented | Hanya `TRADE_CANDIDATE` yang konsisten dapat menjadi BUY/SELL; level trade disembunyikan untuk hasil non-actionable |
| Annotated chart | Implemented | Backend mengembalikan PNG base64 dengan bounding box OB/FVG dan banner keputusan |
| Decision coverage audit | Implemented | Runner lokal memanggil endpoint produksi dan melaporkan funnel detection→pairing→watchlist/actionable serta blocker tanpa retraining |
| Plot-aware mapping calibration | Experimental, opt-in | Mengestimasi batas plot secara color-agnostic, fallback ke full-image, dan mencatat indeks legacy/candidate untuk A/B 2020–2024 |
| Persistent journal | Pending | Harus user-scoped dan menyimpan semua keputusan |
| Verified outcome feedback | Pending | Diperlukan sebelum data dapat eligible untuk incremental learning |
| Four-sheet Excel export | Pending | Mengikuti kontrak pada Bagian 12 |

Payload PNG base64 dipakai untuk vertical slice lokal. Implementasi produksi dapat memindahkan gambar beranotasi ke object storage dan mengembalikan URL tanpa mengubah makna output.

## 7. Dataset dan Desain Evaluasi

### 7.1 Sumber dan split

Dataset OHLCV berasal dari ekspor MT5 broker Valetax. Struktur lokal disusun berdasarkan pair, timeframe, dan tahun. Desain baseline saat ini memakai 2020–2024 untuk development dan 2025 sebagai final temporal test.

Split berbasis waktu wajib dipertahankan. Random split antar-candle yang saling berdekatan berisiko menyebabkan temporal leakage. Untuk evaluasi berikutnya digunakan expanding-window atau rolling walk-forward per bulan.

### 7.2 Ground truth

- Label regime berasal dari aturan labeling yang terdokumentasi dan perlu diaudit per kelas.
- Bounding box OB/FVG boleh diawali semi-otomatis, tetapi subset evaluasi dan data baru untuk update YOLO harus direview.
- Outcome trade dihitung dari pergerakan OHLCV setelah waktu keputusan menggunakan aturan SL/TP yang dibekukan sebelum evaluasi.
- Pilihan pengguna untuk mengikuti atau mengabaikan sinyal bukan ground truth kualitas sinyal.

### 7.3 Pencegahan leakage

- Satu chart window dan window yang sangat overlap tidak boleh tersebar antar train, validation, dan test.
- Threshold, ensemble weight, serta risk rule dipilih hanya pada train/validation.
- Final test tidak digunakan untuk memilih model.
- Monthly incremental candidate diuji pada holdout masa lalu yang dibekukan dan forward window yang belum digunakan training.

## 8. Baseline dan Metrik

### 8.1 Hasil yang sudah tersedia

| Modul | Test | Metrik utama | Hasil |
|---|---|---|---:|
| CNN ensemble | 2025 | Accuracy | 0.8607 |
| CNN ensemble | 2025 | Macro F1 | 0.8427 |
| YOLO11s 50e | 2025 | Precision | 0.591 |
| YOLO11s 50e | 2025 | Recall | 0.593 |
| YOLO11s 50e | 2025 | mAP50 | 0.590 |
| YOLO11s 50e | 2025 | mAP50-95 | 0.452 |

Sumber internal: [`FINAL_CNN_ENSEMBLE_RESULT.md`](../../ai/classification/reports/FINAL_CNN_ENSEMBLE_RESULT.md) dan [`FINAL_YOLO_MODEL_SELECTION.md`](../../ai/benchmarks/reports/FINAL_YOLO_MODEL_SELECTION.md).

### 8.2 Metrik yang wajib dipisahkan

| Level | Metrik |
|---|---|
| CNN | Accuracy, balanced accuracy, Macro F1, per-class precision/recall/F1, calibration, entropy |
| YOLO | Precision, recall, mAP50, mAP50-95, per-class AP, localization error |
| Decision | Precision actionable BUY/SELL, recall setup valid, F1, coverage, no-trade rate, watchlist conversion |
| Trading simulation | Win rate, expectancy dalam R, profit factor, average RR, maximum drawdown, jumlah trade |
| Incremental | Forward-window delta, backward transfer/forgetting, stability, drift recovery |
| Product | Upload success, analysis latency, journal completeness, Excel validity, annotated-image availability |

Metrik trading harus dilaporkan bersama jumlah trade dan coverage. Win rate tinggi dengan hanya sedikit trade tidak boleh disimpulkan lebih baik tanpa konteks.

### 8.3 Audit coverage sebelum evaluasi outcome

Sebelum precision keputusan atau metrik trading dihitung, pipeline dijalankan pada seluruh population GBPUSD 2025 melalui endpoint `/api/analysis/full`. Audit mencatat detection coverage, paired-setup coverage, `WATCHLIST`, actionable `BUY/SELL`, `NO_TRADE`, request failure, serta distribusi blocker per timeframe.

Request failure dan gambar lokal yang hilang dipisahkan dari denominator respons sukses; keduanya tidak boleh diam-diam dihitung sebagai `NO_TRADE`. Output audit berupa CSV per gambar serta ringkasan JSON/Markdown di `local_artifacts/`. Audit ini tidak melakukan training dan tidak digunakan untuk mengubah threshold pada final test. Protokol operasional berada di [`DECISION_COVERAGE_AUDIT.md`](../experiments/DECISION_COVERAGE_AUDIT.md).

Jika summary agregat belum cukup menjelaskan transisi keputusan, E2.1 memakai targeted case review yang telah ditentukan sebelumnya. Telemetry memisahkan kondisi sebelum dan sesudah quality normalization, mengukur recency zona terhadap sisi kanan gambar dan akhir window OHLCV, serta menyimpan raw response dan annotated image dengan verifikasi hash. Review ini bersifat forensik; perubahan algoritme berikutnya tetap dikembangkan pada periode development/validation, bukan dituning pada tujuh kasus final-test. Protokol berada di [`E2_1_DIAGNOSTIC_REVIEW_PACK.md`](../experiments/E2_1_DIAGNOSTIC_REVIEW_PACK.md).

E2.1 mengidentifikasi kemungkinan bias horizontal pada mapping pixel→candle karena koordinat YOLO sebelumnya ditafsirkan terhadap lebar seluruh gambar. E2.2 menguji transformasi terhadap area plot yang dideteksi secara color-agnostic. Fitur ini opt-in dan gagal aman ke mapping lama. Konstanta tidak dipilih dari tujuh kasus 2025; A/B dilakukan pada synthetic test dan GBPUSD 2020–2024, lalu implementasi dibekukan sebelum satu perbandingan final 2025. Protokol berada di [`E2_2_PLOT_MAPPING_CALIBRATION.md`](../experiments/E2_2_PLOT_MAPPING_CALIBRATION.md).

Setelah mapping dibekukan, E2.3 menguji tier `HIGH_RISK_CANDIDATE` sebagai policy paralel. Data quality dan market risk dipisahkan: entry berisiko tinggi masih wajib memiliki metadata, OHLCV, arah, zona, dan mapping harga yang valid. Populasi evaluasi dibentuk per trading day pada slot sesi yang ditentukan sebelumnya; standard-only dan standard+high-risk dibandingkan pada event yang sama. Target daily berarti analisis tersedia setiap hari, bukan memaksa entry ketika hard gate gagal. Protokol berada di [`E2_3_HIGH_RISK_DAILY_COVERAGE.md`](../experiments/E2_3_HIGH_RISK_DAILY_COVERAGE.md).

## 9. Incremental Learning yang Aman

### 9.1 Unit pembelajaran

Upload pengguna pertama-tama merupakan inference event. Event baru menjadi training candidate setelah mempunyai data yang cukup untuk diverifikasi:

1. screenshot dan metadata lengkap;
2. pasangan terhadap OHLCV berhasil;
3. outcome SL/TP atau label regime dapat dihitung;
4. tidak terduplikasi atau mengalami leakage;
5. lolos quality review;
6. persetujuan penggunaan data dipenuhi bila diperlukan.

Prediksi mentah model tidak pernah menjadi ground truth otomatis. Aturan ini mencegah confirmation bias dan error amplification.

### 9.2 Trigger awal

Training candidate dibuat jika salah satu kondisi berikut terpenuhi dan minimum 50 sampel eligible tersedia:

- jumlah data mencapai 200 sampel;
- 30 hari telah berlalu;
- drift score mencapai 0.60.

Angka tersebut adalah initial experimental policy. Hasil ablation dan kapasitas data dapat mengubahnya melalui decision log.

### 9.3 Target update

Prioritas update adalah fine-tuning komponen CNN dan recalibration bobot ensemble. YOLO tidak diperbarui dari outcome trade; update YOLO membutuhkan bounding box OB/FVG yang direview. Aturan liquidity dan candlestick diperbarui sebagai rule/config version, bukan checkpoint detector.

### 9.4 Champion–challenger

Training selalu menghasilkan challenger. Model produksi/champion tidak ditimpa. Challenger hanya dipromosikan jika:

- reproduksi data dan konfigurasi lengkap;
- frozen holdout dan walk-forward lulus;
- primary metric tidak mengalami regresi material;
- risk metric tidak memburuk;
- forgetting pada data historis masih dalam batas;
- lineage dataset, code commit, checkpoint, dan metrics tersedia.

Rollback dilakukan dengan mengaktifkan kembali manifest champion sebelumnya.

## 10. Rencana Eksperimen

| ID | Eksperimen | Tujuan | Output keputusan |
|---|---|---|---|
| E0 | Reproduksi baseline | Memastikan hasil CNN/YOLO dapat direproduksi lokal | Baseline lock |
| E1 | Validasi OHLCV | Mengukur akurasi liquidity, BOS/CHOCH, candle pattern, dan mapping harga | Rule/config lock |
| E2 | Baseline end-to-end GBPUSD | Mengukur kualitas entry dan risk gate | Full-system baseline |
| E2.1 | Diagnostic review pack | Menjelaskan drop-off keputusan tanpa mengubah gate | Defect hypothesis |
| E2.2 | Plot-aware mapping A/B | Menguji koreksi pixel→candle pada development period | Mapping promotion decision |
| E2.3 | High-risk daily coverage | Menambah tier risiko secara paralel dan mengukur candidate-day coverage | Risk-tier promotion decision |
| E3 | Ablation | Mengukur kontribusi tiap komponen | Bukti RQ3 |
| E4 | Incremental comparison | Membandingkan frozen, naive, replay, dan cumulative | Bukti RQ4 |
| E5 | Product acceptance | Menguji React upload, annotated image, journal, dan Excel | Release readiness |

Urutan detail, jalur file, dan promotion gate berada di [`LOCAL_EXPERIMENT_PLAN.md`](../experiments/LOCAL_EXPERIMENT_PLAN.md).

## 11. Desain Ablation

Semua varian memakai time window dan transaction-cost assumptions yang sama.

| Varian | CNN | YOLO | Structure/liquidity | HTF/session/risk |
|---|:---:|:---:|:---:|:---:|
| A0 | – | – | ✓ | ✓ |
| A1 | Single CNN | ✓ | ✓ | ✓ |
| A2 | Ensemble | – | ✓ | ✓ |
| A3 | Ensemble | ✓ | – | ✓ |
| A4 | Ensemble | ✓ | ✓ | – |
| A5 Full | Ensemble | ✓ | ✓ | ✓ |

Tujuan ablation bukan mencari varian dengan trade terbanyak, tetapi menentukan apakah tambahan komponen meningkatkan precision dan expectancy tanpa memperburuk drawdown secara tidak wajar.

## 12. Journal dan Excel sebagai Artefak Penelitian

Setiap analisis disimpan, termasuk `NO_TRADE`. Hanya menyimpan trade yang berhasil akan menghasilkan survivorship bias. Workbook pengguna memiliki empat sheet:

1. `Analyses`: seluruh output inference dan rekomendasi;
2. `Trade_Outcomes`: outcome, PnL, dan feedback terverifikasi;
3. `Model_Metadata`: versi CNN, YOLO, rules, dan policy;
4. `Definitions`: definisi field dan disclaimer.

Export harus mempertahankan timestamp UTC, analysis ID, model version, blockers, dan reasons sehingga hasil dapat diaudit kembali.

## 13. Gap Implementasi Saat Ini

| Gap | Dampak | Prioritas |
|---|---|---|
| Journal router/store belum selesai | Analisis dan feedback belum persisten | P0 |
| Excel export belum tersedia | Kebutuhan pengguna belum terpenuhi | P0 |
| Feedback loop belum memiliki eligibility store | Incremental learning belum aman dijalankan | P1 |
| Analysis ID dan lineage model belum dipersistenkan pada event journal | Audit end-to-end belum lengkap | P1 |
| Timezone broker dataset masih bersifat asumsi provisional | Penyelarasan screenshot lintas platform perlu divalidasi | P1 |
| Endpoint full analysis belum memiliki fixture integration test dengan model stub | Risiko regresi orkestrasi masih lebih tinggi daripada service-level unit test | P1 |
| Baseline coverage 2025 belum selesai dijalankan | Selectivity dan blocker dominan belum dapat diklaim secara kuantitatif | P0 |
| Robustness tema warna/platform belum dievaluasi | Recall dapat turun pada TradingView/MT5 yang berbeda dari renderer dataset | P1 |

## 14. Batas Klaim Akademik

Hasil model menunjukkan performa pada dataset dan split yang ditentukan, bukan bukti profit di seluruh kondisi market. Nilai mAP YOLO mengukur object detection, bukan kualitas entry. Accuracy regime tidak sama dengan win rate. Backtest bukan pengganti forward test, dan outcome bergantung pada spread, slippage, serta definisi eksekusi.

Klaim yang defensible adalah bahwa AI-TDSS menyediakan arsitektur decision support yang terukur, explainable, dan dapat beradaptasi melalui proses incremental yang dikendalikan. Klaim profitabilitas hanya boleh dibuat setelah evaluasi end-to-end dan harus disertai asumsi serta batasannya.

## 15. Pemetaan ke Dokumen Akademik

| Bagian akademik | Materi dari synthesis |
|---|---|
| Latar belakang | Bagian 1–2 |
| Rumusan masalah dan tujuan | Bagian 2–3 |
| Batasan penelitian | Bagian 4 dan 14 |
| Metodologi | Bagian 5–7 |
| Desain sistem | Bagian 5–6 |
| Evaluasi | Bagian 8, 10, dan 11 |
| Incremental learning | Bagian 9 |
| Implementasi web/journal | Bagian 6, 12, dan 13 |
| Pembahasan keterbatasan | Bagian 13–14 |

Dokumen ini adalah synthesis. Angka hasil eksperimen tetap harus dirujuk ke report artefak asli, bukan disalin tanpa version/commit lineage.
