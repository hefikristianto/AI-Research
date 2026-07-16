# Final CNN Ensemble Result

## Method

Weighted soft voting based on validation Macro F1.

## Ensemble Weights

| Model | Weight |
|---|---:|
| vgg11 | 0.2499 |
| vgg16 | 0.2510 |
| googlenet | 0.2483 |
| resnet18 | 0.2508 |

## Test 2025 Result

| Metric | Value |
|---|---:|
| Accuracy | 0.8607 |
| Balanced Accuracy | 0.8746 |
| Macro Precision | 0.8195 |
| Macro Recall | 0.8746 |
| Macro F1 | 0.8427 |
| Average Confidence | 0.8059 |
| Average Entropy | 0.4794 |

## Per-Class Metrics

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| bearish | 0.7177 | 0.8885 | 0.7941 | 601 |
| bullish | 0.8129 | 0.8935 | 0.8513 | 958 |
| sideways | 0.9279 | 0.8419 | 0.8828 | 2568 |

## Confusion Matrix

Class order: bearish, bullish, sideways

```text
[[ 534    1   66]
 [   0  856  102]
 [ 210  196 2162]]
```

## Final Decision

The weighted four-model CNN ensemble is used as the primary market-regime classifier.