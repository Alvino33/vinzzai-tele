# VinAI Telegram

Bot Telegram untuk belajar dari materi sekolah yang lo kirim. Materi dipisahkan per pengguna dan per mata pelajaran.

## Fitur
- Terima materi teks melalui `/tambah`.
- Terima foto dan baca teksnya dengan Gemini OCR.
- Terima PDF, ekstrak teks, dan OCR halaman scan (maksimal 15 halaman scan per dokumen).
- Klasifikasi mapel otomatis untuk materi dan pertanyaan.
- Simpan materi pada folder per pengguna dan file per mapel.
- Jawab pertanyaan berdasarkan bagian materi yang paling relevan.
- Lihat daftar materi seluruh mapel atau satu mapel.
- Hapus seluruh materi milik akun sendiri.

## Struktur penyimpanan

```text
data/
└── users/
    └── TELEGRAM_USER_ID/
        ├── matematika.jsonl
        ├── ipas.jsonl
        ├── bahasa_indonesia.jsonl
        ├── bahasa_inggris.jsonl
        ├── pancasila.jsonl
        ├── agama.jsonl
        └── lainnya.jsonl
```

Kategori mapel dipilih otomatis berdasarkan nama file dan isi materi. Deteksi ini berbasis kata kunci, jadi sesekali kategori bisa kurang tepat. Pertanyaan akan mencari materi pada mapel yang terdeteksi; jika tidak ada materi pada kategori itu, pencarian diperluas ke semua mapel.

## Perintah bot
- `/start` atau `/help` — bantuan.
- `/tambah <teks>` — simpan materi teks.
- `/materi` — daftar materi per mapel.
- `/materi ipas` — daftar materi IPAS (nama mapel lain juga bisa).
- `/mapel` — daftar kategori.
- `/hapus_materi` — hapus seluruh materi milik akun Telegram lo.
- Kirim foto — OCR dan simpan otomatis.
- Kirim PDF — ekstrak teks dan simpan otomatis.
- Kirim pertanyaan biasa — tanya berdasarkan materi tersimpan.

## Menjalankan lokal

Butuh Python 3.10+.

1. Install dependensi:

   ```bash
   pip install -r requirements.txt
   ```

2. Salin `.env.example` menjadi `.env`, lalu isi:
   - `TELEGRAM_BOT_TOKEN`: token bot dari BotFather.
   - `GEMINI_API_KEY`: API key Gemini.
   - `GEMINI_MODEL`: model Gemini yang tersedia pada akun lo.
   - `DATA_DIR`: folder penyimpanan, default `data`.

3. Jalankan:

   ```bash
   python bot.py
   ```

## Deploy cloud

Jalankan sebagai worker/service Python dengan start command `python bot.py`. Atur `TELEGRAM_BOT_TOKEN` dan `GEMINI_API_KEY` sebagai environment variables atau secrets, bukan di source code.

**Penting:** folder `data` harus berada pada persistent disk/volume hosting. GitHub Actions memakai runner sementara, sehingga file materi yang disimpan di runner dapat hilang setelah job selesai. Untuk penggunaan rutin, siapkan database atau penyimpanan persisten eksternal.

## Catatan
- Kuota dan ketentuan Gemini API mengikuti akun Google AI Studio.
- PDF yang berisi teks digital diekstrak langsung. Untuk halaman scan, OCR dicoba pada maksimal 15 halaman tanpa teks.
- Penyimpanan JSONL ini cocok untuk MVP satu instance. Untuk penggunaan ramai atau beberapa instance, pindahkan ke database.
- Jangan pernah commit file `.env` atau membagikan token/API key.
