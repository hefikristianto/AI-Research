# AI-TDSS Local Experiment Plan

**Versi:** 1.0
**Target utama:** GBPUSD
**Execution:** laptop lokal; tidak dijalankan di GitHub Actions

## 1. Aturan Lokasi

Gunakan satu root proyek dan satu root artefak agar file tidak tercecer:

```powershell
$ROOT = "C:\Users\ASUS\Documents\Project\AI-TDSS"
$ARTIFACTS = "$ROOT\local_artifacts"
Set-Location $ROOT
```

`local_artifacts/` diabaikan Git. GitHub hanya menyimpan source code, config, dokumentasi, dan report kecil yang sudah dipilih. Raw dataset, rendered image, checkpoint, prediction dump, serta log besar tetap berada di laptop.

Struktur output setiap eksperimen:

```text
local_artifacts/
  experiments/
    {experiment_id}/
      config/
      logs/
      checkpoints/
      metrics/
      predictions/
      exports/
      manifest.json
```

Format `experiment_id`:

```text
YYYYMMDD_E{nomor}_{deskripsi}
```

Contoh:

```text
20260718_E1_gbpusd_structure_validation
```

## 2. Checklist Sebelum Menjalankan Eksperimen

Setiap eksperimen harus menjawab lokasi berikut sebelum command dijalankan:

| Item | Wajib dicatat |
|---|---|
| Input | Dataset/feedback batch yang dipakai |
| Script | File Python dan config |
| Output | Folder run yang unik |
| Checkpoint | Lokasi `best.pt` atau model candidate |
| Metrics | JSON/CSV/Markdown hasil evaluasi |
| Lineage | Git commit, dataset version, seed, waktu mulai/selesai |

Larangan:

- jangan menimpa checkpoint champion;
- jangan memakai final test untuk tuning;
- jangan memasukkan upload tanpa verified outcome ke training;
- jangan memakai prediksi model sebagai label model itu sendiri;
- jangan menambah kelas YOLO tanpa mengubah kontrak, guideline, dan protocol review;
- jangan menjalankan training GPU melalui GitHub Actions.

## 3. Urutan Eksperimen

### E0 — Contract dan Baseline Readiness

**Tujuan:** memastikan source dan kontrak proyek konsisten. Tidak ada training.

```powershell
Set-Location $ROOT
python ai\scripts\validate_project_contract.py
$env:PYTHONPATH = "backend"
python -m unittest discover -s backend\tests -p "test_*.py" -v
python ai\datasets\scripts\validate_ohlcv.py
```

Input:

```text
config/project_contract.json
ai/datasets/raw/ohlcv/GBPUSD/{M5,M15,H1,H4}/{2020..2025}/*.csv
```

Output:

```text
ai/datasets/metadata/ohlcv_validation_report.csv
```

Gate:

- contract valid;
- unit test pass;
- semua file GBPUSD yang dipakai berstatus `valid`, atau exception terdokumentasi.

### E1 — Validasi Structure, Liquidity, dan Candle Rules

**Tujuan:** menguji fitur deterministik sebelum mempertimbangkan model baru.

Contoh satu file GBPUSD H1:

```powershell
$E1 = "$ARTIFACTS\experiments\20260718_E1_gbpusd_structure_validation"
python ai\structure\scripts\detect_market_structure.py `
  --ohlcv "ai\datasets\raw\ohlcv\GBPUSD\H1\2025\GBPUSD_H1_2025.csv" `
  --output-dir "$E1\exports\H1_2025"
```

Nama file pada `--ohlcv` harus disesuaikan dengan file MT5 aktual. Jangan menebak nama; pilih dari folder yang terlihat di Explorer.

Ulangi untuk M5, M15, H1, dan H4. Jika candle-pattern validator belum tersedia, implementasikan dan uji sebagai rule module terpisah sebelum E2.

Metrik E1:

- precision/recall event pada sampel review;
- jumlah swing, liquidity level, sweep, BOS, dan CHOCH;
- false event per 1.000 candle;
- agreement antar-reviewer jika ada anotasi manual;
- stabilitas parameter pada timeframe berbeda.

Gate:

- definisi event dibekukan;
- contoh true/false positive direview;
- tidak ada kebutuhan yang terbukti untuk menambah kelas liquidity atau candle pattern ke YOLO.

### E2 — Baseline End-to-End GBPUSD

**Tujuan:** mengukur pipeline produksi tanpa retraining.

E2 dimulai dengan audit coverage melalui endpoint produksi yang sama dengan web. Audit ini memisahkan masalah detector, pairing, dan execution gate sebelum outcome trading dihitung.

Smoke sample deterministik:

