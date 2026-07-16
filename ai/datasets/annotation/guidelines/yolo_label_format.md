# YOLO Label Format - AI-TDSS

Setiap image memiliki file label dengan nama yang sama.

Example:

Image:
gbpusd_h1_2020_20200101_000000_0001.png

Label:
gbpusd_h1_2020_20200101_000000_0001.txt

Format isi label:

class_id x_center y_center width height

Semua nilai koordinat menggunakan format normalized value antara 0 sampai 1.

Example:

0 0.512300 0.438100 0.120000 0.080000
1 0.631200 0.522000 0.090000 0.045000

Meaning:

0 = order_block
1 = fair_value_gap

Rules:

- Satu baris untuk satu object.
- Satu image boleh memiliki banyak object.
- File label boleh kosong jika image tidak memiliki object valid.
- Jangan menggunakan nama class di file txt.
- Jangan menggunakan koordinat pixel mentah.
- Jangan menggunakan koma sebagai desimal.
