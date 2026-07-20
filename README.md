# AI-TDSS

AI Trading Decision Support System (AI-TDSS) adalah sistem pendukung keputusan trading berbasis web. Pengguna mengunggah gambar chart, sistem menggabungkan analisis visual dan data OHLCV, lalu mengembalikan rekomendasi `BUY`, `SELL`, `WATCHLIST`, atau `NO_TRADE` beserta area entry, stop loss, take profit, risk-reward, alasan analisis, dan gambar beranotasi.

AI-TDSS bukan sistem auto-trading dan tidak mengeksekusi order ke broker. Pair penelitian utama adalah **GBPUSD**. XAUUSD dipertahankan sebagai pair penelitian sekunder untuk menguji generalisasi.

## Arsitektur Inti

```mermaid
flowchart TD
    A["Upload chart + metadata"] --> B["CNN ensemble: market regime"]
    A --> C["YOLO11s: OB/FVG"]
    A --> D["Canonical OHLCV context"]
    D --> E["Structure, liquidity, volatility"]
    B --> F["Trade Decision Engine"]
    C --> F
    E --> F
    F --> G["Entry, risk, reasons"]
    C --> H["Annotated chart"]
    G --> I["User journal"]
    H --> I
    I --> J["Excel export + verified feedback"]
```

| Komponen | Tanggung jawab | Bukan tanggung jawab |
|---|---|---|
| CNN ensemble | Mengklasifikasikan regime `bearish`, `bullish`, atau `sideways` | Menentukan entry sendirian |
| YOLO11s | Mendeteksi dan menggambar bounding box `order_block` dan `fair_value_gap` | Mendeteksi liquidity atau membuat keputusan trade langsung |
| Aturan OHLCV | Menghitung liquidity, sweep, EQH/EQL, BOS/CHOCH, candle pattern, volatilitas, dan konteks sesi | Menghasilkan bounding box visual |
| Trade Decision Engine | Menggabungkan seluruh bukti dan menerapkan execution/risk gate | Menjamin keuntungan atau mengeksekusi order |
| Journal | Menyimpan setiap analisis, outcome, dan versi model; menyediakan ekspor Excel | Menjadikan prediksi AI sebagai ground truth otomatis |

Kontrak kanonis yang dapat divalidasi mesin berada di [`config/project_contract.json`](config/project_contract.json).

## Baseline Penelitian Saat Ini

- CNN weighted ensemble (VGG11, VGG16, GoogLeNet, ResNet18) pada test 2025: accuracy `0.8607` dan Macro F1 `0.8427`.
- YOLO11s 50 epoch untuk OB/FVG pada final test 2025: precision `0.591`, recall `0.593`, mAP50 `0.590`, dan mAP50-95 `0.452`.
- Eksperimen YOLOv8n incremental sebelumnya valid sebagai proof of workflow, tetapi masih kalah dari cumulative baseline pada final test 2025.
- Pipeline FastAPI CNN→YOLO→OHLCV→structure→risk→execution gate sudah terintegrasi.
- Halaman upload React sudah memakai `/api/analysis/full` dan menampilkan keputusan publik, parameter risiko, reason codes, ringkasan regime/detection, serta annotated chart OB/FVG.
- Journal persisten, feedback outcome, dan ekspor Excel masih menjadi pekerjaan berikutnya.

Lihat [`docs/research/AI_TDSS_RESEARCH_SYNTHESIS.md`](docs/research/AI_TDSS_RESEARCH_SYNTHESIS.md) untuk metodologi dan batas klaim penelitian.

## Kebijakan Incremental Learning

Incremental learning berjalan sebagai proses **offline batch di laptop lokal**, bukan setiap kali pengguna mengunggah gambar dan bukan di GitHub Actions.

Data baru hanya dapat menjadi kandidat training jika outcome dapat diverifikasi dan lolos quality gate. Prediksi mentah AI tidak boleh digunakan sebagai label karena akan memperkuat kesalahan model sendiri. Candidate model dibandingkan dengan champion memakai frozen temporal holdout dan walk-forward evaluation sebelum boleh dipromosikan.

Trigger awal penelitian:

- preferred batch: 200 sampel eligible;
- minimum batch: 50 sampel eligible;
- interval maksimum: 30 hari, tetap mensyaratkan minimum batch;
- drift score: minimal 0.60, tetap mensyaratkan minimum batch.

Nilai tersebut merupakan parameter awal eksperimen, bukan angka final yang tidak dapat diubah.

## Penyimpanan Lokal

Raw OHLCV, chart PNG, checkpoint, dan artefak training berukuran besar tidak disimpan di GitHub. Root proyek lokal yang digunakan pada workstation pengembangan adalah:

```text
C:\Users\ASUS\Documents\Project\AI-TDSS
```

Setiap eksperimen wajib mencatat lima lokasi: input dataset, script/config, output run, checkpoint, serta report/metrics. Daftar lengkapnya tersedia di [`docs/experiments/LOCAL_EXPERIMENT_PLAN.md`](docs/experiments/LOCAL_EXPERIMENT_PLAN.md).

## Menjalankan Aplikasi

Backend kanonis:

```powershell
cd C:\Users\ASUS\Documents\Project\AI-TDSS\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Frontend Next.js/React:

```powershell
cd C:\Users\ASUS\Documents\Project\AI-TDSS\frontend
Copy-Item .env.example .env.local
npm ci
npm run dev
```

Nilai bawaan `NEXT_PUBLIC_API_URL` adalah `http://127.0.0.1:8000`. Ubah `.env.local` hanya jika backend dijalankan pada host atau port lain.

Validasi kontrak dan unit test ringan:

```powershell
cd C:\Users\ASUS\Documents\Project\AI-TDSS
python ai\scripts\validate_project_contract.py
$env:PYTHONPATH = "backend"
python -m unittest discover -s backend\tests -p "test_*.py" -v
```

## Dokumen Utama

- [Research synthesis](docs/research/AI_TDSS_RESEARCH_SYNTHESIS.md)
- [Local experiment plan](docs/experiments/LOCAL_EXPERIMENT_PLAN.md)
- [System overview](docs/sdd/chapters/CH01_System_Overview.md)
- [AI architecture](docs/sdd/chapters/CH06_AI_Architecture.md)
- [Trading journal](docs/sdd/chapters/CH11_Trading_Journal.md)
- [Incremental learning](docs/sdd/chapters/CH12_Incremental_Learning.md)
- [Final CNN ensemble result](ai/classification/reports/FINAL_CNN_ENSEMBLE_RESULT.md)
- [Final YOLO model selection](ai/benchmarks/reports/FINAL_YOLO_MODEL_SELECTION.md)

## Urutan Pengembangan Berikutnya

1. Simpan setiap hasil analisis, termasuk `WATCHLIST` dan `NO_TRADE`, ke journal milik pengguna.
2. Implementasikan feedback outcome terverifikasi dan eligibility store.
3. Implementasikan unduhan workbook Excel empat sheet.
4. Jalankan product acceptance untuk upload, annotated chart, journal, dan Excel.
5. Jalankan baseline end-to-end dan ablation secara lokal pada GBPUSD.
6. Jalankan incremental experiment hanya setelah feedback eligible memenuhi trigger.

Semua rekomendasi AI-TDSS bersifat bantuan analisis, bukan nasihat keuangan atau jaminan hasil trading.