```powershell
$E2 = "$ARTIFACTS\experiments\20260720_E2_gbpusd_full_baseline"
python ai\scripts\audit_decision_coverage.py `
  --year 2025 `
  --pair GBPUSD `
  --sample-size 10 `
  --seed 42 `
  --confidence-threshold 0.25 `
  --output-dir "$E2\metrics\decision_coverage_smoke"
```

Jika smoke audit tidak memiliki request error, jalankan seluruh chart GBPUSD 2025 dengan menghapus `--sample-size`. Gunakan `--resume` bila proses terputus. Protokol lengkap tersedia di [`DECISION_COVERAGE_AUDIT.md`](DECISION_COVERAGE_AUDIT.md).

Jika baseline menunjukkan valid setup tetapi tidak menjelaskan transisi menuju `WATCHLIST`/`NO_TRADE`, jalankan E2.1 pada image ID yang dibekukan. E2.1 mengekspor raw JSON, annotated PNG, telemetry sebelum quality normalization, dan recency zona tanpa mengubah gate. Protokol dan tujuh kasus baseline berada di [`E2_1_DIAGNOSTIC_REVIEW_PACK.md`](E2_1_DIAGNOSTIC_REVIEW_PACK.md).

Input:

```text
GBPUSD temporal holdout
ai/classification/models/ensemble/ensemble_config.json
checkpoint CNN champion lokal
checkpoint YOLO11s champion lokal
config/project_contract.json
```

Output:

```text
local_artifacts/experiments/{E2_ID}/metrics/decision_coverage/decision_coverage_rows.csv
local_artifacts/experiments/{E2_ID}/metrics/decision_coverage/decision_coverage_summary.json
local_artifacts/experiments/{E2_ID}/metrics/decision_coverage/decision_coverage_summary.md
local_artifacts/experiments/{E2_ID}/predictions/full_analysis.jsonl
local_artifacts/experiments/{E2_ID}/metrics/decision_metrics.json
local_artifacts/experiments/{E2_ID}/metrics/trading_metrics.json
local_artifacts/experiments/{E2_ID}/exports/annotated_images/
local_artifacts/experiments/{E2_ID}/manifest.json
```

Evaluasi wajib mencakup semua keputusan, termasuk `NO_TRADE`, untuk mencegah survivorship bias.

Metrik:

- detection coverage, paired-setup coverage, watchlist/actionable/no-trade rate;
- distribusi blocker, warning, execution status, dan kegagalan request;
- actionable precision dan recall;
- decision Macro F1;
- coverage dan no-trade rate;
- win rate, expectancy dalam R, profit factor, average RR;
- maximum drawdown dan jumlah trade;
- annotated-image completeness;
- latency p50/p95.

Gate:

- audit coverage selesai pada denominator yang dilaporkan dan tidak mencampur request failure sebagai `NO_TRADE`;
- threshold tidak dituning pada final test 2025;
- entry hanya dinilai bila mapping OHLCV kanonis tersedia;
- spread/slippage assumption dibekukan;
- reason code dan model version tersimpan untuk setiap event.

### E2.2 — Plot-Aware Mapping Calibration

**Tujuan:** menguji koreksi deterministik koordinat YOLO terhadap area plot candle, tanpa retraining atau perubahan threshold.

Jalankan baseline dan `--plot-aware-mapping` pada sampel GBPUSD 2024 yang identik. Kedua run wajib memakai seed, sample digest, threshold, commit, dan context size yang sama. Bandingkan error indeks OB/FVG, mapping confidence, fallback geometry, keputusan yang berubah, dan request failure. Jumlah sinyal bukan acceptance metric.

E2.2 selesai pada 21 Juli 2026. A/B lengkap GBPUSD 2024 dan frozen comparison GBPUSD 2025 lulus dengan lineage identik serta nol request failure. Plot-aware dipilih untuk chart kanonis dan E2.3; legacy full-image tetap menjadi default upload umum sampai validasi screenshot eksternal lulus. Bukti dan keputusan berada di [`E2_2_PLOT_MAPPING_RESULT.md`](E2_2_PLOT_MAPPING_RESULT.md); kontrak freeze dan keputusan machine-readable berada di `config/experiments/e2_2_plot_mapping_freeze.json` serta `config/experiments/e2_2_plot_mapping_decision.json`.

Gate:

- geometry yang tidak pasti selalu fallback ke full-image mapping;
- mean/median error indeks OB dan FVG membaik pada development set;
- default-mode parity terjaga;
- tidak ada threshold detector, pairing, session, RR, atau execution yang dipilih dari 2025;
- tidak ada training model.

