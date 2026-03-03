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
        logger.error(f"❌ Baza xatolik: {e}")

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

def remove_permission(user_id: int) -> bool:
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
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute('''SELECT user_id, username, first_name, last_name, expires_at 
                     FROM permissions ORDER BY expires_at''')
        users = c.fetchall()
        conn.close()
        return users
    except Exception as e:
        logger.error(f"Foydalanuvchilar ro'yxatini olish xatolik: {e}")
        return []

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

def get_user_file(user_id: int) -> Tuple[Optional[str], Optional[str], Optional[str]]:
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
                "content": "Sen professional tarjimonsan. Matnni O'ZBEK tiliga tarjima qil. Faqat tarjima qilingan matnni qaytar, boshqa hech narsa qo'shma."
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
                    logger.info(f"Tarjima qilindi: {text[:30]}... -> {translated[:30]}...")
                    return translated
                else:
                    error = await resp.text()
                    logger.error(f"DeepSeek xatolik: {resp.status} - {error}")
                    return None
    except Exception as e:
        logger.error(f"Tarjima xatolik: {e}")
        return None

async def translate_srt_file(update: Update, context: ContextTypes.DEFAULT_TYPE, srt_file: str, video_title: str):
    """SRT faylni O'zbek tiliga tarjima qilish"""
    
    user_id = update.effective_user.id
    
    progress_msg = await context.bot.send_message(
        chat_id=user_id,
        text="🧠 *O'zbek tiliga tarjima qilinmoqda...*\n\n`[□□□□□□□□□□]` 0%",
        parse_mode='Markdown'
    )
    
    try:
        subs = pysrt.open(srt_file)
        total = len(subs)
        translated_subs = []
        
        start_time = time.time()
        success_count = 0
        fail_count = 0
        
        for i, sub in enumerate(subs):
            # Har bir qatorni tarjima qilish
            translated_text = await translate_with_deepseek(sub.text)
            
            if translated_text:
                sub.text = translated_text
                success_count += 1
            else:
                sub.text = f"[Tarjima qilinmadi] {sub.text}"
                fail_count += 1
            
            translated_subs.append(sub)
            
            # Progressni yangilash (har 10 qatorda)
            if (i + 1) % 10 == 0 or i == total - 1:
                percent = int((i + 1) / total * 100)
                filled = percent // 10
                empty = 10 - filled
                progress_bar = f"[{'█' * filled}{'□' * empty}]"
                
                await progress_msg.edit_text(
                    f"🧠 *O'zbek tiliga tarjima qilinmoqda...*\n\n"
                    f"{progress_bar} {percent}%\n"
                    f"📊 {i+1}/{total} qator\n"
                    f"✅ {success_count} ta tarjima qilindi",
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
            f"📊 {total} ta qatordan {success_count} tasi tarjima qilindi\n"
            f"❌ {fail_count} tasida xatolik",
            parse_mode='Markdown'
        )
        
        return output_path
        
    except Exception as e:
        logger.error(f"Tarjima jarayonida xatolik: {e}")
        await progress_msg.edit_text("❌ Tarjima qilishda xatolik yuz berdi")
        return None

# ==================== SUBTITR FORMATLARINI O'GIRISH ====================
def vtt_to_srt(vtt_content: str) -> str:
    lines = vtt_content.split('\n')
    srt_lines = []
    counter = 1
    in_cue = False
    
    for line in lines:
        line = line.strip()
        
        if line.startswith('WEBVTT') or line.startswith('NOTE') or line.startswith('STYLE'):
            continue
        
        if '-->' in line:
            line = line.replace('.', ',')
            line = re.sub(r'<[^>]+>', '', line)
            srt_lines.append(str(counter))
            counter += 1
            srt_lines.append(line)
            in_cue = True
        elif line == '':
            if in_cue:
                srt_lines.append('')
                in_cue = False
        else:
            if in_cue:
                line = re.sub(r'<[^>]+>', '', line)
                srt_lines.append(line)
    
    return '\n'.join(srt_lines)

