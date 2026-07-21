# E2.2 Plot-Aware Mapping Calibration

- **Scope:** deterministic coordinate calibration and observability
- **Primary pair:** GBPUSD
- **Development period:** 2020–2024
- **Frozen final test:** 2025
- **Training:** prohibited
- **Default production behavior:** unchanged

## Purpose

E2.2 tests whether YOLO X coordinates should be mapped to the detected candle-plot area instead of the complete image width. Canonical chart images contain horizontal margins, so `round(x * (n - 1))` can shift the estimated candle index even when the bounding box itself is reasonable.

This experiment does not change YOLO confidence, OB/FVG pairing thresholds, risk-reward rules, session rules, or model weights. Plot-aware mapping is opt-in through `plot_aware_mapping=true`; requests without that flag continue to use full-image mapping.

## Evidence and Guardrail

The seven-case E2.1 final-test review showed a repeated horizontal offset between visual zones and OHLCV indices. One H4 case was a pre-quality trade candidate that became `WATCHLIST` only after low mapping confidence was added. This is evidence of a possible deterministic mapping defect, not evidence that the proposed trade was correct or profitable.

The E2.1 cases may motivate E2.2, but they must not determine geometry constants or acceptance thresholds. Calibration is developed on synthetic images and GBPUSD 2020–2024. The 2025 population is rerun once only after the implementation and acceptance rules are frozen.

## Implementation Contract

The endpoint estimates horizontal plot bounds using contrast against the image-border background. The method is color-agnostic and therefore supports light and dark canonical chart themes without assuming green/red candles.

The result is returned as `chart_geometry`:

- `DETECTED` means the candidate bounds passed conservative span, margin, and foreground-density validation;
- `FALLBACK` means the geometry was uncertain and the full image width remains in use;
- a service error also fails closed to full-image mapping.

When opt-in mapping is active and geometry is `DETECTED`, the coordinate transform is:

```text
x_plot = clamp((x_image - plot_left) / (plot_right - plot_left), 0, 1)
index  = round(x_plot * (window_length - 1))
```

The audit records both legacy and plot-aware indices/errors so the change can be inspected rather than inferred from the final recommendation alone.

## Additional Observability

Audit schema version 3 adds:

- geometry status, method, confidence, and normalized left/right bounds;
- requested/applied calibration state and selected index mode;
- legacy and plot-aware OB/FVG approximate indices and index errors;
- evaluated/rejected OB-FVG combinations plus X/Y rejection reasons;
- explicit `SESSION_BELOW_TRADE_CANDIDATE` for session scores from 0.50 through 0.64;
- right-edge label clamping on annotated charts.

These additions do not relax any gate. In particular, an OB/FVG pair just outside the current spatial limit remains rejected until a separate labeled validation experiment supports a threshold change.

## Local A/B Protocol

Start the patched backend in one PowerShell terminal:

```powershell
Set-Location "C:\Users\ASUS\Documents\Project\AI-TDSS"
& ".\backend\.venv\Scripts\Activate.ps1"
$env:PYTHONPATH = "backend"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal, run a deterministic 2024 baseline:

```powershell
Set-Location "C:\Users\ASUS\Documents\Project\AI-TDSS"
& ".\backend\.venv\Scripts\Activate.ps1"

$E22 = ".\local_artifacts\experiments\20260720_E2_2_plot_mapping"

python ai\scripts\audit_decision_coverage.py `
  --year 2024 `
  --pair GBPUSD `
  --sample-size 40 `
  --seed 42 `
  --confidence-threshold 0.25 `
  --output-dir "$E22\baseline"
```

Run the identical sample with plot-aware mapping:

```powershell
python ai\scripts\audit_decision_coverage.py `
  --year 2024 `
  --pair GBPUSD `
  --sample-size 40 `
  --seed 42 `
  --confidence-threshold 0.25 `
  --plot-aware-mapping `
  --output-dir "$E22\plot_aware"
```

The two `run_config.json` files must have the same `sample_digest_sha256`, seed, pair, timeframes, chart/context sizes, detector threshold, and code lineage. Only `plot_aware_mapping` may differ.

After the smoke A/B is valid, repeat both commands without `--sample-size` on the complete available GBPUSD 2024 development population. Use new output directories; do not overwrite smoke results.

## Primary Evaluation

Compare only rows with successful requests and observable canonical matches.

| Metric | Desired result |
|---|---|
| Request failures | No increase caused by calibration |
| Geometry detection | High coverage on canonical generated charts; every failure uses `FALLBACK` |
| OB index error | Plot-aware mean/median lower than legacy on development data |
| FVG index error | Plot-aware mean/median lower than legacy on development data |
| Mapping confidence | Improvement without new direction mismatch or request error |
| Decision changes | Individually explained by mapping telemetry; not judged by signal count alone |
| Default-mode parity | Requests without the flag keep legacy index mode and prior decisions |

Inspect `decision_coverage_rows.csv`, `decision_coverage_summary.json`, and `decision_coverage_summary.md`. A higher number of `BUY`/`SELL` results is not an acceptance criterion.

## Promotion Gate

Freeze plot-aware mapping for the single 2025 comparison only if all conditions hold:

1. unit tests pass for light/dark geometry, fallback behavior, opt-in mapping, pairing telemetry, session explanation, and annotation bounds;
2. both development A/B runs have matching sample lineage and zero unexplained request failures;
3. plot-aware OB and FVG index error improve on development data with adequate observed matches;
4. every geometry validation failure falls back to legacy mapping;
5. no detector, pairing, session, RR, or execution threshold was tuned using 2025;
6. the implementation and decision rule are committed before reopening the final-test population.

The frozen 2025 comparison may estimate the generalization effect, but it must not be used to iterate constants. Outcome accuracy and profitability remain separate experiments requiring verified future outcomes.

After the mapping policy is frozen, the next workflow is [`E2_3_HIGH_RISK_DAILY_COVERAGE.md`](E2_3_HIGH_RISK_DAILY_COVERAGE.md). E2.3 must inherit the approved mapping policy so low mapping quality cannot be relabeled as market risk.

## Non-Goals

- retraining CNN or YOLO;
- supporting arbitrary TradingView/MT5 chrome in this step;
- changing the OB/FVG class set;
- relaxing pairing distance or execution thresholds;
- converting raw predictions or user uploads into ground truth;
- claiming that improved localization implies profitable trading.
