# Scoring v7.1 Summary

## Method

Scoring v7.1 uses scoring v6.1 as the base and applies bounded risk and reward adjustments.

## Rules

- Missing RR target: neutral
- RR below 1.0: -0.05
- RR 1.0 to 1.5: -0.03
- RR 1.5 to 2.0: +0.01
- RR 2.0 to 3.0: +0.03
- RR at least 3.0: +0.04
- Invalidated zone: -0.10
- Far entry: -0.01
- Very far entry: -0.02

## Results

- Total setups: 24
- Average scoring v6.1: 0.7489
- Average scoring v7.1: 0.7210
- Valid RR targets: 4
- Invalidated zones: 4

| Decision | Count |
|---|---:|
| ACCEPT | 10 |
| REVIEW | 9 |
| WATCHLIST | 5 |
| REJECT | 0 |