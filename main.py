from datetime import datetime, timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import json
import os

# SOZLAMALAR
API_ID = 35058290
API_HASH = "d7cb549b10b8965c99673f8bd36c130a"
BOT_TOKEN = "8660286208:AAHssllobxtng0RDXfZ70fEkfFbjx13FyQE"
YOUR_ID = 1700341163  # @maestro_o

app = Client("kanal_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Ma'lumotlar ombori
scheduled = {}
user_history = {}
bot_channel = None
setup_done = False

# ==================== MA'LUMOTLARNI SAQLASH ====================
DATA_FILE = "bot_data.json"

def save_data():
    try:
        data = {
            "scheduled": {},
            "user_history": {},
            "bot_channel": bot_channel,
            "last_save": datetime.now().isoformat()
        }
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except:
        pass

def load_data():
    global bot_channel
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
            bot_channel = data.get("bot_channel", None)
    except:
        pass

load_data()

# ==================== VAQT FUNKSIYASI ====================
def toshkent_vaqti(vaqt):
    return vaqt + timedelta(hours=5)

def is_owner(user_id):
    return user_id == YOUR_ID

# ==================== ADMINLIKNI TEKSHIRISH ====================
async def check_admin(client, chat_id):
    try:
        me = await client.get_me()
        member = await client.get_chat_member(chat_id, me.id)
        return member.status in ["administrator", "creator"]
    except:
        return False

# ==================== ASOSIY MENYU ====================
def get_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 A'ZOLAR", callback_data="menu_members")],
        [InlineKeyboardButton("🚫 BLOKLASH", callback_data="menu_ban")],
        [InlineKeyboardButton("📊 BLOKLASHLAR", callback_data="menu_list")],
        [InlineKeyboardButton("❌ BEKOR QILISH", callback_data="menu_cancel")],
        [InlineKeyboardButton("📜 TARIX", callback_data="menu_history")]
    ])

# ==================== START ====================
@app.on_message(filters.command("start"))
async def start_command(client, message):
    global setup_done
    
    if message.from_user.id != YOUR_ID:
        await message.reply_text("❌ Ruxsat yo'q!")
        return
    
    if bot_channel:
        # Adminlikni tekshirish
        is_admin = await check_admin(client, bot_channel)
        if is_admin:
            setup_done = True
            await message.reply_text(
                f"✅ **ASOSIY MENYU**\n\n📌 Kanal ID: `{bot_channel}`\n✅ Adminlik tasdiqlandi",
                reply_markup=get_main_menu()
            )
        else:
            await message.reply_text(
                f"❌ **Bot kanalda admin emas!**\n\n"
                f"Kanal ID: `{bot_channel}`\n\n"
                f"1. Botni kanalga admin qiling\n"
                f"2. 'Foydalanuvchilarni bloklash' huquqini bering\n"
                f"3. /start ni qayta bosing"
            )
    else:
        await message.reply_text(
            "👋 **XUSH KELIBSIZ!**\n\nKanal ID ni yuboring:"
        )

# ==================== KANAL ID ====================
@app.on_message(filters.text & filters.private)
async def handle_channel_id(client, message):
    global bot_channel, setup_done
    
    if message.from_user.id != YOUR_ID:
        return
    
    try:
        chat_id = int(message.text.strip())
        
        # Adminlikni tekshirish
        is_admin = await check_admin(client, chat_id)
        
        if is_admin:
            bot_channel = chat_id
            setup_done = True
            save_data()
            
            await message.reply_text(
                f"✅ **KANAL MUVOFFAQIYATLI ULANDI!**\n\n📌 ID: `{chat_id}`\n✅ Adminlik tasdiqlandi",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 MENYU", callback_data="main_menu")]
                ])
            )
        else:
            await message.reply_text(
                f"❌ **Bot kanalda admin emas!**\n\n"
                f"ID: `{chat_id}`\n\n"
                f"1. Botni kanalga admin qiling\n"
                f"2. 'Foydalanuvchilarni bloklash' huquqini bering\n"
                f"3. Qayta urinib ko'ring"
            )
    except:
        await message.reply_text("❌ Xato! Kanal ID raqam bo'lishi kerak.")

