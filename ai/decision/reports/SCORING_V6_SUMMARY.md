# Scoring v6 Summary

## Method

Scoring v6 uses scoring v5.1 as the base score.

## Context Adjustments

- HTF alignment: maximum ±0.05
- Volatility context: maximum ±0.03
- Extreme-volatility penalty: -0.02
- HTF-conflict penalty: -0.02
- Session context: logged only, not scored

## Results

- Total setups: 24
- Average scoring v5.1: 0.7520
- Average scoring v6: 0.7678
- HTF aligned: 7
- HTF conflicts: 3
- Extreme volatility: 4

| Decision | Count |
|---|---:|
| ACCEPT | 12 |
| REVIEW | 10 |
| WATCHLIST | 2 |
| REJECT | 0 |