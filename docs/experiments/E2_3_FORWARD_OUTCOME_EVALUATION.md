# E2.3 Forward Outcome Evaluation

- **Scope:** selected Standard and High Risk daily candidates, 2020–2023
- **Outcome source:** verified local GBPUSD M5 OHLCV
- **Training:** none
- **Model inference:** none
- **Frozen holdout 2024:** remains locked
- **Final test 2025:** remains locked
- **Production High Risk:** remains shadow-only

## Purpose

Daily decision coverage answers how often the system produces a candidate. It does not answer whether a pending entry fills or whether the candidate later reaches TP or SL. This slice adds a preregistered forward-outcome evaluator for the 250 selected daily candidates without replaying CNN/YOLO inference.

The machine-readable protocol is [`config/experiments/e2_3_forward_outcome_policy.json`](../../config/experiments/e2_3_forward_outcome_policy.json). The evaluator is [`ai/scripts/evaluate_e2_3_forward_outcomes.py`](../../ai/scripts/evaluate_e2_3_forward_outcomes.py).

The registered input composition is also fail-closed: 250 selected days, made
up of 96 Standard and 154 High Risk candidates (137 BUY and 113 SELL). The High
Risk subset must still contain 132 `ENTRY_DISTANCE_WARNING` and 22
`RR_RELAXATION` candidates before outcome labels are calculated.

## Locked execution protocol

| Dimension | Registered value |
|---|---|
| Signal time | selected `analysis_target_datetime` |
| Outcome stream | M5 raw OHLCV, first bar open at or after signal |
| Order types | `BUY_LIMIT`, `SELL_LIMIT` |
| Nominal entry | stored mapped limit entry |
| Horizon | 24 calendar hours |
| Unfilled order | `0R` |
| Filled but unresolved | exit at last available M5 close before expiry |
| Entry-bar target touch | ignored in primary path, TP in optimistic sensitivity |
| SL and TP in one M5 bar | SL-first primary, TP-first optimistic sensitivity |
| Primary friction | 1.5 pips per filled round trip |
| Sensitivity | 0.0, 1.0, 1.5, and 2.0 pips |
| Primary curve | event-level cumulative R, not a position-sized portfolio |

Using M5 for every selected source timeframe prevents a partial H1/H4 bar that began before the signal from leaking pre-signal movement into the outcome. All raw sources are checked against the SHA256 values already frozen in the daily snapshot manifest.

## Why order type is re-exported

The first shadow-policy export preserved Entry, SL, and TP but omitted `order_type`. The current backend generates `BUY_LIMIT` for bullish setups and `SELL_LIMIT` for bearish setups, yet the outcome evaluator does not silently infer that field. Shadow evaluator v1.1 verifies the cached raw response and writes:

- `order_type` in `snapshot_shadow_decisions.csv`;
- `selected_order_type` in `daily_decisions.csv`.

This rerun reads the existing 8,158 cached responses. It performs no endpoint request or model inference.

## Local run

From the repository root:

```powershell
$PY = ".\backend\.venv\Scripts\python.exe"
$env:PYTHONPATH = "backend"

$RUN_ID = "20260721_E2_3_daily_manifest_dev"
$E23 = ".\local_artifacts\experiments\$RUN_ID"

# Re-export the same frozen daily policy with explicit LIMIT order lineage.
& $PY ai\scripts\evaluate_e2_3_shadow_policy.py `
  --experiment-dir "$E23" `
  --progress-every 500

# Evaluate forward outcomes from local M5 files. No backend server is required.
& $PY ai\scripts\evaluate_e2_3_forward_outcomes.py `
  --experiment-dir "$E23" `
  --progress-every 25
```

The default raw root remains:

```text
ai/datasets/raw/ohlcv/
```

If the files live elsewhere, add `--raw-root "D:\path\to\ohlcv"`.

## Outputs

```text
local_artifacts/experiments/{RUN_ID}/
  config/forward_outcome_policy.json
  outcomes/daily_trade_outcomes.csv
  metrics/forward_outcome_metrics.json
  metrics/outcome_breakdown.csv
  reports/forward_outcome_report.md
  outcome_manifest.json
```

The report separates Standard, High Risk, and combined results. It records fill rate, conservative TP/SL counts, horizon exits, resolved win rate with Wilson interval, gross/net expectancy, profit factor, event-level drawdown, ambiguity, and friction sensitivity.

## Pre-holdout gate

The registered High Risk gate is evaluated on the 2023 policy-selection split and also requires a positive development expectancy. It checks minimum sample size, positive cost-adjusted expectancy, profit factor, conservative win rate, drawdown, ambiguity, data errors, and censoring.

A `PASS` does not itself unlock 2024 and never promotes High Risk to production. A separate freeze decision must record the reviewed results. A `FAIL` stops progression to holdout; it is not permission to tune using 2024 or 2025.

## Interpretation boundaries

- An unfilled limit is neither a win nor a loss and contributes `0R` to candidate-level expectancy.
- Same-bar uncertainty is explicitly conservative in the primary result.
- Event-level R does not model lot size, margin, concurrent exposure, balance compounding, or broker-specific commission.
- Development outcomes are reviewed labels derived from frozen OHLCV, not raw model predictions.
- 2024 remains the first untouched temporal generalization gate; 2025 remains the final test.
