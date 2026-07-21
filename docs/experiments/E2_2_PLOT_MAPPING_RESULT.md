# E2.2 Plot-Aware Mapping Result and Decision

- **Decision:** `PROMOTED_FOR_CANONICAL_PIPELINE`
- **Decided:** 21 July 2026
- **Primary pair:** GBPUSD
- **Development evidence:** 2024
- **Final comparison:** 2025, completed once per mode
- **Training performed:** no
- **Canonical generated charts and E2.3:** `PLOT_AWARE`
- **Arbitrary user-upload API default:** `FULL_IMAGE` remains unchanged
- **Uncertain geometry fallback:** `FULL_IMAGE`

## Decision

The frozen paired GBPUSD 2025 comparison confirms the plot-aware coordinate transform on canonical generated charts. Plot-aware mapping is therefore the selected policy for the canonical research pipeline and for E2.3. The change corrects a systematic horizontal offset without changing detection, pairing, or setup coverage.

This is deliberately not a global upload-default promotion. Requests that omit `plot_aware_mapping=true` continue to use full-image mapping, and uncertain geometry continues to fail closed to that transform. Arbitrary TradingView/MT5 screenshots with variable themes, chrome, panels, crops, and aspect ratios require a separate external-screenshot validation before the default may change.

The frozen constants remain in [`config/experiments/e2_2_plot_mapping_freeze.json`](../../config/experiments/e2_2_plot_mapping_freeze.json). The final evidence and selected scope are recorded in [`config/experiments/e2_2_plot_mapping_decision.json`](../../config/experiments/e2_2_plot_mapping_decision.json).

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

## Frozen 2025 Comparison

Both final runs processed the complete available 165-image GBPUSD 2025 population with zero request failures. Their clean code commit, data hashes, seed, sample digest, detector threshold, and chart/context sizes matched; only timestamps and the requested mapping mode differed.

| Field | Final value |
|---|---|
| Code commit | `9e3d33ff6bcb3664bcc98fb13ea6c7e4b4ee80af` |
| Sample seed | `42` |
| Sample digest | `cae8c845214492a1085dfd93e6979b28e0dee1867ed6b4e168b1988a2a95c9f3` |
| Successful/failed per mode | `165 / 0` |
| Geometry detected | `165 / 165` in both modes |
| Calibration applied | `0 / 37` for full-image / plot-aware |
| Full comparison ZIP SHA256 | `be7e46ceed448228d151287bf163b9ddd93c8f82e48154fa99422412548c825c` |

Upstream coverage was identical in both modes: 70 images had a YOLO detection, 39 contained both classes, 37 had an OB/FVG pair, and 37 had a valid scored setup.

| Public decision | Full-image | Plot-aware |
|---|---:|---:|
| `NO_TRADE` | 153 | 150 |
| `WATCHLIST` | 12 | 14 |
| `BUY` | 0 | 0 |
| `SELL` | 0 | 1 |

Decision transitions were 150 `NO_TRADE → NO_TRADE`, 11 `WATCHLIST → WATCHLIST`, three `NO_TRADE → WATCHLIST`, and one `WATCHLIST → SELL`.

| Image ID | Last chart candle (UTC) | Transition | Primary effect | Remaining state |
|---|---|---|---|---|
| `GBPUSD_H1_2025_20250529_010000_0026` | 2025-06-04 05:00 | `NO_TRADE → WATCHLIST` | RR 0.142 → 3.045 | entry distance 5.65 ATR remains a blocker |
| `GBPUSD_H4_2025_20250218_080000_0003` | 2025-03-12 20:00 | `NO_TRADE → WATCHLIST` | `DIRECTION_MISMATCH → MAPPED` | entry distance 2.10 ATR remains a warning |
| `GBPUSD_H4_2025_20250522_000000_0007` | 2025-06-13 12:00 | `WATCHLIST → SELL` | mapping confidence 0.271 → 0.813 | all execution gates pass; outcome unverified |
| `GBPUSD_M5_2025_20250109_142000_0017` | 2025-01-09 22:35 | `NO_TRADE → WATCHLIST` | RR 0.630 → 4.703 | entry distance 17.32 ATR remains a blocker |

