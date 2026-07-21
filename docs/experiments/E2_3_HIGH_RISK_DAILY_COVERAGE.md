# E2.3 High-Risk Daily Coverage

- **Scope:** separate high-risk candidate policy and daily opportunity evaluation
- **Primary pair:** GBPUSD
- **Development:** 2020–2023
- **Frozen development holdout:** 2024
- **Final temporal test:** 2025
- **Training:** none in the initial policy experiment
- **Production status:** planned; current public decision contract remains unchanged

## Purpose

E2.3 evaluates whether AI-TDSS can provide a clearly separated high-risk analysis tier without weakening the standard decision policy. The product target is daily analysis availability. A daily trade is an exploratory coverage objective, not a quota that overrides quality and safety gates.

The previous 2025 decision audit contained 165 sampled chart images. Its number of detected or valid setups must not be interpreted as the number of opportunities in every trading day of the year. E2.3 therefore creates a complete day-level evaluation population before estimating daily candidate coverage.

## Locked Mapping Dependency

E2.2 selected `PLOT_AWARE` for canonical generated charts after matched 2024 development and 2025 frozen comparisons. Every E2.3 canonical run must therefore request `plot_aware_mapping=true`, record the mapping mode in its manifest, and preserve the `FULL_IMAGE` fail-closed fallback when plot geometry is uncertain.

The standard-only control and standard+high-risk candidate must consume the same inference event and the same mapping result. Mapping mode may not vary between policy arms. A failed, provisional, direction-mismatched, or low-confidence mapping remains a data-quality blocker and cannot be reclassified as high market risk. The arbitrary user-upload API default remains outside E2.3 scope and stays full-image until external screenshot validation passes.

## Decision Tiers

| Tier | Internal status | Intended public presentation |
|---|---|---|
| Standard | `TRADE_CANDIDATE` | `BUY` or `SELL`, standard risk badge |
| High risk | `HIGH_RISK_CANDIDATE` | `BUY` or `SELL`, prominent `HIGH RISK` badge |
| Review | `REVIEW` | `WATCHLIST` |
| Invalid/no setup | `INVALID`, `NO_SETUP`, or `WAIT` | `NO_TRADE` |

The standard tier and all existing thresholds remain unchanged during E2.3. The high-risk tier is evaluated as a parallel policy. It must never silently convert a standard `NO_TRADE` caused by invalid data into an actionable result.

## Two-Dimensional Gate

The policy separates data reliability from market risk:

```text
data_quality = VALID | PROVISIONAL | INVALID
market_risk  = STANDARD | HIGH | EXTREME
```

Entry, stop loss, and take profit may be exposed only when `data_quality=VALID`. A high-risk candidate means the price mapping is reliable but the market setup has weaker confluence. It must not mean that the system is uncertain where the entry price is located.

### Non-relaxable hard blockers

- no valid OB/FVG setup;
- metadata or canonical OHLCV unavailable;
- plot/price mapping provisional, direction-mismatched, or below the locked quality requirement;
- entry side invalid;
- zone invalidated;
- severe structure and higher-timeframe conflict;
- extreme volatility or prohibited news state;
- missing risk-reward calculation.

### Candidate high-risk conditions

Only soft market-quality conditions may define the high-risk tier, for example:

- advanced score below the standard candidate threshold but above the review floor;
- session suitability below the standard tier but not in the low-suitability band;
- entry distance in the existing warning band, but not beyond the hard maximum;
- risk-reward below the standard tier but above a separately validated minimum;
- reduced confluence while structure, direction, mapping, and invalidation checks remain valid.

Exact numerical bands are not selected from 2025. Candidate values must be registered before each development run and frozen before the 2024 holdout.

## Daily Evaluation Population

The unit of evaluation is one GBPUSD trading day, not one arbitrary screenshot.

1. Generate or select canonical chart snapshots at two predeclared daily slots: London and London–New York overlap.
2. Record the exact UTC timestamps and session-policy version; daylight-saving handling must be consistent for all years.
3. Run the existing multi-timeframe context for M5, M15, H1, and H4.
4. Retain at most the highest-ranked standard candidate and highest-ranked high-risk candidate per day.
5. Preserve days with only `WATCHLIST` or `NO_TRADE`; they remain part of the denominator.
6. Deduplicate heavily overlapping windows so repeated snapshots do not inflate candidate frequency.

Initial temporal use:

| Period | Use |
|---|---|
| 2020–2022 | policy design and diagnostics |
| 2023 | threshold/config selection and validation |
| 2024 | frozen development holdout and promotion gate |
| 2025 | one final temporal evaluation after policy lock |

## Required Metrics

### Coverage

- successful daily analysis rate;
- days with at least one standard candidate;
- additional days covered only by a high-risk candidate;
- combined candidate-day coverage;
- days with only `WATCHLIST`;
- days with `NO_TRADE`;
- candidates per week and per session;
- hard-blocker and soft-condition distributions.

### Decision and trading quality

- precision and recall reported separately for standard and high-risk tiers;
- verified win rate, expectancy in R, profit factor, average RR, and maximum drawdown per tier;
- combined-policy metrics compared with the unchanged standard-only policy;
- confidence/calibration and false-positive cost;
- pair/timeframe/session breakdown;
- result count and coverage alongside every performance metric.

Daily output is not evidence of daily trading quality. An increase in coverage is acceptable only when the registered minimum decision and risk metrics pass.

## Implementation Workflow

1. Load the selected E2.2 canonical policy and assert `plot_aware_mapping=true` with full-image fallback.
2. Build and validate the day-level snapshot manifest for 2020–2024.
3. Add `data_quality`, `risk_tier`, and `HIGH_RISK_CANDIDATE` internally without changing the standard path.
4. Implement a shadow-mode audit that records both standard-only and combined policies from the same inference event.
5. Select high-risk bands on 2020–2023 only.
6. Freeze configuration and evaluate once on 2024.
7. Promote the public high-risk badge and actionable levels only if the 2024 gate passes.
8. Commit the policy/config, then run one frozen 2025 final evaluation.
9. Store every tier, including `WATCHLIST` and `NO_TRADE`, in the journal and Excel export.

## Artifacts

```text
local_artifacts/experiments/{E2_3_ID}/
  input/daily_snapshot_manifest.csv
  config/high_risk_policy.json
  predictions/daily_decisions.csv
  metrics/daily_coverage.json
  metrics/tier_decision_metrics.json
  metrics/tier_trading_metrics.json
  metrics/session_timeframe_breakdown.csv
  reports/high_risk_promotion_decision.md
  manifest.json
```

Each artifact records the Git commit, dataset version, sample digest, session policy, mapping mode, standard policy version, high-risk policy version, and confirmation that no model training occurred.

## Promotion Gate

- E2.2 canonical mapping policy is `PLOT_AWARE`, both policy arms use it, and uncertain geometry falls back to full-image;
- standard-tier decisions are identical to the standard-only control;
- no hard data-quality blocker is bypassed;
- 2024 contains no unexplained request failure or lineage mismatch;
- high-risk performance is reported separately and meets preregistered minimums;
- combined coverage improves without unacceptable expectancy or drawdown regression;
- the UI makes `HIGH RISK` unambiguous and does not present it as guaranteed entry;
- journal and export retain tier, blockers, warnings, reasons, and outcome lineage;
- 2025 has not been used to adjust thresholds.

If the quality gate fails, the high-risk results remain `WATCHLIST` research telemetry. The project must not force a daily actionable entry merely to satisfy a product-frequency target.
