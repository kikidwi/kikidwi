# Cara Pasang README Profil Ini

## 1. Buat repo khusus
GitHub punya fitur "profile README" khusus: buat repo baru dengan nama
**persis sama dengan username kamu**, yaitu `kikidwi/kikidwi`, dan jadikan
**Public**. Centang "Add a README file" saat membuat (nanti akan ditimpa).

## 2. Upload semua file di folder ini
Upload/push semua isi folder `profile-readme/` ke repo `kikidwi/kikidwi`:
```
README.md
today.py
requirements.txt
.github/workflows/main.yml
templates/light_mode.svg
templates/dark_mode.svg
light_mode.svg      (hasil awal, sementara)
dark_mode.svg       (hasil awal, sementara)
```

Struktur akhirnya harus persis seperti itu di root repo (kecuali folder `templates/`
yang tetap sebagai subfolder).

## 3. Buat Personal Access Token (PAT)
1. Buka https://github.com/settings/tokens → **Generate new token (classic)**
2. Centang scope: `repo` dan `read:user`
3. Generate, lalu **copy token-nya** (hanya muncul sekali)

## 4. Simpan token sebagai Secret
1. Di repo `kikidwi/kikidwi` → **Settings → Secrets and variables → Actions**
2. **New repository secret**
3. Name: `ACCESS_TOKEN`, Value: (paste token dari langkah 3)

## 5. Jalankan workflow-nya
- Buka tab **Actions** di repo → pilih workflow **"Update profile stats"**
  → klik **Run workflow** untuk trigger manual pertama kali.
- Setelahnya, workflow otomatis jalan tiap 12 jam (bisa diubah di
  `.github/workflows/main.yml` bagian `cron`).

## 6. Cek hasilnya
Buka `https://github.com/kikidwi` — README profil kamu akan menampilkan kartu
statistik SVG yang otomatis update.

---

### Catatan
- Proses hitung **lines of code** meng-clone semua repo publik kamu satu per
  satu untuk menjumlah baris yang ditambah/dihapus. Kalau repo kamu banyak,
  proses ini bisa memakan waktu beberapa menit — itu normal.
- Kalau mau **skip** perhitungan lines of code (lebih cepat), tambahkan env
  `SKIP_LOC: "true"` di step "Generate stats SVGs" pada `main.yml`.
- Warna & layout kartu bisa diubah bebas di `templates/light_mode.svg` dan
  `templates/dark_mode.svg` — cari tag `<text>` dan `<rect>` untuk edit posisi/warna.
- Kalau username, nama, atau tanggal lahir berubah, update juga di
  `.github/workflows/main.yml` (env `USER_NAME`, `BIRTHDAY`) dan di teks statis
  dalam `templates/*.svg` (nama & bio ditulis manual, bukan placeholder).