def ass_to_srt(ass_content: str) -> str:
    srt_lines = []
    counter = 1
    dialogue_pattern = r'Dialogue:\s*\d+,(\d+:\d+:\d+\.\d+),(\d+:\d+:\d+\.\d+),[^,]*,[^,]*,\d+,\d+,\d+,(.*)'
    
    for line in ass_content.split('\n'):
        if line.startswith('Dialogue:'):
            match = re.match(dialogue_pattern, line)
            if match:
                start = match.group(1).replace('.', ',')
                end = match.group(2).replace('.', ',')
                text = match.group(3)
                text = re.sub(r'\{[^}]*\}', '', text)
                text = text.replace('\\N', '\n').replace('\\n', '\n')
                text = re.sub(r'<[^>]+>', '', text)
                
                srt_lines.append(str(counter))
                counter += 1
                srt_lines.append(f"{start} --> {end}")
                srt_lines.append(text.strip())
                srt_lines.append('')
    
    return '\n'.join(srt_lines)

def sbv_to_srt(sbv_content: str) -> str:
    lines = sbv_content.split('\n')
    srt_lines = []
    counter = 1
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        if ',' in line and line.count(':') >= 2:
            times = line.split(',')
            if len(times) == 2:
                start = times[0].replace('.', ',')
                end = times[1].replace('.', ',')
                
                srt_lines.append(str(counter))
                counter += 1
                srt_lines.append(f"{start} --> {end}")
                
                i += 1
                while i < len(lines) and lines[i].strip():
                    text = lines[i].strip()
                    text = re.sub(r'<[^>]+>', '', text)
                    srt_lines.append(text)
                    i += 1
                
                srt_lines.append('')
        i += 1
    
    return '\n'.join(srt_lines)

def convert_to_srt(input_file: str, input_format: str) -> Optional[str]:
    output_file = input_file.replace(f'.{input_format}', '.srt')
    
    try:
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        if input_format == 'vtt':
            srt_content = vtt_to_srt(content)
        elif input_format in ['ass', 'ssa']:
            srt_content = ass_to_srt(content)
        elif input_format in ['sbv', 'sub']:
            srt_content = sbv_to_srt(content)
        elif input_format == 'srt':
            return input_file
        else:
            try:
                subs = pysrt.open(input_file)
                subs.save(output_file, encoding='utf-8')
                return output_file
            except:
                return None
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(srt_content)
        
        return output_file
    except Exception as e:
        logger.error(f"Konvertatsiya xatolik: {e}")
        return None

# ==================== YOUTUBE SUBTITR OLISH ====================
async def get_youtube_subtitles(url: str):
    """YouTube dan subtitr olish - manual va auto alohida"""
    
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['all'],
        'subtitlesformat': 'srt/vtt/ass/ssa/sbv',
        'quiet': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'Video')
            
            subtitles = info.get('subtitles', {})
            automatic = info.get('automatic_captions', {})
            
            manual_subs = {}
            auto_subs = {}
            
            # 1. QO'LDA YUKLANGANLAR - HAMMASI
            for lang, data in subtitles.items():
                if data:
                    name = get_language_name(lang)
                    manual_subs[lang] = {
                        'name': name,
                        'type': 'manual',
                        'data': data
                    }
                    logger.info(f"Manual: {lang} - {name}")
            
            # 2. AVTO GENERATED - FAQAT O'zbek, Ingliz, Xitoy
            allowed_auto = {'uz': 'O\'zbek tili', 'en': 'Ingliz tili', 'zh': 'Xitoy tili'}
            for lang, data in automatic.items():
                if data and lang not in manual_subs:
                    if lang in allowed_auto:
                        auto_subs[lang] = {
                            'name': f"{allowed_auto[lang]} (avto)",
                            'type': 'auto',
                            'data': data
                        }
                        logger.info(f"Auto: {lang} - {allowed_auto[lang]}")
            
            return video_title, manual_subs, auto_subs
            
    except Exception as e:
        logger.error(f"YouTube xatolik: {e}")
        return None, {}, {}

