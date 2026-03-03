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
# TOKENLAR TO'G'RIDAN-TO'G'RI YOZILDI
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
        logger.info("✅ Baza muvaffaqiyatli yaratildi")
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
        'bn': 'Bengal tili', 'pl': 'Polyak tili', 'uk': 'Ukrain tili', 'ro': 'Rumin tili',
        'nl': 'Golland tili', 'el': 'Grek tili', 'hu': 'Venger tili', 'sv': 'Shved tili',
        'cs': 'Chex tili', 'fi': 'Fin tili', 'da': 'Daniya tili', 'he': 'Ibroniycha',
        'no': 'Norveg tili', 'sk': 'Slovak tili', 'hr': 'Xorvat tili', 'sr': 'Serb tili',
        'bg': 'Bolg\'ar tili', 'lt': 'Litva tili', 'lv': 'Latish tili', 'et': 'Eston tili',
    }
    return languages.get(lang_code, lang_code.upper())

# ==================== DEEPSEEK TARJIMA ====================
async def translate_with_deepseek(text: str, target_lang: str = "uzbek") -> Optional[str]:
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
                "content": f"Sen professional tarjimonsan. Matnni {target_lang} tiliga tarjima qil. Faqat tarjima qilingan matnni qaytar, hech qanday izohsiz."
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
                else:
                    error_text = await resp.text()
                    logger.error(f"Tarjima xatolik: {resp.status} - {error_text}")
                    return None
    except Exception as e:
        logger.error(f"Tarjima exception: {e}")
        return None

async def translate_with_progress(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                  srt_file: str, video_title: str) -> Tuple[Optional[str], Optional[Update]]:
    """Progress bar bilan tarjima qilish (10 sekundda yangilanadi)"""
    
    user_id = update.effective_user.id
    
    # Progress xabar yuborish
    progress_msg = await context.bot.send_message(
        chat_id=user_id,
        text="🧠 *Tarjima boshlandi*\n\n"
             "`[□□□□□□□□□□]` 0%",
        parse_mode='Markdown'
    )
    
    try:
        subs = pysrt.open(srt_file)
        total = len(subs)
        translated_subs = []
        
        # Vaqtni hisoblash
        start_time = time.time()
        last_update = time.time()
        
        for i, sub in enumerate(subs):
            # Tarjima qilish
            translated_text = await translate_with_deepseek(sub.text, "uzbek")
            
            if translated_text:
                sub.text = translated_text
            else:
                sub.text = f"[?] {sub.text}"
            
            translated_subs.append(sub)
            
            # HAR 10 SEKUNDDA PROGRESSNI YANGILASH
            current_time = time.time()
            if current_time - last_update >= 10 or i == total - 1:
                percent = int((i + 1) / total * 100)
                elapsed = int(current_time - start_time)
                
                # Qolgan vaqtni hisoblash
                if i > 0:
                    avg_time_per_item = elapsed / (i + 1)
                    remaining_items = total - (i + 1)
                    remaining_seconds = int(avg_time_per_item * remaining_items)
                    remaining_min = remaining_seconds // 60
                    remaining_sec = remaining_seconds % 60
                    time_text = f"{remaining_min}m {remaining_sec}s"
                else:
                    time_text = "hisoblanmoqda..."
                
                # Chiroyli progress bar
                filled = percent // 10
                empty = 10 - filled
                progress_bar = f"[{'█' * filled}{'□' * empty}]"
                
                try:
                    await progress_msg.edit_text(
                        f"🧠 *Tarjima qilinmoqda...*\n\n"
                        f"{progress_bar} {percent}%\n"
                        f"⏱️ Qolgan vaqt: ~{time_text}\n"
                        f"📊 Qator: {i+1}/{total}\n"
                        f"🔄 Yangilanadi: har 10 sekundda",
                        parse_mode='Markdown'
                    )
                    last_update = current_time
                except Exception as e:
                    logger.error(f"Progress yangilash xatolik: {e}")
            
            # API limiti uchun kutish
            if (i + 1) % 5 == 0:
                await asyncio.sleep(1)
        
        # Tugaganini bildirish
        await progress_msg.edit_text("✅ *Tarjima tugadi! Fayl tayyorlanmoqda...*", parse_mode='Markdown')
        
        # Faylni saqlash
        output_path = srt_file.replace('.srt', f'_uz.srt')
        new_subs = pysrt.SubRipFile()
        for sub in translated_subs:
            new_subs.append(sub)
        new_subs.save(output_path, encoding='utf-8')
        
        return output_path, progress_msg
        
    except Exception as e:
        logger.error(f"Tarjima jarayonida xatolik: {e}")
        await progress_msg.edit_text("❌ Tarjima qilishda xatolik yuz berdi!")
        return None, progress_msg

