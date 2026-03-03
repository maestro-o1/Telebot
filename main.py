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
import math
from typing import Optional, Tuple, List, Dict, Any
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

# Avtomatik tarjimalarda faqat shu tillarni ko'rsatish
ALLOWED_AUTO_LANGUAGES = ['en', 'uz', 'uz-Cyrl', 'uz-Latn', 'ru', 'zh']

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

def get_language_name(lang_code: str, is_auto: bool = False) -> str:
    """Til kodini nomga o'girish - auto generated ni ajratish"""
    languages = {
        'en': 'Ingliz tili', 'ru': 'Rus tili', 'uz': 'O\'zbek tili', 
        'uz-Cyrl': 'O\'zbek (Kirill)', 'uz-Latn': 'O\'zbek (Lotin)',
        'tr': 'Turk tili',
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
    
    name = languages.get(lang_code, lang_code.upper())
    if is_auto:
        name += " 🤖 (Auto-generated)"
    
    return name

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
                "content": f"Sen professional tarjimonsan. Matnni {target_lang} tiliga tarjima qil. "
                           f"Har bir qatorni '###' bilan ajratilgan holda qaytar. Faqat tarjima qilingan matnni qaytar, hech qanday izohsiz."
            },
            {
                "role": "user",
                "content": text
            }
        ],
        "temperature": 0.3,
        "max_tokens": 8000
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=180) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result['choices'][0]['message']['content'].strip()
                else:
                    error_text = await resp.text()
                    logger.error(f"Tarjima xatolik: {resp.status} - {error_text}")
                    
                    # Qayta urinish - 1 marta
                    if resp.status == 429:  # Rate limit
                        await asyncio.sleep(5)
                        async with session.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=180) as resp2:
                            if resp2.status == 200:
                                result2 = await resp2.json()
                                return result2['choices'][0]['message']['content'].strip()
                    return None
    except asyncio.TimeoutError:
        logger.error("Tarjima timeout")
        return None
    except Exception as e:
        logger.error(f"Tarjima exception: {e}")
        return None

# ==================== OPTIMALLASHTIRILGAN TARJIMA ====================

