# E2.4.2 OCR Theme and Platform Robustness

- **Status:** implementation frozen; fresh holdout not evaluated
- **Evidence role:** the 32 E2.4.1 fixtures are development regression data only
- **Freeze ID:** `E2_4_2_FREEZE_20260905_01`
- **Frozen implementation commit:** `32cd3015f694ae9fc36bd545d160f6b6c5c1a1fd`
- **Next gate:** one fresh, post-freeze set of at least 32 reviewed external screenshots
- **Training/model inference:** not performed
- **Trading outcomes:** not read
- **Production decision/default:** unchanged
- **Entry authorization:** always false

## Why E2.4.2 exists

The reviewed Windows E2.4.1 run processed all 32 external fixtures with
Tesseract `5.5.3.20260724`, but every registered profile failed at least one
gate. The submitted result ZIP has SHA256
`a9ca2ad2576171c9a5898afd59f2d716158bc47fbdfba7821d039d78fb3d1241`;
the frozen fixture-manifest SHA256 is
`888c3627713798f87d58e1b76fe92eac5c4ca8e192419c75a6fe8f5087517852`.
No E2.4.1 profile was selected.

| E2.4.1 profile | Precision | Recall | Calibration recall | Fail-closed recall | Result |
|---|---:|---:|---:|---:|---|
| `GRAY_AUTOCONTRAST_2X_PSM11` | 97.77% | 48.08% | 45.83% | 100.00% | FAIL |
| `GRAY_FOOTER_TRIM_AUTOCONTRAST_2X_PSM11` | 98.47% | 53.02% | 50.00% | 100.00% | FAIL |
| `GRAY_INVERT_AUTOCONTRAST_2X_PSM11` | 97.75% | 47.80% | 45.83% | 100.00% | FAIL |
| `RAW_RGB_PSM11` | 93.50% | 71.15% | 95.83% | 100.00% | FAIL |

Review of the image, row, and raw-OCR evidence found three engineering
causes:

1. The wide grayscale crop retained MT5 plot/grid content next to the axis.
   On several screenshots this content joined a price label as a spurious
   leading digit, so an otherwise valid tick could not be parsed.
2. Raw RGB recovered more MT5 labels, but it also accepted the filled live
   current-price badge and several OCR mistakes as static axis ticks.
3. A fixed absolute-price MAE is not comparable across pairs and chart zoom
   levels. Pixel and tick-step normalized errors directly measure the mapping
   quality visible in the screenshot, so E2.4.2 gates those metrics and keeps
   absolute GBPUSD/XAUUSD MAE as reported, non-gating telemetry.

## Registered remediation

The machine-readable contract is
[`config/experiments/e2_4_2_ocr_robustness.json`](../../config/experiments/e2_4_2_ocr_robustness.json).
It registers exactly one adaptive candidate:
`ADAPTIVE_WIDE_FOOTER2_TIGHT_GRAY3_PSM11`.

The provider performs two deterministic Tesseract PSM 11 passes:

| Pass | Intended coverage | Preprocessing |
|---|---|---|
| `WIDE_FOOTER_TRIM_GRAY2` | TradingView and faint/light labels | registered right strip, safe contiguous-footer trim, grayscale autocontrast, 2× |
| `TIGHT_GRAY3` | MT5 axis labels without plot/grid contamination | tight right-side strip, grayscale autocontrast, 3× |

The tight pass begins at `11/14` of the already bounded outer axis region.
When the outer fallback begins at 72% of canvas width, its effective start is
94% of canvas width; if detected geometry safely extends the outer region,
the relative ratio stays fixed.

For both passes, OCR observations on a strongly different, locally uniform
filled background are rejected as live-price badges. The rule uses only
source-image color structure; it does not use pair, platform, expected text,
or fixture ground truth.

Percentage evidence from either pass preempts calibration. Otherwise, pass
selection is fixed in this order: calibrated status, inlier count, vertical
coverage, normalized RMSE, then the wide-pass tie-break. Each raw pass,
rejected observation, source hash, and selected pass is persisted for audit.

## Linux development regression result

The candidate was run on Linux with Tesseract `5.3.4` against the already
reviewed E2.4.1 set. Because those same fixtures informed the remediation,
this is development evidence and cannot pass the E2.4.2 freeze.
The machine-readable result and evidence hashes are stored in
[`config/experiments/e2_4_2_development_result.json`](../../config/experiments/e2_4_2_development_result.json).

