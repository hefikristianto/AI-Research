# E2.3 Standard / High Risk Shadow Policy

- **Input:** completed 2020–2023 E2.3 inference cache
- **Standard arm:** unchanged cached production decision
- **High Risk arm:** registered development candidate, shadow only
- **Frozen holdout:** 2024 remains unread
- **Final temporal test:** 2025 remains locked
- **Training/inference:** none in this stage
- **Outcome evaluation:** not yet performed

## Development Result Used for Registration

The complete cache contains 8,158 successful snapshot responses: 6,086 policy-design rows from 2020–2022 and 2,072 policy-selection rows from 2023. All analysis clocks were validated, and no request failure remained.

The unchanged Standard arm produced 107 actionable snapshot decisions. At day level, before the new daily direction-conflict gate, this represented 65 of 781 planned design days and 32 of 260 planned selection days.

The development grid showed that `advanced_score` did not separate the eligible soft-risk cases: every otherwise valid candidate already met the Standard score threshold of `0.60`. Risk/reward therefore became the useful registered selection variable.

| High Risk RR floor | Additional 2020–2022 days | Additional 2023 days |
|---:|---:|---:|
| 1.50 | 101 | 37 |
| 1.40 | 107 | 38 |
| 1.30 | 115 | 40 |
| **1.25** | **119** | **40** |
| 1.20 | 123 | 40 |
| 1.10 | 128 | 48 |
| 1.00 | 132 | 52 |

The registered candidate uses `RR >= 1.25`. Lowering the floor to `1.20` added only four design days and zero selection days, so the extra relaxation was rejected. The selected floor produced 210 eligible snapshots before daily direction deduplication: 184 existing `REVIEW` rows in the 1.5–3 ATR entry-distance warning band and 26 `WAIT` rows whose only blocker was `RISK_REWARD_BELOW_1_5`.

This selection is evidence of coverage stability only. It is not evidence of accuracy, profitability, or acceptable drawdown.

## Registered High Risk Gate

A High Risk candidate must satisfy every data-quality condition:

- successful cached response with validated anti-lookahead clock;
- at least one paired OB/FVG setup;
- `MAPPED` and `PLOT_AWARE` price conversion;
- plot-aware calibration applied;
- non-provisional mapping with confidence at least `0.65`;
- bullish or bearish setup direction with finite entry, stop-loss, and take-profit;
- advanced score at least `0.60`;
- session score at least `0.65`;
- entry distance no more than `3.0 ATR`.

Exactly two soft-market-risk rules are allowed:

1. `ENTRY_DISTANCE_WARNING`: no blocker, RR at least `1.50`, and entry distance above `1.5` through `3.0 ATR`;
2. `RR_RELAXATION`: the only blocker is `RISK_REWARD_BELOW_1_5`, with RR from `1.25` up to but not including `1.50`.

Any unknown blocker or warning fails closed. In particular, no setup, provisional/failed mapping, invalid entry side, invalidated zone, structure/HTF conflict, extreme volatility, distance above 3 ATR, or unavailable RR can become High Risk.

## Daily Aggregation

The evaluator retains at most one candidate per tier per trading day. Standard always takes precedence. Candidates are ranked without outcome information by:

1. advanced score descending;
2. mapping confidence descending;
3. RR descending;
4. entry distance ascending;
5. timeframe duration descending;
6. analysis target ascending;
7. snapshot ID ascending.

If actionable snapshots on the same day disagree between BUY and SELL, the daily result fails closed to `WATCHLIST`. This is necessary because the compact development audit found one known Standard conflict on 10 August 2022 between H4 BUY and M5 SELL. The raw-response evaluator also checks High Risk direction conflicts before selecting a daily candidate.

## Run the Evaluator

Run this only after the 2020–2023 inference summary reports complete development coverage and zero failure. The backend does not need to be running.

```powershell
cd C:\Users\ASUS\Documents\Project\AI-TDSS

$PY = ".\backend\.venv\Scripts\python.exe"
$RUN_ID = "20260721_E2_3_daily_manifest_dev"
$E23 = ".\local_artifacts\experiments\$RUN_ID"

& $PY ai\scripts\evaluate_e2_3_shadow_policy.py `
  --experiment-dir "$E23" `
  --progress-every 500
```

The evaluator verifies all 8,158 response SHA256 values and CSV/JSON parity. It performs no HTTP request.

## Outputs

```text
local_artifacts/experiments/{RUN_ID}/
  config/high_risk_policy.json
  predictions/snapshot_shadow_decisions.csv
  predictions/daily_decisions.csv
  metrics/daily_coverage.json
  metrics/session_timeframe_breakdown.csv
  reports/high_risk_shadow_policy_report.md
  manifest.json
```

Inspect the result:

```powershell
Get-Content "$E23\metrics\daily_coverage.json" -Raw
Get-Content "$E23\reports\high_risk_shadow_policy_report.md" -Raw

Import-Csv "$E23\predictions\daily_decisions.csv" |
  Group-Object evaluation_split, daily_status |
  Select-Object Name, Count
```

Expected integrity conditions:

- 8,158 cached snapshot responses verified;
- 210 High Risk snapshot candidates before daily aggregation;
- 2024 and 2025 absent;
- Standard decisions unchanged at snapshot level;
- every daily direction conflict converted to `WATCHLIST`;
- entry/SL/TP exposed only for selected Standard or High Risk candidates;
- snapshot `order_type` and daily `selected_order_type` explicitly match `BUY_LIMIT`/`SELL_LIMIT` from the cached response;
- `training_performed=false`, `model_inference_performed=false`, and `outcome_evaluation_performed=false`.

The exact selected-day counts can be lower than the compact coverage simulation because the final evaluator reads setup direction from raw responses and fails closed on daily High Risk direction conflicts.

## Next Gate

Do not run the 2024 holdout after coverage evaluation alone. The next slice attaches verified M5 forward outcomes to the frozen daily selections and reports fill rate, conservative win rate, expectancy in R, profit factor, event-level drawdown, ambiguity, and result counts separately for Standard and High Risk. The registered protocol is [`E2_3_FORWARD_OUTCOME_EVALUATION.md`](E2_3_FORWARD_OUTCOME_EVALUATION.md). If the registered High Risk candidate fails those development gates, it remains research telemetry and no alternative floor is tuned from 2024 or 2025.
