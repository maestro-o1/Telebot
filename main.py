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
from typing import Dict, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, CallbackQueryHandler, ContextTypes, ConversationHandler
)
import yt_dlp

# ==================== SOZLAMALAR ====================
BOT_TOKEN = "8763594610:AAE2UV2zYNUFk3HKEEKaWOZYo_XRsvvACOQ"
DEEPSEEK_API_KEY = "sk-37d52e756c5b43ee9d7f7042844277cb"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

ADMIN_ID = 1700341163  # Sizning Telegram ID

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
        
        c.execute('''CREATE TABLE IF NOT EXISTS permissions
                     (user_id INTEGER PRIMARY KEY,
                      username TEXT,
                      first_name TEXT,
                      expires_at TIMESTAMP,
                      granted_by INTEGER,
                      granted_at TIMESTAMP)''')
        
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

def add_permission(user_id, username, first_name, days):
    """Foydalanuvchiga ruxsat berish"""
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        
        expires_at = datetime.datetime.now() + datetime.timedelta(days=days)
        
        c.execute('''INSERT OR REPLACE INTO permissions 
                     (user_id, username, first_name, expires_at, granted_by, granted_at)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (user_id, username, first_name, expires_at, ADMIN_ID, datetime.datetime.now()))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ruxsat berish xatolik: {e}")
        return False

def remove_permission(user_id):
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

def check_permission(user_id):
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

def get_all_users():
    """Barcha ruxsat berilgan foydalanuvchilarni olish"""
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        
        c.execute('''SELECT user_id, username, first_name, expires_at 
                     FROM permissions 
                     ORDER BY expires_at''')
        users = c.fetchall()
        
        conn.close()
        return users
    except Exception as e:
        logger.error(f"Foydalanuvchilar ro'yxatini olish xatolik: {e}")
        return []

def save_user_file(user_id, file_path, video_title, original_lang=None):
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

def get_user_file(user_id):
    """Foydalanuvchi faylini olish"""
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        
        c.execute('SELECT current_file, video_title, original_lang FROM user_data WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        conn.close()
        
        if result and result[0] and os.path.exists(result[0]):
            return result
        return None, None, None
    except Exception as e:
        logger.error(f"Fayl olish xatolik: {e}")
        return None, None, None

# ==================== TIL NOMLARI ====================
def get_language_name(lang_code):
    languages = {
        'en': 'Ingliz tili', 'ru': 'Rus tili', 'uz': 'O\'zbek tili', 'tr': 'Turk tili',
        'ar': 'Arab tili', 'fa': 'Fors tili', 'ur': 'Urdu tili', 'hi': 'Hind tili',
        'es': 'Ispan tili', 'fr': 'Fransuz tili', 'de': 'Nemis tili', 'it': 'Italyan tili',
        'ja': 'Yapon tili', 'ko': 'Koreys tili', 'zh': 'Xitoy tili', 'pt': 'Portugal tili',
    }
    return languages.get(lang_code, lang_code.upper())

# ==================== DEEPSEEK TARJIMA ====================
async def translate_with_deepseek(text, target_lang="uzbek"):
    """DeepSeek orqali matn tarjima qilish"""
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": f"Sen professional tarjimonsan. Matnni {target_lang} tiliga tarjima qil. Faqat tarjima qilingan matnni qaytar."
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
                    return result['choices'][0]['message']['content'].strip()
                return None
    except Exception as e:
        logger.error(f"Tarjima xatolik: {e}")
        return None

async def translate_with_progress(update, context, srt_file, video_title):
    """Progress bar bilan tarjima qilish"""
    
    user_id = update.effective_user.id
    
    progress_msg = await context.bot.send_message(
        chat_id=user_id,
        text="🧠 *Tarjima boshlandi*\n\n`[□□□□□□□□□□]` 0%",
        parse_mode='Markdown'
    )
    
    subs = pysrt.open(srt_file)
    total = len(subs)
    translated_subs = []
    
    start_time = time.time()
    last_update = time.time()
    
    for i, sub in enumerate(subs):
        translated_text = await translate_with_deepseek(sub.text, "uzbek")
        
        if translated_text:
            sub.text = translated_text
        else:
            sub.text = f"[?] {sub.text}"
        
        translated_subs.append(sub)
        
        current_time = time.time()
        if current_time - last_update >= 20 or i == total - 1:
            percent = int((i + 1) / total * 100)
            elapsed = int(current_time - start_time)
            
            if i > 0:
                avg_time = elapsed / (i + 1)
                remaining = int(avg_time * (total - i - 1))
                remaining_min = remaining // 60
                remaining_sec = remaining % 60
                time_text = f"{remaining_min}m {remaining_sec}s"
            else:
                time_text = "hisoblanmoqda..."
            
            filled = percent // 10
            empty = 10 - filled
            progress_bar = f"[{'█' * filled}{'□' * empty}]"
            
            try:
                await progress_msg.edit_text(
                    f"🧠 *Tarjima qilinmoqda...*\n\n"
                    f"{progress_bar} {percent}%\n"
                    f"⏱️ Qolgan vaqt: ~{time_text}\n"
                    f"📊 Qator: {i+1}/{total}",
                    parse_mode='Markdown'
                )
                last_update = current_time
            except:
                pass
        
        if (i + 1) % 5 == 0:
            await asyncio.sleep(1)
    
    await progress_msg.edit_text("✅ *Tarjima tugadi! Fayl tayyorlanmoqda...*", parse_mode='Markdown')
    
    output_path = srt_file.replace('.srt', f'_uz.srt')
    new_subs = pysrt.SubRipFile()
    for sub in translated_subs:
        new_subs.append(sub)
    new_subs.save(output_path, encoding='utf-8')
    
    if os.path.exists(output_path):
        logger.info(f"✅ Fayl saqlandi: {output_path}")
        return output_path, progress_msg
    return None, progress_msg

# ==================== SUBTITR FORMATLARINI O'GIRISH ====================
def convert_to_srt(input_file, input_format):
    """Turli formatdagi subtitrni SRT ga o'girish"""
    
    output_file = input_file.replace(f'.{input_format}', '.srt')
    
    try:
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        if input_format == 'vtt':
            lines = content.split('\n')
            srt_lines = []
            counter = 1
            in_cue = False
            
            for line in lines:
                line = line.strip()
                if '-->' in line and not line.startswith('WEBVTT'):
                    line = line.replace('.', ',')
                    srt_lines.append(str(counter))
                    counter += 1
                    srt_lines.append(line)
                    in_cue = True
                elif line == '' and in_cue:
                    srt_lines.append('')
                    in_cue = False
                elif in_cue and line:
                    srt_lines.append(line)
            
            content = '\n'.join(srt_lines)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return output_file
    except Exception as e:
        logger.error(f"Konvertatsiya xatolik: {e}")
        return None

# ==================== YOUTUBE SUBTITR OLISH ====================
async def get_youtube_subtitles(url):
    """YouTube dan subtitr olish"""
    
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['all'],
        'subtitlesformat': 'srt/vtt',
        'quiet': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'Noma\'lum video')
            
            subtitles = info.get('subtitles', {})
            auto_captions = info.get('automatic_captions', {})
            
            available_langs = {}
            
            for lang, sub_data in subtitles.items():
                if sub_data:
                    lang_name = get_language_name(lang)
                    available_langs[lang] = {
                        'name': lang_name, 
                        'type': 'manual',
                        'data': sub_data
                    }
            
            for lang, sub_data in auto_captions.items():
                if sub_data and lang not in available_langs:
                    lang_name = get_language_name(lang)
                    available_langs[lang] = {
                        'name': lang_name + ' (auto)', 
                        'type': 'auto',
                        'data': sub_data
                    }
            
            return video_title, available_langs, info
            
    except Exception as e:
        logger.error(f"YouTube xatolik: {e}")
        return None, {}, None

async def download_subtitle(url, lang_code, lang_info):
    """Subtitrni yuklab olish"""
    
    with tempfile.NamedTemporaryFile(suffix='.srt', delete=False) as tmp_file:
        temp_filename = tmp_file.name
    
    try:
        ydl_opts = {
            'skip_download': True,
            'writesubtitles': True,
            'subtitleslangs': [lang_code],
            'subtitlesformat': 'srt/vtt',
            'outtmpl': temp_filename.replace('.srt', ''),
            'quiet': True,
        }
        
        if lang_info['type'] == 'auto':
            ydl_opts['writeautomaticsub'] = True
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        base_name = temp_filename.replace('.srt', '')
        possible_files = []
        
        for ext in ['srt', 'vtt']:
            file_path = f"{base_name}.{lang_code}.{ext}"
            if os.path.exists(file_path):
                possible_files.append((file_path, ext))
            
            file_path2 = f"{base_name}.{ext}"
            if os.path.exists(file_path2):
                possible_files.append((file_path2, ext))
        
        if not possible_files:
            return None
        
        downloaded_file, file_ext = possible_files[0]
        
        if file_ext != 'srt':
            srt_file = convert_to_srt(downloaded_file, file_ext)
            try:
                os.remove(downloaded_file)
            except:
                pass
            return srt_file
        else:
            return downloaded_file
        
    except Exception as e:
        logger.error(f"Subtitr yuklash xatolik: {e}")
        return None

# ==================== START KOMANDASI ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        username = update.effective_user.username
        first_name = update.effective_user.first_name or "Foydalanuvchi"
        
        logger.info(f"🔥 START: {user_id} (@{username})")
        
        if user_id == ADMIN_ID:
            keyboard = [
                [InlineKeyboardButton("👤 Ruxsat berish", callback_data="admin_menu")],
                [InlineKeyboardButton("📋 Ruxsatlarni boshqarish", callback_data="admin_manage")],
                [InlineKeyboardButton("🎬 Botdan foydalanish", callback_data="user_menu")]
            ]
            await update.message.reply_text(
                "👑 *Admin panel*",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            return
        
        has_perm, expires = check_permission(user_id)
        
        if has_perm:
            keyboard = [
                [InlineKeyboardButton("🎬 YouTube video", callback_data="main_youtube")],
                [InlineKeyboardButton("📄 SRT fayl yuborish", callback_data="main_srt")]
            ]
            days_left = (expires - datetime.datetime.now()).days
            await update.message.reply_text(
                f"✅ *Xush kelibsiz!*\n🕒 {days_left} kun qoldi",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"❌ *Ruxsat yo'q*\n\n"
                f"Botdan foydalanish uchun @maestro_o ga murojaat qiling.\n"
                f"Rozi bo'lsa, ID raqamingizni yuboring.\n\n"
                f"🆔 *Sizning ID:* `{user_id}`",
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Start xatolik: {e}")

# ==================== ADMIN MENYU ====================
async def admin_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        await query.edit_message_text("❌ Ruxsat yo'q!")
        return
    
    await query.edit_message_text(
        "👤 *Ruxsat berish*\n\nFoydalanuvchi ID raqamini yuboring:",
        parse_mode='Markdown'
    )
    context.user_data['admin_action'] = 'waiting_for_add_id'

async def admin_manage_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        await query.edit_message_text("❌ Ruxsat yo'q!")
        return
    
    users = get_all_users()
    
    if not users:
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]]
        await query.edit_message_text(
            "📋 *Ruxsatlar ro'yxati*\n\nHech kimga ruxsat berilmagan.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    
    text = "📋 *Ruxsat berilgan foydalanuvchilar:*\n\n"
    keyboard = []
    
    for uid, uname, fname, expires in users:
        days_left = (datetime.datetime.fromisoformat(expires) - datetime.datetime.now()).days
        
        if uname and uname != "noma'lum":
            display_name = f"@{uname}"
            button = InlineKeyboardButton(
                f"👤 {uid} | {display_name} | {days_left} kun",
                url=f"https://t.me/{uname}"
            )
        else:
            display_name = fname or str(uid)
            button = InlineKeyboardButton(
                f"👤 {uid} | {display_name} | {days_left} kun",
                callback_data=f"user_{uid}"
            )
        
        keyboard.append([button])
        keyboard.append([InlineKeyboardButton(f"❌ {uid} ni bekor qilish", callback_data=f"remove_{uid}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")])
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def remove_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    target_id = int(query.data.replace("remove_", ""))
    
    if remove_permission(target_id):
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="❌ *Ruxsatingiz bekor qilindi!*",
                parse_mode='Markdown'
            )
        except:
            pass
    
    await admin_manage_callback(update, context)

async def back_to_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    keyboard = [
        [InlineKeyboardButton("👤 Ruxsat berish", callback_data="admin_menu")],
        [InlineKeyboardButton("📋 Ruxsatlarni boshqarish", callback_data="admin_manage")],
        [InlineKeyboardButton("🎬 Botdan foydalanish", callback_data="user_menu")]
    ]
    
    await query.edit_message_text(
        "👑 *Admin panel*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def user_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    keyboard = [
        [InlineKeyboardButton("🎬 YouTube video", callback_data="main_youtube")],
        [InlineKeyboardButton("📄 SRT fayl yuborish", callback_data="main_srt")],
        [InlineKeyboardButton("🔙 Admin panel", callback_data="back_to_admin")]
    ]
    
    await query.edit_message_text(
        "🎬 *Botdan foydalanish*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ==================== ADMIN XABARLAR ====================
async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    text = update.message.text
    action = context.user_data.get('admin_action')
    
    if action == 'waiting_for_add_id':
        try:
            target_id = int(text.strip())
            context.user_data['target_id'] = target_id
            context.user_data['admin_action'] = 'waiting_for_days'
            
            keyboard = [
                [InlineKeyboardButton("3 kun", callback_data="days_3"),
                 InlineKeyboardButton("7 kun", callback_data="days_7")],
                [InlineKeyboardButton("10 kun", callback_data="days_10"),
                 InlineKeyboardButton("20 kun", callback_data="days_20")],
                [InlineKeyboardButton("30 kun", callback_data="days_30")],
                [InlineKeyboardButton("🔙 Bekor qilish", callback_data="back_to_admin")]
            ]
            
            await update.message.reply_text(
                f"🆔 ID: {target_id}\n\nQancha kun?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except ValueError:
            await update.message.reply_text("❌ Noto'g'ri ID")

async def days_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    data = query.data
    target_id = context.user_data.get('target_id')
    
    if not target_id:
        return
    
    days_map = {'days_3': 3, 'days_7': 7, 'days_10': 10, 'days_20': 20, 'days_30': 30}
    days = days_map.get(data)
    
    if days and add_permission(target_id, "user", "Foydalanuvchi", days):
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"✅ *Ruxsat berildi!*\n\nSizga {days} kun ruxsat berildi.\n/start ni bosing.",
                parse_mode='Markdown'
            )
        except:
            pass
        
        await query.edit_message_text(f"✅ Ruxsat berildi! ID: {target_id}, {days} kun")
        
        context.user_data['admin_action'] = None
        context.user_data['target_id'] = None

# ==================== ASOSIY MENYU ====================
async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    has_perm, _ = check_permission(user_id)
    if not has_perm and user_id != ADMIN_ID:
        await query.edit_message_text("❌ Ruxsat yo'q!")
        return
    
    if data == "main_youtube":
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="main_back")]]
        await query.edit_message_text(
            "🎬 *YouTube video*\n\nVideo havolasini yuboring:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        context.user_data['state'] = WAITING_FOR_YOUTUBE
        
    elif data == "main_srt":
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="main_back")]]
        await query.edit_message_text(
            "📄 *SRT fayl*\n\nSRT faylni yuboring:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        context.user_data['state'] = WAITING_FOR_SRT
        
    elif data == "main_back":
        if user_id == ADMIN_ID:
            keyboard = [
                [InlineKeyboardButton("🎬 YouTube video", callback_data="main_youtube")],
                [InlineKeyboardButton("📄 SRT fayl yuborish", callback_data="main_srt")],
                [InlineKeyboardButton("🔙 Admin panel", callback_data="back_to_admin")]
            ]
        else:
            keyboard = [
                [InlineKeyboardButton("🎬 YouTube video", callback_data="main_youtube")],
                [InlineKeyboardButton("📄 SRT fayl yuborish", callback_data="main_srt")]
            ]
        
        has_perm, expires = check_permission(user_id)
        days_left = (expires - datetime.datetime.now()).days if has_perm else 0
        text = f"✅ *Xush kelibsiz!*\n🕒 {days_left} kun qoldi" if user_id != ADMIN_ID else "Tanlang:"
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

# ==================== YOUTUBE HAVOLA ====================
async def handle_youtube_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('state') != WAITING_FOR_YOUTUBE:
        return
    
    user_id = update.effective_user.id
    url = update.message.text
    
    has_perm, _ = check_permission(user_id)
    if not has_perm and user_id != ADMIN_ID:
        await update.message.reply_text("❌ Ruxsat yo'q!")
        return
    
    progress_msg = await update.message.reply_text("⏳ Video tekshirilmoqda...")
    
    video_title, available_langs, _ = await get_youtube_subtitles(url)
    
    if not available_langs:
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="main_back")]]
        await progress_msg.edit_text(
            "😕 *Subtitr topilmadi!*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        context.user_data['state'] = None
        return
    
    keyboard = []
    for lang_code, lang_info in available_langs.items():
        icon = "📝" if lang_info['type'] == 'manual' else "🤖"
        button = InlineKeyboardButton(
            f"{icon} {lang_info['name']}",
            callback_data=f"sub_{lang_code}"
        )
        keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton("🔙 Asosiy menyu", callback_data="main_back")])
    
    context.user_data['video_url'] = url
    context.user_data['video_title'] = video_title
    context.user_data['langs'] = available_langs
    
    await progress_msg.edit_text(
        f"📹 *{video_title[:50]}*\n\n🎯 {len(available_langs)} ta subtitr",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    context.user_data['state'] = None

# ==================== SUBTITR YUKLASH ====================
async def subtitle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    has_perm, _ = check_permission(user_id)
    if not has_perm and user_id != ADMIN_ID:
        await query.edit_message_text("❌ Ruxsat yo'q!")
        return
    
    if data.startswith("sub_"):
        lang_code = data.replace("sub_", "")
        
        url = context.user_data.get('video_url')
        video_title = context.user_data.get('video_title')
        langs = context.user_data.get('langs', {})
        
        if not url or lang_code not in langs:
            await query.edit_message_text("❌ Xatolik")
            return
        
        lang_info = langs[lang_code]
        
        await query.edit_message_text(f"⏳ {lang_info['name']} yuklanmoqda...")
        
        srt_file = await download_subtitle(url, lang_code, lang_info)
        
        if srt_file and os.path.exists(srt_file):
            save_user_file(user_id, srt_file, video_title, lang_info['name'])
            
            with open(srt_file, 'rb') as f:
                await context.bot.send_document(
                    chat_id=user_id,
                    document=f,
                    filename=f"{video_title[:30]}_{lang_code}.srt",
                    caption=f"📥 {video_title[:50]}"
                )
            
            keyboard = [
                [InlineKeyboardButton("🧠 Tarjima qilish", callback_data="translate_srt")],
                [InlineKeyboardButton("🔙 Asosiy menyu", callback_data="main_back")]
            ]
            
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ *Subtitr tayyor!*\n\n🧠 Tarjima qilish uchun tugmani bosing:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
            await query.delete_message()
        else:
            await query.edit_message_text("❌ Subtitr yuklanmadi")

# ==================== SRT FAYLNI QAYTA ISHLASH ====================
async def handle_srt_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('state') != WAITING_FOR_SRT:
        return
    
    user_id = update.effective_user.id
    
    has_perm, _ = check_permission(user_id)
    if not has_perm and user_id != ADMIN_ID:
        await update.message.reply_text("❌ Ruxsat yo'q!")
        return
    
    document = update.message.document
    
    if not document.file_name.endswith('.srt'):
        await update.message.reply_text("❌ Faqat .srt fayl yuboring!")
        return
    
    file = await context.bot.get_file(document.file_id)
    
    with tempfile.NamedTemporaryFile(suffix='.srt', delete=False) as tmp_file:
        temp_filename = tmp_file.name
    
    await file.download_to_drive(temp_filename)
    
    save_user_file(user_id, temp_filename, document.file_name, "Yuklangan")
    
    keyboard = [
        [InlineKeyboardButton("🧠 Tarjima qilish", callback_data="translate_srt")],
        [InlineKeyboardButton("🔙 Asosiy menyu", callback_data="main_back")]
    ]
    
    await update.message.reply_text(
        f"✅ *{document.file_name} qabul qilindi!*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    context.user_data['state'] = None

# ==================== TARJIMA QILISH ====================
async def translate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    has_perm, _ = check_permission(user_id)
    if not has_perm and user_id != ADMIN_ID:
        await query.edit_message_text("❌ Ruxsat yo'q!")
        return
    
    if query.data == "translate_srt":
        srt_file, video_title, _ = get_user_file(user_id)
        
        if not srt_file:
            await query.edit_message_text("❌ Fayl topilmadi")
            return
        
        translated_file, progress_msg = await translate_with_progress(
            update, context, srt_file, video_title
        )
        
        if translated_file and os.path.exists(translated_file):
            try:
                with open(translated_file, 'rb') as f:
                    await context.bot.send_document(
                        chat_id=user_id,
                        document=f,
                        filename=f"ozbekcha_{os.path.basename(srt_file)}",
                        caption=f"✅ *Tarjima tayyor!*"
                    )
                
                await progress_msg.delete()
                
                try:
                    os.remove(translated_file)
                except:
                    pass
                
                if user_id == ADMIN_ID:
                    keyboard = [
                        [InlineKeyboardButton("🎬 YouTube", callback_data="main_youtube")],
                        [InlineKeyboardButton("📄 SRT", callback_data="main_srt")],
                        [InlineKeyboardButton("🔙 Admin", callback_data="back_to_admin")]
                    ]
                else:
                    keyboard = [
                        [InlineKeyboardButton("🎬 YouTube", callback_data="main_youtube")],
                        [InlineKeyboardButton("📄 SRT", callback_data="main_srt")]
                    ]
                
                await context.bot.send_message(
                    chat_id=user_id,
                    text="✨ Yana?",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
            except Exception as e:
                logger.error(f"Fayl yuborish xatolik: {e}")
                await progress_msg.edit_text(f"❌ Xatolik: {str(e)[:100]}")
        else:
            await progress_msg.edit_text("❌ Tarjima xatolik")

# ==================== ASOSIY FUNKSIYA ====================
def main():
    """Botni ishga tushirish"""
    
    try:
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates", params={"offset": -1})
        time.sleep(2)
        
        init_db()
        
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Handlerlar
        application.add_handler(CommandHandler("start", start))
        
        application.add_handler(CallbackQueryHandler(admin_menu_callback, pattern="^admin_menu$"))
        application.add_handler(CallbackQueryHandler(admin_manage_callback, pattern="^admin_manage$"))
        application.add_handler(CallbackQueryHandler(remove_user_callback, pattern="^remove_"))
        application.add_handler(CallbackQueryHandler(user_menu_callback, pattern="^user_menu$"))
        application.add_handler(CallbackQueryHandler(back_to_admin_callback, pattern="^back_to_admin$"))
        application.add_handler(CallbackQueryHandler(days_callback, pattern="^days_"))
        application.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_"))
        application.add_handler(CallbackQueryHandler(subtitle_callback, pattern="^sub_"))
        application.add_handler(CallbackQueryHandler(translate_callback, pattern="^translate_"))
        
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_message))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_youtube_url))
        application.add_handler(MessageHandler(filters.Document.ALL, handle_srt_file))
        
        print("🚀 Bot ishga tushdi...")
        print(f"👑 Admin ID: {ADMIN_ID}")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"Main xatolik: {e}")
        time.sleep(5)
        main()

if __name__ == '__main__':
    main()