| Metric | Development result | Registered target |
|---|---:|---:|
| External fixtures | 32 | ≥ 32 |
| Tick precision | 99.72% | ≥ 99.00% |
| Tick recall | 98.63% | ≥ 95.00% |
| Exact text | 99.16% | ≥ 95.00% |
| Expected calibration recall | 100.00% | ≥ 95.00% |
| Fail-closed recall | 100.00% | 100.00% |
| False calibration | 0.00% | 0.00% |
| Normalized mapping MAE | 0.007794 tick step | ≤ 0.10 |
| Mapping MAE | 0.301863 px | ≤ 0.75 px |

All 24 valid fixtures calibrated and all eight negative fixtures failed
closed. Aggregate matching produced 359 true positives, one false positive,
and five false negatives. This is a technical development-target pass only:
`benchmark_pass=false`, `freeze_evaluated=false`, and
`production_promotion_allowed=false`.

## Windows development verification

The same candidate and unchanged 32-image fixture pack were rerun on Windows
with Tesseract `5.5.3.20260724` and pytesseract `0.3.13`. The submitted ZIP
has SHA256
`07d99c4d83d1a36ec12cb1c92c44caa5f1f17896a42a20f3c03964efd27e9713`.
Its ZIP entries, raw-response hashes, aggregate metrics, boundary fields, and
all 15 technical gates were independently checked. The complete Windows test
suite also passed: 114 tests, zero failures.

| Metric | Windows result | Registered target |
|---|---:|---:|
| External fixtures | 32 | >= 32 |
| Tick precision | 100.00% | >= 99.00% |
| Tick recall | 98.90% | >= 95.00% |
| Exact text | 99.17% | >= 95.00% |
| Expected calibration recall | 100.00% | >= 95.00% |
| Fail-closed recall | 100.00% | 100.00% |
| False calibration | 0.00% | 0.00% |
| Normalized mapping MAE | 0.007793 tick step | <= 0.10 |
| Mapping MAE | 0.301831 px | <= 0.75 px |

All 24 valid fixtures calibrated and all eight negative fixtures failed
closed. Aggregate matching produced 360 true positives, zero false positives,
and four false negatives. The evidence remains development-only:

```text
Evidence role: DEVELOPMENT_REGRESSION_ONLY
Development targets: PASS; E2.4.2 freeze: NOT EVALUATED
```

The audited artifact lineage is recorded in
[`config/experiments/e2_4_2_development_result.json`](../../config/experiments/e2_4_2_development_result.json).

## Implementation freeze and fresh holdout rule

Implementation freeze `E2_4_2_FREEZE_20260905_01` was recorded at
`2026-09-05T13:00:43+00:00`. It locks the provider, runner, preprocessing
values, badge rule, selection order, matching rules, and gates at implementation
commit `32cd3015f694ae9fc36bd545d160f6b6c5c1a1fd`.

The runtime source hashes are the exact CRLF bytes reviewed on Windows; the
contract also records canonical LF hashes for repository lineage. Run the
fresh holdout from the same Windows checkout so the frozen runtime hashes are
verified before OCR starts.

Only screenshots captured after the freeze timestamp are eligible. Capture
and annotate at least 32 new external TradingView/MT5 screenshots with the
same required pair/platform/theme/timeframe/locale marginal coverage.

The builder deliberately refuses an E2.4.2 manifest unless the contract has
this freeze record. Copy
[`templates/e2_4_2_external_annotations.example.json`](templates/e2_4_2_external_annotations.example.json),
fill the frozen ID and post-freeze capture timestamp, then use the same
external-fixture builder with `--contract` pointing to the E2.4.2 contract.

The original 32 screenshots must not be relabeled as the fresh holdout. After
the first fresh-holdout run, no profile or threshold change is allowed. A
failed holdout remains a failed E2.4.2 result and requires a separately
registered successor experiment.

Even a valid holdout PASS remains engineering evidence only. It cannot change
BUY/SELL/WATCHLIST/NO_TRADE, entry/SL/TP, High Risk, canonical OHLCV, or any
locked trading-outcome dataset.
