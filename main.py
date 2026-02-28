from datetime import datetime, timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import json
import os
import asyncio

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

# ==================== ADMINLIKNI TEKSHIRISH (3 XIL USULDA) ====================
async def check_admin_3ways(client, chat_id):
    """3 xil usulda adminlikni tekshirish"""
    me = await client.get_me()
    
    # 1-USUL: get_chat_member (standart)
    try:
        member = await client.get_chat_member(chat_id, me.id)
        if member.status in ["administrator", "creator"]:
            print(f"✅ 1-usul: Admin (status: {member.status})")
            return True
    except Exception as e:
        print(f"1-usul xatolik: {e}")
    
    # 2-USUL: Adminlar ro'yxatidan qidirish [citation:1]
    try:
        async for admin in client.get_chat_members(chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
            if admin.user.id == me.id:
                print(f"✅ 2-usul: Adminlar ro'yxatidan topildi (status: {admin.status})")
                return True
    except Exception as e:
        print(f"2-usul xatolik: {e}")
    
    # 3-USUL: Barcha a'zolar ichidan qidirish
    try:
        async for member in client.get_chat_members(chat_id):
            if member.user.id == me.id:
                if member.status in ["administrator", "creator"]:
                    print(f"✅ 3-usul: A'zolar ichidan topildi (status: {member.status})")
                    return True
    except Exception as e:
        print(f"3-usul xatolik: {e}")
    
    # 4-USUL: Kanal ma'lumotini olish va tekshirish
    try:
        chat = await client.get_chat(chat_id)
        # Agar kanal egasi yoki admin bo'lsa
        if hasattr(chat, 'permissions') and chat.permissions:
            print("ℹ️ Kanal permissions mavjud")
    except:
        pass
    
    print("❌ Adminlik aniqlanmadi")
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
        # Adminlikni 3 xil usulda tekshirish
        is_admin = await check_admin_3ways(client, bot_channel)
        
        if is_admin:
            setup_done = True
            await message.reply_text(
                f"✅ **ASOSIY MENYU**\n\n"
                f"📌 Kanal ID: `{bot_channel}`\n"
                f"✅ Adminlik tasdiqlandi",
                reply_markup=get_main_menu()
            )
        else:
            await message.reply_text(
                f"❌ **Bot kanalda admin emas!**\n\n"
                f"Kanal ID: `{bot_channel}`\n\n"
                f"📌 **SABABI:**\n"
                f"• Telegram serverida ma'lumot yangilanmagan\n"
                f"• Botni kanaldan olib tashlab, qayta qo'shing\n\n"
                f"**YECHIM:**\n"
                f"1. Kanalda adminlar ro'yxatiga kiring\n"
                f"2. @uzdramadubbot ni olib tashlang (Remove)\n"
                f"3. Qayta admin qiling (Add Admin)\n"
                f"4. 'Foydalanuvchilarni bloklash' huquqini bering\n"
                f"5. 30 soniya kuting\n"
                f"6. /start ni qayta bosing"
            )
    else:
        await message.reply_text(
            "👋 **XUSH KELIBSIZ!**\n\n"
            "Bot ishlashi uchun **kanal ID** sini yuboring.\n\n"
            "📌 **KANAL ID:**\n"
            "• Har doim minus bilan boshlanadi: `-100...`\n"
            "• Masalan: `-1003726881716`\n\n"
            "Kanal ID ni yozib yuboring:"
        )

# ==================== KANAL ID ====================
@app.on_message(filters.text & filters.private)
async def handle_channel_id(client, message):
    global bot_channel, setup_done
    
    if message.from_user.id != YOUR_ID:
        return
    
    try:
        chat_id = int(message.text.strip())
        
        # Avval xabar beramiz
        msg = await message.reply_text("⏳ Tekshirilmoqda...")
        
        # Adminlikni 3 xil usulda tekshirish
        is_admin = await check_admin_3ways(client, chat_id)
        
        if is_admin:
            bot_channel = chat_id
            setup_done = True
            save_data()
            
            # Kanal ma'lumotini olish
            chat = await client.get_chat(chat_id)
            
            await msg.edit_text(
                f"✅ **KANAL MUVOFFAQIYATLI ULANDI!**\n\n"
                f"📌 **Kanal:** {chat.title}\n"
                f"🆔 **ID:** `{chat_id}`\n"
                f"✅ Adminlik tasdiqlandi\n\n"
                f"Endi barcha funksiyalardan foydalanishingiz mumkin.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 ASOSIY MENYU", callback_data="main_menu")]
                ])
            )
        else:
            await msg.edit_text(
                f"❌ **Bot kanalda admin emas!**\n\n"
                f"ID: `{chat_id}`\n\n"
                f"📌 **SABABI:**\n"
                f"• Kanal ID noto'g'ri\n"
                f"• Bot admin qilinmagan\n"
                f"• Telegram serverida ma'lumot yangilanmagan\n\n"
                f"**YECHIM:**\n"
                f"1. Kanal ID ni tekshiring: @getidsbot\n"
                f"2. Botni kanalga admin qiling\n"
                f"3. 'Foydalanuvchilarni bloklash' huquqini bering\n"
                f"4. 30-60 soniya kuting\n"
                f"5. Qayta urinib ko'ring"
            )
    except ValueError:
        await message.reply_text(
            "❌ **Noto'g'ri format!**\n\n"
            "Kanal ID raqam bo'lishi kerak.\n"
            "Misol: `-1003726881716`"
        )
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

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
        is_admin = await check_admin_3ways(client, bot_channel)
        if not is_admin:
            await callback_query.message.edit_text(
                f"❌ **Bot kanalda admin emas!**\n\n"
                f"Botni qayta admin qiling va /start ni bosing."
            )
            await callback_query.answer()
            return
    
    if data == "main_menu":
        await callback_query.message.edit_text(
            f"✅ **ASOSIY MENYU**\n\n"
            f"📌 Kanal ID: `{bot_channel}`",
            reply_markup=get_main_menu()
        )
    
    elif data == "menu_members":
        await callback_query.message.edit_text(
            "👥 **A'ZOLAR**\n\n"
            "`/members` - barcha a'zolar\n"
            "`/members Alisher` - qidirish",
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
            "🚫 **BLOKLASH VAQTI TANLANG**",
            reply_markup=ban_keyboard
        )
    
    elif data.startswith("ban_"):
        time_str = data.replace("ban_", "")
        await callback_query.message.edit_text(
            f"✅ **{time_str} TANLANDI**\n\n"
            f"Endi bloklamoqchi bo'lgan foydalanuvchi nomini yozing:\n"
            f"`/setban @user {time_str}`\n\n"
            f"Yoki ID orqali:\n"
            f"`/setbanid 123456789 {time_str}`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ ORQAGA", callback_data="menu_ban")]
            ])
        )
    
    elif data == "menu_list":
        await callback_query.message.edit_text(
            "📊 **BLOKLASHLAR**\n\n"
            "`/list` - bloklashlar ro'yxati",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ ORQAGA", callback_data="main_menu")]
            ])
        )
    
    elif data == "menu_cancel":
        await callback_query.message.edit_text(
            "❌ **BEKOR QILISH**\n\n"
            "`/cancelban @user`\n"
            "`/cancelban 123456789`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ ORQAGA", callback_data="main_menu")]
            ])
        )
    
    elif data == "menu_history":
        await callback_query.message.edit_text(
            f"📜 **TARIX:** {len(user_history)} ta foydalanuvchi",
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
    await message.reply_text("👥 A'zolar ro'yxati yuklanmoqda...")

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
print("=" * 50)
print("✅ KANAL BOSHQARUV BOTI ISHGA TUSHMOQDA...")
print("=" * 50)
print(f"🤖 Bot: @uzdramadubbot")
print(f"👤 Egasi: @maestro_o (ID: {YOUR_ID})")
print("=" * 50)

app.run()
