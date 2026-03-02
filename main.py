import os
import logging
import tempfile
import sqlite3
import datetime
import pysrt
import aiohttp
import asyncio
import re
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
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    # Ruxsatlar jadvali
    c.execute('''CREATE TABLE IF NOT EXISTS permissions
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  expires_at TIMESTAMP,
                  granted_by INTEGER,
                  granted_at TIMESTAMP)''')
    
    # Foydalanuvchi ma'lumotlari jadvali
    c.execute('''CREATE TABLE IF NOT EXISTS user_data
                 (user_id INTEGER PRIMARY KEY,
                  current_file TEXT,
                  video_title TEXT,
                  original_lang TEXT)''')
    
    conn.commit()
    conn.close()

def add_permission(user_id, username, days):
    """Foydalanuvchiga ruxsat berish"""
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    expires_at = datetime.datetime.now() + datetime.timedelta(days=days)
    
    c.execute('''INSERT OR REPLACE INTO permissions 
                 (user_id, username, expires_at, granted_by, granted_at)
                 VALUES (?, ?, ?, ?, ?)''',
              (user_id, username, expires_at, ADMIN_ID, datetime.datetime.now()))
    
    conn.commit()
    conn.close()

def remove_permission(user_id):
    """Ruxsatni olib tashlash"""
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('DELETE FROM permissions WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def check_permission(user_id):
    """Ruxsatni tekshirish"""
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    c.execute('SELECT expires_at FROM permissions WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    
    if result:
        expires_at = datetime.datetime.fromisoformat(result[0])
        if expires_at > datetime.datetime.now():
            conn.close()
            return True, expires_at
    
    conn.close()
    return False, None

def get_all_users():
    """Barcha ruxsat berilgan foydalanuvchilarni olish"""
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    c.execute('''SELECT user_id, username, expires_at 
                 FROM permissions 
                 ORDER BY expires_at''')
    users = c.fetchall()
    
    conn.close()
    return users

def save_user_file(user_id, file_path, video_title, original_lang=None):
    """Foydalanuvchi faylini saqlash"""
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    c.execute('''INSERT OR REPLACE INTO user_data 
                 (user_id, current_file, video_title, original_lang)
                 VALUES (?, ?, ?, ?)''',
              (user_id, file_path, video_title, original_lang))
    
    conn.commit()
    conn.close()

def get_user_file(user_id):
    """Foydalanuvchi faylini olish"""
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    c.execute('SELECT current_file, video_title, original_lang FROM user_data WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    
    conn.close()
    return result if result else (None, None, None)

# ==================== TIL NOMLARI ====================
def get_language_name(lang_code):
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

async def translate_srt_file(srt_path, target_lang="uzbek"):
    """SRT faylni tarjima qilish - VAQT KODLARI O'ZGARMAYDI"""
    
    try:
        subs = pysrt.open(srt_path)
        translated_subs = []
        
        for i, sub in enumerate(subs):
            # FAQAT MATN TARJIMA QILINADI
            translated_text = await translate_with_deepseek(sub.text, target_lang)
            
            if translated_text:
                sub.text = translated_text
            else:
                sub.text = f"[?] {sub.text}"
            
            # VAQT KODLARI O'ZGARMASIDAN QOLADI
            translated_subs.append(sub)
            
            # API limiti uchun kutish
            if (i + 1) % 5 == 0:
                await asyncio.sleep(1)
        
        # Yangi fayl yaratish
        output_path = srt_path.replace('.srt', f'_uz.srt')
        
        new_subs = pysrt.SubRipFile()
        for sub in translated_subs:
            new_subs.append(sub)
        
        new_subs.save(output_path, encoding='utf-8')
        return output_path
        
    except Exception as e:
        logger.error(f"SRT tarjima xatolik: {e}")
        return None

# ==================== SUBTITR FORMATLARINI O'GIRISH ====================
def vtt_to_srt(vtt_content):
    """VTT formatini SRT ga o'girish"""
    lines = vtt_content.split('\n')
    srt_lines = []
    counter = 1
    in_cue = False
    
    for line in lines:
        line = line.strip()
        
        # WEBVTT sarlavhasini o'tkazib yuborish
        if line.startswith('WEBVTT') or line.startswith('NOTE') or line.startswith('STYLE'):
            continue
        
        # Vaqt kodlarini o'girish
        if '-->' in line:
            # VTT vaqti: 00:00:00.000 --> 00:00:00.000
            # SRT vaqti: 00:00:00,000 --> 00:00:00,000
            line = line.replace('.', ',')
            # Qo'shimcha belgilarni tozalash
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
                # HTML teglarini olib tashlash
                line = re.sub(r'<[^>]+>', '', line)
                srt_lines.append(line)
    
    return '\n'.join(srt_lines)

def ass_to_srt(ass_content):
    """ASS/SSA formatini SRT ga o'girish"""
    
    srt_lines = []
    counter = 1
    
    # ASS formatida qatorlar: Dialogue: layer,start,end,style,name,marginL,marginR,marginZ,text
    dialogue_pattern = r'Dialogue:\s*\d+,(\d+:\d+:\d+\.\d+),(\d+:\d+:\d+\.\d+),[^,]*,[^,]*,\d+,\d+,\d+,(.*)'
    
    for line in ass_content.split('\n'):
        if line.startswith('Dialogue:'):
            match = re.match(dialogue_pattern, line)
            if match:
                start = match.group(1).replace('.', ',')
                end = match.group(2).replace('.', ',')
                text = match.group(3)
                
                # ASS kodlarini olib tashlash
                text = re.sub(r'\{[^}]*\}', '', text)
                text = text.replace('\\N', '\n')
                text = text.replace('\\n', '\n')
                
                # HTML teglarini olib tashlash
                text = re.sub(r'<[^>]+>', '', text)
                
                srt_lines.append(str(counter))
                counter += 1
                srt_lines.append(f"{start} --> {end}")
                srt_lines.append(text.strip())
                srt_lines.append('')
    
    return '\n'.join(srt_lines)

def sbv_to_srt(sbv_content):
    """SBV (YouTube) formatini SRT ga o'girish"""
    
    lines = sbv_content.split('\n')
    srt_lines = []
    counter = 1
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # SBV formati: 0:00:00.000,0:00:00.000
        # Matn matn matn
        if ',' in line and line.count(':') >= 2:
            # Vaqt qatorini o'girish
            times = line.split(',')
            if len(times) == 2:
                start = times[0].replace('.', ',')
                end = times[1].replace('.', ',')
                
                srt_lines.append(str(counter))
                counter += 1
                srt_lines.append(f"{start} --> {end}")
                
                # Keyingi qator matn
                i += 1
                while i < len(lines) and lines[i].strip():
                    text = lines[i].strip()
                    # HTML teglarini olib tashlash
                    text = re.sub(r'<[^>]+>', '', text)
                    srt_lines.append(text)
                    i += 1
                
                srt_lines.append('')
        i += 1
    
    return '\n'.join(srt_lines)

def convert_to_srt(input_file, input_format):
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
            # SRT bo'lsa, o'ziday qaytarish
            return input_file
        else:
            # Boshqa formatlar uchun pysrt dan foydalanish
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
async def get_youtube_subtitles(url):
    """YouTube dan subtitr olish - HAR QANDAY FORMATDA"""
    
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['all'],
        'subtitlesformat': 'srt/vtt/ass/ssa/sbv',  # HAMMA FORMATLAR
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'Noma\'lum video')
            
            subtitles = info.get('subtitles', {})
            automatic_captions = info.get('automatic_captions', {})
            
            available_langs = {}
            
            # Qo'lda kiritilgan subtitrlar - HAR QANDAY FORMAT
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
            
            # Avtomatik subtitrlar - HAR QANDAY FORMAT
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

async def download_subtitle(url, lang_code, lang_info):
    """Subtitrni yuklab olish va SRT ga o'girish - HAR QANDAY FORMAT"""
    
    with tempfile.NamedTemporaryFile(suffix='.srt', delete=False) as tmp_file:
        temp_filename = tmp_file.name
    
    try:
        # yt-dlp orqali subtitr yuklab olish (eng yaxshi formatda)
        ydl_opts = {
            'skip_download': True,
            'writesubtitles': True,
            'subtitleslangs': [lang_code],
            'subtitlesformat': 'srt/vtt/ass/ssa/sbv',  # BARCHA FORMATLAR
            'outtmpl': temp_filename.replace('.srt', ''),
            'quiet': True,
        }
        
        if lang_info['type'] == 'auto':
            ydl_opts['writeautomaticsub'] = True
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Yuklab olingan faylni topish (qanday formatda bo'lsa)
        base_name = temp_filename.replace('.srt', '')
        possible_files = []
        
        # Barcha mumkin bo'lgan formatlar
        for ext in ['srt', 'vtt', 'ass', 'ssa', 'sbv', 'sub', 'dfxp', 'ttml']:
            # Format: base_name.lang.ext
            file_path = f"{base_name}.{lang_code}.{ext}"
            if os.path.exists(file_path):
                possible_files.append((file_path, ext))
            
            # Format: base_name.ext
            file_path2 = f"{base_name}.{ext}"
            if os.path.exists(file_path2):
                possible_files.append((file_path2, ext))
        
        if not possible_files:
            logger.error(f"Hech qanday subtitr fayli topilmadi: {base_name}")
            return None
        
        # Topilgan faylni SRT ga o'girish
        downloaded_file, file_ext = possible_files[0]
        logger.info(f"Subtitr topildi: {downloaded_file} ({file_ext})")
        
        # Formatni o'girish
        if file_ext != 'srt':
            srt_file = convert_to_srt(downloaded_file, file_ext)
            # Vaqtinchalik faylni o'chirish
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
    user_id = update.effective_user.id
    username = update.effective_user.username or "noma'lum"
    
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
        await update.message.reply_text(
            f"❌ *Ruxsat yo'q*\n\n"
            f"Botdan foydalanish uchun @maestro_o ga murojaat qiling.\n"
            f"Rozi bo'lsa, ID raqamingizni yuboring. Admin sizni qo'shish uchun shu ID dan foydalanadi.\n\n"
            f"🆔 Sizning ID: `{user_id}`",
            parse_mode='Markdown'
        )

# ==================== ADMIN MENYU ====================
async def admin_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
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
    
    for uid, uname, expires in users:
        days_left = (datetime.datetime.fromisoformat(expires) - datetime.datetime.now()).days
        text += f"🆔 {uid} | @{uname} | {days_left} kun qoldi\n"
        keyboard.append([InlineKeyboardButton(f"❌ {uid} ni bekor qilish", callback_data=f"remove_{uid}")])
    
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
        return
    
    data = query.data
    target_id = int(data.replace("remove_", ""))
    
    remove_permission(target_id)
    
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
    
    for uid, uname, expires in users:
        days_left = (datetime.datetime.fromisoformat(expires) - datetime.datetime.now()).days
        text += f"🆔 {uid} | @{uname} | {days_left} kun qoldi\n"
        keyboard.append([InlineKeyboardButton(f"❌ {uid} ni bekor qilish", callback_data=f"remove_{uid}")])
    
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
async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if user_id != ADMIN_ID:
        return
    
    action = context.user_data.get('admin_action')
    
    if action == 'waiting_for_add_id':
        try:
            target_id = int(text.strip())
            context.user_data['target_id'] = target_id
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
            
            await update.message.reply_text(
                f"🆔 ID: {target_id}\n\n"
                f"Qancha kun ruxsat beramiz?",
                reply_markup=reply_markup
            )
            
        except ValueError:
            await update.message.reply_text("❌ Noto'g'ri ID. Qaytadan urinib ko'ring.")

# ==================== KUN TANLASH ====================
async def days_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        return
    
    data = query.data
    target_id = context.user_data.get('target_id')
    
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
        
        add_permission(target_id, "user", days)
        
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
        
        keyboard = [[InlineKeyboardButton("🔙 Admin panel", callback_data="back_to_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ *Ruxsat berildi!*\n\n"
            f"🆔 ID: {target_id}\n"
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
    
    has_perm, expires = check_permission(user_id)
    if not has_perm and user_id != ADMIN_ID:
        await query.edit_message_text("❌ Ruxsat yo'q!")
        return
    
    data = query.data
    
    if data == "main_youtube":
        await query.edit_message_text(
            "🎬 *YouTube video*\n\n"
            "Video havolasini yuboring:",
            parse_mode='Markdown'
        )
        context.user_data['state'] = WAITING_FOR_YOUTUBE
        
    elif data == "main_srt":
        await query.edit_message_text(
            "📄 *SRT fayl*\n\n"
            "SRT faylni yuboring:",
            parse_mode='Markdown'
        )
        context.user_data['state'] = WAITING_FOR_SRT

# ==================== YOUTUBE HAVOLA ====================
async def handle_youtube_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if context.user_data.get('state') != WAITING_FOR_YOUTUBE:
        return
    
    url = update.message.text
    
    has_perm, expires = check_permission(user_id)
    if not has_perm and user_id != ADMIN_ID:
        await update.message.reply_text("❌ Ruxsat yo'q!")
        return
    
    progress_msg = await update.message.reply_text("⏳ Video tekshirilmoqda...")
    
    video_title, available_langs, info = await get_youtube_subtitles(url)
    
    if not available_langs:
        await progress_msg.edit_text(
            "😕 *Subtitr topilmadi!*\n\n"
            "Boshqa drama/video yuboring, buning subtitr fayli yo'q.",
            parse_mode='Markdown'
        )
        context.user_data['state'] = None
        return
    
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
    
    keyboard.append([InlineKeyboardButton("🔙 Asosiy menyu", callback_data="main_back")])
    
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
        
        lang_info = langs[lang_code]  # BU DICTIONARY!
        
        await query.edit_message_text(
            f"⏳ {lang_info['name']} yuklanmoqda...",
            parse_mode='Markdown'
        )
        
        # TO'G'RI: lang_info ni to'liq yuborish
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
                [InlineKeyboardButton("🔙 Asosiy menyu", callback_data="main_back")]
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
            await query.edit_message_text(
                f"❌ Subtitr yuklab olishda xatolik yuz berdi.\n"
                f"Boshqa tilni tanlab ko'ring yoki keyinroq urinib ko'ring."
            )
    
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

# ==================== SRT FAYLNI QAYTA ISHLASH ====================
async def handle_srt_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        [InlineKeyboardButton("🔙 Asosiy menyu", callback_data="main_back")]
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
        
        await query.edit_message_text(
            "🧠 *Sun'iy intellekt orqali sifatli tarjima qilinmoqda...*\n\n"
            "• Bu bir necha daqiqa olishi mumkin\n"
            "• AI tarjimon ishlamoqda\n"
            "• Iltimos, kuting...",
            parse_mode='Markdown'
        )
        
        translated_file = await translate_srt_file(srt_file, "uzbek")
        
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
            
            try:
                os.remove(translated_file)
            except:
                pass
            
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
            
            await query.delete_message()
            
        else:
            await query.edit_message_text(
                "❌ Tarjima qilishda xatolik yuz berdi.\n\n"
                "Qaytadan urinib ko'ring yoki admin @maestro_o ga murojaat qiling."
            )

# ==================== ASOSIY FUNKSIYA ====================
def main():
    """Botni ishga tushirish"""
    
    init_db()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlerlar
    application.add_handler(CommandHandler("start", start))
    
    # Callback handlerlar
    application.add_handler(CallbackQueryHandler(admin_menu_callback, pattern="^admin_menu$"))
    application.add_handler(CallbackQueryHandler(admin_manage_callback, pattern="^admin_manage$"))
    application.add_handler(CallbackQueryHandler(remove_user_callback, pattern="^remove_"))
    application.add_handler(CallbackQueryHandler(user_menu_callback, pattern="^user_menu$"))
    application.add_handler(CallbackQueryHandler(back_to_admin_callback, pattern="^back_to_admin$"))
    application.add_handler(CallbackQueryHandler(days_callback, pattern="^days_"))
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_"))
    application.add_handler(CallbackQueryHandler(subtitle_callback, pattern="^sub_"))
    application.add_handler(CallbackQueryHandler(translate_callback, pattern="^translate_"))
    
    # Xabar handlerlar
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_youtube_url))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_srt_file))
    
    print("🤖 Bot ishga tushdi...")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print(f"📊 Barcha formatlar qo'llab-quvvatlanadi: SRT, VTT, ASS, SSA, SBV")
    print(f"✅ MUHIM: subtitle_callback da lang_info to'liq yuboriladi!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
