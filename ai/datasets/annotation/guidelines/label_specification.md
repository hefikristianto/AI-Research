# AI-TDSS Label Specification

Version : v1.0
Sprint  : Sprint 3 - Annotation System
Status  : Draft

---

## Class List

| ID | Class Name | Description |
|----|------------|-------------|
| 0 | order_block | Area candle terakhir sebelum pergerakan impulsif yang menyebabkan break structure |
| 1 | fair_value_gap | Area imbalance antara candle yang tidak tertutup sempurna |
| 2 | liquidity | Area kumpulan high/low yang berpotensi menjadi target likuiditas |
| 3 | supply | Area potensial tekanan jual |
| 4 | demand | Area potensial tekanan beli |
| 5 | bos | Break of Structure |
| 6 | choch | Change of Character |
| 7 | equal_high | High sejajar yang berpotensi menjadi buy-side liquidity |
| 8 | equal_low | Low sejajar yang berpotensi menjadi sell-side liquidity |
| 9 | mitigation | Area zona yang sudah disentuh kembali oleh harga |

---

## YOLO Class Mapping

0 order_block
1 fair_value_gap
2 liquidity
3 supply
4 demand
5 bos
6 choch
7 equal_high
8 equal_low
9 mitigation

---

## Notes

Label specification ini digunakan sebagai acuan awal untuk proses anotasi dataset chart image AI-TDSS.