async def download_subtitle(url: str, lang_code: str, lang_info: dict) -> Optional[str]:
    """Subtitrni yuklab olish - barcha formatlarni qo'llab-quvvatlash"""
    
    with tempfile.NamedTemporaryFile(suffix='.srt', delete=False) as tmp:
        temp_filename = tmp.name
    
    try:
        ydl_opts = {
            'skip_download': True,
            'writesubtitles': True,
            'subtitleslangs': [lang_code],
            'subtitlesformat': 'srt/vtt/ass/ssa/sbv',
            'outtmpl': temp_filename.replace('.srt', ''),
            'quiet': True,
        }
        
        if lang_info['type'] == 'auto':
            ydl_opts['writeautomaticsub'] = True
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        base_name = temp_filename.replace('.srt', '')
        
        # Barcha formatlarni qidirish
        for ext in ['srt', 'vtt', 'ass', 'ssa', 'sbv']:
            # Lang kod bilan
            file_path = f"{base_name}.{lang_code}.{ext}"
            if os.path.exists(file_path):
                logger.info(f"Subtitr topildi: {file_path}")
                if ext != 'srt':
                    return convert_to_srt(file_path, ext)
                return file_path
            
            # Lang kodsiz
            file_path2 = f"{base_name}.{ext}"
            if os.path.exists(file_path2):
                logger.info(f"Subtitr topildi: {file_path2}")
                if ext != 'srt':
                    return convert_to_srt(file_path2, ext)
                return file_path2
        
        logger.error(f"Hech qanday subtitr topilmadi: {base_name}")
        return None
        
    except Exception as e:
        logger.error(f"Subtitr yuklash xatolik: {e}")
        return None

