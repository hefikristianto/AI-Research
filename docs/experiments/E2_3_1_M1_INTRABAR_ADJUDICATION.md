# E2.3.1 M1 Intrabar Adjudication

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

## Interpretation boundary

The ambiguity observation rate and the outcome-sensitive ambiguity rate are reported separately. A resolved ordering is reviewed OHLCV-derived evidence, not permission to relabel raw model predictions automatically. A PASS still does not unlock 2024 and does not expose High Risk in production; it only supports a separate freeze decision.

## Next registered engineering slice

After E2.3.1 is reviewed, implement user-screenshot price-axis calibration before liquidity or candlestick retraining. The upload path must detect the plot and right price axis, OCR at least three price ticks, fit a robust linear `price(y)` mapping, validate monotonicity and residual error, and fail closed when the axis is cropped, logarithmic, percentage-based, or otherwise unverifiable. Candle-count normalization must remain separate: CNN receives a canonical recent-candle crop, while YOLO receives the full detected plot.
