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
import requests
from typing import Dict, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, CallbackQueryHandler, ContextTypes, ConversationHandler
)
import yt_dlp

# ==================== SOZLAMALAR ====================
BOT_TOKEN = "8763594610:AAE2UV2zYNUFk3HKEEKaWOZYo_XRsvvACOQ"
DEEPSEEK_API_KEY = "sk-37d52e756c5b43ee9d7f7042844277cb"
ADMIN_ID = 1700341163

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# Conversation states
WAITING_FOR_YOUTUBE = 1
WAITING_FOR_SRT = 2

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== MA'LUMOTLAR BAZASI ====================
def init_db():
    """SQLite bazasini yaratish"""
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        
        # Ruxsatlar jadvali
        c.execute('''CREATE TABLE IF NOT EXISTS permissions
                     (user_id INTEGER PRIMARY KEY,
                      username TEXT,
                      first_name TEXT,
                      last_name TEXT,
                      expires_at TEXT,
                      granted_by INTEGER,
                      granted_at TEXT)''')
        
        # Foydalanuvchi ma'lumotlari jadvali
        c.execute('''CREATE TABLE IF NOT EXISTS user_data
                     (user_id INTEGER PRIMARY KEY,
                      current_file TEXT,
                      video_title TEXT,
                      original_lang TEXT)''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Baza yaratildi")
    except Exception as e:
        logger.error(f"❌ Baza xatolik: {e}")

def add_permission(user_id: int, username: str, first_name: str, last_name: str, days: int) -> bool:
    """Foydalanuvchiga ruxsat berish"""
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

def remove_permission(user_id: int) -> bool:
    """Ruxsatni olib tashlash"""
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute('DELETE FROM permissions WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ruxsat o'chirish xatolik: {e}")
        return False

def check_permission(user_id: int) -> Tuple[bool, Optional[datetime.datetime]]:
    """Ruxsatni tekshirish"""
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

def get_all_users() -> list:
    """Barcha ruxsat berilgan foydalanuvchilarni olish"""
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        
        c.execute('''SELECT user_id, username, first_name, last_name, expires_at 
                     FROM permissions 
                     ORDER BY expires_at''')
        users = c.fetchall()
        
        conn.close()
        return users
    except Exception as e:
        logger.error(f"Foydalanuvchilar ro'yxatini olish xatolik: {e}")
        return []

def save_user_file(user_id: int, file_path: str, video_title: str, original_lang: str = None) -> bool:
    """Foydalanuvchi faylini saqlash"""
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

def get_user_file(user_id: int) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Foydalanuvchi faylini olish"""
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
                # Fayl yo'q bo'lsa, bazadan o'chirish
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
    """Til kodini nomga o'girish"""
    languages = {
        'en': 'Ingliz tili', 'ru': 'Rus tili', 'uz': 'O\'zbek tili', 'tr': 'Turk tili',
        'ar': 'Arab tili', 'fa': 'Fors tili', 'ur': 'Urdu tili', 'hi': 'Hind tili',
        'es': 'Ispan tili', 'fr': 'Fransuz tili', 'de': 'Nemis tili', 'it': 'Italyan tili',
        'ja': 'Yapon tili', 'ko': 'Koreys tili', 'zh': 'Xitoy tili', 'pt': 'Portugal tili',
        'id': 'Indonez tili', 'ms': 'Malay tili', 'th': 'Tay tili', 'vi': 'Vyetnam tili',
    }
    return languages.get(lang_code, lang_code.upper())

# ==================== DEEPSEEK TARJIMA (TO'G'IRLANGAN) ====================
async def translate_with_deepseek(text: str) -> Optional[str]:
    """DeepSeek orqali matnni O'ZBEK tiliga tarjima qilish"""
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": "Sen professional tarjimonsan. Matnni O'ZBEK tiliga tarjima qil. Faqat tarjima qilingan matnni qaytar."
            },
            {
                "role": "user",
                "content": text
            }
        ],
        "temperature": 0.3,
        "max_tokens": 2000
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(DEEPSEEK_API_URL, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    translated = result['choices'][0]['message']['content'].strip()
                    return translated
                else:
                    return None
    except Exception as e:
        logger.error(f"Tarjima xatolik: {e}")
        return None

async def translate_srt_file(update: Update, context: ContextTypes.DEFAULT_TYPE, srt_file: str, video_title: str):
    """SRT faylni tarjima qilish"""
    
    user_id = update.effective_user.id
    
    progress_msg = await context.bot.send_message(
        chat_id=user_id,
        text="🧠 *Tarjima boshlandi (O'zbek tiliga)*\n\n`[□□□□□□□□□□]` 0%",
        parse_mode='Markdown'
    )
    
    try:
        subs = pysrt.open(srt_file)
        total = len(subs)
        translated_subs = []
        
        start_time = time.time()
        
        for i, sub in enumerate(subs):
            translated_text = await translate_with_deepseek(sub.text)
            
            if translated_text:
                sub.text = translated_text
            else:
                sub.text = f"[?] {sub.text}"
            
            translated_subs.append(sub)
            
            # Har 20 qatorda progressni yangilash
            if (i + 1) % 20 == 0 or i == total - 1:
                percent = int((i + 1) / total * 100)
                filled = percent // 10
                empty = 10 - filled
                progress_bar = f"[{'█' * filled}{'□' * empty}]"
                
                await progress_msg.edit_text(
                    f"🧠 *Tarjima qilinmoqda...*\n\n"
                    f"{progress_bar} {percent}%\n"
                    f"📊 {i+1}/{total} qator",
                    parse_mode='Markdown'
                )
        
        # Faylni saqlash
        output_path = srt_file.replace('.srt', f'_ozbek.srt')
        new_subs = pysrt.SubRipFile()
        for sub in translated_subs:
            new_subs.append(sub)
        new_subs.save(output_path, encoding='utf-8')
        
        total_time = int(time.time() - start_time)
        
        await progress_msg.edit_text(
            f"✅ *Tarjima tugadi!*\n"
            f"⏱️ {total_time} sekund\n"
            f"📊 {total} ta qator",
            parse_mode='Markdown'
        )
        
        return output_path
        
    except Exception as e:
        logger.error(f"Tarjima xatolik: {e}")
        await progress_msg.edit_text("❌ Tarjima qilishda xatolik")
        return None

# ==================== YOUTUBE SUBTITR OLISH ====================
async def get_youtube_subtitles(url: str):
    """YouTube dan subtitr olish"""
    
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['all'],
        'subtitlesformat': 'srt',
        'quiet': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'Video')
            
            subtitles = info.get('subtitles', {})
            automatic = info.get('automatic_captions', {})
            
            available = {}
            
            # Qo'lda yuklanganlar
            for lang, data in subtitles.items():
                if data:
                    available[lang] = {'name': get_language_name(lang), 'type': 'manual'}
            
            # Avtomatik (faqat en, ru, uz, zh, ko)
            auto_allowed = ['en', 'ru', 'uz', 'zh', 'ko']
            for lang, data in
