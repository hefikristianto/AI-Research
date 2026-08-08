# E2.4 User Screenshot Price-Axis Calibration

- **Status:** core service implemented; E2.4.1 OCR benchmark registered
- **API mode:** opt-in telemetry only
- **Training/inference:** no model training; calibration does not require CNN/YOLO inference
- **Production decision:** unchanged
- **Canonical OHLCV requirement:** unchanged
- **High Risk:** shadow-only and unchanged
- **Frozen holdout 2024:** unread
- **Final test 2025:** unread

## Purpose

E2.2 can map horizontal YOLO coordinates on canonical charts, but an arbitrary TradingView or MT5 screenshot does not automatically provide an auditable price scale. E2.4 estimates a separate vertical relation:

```text
price(y) = slope * y + intercept
```

The service reads price labels from the right axis, requires at least three valid OCR ticks, fits the relation robustly, and validates direction, residual error, vertical coverage, decimal precision, pair range, and suspected non-linear scale. This slice supplies telemetry and evaluation evidence only. It cannot replace canonical OHLCV or turn a non-actionable recommendation into `BUY`/`SELL`.

The machine-readable contract is [`config/experiments/e2_4_user_screenshot_price_axis_calibration.json`](../../config/experiments/e2_4_user_screenshot_price_axis_calibration.json).

## Architecture boundary

| Component | E2.4 responsibility |
|---|---|
| Plot geometry | Supplies a candidate right edge; uncertain geometry falls back to a conservative right-side OCR strip |
| OCR adapter | Returns text, confidence, and bounding geometry for candidate price labels |
| Calibration service | Parses localized prices, removes outliers, fits `price(y)`, and validates the fit |
| Canonical OHLCV converter | Remains the only source authorized for production entry/SL/TP |
| CNN | Continues unchanged in this slice; canonical recent-candle crop is a separate future slice |
| YOLO | Continues to receive the full detected plot; no class or threshold changes |

The OCR adapter is replaceable. The initial implementation lazily uses `pytesseract` when that local backend exists. Missing Python package, missing Tesseract executable, or OCR failure returns `FAIL_CLOSED`; it never silently creates a price mapping.

## Registered validation rules

| Rule | Value/action |
|---|---|
| Minimum valid ticks | 3 |
| Minimum OCR confidence | 0.50 |
| Minimum vertical coverage | 0.12 of image height |
| Minimum linear R² | 0.995 |
| Maximum normalized RMSE | 0.08 tick step |
| Maximum normalized residual | 0.20 tick step |
| Expected direction | Price decreases as pixel Y increases |
| Supported scale | Linear price only |
| Pair range | Pair metadata must resolve GBPUSD or XAUUSD |
| Number formats | Dot/comma decimal and dot/comma thousands variants |

The service fails closed when:

- fewer than three price ticks survive parsing and confidence filters;
- tick labels occupy too little vertical range, indicating a cropped or unverifiable axis;
- values are not strictly descending with increasing Y;
- the robust linear fit fails its residual or R² gate;
- decimal precision is inconsistent;
- the axis is declared or detected as percentage/logarithmic;
- pair metadata is missing or unsupported;
- the OCR backend is unavailable or errors.

## API telemetry

The existing endpoint accepts two opt-in parameters:

```text
screenshot_price_axis_calibration=true
price_axis_scale_mode=AUTO|LINEAR|LOG|PERCENT
```

The response adds:

```text
price_axis_calibration
```

Default requests return `NOT_REQUESTED`. A valid experimental fit returns `CALIBRATED`; every unverifiable condition returns `FAIL_CLOSED`. Both states explicitly set:

```text
entry_price_authorized=false
production_decision_changed=false
```

Therefore this field is diagnostic evidence, not another path around the canonical OHLCV gate.

## Local verification

From the project root:

```powershell
$PY = ".\backend\.venv\Scripts\python.exe"
$env:PYTHONPATH = "backend"

& $PY -m unittest discover `
  -s backend\tests `
  -p "test_screenshot_price_axis_calibration_service.py" `
  -v

& $PY -m unittest discover `
  -s backend\tests `
  -p "test_e2_4_user_screenshot_price_axis_calibration.py" `
  -v

& $PY ai\scripts\validate_project_contract.py
```

Once an OCR backend is deliberately installed and recorded, a local API request may enable the telemetry flag. Backend startup and the normal upload flow remain unchanged. Do not enable the flag as a frontend default in this slice.

## E2.4.1 benchmark before any promotion

E2.4.1 menambahkan Tesseract 5 runner, tiga preprocessing profile, 32 deterministic smoke fixtures, portable external-fixture builder, SHA256 evidence, dan resumable per-task cache. Protocol serta command Windows berada di [`E2_4_1_OCR_BACKEND_BENCHMARK.md`](E2_4_1_OCR_BACKEND_BENCHMARK.md).

Synthetic smoke tidak dapat memilih profile atau meluluskan gate. Acceptance hanya memakai minimal 32 screenshot eksternal TradingView/MT5 yang telah direview.

The next E2.4 slice must build a frozen fixture manifest with known tick text and pixel centers. Report separately by:

- TradingView, MT5, and deterministic synthetic renderer;
- light, dark, and custom candle themes;
- GBPUSD and XAUUSD;
- M5, M15, H1, and H4;
- desktop/mobile aspect ratio, zoom, chrome, crop, and indicator panels;
- dot-decimal and comma-decimal locale.

Required metrics:

- price-axis region detection rate;
- OCR tick precision/recall and exact-text accuracy;
- calibrated/failed-closed/false-calibration counts;
- pixel-to-price MAE and maximum error, stratified by pair;
- residual and R² distributions;
- fail-closed recall for cropped/log/percentage/unsupported fixtures;
- parity showing no change to the canonical production decision.

No accuracy target may be selected from 2024 or 2025 trading outcomes. Screenshot fixtures may contain those visual styles only when they are not used to inspect or tune the frozen E2.3 outcome streams.

## Interpretation boundary

A readable axis is not proof that the screenshot timestamp, timeframe, broker feed, or displayed candles match canonical OHLCV. E2.4 can reduce vertical price uncertainty, but it does not validate market history by itself. Production entry levels remain blocked until the broader upload identity and canonical-data checks are reviewed.

After the OCR backend and external fixture benchmark pass, E2.4.2 freezes screenshot theme/platform robustness before any frontend default is considered. Structure-based liquidity and OHLCV candlestick rules follow as separate slices. High Risk remains shadow-only and 2024/2025 remain locked throughout E2.4.