# ==================== START KOMANDASI - 3 TUGMA ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """START KOMANDASI - 3 ta tugma bilan"""
    try:
        user_id = update.effective_user.id
        
        # Adminmi tekshirish
        if user_id == ADMIN_ID:
            keyboard = [
                [InlineKeyboardButton("🎬 YouTubedan srt olish va tarjima", callback_data="main_youtube")],
                [InlineKeyboardButton("📄 SRT faylni tarjima qilish", callback_data="main_srt")],
                [InlineKeyboardButton("👑 Admin panel", callback_data="admin_menu")]
            ]
            await update.message.reply_text(
                "👋 *Xush kelibsiz!*\n\nTanlang:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            return
        
        # Oddiy foydalanuvchi
        has_perm, expires = check_permission(user_id)
        
        if has_perm:
            keyboard = [
                [InlineKeyboardButton("🎬 YouTubedan srt olish va tarjima", callback_data="main_youtube")],
                [InlineKeyboardButton("📄 SRT faylni tarjima qilish", callback_data="main_srt")]
            ]
            days_left = (expires - datetime.datetime.now()).days
            await update.message.reply_text(
                f"👋 *Xush kelibsiz!* ({days_left} kun qoldi)\n\nTanlang:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"❌ *Ruxsat yo'q*\n\n"
                f"Botdan foydalanish uchun @maestro_o ga murojaat qiling.\n"
                f"🆔 ID: `{user_id}`",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Start xatolik: {e}")
        await update.message.reply_text("⚠️ Xatolik yuz berdi.")

# ==================== ADMIN PANEL ====================
async def admin_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        await query.edit_message_text("❌ Bu faqat admin uchun!")
        return
    
    keyboard = [
        [InlineKeyboardButton("👤 Ruxsat berish", callback_data="admin_add")],
        [InlineKeyboardButton("📋 Ruxsatlarni boshqarish", callback_data="admin_list")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_start")]
    ]
    await query.edit_message_text(
        "👑 *Admin panel*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def admin_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("👤 Foydalanuvchi ID raqamini yuboring:")
    context.user_data['admin_action'] = 'waiting_for_add_id'

async def admin_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    users = get_all_users()
    
    if not users:
        await query.edit_message_text(
            "📋 Hech kimga ruxsat berilmagan",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_menu")]])
        )
        return
    
    text = "📋 *Ruxsat berilganlar:*\n\n"
    keyboard = []
    
    for uid, uname, fname, lname, expires in users:
        days_left = (datetime.datetime.fromisoformat(expires) - datetime.datetime.now()).days
        name = f"{fname} {lname}".strip() or "Ismsiz"
        text += f"🆔 {uid} | {name} | {days_left} kun\n"
        keyboard.append([InlineKeyboardButton(f"❌ {name} ni o'chirish", callback_data=f"remove_{uid}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_menu")])
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def remove_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    target_id = int(query.data.replace("remove_", ""))
    
    if remove_permission(target_id):
        await query.edit_message_text("✅ Ruxsat bekor qilindi")
    else:
        await query.edit_message_text("❌ Xatolik")
    
    await admin_list_callback(update, context)

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if update.effective_user.id != ADMIN_ID:
        return False
    
    if context.user_data.get('admin_action') == 'waiting_for_add_id':
        try:
            target_id = int(update.message.text)
            
            try:
                chat = await context.bot.get_chat(target_id)
                username = chat.username or "noma'lum"
                first_name = chat.first_name or ""
                last_name = chat.last_name or ""
            except:
                username = "noma'lum"
                first_name = "Noma'lum"
                last_name = ""
            
            context.user_data['target_id'] = target_id
            context.user_data['target_username'] = username
            context.user_data['target_first_name'] = first_name
            context.user_data['target_last_name'] = last_name
            context.user_data['admin_action'] = 'waiting_for_days'
            
            keyboard = [
                [InlineKeyboardButton("3 kun", callback_data="days_3"),
                 InlineKeyboardButton("7 kun", callback_data="days_7")],
                [InlineKeyboardButton("10 kun", callback_data="days_10"),
                 InlineKeyboardButton("20 kun", callback_data="days_20")],
                [InlineKeyboardButton("30 kun", callback_data="days_30")],
                [InlineKeyboardButton("🔙 Bekor qilish", callback_data="admin_menu")]
            ]
            
            name = f"{first_name} {last_name}".strip()
            await update.message.reply_text(
                f"ID: {target_id}\nIsm: {name}\nUsername: @{username}\n\nKun tanlang:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await update.message.reply_text("❌ Noto'g'ri ID")
        
        return True
    
    return False

async def days_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    target_id = context.user_data.get('target_id')
    target_username = context.user_data.get('target_username', 'user')
    target_first_name = context.user_data.get('target_first_name', '')
    target_last_name = context.user_data.get('target_last_name', '')
    
    if not target_id:
        await query.edit_message_text("❌ Xatolik")
        return
    
    days_map = {'days_3': 3, 'days_7': 7, 'days_10': 10, 'days_20': 20, 'days_30': 30}
    
    if data in days_map:
        days = days_map[data]
        
        if add_permission(target_id, target_username, target_first_name, target_last_name, days):
            try:
                await context.bot.send_message(target_id, f"✅ Ruxsat berildi! {days} kun")
                msg = "✅ Ruxsat berildi"
            except:
                msg = "✅ Ruxsat berildi (xabar bormadi)"
        else:
            msg = "❌ Xatolik"
        
        await query.edit_message_text(msg)
        context.user_data['admin_action'] = None
        context.user_data['target_id'] = None

# ==================== BACK TO START ====================
async def back_to_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if user_id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("🎬 YouTubedan srt olish va tarjima", callback_data="main_youtube")],
            [InlineKeyboardButton("📄 SRT faylni tarjima qilish", callback_data="main_srt")],
            [InlineKeyboardButton("👑 Admin panel", callback_data="admin_menu")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("🎬 YouTubedan srt olish va tarjima", callback_data="main_youtube")],
            [InlineKeyboardButton("📄 SRT faylni tarjima qilish", callback_data="main_srt")]
        ]
    
    await query.edit_message_text(
        "👋 *Xush kelibsiz!*\n\nTanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# ==================== ASOSIY MENYU ====================
async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    has_perm, _ = check_permission(user_id)
    if not has_perm and user_id != ADMIN_ID:
        await query.edit_message_text("❌ Ruxsat yo'q")
        return
    
    if query.data == "main_youtube":
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_start")]]
        await query.edit_message_text(
            "🎬 *YouTube havolasini yuboring:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        context.user_data['state'] = WAITING_FOR_YOUTUBE
        
    elif query.data == "main_srt":
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_start")]]
        await query.edit_message_text(
            "📄 *SRT faylni yuboring:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        context.user_data['state'] = WAITING_FOR_SRT

# ==================== YOUTUBE HAVOLA ====================
async def handle_youtube_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if context.user_data.get('state') != WAITING_FOR_YOUTUBE:
        return False
    
    user_id = update.effective_user.id
    url = update.message.text
    
    has_perm, _ = check_permission(user_id)
    if not has_perm and user_id != ADMIN_ID:
        await update.message.reply_text("❌ Ruxsat yo'q")
        return True
    
    msg = await update.message.reply_text("⏳ Video tekshirilmoqda...")
    
    video_title, manual_subs, auto_subs = await get_youtube_subtitles(url)
    
    if not manual_subs and not auto_subs:
        await msg.edit_text("❌ Subtitr topilmadi")
        context.user_data['state'] = None
        return True
    
    text = f"📹 *{video_title}*\n\n"
    keyboard = []
    
    # Manual subtitrlar
    if manual_subs:
        text += "📝 *Qo'lda yuklanganlar:*\n"
        for lang_code, lang_info in manual_subs.items():
            text += f"  • {lang_info['name']}\n"
            keyboard.append([InlineKeyboardButton(f"📝 {lang_info['name']}", callback_data=f"sub_{lang_code}_manual")])
        text += "\n"
    
    # Auto subtitrlar
    if auto_subs:
        text += "🤖 *Avtomatik yaratilganlar:*\n"
        for lang_code, lang_info in auto_subs.items():
            text += f"  • {lang_info['name']}\n"
            keyboard.append([InlineKeyboardButton(f"🤖 {lang_info['name']}", callback_data=f"sub_{lang_code}_auto")])
    
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_start")])
    
    await msg.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    # Ma'lumotlarni saqlash
    all_langs = {**manual_subs, **auto_subs}
    context.user_data['video_url'] = url
    context.user_data['video_title'] = video_title
    context.user_data['langs'] = all_langs
    context.user_data['state'] = None
    
    return True

# ==================== SUBTITR YUKLASH ====================
async def subtitle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    has_perm, _ = check_permission(user_id)
    if not has_perm and user_id != ADMIN_ID:
        await query.edit_message_text("❌ Ruxsat yo'q")
        return
    
    data = query.data
    if not data.startswith("sub_"):
        return
    
    parts = data.split("_")
    lang_code = parts[1]
    sub_type = parts[2]  # manual yoki auto
    
    url = context.user_data.get('video_url')
    video_title = context.user_data.get('video_title')
    langs = context.user_data.get('langs', {})
    
    if not url or lang_code not in langs:
        await query.edit_message_text("❌ Xatolik yuz berdi")
        return
    
    lang_info = langs[lang_code]
    
    await query.edit_message_text(f"⏳ Yuklanmoqda...")
    
    srt_file = await download_subtitle(url, lang_code, lang_info)
    
    if srt_file and os.path.exists(srt_file):
        save_user_file(user_id, srt_file, video_title, lang_info['name'])
        
        with open(srt_file, 'rb') as f:
            await context.bot.send_document(
                user_id,
                f,
                filename=f"{video_title[:30]}.srt",
                caption=f"✅ {lang_info['name']}"
            )
        
        keyboard = [
            [InlineKeyboardButton("🧠 O'zbek tiliga tarjima qilish", callback_data="translate_srt")],
            [InlineKeyboardButton("🔙 Bosh menyu", callback_data="back_to_start")]
        ]
        await context.bot.send_message(
            user_id,
            "✅ *Fayl tayyor!*\n\nEndi O'zbek tiliga tarjima qilish uchun tugmani bosing:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        await query.delete_message()
    else:
        await query.edit_message_text(
            "❌ Yuklab olishda xatolik.\n"
            "Boshqa subtitrni tanlab ko'ring."
        )

# ==================== SRT FAYL ====================
async def handle_srt_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('state') != WAITING_FOR_SRT:
        return
    
    user_id = update.effective_user.id
    
    has_perm, _ = check_permission(user_id)
    if not has_perm and user_id != ADMIN_ID:
        await update.message.reply_text("❌ Ruxsat yo'q")
        return
    
    document = update.message.document
    
    if not document.file_name.endswith('.srt'):
        await update.message.reply_text("❌ Faqat .srt fayl yuboring")
        return
    
    file = await context.bot.get_file(document.file_id)
    
    with tempfile.NamedTemporaryFile(suffix='.srt', delete=False) as tmp:
        temp_filename = tmp.name
    
    await file.download_to_drive(temp_filename)
    
    save_user_file(user_id, temp_filename, document.file_name, "Yuklangan")
    
    keyboard = [
        [InlineKeyboardButton("🧠 O'zbek tiliga tarjima qilish", callback_data="translate_srt")],
        [InlineKeyboardButton("🔙 Bosh menyu", callback_data="back_to_start")]
    ]
    
    await update.message.reply_text(
        f"✅ *{document.file_name} qabul qilindi!*\n\n"
        f"Endi O'zbek tiliga tarjima qilish uchun tugmani bosing:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    context.user_data['state'] = None

# ==================== TARJIMA ====================
async def translate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    has_perm, _ = check_permission(user_id)
    if not has_perm and user_id != ADMIN_ID:
        await query.edit_message_text("❌ Ruxsat yo'q")
        return
    
    srt_file, video_title, original_lang = get_user_file(user_id)
    
    if not srt_file or not os.path.exists(srt_file):
        await query.edit_message_text("❌ Fayl topilmadi. Avval subtitr yuklang.")
        return
    
    await query.edit_message_text("⏳ Tarjima boshlanmoqda...")
    
    translated_file = await translate_srt_file(update, context, srt_file, video_title)
    
    if translated_file and os.path.exists(translated_file):
        with open(translated_file, 'rb') as f:
            await context.bot.send_document(
                user_id,
                f,
                filename=f"ozbekcha_{os.path.basename(srt_file)}",
                caption="✅ *Tarjima tayyor!* (O'zbek tilida)",
                parse_mode='Markdown'
            )
        
        # Bosh menyuga qaytish
        if user_id == ADMIN_ID:
            keyboard = [
                [InlineKeyboardButton("🎬 YouTubedan srt olish va tarjima", callback_data="main_youtube")],
                [InlineKeyboardButton("📄 SRT faylni tarjima qilish", callback_data="main_srt")],
                [InlineKeyboardButton("👑 Admin panel", callback_data="admin_menu")]
            ]
        else:
            keyboard = [
                [InlineKeyboardButton("🎬 YouTubedan srt olish va tarjima", callback_data="main_youtube")],
                [InlineKeyboardButton("📄 SRT faylni tarjima qilish", callback_data="main_srt")]
            ]
        
        await context.bot.send_message(
            user_id,
            "✨ *Yana nima qilamiz?*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        # Fayllarni o'chirish
        try:
            os.remove(translated_file)
            os.remove(srt_file)
        except:
            pass
    else:
        await query.edit_message_text("❌ Tarjima qilishda xatolik yuz berdi.")

# ==================== XABAR HANDLER ====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await handle_admin_message(update, context):
        return
    
    if await handle_youtube_url(update, context):
        return
    
    if context.user_data.get('state') is None:
        await update.message.reply_text("❌ Iltimos, /start ni bosing.")

# ==================== MAIN ====================
def main():
    try:
        print("⏳ Bot ishga tushmoqda...")
        
        init_db()
        
        app = Application.builder().token(BOT_TOKEN).build()
        
        # Command handler
        app.add_handler(CommandHandler("start", start))
        
        # Callback handlers
        app.add_handler(CallbackQueryHandler(admin_menu_callback, pattern="^admin_menu$"))
        app.add_handler(CallbackQueryHandler(admin_add_callback, pattern="^admin_add$"))
        app.add_handler(CallbackQueryHandler(admin_list_callback, pattern="^admin_list$"))
        app.add_handler(CallbackQueryHandler(remove_user_callback, pattern="^remove_"))
        app.add_handler(CallbackQueryHandler(back_to_start_callback, pattern="^back_to_start$"))
        app.add_handler(CallbackQueryHandler(days_callback, pattern="^days_"))
        app.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_"))
        app.add_handler(CallbackQueryHandler(subtitle_callback, pattern="^sub_"))
        app.add_handler(CallbackQueryHandler(translate_callback, pattern="^translate_"))
        
        # Message handlers
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(MessageHandler(filters.Document.ALL, handle_srt_file))
        
        print("✅ Bot ishga tushdi!")
        print(f"👑 Admin ID: {ADMIN_ID}")
        print(f"📌 Manual: HAMMA tillar")
        print(f"📌 Auto: O'zbek, Ingliz, Xitoy")
        print(f"🧩 Tarjima: HAR DOIM O'zbek tiliga")
        
        app.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"Xatolik: {e}")
        print(f"❌ Xatolik: {e}")
        time.sleep(5)
        main()

if __name__ == "__main__":
    main()
