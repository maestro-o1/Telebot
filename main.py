import os
import tempfile
import subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = "8763594610:AAE2UV2zYNUFk3HKEEKaWOZYo_XRsvvACOQ"

# START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 YouTube havolasini yuboring.\nMen sizga SRT qilib beraman."
    )

# YOUTUBE LINK QABUL QILISH
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text

    if "youtube.com" not in url and "youtu.be" not in url:
        await update.message.reply_text("❌ Faqat YouTube havola yuboring.")
        return

    await update.message.reply_text("🔍 Subtitrlar tekshirilmoqda...")

    try:
        # Manual subtitle list olish (auto-generated emas)
        result = subprocess.run(
            ["yt-dlp", "--list-subs", "--skip-download", url],
            capture_output=True,
            text=True
        )

        output = result.stdout

        lines = output.splitlines()
        manual_subs = []

        for line in lines:
            if "vtt" in line and "auto" not in line.lower():
                lang = line.strip().split()[0]
                manual_subs.append(lang)

        if not manual_subs:
            await update.message.reply_text(
                "❌ Bu videoda qo‘lda kiritilgan subtitrlar yo‘q.\nBoshqa drama toping."
            )
            return

        keyboard = []
        for lang in manual_subs:
            keyboard.append(
                [InlineKeyboardButton(lang, callback_data=f"{lang}|{url}")]
            )

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "🌍 Qaysi til kerak?",
            reply_markup=reply_markup
        )

    except Exception as e:
        await update.message.reply_text("❌ Xatolik yuz berdi.")


# TIL BOSILGANDA
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
            ])

            for file in os.listdir(tmpdir):
                if file.endswith(".srt"):
                    path = os.path.join(tmpdir, file)
                    await query.message.reply_document(document=open(path, "rb"))
                    return

        await query.message.reply_text("❌ SRT topilmadi.")

    except Exception:
        await query.message.reply_text("❌ Yuklashda xatolik.")

# BOTNI ISHGA TUSHIRISH
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CallbackQueryHandler(download_sub))

app.run_polling()
