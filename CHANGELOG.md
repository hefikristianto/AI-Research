# Changelog - AI-TDSS

## Unreleased - 18-07-2026

### Added

- Added a machine-readable canonical project contract.
- Added project-contract validation and unit tests.
- Added research synthesis for academic writing and revision.
- Added a local-only experiment plan with explicit artifact paths.
- Added SDD chapters for overview, architecture, requirements, AI roles, labeling, journal, and incremental learning.
- Added the four-sheet Excel journal contract.

### Changed

- Locked GBPUSD as the primary research/product pair.
- Locked production YOLO scope to Order Block and Fair Value Gap.
- Assigned liquidity, BOS/CHOCH, EQH/EQL, and candle patterns to deterministic OHLCV analysis.
- Defined CNN incremental learning as an offline batch champion–challenger process.
- Required verified outcomes and prohibited raw predictions as automatic ground truth.
- Standardized large local artifacts under ignored `local_artifacts/`.

### Notes

- No model retraining is performed by this documentation/contract milestone.
- GitHub CI remains limited to lightweight tests, syntax checks, and contract validation.

---

## v0.1.0 - 30-06-2026

### Added

- Initial project folder structure
- Supabase selected as database, auth, and storage provider
- MASTER_SDD.md created
- DECISION_LOG.md created
- AI-TDSS defined as Decision Support System
- Initial research scope:
  - XAUUSD
  - GBPUSD
  - TradingView
  - Desktop and Mobile
  - H4, H1, M15
  - Intraday trading style

---

## v0.3.0 - 30-06-2026

### Changed

- MASTER_SDD changed into documentation index
- SDD split into independent chapter files
- One chapter equals one markdown file
- Documentation workflow changed to modular documentation

---

## v0.4.0 - 30-06-2026

### Added

- Architecture Decision Document (ADD)
- Technical Development Document (TDD)

### Changed

- Documentation now consists of:
  - SDD
  - ADD
  - TDD

---

## v0.5.0 - 30-06-2026

### Added

- Sprint backlog created
- Core roadmap locked
- Project moved from planning phase to implementation preparation phase

---

## v0.6.0 - 30-06-2026

### Added

- Next.js frontend app initialized
- Tailwind CSS configured
- Frontend folder structure prepared:
  - layout
  - common
  - dashboard
  - journal
  - upload
  - watchlist
  - ui
  - hooks
  - services
  - types
  - utils
  - constants
  - store

---

## v0.7.0 - 30-06-2026

### Changed

- Zone Scoring repositioned as internal variable
- Trade Decision Engine defined as main decision module
- Trading recommendation flow updated:
  - YOLO Detection
  - Rule-Based Market Structure
  - Zone Filtering
  - Trade Decision Engine
  - Watchlist or Journal

---

## v0.8.1 - 30-06-2026

### Changed

- Chapter 9 rewritten using section-based workflow
- Section 9.1 to 9.3 added and locked
- Documentation workflow changed to smaller section batches

---

---

## 2026-07-04 - Sprint 2 Dataset Engineering

### Added

- Added yearly raw OHLCV dataset structure.
- Added dataset folder structure for XAUUSD and GBPUSD.
- Added timeframe structure for M5, M15, H1, and H4.
- Added yearly structure from 2020 to 2025.
- Added raw OHLCV metadata.
- Added chart image metadata.
- Added class mapping file.
- Added dataset versioning file.
- Added OHLCV validation script.
- Added chart image generation script.
- Added OHLCV validation report.
- Added chart image distribution report.
- Added generated chart image pipeline.

### Changed

- Updated dataset version status to raw_chart_generated.
- Updated dataset source to broker_mt5_valetax.
- Updated dataset strategy to support yearly incremental learning.
- Updated .gitignore to exclude raw CSV and generated PNG dataset files.

### Dataset Summary

- Total raw OHLCV files: 48
- Total generated chart images: 1980
- Pairs: XAUUSD, GBPUSD
- Timeframes: M5, M15, H1, H4
- Years: 2020, 2021, 2022, 2023, 2024, 2025

### Notes

Raw OHLCV CSV files and generated chart PNG files are excluded from GitHub to prevent repository size issues.
Only scripts, metadata, reports, and documentation are tracked.
