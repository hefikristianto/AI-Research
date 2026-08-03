# E2.3 Resumable Daily Inference Cache

- **Scope:** canonical GBPUSD snapshots from the reviewed E2.3 manifest
- **Current inference period:** development and policy selection, 2020–2023
- **Frozen holdout:** 2024, blocked until the Standard/High Risk policy is frozen
- **Final temporal test:** 2025, locked
- **Training:** none
- **Policy selection:** none in this stage

## Why This Stage Exists

The Standard and High Risk policies must be compared on the same model output. Running the full CNN/YOLO/OHLCV pipeline separately for each policy would waste time and could introduce an unmatched comparison if code, model state, or request parameters changed between runs.

[`ai/scripts/run_e2_3_daily_inference.py`](../../ai/scripts/run_e2_3_daily_inference.py) therefore calls `/api/analysis/full` once per canonical snapshot and stores the complete response in a verified local cache. A later shadow-policy evaluator will derive both policy arms from that same response.

This stage does not label outcomes, train a model, choose High Risk thresholds, or make a profitability claim.

## Locked Request Contract

The machine-readable contract is [`config/experiments/e2_3_daily_inference.json`](../../config/experiments/e2_3_daily_inference.json).

| Parameter | Locked value |
|---|---|
| Endpoint | `/api/analysis/full` |
| YOLO confidence | `0.25` |
| Chart candles | `100` |
| Context candles | `300` |
| Market UTC offset | `0.0` |
| Annotated chart in response | `false` |
| Plot-aware mapping | `true` |
| OHLCV cutoff | manifest `chart_end_open_datetime` |
| Session clock | manifest `analysis_target_market_datetime` |

The runner validates that the backend response loaded OHLCV at the declared cutoff and returned `ANALYSIS_TARGET_VALIDATED` with anti-lookahead protection. A malformed or mismatched response is recorded as `RESPONSE_CONTRACT_ERROR`; it is not counted as `NO_TRADE`.

## Preconditions

The experiment root must contain the completed renderer artifacts:

```text
local_artifacts/experiments/{RUN_ID}/
  input/
    daily_snapshot_manifest.csv
    daily_manifest_summary.json
    run_config.json
  images/
  render/
    daily_snapshot_render_rows.csv
    daily_snapshot_render_summary.json
```

Before the first HTTP request, the runner verifies:

- the exact reviewed manifest digest;
- all 10,230 `READY` rows are present in the render audit;
- the render summary is complete and contains no failure;
- each selected PNG exists and matches its render SHA256;
- canonical dimensions are `691 × 482`;
- selected rows belong only to 2020–2023;
- the request and guardrail contract has not changed.

## Start the Backend

Use the backend virtual environment because it contains the local model dependencies:

```powershell
cd C:\Users\ASUS\Documents\Project\AI-TDSS

& ".\backend\.venv\Scripts\Activate.ps1"
$env:PYTHONPATH = "backend"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Keep that terminal open. Run the inference command from a second PowerShell terminal.

## Eight-Snapshot Smoke Run

```powershell
cd C:\Users\ASUS\Documents\Project\AI-TDSS

$PY = ".\backend\.venv\Scripts\python.exe"
$RUN_ID = "20260721_E2_3_daily_manifest_dev"
$E23 = ".\local_artifacts\experiments\$RUN_ID"

& $PY ai\scripts\run_e2_3_daily_inference.py `
  --experiment-dir "$E23" `
  --year 2020 `
  --limit 8 `
  --fail-fast
```

Inspect the checkpoint:

```powershell
Get-Content "$E23\inference\daily_snapshot_inference_summary.json" -Raw
Import-Csv "$E23\inference\daily_snapshot_inference_rows.csv" |
  Select-Object snapshot_id, request_status, cache_status, public_decision,
    detection_count, pair_count, analysis_clock_validated
```

Expected smoke conditions:

- eight `SUCCESS` rows;
- `analysis_clock_validated = 1` for every row;
- no `REQUEST_ERROR` or `RESPONSE_CONTRACT_ERROR`;
- `frozen_holdout_inference_rows = 0`;
- `final_2025_inference_rows = 0`.

## Full Development Run

Continue in the same output with `--resume`:

```powershell
& $PY ai\scripts\run_e2_3_daily_inference.py `
  --experiment-dir "$E23" `
  --resume
```

The default population is every `READY` snapshot from 2020–2023. Responses from the smoke run are verified and reused. If the terminal, backend, or laptop stops, run the same command again with `--resume`.

The endpoint currently serializes YOLO prediction for thread safety. A full development run can therefore take several hours; using multiple simultaneous runners against the same backend is not an approved speed-up.

## Output Contract

```text
local_artifacts/experiments/{RUN_ID}/inference/
  daily_snapshot_inference_rows.csv
  daily_snapshot_inference_summary.json
  run_config.json
  responses/
    POLICY_DEVELOPMENT/{YEAR}/{TIMEFRAME}/{SNAPSHOT_ID}.json
    POLICY_SELECTION/2023/{TIMEFRAME}/{SNAPSHOT_ID}.json
```

Each response file is an envelope containing:

- manifest, contract, image, and request lineage;
- HTTP status and latency;
- the complete full-analysis response;
- an explicit `training_performed=false`;
- enough data for orphan recovery if the process stops after writing JSON but before updating the CSV.

On resume, both the response file SHA256 and its internal lineage are verified. A changed image, response, request contract, render audit, or pipeline-content digest fails closed instead of silently mixing runs.

## Completion Gate

The development cache is complete only when the summary reports:

- `complete_for_policy_development = true`;
- `remaining_policy_development_rows = 0`;
- `failed_inference_rows = 0`;
- `frozen_holdout_inference_rows = 0`;
- `final_2025_inference_rows = 0`;
- one model path and one locked request contract;
- raw responses remain explicitly marked as not ground truth.

After this gate, run the offline matched Standard/High Risk evaluator in [`E2_3_SHADOW_POLICY_EVALUATION.md`](E2_3_SHADOW_POLICY_EVALUATION.md). It verifies every response hash, preserves the production Standard arm, applies the registered RR `1.25` High Risk candidate, and aggregates at most one candidate per tier per day. It may not rerun model inference, inspect 2024/2025, or promote High Risk to production.