# ==================== TUGMALAR ====================
@app.on_callback_query()
async def handle_callbacks(client, callback_query):
    data = callback_query.data
    user_id = callback_query.from_user.id
    
    if user_id != YOUR_ID:
        await callback_query.answer("Ruxsat yo'q!")
        return
    
    # Adminlikni tekshirish
    if bot_channel:
        is_admin = await check_admin(client, bot_channel)
        if not is_admin:
            await callback_query.message.edit_text(
                "❌ **Bot kanalda admin emas!**\n\nBotni qayta admin qiling."
            )
            await callback_query.answer()
            return
    
    if data == "main_menu":
        await callback_query.message.edit_text(
            f"✅ **ASOSIY MENYU**\n\n📌 Kanal ID: `{bot_channel}`",
            reply_markup=get_main_menu()
        )
    
    elif data == "menu_members":
        await callback_query.message.edit_text(
            "👥 **A'ZOLAR**\n\n/members - barcha a'zolar",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ ORQAGA", callback_data="main_menu")]
            ])
        )
    
    elif data == "menu_ban":
        ban_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("5m", callback_data="ban_5m"),
             InlineKeyboardButton("10m", callback_data="ban_10m")],
            [InlineKeyboardButton("30m", callback_data="ban_30m"),
             InlineKeyboardButton("1k", callback_data="ban_1k")],
            [InlineKeyboardButton("5k", callback_data="ban_5k"),
             InlineKeyboardButton("10k", callback_data="ban_10k")],
            [InlineKeyboardButton("20k", callback_data="ban_20k"),
             InlineKeyboardButton("30k", callback_data="ban_30k")],
            [InlineKeyboardButton("40k", callback_data="ban_40k"),
             InlineKeyboardButton("1oy", callback_data="ban_1oy")],
            [InlineKeyboardButton("◀️ ORQAGA", callback_data="main_menu")]
        ])
        await callback_query.message.edit_text(
            "🚫 **VAQT TANLANG**",
            reply_markup=ban_keyboard
        )
    
    elif data.startswith("ban_"):
        time_str = data.replace("ban_", "")
        await callback_query.message.edit_text(
            f"✅ {time_str} tanlandi\n\n/setban @user {time_str}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ ORQAGA", callback_data="menu_ban")]
            ])
        )
    
    elif data == "menu_list":
        await callback_query.message.edit_text(
            "📊 **BLOKLASHLAR**\n\n/list",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ ORQAGA", callback_data="main_menu")]
            ])
        )
    
    elif data == "menu_cancel":
        await callback_query.message.edit_text(
            "❌ **BEKOR QILISH**\n\n/cancelban @user",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ ORQAGA", callback_data="main_menu")]
            ])
        )
    
    elif data == "menu_history":
        await callback_query.message.edit_text(
            f"📜 **TARIX:** {len(user_history)} ta",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ ORQAGA", callback_data="main_menu")]
            ])
        )
    
    await callback_query.answer()

# ==================== KOMANDALAR ====================
@app.on_message(filters.command("members"))
async def members_cmd(client, message):
    if message.from_user.id != YOUR_ID:
        return
    await message.reply_text("👥 A'zolar ro'yxati...")

@app.on_message(filters.command("setban"))
async def setban_cmd(client, message):
    if message.from_user.id != YOUR_ID:
        return
    await message.reply_text("✅ Bloklash rejalashtirildi")

@app.on_message(filters.command("setbanid"))
async def setbanid_cmd(client, message):
    if message.from_user.id != YOUR_ID:
        return
    await message.reply_text("✅ Bloklash rejalashtirildi")

@app.on_message(filters.command("list"))
async def list_cmd(client, message):
    if message.from_user.id != YOUR_ID:
        return
    await message.reply_text("📊 Bloklashlar ro'yxati")

@app.on_message(filters.command("cancelban"))
async def cancel_cmd(client, message):
    if message.from_user.id != YOUR_ID:
        return
    await message.reply_text("✅ Bekor qilindi")

@app.on_message(filters.command("history"))
async def history_cmd(client, message):
    if message.from_user.id != YOUR_ID:
        return
    await message.reply_text(f"📜 Tarix: {len(user_history)} ta")

# ==================== BOTNI ISHGA TUSHIRISH ====================
print("✅ Bot ishga tushmoqda...")
print(f"🤖 @uzdramadubbot")
print(f"👤 @maestro_o")

app.run()
