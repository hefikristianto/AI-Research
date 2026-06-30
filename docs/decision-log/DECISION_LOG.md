# Decision Log - AI-TDSS

## Decision #001

| Item | Description |
|------|-------------|
| Date | 30-06-2026 |
| Decision | AI-TDSS dikembangkan sebagai Decision Support System, bukan Auto Trading System |
| Reason | Membatasi ruang lingkup penelitian, mengurangi risiko implementasi, memperjelas kontribusi sistem, dan memudahkan validasi hasil |
| Impact | Sistem hanya memberikan rekomendasi trading berupa entry, stop loss, take profit, status setup, dan alasan analisis. Sistem tidak melakukan eksekusi transaksi otomatis ke broker |

---

## Decision #003

| Item | Description |
|------|-------------|
| Date | 30-06-2026 |
| Decision | MASTER_SDD diubah menjadi dokumen induk yang menghubungkan seluruh chapter SDD |
| Reason | Mempermudah pengembangan dokumentasi, mengurangi konflik revisi, serta menjaga setiap chapter tetap fokus pada satu topik utama |
| Impact | Seluruh dokumentasi SDD menggunakan pendekatan modular dan setiap chapter disimpan pada file terpisah |

---

## Decision #004

| Item | Description |
|------|-------------|
| Date | 30-06-2026 |
| Decision | Dokumentasi dipisahkan menjadi tiga dokumen utama (SDD, ADD, dan TDD) |
| Reason | Memisahkan desain sistem, alasan arsitektur, dan implementasi teknis sehingga dokumentasi lebih mudah dipelihara dan digunakan selama penelitian |
| Impact | Seluruh keputusan arsitektur akan dicatat di ADD, sedangkan implementasi dicatat di TDD |

---

## Decision #005

| Item | Description |
|------|-------------|
| Date | 30-06-2026 |
| Decision | Core roadmap dikunci dan project masuk ke fase implementasi |
| Reason | Batas waktu 12 Juli membuat penambahan fitur baru harus dihentikan agar pengembangan tetap realistis |
| Impact | Fitur baru setelah tanggal ini masuk ke Future Development, bukan roadmap utama |

---

## Decision #006

| Item | Description |
|------|-------------|
| Date | 30-06-2026 |
| Decision | Istilah Zone Scoring tidak dijadikan inti sistem dan digantikan oleh Trade Decision Engine (TDE) |
| Reason | Zone Scoring hanya menilai kualitas zona, sedangkan sistem membutuhkan modul keputusan yang mempertimbangkan hasil YOLO, struktur pasar, liquidity, risk-reward, sesi market, news, watchlist state, dan histori performa |
| Impact | Seluruh output rekomendasi trading akan berasal dari Trade Decision Engine. Zone Strength Score tetap digunakan sebagai salah satu variabel internal, bukan sebagai modul utama |

---
