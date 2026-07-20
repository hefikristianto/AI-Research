# AI-TDSS Frontend

Frontend Next.js/React untuk mengunggah chart, mengirim metadata market ke FastAPI, dan menampilkan rekomendasi AI-TDSS beserta annotated chart.

## Menjalankan secara lokal

Pastikan backend FastAPI sudah berjalan pada `http://127.0.0.1:8000`, lalu jalankan:

```powershell
cd C:\Users\ASUS\Documents\Project\AI-TDSS\frontend
Copy-Item .env.example .env.local
npm ci
npm run dev
```

Buka `http://localhost:3000/upload`. Jika backend memakai alamat lain, ubah `NEXT_PUBLIC_API_URL` di `.env.local`.

## Kontrak halaman upload

Halaman upload mengirim multipart image ke `POST /api/analysis/full` bersama:

- pair: GBPUSD sebagai default, XAUUSD untuk riset sekunder;
- timeframe: M5, M15, H1, atau H4;
- waktu candle terakhir pada chart;
- UTC offset waktu chart.

UI hanya menampilkan level entry/SL/TP/RR untuk keputusan `BUY` atau `SELL` yang lolos seluruh execution gate. `WATCHLIST` dan `NO_TRADE` tetap menampilkan alasan serta annotated chart, tetapi bukan entry siap eksekusi.

## Validasi

```powershell
npm run lint
npx tsc --noEmit
npm run build
```

Pelatihan model tidak dijalankan oleh frontend maupun GitHub Actions. Training AI-TDSS tetap merupakan proses offline pada laptop lokal.
