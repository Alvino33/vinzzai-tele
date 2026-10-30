import asyncio
import logging
import os
import tempfile
from pathlib import Path

import fitz
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from ai import answer_from_materials, extract_image_text
from knowledge import add_material, clear_materials, list_materials, retrieve

load_dotenv()
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("vinai")


def _user_id(update: Update) -> int:
    return update.effective_user.id


async def _send_long(update: Update, text: str) -> None:
    message = update.effective_message
    if not message:
        return
    text = text.strip() or "Tidak ada teks yang bisa ditampilkan."
    for start in range(0, len(text), 4000):
        await message.reply_text(text[start:start + 4000])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Halo! Gue VinAI, asisten belajar dari materi yang lo kirim.\n\n"
        "Kirim foto atau PDF untuk menyimpan materi.\n"
        "Perintah:\n"
        "/tambah <teks> — simpan materi teks\n"
        "/materi — lihat daftar materi\n"
        "/hapus_materi — hapus semua materi akun lo\n"
        "/help — bantuan\n\n"
        "Setelah materi tersimpan, langsung tanyakan soal lo."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)


async def add_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args).strip()
    if not text:
        await update.effective_message.reply_text(
            "Format: /tambah isi materi lo\nContoh: /tambah Fotosintesis adalah proses..."
        )
        return
    count = add_material(_user_id(update), "Materi teks", text)
    await update.effective_message.reply_text(
        f"Materi teks tersimpan. Gue simpan {count} bagian."
    )


async def show_materials(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    titles = list_materials(_user_id(update))
    if not titles:
        await update.effective_message.reply_text("Belum ada materi. Kirim foto/PDF atau pakai /tambah.")
        return
    listing = "\n".join(f"• {title}" for title in titles)
    await update.effective_message.reply_text(f"Materi tersimpan ({len(titles)}):\n{listing}")


async def delete_materials(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    removed = clear_materials(_user_id(update))
    await update.effective_message.reply_text(
        f"Selesai. {removed} bagian materi milik akun lo dihapus."
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    await message.reply_text("Gue lagi membaca teks di foto...")
    try:
        photo = message.photo[-1]
        telegram_file = await context.bot.get_file(photo.file_id)
        image_bytes = bytes(await telegram_file.download_as_bytearray())
        text = await asyncio.to_thread(extract_image_text, image_bytes, "image/jpeg")
        if not text:
            await message.reply_text("Teksnya belum berhasil terbaca. Coba kirim foto yang lebih jelas.")
            return
        count = add_material(_user_id(update), "Foto materi", text)
        preview = text[:700]
        await message.reply_text(
            f"Foto berhasil dibaca dan disimpan ({count} bagian).\n\n"
            f"Cuplikan:\n{preview}\n\nSekarang lo bisa tanya isi materinya."
        )
    except Exception:
        log.exception("Photo processing failed")
        await message.reply_text("Gagal memproses foto. Cek API key Gemini atau coba lagi nanti.")


def _extract_pdf(path: str) -> tuple[str, int, list[tuple[int, bytes]]]:
    doc = fitz.open(path)
    sections = []
    ocr_pages = []
    try:
        for index, page in enumerate(doc):
            page_text = page.get_text("text").strip()
            if page_text:
                sections.append(f"[Halaman {index + 1}]\n{page_text}")
            elif index < 15:
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                ocr_pages.append((index + 1, pix.tobytes("png")))
        return "\n\n".join(sections), len(doc), ocr_pages
    finally:
        doc.close()


async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    document = message.document
    if document.file_size and document.file_size > 20 * 1024 * 1024:
        await message.reply_text("PDF terlalu besar. Batas ukuran bot ini 20 MB.")
        return
    await message.reply_text("Gue lagi membaca PDF. Tunggu sebentar...")
    temp_path = None
    try:
        telegram_file = await context.bot.get_file(document.file_id)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp:
            temp_path = temp.name
        await telegram_file.download_to_drive(custom_path=temp_path)
        extracted = await asyncio.to_thread(_extract_pdf, temp_path)
        text, page_count, ocr_pages = extracted
        if ocr_pages:
            await message.reply_text(f"Ada {len(ocr_pages)} halaman scan yang perlu dibaca dengan OCR...")
            for page_number, image_bytes in ocr_pages:
                try:
                    page_text = await asyncio.to_thread(
                        extract_image_text, image_bytes, "image/png"
                    )
                    if page_text:
                        text += f"\n\n[Hasil OCR halaman {page_number}]\n{page_text}"
                except Exception:
                    log.exception("PDF page OCR failed: %s", page_number)
        if not text.strip():
            await message.reply_text("Belum ada teks yang berhasil dibaca dari PDF ini.")
            return
        title = (document.file_name or "Dokumen PDF")[:180]
        count = add_material(_user_id(update), title, text)
        await message.reply_text(
            f"PDF berhasil diproses: {page_count} halaman, tersimpan dalam {count} bagian. "
            "Sekarang lo bisa tanya isi materinya."
        )
    except Exception:
        log.exception("PDF processing failed")
        await message.reply_text("Gagal memproses PDF. Pastikan file tidak rusak dan coba lagi.")
    finally:
        if temp_path and Path(temp_path).exists():
            Path(temp_path).unlink(missing_ok=True)


async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = (update.effective_message.text or "").strip()
    if not question:
        return
    await update.effective_message.chat.send_action("typing")
    try:
        sources = retrieve(_user_id(update), question)
        answer = await asyncio.to_thread(answer_from_materials, question, sources)
        await _send_long(update, answer)
    except Exception:
        log.exception("Answer generation failed")
        await update.effective_message.reply_text(
            "Gue gagal membuat jawaban. Cek GEMINI_API_KEY, kuota API, dan nama model."
        )


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("Unhandled bot error", exc_info=context.error)


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN belum diatur.")
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY belum diatur.")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("tambah", add_text))
    app.add_handler(CommandHandler("materi", show_materials))
    app.add_handler(CommandHandler("hapus_materi", delete_materials))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question))
    app.add_error_handler(on_error)
    log.info("VinAI Telegram is starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
