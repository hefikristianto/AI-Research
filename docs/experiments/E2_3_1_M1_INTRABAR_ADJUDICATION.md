# E2.3.1 M1 Intrabar Adjudication

- **Reviewed result:** `FAIL` — High Risk remains shadow-only
- **Baseline:** frozen E2.3 forward-outcome result, 250 selected days
- **Review population:** 55 pre-existing M5 ambiguity observations
- **Outcome-sensitive subset:** 40 observations
- **Adjudication source:** local GBPUSD M1, 2020–2023
- **Training/inference:** none
- **Candidate selection and thresholds:** unchanged
- **Frozen holdout 2024:** unread
- **Final test 2025:** unread

## Purpose

The E2.3 M5 evaluator correctly treated event order inside one five-minute bar as unknown. Its conservative primary result therefore counted a bar touching SL and TP as SL-first and did not credit a target touched on the entry bar. That produced 55 ambiguity observations; only 40 changed net R between the conservative and optimistic paths.

E2.3.1 narrows that uncertainty with M1 data. It does not generate new candidates and does not revisit any non-ambiguous outcome. The machine-readable contract is [`config/experiments/e2_3_1_m1_intrabar_adjudication.json`](../../config/experiments/e2_3_1_m1_intrabar_adjudication.json), and the runner is [`ai/scripts/adjudicate_e2_3_m1_intrabar.py`](../../ai/scripts/adjudicate_e2_3_m1_intrabar.py).

## Frozen adjudication rules

| Condition | E2.3.1 action |
|---|---|
| M1 shows TP before SL after fill | Resolve to TP |
| M1 shows SL before TP after fill | Resolve to SL |
| Target appears before limit fill | Ignore that target and retain baseline continuation |
| Limit is already marketable at M1 open, then target touches | Resolve to TP |
| Entry and target occur in the same M1 bar with unknown order | `M1_UNRESOLVED`; retain conservative primary |
| SL and TP occur in the same M1 bar | `M1_UNRESOLVED`; retain conservative primary |
| M1 bar cannot reproduce or match the registered M5 bar | Data error; fail the integrity gate |

Entry, stop-loss, take-profit, 24-hour horizon, nominal LIMIT fill, 1.5-pip primary friction, candidate set, High Risk RR floor, and all pre-holdout gates remain unchanged.

## Source lineage gate

The local M1 files must be exactly:

```text
ai/datasets/raw/ohlcv/GBPUSD/M1/{2020..2023}/GBPUSD_M1_{YEAR}_RAW.csv
```

The adjudicator reads SHA256 values from the reviewed local manifest:

```text
ai/datasets/raw/ohlcv/GBPUSD/M1/GBPUSD_M1_2020_2023_MT5_STAGING_MANIFEST.json
```

It verifies the registered row counts:

| Year | Rows |
|---:|---:|
| 2020 | 373,047 |
| 2021 | 373,170 |
| 2022 | 372,759 |
| 2023 | 371,316 |

For every ambiguous M5 window, the runner aggregates the matching M1 bars and requires exact OHLC agreement with the frozen M5 source within `1e-9`. This independently confirms feed, timezone, and bar alignment for the evidence actually used. Raw data and its local manifest remain excluded from Git.

## Run locally

The backend server is not needed.

```powershell
cd C:\Users\ASUS\Documents\Project\AI-TDSS

$PY = ".\backend\.venv\Scripts\python.exe"
$RUN_ID = "20260721_E2_3_daily_manifest_dev"
$E23 = ".\local_artifacts\experiments\$RUN_ID"
$M1_MANIFEST = ".\ai\datasets\raw\ohlcv\GBPUSD\M1\GBPUSD_M1_2020_2023_MT5_STAGING_MANIFEST.json"

& $PY -m pip install -r ".\backend\requirements-test.txt"

& $PY ai\scripts\adjudicate_e2_3_m1_intrabar.py `
  --experiment-dir "$E23" `
  --m1-manifest "$M1_MANIFEST" `
  --progress-every 10
```

The runner fails closed unless the frozen inputs still match:

- 250 candidate rows;
- 96 Standard and 154 High Risk;
- 137 BUY and 113 SELL;
- 55 ambiguity observations and 40 outcome-sensitive observations;
- frozen baseline CSV SHA256 `b0fc31a8...e6bcd837`;
- no access to 2024 or 2025.

## Outputs

```text
local_artifacts/experiments/{RUN_ID}/
  config/e2_3_1_m1_adjudication_policy.json
  config/e2_3_1_m1_source_contract.json
  outcomes/daily_trade_outcomes_m1_adjudicated.csv
  outcomes/m1_ambiguity_adjudications.csv
  metrics/e2_3_1_m1_adjudication_metrics.json
  metrics/e2_3_1_outcome_breakdown.csv
  reports/e2_3_1_m1_adjudication_report.md
  e2_3_1_manifest.json