# ==================== SUBTITR FORMATLARINI O'GIRISH ====================
def vtt_to_srt(vtt_content: str) -> str:
    """VTT formatini SRT ga o'girish"""
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
    """ASS/SSA formatini SRT ga o'girish"""
    
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
                text = text.replace('\\N', '\n')
                text = text.replace('\\n', '\n')
                text = re.sub(r'<[^>]+>', '', text)
                
                srt_lines.append(str(counter))
                counter += 1
                srt_lines.append(f"{start} --> {end}")
                srt_lines.append(text.strip())
                srt_lines.append('')
    
    return '\n'.join(srt_lines)

def sbv_to_srt(sbv_content: str) -> str:
    """SBV (YouTube) formatini SRT ga o'girish"""
    
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
    """Turli formatdagi subtitrni SRT ga o'girish"""
    
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
                logger.error(f"Format o'girib bo'lmadi: {input_format}")
                return None
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(srt_content)
        
        return output_file
        
    except Exception as e:
        logger.error(f"Konvertatsiya xatolik: {e}")
        return None

# ==================== YOUTUBE SUBTITR OLISH ====================
async def get_youtube_subtitles(url: str) -> Tuple[Optional[str], dict, Optional[dict]]:
    """YouTube dan subtitr olish"""
    
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
            logger.info(f"YouTube ma'lumot olinmoqda: {url}")
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'Noma\'lum video')
            
            subtitles = info.get('subtitles', {})
            automatic_captions = info.get('automatic_captions', {})
            
            available_langs = {}
            
            for lang, sub_data in subtitles.items():
                if sub_data:
                    formats = []
                    for sub in sub_data:
                        ext = sub.get('ext', 'unknown')
                        if ext not in formats:
                            formats.append(ext)
                    
                    lang_name = get_language_name(lang)
                    available_langs[lang] = {
                        'name': lang_name, 
                        'type': 'manual',
                        'data': sub_data,
                        'formats': formats
                    }
            
            for lang, sub_data in automatic_captions.items():
                if sub_data and lang not in available_langs:
                    formats = []
                    for sub in sub_data:
                        ext = sub.get('ext', 'unknown')
                        if ext not in formats:
                            formats.append(ext)
                    
                    lang_name = get_language_name(lang)
                    available_langs[lang] = {
                        'name': lang_name + ' (auto)', 
                        'type': 'auto',
                        'data': sub_data,
                        'formats': formats
                    }
            
            return video_title, available_langs, info
            
    except Exception as e:
        logger.error(f"YouTube xatolik: {e}")
        return None, {}, None

