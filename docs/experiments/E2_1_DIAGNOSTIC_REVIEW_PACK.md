# E2.1 GBPUSD Diagnostic Review Pack

- **Scope:** targeted local inference diagnostics
- **Training:** prohibited
- **Decision-rule changes:** none
- **Frozen reference:** E2 GBPUSD 2025 baseline

## Purpose

E2.1 explains why a valid visual setup stops before an actionable public decision. It preserves the E2 decision rules and adds observability for detector composition, zone recency, canonical OHLCV mapping, advanced scoring, session scoring, risk-reward, and execution-quality normalization.

This is a forensic review of a frozen baseline. It is not a threshold search, profitability test, or source of ground-truth labels.

## E2 Observation That Triggered E2.1

The local GBPUSD 2025 baseline processed 165 chart windows with 165 successful responses and no request failures.

| Stage | Count | Rate |
|---|---:|---:|
| At least one detection | 70 | 42.42% |
| Both OB and FVG classes present | 39 | 23.64% |
| Paired and valid setup | 37 | 22.42% |
| Public WATCHLIST | 12 | 7.27% |
| Actionable BUY/SELL | 0 | 0.00% |

Detector composition was 95 windows with no detection, 24 with FVG only, seven with Order Block only, and 39 with both classes. Pairing succeeded in 37 of the 39 windows containing both classes (94.87%). This means the pairing service is not the primary funnel bottleneck.

Across 37 valid setups, 21 exceeded three ATR from entry, 18 had low mapping confidence, and 13 had risk-reward below 1.5. Three setups had no hard blocker but remained in review. The original audit did not retain the advanced score, session score, pre-normalization status, or detailed zone recency needed to distinguish those cases.

## Added Diagnostic Contract

Audit schema version 2 records:

- both-class presence and candidate-pair combinations;
- rightmost detection and best-pair distance from the image's right edge;
- best setup score, detector validity, confidence, and spatial distances;
- base structure, advanced, HTF alignment, volatility, session, and RR values;
- decision/status/readiness before execution-quality normalization;
- blockers and warnings added specifically by quality normalization;
- mapping mode, index errors, mapped timestamps, and candles from chart end;
- zone status, touches, invalidation, and entry-side validity;
- annotated-image status, SHA256 verification, and review-artifact paths.

The endpoint also returns a nested `execution_gate.quality_normalization` trace. This trace is observational and does not alter the public recommendation.

## Target Cases

| Image ID | Diagnostic role |
|---|---|
| `GBPUSD_M5_2025_20250115_192000_0029` | No hard blocker; generic execution review |
| `GBPUSD_H1_2025_20250430_010000_0021` | Distance warning only |
| `GBPUSD_H1_2025_20250522_200000_0025` | Near entry with low mapping confidence |
| `GBPUSD_H4_2025_20250522_000000_0007` | Near entry with very low mapping confidence |
| `GBPUSD_H4_2025_20250613_160000_0008` | Both detector classes but no accepted pair |
| `GBPUSD_H4_2025_20250708_080000_0009` | Second both-class/no-pair control |
| `GBPUSD_M15_2025_20250128_220000_0019` | Near entry rejected by RR, side, and volatility gates |

These cases were selected to explain distinct branches of the existing pipeline. They must not be presented as a random accuracy sample.

## Run Locally

Keep the backend running, then use a separate PowerShell terminal:

```powershell
Set-Location "C:\Users\ASUS\Documents\Project\AI-TDSS"
& ".\backend\.venv\Scripts\Activate.ps1"

$REVIEW = ".\local_artifacts\decision_coverage\gbpusd_2025_e2_1_review"

python ai\scripts\audit_decision_coverage.py `
  --year 2025 `
  --pair GBPUSD `
  --confidence-threshold 0.25 `
  --image-id "GBPUSD_M5_2025_20250115_192000_0029" `
  --image-id "GBPUSD_H1_2025_20250430_010000_0021" `
  --image-id "GBPUSD_H1_2025_20250522_200000_0025" `
  --image-id "GBPUSD_H4_2025_20250522_000000_0007" `
  --image-id "GBPUSD_H4_2025_20250613_160000_0008" `
  --image-id "GBPUSD_H4_2025_20250708_080000_0009" `
  --image-id "GBPUSD_M15_2025_20250128_220000_0019" `
  --review-pack `
  --output-dir $REVIEW
```

`--image-id` is exact and repeatable. It cannot be combined with `--sample-size`. Missing IDs cause an explicit failure instead of silently changing the review population.

## Output

```text
gbpusd_2025_e2_1_review/
  run_config.json
  decision_coverage_rows.csv
  decision_coverage_summary.json
  decision_coverage_summary.md
  review_pack/
    responses/{image_id}.json
    annotated/{image_id}.png
```

Each JSON response preserves the complete endpoint payload. Every decoded PNG is checked against the SHA256 returned by the backend, and the verification result is written to the row CSV.

To prepare the artifacts for review without committing them to Git:

```powershell
Compress-Archive `
  -Path "$REVIEW\review_pack\*" `
  -DestinationPath "$REVIEW\review_pack.zip" `
  -Force
```

## Acceptance Gate

- exactly seven selected image IDs and seven successful responses;
- seven response JSON files;
- seven annotated PNG files with SHA256 verification equal to `1`;
- no `review_artifact_error`;
- populated pre-quality, advanced, session, RR, mapping, and recency fields where a valid setup exists;
- no model training, threshold change, or production-gate change.

## Decision After Review

If a defect is confirmed, implement and tune it only on development/validation periods before running a frozen comparison. Do not use these seven final-test cases to choose a new threshold. Possible follow-up experiments are detector co-detection review, right-edge/zone-recency validation, canonical mapping calibration, or execution-score calibration.
