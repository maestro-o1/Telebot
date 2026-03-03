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
ADMIN_ID = 1700341163

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

WAITING_FOR_YOUTUBE = 1
WAITING_FOR_SRT = 2

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== MA'LUMOTLAR BAZASI ====================
def init_db():
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

def add_permission(user_id, username, first_name, last_name, days):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    expires_at = datetime.datetime.now() + datetime.timedelta(days=days)
    c.execute('''INSERT OR REPLACE INTO permissions 
                 (user_id, username, first_name, last_name, expires_at, granted_by, granted_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (user_id, username, first_name, last_name, expires_at.isoformat(), ADMIN_ID, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()

def check_permission(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('SELECT expires_at FROM permissions WHERE user_id=?', (user_id,))
    result = c.fetchone()
    conn.close()
    if result:
        expires_at = datetime.datetime.fromisoformat(result[0])
        return expires_at > datetime.datetime.now()
    return False

def save_user_file(user_id, file_path, video_title, original_lang=None):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO user_data 
                 (user_id, current_file, video_title, original_lang)
                 VALUES (?, ?, ?, ?)''',
              (user_id, file_path, video_title, original_lang))
    conn.commit()
    conn.close()

def get_user_file(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('SELECT current_file, video_title, original_lang FROM user_data WHERE user_id=?', (user_id,))
    result = c.fetchone()
    conn.close()
    if result and os.path.exists(result[0]):
        return result
    return None, None, None

# ==================== TIL NOMLARI ====================
def get_language_name(lang_code):
    languages = {'en':'Ingliz tili','uz':'O\'zbek tili'}
    return languages.get(lang_code, lang_code.upper())

# ==================== DEEPSEEK TARJIMA ====================
async def translate_with_deepseek(text):
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    system_prompt = "You are a professional translator. Translate the given text to Uzbek language. Return ONLY the translated text."
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role":"system","content":system_prompt},{"role":"user","content":text}],
        "temperature":0.3,"max_tokens":2000
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(DEEPSEEK_API_URL, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    translated = result['choices'][0]['message']['content'].strip()
                    return re.sub(r'^Translate this to Uzbek:?\s*', '', translated, flags=re.IGNORECASE)
                else:
                    return f"[?] {text}"
    except:
        return f"[?] {text}"

async def translate_srt_file(update, context, srt_file, video_title):
    user_id = update.effective_user.id
    subs = pysrt.open(srt_file)
    total = len(subs)
    translated_subs = []
    for i, sub in enumerate(subs):
        translated_text = await translate_with_deepseek(sub.text)
        sub.text = translated_text
        translated_subs.append(sub)
    output_path = srt_file.replace('.srt','_ozbek.srt')
    new_subs = pysrt.SubRipFile()
    for sub in translated_subs: new_subs.append(sub)
    new_subs.save(output_path, encoding='utf-8')
    return output_path

# ==================== SRT KONVERT ====================
def convert_to_srt(file_path, ext):
    if ext=='srt': return file_path
    with open(file_path,'r',encoding='utf-8',errors='ignore') as f: content=f.read()
    if ext=='vtt':
        lines=[l for l in content.split('\n') if '-->' in l or l.strip() and not l.startswith('WEBVTT')]
        content='\n'.join(lines)
    out_file=file_path.replace(f'.{ext}','.srt')
    with open(out_file,'w',encoding='utf-8') as f: f.write(content)
    return out_file

# ==================== YOUTUBE SUBTITR ====================
async def get_youtube_subtitles(url):
    ydl_opts={'skip_download':True,'writesubtitles':True,'writeautomaticsub':True,'subtitleslangs':['uz','en'],'quiet':True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title','Video')
            subs_manual = info.get('subtitles',{})
            subs_auto = info.get('automatic_captions',{})
            manual_subs={}
            auto_subs={}
            for lang,data in subs_manual.items():
                if lang in ['uz','en']: manual_subs[lang]={'name':get_language_name(lang),'type':'manual','data':data}
            for lang,data in subs_auto.items():
                if lang in ['uz','en']: auto_subs[lang]={'name':get_language_name(lang)+' (avto)','type':'auto','data':data}
            return video_title, manual_subs, auto_subs
    except:
        return None, {}, {}

async def download_subtitle(url, lang_code, lang_info):
    with tempfile.NamedTemporaryFile(suffix='.srt', delete=False) as tmp: fname=tmp.name
    ydl_opts={'skip_download':True,'writesubtitles':True,'subtitleslangs':[lang_code],'outtmpl':fname.replace('.srt',''),'quiet':True}
    if lang_info['type']=='auto': ydl_opts['writeautomaticsub']=True
    with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([url])
    for ext in ['srt','vtt','ass','ssa','sbv']:
        fpath=f"{fname}.{lang_code}.{ext}"; 
        if os.path.exists(fpath): return convert_to_srt(fpath, ext)
    return None

# ==================== START ====================
async def start(update, context):
    user_id=update.effective_user.id
    keyboard=[[InlineKeyboardButton("🎬 YouTube SRT",callback_data="main_youtube")],[InlineKeyboardButton("📄 SRT Tarjima",callback_data="main_srt")]]
    if user_id==ADMIN_ID: keyboard.append([InlineKeyboardButton("👑 Admin panel",callback_data="admin_menu")])
    await update.message.reply_text("👋 Xush kelibsiz! Tanlang:",reply_markup=InlineKeyboardMarkup(keyboard))

# ==================== MAIN ====================
async def handle_message(update,context):
    await update.message.reply_text("❌ Iltimos /start ni bosing.")

def main():
    init_db()
    app=Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    main()