async def download_subtitle(url: str, lang_code: str, lang_info: dict) -> Optional[str]:
    """Subtitrni yuklab olish va SRT ga o'girish"""
    
    with tempfile.NamedTemporaryFile(suffix='.srt', delete=False) as tmp_file:
        temp_filename = tmp_file.name
    
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
        possible_files = []
        
        for ext in ['srt', 'vtt', 'ass', 'ssa', 'sbv', 'sub', 'dfxp', 'ttml']:
            file_path = f"{base_name}.{lang_code}.{ext}"
            if os.path.exists(file_path):
                possible_files.append((file_path, ext))
            
            file_path2 = f"{base_name}.{ext}"
            if os.path.exists(file_path2):
                possible_files.append((file_path2, ext))
        
        if not possible_files:
            logger.error(f"Hech qanday subtitr fayli topilmadi: {base_name}")
            return None
        
        downloaded_file, file_ext = possible_files[0]
        logger.info(f"Subtitr topildi: {downloaded_file} ({file_ext})")
        
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
    """START KOMANDASI"""
    try:
        user_id = update.effective_user.id
        username = update.effective_user.username or "noma'lum"
        first_name = update.effective_user.first_name or ""
        last_name = update.effective_user.last_name or ""
        
        logger.info(f"🔥 START: {user_id} (@{username})")
        
        # Adminmi tekshirish
        if user_id == ADMIN_ID:
            keyboard = [
                [InlineKeyboardButton("👤 Ruxsat berish", callback_data="admin_menu")],
                [InlineKeyboardButton("📋 Ruxsatlarni boshqarish", callback_data="admin_manage")],
                [InlineKeyboardButton("🎬 Botdan foydalanish", callback_data="user_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "👑 *Admin panel*\n\nNima qilmoqchisiz?",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return
        
        # Ruxsatni tekshirish
        has_perm, expires = check_permission(user_id)
        
        if has_perm:
            keyboard = [
                [InlineKeyboardButton("🎬 YouTube video", callback_data="main_youtube")],
                [InlineKeyboardButton("📄 SRT fayl yuborish", callback_data="main_srt")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            days_left = (expires - datetime.datetime.now()).days
            await update.message.reply_text(
                f"✅ *Xush kelibsiz!*\n\n"
                f"🕒 Ruxsatingiz: {days_left} kun qoldi\n\n"
                f"Tanlang:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            # To'g'irlangan xabar
            await update.message.reply_text(
                f"❌ *Ruxsat yo'q*\n\n"
                f"Botdan foydalanish uchun @maestro_o ga murojaat qiling. "
                f"Rozi bo'lsa, quyidagi ID raqamingizni yuboring. "
                f"Admin sizning ID raqamingiz orqali ruxsat beradi.\n\n"
                f"🆔 *ID raqamingiz:* `{user_id}`",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Start xatolik: {e}")
        await update.message.reply_text("⚠️ Xatolik yuz berdi. Admin @maestro_o ga murojaat qiling.")

# ==================== ADMIN MENYU ====================
async def admin_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await query.edit_message_text("❌ Bu faqat admin uchun!")
        return
    
    await query.edit_message_text(
        "👤 *Ruxsat berish*\n\n"
        "Foydalanuvchi ID raqamini yuboring:",
        parse_mode='Markdown'
    )
    context.user_data['admin_action'] = 'waiting_for_add_id'

async def admin_manage_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await query.edit_message_text("❌ Bu faqat admin uchun!")
        return
    
    users = get_all_users()
    
    if not users:
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📋 *Ruxsatlar ro'yxati*\n\n"
            "Hech kimga ruxsat berilmagan.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    text = "📋 *Ruxsat berilgan foydalanuvchilar:*\n\n"
    keyboard = []
    
    for uid, uname, fname, lname, expires in users:
        days_left = (datetime.datetime.fromisoformat(expires) - datetime.datetime.now()).days
        
        # Ism familya ham ko'rinadi
        full_name = f"{fname} {lname}".strip() or "Ismsiz"
        display_name = f"{full_name} (@{uname})" if uname != "noma'lum" else full_name
        
        text += f"🆔 {uid} | {display_name} | {days_left} kun qoldi\n"
        
        # Profilga o'tish tugmasi
        keyboard.append([
            InlineKeyboardButton(
                f"👤 {full_name[:15]} - Profil", 
                url=f"tg://user?id={uid}"
            )
        ])
        keyboard.append([
            InlineKeyboardButton(
                f"❌ Ruxsatni bekor qilish", 
                callback_data=f"remove_{uid}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def remove_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await query.edit_message_text("❌ Bu faqat admin uchun!")
        return
    
    data = query.data
    target_id = int(data.replace("remove_", ""))
    
    if remove_permission(target_id):
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="❌ *Ruxsatingiz bekor qilindi!*\n\n"
                     "Admin sizning ruxsatingizni olib tashladi. "
                     "Qayta ruxsat olish uchun @maestro_o ga murojaat qiling.",
                parse_mode='Markdown'
            )
            user_notified = "Xabar yuborildi ✅"
        except:
            user_notified = "Xabar yuborilmadi ⚠️"
    else:
        user_notified = "Ruxsat o'chirilmadi ⚠️"
    
    users = get_all_users()
    
    if not users:
        keyboard = [[InlineKeyboardButton("🔙 Admin panel", callback_data="back_to_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ *Ruxsat bekor qilindi!*\n\n"
            f"🆔 ID: {target_id}\n"
            f"📨 {user_notified}\n\n"
            f"Endi hech kimga ruxsat berilmagan.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    text = "📋 *Ruxsat berilgan foydalanuvchilar:*\n\n"
    keyboard = []
    
    for uid, uname, fname, lname, expires in users:
        days_left = (datetime.datetime.fromisoformat(expires) - datetime.datetime.now()).days
        full_name = f"{fname} {lname}".strip() or "Ismsiz"
        text += f"🆔 {uid} | {full_name} (@{uname}) | {days_left} kun qoldi\n"
        
        keyboard.append([
            InlineKeyboardButton(
                f"👤 {full_name[:15]} - Profil", 
                url=f"tg://user?id={uid}"
            )
        ])
        keyboard.append([
            InlineKeyboardButton(
                f"❌ Ruxsatni bekor qilish", 
                callback_data=f"remove_{uid}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"✅ *Ruxsat bekor qilindi!*\n\n"
        f"🆔 ID: {target_id}\n"
        f"📨 {user_notified}\n\n"
        f"{text}",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ==================== ADMIN XABARLAR ====================
async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Admin xabarlarini qayta ishlash"""
    user_id = update.effective_user.id
    text = update.message.text
    
    if user_id != ADMIN_ID:
        return False
    
    action = context.user_data.get('admin_action')
    
    if action == 'waiting_for_add_id':
        try:
            target_id = int(text.strip())
            
            # Foydalanuvchi ma'lumotlarini olishga urinish
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
                 InlineKeyboardButton("1 hafta", callback_data="days_7")],
                [InlineKeyboardButton("10 kun", callback_data="days_10"),
                 InlineKeyboardButton("20 kun", callback_data="days_20")],
                [InlineKeyboardButton("30 kun", callback_data="days_30")],
                [InlineKeyboardButton("🔙 Bekor qilish", callback_data="back_to_admin")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            full_name = f"{first_name} {last_name}".strip() or "Noma'lum"
            await update.message.reply_text(
                f"🆔 ID: {target_id}\n"
                f"👤 Ism: {full_name}\n"
                f"📱 Username: @{username}\n\n"
                f"Qancha kun ruxsat beramiz?",
                reply_markup=reply_markup
            )
            return True
            
        except ValueError:
            await update.message.reply_text("❌ Noto'g'ri ID. Qaytadan urinib ko'ring.")
            return True
    
    return False

# ==================== KUN TANLASH ====================
async def days_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await query.edit_message_text("❌ Bu faqat admin uchun!")
        return
    
    data = query.data
    target_id = context.user_data.get('target_id')
    target_username = context.user_data.get('target_username', 'user')
    target_first_name = context.user_data.get('target_first_name', '')
    target_last_name = context.user_data.get('target_last_name', '')
    
    if not target_id:
        await query.edit_message_text("❌ Xatolik yuz berdi. Qaytadan boshlang.")
        return
    
    days_map = {
        'days_3': 3,
        'days_7': 7,
        'days_10': 10,
        'days_20': 20,
        'days_30': 30
    }
    
    if data in days_map:
        days = days_map[data]
        
        if add_permission(target_id, target_username, target_first_name, target_last_name, days):
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=f"✅ *Ruxsat berildi!*\n\n"
                         f"Sizga {days} kun muddat bilan botdan foydalanish ruxsati berildi.\n"
                         f"/start ni bosing va ishlatishni boshlang.",
                    parse_mode='Markdown'
                )
                user_notified = "Xabar yuborildi ✅"
            except Exception as e:
                user_notified = "Xabar yuborilmadi (foydalanuvchi botni blocklagan) ⚠️"
                logger.error(f"Xabar yuborilmadi {target_id}: {e}")
        else:
            user_notified = "Ruxsat berilmadi ⚠️"
        
        keyboard = [[InlineKeyboardButton("🔙 Admin panel", callback_data="back_to_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        full_name = f"{target_first_name} {target_last_name}".strip() or "Foydalanuvchi"
        
        await query.edit_message_text(
            f"✅ *Ruxsat berildi!*\n\n"
            f"🆔 ID: {target_id}\n"
            f"👤 Ism: {full_name}\n"
            f"📅 Muddat: {days} kun\n"
            f"📨 {user_notified}\n\n"
            f"Foydalanuvchi endi botdan foydalana oladi.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        context.user_data['admin_action'] = None
        context.user_data['target_id'] = None

# ==================== USER MENYU ====================
async def user_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await query.edit_message_text("❌ Bu faqat admin uchun!")
        return
    
    keyboard = [
        [InlineKeyboardButton("🎬 YouTube video", callback_data="main_youtube")],
        [InlineKeyboardButton("📄 SRT fayl yuborish", callback_data="main_srt")],
        [InlineKeyboardButton("🔙 Admin panel", callback_data="back_to_admin")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🎬 *Botdan foydalanish*\n\n"
        "Tanlang:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ==================== BACK TO ADMIN ====================
async def back_to_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await query.edit_message_text("❌ Bu faqat admin uchun!")
        return
    
    keyboard = [
        [InlineKeyboardButton("👤 Ruxsat berish", callback_data="admin_menu")],
        [InlineKeyboardButton("📋 Ruxsatlarni boshqarish", callback_data="admin_manage")],
        [InlineKeyboardButton("🎬 Botdan foydalanish", callback_data="user_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "👑 *Admin panel*\n\nNima qilmoqchisiz?",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ==================== ASOSIY MENYU ====================
async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Ruxsatni tekshirish
    has_perm, expires = check_permission(user_id)
    if not has_perm and user_id != ADMIN_ID:
        await query.edit_message_text("❌ Ruxsat yo'q!")
        return
    
    data = query.data
    
    if data == "main_youtube":
        # Orqaga qaytish tugmasi
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🎬 *YouTube video*\n\n"
            "Video havolasini yuboring:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        context.user_data['state'] = WAITING_FOR_YOUTUBE
        
    elif data == "main_srt":
        # Orqaga qaytish tugmasi
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📄 *SRT fayl*\n\n"
            "SRT faylni yuboring:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        context.user_data['state'] = WAITING_FOR_SRT

# ==================== ORQAGA QAYTISH ====================
async def back_to_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    context.user_data['state'] = None
    
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
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if user_id != ADMIN_ID:
        has_perm, expires = check_permission(user_id)
        days_left = (expires - datetime.datetime.now()).days if has_perm else 0
        text = f"✅ *Xush kelibsiz!*\n\n🕒 Ruxsatingiz: {days_left} kun qoldi\n\nTanlang:"
    else:
        text = "Tanlang:"
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ==================== YOUTUBE HAVOLA ====================
async def handle_youtube_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """YouTube havolani qayta ishlash"""
    user_id = update.effective_user.id
    
    if context.user_data.get('state') != WAITING_FOR_YOUTUBE:
        return False
    
    url = update.message.text
    
    has_perm, expires = check_permission(user_id)
    if not has_perm and user_id != ADMIN_ID:
        await update.message.reply_text("❌ Ruxsat yo'q!")
        return True
    
    # YouTube havola ekanligini tekshirish
    youtube_patterns = [
        r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/',
        r'(https?://)?(www\.)?(m\.)?youtube\.com/',
        r'(https?://)?youtu\.be/'
    ]
    
    is_youtube = False
    for pattern in youtube_patterns:
        if re.search(pattern, url):
            is_youtube = True
            break
    
    if not is_youtube:
        await update.message.reply_text("❌ Iltimos, YouTube havolasini yuboring!")
        return True
    
    progress_msg = await update.message.reply_text("⏳ Video tekshirilmoqda...")
    
    video_title, available_langs, info = await get_youtube_subtitles(url)
    
    if not available_langs:
        # Orqaga qaytish tugmasi
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await progress_msg.edit_text(
            "😕 *Subtitr topilmadi!*\n\n"
            "Boshqa drama/video yuboring, buning subtitr fayli yo'q.\n\n"
            "💡 Agar muammo davom etsa, admin @maestro_o ga murojaat qiling.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        context.user_data['state'] = None
        return True
    
    keyboard = []
    
    for lang_code, lang_info in available_langs.items():
        formats_text = f" [{', '.join(lang_info['formats'])}]" if lang_info['formats'] else ""
        
        if lang_info['type'] == 'manual':
            button_text = f"📝 {lang_info['name']}{formats_text}"
        else:
            button_text = f"🤖 {lang_info['name']}{formats_text}"
        
        button = InlineKeyboardButton(
            button_text,
            callback_data=f"sub_{lang_code}"
        )
        keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton("🔙 Asosiy menyu", callback_data="back_to_main")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    context.user_data['video_url'] = url
    context.user_data['video_title'] = video_title
    context.user_data['langs'] = available_langs
    
    await progress_msg.edit_text(
        f"📹 *{video_title[:50]}*\n\n"
        f"🎯 {len(available_langs)} ta subtitr topildi.\n\n"
        f"Tanlang:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    context.user_data['state'] = None
    return True

# ==================== SUBTITR YUKLASH ====================
async def subtitle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    has_perm, expires = check_permission(user_id)
    if not has_perm and user_id != ADMIN_ID:
        await query.edit_message_text("❌ Ruxsat yo'q!")
        return
    
    if data.startswith("sub_"):
        lang_code = data.replace("sub_", "")
        
        url = context.user_data.get('video_url')
        video_title = context.user_data.get('video_title')
        langs = context.user_data.get('langs', {})
        
        if not url or lang_code not in langs:
            await query.edit_message_text("❌ Xatolik yuz berdi. Qaytadan boshlang.")
            return
        
        lang_info = langs[lang_code]
        
        await query.edit_message_text(
            f"⏳ {lang_info['name']} yuklanmoqda...",
            parse_mode='Markdown'
        )
        
        srt_file = await download_subtitle(url, lang_code, lang_info)
        
        if srt_file and os.path.exists(srt_file):
            save_user_file(user_id, srt_file, video_title, lang_info['name'])
            
            with open(srt_file, 'rb') as f:
                await context.bot.send_document(
                    chat_id=user_id,
                    document=f,
                    filename=f"{video_title[:30]}_{lang_code}.srt",
                    caption=f"📥 *{video_title[:50]}*\n"
                            f"🌐 Til: {lang_info['name']}"
                )
            
            keyboard = [
                [InlineKeyboardButton("🧠 AI tarjima (O'zbek)", callback_data="translate_srt")],
                [InlineKeyboardButton("🔙 Asosiy menyu", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ *Subtitr tayyor!*\n\n"
                     "🧠 Sun'iy intellekt orqali O'zbek tiliga tarjima qilish uchun tugmani bosing:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            await query.delete_message()
            
        else:
            keyboard = [[InlineKeyboardButton("🔙 Asosiy menyu", callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"❌ Subtitr yuklab olishda xatolik yuz berdi.\n"
                f"Boshqa tilni tanlab ko'ring yoki keyinroq urinib ko'ring.",
                reply_markup=reply_markup
            )

# ==================== SRT FAYLNI QAYTA ISHLASH ====================
async def handle_srt_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """SRT faylni qayta ishlash"""
    user_id = update.effective_user.id
    
    if context.user_data.get('state') != WAITING_FOR_SRT:
        return
    
    has_perm, expires = check_permission(user_id)
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
    
    save_user_file(user_id, temp_filename, document.file_name, "Yuklangan fayl")
    
    keyboard = [
        [InlineKeyboardButton("🧠 AI tarjima (O'zbek)", callback_data="translate_srt")],
        [InlineKeyboardButton("🔙 Asosiy menyu", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ *{document.file_name} qabul qilindi!*\n\n"
        f"🧠 Sun'iy intellekt orqali O'zbek tiliga tarjima qilish uchun tugmani bosing:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    context.user_data['state'] = None

# ==================== TARJIMA QILISH ====================
async def translate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    has_perm, expires = check_permission(user_id)
    if not has_perm and user_id != ADMIN_ID:
        await query.edit_message_text("❌ Ruxsat yo'q!")
        return
    
    if data == "translate_srt":
        srt_file, video_title, original_lang = get_user_file(user_id)
        
        if not srt_file or not os.path.exists(srt_file):
            await query.edit_message_text("❌ Fayl topilmadi. Avval subtitr yuklang!")
            return
        
        # Progress bar bilan tarjima qilish
        translated_file, progress_msg = await translate_with_progress(
            update, context, srt_file, video_title
        )
        
        if translated_file and os.path.exists(translated_file):
            with open(translated_file, 'rb') as f:
                await context.bot.send_document(
                    chat_id=user_id,
                    document=f,
                    filename=f"ozbekcha_{os.path.basename(srt_file)}",
                    caption=f"✅ *Tarjima tayyor!*\n\n"
                            f"🧠 Sun'iy intellekt yordamida O'zbek tiliga sifatli tarjima qilindi.\n"
                            f"📁 Asl fayl: {video_title}\n"
                            f"⏱️ Vaqt kodlari o'zgarmadi!",
                    parse_mode='Markdown'
                )
            
            # Progress xabarni o'chirish
            await progress_msg.delete()
            
            # Fayl yuborilgandan keyin menyu chiqarish
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
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=user_id,
                text="✨ Yana nima qilamiz?",
                reply_markup=reply_markup
            )
            
            # Fayllarni o'chirish
            try:
                os.remove(translated_file)
                os.remove(srt_file)
            except:
                pass
            
        else:
            keyboard = [[InlineKeyboardButton("🔙 Asosiy menyu", callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "❌ Tarjima qilishda xatolik yuz berdi.",
                reply_markup=reply_markup
            )

# ==================== ASOSIY XABAR HANDLER ====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Barcha xabarlarni qabul qilish"""
    
    # Admin xabarlarini tekshirish
    if await handle_admin_message(update, context):
        return
    
    # YouTube havola tekshirish
    if await handle_youtube_url(update, context):
        return
    
    # Agar state bo'lmasa
    if context.user_data.get('state') is None:
        await update.message.reply_text(
            "❌ Noto'g'ri buyruq. Iltimos, /start ni bosing."
        )

# ==================== ASOSIY FUNKSIYA ====================
def main():
    """Botni ishga tushirish"""
    
    try:
        print("⏳ Eski botlarni tozalash...")
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        requests.get(url, params={"offset": -1, "timeout": 1})
        time.sleep(2)
        
        # Bazani yaratish
        init_db()
        
        # Botni yaratish
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Handlerlar
        application.add_handler(CommandHandler("start", start))
        
        # Callback handlerlar
        application.add_handler(CallbackQueryHandler(admin_menu_callback, pattern="^admin_menu$"))
        application.add_handler(CallbackQueryHandler(admin_manage_callback, pattern="^admin_manage$"))
        application.add_handler(CallbackQueryHandler(remove_user_callback, pattern="^remove_"))
        application.add_handler(CallbackQueryHandler(user_menu_callback, pattern="^user_menu$"))
        application.add_handler(CallbackQueryHandler(back_to_admin_callback, pattern="^back_to_admin$"))
        application.add_handler(CallbackQueryHandler(back_to_main_callback, pattern="^back_to_main$"))
        application.add_handler(CallbackQueryHandler(days_callback, pattern="^days_"))
        application.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_"))
        application.add_handler(CallbackQueryHandler(subtitle_callback, pattern="^sub_"))
        application.add_handler(CallbackQueryHandler(translate_callback, pattern="^translate_"))
        
        # Xabar handlerlar
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(MessageHandler(filters.Document.ALL, handle_srt_file))
        
        print("🚀 Bot ishga tushmoqda...")
        print(f"👑 Admin ID: {ADMIN_ID}")
        print(f"📊 Barcha formatlar qo'llab-quvvatlanadi: SRT, VTT, ASS, SSA, SBV")
        print(f"✅ Progress bar: har 10 sekundda yangilanadi")
        
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            pool_timeout=30
        )
        
    except Exception as e:
        logger.error(f"❌ Main xatolik: {e}")
        print(f"❌ Xatolik: {e}")
        time.sleep(5)
        main()

if __name__ == '__main__':
    main()
