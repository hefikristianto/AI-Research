# E2.3 Daily Snapshot Manifest

- **Stage:** deterministic manifest construction
- **Primary pair:** GBPUSD
- **Permitted years:** 2020–2024
- **Final temporal test:** 2025 remains locked
- **Inference:** none
- **Training:** none
- **Production behavior:** unchanged

## Purpose

This stage builds the complete event population for the E2.3 standard-versus-high-risk shadow experiment. It does not render chart images, call the FastAPI endpoint, classify a market regime, run YOLO, or alter any decision threshold.

The earlier 165-image audits are sparse, non-overlapping research windows. They are not a daily population. The E2.3 manifest instead represents every observed GBPUSD trading day at two preregistered analysis targets and preserves unavailable or invalid events in the denominator.

The machine-readable contract is [`config/experiments/e2_3_daily_manifest.json`](../../config/experiments/e2_3_daily_manifest.json). The builder is [`ai/scripts/build_e2_3_daily_manifest.py`](../../ai/scripts/build_e2_3_daily_manifest.py).

## Locked Event Definition

| Dimension | Locked value |
|---|---|
| Pair | GBPUSD |
| Trading calendar | Weekday dates observed in the raw M5 source |
| Daily slots | `09:00 UTC` London and `14:00 UTC` London–New York overlap |
| Timeframes per event | M5, M15, H1, H4 |
| Chart window | 100 candles |
| Context window | 300 candles |
| Mapping | E2.2 `PLOT_AWARE` with `FULL_IMAGE` uncertainty fallback |
| Unit of evaluation | One slot event; results later aggregate to one trading day |
| Candidate cap | At most one standard and one high-risk candidate per day |

Each slot produces one event containing four timeframe rows. An event is `READY` only when all four rows are ready, have sufficient context, and pass the anti-lookahead check.

## Timestamp and Anti-Lookahead Contract

The raw MT5 timestamp is treated as the **bar-open timestamp**. At target time $T$, a candle with duration $\Delta$ is eligible only when:

$$
\text{bar\_open} + \Delta \leq T
$$

For example, at the `09:00 UTC` target:

| Timeframe | Last normally eligible bar open | Bar close | Included? |
|---|---:|---:|---|
| M5 | 08:55 | 09:00 | Yes |
| M15 | 08:45 | 09:00 | Yes |
| H1 | 08:00 | 09:00 | Yes |
| H4 | 04:00 | 08:00 | Yes |
| Any bar opening at 09:00 | 09:00 | After 09:00 | No |

The manifest therefore stores two distinct concepts:

- `chart_end_open_datetime` / `ohlcv_cutoff_datetime`: last included raw bar-open timestamp, which is the timestamp accepted by the current OHLCV endpoint;
- `analysis_target_utc_datetime`: the time at which the decision is conceptually evaluated and from which the session must be resolved.

This distinction prevents look-ahead and avoids incorrectly classifying an H4 London analysis as the session of its older bar-open timestamp. The subsequent E2.3 runner must add an explicit analysis-target/session override to the endpoint; it must not substitute a future H4 candle.

## Timezone Assumption

The current raw-source contract provisionally treats Valetax MT5 timestamps as UTC with `market_utc_offset_hours=0`. The assumption and its provisional status are written to every run. If broker-server timezone evidence later contradicts it, create a new contract version and rebuild development manifests. Do not silently reinterpret an existing manifest.

Daylight-saving behavior is intentionally represented by fixed UTC experiment slots for this first policy experiment. This creates reproducible cross-year sampling. A later product scheduler may use timezone-aware session windows, but it cannot rewrite the population used by this experiment.

## Source and Lineage

The builder reads local files with this layout:

```text
ai/datasets/raw/ohlcv/GBPUSD/{TIMEFRAME}/{YEAR}/
  GBPUSD_{TIMEFRAME}_{YEAR}_RAW.csv
```

To supply the first 300-candle context at a year boundary, the builder also reads the preceding year when available. Raw files remain local and ignored by Git. The manifest records raw-root-relative source paths and SHA256 digests, while `run_config.json` records the raw root, config hashes, Git commit, and dirty-tree state.

Duplicate raw timestamps are rejected. Exact duplicate chart windows across slot events are retained but marked `DUPLICATE_WINDOW`; the later event is not ready and cannot inflate coverage.

## Output Contract

```text
local_artifacts/experiments/{RUN_ID}/input/
  daily_snapshot_manifest.csv
  daily_manifest_summary.json
  run_config.json
```

The planned image path is recorded per row, but this stage does not create the PNG. The next implementation slice will render each ready canonical snapshot from the exact manifest window.

Row status values:

| Status | Meaning |
|---|---|
| `READY` | Closed candle, freshness, context, and lineage checks passed |
| `NO_CLOSED_CANDLE` | No candle had closed by the target |
| `STALE_SOURCE` | Latest closed candle exceeded the timeframe freshness allowance |
| `INSUFFICIENT_CONTEXT` | Fewer than 300 historical candles were available |
| `MISSING_SOURCE_YEAR` | The target-year source file for that timeframe was absent |
| `DUPLICATE_WINDOW` | An earlier event already owns the same exact chart window |

`event_ready=1` is allowed only when exactly one row for every required timeframe is `READY` and all four anti-lookahead checks equal `1`.

## Local Run

From the project root with the backend virtual environment active:

```powershell
$RUN_ID = "20260721_E2_3_daily_manifest_dev"
$E23 = ".\local_artifacts\experiments\$RUN_ID\input"

python ai\scripts\build_e2_3_daily_manifest.py `
  --year 2020 `
  --year 2021 `
  --year 2022 `
  --year 2023 `
  --year 2024 `
  --output-dir $E23
```

This command reads and hashes local CSV files, so runtime depends on disk speed and raw-file size. It performs no model inference and uses no GPU.

The builder intentionally rejects `--year 2025`. That year can be unlocked only after the standard/high-risk policy is selected on 2020–2023, frozen, and passes the 2024 holdout gate.

## Review Pack

Inspect the compact summary first:

```powershell
Get-Content "$E23\daily_manifest_summary.json" -Raw
Get-Content "$E23\run_config.json" -Raw
```

Package all three manifest artifacts for review:

```powershell
$ZIP = ".\local_artifacts\experiments\${RUN_ID}_manifest_review.zip"
Compress-Archive -Path "$E23\*" -DestinationPath $ZIP -Force
Get-Item $ZIP | Select-Object FullName, Length
```

The review checks:

- requested years are exactly 2020–2024;
- `training_performed=false` and `inference_performed=false`;
- source/config/mapping hashes are populated;
- `anti_lookahead_failures=0`;
- ready-event and failure counts are explained by status;
- duplicate windows do not remain `READY`;
- session overrides are explicit rather than resolved from an older H4 bar;
- no 2025 source appears in the target population.

## Interpretation Boundaries

- Ready-event rate is dataset availability, not detection accuracy.
- Two analysis slots do not imply two trades per day.
- A daily analysis target does not authorize forced daily entry.
- Manifest generation provides no evidence that a high-risk tier is accurate or profitable.
- No threshold may be selected from 2024 holdout outcomes or 2025 final outcomes.
- Raw predictions and user uploads remain ineligible as automatic ground truth.

## Next Slice

After the manifest passes review:

1. render canonical images from the exact 100-candle windows;
2. add the explicit analysis-target/session override needed by H4 and other stale endpoints;
3. run the existing inference once per manifest event with E2.2 plot-aware mapping;
4. derive unchanged-standard and candidate-high-risk shadow decisions from the same inference response;
5. select high-risk policy bands only on 2020–2023, then freeze before 2024.
