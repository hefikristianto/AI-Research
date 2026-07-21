# E2.3 Reviewed Manifest and Snapshot Rendering

- **Manifest decision:** validated for rendering
- **Reviewed population:** GBPUSD 2020–2024
- **Ready snapshots:** 10,230 of 10,408 rows
- **Non-ready snapshots:** 178 retained in the denominator and not rendered
- **Inference:** none
- **Training:** none
- **Final 2025:** remains locked

## Reviewed Manifest Result

The E2.3 daily manifest review passed all lineage and anti-lookahead checks. The machine-readable result is [`config/experiments/e2_3_daily_manifest_result.json`](../../config/experiments/e2_3_daily_manifest_result.json).

| Check | Result |
|---|---:|
| Manifest rows | 10,408 |
| Slot events | 2,602 |
| Trading days | 1,301 |
| Ready rows | 10,230 |
| Ready events | 2,491 (95.7341%) |
| Insufficient context | 134 |
| Stale source | 44 |
| Anti-lookahead failures | 0 |
| Duplicate windows | 0 |
| Source files with SHA256 lineage | 20 |

The reviewed manifest digest is `1a66cd589a8df5df39fef2ba86be8a0df6e73ffe8e6668fad034fdf0b3dd0519`. The review archive SHA256 is `3bed525f2ab60e8822c8e423f7d0daf2bf20e3a02d99a3106e74830b724fccf9`.

`INSUFFICIENT_CONTEXT` rows occur at the beginning of 2020 because no 2019 source was registered. `STALE_SOURCE` rows occur around partial holiday/year-end data. These rows are not silently dropped from the manifest, but they are ineligible for image rendering and later inference.

## Renderer Contract

[`ai/scripts/render_e2_3_daily_snapshots.py`](../../ai/scripts/render_e2_3_daily_snapshots.py) reads the exact reviewed CSV window and:

- rejects a changed manifest digest or an unreviewed manifest;
- verifies every required raw-source SHA256 before rendering;
- renders only rows whose manifest status is `READY`;
- requires the exact 100-candle start/end window from the manifest;
- writes deterministic `691 × 482` white-background candlestick PNGs using the canonical Charles-compatible green/red palette;
- writes images atomically and verifies deterministic SHA256 on resume;
- checkpoints a cumulative render audit and can continue after interruption;
- performs no CNN/YOLO inference and no model training.

The renderer output root is the experiment run root, not the Git repository:

```text
local_artifacts/experiments/{RUN_ID}/
  input/
    daily_snapshot_manifest.csv
    daily_manifest_summary.json
    run_config.json
  images/GBPUSD/{TIMEFRAME}/{YEAR}/
    *.png
  render/
    daily_snapshot_render_rows.csv
    daily_snapshot_render_summary.json
    run_config.json
```

## Local Smoke Run

From the project root with the backend virtual environment active:

```powershell
$RUN_ID = "20260721_E2_3_daily_manifest_dev"
$E23 = ".\local_artifacts\experiments\$RUN_ID"

python ai\scripts\render_e2_3_daily_snapshots.py `
  --manifest "$E23\input\daily_snapshot_manifest.csv" `
  --manifest-summary "$E23\input\daily_manifest_summary.json" `
  --manifest-run-config "$E23\input\run_config.json" `
  --output-dir $E23 `
  --limit 8 `
  --fail-fast
```

Inspect the smoke artifacts:

```powershell
Get-Content "$E23\render\daily_snapshot_render_summary.json" -Raw
Get-ChildItem "$E23\images" -Recurse -Filter "*.png" |
  Select-Object -First 8 FullName, Length
```

## Full Resumable Run

Continue from the same smoke output:

```powershell
python ai\scripts\render_e2_3_daily_snapshots.py `
  --manifest "$E23\input\daily_snapshot_manifest.csv" `
  --manifest-summary "$E23\input\daily_manifest_summary.json" `
  --manifest-run-config "$E23\input\run_config.json" `
  --output-dir $E23 `
  --resume `
  --fail-fast
```

The script reuses verified smoke PNGs. Runtime depends on disk speed because all relevant source hashes are checked and 10,230 PNGs are produced. If the terminal or machine stops, run the same command with `--resume`; do not delete the output directory.

A complete run must report:

- `manifest_ready_rows = 10230`;
- `manifest_non_ready_rows = 178`;
- `complete_for_reviewed_manifest = true`;
- no `FAILED` render row;
- every PNG width/height equals `691/482`;
- `training_performed=false` and `inference_performed=false`.

## Analysis-Target Clock

The full-analysis endpoint now accepts optional `analysis_target_datetime`. It is an experiment clock in the same source/market timezone as `chart_datetime`. It changes only session evaluation; OHLCV loading, HTF volatility, and the canonical cutoff continue to use `chart_datetime`.

For example, an H4 candle opening at `04:00` closes at `08:00` and may be evaluated at the London target `09:00`:

```text
chart_datetime=2023-01-02T04:00:00
analysis_target_datetime=2023-01-02T09:00:00
timeframe=H4
```

The endpoint rejects a target before the candle close or more than one timeframe beyond the close. Requests that omit the parameter preserve the existing upload behavior. E2.3 must pass `analysis_target_market_datetime` from the manifest; it must not pass the `Z`-suffixed UTC field when the OHLCV clock is timezone-naive.

## Boundaries

- Successful rendering is dataset preparation, not evidence of detection accuracy or profitability.
- The renderer cannot select high-risk thresholds or unlock 2025.
- The public upload frontend remains unchanged and does not send the experiment-only clock.
- The next slice is a resumable inference runner that consumes these images and passes each manifest analysis target, followed by the standard/high-risk shadow policy on 2020–2023.
