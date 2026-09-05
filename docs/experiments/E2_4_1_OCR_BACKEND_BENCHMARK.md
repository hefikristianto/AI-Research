# E2.4.1 OCR Backend and Fixture Benchmark

- **Status:** completed external benchmark — FAIL; no profile selected
- **Execution:** laptop lokal, tanpa FastAPI/React server
- **Training/model inference:** tidak dilakukan
- **Trading outcome:** tidak dibaca
- **Production decision:** tidak berubah
- **High Risk:** tetap shadow-only
- **Holdout 2024/final 2025:** tetap terkunci

## Tujuan

E2.4 core telah memiliki adapter OCR dan robust linear fit, tetapi belum ada bukti bahwa backend OCR dapat membaca sumbu harga beragam. E2.4.1 membandingkan profil Tesseract yang terdaftar berikut:

| Profile ID | Preprocessing |
|---|---|
| `RAW_RGB_PSM11` | RGB asli |
| `GRAY_AUTOCONTRAST_2X_PSM11` | grayscale, autocontrast, 2× resize |
| `GRAY_INVERT_AUTOCONTRAST_2X_PSM11` | grayscale, invert, autocontrast, 2× resize |
| `GRAY_FOOTER_TRIM_AUTOCONTRAST_2X_PSM11` | untuk chart terang, trim footer gelap yang kontigu di bawah; lalu grayscale, autocontrast, 2× resize |

Semua profil memakai Tesseract 5, English language data, OEM 1, PSM 11, dan whitelist `0123456789.,-%`. Koordinat hasil OCR 2× dikembalikan ke koordinat screenshot asli sebelum matching dan kalibrasi.

Profil footer-trim ditambahkan sebagai kandidat eksplisit setelah partial review 8 fixture menemukan footer hitam TradingView menekan kontras label sumbu abu-abu pada chart terang. Profil lama tidak diubah. Deteksi sumbu persen juga diperketat: sekurangnya tiga label persen berformat valid dengan confidence ≥ 0,10 harus ditemukan. Ambang khusus ini memakai pengulangan struktur label sebagai bukti sumbu; token `%` tunggal, malformed, atau confidence nol tetap dicatat sebagai telemetry tetapi tidak lagi menjadi bukti sumbu persen.

Kontrak machine-readable berada di [`config/experiments/e2_4_1_ocr_benchmark.json`](../../config/experiments/e2_4_1_ocr_benchmark.json).

## Hasil eksternal final

Run Windows yang direview memproses seluruh 32 fixture eksternal dengan
Tesseract `5.5.3.20260724`. SHA256 result ZIP adalah
`a9ca2ad2576171c9a5898afd59f2d716158bc47fbdfba7821d039d78fb3d1241`
dan SHA256 fixture manifest adalah
`888c3627713798f87d58e1b76fe92eac5c4ca8e192419c75a6fe8f5087517852`.
Ringkasan machine-readable dan hash artefak disimpan di
[`config/experiments/e2_4_1_external_result.json`](../../config/experiments/e2_4_1_external_result.json).

| Profile | Precision | Recall | Exact text | Calibration recall | Fail-closed recall | False calibration | Normalized MAE | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `GRAY_AUTOCONTRAST_2X_PSM11` | 97.77% | 48.08% | 98.86% | 45.83% | 100.00% | 0.00% | 0.010097 | FAIL |
| `GRAY_FOOTER_TRIM_AUTOCONTRAST_2X_PSM11` | 98.47% | 53.02% | 98.45% | 50.00% | 100.00% | 0.00% | 0.010131 | FAIL |
| `GRAY_INVERT_AUTOCONTRAST_2X_PSM11` | 97.75% | 47.80% | 99.43% | 45.83% | 100.00% | 0.00% | 0.010107 | FAIL |
| `RAW_RGB_PSM11` | 93.50% | 71.15% | 99.61% | 95.83% | 100.00% | 0.00% | 0.006775 | FAIL |