async def translate_with_progress(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                  srt_file: str, video_title: str) -> Tuple[Optional[str], Optional[Any]]:
    """Progress bar bilan tarjima qilish - VAQT QOLGANINI KO'RSATISH"""
    
    user_id = update.effective_user.id
    
    # Progress xabar yuborish
    keyboard = [[InlineKeyboardButton("❌ To'xtatish", callback_data="cancel_translate")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    progress_msg = await context.bot.send_message(
        chat_id=user_id,
        text="🧠 *Tarjima boshlandi*\n\n"
             "Subtitr yuklanmoqda...",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    context.user_data['cancelled'] = False
    
    try:
        # Subtitrni yuklash
        subs = pysrt.open(srt_file)
        total = len(subs)
        
        if context.user_data.get('cancelled', False):
            await progress_msg.edit_text("⏹️ *Tarjima to'xtatildi*", parse_mode='Markdown')
            return None, progress_msg
        
        await progress_msg.edit_text(
            f"🧠 *Tarjima qilinmoqda...*\n\n"
            f"📊 {total} ta qator birlashtirilmoqda...",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        # HAMMA TEXTNI BIRLASHTIRISH
        separator = "\n###\n"
        full_text = separator.join([sub.text for sub in subs])
        
        # Yuklanayotgan ma'lumot
        text_size = len(full_text)
        estimated_time = math.ceil(text_size / 500)  # 500 belgi = ~1 sekund
        
        await progress_msg.edit_text(
            f"🧠 *DeepSeek tarjima qilmoqda...*\n\n"
            f"📊 {total} ta qator\n"
            f"📝 {text_size} ta belgi\n"
            f"⏳ Taxminan {estimated_time} soniya\n"
            f"🔄 Iltimos kuting...",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        # API ga yuborish
        start_time = time.time()
        translated_full = await translate_with_deepseek(full_text, "uzbek")
        
        if context.user_data.get('cancelled', False):
            await progress_msg.edit_text("⏹️ *Tarjima to'xtatildi*", parse_mode='Markdown')
            return None, progress_msg
        
        if not translated_full:
            await progress_msg.edit_text(
                "❌ *Tarjima xatolik yuz berdi*\n\n"
                "Sabablari:\n"
                "• DeepSeek API vaqtincha ishlamayapti\n"
                "• Juda katta fayl (8000 tokendan oshgan)\n"
                "• Internet aloqasi uzilgan\n\n"
                "Qayta urinib ko'ring.",
                parse_mode='Markdown'
            )
            return None, progress_msg
        
        # QAYTA AJRATISH
        translated_parts = translated_full.split("###")
        translated_parts = [p.strip() for p in translated_parts if p.strip()]
        
        # Agar qatorlar soni mos kelmasa
        if len(translated_parts) != total:
            logger.warning(f"Qatorlar soni mos kelmadi: original={total}, tarjima={len(translated_parts)}")
            
            # Moslashtirish
            if len(translated_parts) > total:
                translated_parts = translated_parts[:total]
            elif len(translated_parts) < total:
                translated_parts.extend([f"[Tarjima qilinmadi: qator {i+1}]" for i in range(len(translated_parts), total)])
        
        # Qatorlarni yangilash
        for i, sub in enumerate(subs):
            if i < len(translated_parts):
                sub.text = translated_parts[i]
        
        # Faylni saqlash
        output_path = srt_file.replace('.srt', f'_uz.srt')
        subs.save(output_path, encoding='utf-8')
        
        total_time = int(time.time() - start_time)
        await progress_msg.edit_text(
            f"✅ *Tarjima tugadi!*\n"
            f"⏱️ {total_time} soniya\n"
            f"📊 {total} ta qator\n"
            f"🚀 1 ta API so'rov",
            parse_mode='Markdown'
        )
        
        return output_path, progress_msg
        
    except Exception as e:
        logger.error(f"Tarjima xatolik: {e}")
        error_msg = str(e)
        if "timed out" in error_msg.lower():
            await progress_msg.edit_text(
                "❌ *Timeout xatolik*\n\n"
                "Server juda sekin javob berdi.\n"
                "Qayta urinib ko'ring.",
                parse_mode='Markdown'
            )
        elif "memory" in error_msg.lower():
            await progress_msg.edit_text(
                "❌ *Xotira xatolik*\n\n"
                "Fayl juda katta. Qisqaroq subtitr tanlang.",
                parse_mode='Markdown'
            )
        else:
            await progress_msg.edit_text(
                f"❌ *Xatolik:*\n`{error_msg[:100]}`",
                parse_mode='Markdown'
            )
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
    """YouTube dan subtitr olish - QO'LDA VA AVTOMATIKNI AJRATISH"""
    
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
            
            # HAMMA QO'LDA YUKLANGANLAR - BULAR ASOSIY
            for lang, sub_data in subtitles.items():
                if sub_data:
                    formats = []
                    for sub in sub_data:
                        ext = sub.get('ext', 'unknown')
                        if ext not in formats:
                            formats.append(ext)
                    
                    # Qo'lda kiritilgan - auto emas
                    lang_name = get_language_name(lang, is_auto=False)
                    available_langs[lang] = {
                        'name': lang_name,
                        'type': 'manual',
                        'formats': formats,
                        'is_auto': False
                    }
            
            # AVTOMATIK - FAQAT QO'LDA YO'Q BO'LSA
            for lang, sub_data in automatic_captions.items():
                if sub_data and lang not in available_langs:
                    # Ruxsat etilgan tillarni tekshirish
                    is_allowed = False
                    for allowed in ALLOWED_AUTO_LANGUAGES:
                        if lang.startswith(allowed.split('-')[0]):
                            is_allowed = True
                            break
                    
                    if is_allowed or lang in ALLOWED_AUTO_LANGUAGES:
                        formats = []
                        for sub in sub_data:
                            ext = sub.get('ext', 'unknown')
                            if ext not in formats:
                                formats.append(ext)
                        
                        # Auto-generated ekanligini belgilash
                        lang_name = get_language_name(lang, is_auto=True)
                        available_langs[lang] = {
                            'name': lang_name,
                            'type': 'auto',
                            'formats': formats,
                            'is_auto': True
                        }
            
            # Tillarni saralash: manual (qo'lda) lar birinchi, keyin auto
            sorted_langs = {}
            # Avval manual
            for lang, info in available_langs.items():
                if not info['is_auto']:
                    sorted_langs[lang] = info
            # Keyin auto
            for lang, info in available_langs.items():
                if info['is_auto']:
                    sorted_langs[lang] = info
            
            return video_title, sorted_langs, info
            
    except Exception as e:
        logger.error(f"YouTube xatolik: {e}")
        return None, {}, None

async def download_subtitle(url: str, lang_code: str, lang_info: dict) -> Optional[str]:
    """Subtitrni yuklab olish"""
    
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
        
        # Faylni qidirish
        for ext in ['srt', 'vtt', 'ass', 'ssa', 'sbv']:
            file_path = f"{base_name}.{lang_code}.{ext}"
            if os.path.exists(file_path):
                if ext != 'srt':
                    return convert_to_srt(file_path, ext)
                return file_path
            
            file_path2 = f"{base_name}.{ext}"
            if os.path.exists(file_path2):
                if ext != 'srt':
                    return convert_to_srt(file_path2, ext)
                return file_path2
        
        return None
        
    except Exception as e:
        logger.error(f"Subtitr yuklash xatolik: {e}")
        return None

# ==================== START KOMANDASI ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """START KOMANDASI - ADMIN PANEL"""
    try:
        user_id = update.effective_user.id
        username = update.effective_user.username or "noma'lum"
        
        logger.info(f"🔥 START: {user_id}")
        
        # STATE ni tozalash
        context.user_data.clear()
        
        # Adminmi tekshirish
        if user_id == ADMIN_ID:
            keyboard = [
                [InlineKeyboardButton("👤 Ruxsat berish", callback_data="admin_menu")],
                [InlineKeyboardButton("📋 Ruxsatlarni boshqarish", callback_data="admin_manage")],
                [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
                [InlineKeyboardButton("🎬 Botdan foydalanish", callback_data="user_menu")]
            ]
            await update.message.reply_text(
                "👑 *Admin Panel*\n\n"
                "🏠 Asosiy menyu:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            return
        
        # Oddiy foydalanuvchi
        has_perm, expires = check_permission(user_id)
        
        if has_perm:
            keyboard = [
                [InlineKeyboardButton("🎬 YouTube video", callback_data="main_youtube")],
                [InlineKeyboardButton("📄 SRT fayl", callback_data="main_srt")]
            ]
            days_left = (expires - datetime.datetime.now()).days
            await update.message.reply_text(
                f"✅ *Xush kelibsiz!*\n"
                f"📅 {days_left} kun qoldi\n\n"
                f"Tanlang:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"❌ *Ruxsat yo'q*\n\n"
                f"Botdan foydalanish uchun @maestro_o ga murojaat qiling.\n"
                f"ID raqamingiz: `{user_id}`",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Start xatolik: {e}")
        await update.message.reply_text("⚠️ Xatolik. Admin @maestro_o ga murojaat qiling.")

# ==================== STATISTIKA ====================

async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin uchun statistika"""
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        await query.edit_message_text("❌ Admin uchun")
        return
    
    users = get_all_users()
    
    # Faol foydalanuvchilar
    active_users = 0
    for uid, uname, fname, lname, expires in users:
        try:
            if datetime.datetime.fromisoformat(expires) > datetime.datetime.now():
                active_users += 1
        except:
            pass
    
    text = (
        f"📊 *Statistika*\n\n"
        f"👥 Jami foydalanuvchilar: {len(users)}\n"
        f"✅ Faol: {active_users}\n"
        f"❌ Muddati o'tgan: {len(users) - active_users}\n\n"
        f"🤖 Bot holati: ✅ Ishlayapti\n"
        f"🔄 Tarjima: Optimallashtirilgan"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]]
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

# ==================== TARJIMANI TO'XTATISH ====================

async def cancel_translate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['cancelled'] = True
    await query.edit_message_text("⏹️ To'xtatildi")

# ==================== ADMIN MENYU ====================

async def admin_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        await query.edit_message_text("❌ Admin uchun")
        return
    
    await query.edit_message_text("👤 Foydalanuvchi ID raqamini yuboring:")
    context.user_data['admin_action'] = 'waiting_for_add_id'

async def admin_manage_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        await query.edit_message_text("❌ Admin uchun")
        return
    
    users = get_all_users()
    
    if not users:
        await query.edit_message_text(
            "📋 Hech kimga ruxsat berilmagan",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]])
        )
        return
    
    text = "📋 *Foydalanuvchilar:*\n\n"
    keyboard = []
    
    for uid, uname, fname, lname, expires in users:
        try:
            expires_date = datetime.datetime.fromisoformat(expires)
            days_left = (expires_date - datetime.datetime.now()).days
            status = "✅" if days_left > 0 else "❌"
        except:
            days_left = 0
            status = "❌"
        
        name = f"{fname} {lname}".strip() or "Ismsiz"
        text += f"{status} {uid} | {name} | {days_left} kun\n"
        
        keyboard.append([InlineKeyboardButton(f"👤 {name}", url=f"tg://user?id={uid}")])
        keyboard.append([InlineKeyboardButton(f"❌ Bekor qilish", callback_data=f"remove_{uid}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")])
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def remove_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    target_id = int(query.data.replace("remove_", ""))
    
    if remove_permission(target_id):
        try:
            await context.bot.send_message(target_id, "❌ Ruxsatingiz bekor qilindi")
        except:
            pass
        
        await query.edit_message_text("✅ Bekor qilindi")
        await admin_manage_callback(update, context)

# ==================== ADMIN XABARLAR ====================

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
                [InlineKeyboardButton("🔙 Bekor qilish", callback_data="back_to_admin")]
            ]
            
            name = f"{first_name} {last_name}".strip()
            await update.message.reply_text(
                f"*ID:* `{target_id}`\n"
                f"*Ism:* {name}\n"
                f"*Username:* @{username}\n\n"
                f"Kun tanlang:",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except ValueError:
            await update.message.reply_text("❌ Noto'g'ri ID. Raqam yuboring.")
        except Exception as e:
            await update.message.reply_text(f"❌ Xatolik: {str(e)[:50]}")
        
        return True
    
    return False

# ==================== KUN TANLASH ====================

async def days_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    data = query.data
    target_id = context.user_data.get('target_id')
    target_username = context.user_data.get('target_username', 'user')
    target_first_name = context.user_data.get('target_first_name', '')
    target_last_name = context.user_data.get('target_last_name', '')
    
    if not target_id:
        await query.edit_message_text("❌ Xatolik: Ma'lumot topilmadi")
        return
    
    days_map = {'days_3': 3, 'days_7': 7, 'days_10': 10, 'days_20': 20, 'days_30': 30}
    
    if data in days_map:
        days = days_map[data]
        
        if add_permission(target_id, target_username, target_first_name, target_last_name, days):
            try:
                await context.bot.send_message(
                    target_id,
                    f"✅ *Ruxsat berildi!*\n\n"
                    f"📅 {days} kun\n"
                    f"👑 Admin: @maestro_o",
                    parse_mode='Markdown'
                )
                msg = f"✅ Ruxsat berildi ({days} kun)"
            except Exception as e:
                msg = f"✅ Ruxsat berildi ({days} kun) - xabar bormadi"
        else:
            msg = "❌ Xatolik: Ruxsat berilmadi"
        
        await query.edit_message_text(msg)
        context.user_data['admin_action'] = None
        context.user_data['target_id'] = None

# ==================== USER MENYU ====================

async def user_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    keyboard = [
        [InlineKeyboardButton("🎬 YouTube", callback_data="main_youtube")],
        [InlineKeyboardButton("📄 SRT fayl", callback_data="main_srt")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")]
    ]
    await query.edit_message_text(
        "🎬 *Botdan foydalanish*\n\n"
        "Tanlang:",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ==================== BACK TO ADMIN ====================

async def back_to_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    keyboard = [
        [InlineKeyboardButton("👤 Ruxsat berish", callback_data="admin_menu")],
        [InlineKeyboardButton("📋 Ruxsatlarni boshqarish", callback_data="admin_manage")],
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("🎬 Botdan foydalanish", callback_data="user_menu")]
    ]
    await query.edit_message_text(
        "👑 *Admin Panel*\n\n"
        "🏠 Asosiy menyu:",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
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
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]]
        await query.edit_message_text(
            "🎬 *YouTube havolasini yuboring:*\n\n"
            "Misol: `https://youtube.com/watch?v=...`",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data['state'] = WAITING_FOR_YOUTUBE
        
    elif query.data == "main_srt":
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]]
        await query.edit_message_text(
            "📄 *SRT faylni yuboring:*\n\n"
            "Faqat `.srt` formatidagi fayllar qabul qilinadi.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
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
            [InlineKeyboardButton("🎬 YouTube", callback_data="main_youtube")],
            [InlineKeyboardButton("📄 SRT fayl", callback_data="main_srt")],
            [InlineKeyboardButton("🔙 Admin", callback_data="back_to_admin")]
        ]
        text = "🎬 *Botdan foydalanish*\n\nTanlang:"
    else:
        keyboard = [
            [InlineKeyboardButton("🎬 YouTube video", callback_data="main_youtube")],
            [InlineKeyboardButton("📄 SRT fayl", callback_data="main_srt")]
        ]
        has_perm, expires = check_permission(user_id)
        days_left = (expires - datetime.datetime.now()).days if has_perm else 0
        text = f"✅ *Xush kelibsiz!*\n📅 {days_left} kun qoldi\n\nTanlang:"
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ==================== YOUTUBE HAVOLA ====================

async def handle_youtube_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if context.user_data.get('state') != WAITING_FOR_YOUTUBE:
        return False
    
    user_id = update.effective_user.id
    url = update.message.text.strip()
    
    has_perm, _ = check_permission(user_id)
    if not has_perm and user_id != ADMIN_ID:
        await update.message.reply_text("❌ Ruxsat yo'q")
        context.user_data['state'] = None
        return True
    
    # URL tekshirish
    if not ('youtube.com/watch' in url or 'youtu.be/' in url or 'youtube.com/shorts/' in url):
        await update.message.reply_text(
            "❌ *Noto'g'ri URL*\n\n"
            "Faqat YouTube havolalari qabul qilinadi.\n"
            "Misol: `https://youtube.com/watch?v=...`",
            parse_mode='Markdown'
        )
        context.user_data['state'] = None
        return True
    
    msg = await update.message.reply_text("⏳ *Tekshirilmoqda...*", parse_mode='Markdown')
    
    video_title, available_langs, _ = await get_youtube_subtitles(url)
    
    if not video_title:
        await msg.edit_text(
            "❌ *Xatolik*\n\n"
            "Video topilmadi yoki maxfiy video.\n"
            "Boshqa havola sinab ko'ring.",
            parse_mode='Markdown'
        )
        context.user_data['state'] = None
        return True
    
    if not available_langs:
        await msg.edit_text(
            f"📹 *{video_title[:50]}*\n\n"
            "❌ Subtitr topilmadi.\n\n"
            "Bu videoda subtitr mavjud emas.",
            parse_mode='Markdown'
        )
        context.user_data['state'] = None
        return True
    
    # Tillarni guruhlash
    manual_langs = []
    auto_langs = []
    
    for lang_code, lang_info in available_langs.items():
        if not lang_info['is_auto']:
            manual_langs.append((lang_code, lang_info))
        else:
            auto_langs.append((lang_code, lang_info))
    
    keyboard = []
    
    # Qo'lda kiritilganlar
    if manual_langs:
        for lang_code, lang_info in manual_langs:
            button_text = f"📝 {lang_info['name']}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"sub_{lang_code}")])
    
    # Auto-generated (ozgina)
    if auto_langs:
        if manual_langs:
            keyboard.append([InlineKeyboardButton("─" * 20, callback_data="ignore")])
        for lang_code, lang_info in auto_langs:
            button_text = f"🤖 {lang_info['name']}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"sub_{lang_code}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")])
    
    # Xabarni tayyorlash
    manual_count = len(manual_langs)
    auto_count = len(auto_langs)
    
    await msg.edit_text(
        f"📹 *{video_title[:100]}*\n\n"
        f"📝 Qo'lda kiritilgan: {manual_count} ta\n"
        f"🤖 Auto-generated: {auto_count} ta\n\n"
        f"Subtitr tilini tanlang:",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    context.user_data['video_url'] = url
    context.user_data['video_title'] = video_title
    context.user_data['langs'] = available_langs
    context.user_data['state'] = None
    
    return True

# ==================== SUBTITR YUKLASH ====================

async def subtitle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "ignore":
        return
    
    user_id = update.effective_user.id
    
    has_perm, _ = check_permission(user_id)
    if not has_perm and user_id != ADMIN_ID:
        await query.edit_message_text("❌ Ruxsat yo'q")
        return
    
    if not query.data.startswith("sub_"):
        return
    
    lang_code = query.data.replace("sub_", "")
    
    url = context.user_data.get('video_url')
    video_title = context.user_data.get('video_title')
    langs = context.user_data.get('langs', {})
    
    if not url or lang_code not in langs:
        await query.edit_message_text("❌ Xatolik: Ma'lumot topilmadi")
        return
    
    lang_info = langs[lang_code]
    
    await query.edit_message_text(f"⏳ *Yuklanmoqda...*\n\n{lang_info['name']}", parse_mode='Markdown')
    
    srt_file = await download_subtitle(url, lang_code, lang_info)
    
    if srt_file and os.path.exists(srt_file):
        save_user_file(user_id, srt_file, video_title, lang_info['name'])
        
        with open(srt_file, 'rb') as f:
            await context.bot.send_document(
                user_id,
                f,
                filename=f"{video_title[:50].replace(' ', '_')}.srt",
                caption=f"✅ *{lang_info['name']}*\n\n📹 {video_title[:100]}",
                parse_mode='Markdown'
            )
        
        keyboard = [
            [InlineKeyboardButton("🧠 Tarjima qilish", callback_data="translate_srt")],
            [InlineKeyboardButton("🔙 Menyu", callback_data="back_to_main")]
        ]
        await context.bot.send_message(
            user_id,
            "✅ *Subtitr yuklandi!*\n\n"
            "O'zbek tiliga tarjima qilish uchun tugmani bosing:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        await query.delete_message()
    else:
        await query.edit_message_text(
            "❌ *Xatolik*\n\n"
            "Subtitr yuklab olinmadi.\n"
            "Qayta urinib ko'ring.",
            parse_mode='Markdown'
        )

# ==================== SRT FAYL ====================

async def handle_srt_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('state') != WAITING_FOR_SRT:
        return
    
    user_id = update.effective_user.id
    
    has_perm, _ = check_permission(user_id)
    if not has_perm and user_id != ADMIN_ID:
        await update.message.reply_text("❌ Ruxsat yo'q")
        context.user_data['state'] = None
        return
    
    document = update.message.document
    
    if not document.file_name.lower().endswith('.srt'):
        await update.message.reply_text(
            "❌ *Noto'g'ri format*\n\n"
            "Faqat `.srt` fayllar qabul qilinadi.",
            parse_mode='Markdown'
        )
        context.user_data['state'] = None
        return
    
    # Fayl hajmini tekshirish (50 MB dan kichik)
    if document.file_size > 50 * 1024 * 1024:
        await update.message.reply_text(
            "❌ *Fayl juda katta*\n\n"
            "Maksimal 50 MB hajmli fayl yuborishingiz mumkin.",
            parse_mode='Markdown'
        )
        context.user_data['state'] = None
        return
    
    msg = await update.message.reply_text("⏳ *Yuklanmoqda...*", parse_mode='Markdown')
    
    file = await context.bot.get_file(document.file_id)
    
    with tempfile.NamedTemporaryFile(suffix='.srt', delete=False) as tmp:
        temp_filename = tmp.name
    
    await file.download_to_drive(temp_filename)
    
    # Faylni tekshirish
    try:
        subs = pysrt.open(temp_filename)
        line_count = len(subs)
        save_user_file(user_id, temp_filename, document.file_name, "Yuklangan")
        
        await msg.edit_text(
            f"✅ *Fayl qabul qilindi!*\n\n"
            f"📄 {document.file_name}\n"
            f"📊 {line_count} ta qator\n\n"
            f"Endi tarjima qilishingiz mumkin.",
            parse_mode='Markdown'
        )
        
        keyboard = [
            [InlineKeyboardButton("🧠 Tarjima qilish", callback_data="translate_srt")],
            [InlineKeyboardButton("🔙 Menyu", callback_data="back_to_main")]
        ]
        
        await context.bot.send_message(
            user_id,
            "O'zbek tiliga tarjima qilish uchun tugmani bosing:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"SRT fayl xatolik: {e}")
        await msg.edit_text(
            "❌ *Xatolik*\n\n"
            "Fayl buzilgan yoki noto'g'ri formatda.\n"
            "Qayta urinib ko'ring.",
            parse_mode='Markdown'
        )
        try:
            os.remove(temp_filename)
        except:
            pass
    
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
    
    if query.data != "translate_srt":
        return
    
    srt_file, video_title, original_lang = get_user_file(user_id)
    
    if not srt_file or not os.path.exists(srt_file):
        await query.edit_message_text(
            "❌ *Fayl topilmadi*\n\n"
            "Avval subtitr yuklang.",
            parse_mode='Markdown'
        )
        return
    
    # Eski progress xabarni o'chirish
    await query.delete_message()
    
    translated_file, progress_msg = await translate_with_progress(
        update, context, srt_file, video_title or "subtitr"
    )
    
    if translated_file and os.path.exists(translated_file):
        with open(translated_file, 'rb') as f:
            await context.bot.send_document(
                user_id,
                f,
                filename=f"uzbek_{os.path.basename(srt_file)}",
                caption="✅ *Tarjima tayyor!*\n\n"
                        "🇺🇿 O'zbek tiliga tarjima qilindi.",
                parse_mode='Markdown'
            )
        
        try:
            await progress_msg.delete()
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
            user_id,
            "✨ *Yana?*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # Fayllarni tozalash
        try:
            os.remove(translated_file)
            os.remove(srt_file)
        except:
            pass
    else:
        if not context.user_data.get('cancelled'):
            await context.bot.send_message(
                user_id,
                "❌ *Tarjima xatolik*\n\n"
                "Qayta urinib ko'ring.",
                parse_mode='Markdown'
            )

# ==================== XABAR HANDLER ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Admin xabarlarini tekshirish
    if await handle_admin_message(update, context):
        return
    
    # YouTube URL ni tekshirish
    if await handle_youtube_url(update, context):
        return
    
    # Oddiy xabar
    if context.user_data.get('state') is None:
        await update.message.reply_text(
            "❌ *Noto'g'ri buyruq*\n\n"
            "Iltimos, /start ni bosing",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "❌ *Kutilmagan xabar*\n\n"
            "Iltimos, yuqoridagi ko'rsatmalarga amal qiling.",
            parse_mode='Markdown'
        )

# ==================== MAIN ====================

def main():
    try:
        print("⏳ Ishga tushmoqda...")
        print("=" * 40)
        
        # Bazani yaratish
        init_db()
        
        # Bot
        app = Application.builder().token(BOT_TOKEN).build()
        
        # Handlerlar
        app.add_handler(CommandHandler("start", start))
        
        # Callbacklar
        app.add_handler(CallbackQueryHandler(admin_menu_callback, pattern="^admin_menu$"))
        app.add_handler(CallbackQueryHandler(admin_manage_callback, pattern="^admin_manage$"))
        app.add_handler(CallbackQueryHandler(admin_stats_callback, pattern="^admin_stats$"))
        app.add_handler(CallbackQueryHandler(remove_user_callback, pattern="^remove_"))
        app.add_handler(CallbackQueryHandler(user_menu_callback, pattern="^user_menu$"))
        app.add_handler(CallbackQueryHandler(back_to_admin_callback, pattern="^back_to_admin$"))
        app.add_handler(CallbackQueryHandler(back_to_main_callback, pattern="^back_to_main$"))
        app.add_handler(CallbackQueryHandler(days_callback, pattern="^days_"))
        app.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_"))
        app.add_handler(CallbackQueryHandler(subtitle_callback, pattern="^sub_"))
        app.add_handler(CallbackQueryHandler(translate_callback, pattern="^translate_"))
        app.add_handler(CallbackQueryHandler(cancel_translate_callback, pattern="^cancel_translate$"))
        
        # Xabarlar
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(MessageHandler(filters.Document.ALL, handle_srt_file))
        
        print("✅ Bot ishga tushdi!")
        print(f"👑 Admin ID: {ADMIN_ID}")
        print(f"📊 Holat: Optimallashtirilgan")
        print(f"🚀 Tarjima: 1 API so'rov = butun subtitr")
        print("=" * 40)
        
        app.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"Xatolik: {e}")
        print(f"❌ Xatolik: {e}")
        print("⏳ 5 soniyadan keyin qayta ishga tushadi...")
        time.sleep(5)
        main()

if __name__ == "__main__":
    main()