### E2.3 — High-Risk Daily Coverage

**Tujuan:** menambah tier kandidat high risk secara terpisah untuk mengukur peluang harian tanpa melemahkan policy standard.

E2.3 memakai plot-aware mapping yang telah dipilih E2.2 untuk seluruh chart kanonis. Audit 165 screenshot tahun 2025 bukan populasi harian lengkap, sehingga langkah pertama adalah membuat manifest snapshot GBPUSD per trading day pada slot London dan London–New York overlap. Unit evaluasi adalah hari, dengan maksimal satu kandidat terbaik per tier agar window yang overlap tidak menggandakan frekuensi. Manifest 2020–2024 telah direview: 10.230 dari 10.408 row siap dirender, 178 row non-ready dipertahankan dalam denominator, dan tidak ada kegagalan anti-lookahead atau duplicate window. Kontrak, hasil review, builder, dan renderer berada di `config/experiments/e2_3_daily_manifest.json`, `config/experiments/e2_3_daily_manifest_result.json`, `ai/scripts/build_e2_3_daily_manifest.py`, serta `ai/scripts/render_e2_3_daily_snapshots.py`; panduan run berada di [`E2_3_SNAPSHOT_RENDERING.md`](E2_3_SNAPSHOT_RENDERING.md).

Policy memisahkan `data_quality` dari `risk_tier`. Mapping/OHLCV tidak valid, entry side salah, zona invalid, konflik struktur berat, extreme volatility, dan risk calculation yang hilang tetap menjadi hard blocker. Hanya kondisi market yang lebih lunak—seperti confluence, session suitability, warning entry distance, atau RR—yang boleh membentuk `HIGH_RISK_CANDIDATE`.

Development menggunakan 2020–2023, lalu aturan dibekukan untuk holdout 2024. Satu evaluasi final 2025 hanya dilakukan setelah gate 2024 lulus. Standard-only dan standard+high-risk harus dinilai pada event yang sama, dan metrik setiap tier dilaporkan terpisah. Protokol lengkap berada di [`E2_3_HIGH_RISK_DAILY_COVERAGE.md`](E2_3_HIGH_RISK_DAILY_COVERAGE.md).

Gate:

- daily analysis tersedia; daily trade tidak dipaksakan;
- standard tier tidak berubah dibanding kontrol;
- tidak ada hard data-quality gate yang dilonggarkan;
- tambahan candidate-day coverage harus disertai precision, expectancy, drawdown, dan jumlah outcome terverifikasi;
- hasil high risk tetap `WATCHLIST` bila promotion gate gagal;
- threshold tidak dipilih dari 2025.
- manifest memakai hanya candle yang telah close pada analysis target, mencatat SHA256 sumber, dan menolak 2025 sampai gate holdout 2024 lulus.

### E3 — Ablation Study

**Tujuan:** mengukur kontribusi modul, bukan sekadar membandingkan jumlah sinyal.

| ID | Konfigurasi |
|---|---|
| A0 | Structure/liquidity + risk rules |
| A1 | Single CNN + YOLO + structure + risk |
| A2 | Ensemble + structure + risk, tanpa YOLO candidate |
| A3 | Ensemble + YOLO + risk, tanpa structure/liquidity |
| A4 | Ensemble + YOLO + structure, tanpa HTF/session/risk gate |
| A5 | Full AI-TDSS |

Semua varian memakai dataset, time window, dan cost assumptions yang sama. Simpan hasil di:

```text
local_artifacts/experiments/{E3_ID}/metrics/ablation_results.csv
local_artifacts/experiments/{E3_ID}/metrics/ablation_summary.md
```

Primary comparison: actionable precision dan expectancy. Secondary comparison: coverage, Macro F1, profit factor, dan maximum drawdown.

### E4 — Incremental Learning Comparison

**Prasyarat:** E0–E3 selesai dan minimal 50 feedback sample ber-outcome terverifikasi tersedia.

Bandingkan empat metode:

| Varian | Deskripsi |
|---|---|
| I0 Frozen | Champion tidak diubah |
| I1 Naive | Fine-tune hanya data baru |
| I2 Replay | Fine-tune data baru + replay historis |
| I3 Cumulative | Retrain seluruh data; upper-bound pembanding |

Target pertama adalah komponen CNN dan ensemble weight. YOLO hanya ikut E4 jika terdapat bounding box OB/FVG baru yang sudah direview.

#### Trigger awal

Training candidate boleh dimulai ketika:

```text
eligible_count >= 200
OR (days_since_last_candidate >= 30 AND eligible_count >= 50)
OR (drift_score >= 0.60 AND eligible_count >= 50)
```

