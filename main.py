import os
import logging
import tempfile
import sqlite3
import datetime
import pysrt
import aiohttp
import asyncio
import re
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, CallbackQueryHandler, ContextTypes
)
import yt_dlp

# ==================== SOZLAMALAR ====================
BOT_TOKEN = "8763594610:AAE2UV2zYNUFk3HKEEKaWOZYo_XRsvvACOQ"
DEEPSEEK_API_KEY = "sk-37d52e756c5b43ee9d7f7042844277cb"
ADMIN_ID = 1700341163  # Sizning Telegram IDingiz

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

ALLOWED_AUTO_LANGUAGES = ['en', 'uz', 'ru', 'zh']  # Avtomatik tarjima qo'llab-quvvatlanadigan tillar

WAITING_FOR_YOUTUBE = 1
WAITING_FOR_SRT = 2

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== MA'LUMOTLAR BAZASI ====================
def init_db():
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS permissions
                     (user_id INTEGER PRIMARY KEY,
                      username TEXT,
                      first_name TEXT,
                      last_name TEXT,
                      expires_at TEXT,
                      granted_by INTEGER,
                      granted_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS user_data
                     (user_id INTEGER PRIMARY KEY,
                      current_file TEXT,
                      video_title TEXT,
                      original_lang TEXT)''')
        conn.commit()
        conn.close()
        logger.info("✅ Baza yaratildi")
    except Exception as e:
        logger.error(f"Baza xatolik: {e}")

def add_permission(user_id: int, username: str, first_name: str, last_name: str, days: int) -> bool:
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        expires_at = datetime.datetime.now() + datetime.timedelta(days=days)
        c.execute('''INSERT OR REPLACE INTO permissions 
                     (user_id, username, first_name, last_name, expires_at, granted_by, granted_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (user_id, username, first_name, last_name, expires_at.isoformat(), ADMIN_ID, datetime.datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ruxsat berish xatolik: {e}")
        return False

def check_permission(user_id: int) -> tuple:
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute('SELECT expires_at FROM permissions WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        conn.close()
        if result:
            expires_at = datetime.datetime.fromisoformat(result[0])
            if expires_at > datetime.datetime.now():
                return True, expires_at
        return False, None
    except Exception as e:
        logger.error(f"Ruxsat tekshirish xatolik: {e}")
        return False, None

def save_user_file(user_id: int, file_path: str, video_title: str, original_lang: str = None) -> bool:
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO user_data 
                     (user_id, current_file, video_title, original_lang)
                     VALUES (?, ?, ?, ?)''',
                  (user_id, file_path, video_title, original_lang))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Fayl saqlash xatolik: {e}")
        return False

def get_user_file(user_id: int):
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute('SELECT current_file, video_title, original_lang FROM user_data WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        conn.close()
        if result:
            file_path = result[0]
            if file_path and os.path.exists(file_path):
                return result
            else:
                conn = sqlite3.connect('bot_data.db')
                c = conn.cursor()
                c.execute('DELETE FROM user_data WHERE user_id = ?', (user_id,))
                conn.commit()
                conn.close()
                return None, None, None
        else:
            return None, None, None
    except Exception as e:
        logger.error(f"Fayl olish xatolik: {e}")
        return None, None, None

# ==================== TIL NOMLARI ====================
def get_language_name(lang_code: str) -> str:
    languages = {'en': 'Ingliz', 'ru': 'Rus', 'uz': "O'zbek", 'zh': 'Xitoy'}
    return languages.get(lang_code, lang_code.upper())

# ==================== DEEPSEEK TARJIMA ====================
async def translate_with_deepseek(text: str, target_lang: str = "uzbek") -> str:
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": f"Professional tarjimonsiz. Matnni {target_lang} tiliga tarjima qil. Faqat matn."},
            {"role": "user", "content": text}
        ],
        "temperature": 0.3,
        "max_tokens": 2000
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(DEEPSEEK_API_URL, headers=headers, json=payload) as resp:
            if resp.status == 200:
                result = await resp.json()
                return result['choices'][0]['message']['content'].strip()
            else:
                return text

# ==================== SRT KONVERT ====================
def convert_to_srt(input_file: str) -> str:
    try:
        subs = pysrt.open(input_file)
        output_file = input_file.replace('.srt', '_conv.srt')
        subs.save(output_file, encoding='utf-8')
        return output_file
    except:
        return input_file

# ==================== YOUTUBE SUB ====================
async def get_youtube_subtitles(url: str):
    ydl_opts = {'skip_download': True, 'writesubtitles': True, 'writeautomaticsub': True,
                'subtitleslangs': ['all'], 'subtitlesformat': 'srt', 'quiet': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'Video')
            subs = info.get('subtitles', {})
            auto = info.get('automatic_captions', {})
            langs = {}
            for l, d in {**subs, **auto}.items():
                langs[l] = {'type': 'manual' if l in subs else 'auto', 'name': get_language_name(l)}
            return video_title, langs
    except:
        return "Video", {}

# ==================== START KOMANDASI ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    has_perm, expires = check_permission(user_id)
    if user_id == ADMIN_ID:
        keyboard = [[InlineKeyboardButton("👤 Admin Panel", callback_data="admin_menu")]]
        await update.message.reply_text("👑 Admin panel", reply_markup=InlineKeyboardMarkup(keyboard))
    elif has_perm:
        days_left = (expires - datetime.datetime.now()).days
        keyboard = [[InlineKeyboardButton("🎬 YouTube", callback_data="main_youtube")],
                    [InlineKeyboardButton("📄 SRT", callback_data="main_srt")]]
        await update.message.reply_text(f"✅ Xush kelibsiz! ({days_left} kun)\nTanlang:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(f"❌ Ruxsat yo'q. @Maestro_o ga murojaat qiling.\n🆔 ID: {user_id}")

# ==================== MAIN ====================
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    # Boshqa handlerlar (Callback, Message, SRT, Translate) shu yerga qo'shishingiz mumkin
    print("✅ Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
