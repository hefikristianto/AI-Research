# AI-TDSS Bounding Box Guideline

Version : v2.0
Sprint  : Sprint 3 - Annotation System
Status  : Production Scope Locked

---

# Objective

Dokumen ini menjelaskan aturan pembuatan bounding box untuk setiap class pada dataset chart image AI-TDSS.

Bounding box guideline digunakan agar proses anotasi memiliki standar visual yang konsisten sebelum dataset digunakan untuk training YOLO.

Scope YOLO produksi hanya `order_block` dan `fair_value_gap`. Liquidity, BOS/CHOCH, EQH/EQL, candle pattern, dan mitigation dihitung dari OHLCV dan tidak diberi bounding box training YOLO.

---

# General Bounding Box Rules

1. Bounding box harus menutup area objek secara visual.
2. Jangan membuat bounding box terlalu besar sampai mencakup area yang tidak relevan.
3. Jangan membuat bounding box terlalu kecil sampai struktur utama objek terpotong.
4. Jika objek ambigu, jangan diberi label.
5. Jika dua objek overlap, gunakan label yang paling dominan secara struktur.
6. Jika satu area memiliki dua makna, prioritaskan class sesuai tujuan deteksi utama.
7. Label dibuat berdasarkan struktur yang terlihat pada gambar, bukan prediksi masa depan.

---

# 0 - Order Block

## Definition

Order Block adalah area candle terakhir sebelum pergerakan impulsif yang menyebabkan perubahan struktur market, seperti BOS atau CHOCH.

Order Block dapat berupa:

- Bullish Order Block
- Bearish Order Block

Namun pada class mapping awal, keduanya tetap menggunakan class:

0 order_block

---

## Bullish Order Block

Bullish Order Block adalah candle bearish terakhir sebelum harga bergerak naik secara impulsif.

Bounding box dibuat pada area candle tersebut.

Area box mencakup:

- High candle OB
- Low candle OB
- Body candle
- Wick candle jika wick masih relevan sebagai area reaksi

Label digunakan jika:

- Setelah candle tersebut muncul pergerakan bullish impulsif.
- Pergerakan menyebabkan break structure atau perubahan karakter.
- Area tersebut terlihat jelas sebagai origin dari pergerakan.

Jangan label jika:

- Candle hanya bagian dari sideways kecil.
- Tidak ada pergerakan impulsif setelahnya.
- Area terlalu kecil atau tidak jelas.
- Terlalu banyak candle base sehingga origin sulit ditentukan.

---

## Bearish Order Block

Bearish Order Block adalah candle bullish terakhir sebelum harga bergerak turun secara impulsif.

Bounding box dibuat pada area candle tersebut.

Area box mencakup:

- High candle OB
- Low candle OB
- Body candle
- Wick candle jika wick masih relevan sebagai area reaksi

Label digunakan jika:

- Setelah candle tersebut muncul pergerakan bearish impulsif.
- Pergerakan menyebabkan break structure atau perubahan karakter.
- Area tersebut terlihat jelas sebagai origin dari pergerakan.

Jangan label jika:

- Candle hanya bagian dari sideways kecil.
- Tidak ada pergerakan impulsif setelahnya.
- Area terlalu ambigu.
- Pergerakan setelahnya terlalu lemah.

---

## Order Block Box Placement

Bounding box untuk order_block harus:

- Mengikuti lebar candle OB atau candle base utama.
- Mengikuti tinggi area high sampai low OB.
- Tidak mencakup seluruh impulsive move.
- Tidak mencakup terlalu banyak candle lanjutan.
- Fokus pada area asal pergerakan.

---

# 1 - Fair Value Gap

## Definition

Fair Value Gap adalah area imbalance antara tiga candle ketika harga bergerak impulsif dan meninggalkan celah visual yang belum terisi sempurna.

Fair Value Gap dapat berupa:

- Bullish FVG
- Bearish FVG

Namun pada class mapping awal, keduanya tetap menggunakan class:

1 fair_value_gap

---

## Bullish Fair Value Gap

Bullish FVG terjadi jika terdapat gap antara high candle pertama dan low candle ketiga pada struktur tiga candle bullish impulsif.

Bounding box dibuat pada area kosong di antara:

- High candle pertama
- Low candle ketiga

Label digunakan jika:

- Gap terlihat jelas secara visual.
- Pergerakan candle tengah impulsif.
- Area imbalance belum tertutup penuh.
- FVG tidak terlalu kecil.

Jangan label jika:

- Gap terlalu kecil.
- Gap tidak terlihat secara visual.
- Harga langsung menutup seluruh gap.
- Struktur candle tidak impulsif.

---

## Bearish Fair Value Gap

Bearish FVG terjadi jika terdapat gap antara low candle pertama dan high candle ketiga pada struktur tiga candle bearish impulsif.

Bounding box dibuat pada area kosong di antara:

- Low candle pertama
- High candle ketiga

Label digunakan jika:

- Gap terlihat jelas secara visual.
- Pergerakan candle tengah impulsif.
- Area imbalance belum tertutup penuh.
- FVG tidak terlalu kecil.

Jangan label jika:

- Gap terlalu kecil.
- Gap tidak terlihat secara visual.
- Harga langsung menutup seluruh gap.
- Struktur candle tidak impulsif.

---

## Fair Value Gap Box Placement

Bounding box untuk fair_value_gap harus:

- Mencakup area imbalance saja.
- Tidak mencakup seluruh candle.
- Tidak mencakup candle impulsive secara penuh.
- Fokus pada ruang kosong antara candle pertama dan candle ketiga.
- Memanjang secara horizontal pada area gap yang terlihat.

---

# Ambiguous Cases

Jika terdapat area yang tampak seperti zona reaksi umum tetapi tidak memenuhi definisi Order Block, jangan memberi label. Dataset produksi tidak memiliki class supply atau demand.

Jika terdapat FVG yang overlap dengan OB:

- Tetap label keduanya jika keduanya terlihat jelas.
- Pastikan bounding box tidak dibuat identik.
- OB mengikuti candle origin.
- FVG mengikuti area imbalance.

---

# Quality Standard

Annotation dianggap valid jika:

- Class sesuai definisi.
- Bounding box menutup objek utama.
- Tidak terlalu banyak area kosong di dalam box.
- Tidak melewati area objek lain secara berlebihan.
- Bisa dipahami ulang oleh annotator lain.

Annotation dianggap invalid jika:

- Label dibuat berdasarkan tebakan.
- Bounding box terlalu besar.
- Bounding box terlalu kecil.
- Class tidak sesuai.
- Objek tidak terlihat jelas.