Kesimpulan E2.4.1 adalah **FAIL**. Tidak ada profile yang dipilih atau
dipromosikan. Remediasi hanya boleh dilakukan melalui eksperimen baru yang
diregistrasikan; tindak lanjut tersebut dicatat sebagai E2.4.2.

## Batas metodologis

Fixture hanya menilai kemampuan membaca label sumbu dan memetakan pixel Y ke harga. Fixture tidak boleh menyimpan win rate, TP/SL outcome, expectancy, drawdown, atau field hasil trading lain. Runner juga memverifikasi bahwa:

- setiap image cocok dengan SHA256 manifest;
- setiap raw OCR response disimpan dan SHA256-nya diverifikasi saat `--resume`;
- error lama diproses ulang, bukan dianggap cache sukses;
- hasil selalu `entry_price_authorized=false` dan `production_decision_changed=false`;
- fixture sintetis hanya smoke test;
- pemilihan profil dan acceptance gate hanya memakai fixture eksternal yang direview.

Area OCR tidak boleh dimulai di sebelah kanan fallback strip 72% lebar gambar. Batas ini mencegah geometry detector yang ikut menghitung teks sumbu sebagai foreground memotong label harga sebelum OCR.

## Instalasi lokal Windows

Tesseract adalah executable terpisah dari package Python. Gunakan installer Windows yang dirujuk oleh [dokumentasi instalasi Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html), lalu install wrapper Python yang dibekukan pada `pytesseract==0.3.13`.

```powershell
Set-Location "C:\Users\ASUS\Documents\Project\AI-TDSS"
$PY = ".\backend\.venv\Scripts\python.exe"
$env:PYTHONPATH = "backend"

& $PY -m pip install -r ".\backend\requirements-ocr.txt"

$TESSERACT = "C:\Program Files\Tesseract-OCR\tesseract.exe"
if (!(Test-Path $TESSERACT)) {
    $COMMAND = Get-Command tesseract -ErrorAction SilentlyContinue
    if ($null -eq $COMMAND) {
        throw "Tesseract 5 belum ditemukan. Install executable Windows terlebih dahulu."
    }
    $TESSERACT = $COMMAND.Source
}

$env:AI_TDSS_TESSERACT_CMD = $TESSERACT
& $TESSERACT --version
& $PY -c "import pytesseract; print('pytesseract', pytesseract.__version__)"
```

Versi major Tesseract harus minimal 5. Path executable ikut masuk `run_contract.json`, sehingga perubahan executable akan menolak resume yang tidak kompatibel.

## Smoke test sintetis

```powershell
$RUN_ID = "$(Get-Date -Format yyyyMMdd_HHmmss)_E2_4_1_ocr_synthetic"
$RUN = ".\local_artifacts\experiments\$RUN_ID"
$FIXTURES = "$RUN\fixtures_synthetic"
$BENCHMARK = "$RUN\benchmark_synthetic"

& $PY ai\scripts\generate_e2_4_synthetic_ocr_fixtures.py `
  --output-dir $FIXTURES

& $PY ai\scripts\benchmark_e2_4_price_axis_ocr.py `
  --fixture-manifest "$FIXTURES\e2_4_1_fixture_manifest.json" `
  --output-dir $BENCHMARK `
  --progress-every 16

Get-Content "$BENCHMARK\e2_4_1_ocr_benchmark_summary.md" -Raw
```

Generator membuat 32 screenshot deterministik: 24 axis valid dan 8 negative fixture untuk crop, persen, dan log. Hasil overall **harus tetap `FAIL / INCOMPLETE`** karena synthetic smoke tidak memenuhi minimum 32 fixture eksternal yang direview. Ini bukan kegagalan instalasi selama task berstatus `SUCCESS` dan sekurangnya satu profil preprocessing membaca fixture valid.

Command yang sama dapat dilanjutkan setelah interupsi:

```powershell
& $PY ai\scripts\benchmark_e2_4_price_axis_ocr.py `
  --fixture-manifest "$FIXTURES\e2_4_1_fixture_manifest.json" `
  --output-dir $BENCHMARK `
  --progress-every 16 `
  --resume
```

## Fixture eksternal

Kumpulkan minimal 32 screenshot yang merepresentasikan upload pengguna. Setiap nilai strata berikut harus muncul minimal empat kali: GBPUSD/XAUUSD, TradingView/MT5, light/dark/custom, M5/M15/H1/H4, serta locale titik/koma. Jumlah tersebut adalah coverage marginal yang boleh overlap, bukan keharusan membuat seluruh kombinasi kartesian.

Gunakan screenshot asli dengan sumbu harga terlihat. Jangan mengubah label harga setelah screenshot dibuat. Untuk setiap label yang direview, catat:

- teks persis seperti terlihat;
- harga numerik setelah normalisasi locale;
- `y_center` dalam pixel pada gambar asli;
- perkiraan region sumbu dan batas kanan plot;
- status yang diharapkan (`CALIBRATED` atau `FAIL_CLOSED`).

Salin [`e2_4_1_external_annotations.example.json`](templates/e2_4_1_external_annotations.example.json), ganti placeholder, lalu buat portable pack:

```powershell
$ANNOTATIONS = ".\local_artifacts\experiments\$RUN_ID\external_annotations.json"
$EXTERNAL_FIXTURES = "$RUN\fixtures_external"
$EXTERNAL_BENCHMARK = "$RUN\benchmark_external"

& $PY ai\scripts\build_e2_4_external_ocr_fixture_pack.py `
  --annotations $ANNOTATIONS `
  --output-dir $EXTERNAL_FIXTURES

& $PY ai\scripts\benchmark_e2_4_price_axis_ocr.py `
  --fixture-manifest "$EXTERNAL_FIXTURES\e2_4_1_fixture_manifest.json" `
  --output-dir $EXTERNAL_BENCHMARK `
  --progress-every 16

Get-Content "$EXTERNAL_BENCHMARK\e2_4_1_ocr_benchmark_summary.md" -Raw
```

Review kedua disarankan untuk `y_center`, teks, locale, crop/log/persen, dan expected status. `external_reviewed=true` menyatakan anotasi sudah direview; flag tersebut tidak boleh diberikan otomatis pada upload mentah.

## Gate terdaftar

| Gate eksternal | Batas |
|---|---:|
| Minimum fixture | 32 |
| Tick precision | ≥ 0,99 |
| Tick recall | ≥ 0,95 |
| Exact-text accuracy | ≥ 0,95 |
| Expected axis-region containment recall | 1,00 |
| Expected calibration recall | ≥ 0,95 |
| Fail-closed recall | 1,00 |
| False-calibration rate | 0,00 |
| Normalized mapping MAE | ≤ 0,10 tick step |
| GBPUSD mapping MAE | ≤ 0,00005 |
| XAUUSD mapping MAE | ≤ 0,05 |

Profile yang lulus tetap belum boleh menjadi default frontend. Hasil E2.4.1 memasok bukti untuk review E2.4.2 lintas platform/theme; keputusan produksi memerlukan freeze terpisah.

## Artefak yang dikirim untuk review

```powershell
$PACK = "$RUN\e2_4_1_review.zip"
Compress-Archive `
  -Path "$EXTERNAL_FIXTURES\*", "$EXTERNAL_BENCHMARK\*" `
  -DestinationPath $PACK `
  -Force

Get-Item $PACK | Select-Object FullName, Length
```

Review pack wajib memuat manifest fixture, image yang di-hash, CSV per task, raw OCR JSON, `run_contract.json`, summary JSON, dan summary Markdown. Screenshot dapat berisi informasi akun; crop atau redaksi informasi personal dilakukan **sebelum** fixture dianotasi dan SHA256 dibekukan.
