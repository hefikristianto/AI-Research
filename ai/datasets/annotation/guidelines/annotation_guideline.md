# AI-TDSS Annotation Guideline

Version : v1.0
Sprint  : Sprint 3 - Annotation System
Status  : Draft

---

# Objective

Dokumen ini menjelaskan aturan anotasi dataset chart image AI-TDSS.

Annotation guideline digunakan untuk menjaga konsistensi labeling sebelum dataset digunakan untuk training YOLO.

---

# General Rules

1. Setiap bounding box harus mengikuti area visual objek seakurat mungkin.
2. Jangan memberi label pada area yang ambigu.
3. Jika sebuah zona terlalu kecil dan tidak terlihat jelas, abaikan.
4. Jika dua zona overlap kuat, prioritaskan zona yang lebih jelas secara struktur.
5. Label harus konsisten antar pair, timeframe, dan tahun.
6. Label tidak boleh dibuat berdasarkan hasil trade masa depan.
7. Label hanya dibuat berdasarkan struktur chart yang terlihat pada gambar.

---

# Labeling Rules

## 1. Order Block

Order Block adalah area candle terakhir sebelum pergerakan impulsif yang menyebabkan BOS atau CHOCH.

Label digunakan jika:

- Ada candle base sebelum impulsive move.
- Pergerakan setelah area tersebut cukup jelas.
- Area berkaitan dengan struktur market.

Jangan label jika:

- Candle tidak menghasilkan pergerakan signifikan.
- Area terlalu ambigu.
- Tidak ada struktur pendukung.

---

## 2. Fair Value Gap

Fair Value Gap adalah area imbalance antara tiga candle.

Label digunakan jika:

- Ada gap visual antara candle pertama dan candle ketiga.
- Harga bergerak impulsif.
- Area gap terlihat jelas.

Jangan label jika:

- Gap terlalu kecil.
- Sudah tertutup penuh.
- Tidak terlihat secara visual.

---

## 3. Liquidity

Liquidity adalah area high/low yang berpotensi menjadi target harga.

Label digunakan untuk:

- Swing high
- Swing low
- Equal high
- Equal low
- Area stop hunt potensial

---

## 4. Supply

Supply adalah area potensial tekanan jual.

Label digunakan jika:

- Harga turun kuat dari area tersebut.
- Area berada di sekitar swing high atau rejection zone.
- Ada candle bearish impulsive.

---

## 5. Demand

Demand adalah area potensial tekanan beli.

Label digunakan jika:

- Harga naik kuat dari area tersebut.
- Area berada di sekitar swing low atau rejection zone.
- Ada candle bullish impulsive.

---

## 6. BOS

Break of Structure digunakan saat harga menembus struktur high/low sebelumnya searah trend.

---

## 7. CHOCH

Change of Character digunakan saat harga menunjukkan perubahan karakter dari bullish ke bearish atau sebaliknya.

---

## 8. Equal High

Equal High digunakan jika terdapat dua atau lebih high yang relatif sejajar.

---

## 9. Equal Low

Equal Low digunakan jika terdapat dua atau lebih low yang relatif sejajar.

---

## 10. Mitigation

Mitigation digunakan untuk zona yang sudah disentuh kembali oleh harga.

---

# Annotation Output Format

Format label mengikuti YOLO:

class_id x_center y_center width height

Seluruh nilai koordinat dinormalisasi antara 0 sampai 1.

---

# Dataset Notes

Dataset image berasal dari generated chart image berbasis raw OHLCV MetaTrader 5.

Chart image tidak menampilkan harga dan waktu secara eksplisit agar model fokus pada struktur visual chart.
