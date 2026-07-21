# E2.2 Plot-Aware Mapping Result and Freeze

- **Decision:** `FROZEN_FOR_SINGLE_FINAL_COMPARISON`
- **Frozen:** 21 July 2026
- **Primary pair:** GBPUSD
- **Development evidence:** 2024
- **Final comparison:** 2025, one run per mode
- **Training performed:** no
- **Production default:** `FULL_IMAGE` remains unchanged
- **Candidate:** opt-in `PLOT_AWARE`

## Decision

The plot-aware coordinate transform passed the E2.2 development gate and is frozen for one paired 2025 comparison. This is not yet a production-default promotion. Requests that omit `plot_aware_mapping=true` continue to use full-image mapping, and uncertain plot geometry continues to fail closed to the legacy transform.

The freeze covers the geometry constants, detector threshold, sample construction, mapping comparison, and interpretation rules. Results from 2025 may estimate generalization, but they may not be used to retune this implementation.

The machine-readable contract is [`config/experiments/e2_2_plot_mapping_freeze.json`](../../config/experiments/e2_2_plot_mapping_freeze.json).

## Development Lineage

Both complete runs used the same 165 GBPUSD 2024 images and were produced from a clean implementation tree.

| Field | Frozen value |
|---|---|
| Implementation commit | `f7993442cfc9f63b381ea8ddd02fab79d5d29c15` |
| Dataset | `v1.0` / `raw_chart_generated` |
| Sample seed | `42` |
| Sample digest | `8b756a1aebe9383a90b44669842da0de05953a4525bcbbb9deee322c7a041d34` |
| Metadata SHA256 | `78e0e6c2a1273cc2f8e5844e309ada3e740ba6c7b32d016d8cbe7375df11a65d` |
| Project contract SHA256 | `5149b0e8b31b819217f6a44c83373d3a4d2d7faf1f72976592bc3de4cc8694d0` |
| Ensemble config SHA256 | `86e50b207d5b5915c17d321719b83f258aba463159cf476983a2c459928d1a6f` |
| Detector threshold | `0.25` |
| Chart/context candles | `100 / 300` |
| Timeframes | `H1, H4, M15, M5` |
| Successful/failed per mode | `165 / 0` |

Only timestamps and the `plot_aware_mapping` flag differed between the two run configurations.

## Complete 2024 A/B Result

Upstream model behavior remained identical. The calibration changed selected candle indices and mapping confidence only after a valid OB/FVG pair existed.

| Metric | Full-image | Plot-aware | Interpretation |
|---|---:|---:|---|
| YOLO detection | 59/165 | 59/165 | unchanged |
| Both YOLO classes | 34/165 | 34/165 | unchanged |
| OB/FVG pair | 33/165 | 33/165 | unchanged |
| Valid scored setup | 33/165 | 33/165 | unchanged |
| Geometry detected | 165/165 | 165/165 | canonical chart coverage |
| Calibration applied | 0 | 33 | only paired candidate rows |
| `NO_TRADE` | 150 | 150 | unchanged |
| `WATCHLIST` | 15 | 12 | three promoted cases |
| `BUY`/`SELL` | 0/0 | 3/0 | not an acceptance metric |
| Request failures | 0 | 0 | no regression |

Across 30 rows with observable canonical matches:

| Paired index error | Improved | Same | Worse | Mean legacy minus plot-aware |
|---|---:|---:|---:|---:|
| Order Block | 28 | 2 | 0 | 2.966667 candles |
| Fair Value Gap | 22 | 5 | 3 | 1.766667 candles |

Mapping status did not change on any of the 165 rows. Nineteen rows lost only the `LOW_MAPPING_CONFIDENCE` quality blocker; no detector, pairing, session, risk-reward, or execution threshold changed.

## Decision Changes

Exactly three rows changed from `WATCHLIST` to `BUY`:

