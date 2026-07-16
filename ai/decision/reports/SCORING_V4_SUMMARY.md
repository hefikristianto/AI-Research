# Scoring v4 Summary

## Configuration

- Pairing source: ai\benchmarks\reports\yolo11s_pairing_v3\yolo11s_ob_fvg_pairs_v3.csv
- CNN source: ai\classification\reports\ensemble\yolo_pairing_ensemble_predictions.csv
- Base scoring v3 weight: 0.80
- CNN context weight: 0.20

## Results

- Total pairs: 24
- Average base score v3: 0.7706
- Average final score v4: 0.7089
- CNN matched samples: 24
- CNN missing samples: 0
- Direction conflicts: 5

## Decisions

| Decision | Count |
|---|---:|
| ACCEPT | 7 |
| REVIEW | 14 |
| WATCHLIST | 3 |
| REJECT | 0 |