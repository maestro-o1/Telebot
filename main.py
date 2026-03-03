import os
import tempfile
import subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = "8763594610:AAE2UV2zYNUFk3HKEEKaWOZYo_XRsvvACOQ"
OWNER_ID = 1700341163

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Sizga ruxsat yo‘q.")
        return
    await update.message.reply_text(
        "🎬 YouTube havolasini yuboring.\nMen sizga SRT qilib beraman."
    )

# YouTube link qabul qilish
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Sizga ruxsat yo‘q.")
        return

    url = update.message.text.strip()

    if "youtube.com" not in url and "youtu.be" not in url:
        await update.message.reply_text("❌ Faqat YouTube havola yuboring.")
        return

    await update.message.reply_text("🔍 Subtitrlar tekshirilmoqda...")

    try:
        # Subtitrlar ro'yxatini olish
        result = subprocess.run(
            ["yt-dlp", "--skip-download", "--write-sub", "--list-subs", url],
            capture_output=True, text=True
        )

        output = result.stdout
        lines = output.splitlines()
        manual_subs = []

        # Manual (qo'lda) subtitrlarni aniqlash
        for line in lines:
            if "vtt" in line and "auto" not in line.lower():
                lang = line.strip().split()[0]
                manual_subs.append(lang)

        if not manual_subs:
            await update.message.reply_text(
                "❌ Bu videoda qo‘lda kiritilgan subtitrlar yo‘q.\nBoshqa drama toping."
            )
            return

        keyboard = [[InlineKeyboardButton(lang, callback_data=f"{lang}|{url}")] for lang in manual_subs]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text("🌍 Qaysi til kerak?", reply_markup=reply_markup)

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik yuz berdi: {e}")


# Til bosilganda SRT yuborish
async def download_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang, url = query.data.split("|")
    await query.edit_message_text("⬇️ Yuklab olinmoqda...")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run([
                "yt-dlp",
                "--skip-download",
                "--write-sub",
                "--sub-lang", lang,
                "--convert-subs", "srt",
                "-o", f"{tmpdir}/video.%(ext)s",
                url
            ], check=True)

            srt_files = [f for f in os.listdir(tmpdir) if f.endswith(".srt")]
            if not srt_files:
                await query.message.reply_text("❌ SRT topilmadi.")
                return

            for file in srt_files:
                path = os.path.join(tmpdir, file)
                await query.message.reply_document(document=open(path, "rb"))

    except Exception as e:
        await query.message.reply_text(f"❌ Yuklashda xatolik: {e}")


# Bot ishga tushishi
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CallbackQueryHandler(download_sub))
app.run_polling()
