# VinAI Telegram

Bot Telegram untuk belajar dari materi sekolah yang lo kirim. VinAI menyimpan materi per akun Telegram dan mengambil bagian yang relevan sebelum menjawab.

## Fitur MVP
- Terima materi teks melalui `/tambah`.
- Terima foto dan baca teksnya dengan Gemini OCR.
- Terima PDF, ekstrak teks, dan OCR halaman scan (maksimal 15 halaman scan per dokumen).
- Simpan materi per pengguna ke file JSONL.
- Jawab pertanyaan berdasarkan potongan materi yang paling relevan.
- Daftar dan hapus materi milik akun sendiri.

## Menjalankan lokal

Butuh Python 3.10+.

1. Install dependensi:

   ```bash
   pip install -r requirements.txt
   ```

2. Salin `.env.example` menjadi `.env`, lalu isi:
   - `TELEGRAM_BOT_TOKEN`: token bot dari BotFather.
   - `GEMINI_API_KEY`: API key Gemini.
   - `GEMINI_MODEL`: default `gemini-3.8-flash`.
   - `DATA_DIR`: folder penyimpanan, default `data`.

3. Jalankan:

   ```bash
   python bot.py
   ```

## Perintah bot
- `/start` atau `/help` — bantuan.
- `/tambah <teks>` — simpan materi teks.
- `/materi` — daftar materi tersimpan.
- `/hapus_materi` — hapus seluruh materi milik akun Telegram lo.
- Kirim foto — OCR dan simpan.
- Kirim PDF — ekstrak teks dan simpan.
- Kirim pertanyaan biasa — tanya berdasarkan materi tersimpan.

## Deploy cloud

Jalankan sebagai worker/service Python dengan start command `python bot.py`. Atur `TELEGRAM_BOT_TOKEN` dan `GEMINI_API_KEY` sebagai environment variables di dashboard hosting, bukan di source code.

**Penting untuk data:** folder `data` harus diarahkan ke persistent disk/volume hosting. Kalau hosting memakai filesystem sementara, materi bisa hilang saat service dibuat ulang atau restart. Pastikan layanan mendukung proses worker yang terus aktif; layanan gratis bisa punya batas tidur, kuota, atau jam aktif.

## Catatan
- Gemini API punya kuota dan ketentuan penggunaan sendiri; bot ini tidak menjanjikan API gratis tanpa batas.
- PDF yang berisi teks digital diekstrak langsung. Untuk halaman scan, OCR dicoba pada maksimal 15 halaman tanpa teks.
- Penyimpanan saat ini berbasis file JSONL, cocok untuk MVP satu instance. Untuk penggunaan ramai atau beberapa instance, pindahkan ke database.
- Jangan pernah commit file `.env` atau mengirim token/API key ke chat.
