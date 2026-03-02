import os
import logging
import tempfile
import sqlite3
import datetime
import pysrt
import aiohttp
import asyncio
from typing import Dict, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, CallbackQueryHandler, ContextTypes, ConversationHandler
)
import yt_dlp

# ==================== SOZLAMALAR ====================
# SIZ YUBORGAN MA'LUMOTLAR
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
    """SRT faylni tarjima qilish"""
    
    try:
        subs = pysrt.open(srt_path)
        translated_subs = []
        
        # Foydalanuvchiga ko'rinadigan xabar (DeepSeek nomi yo'q)
        total = len(subs)
        
        for i, sub in enumerate(subs):
            # Har bir subtitrni tarjima qilish
            translated_text = await translate_with_deepseek(sub.text, target_lang)
            
            if translated_text:
                sub.text = translated_text
            else:
                # Xatolik bo'lsa, asl matnni qoldirish
                sub.text = f"[?] {sub.text}"
            
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

# ==================== YOUTUBE SUBTITR OLISH ====================
async def get_youtube_subtitles(url):
    """YouTube dan subtitr olish"""
    
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['all'],
        'quiet': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'Noma\'lum video')
            
            subtitles = info.get('subtitles', {})
            auto_captions = info.get('automatic_captions', {})
            
            available_langs = {}
            
            # Qo'lda kiritilgan subtitrlar
            for lang, sub_data in subtitles.items():
                if sub_data:
                    lang_name = get_language_name(lang)
                    available_langs[lang] = {'name': lang_name, 'type': 'manual'}
            
            # Avtomatik subtitrlar
            for lang, sub_data in auto_captions.items():
                if sub_data and lang not in available_langs:
                    lang_name = get_language_name(lang)
                    available_langs[lang] = {'name': lang_name, 'type': 'auto'}
            
            return video_title, available_langs, info
            
    except Exception as e:
        logger.error(f"YouTube xatolik: {e}")
        return None, {}, None

async def download_subtitle(url, lang_code, lang_type):
    """Subtitrni yuklab olish"""
    
    with tempfile.NamedTemporaryFile(suffix='.srt', delete=False) as tmp_file:
        temp_filename = tmp_file.name
    
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'subtitleslangs': [lang_code],
        'subtitlesformat': 'srt',
        'outtmpl': temp_filename.replace('.srt', ''),
        'quiet': True,
    }
    
    if lang_type == 'auto':
        ydl_opts['writeautomaticsub'] = True
    else:
        ydl_opts['writeautomaticsub'] = False
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Yuklab olingan faylni topish
        possible_srt = temp_filename.replace('.srt', '') + f'.{lang_code}.srt'
        if not os.path.exists(possible_srt):
            possible_srt = temp_filename.replace('.srt', '') + '.srt'
        
        if os.path.exists(possible_srt) and os.path.getsize(possible_srt) > 0:
            return possible_srt
        else:
            return None
            
    except Exception as e:
        logger.error(f"Subtitr yuklash xatolik: {e}")
        return None

# ==================== BOT HANDLERLARI ====================