```

Inspect the result:

```powershell
Get-Content "$E23\reports\e2_3_1_m1_adjudication_report.md" -Raw

Import-Csv "$E23\outcomes\m1_ambiguity_adjudications.csv" |
  Group-Object m1_resolution_status |
  Select-Object Name, Count

Get-Content "$E23\metrics\e2_3_1_m1_adjudication_metrics.json" -Raw
```

## Recorded reviewed result

The reviewed run used clean commit `f1984f53a94ecea3077f6272ae9f573a9aeaebee`. All seven archived artifact hashes matched their manifest, all 55 registered ambiguity observations were processed, 56 required M1/M5 source windows passed exact OHLC reconciliation, and no M1 data error occurred. The review archive SHA256 is `4542cd5945ab3392360d11500dc0c44cc5167b3ad4a8329b657c37d0eb6584b1`.

| M1 resolution | Count |
|---|---:|
| Target first | 17 |
| Target before limit fill | 11 |
| Stop first | 2 |
| Stop and target remain in one M1 bar | 17 |
| Entry and target remain in one M1 bar | 8 |

Fifteen primary outcomes changed. Ambiguity fell from 55 to 25 observations, while outcome-sensitive ambiguity fell from 40 to 18.

| Combined primary metric | M5 conservative | M1 adjudicated |
|---|---:|---:|
| Filled | 172 | 172 |
| TP / SL | 53 / 117 | 66 / 104 |
| Resolved win rate | 31.1765% | 38.8235% |
| Net expectancy / candidate | -0.1153R | +0.0584R |
| Net profit factor | 0.8119 | 1.1097 |
| Maximum event drawdown | 39.3268R | 21.5338R |
| Ambiguity observations | 55 | 25 |

The registered decision is nevertheless **FAIL**. The only failed check is `maximum_selection_ambiguous_filled_rate`: the High Risk policy-selection split retains 5 ambiguous outcomes among 20 fills (`25%`), above the preregistered `10%` maximum. Every other registered gate and every M1 integrity check passed.

| High Risk metric | Development | Policy selection |
|---|---:|---:|
| Candidates / filled | 117 / 70 | 37 / 20 |
| Ambiguous / filled | 14 / 70 (20%) | 5 / 20 (25%) |
| Resolved win rate | 36.2319% | 45.0000% |
| Net expectancy / candidate at 1.5 pips | +0.0056R | +0.0139R |
| Net profit factor | 1.0117 | 1.0359 |
| Expectancy bootstrap 95% interval | [-0.2588R, +0.2871R] | [-0.3351R, +0.3885R] |
| Net expectancy / candidate at 2.0 pips | -0.0551R | -0.0447R |

The positive point estimates are too small and too friction-sensitive to support a profitability or promotion claim. They also have wide uncertainty intervals crossing zero. Diagnostics such as stronger BUY than SELL performance or stronger RR-relaxation than entry-distance-warning performance are recorded only as hypotheses; they must not be converted into post-hoc filters on this result.

The machine-readable review decision is [`config/experiments/e2_3_1_m1_adjudication_result.json`](../../config/experiments/e2_3_1_m1_adjudication_result.json).

## Interpretation boundary

The ambiguity observation rate and the outcome-sensitive ambiguity rate are reported separately. A resolved ordering is reviewed OHLCV-derived evidence, not permission to relabel raw model predictions automatically. A PASS still does not unlock 2024 and does not expose High Risk in production; it only supports a separate freeze decision.

Because the recorded result is `FAIL`, High Risk remains shadow-only and neither 2024 nor 2025 may be opened. The `10%` ambiguity limit must not be relaxed after observing the result. Any tick-level follow-up requires a separately preregistered experiment and is not automatically authorized by this run.

## Next registered engineering slice

After E2.3.1 is reviewed, implement user-screenshot price-axis calibration before liquidity or candlestick retraining. The upload path must detect the plot and right price axis, OCR at least three price ticks, fit a robust linear `price(y)` mapping, validate monotonicity and residual error, and fail closed when the axis is cropped, logarithmic, percentage-based, or otherwise unverifiable. Candle-count normalization must remain separate: CNN receives a canonical recent-candle crop, while YOLO receives the full detected plot.
