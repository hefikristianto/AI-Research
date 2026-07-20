# AI-TDSS Decision Coverage Audit

**Scope:** local inference audit; no model training
**Primary population:** GBPUSD temporal test year 2025
**Production threshold:** 0.25

## Purpose

This audit measures how often the deployed pipeline progresses through each decision stage:

1. at least one YOLO detection;
2. at least one paired Order Block/Fair Value Gap setup;
3. at least one pair that passes preliminary setup scoring;
4. public `WATCHLIST`;
5. actionable `BUY` or `SELL`;
6. public `NO_TRADE` and its blocker distribution.

The runner calls the same `/api/analysis/full` endpoint used by the React application. It therefore evaluates the live CNN, YOLO, OHLCV, structure, HTF, session, risk, execution-gate, and public-recommendation path instead of reproducing only an offline scoring table.

Coverage is not accuracy, profitability, or evidence that an entry is correct. This audit must finish before outcome-based decision metrics are interpreted.

## Preconditions

Run the backend in the first PowerShell terminal:

```powershell
Set-Location "C:\Users\ASUS\Documents\Project\AI-TDSS"
& ".\backend\.venv\Scripts\Activate.ps1"
$env:PYTHONPATH = "backend"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Confirm that these local-only inputs exist:

```text
ai/datasets/metadata/chart_image_metadata.csv
ai/datasets/raw/charts/GBPUSD/{M5,M15,H1,H4}/2025/*.png
ai/datasets/raw/ohlcv/GBPUSD/{M5,M15,H1,H4}/2025/*.csv
CNN champion checkpoints
runs/detect/ai/benchmarks/runs/yolo11s_cumulative_2020_2024_50e/weights/best.pt
```

## Smoke Audit

Use a small deterministic sample before the complete run:

```powershell
Set-Location "C:\Users\ASUS\Documents\Project\AI-TDSS"
& ".\backend\.venv\Scripts\Activate.ps1"

$AUDIT = ".\local_artifacts\decision_coverage\gbpusd_2025_smoke"

python ai\scripts\audit_decision_coverage.py `
  --year 2025 `
  --pair GBPUSD `
  --sample-size 10 `
  --seed 42 `
  --confidence-threshold 0.25 `
  --output-dir $AUDIT
```

The default request omits annotated PNG base64 to reduce batch latency and disk/memory overhead. This does not change CNN, YOLO, pairing, or decision results.

## Complete GBPUSD Audit

After the smoke sample completes without request errors, run all available GBPUSD 2025 chart windows:

```powershell
$AUDIT = ".\local_artifacts\decision_coverage\gbpusd_2025_full"

python ai\scripts\audit_decision_coverage.py `
  --year 2025 `
  --pair GBPUSD `
  --seed 42 `
  --confidence-threshold 0.25 `
  --output-dir $AUDIT
```

To limit the audit to selected timeframes, repeat `--timeframe`:

```powershell
python ai\scripts\audit_decision_coverage.py `
  --year 2025 `
  --pair GBPUSD `
  --timeframe M15 `
  --timeframe H1 `
  --confidence-threshold 0.25 `
  --output-dir ".\local_artifacts\decision_coverage\gbpusd_2025_m15_h1"
```

## Resume After Interruption

Every completed image is appended immediately to the row CSV. Repeat the identical command with `--resume` to skip existing image IDs:

```powershell
python ai\scripts\audit_decision_coverage.py `
  --year 2025 `
  --pair GBPUSD `
  --seed 42 `
  --confidence-threshold 0.25 `
  --output-dir ".\local_artifacts\decision_coverage\gbpusd_2025_full" `
  --resume
```

Resume is rejected if the sample, threshold, timeframe, context size, or UTC offset differs from the original run.

## Output Contract

Each audit folder contains:

```text
run_config.json
decision_coverage_rows.csv
decision_coverage_summary.json
decision_coverage_summary.md
```

`decision_coverage_rows.csv` stores one row per selected image, including:

- request status and latency;
- regime label/confidence;
- OB, FVG, pairing, and valid preliminary-setup counts;
- internal and public decisions;
- execution status and actionable flag;
- mapping status/confidence and entry distance in ATR;
- blockers, warnings, reasons, and errors.

The summary also reports mean, p50, p95, and maximum end-to-end request latency.

`run_config.json` records the Git commit/dirty flag, dataset version, manifest/config hashes, sample digest, seed, threshold, context sizes, and confirmation that no training was performed.

The JSON and Markdown summaries report the denominator explicitly. Failed or missing images are never silently counted as `NO_TRADE`; they are reported separately and excluded from successful-response coverage rates.

## Interpretation Rules

- Do not search for individual screenshots until one returns BUY/SELL. That creates selection bias.
- Do not lower the production threshold after inspecting final-test results.
- Report detection coverage, paired-setup coverage, watchlist rate, actionable rate, and no-trade rate together.
- Report dominant blockers by pair and timeframe before changing any gate.
- A high `NO_TRADE` rate may reflect deliberate abstention; it is not automatically a defect.
- A high actionable rate is not automatically desirable and is not evidence of profitability.
- Trading performance requires verified future outcomes, frozen execution rules, spread/slippage assumptions, and a separate report.
- Raw predictions and uploaded screenshots do not become ground truth automatically.

## Next Decision

After the complete GBPUSD audit:

1. verify that missing/error rates are acceptable;
2. identify the dominant funnel drop-off and blocker distribution;
3. decide whether the next experiment targets detector recall, pairing, mapping, HTF alignment, or risk feasibility;
4. preserve 2025 as final evaluation data and perform any tuning on development/validation periods only;
5. run the chart-color/platform robustness experiment as a separate protocol.