# /start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "noma'lum"
    
    # Adminmi tekshirish
    if user_id == ADMIN_ID:
        # Admin panel
        keyboard = [
            [InlineKeyboardButton("👤 Ruxsat berish", callback_data="admin_add")],
            [InlineKeyboardButton("🗑️ Ruxsat olib tashlash", callback_data="admin_remove")],
            [InlineKeyboardButton("📋 Ruxsatlar ro'yxati", callback_data="admin_list")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "👑 *Admin panel*\n\nNima qilmoqchisiz?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    # Oddiy foydalanuvchi - ruxsatni tekshirish
    has_perm, expires = check_permission(user_id)
    
    if has_perm:
        # Ruxsat bor - asosiy menyu
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
        # Ruxsat yo'q
        await update.message.reply_text(
            f"❌ *Ruxsat yo'q*\n\n"
            f"Botdan foydalanish uchun @maestro_o ga murojaat qiling.\n\n"
            f"🆔 Sizning ID: `{user_id}`\n\n"
            f"Admin sizni qo'shishi uchun shu ID ni yuboring.",
            parse_mode='Markdown'
        )

# ==================== ADMIN PANEL ====================
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Faqat admin uchun
    if user_id != ADMIN_ID:
        await query.edit_message_text("❌ Bu faqat admin uchun!")
        return
    
    data = query.data
    
    if data == "admin_add":
        # ID so'rash
        await query.edit_message_text(
            "👤 *Ruxsat berish*\n\n"
            "Foydalanuvchi ID raqamini yuboring:",
            parse_mode='Markdown'
        )
        context.user_data['admin_action'] = 'waiting_for_add_id'
        return
        
    elif data == "admin_remove":
        # O'chirish uchun ID so'rash
        await query.edit_message_text(
            "🗑️ *Ruxsatni olib tashlash*\n\n"
            "Foydalanuvchi ID raqamini yuboring:",
            parse_mode='Markdown'
        )
        context.user_data['admin_action'] = 'waiting_for_remove_id'
        return
        
    elif data == "admin_list":
        # Ruxsatlar ro'yxati
        users = get_all_users()
        
        if not users:
            await query.edit_message_text(
                "📋 *Ruxsatlar ro'yxati*\n\n"
                "Hech kimga ruxsat berilmagan.",
                parse_mode='Markdown'
            )
            return
        
        text = "📋 *Ruxsat berilgan foydalanuvchilar:*\n\n"
        for uid, uname, expires in users:
            days_left = (datetime.datetime.fromisoformat(expires) - datetime.datetime.now()).days
            text += f"🆔 {uid} | @{uname} | {days_left} kun\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    elif data == "admin_back":
        # Admin panelga qaytish
        keyboard = [
            [InlineKeyboardButton("👤 Ruxsat berish", callback_data="admin_add")],
            [InlineKeyboardButton("🗑️ Ruxsat olib tashlash", callback_data="admin_remove")],
            [InlineKeyboardButton("📋 Ruxsatlar ro'yxati", callback_data="admin_list")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "👑 *Admin panel*\n\nNima qilmoqchisiz?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

# ==================== ADMIN XABARLARINI QAYTA ISHLASH ====================
async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    # Faqat admin uchun
    if user_id != ADMIN_ID:
        return
    
    action = context.user_data.get('admin_action')
    
    if action == 'waiting_for_add_id':
        # ID ni olish
        try:
            target_id = int(text.strip())
            context.user_data['target_id'] = target_id
            context.user_data['admin_action'] = 'waiting_for_days'
            
            # Kunlar tugmalari
            keyboard = [
                [InlineKeyboardButton("3 kun", callback_data="days_3")],
                [InlineKeyboardButton("5 kun", callback_data="days_5")],
                [InlineKeyboardButton("10 kun", callback_data="days_10")],
                [InlineKeyboardButton("1 oy (30 kun)", callback_data="days_30")],
                [InlineKeyboardButton("🔙 Bekor qilish", callback_data="admin_back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🆔 ID: {target_id}\n\n"
                f"Qancha kun ruxsat beramiz?",
                reply_markup=reply_markup
            )
            
        except ValueError:
            await update.message.reply_text("❌ Noto'g'ri ID. Qaytadan urinib ko'ring.")
            
    elif action == 'waiting_for_remove_id':
        # O'chirish uchun ID
        try:
            target_id = int(text.strip())
            remove_permission(target_id)
            
            await update.message.reply_text(
                f"✅ {target_id} ID li foydalanuvchi ruxsati olib tashlandi!"
            )
            
            # Admin panelga qaytish
            context.user_data['admin_action'] = None
            
            keyboard = [
                [InlineKeyboardButton("👤 Ruxsat berish", callback_data="admin_add")],
                [InlineKeyboardButton("🗑️ Ruxsat olib tashlash", callback_data="admin_remove")],
                [InlineKeyboardButton("📋 Ruxsatlar ro'yxati", callback_data="admin_list")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "👑 *Admin panel*",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except ValueError:
            await update.message.reply_text("❌ Noto'g'ri ID. Qaytadan urinib ko'ring.")

# ==================== KUN TANLASH ====================
async def days_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Faqat admin uchun
    if user_id != ADMIN_ID:
        return
    
    data = query.data
    target_id = context.user_data.get('target_id')
    
    if not target_id:
        await query.edit_message_text("❌ Xatolik yuz berdi. Qaytadan boshlang.")
        return
    
    days_map = {
        'days_3': 3,
        'days_5': 5,
        'days_10': 10,
        'days_30': 30
    }
    
    if data in days_map:
        days = days_map[data]
        
        # Ruxsat berish
        add_permission(target_id, "user", days)
        
        await query.edit_message_text(
            f"✅ *Ruxsat berildi!*\n\n"
            f"🆔 ID: {target_id}\n"
            f"📅 Muddat: {days} kun\n\n"
            f"Foydalanuvchi endi botdan foydalana oladi.",
            parse_mode='Markdown'
        )
        
        context.user_data['admin_action'] = None
        context.user_data['target_id'] = None

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

# ==================== YOUTUBE HAVOLASINI QAYTA ISHLASH ====================
async def handle_youtube_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Faqat YouTube kutilayotgan holatda
    if context.user_data.get('state') != WAITING_FOR_YOUTUBE:
        return
    
    url = update.message.text
    
    # Ruxsatni tekshirish
    has_perm, expires = check_permission(user_id)
    if not has_perm and user_id != ADMIN_ID:
        await update.message.reply_text("❌ Ruxsat yo'q!")
        return
    
    progress_msg = await update.message.reply_text("⏳ Video tekshirilmoqda...")
    
    # YouTube subtitrlarni olish
    video_title, available_langs, info = await get_youtube_subtitles(url)
    
    if not available_langs:
        # Subtitr yo'q
        await progress_msg.edit_text(
            "😕 *Subtitr topilmadi!*\n\n"
            "Boshqa drama/video yuboring, buning subtitr fayli yo'q.",
            parse_mode='Markdown'
        )
        # Holatni tozalash
        context.user_data['state'] = None
        return
    
    # Subtitr bor - tillarni ko'rsatish
    keyboard = []
    
    # Qo'lda kiritilganlar
    for lang_code, lang_info in available_langs.items():
        if lang_info['type'] == 'manual':
            button = InlineKeyboardButton(
                f"📝 {lang_info['name']}",
                callback_data=f"sub_{lang_code}"
            )
            keyboard.append([button])
    
    # Avtomatiklar
    for lang_code, lang_info in available_langs.items():
        if lang_info['type'] == 'auto':
            button = InlineKeyboardButton(
                f"🤖 {lang_info['name']}",
                callback_data=f"sub_{lang_code}"
            )
            keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton("🔙 Asosiy menyu", callback_data="main_back")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Ma'lumotlarni saqlash
    context.user_data['video_url'] = url
    context.user_data['video_title'] = video_title
    context.user_data['langs'] = available_langs
    
    await progress_msg.edit_text(
        f"📹 *{video_title[:50]}*\n\n"
        f"🎯 {len(available_langs)} ta subtitr topildi. Tanlang:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Holatni tozalash
    context.user_data['state'] = None

# ==================== SUBTITR YUKLASH ====================
async def subtitle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    # Ruxsatni tekshirish
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
        
        # Yuklanayotgani haqida xabar
        await query.edit_message_text(
            f"⏳ {lang_info['name']} yuklanmoqda...",
            parse_mode='Markdown'
        )
        
        # Subtitrni yuklab olish
        srt_file = await download_subtitle(url, lang_code, lang_info['type'])
        
        if srt_file:
            # Faylni saqlash
            save_user_file(user_id, srt_file, video_title, lang_info['name'])
            
            # Faylni yuborish
            with open(srt_file, 'rb') as f:
                await context.bot.send_document(
                    chat_id=user_id,
                    document=f,
                    filename=f"{video_title[:30]}_{lang_code}.srt",
                    caption=f"📥 *{video_title[:50]}*\n"
                            f"🌐 Til: {lang_info['name']}"
                )
            
            # Tarjima tugmasi
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
            
            # Progress xabarni o'chirish
            await query.delete_message()
            
        else:
            await query.edit_message_text("❌ Subtitr yuklab olishda xatolik yuz berdi.")
    
    elif data == "main_back":
        # Asosiy menyuga qaytish
        keyboard = [
            [InlineKeyboardButton("🎬 YouTube video", callback_data="main_youtube")],
            [InlineKeyboardButton("📄 SRT fayl yuborish", callback_data="main_srt")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Tanlang:",
            reply_markup=reply_markup
        )

# ==================== SRT FAYLNI QAYTA ISHLASH ====================
async def handle_srt_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Faqat SRT kutilayotgan holatda
    if context.user_data.get('state') != WAITING_FOR_SRT:
        return
    
    # Ruxsatni tekshirish
    has_perm, expires = check_permission(user_id)
    if not has_perm and user_id != ADMIN_ID:
        await update.message.reply_text("❌ Ruxsat yo'q!")
        return
    
    document = update.message.document
    
    if not document.file_name.endswith('.srt'):
        await update.message.reply_text("❌ Faqat .srt fayl yuboring!")
        return
    
    # Faylni yuklab olish
    file = await context.bot.get_file(document.file_id)
    
    with tempfile.NamedTemporaryFile(suffix='.srt', delete=False) as tmp_file:
        temp_filename = tmp_file.name
    
    await file.download_to_drive(temp_filename)
    
    # Faylni saqlash
    save_user_file(user_id, temp_filename, document.file_name, "Yuklangan fayl")
    
    # Tarjima tugmasi
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
    
    # Holatni tozalash
    context.user_data['state'] = None

# ==================== TARJIMA QILISH ====================
async def translate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    # Ruxsatni tekshirish
    has_perm, expires = check_permission(user_id)
    if not has_perm and user_id != ADMIN_ID:
        await query.edit_message_text("❌ Ruxsat yo'q!")
        return
    
    if data == "translate_srt":
        # Foydalanuvchi faylini olish
        srt_file, video_title, original_lang = get_user_file(user_id)
        
        if not srt_file or not os.path.exists(srt_file):
            await query.edit_message_text("❌ Fayl topilmadi. Avval subtitr yuklang!")
            return
        
        # YOZUV - DeepSeek nomi YO'Q
        await query.edit_message_text(
            "🧠 *Sun'iy intellekt orqali sifatli tarjima qilinmoqda...*\n\n"
            "• Bu bir necha daqiqa olishi mumkin\n"
            "• AI tarjimon ishlamoqda\n"
            "• Iltimos, kuting...",
            parse_mode='Markdown'
        )
        
        # Tarjima qilish
        translated_file = await translate_srt_file(srt_file, "uzbek")
        
        if translated_file and os.path.exists(translated_file):
            # Faylni yuborish
            with open(translated_file, 'rb') as f:
                await context.bot.send_document(
                    chat_id=user_id,
                    document=f,
                    filename=f"ozbekcha_{os.path.basename(srt_file)}",
                    caption=f"✅ *Tarjima tayyor!*\n\n"
                            f"🧠 Sun'iy intellekt yordamida O'zbek tiliga sifatli tarjima qilindi.\n"
                            f"📁 Asl fayl: {video_title}",
                    parse_mode='Markdown'
                )
            
            # Vaqtinchalik faylni o'chirish
            try:
                os.remove(translated_file)
            except:
                pass
            
            # Asosiy menyu tugmalari
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
            
            # Progress xabarni o'chirish
            await query.delete_message()
            
        else:
            await query.edit_message_text(
                "❌ Tarjima qilishda xatolik yuz berdi.\n\n"
                "Qaytadan urinib ko'ring yoki admin @maestro_o ga murojaat qiling."
            )

# ==================== ASOSIY FUNKSIYA ====================
def main():
    """Botni ishga tushirish"""
    
    # Bazani yaratish
    init_db()
    
    # Botni yaratish
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlerlar
    application.add_handler(CommandHandler("start", start))
    
    # Callback handlerlar
    application.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
    application.add_handler(CallbackQueryHandler(days_callback, pattern="^days_"))
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_"))
    application.add_handler(CallbackQueryHandler(subtitle_callback, pattern="^sub_"))
    application.add_handler(CallbackQueryHandler(translate_callback, pattern="^translate_"))
    
    # Xabar handlerlar
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_youtube_url))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_srt_file))
    
    # Botni ishga tushirish
    print("🤖 Bot ishga tushdi...")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print(f"🤖 Bot token: {BOT_TOKEN[:10]}...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