| Image ID | Last chart candle (UTC) | Mapping confidence | OB error | FVG error | RR | Zone state |
|---|---|---:|---:|---:|---:|---|
| `GBPUSD_H1_2024_20240222_120000_0010` | 2024-02-28 15:00 | 0.3049 → 0.8466 | 5 → 0 | 4 → 1 | 3.36 | mitigated, 4 touches |
| `GBPUSD_H1_2024_20240730_050000_0037` | 2024-08-05 09:00 | 0.5791 → 0.9041 | 3 → 0 | 4 → 1 | 8.41 | partially mitigated, 1 touch |
| `GBPUSD_M15_2024_20240125_170000_0018` | 2024-01-26 17:45 | 0.4865 → 0.8115 | 3 → 0 | 4 → 1 | 4.67 | mitigated, 3 touches |

The same mapped OHLCV structures, setup scores, risk-reward values, sessions, and entry distances were preserved. The transition was caused by removing the low-confidence mapping blocker after better horizontal localization.

The repeated mitigated/touched zone state is a decision-quality question for a separate zone-policy or outcome experiment. It is not evidence against the coordinate correction and must not be used to retune E2.2.

## Artifact and Product Verification

Eight predetermined cases were rendered in both modes. All 16 annotated PNGs reported `RENDERED`, passed SHA256 verification, and had no review-artifact error. Bounding boxes remained visually identical between modes; the decision banner changed only where the public recommendation changed. Right-edge annotation labels remained within image bounds.

The strongest changed case, `GBPUSD_H1_2024_20240730_050000_0037`, was also reproduced through the React upload page using its last chart candle timestamp, `2024-08-05 09:00 UTC`. The web response matched the batch result: `BUY`, entry `1.27162`, stop loss `1.27016`, take profit `1.28388`, and risk-reward `8.41`.

This verifies the frontend-to-backend path. It does not verify whether the trade later reached take profit or whether the system is profitable.

## Frozen Geometry Constants

| Constant | Value |
|---|---:|
| Difference threshold | 24 |
| Minimum/maximum plot span | 0.55 / 0.98 |
| Minimum/maximum margin | 0.01 / 0.20 |
| Minimum active-column ratio | 0.10 |

Tests bind these values to `ChartPlotGeometryService`. A later code change that silently drifts from the freeze contract must fail CI.

## Single 2025 Comparison

Run this only after the freeze commit is merged and the backend is running from a clean `main`. Do not add `--sample-size`; both modes must process the complete available 2025 population.

```powershell
Set-Location "C:\Users\ASUS\Documents\Project\AI-TDSS"
& ".\backend\.venv\Scripts\Activate.ps1"

$E22Final = ".\local_artifacts\experiments\20260721_E2_2_final_2025"

python ai\scripts\audit_decision_coverage.py `
  --year 2025 `
  --pair GBPUSD `
  --seed 42 `
  --confidence-threshold 0.25 `
  --chart-candles 100 `
  --context-candles 300 `
  --output-dir "$E22Final\baseline"

python ai\scripts\audit_decision_coverage.py `
  --year 2025 `
  --pair GBPUSD `
  --seed 42 `
  --confidence-threshold 0.25 `
  --chart-candles 100 `
  --context-candles 300 `
  --plot-aware-mapping `
  --output-dir "$E22Final\plot_aware"
```

If a run is interrupted, repeat only its original command with `--resume` and the same output directory. Do not create a replacement configuration or a second completed run.

Validate the paired lineage before interpreting any decision count:

```powershell
python ai\scripts\validate_e2_2_final_comparison.py `
  --baseline "$E22Final\baseline\run_config.json" `
  --candidate "$E22Final\plot_aware\run_config.json"
```

The validator requires matching code, dataset, metadata, project-contract, ensemble, sample digest, population, and run parameters. It also requires a clean tree, complete processing, baseline `false`, and candidate `true`.

## Interpretation Boundary

- The local nearest-candle matcher is diagnostic telemetry, not independently reviewed ground truth.
- Better index localization does not establish setup accuracy, expectancy, or profitability.
- The three development `BUY` cases have no verified outcome labels in this experiment.
- No `SELL` transition was observed, so directional generalization remains unproven.
- Earlier 2025 audits informed the defect investigation; the locked E2.2 comparison must therefore be reported as a final comparison for this calibration, not as an untouched test set for the entire project.
- Whatever the 2025 result, geometry constants and thresholds stay frozen. Any future revision requires a new experiment ID and a new development/validation split.

After the paired 2025 report is archived, E2.3 may inherit the chosen mapping policy and begin its separate development-first high-risk daily-coverage workflow.