#### Folder kandidat

```text
local_artifacts/experiments/{E4_ID}/
  input/eligible_feedback_manifest.csv
  input/replay_manifest.csv
  checkpoints/{model}/best.pt
  predictions/{model}_{split}.csv
  metrics/{model}_{split}.json
  metrics/forgetting_report.json
  metrics/champion_challenger.json
  config/training_config.json
  manifest.json
```

#### Contoh fine-tuning CNN lokal

Command ini template dan baru boleh dijalankan setelah manifest E4 dibekukan:

```powershell
$E4 = "$ARTIFACTS\experiments\{E4_ID}"
python ai\classification\scripts\train_cnn_market_regime.py `
  --model resnet18 `
  --dataset-root "$E4\input\market_regime" `
  --output-dir "$E4\checkpoints\resnet18_replay" `
  --resume-checkpoint "ai\classification\models\ensemble\resnet18.pt" `
  --epochs 10 `
  --batch-size 16 `
  --workers 0 `
  --learning-rate 0.0001 `
  --patience 4 `
  --seed 42
```

Ulangi secara terkontrol untuk komponen yang dipilih. Jangan menjalankan empat training sekaligus sebelum satu command smoke test berhasil.

#### Evaluation gate

- frozen temporal holdout pass;
- next-month walk-forward pass;
- tidak ada regresi primary metric yang material;
- per-class recall tidak runtuh;
- forgetting report diterima;
- trading risk metric tidak memburuk;
- config, checkpoint, prediction, metrics, dan lineage lengkap.

Model baru tetap berstatus `challenger` sampai seluruh gate lulus. Promotion dilakukan dengan mengganti manifest/config deployment, bukan menimpa checkpoint champion.

### E5 — Web, Explainability, Journal, dan Excel

**Tujuan:** menguji bahwa hasil model benar-benar dapat dipakai pengguna.

Acceptance cases:

1. Pengguna mengunggah PNG/JPG/WEBP maksimal 10 MB.
2. Pair default adalah GBPUSD.
3. Frontend mengirim metadata ke `/api/analysis/full`.
4. UI menampilkan keputusan, entry/SL/TP/RR, blockers, warnings, dan reasons.
5. UI menampilkan chart dengan bounding box OB/FVG.
6. Setiap hasil, termasuk `NO_TRADE`, tersimpan ke journal user yang benar.
7. Outcome dapat diperbarui tanpa mengubah snapshot analisis awal.
8. Workbook Excel dapat dibuka dan memiliki empat sheet wajib.
9. Record memiliki model version dan analysis ID yang sama antara UI, database, dan workbook.
10. Data satu pengguna tidak dapat dibaca pengguna lain.

Output acceptance:

```text
local_artifacts/experiments/{E5_ID}/metrics/api_contract_results.json
local_artifacts/experiments/{E5_ID}/metrics/ui_acceptance_results.json
local_artifacts/experiments/{E5_ID}/exports/sample_trade_journal.xlsx
local_artifacts/experiments/{E5_ID}/exports/sample_annotated_chart.png
```

## 4. Manifest Minimum

Setiap `manifest.json` minimal berisi:

```json
{
  "experiment_id": "20260718_E2_gbpusd_full_baseline",
  "git_commit": "<commit-sha>",
  "dataset_version": "<version>",
  "pair": "GBPUSD",
  "timeframes": ["M5", "M15", "H1", "H4"],
  "train_period": "<period-or-null>",
  "validation_period": "<period>",
  "test_period": "<period>",
  "seed": 42,
  "input_paths": [],
  "checkpoint_paths": [],
  "metric_paths": [],
  "started_at_utc": "<timestamp>",
  "finished_at_utc": "<timestamp>",
  "status": "PASS|FAIL|INCOMPLETE"
}
```

## 5. Keputusan Tahap Berikutnya

Urutan kerja aktif adalah menyelesaikan render 10.230 snapshot E2.3 → inference resumable dengan session-target clock → shadow policy standard/high-risk → holdout 2024 → journal/feedback/Excel → E3 ablation → E5 product acceptance. Manifest harian sudah lulus review, E2.2 telah selesai, dan keduanya tidak boleh dituning ulang dari hasil 2025. E2.3 memakai plot-aware mapping untuk chart kanonis, sedangkan tier high risk tidak masuk produksi sebelum holdout 2024 lulus. E4 tidak dijalankan hanya karena satu bulan berlalu; training tetap memerlukan minimum eligible batch dan evaluation gate. Dengan urutan ini, incremental learning memperbaiki sistem yang sudah dapat diukur, bukan menambah kompleksitas sebelum baseline end-to-end tersedia.