Across 35 paired rows with observable canonical matches:

| Metric | Legacy mean/median | Plot-aware mean/median | Improved | Same | Worse |
|---|---:|---:|---:|---:|---:|
| OB index error | 2.714 / 3 | 0.000 / 0 | 31 | 4 | 0 |
| FVG index error | 2.771 / 3 | 0.971 / 1 | 25 | 8 | 2 |
| Mapping confidence | 0.6558 mean | 0.8988 mean | 31 | 4 | 0 |

The two FVG regressions were one-candle shifts in adjacent impulse/FVG interpretation. Neither changed the public decision. One M15 row changed from `MAPPED` to `NO_LOCAL_OB_FVG_MATCH`; it stayed `NO_TRADE` and added `PRICE_MAPPING_PROVISIONAL`, which is the intended fail-closed behavior when no supported local match exists.

Twenty-one rows changed blocker sets. Plot-aware mapping removed `LOW_MAPPING_CONFIDENCE` 18 times, `RISK_REWARD_BELOW_1_5` twice, and `PRICE_MAPPING_PROVISIONAL` once; it added `PRICE_MAPPING_PROVISIONAL` on the safe M15 regression. No detector, pairing, session, risk, or execution threshold changed.

## Development Decision Changes

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

## Executed Frozen 2025 Comparison

The following frozen commands produced the archived comparison above. They are retained for reproducibility, not as permission to rerun E2.2 and tune constants from another 2025 result. Both modes processed the complete available population; no `--sample-size` was used.

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

The completed configurations were validated before interpreting any decision count:

```powershell
python ai\scripts\validate_e2_2_final_comparison.py `
  --baseline "$E22Final\baseline\run_config.json" `
  --candidate "$E22Final\plot_aware\run_config.json"
```

The validator confirmed matching code, dataset, metadata, project-contract, ensemble, sample digest, population, and run parameters. It also confirmed a clean tree, complete processing, baseline `false`, and candidate `true`.

## Final Targeted Review

Seven predetermined diagnostic cases were rendered in both modes. All 14 annotated PNGs reported `RENDERED`, matched their recorded SHA256 values, and had no artifact errors. The review sample digest was `6efdb4138fdeb79ce52fce4ceb1b84851b8c7327a78ff195fbc68f4c8f8eb349`; the review ZIP SHA256 was `6d013ddcc498439618a98050d8bb5108250802b425e91d8ec3f943391bff2d8e`.

Pixel comparison showed that the detected boxes and chart content were identical between modes. On the four public-decision changes, all differing pixels were confined to the decision banner; every pixel below row 32 was unchanged. Right-edge labels stayed within image bounds. This review supports the coordinate-policy decision on canonical generated charts, but it does not validate arbitrary broker-platform screenshots.

The only actionable final transition was `GBPUSD_H4_2025_20250522_000000_0007`: `WATCHLIST → SELL`, entry `1.35977`, stop loss `1.362394642857143`, take profit `1.352275`, and RR `2.8556`. Its outcome has not been verified, so it is not evidence of accuracy or profitability.

## Interpretation Boundary

- The local nearest-candle matcher is diagnostic telemetry, not independently reviewed ground truth.
- Better index localization does not establish setup accuracy, expectancy, or profitability.
- The three development `BUY` cases and the final `SELL` case have no verified outcome labels in this experiment.
- One `SELL` transition demonstrates execution-path coverage, not directional accuracy or profitability.
- Earlier 2025 audits informed the defect investigation; the locked E2.2 comparison must therefore be reported as a final comparison for this calibration, not as an untouched test set for the entire project.
- Whatever the 2025 result, geometry constants and thresholds stay frozen. Any future revision requires a new experiment ID and a new development/validation split.
- Canonical generated charts use plot-aware mapping in E2.3. The public arbitrary-upload default remains full-image until external TradingView/MT5 screenshot validation passes.

E2.2 is complete. The active next workflow is E2.3 high-risk daily coverage, using the selected plot-aware mapping policy for its canonical chart population.
