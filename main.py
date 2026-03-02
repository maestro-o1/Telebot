from datetime import datetime, timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import asyncio
import threading
import json
import os
import time

# SOZLAMALAR
API_ID = 35058290
API_HASH = "d7cb549b10b8965c99673f8bd36c130a"
BOT_TOKEN = "8660286208:AAHssllobxtng0RDXfZ70fEkfFbjx13FyQE"

# ============= SIZNING ID INGIZ =============
YOUR_ID = 1700341163  # @maestro_o
# ===========================================

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Ma'lumotlar ombori
scheduled = {}  # {chat_id: {user_id: {...}}}
selected_channel = {}  # {user_id: {"chat_id": ..., "title": ...}}
user_history = {}  # {chat_id: {user_id: {...}}}
bot_channels = {}  # {chat_id: {"title": ..., "username": ...}}
last_check = {}  # Oxirgi tekshirish vaqtlari (duplicate oldini olish)
time_settings = {}  # {user_id: soat_farqi} - Vaqt sozlamalari
temp_data = {}  # Vaqtinchalik ma'lumotlar

# ==================== VAQT FUNKSIYALARI ====================
def local_time(user_id=None):
    """Foydalanuvchi uchun lokal vaqtni qaytarish"""
    utc_now = datetime.utcnow()
    soat_farqi = time_settings.get(user_id, 5) if user_id else 5  # Standart 5 (Toshkent)
    return utc_now + timedelta(hours=soat_farqi)

def format_time(dt, user_id=None):
    """Vaqtni formatlash (lokal vaqt bilan)"""
    if isinstance(dt, datetime):
        soat_farqi = time_settings.get(user_id, 5) if user_id else 5
        local_dt = dt + timedelta(hours=soat_farqi)
        return local_dt.strftime("%H:%M %d.%m.%Y")
    return "noma'lum"

def utc_to_local(dt, user_id=None):
    """UTC vaqtni lokal vaqtga o'tkazish"""
    if isinstance(dt, datetime):
        soat_farqi = time_settings.get(user_id, 5) if user_id else 5
        return dt + timedelta(hours=soat_farqi)
    return dt

# ==================== MA'LUMOTLARNI SAQLASH ====================
DATA_FILE = "bot_data.json"

def save_data():
    """Ma'lumotlarni faylga saqlash"""
    try:
        data = {
            "scheduled": {},
            "user_history": {},
            "time_settings": time_settings,
            "last_save": datetime.utcnow().isoformat()
        }
        
        # scheduled ma'lumotlarini saqlash
        for chat_id, users in scheduled.items():
            data["scheduled"][str(chat_id)] = {}
            for user_id, user_data in users.items():
                data["scheduled"][str(chat_id)][str(user_id)] = {
                    "username": user_data.get("username", ""),
                    "full_name": user_data.get("full_name", ""),
                    "time": user_data["time"].isoformat() if isinstance(user_data["time"], datetime) else user_data["time"],
                    "user_id": user_data["user_id"],
                    "join_time": user_data.get("join_time", datetime.utcnow()).isoformat() if isinstance(user_data.get("join_time"), datetime) else user_data.get("join_time", ""),
                    "permanent": user_data.get("permanent", False),
                    "chat_id": user_data.get("chat_id", chat_id)
                }
        
        # user_history ma'lumotlarini saqlash
        for chat_id, users in user_history.items():
            data["user_history"][str(chat_id)] = {}
            for user_id, hist_data in users.items():
                data["user_history"][str(chat_id)][str(user_id)] = {
                    "username": hist_data.get("username", ""),
                    "full_name": hist_data.get("full_name", ""),
                    "join_time": hist_data["join_time"].isoformat() if isinstance(hist_data["join_time"], datetime) else hist_data["join_time"],
                    "leave_time": hist_data.get("leave_time", "").isoformat() if isinstance(hist_data.get("leave_time"), datetime) else hist_data.get("leave_time", ""),
                    "status": hist_data.get("status", ""),
                    "scheduled_ban": hist_data.get("scheduled_ban", "").isoformat() if isinstance(hist_data.get("scheduled_ban"), datetime) else hist_data.get("scheduled_ban", ""),
                    "ban_time_str": hist_data.get("ban_time_str", ""),
                    "chat_id": hist_data.get("chat_id", chat_id),
                    "chat_title": hist_data.get("chat_title", "")
                }
        
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"✅ Ma'lumotlar saqlandi: {datetime.utcnow().strftime('%H:%M:%S')} UTC")
    except Exception as e:
        print(f"❌ Ma'lumotlarni saqlashda xatolik: {e}")

def load_data():
    """Ma'lumotlarni fayldan yuklash"""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
            
            # scheduled ma'lumotlarini yuklash
            for chat_id, users in data.get("scheduled", {}).items():
                scheduled[int(chat_id)] = {}
                for user_id, user_data in users.items():
                    scheduled[int(chat_id)][int(user_id)] = {
                        "username": user_data.get("username", ""),
                        "full_name": user_data.get("full_name", ""),
                        "time": datetime.fromisoformat(user_data["time"]),
                        "user_id": user_data["user_id"],
                        "join_time": datetime.fromisoformat(user_data["join_time"]) if user_data.get("join_time") else datetime.utcnow(),
                        "permanent": user_data.get("permanent", False),
                        "chat_id": user_data.get("chat_id", int(chat_id))
                    }
            
            # user_history ma'lumotlarini yuklash
            for chat_id, users in data.get("user_history", {}).items():
                user_history[int(chat_id)] = {}
                for user_id, hist_data in users.items():
                    user_history[int(chat_id)][int(user_id)] = {
                        "username": hist_data.get("username", ""),
                        "full_name": hist_data.get("full_name", ""),
                        "join_time": datetime.fromisoformat(hist_data["join_time"]),
                        "leave_time": datetime.fromisoformat(hist_data["leave_time"]) if hist_data.get("leave_time") else None,
                        "status": hist_data.get("status", ""),
                        "scheduled_ban": datetime.fromisoformat(hist_data["scheduled_ban"]) if hist_data.get("scheduled_ban") else None,
                        "ban_time_str": hist_data.get("ban_time_str", ""),
                        "chat_id": hist_data.get("chat_id", int(chat_id)),
                        "chat_title": hist_data.get("chat_title", "")
                    }
            
            # time_settings ni yuklash
            time_settings.update(data.get("time_settings", {}))
            
            print(f"✅ Ma'lumotlar yuklandi: {data.get('last_save', '')}")
    except Exception as e:
        print(f"❌ Ma'lumotlarni yuklashda xatolik: {e}")

# Yuklash
load_data()

# ==================== 60 KUNDAN KEYIN O'CHIRISH ====================
def clean_old_data():
    """60 kundan eski ma'lumotlarni o'chirish"""
    try:
        now = datetime.utcnow()
        cutoff = now - timedelta(days=60)
        cleaned = 0
        
        # scheduled dan o'chirish
        for chat_id in list(scheduled.keys()):
            for user_id in list(scheduled[chat_id].keys()):
                ban_time = scheduled[chat_id][user_id]["time"]
                if ban_time < cutoff:
                    del scheduled[chat_id][user_id]
                    cleaned += 1
        
        # user_history dan o'chirish
        for chat_id in list(user_history.keys()):
            for user_id in list(user_history[chat_id].keys()):
                hist = user_history[chat_id][user_id]
                join_time = hist.get("join_time")
                leave_time = hist.get("leave_time")
                
                if leave_time and leave_time < cutoff:
                    del user_history[chat_id][user_id]
                    cleaned += 1
                elif join_time and join_time < cutoff and hist.get("status") != "active":
                    del user_history[chat_id][user_id]
                    cleaned += 1
        
        if cleaned > 0:
            print(f"🧹 {cleaned} ta eski ma'lumot o'chirildi ({cutoff.strftime('%d.%m.%Y')})")
            save_data()
    except Exception as e:
        print(f"❌ Tozalashda xatolik: {e}")

# Har kuni tozalash
def cleanup_background():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def cleaner():
        while True:
            await asyncio.sleep(86400)  # 24 soat
            clean_old_data()
    
    loop.run_until_complete(cleaner())

cleanup_thread = threading.Thread(target=cleanup_background, daemon=True)
cleanup_thread.start()

# ==================== VAQTNI PARSE QILISH ====================
def parse_time(time_str):
    """Vaqt matnini minutlarga o'tkazish"""
    try:
        time_str = time_str.lower().strip()
        number = ''
        for char in time_str:
            if char.isdigit():
                number += char
            else:
                break
        
        if not number:
            return 366 * 24 * 60
            
        number = int(number)
        
        if 'k' in time_str:  # kun
            return number * 24 * 60
        elif 'm' in time_str:  # minut
            return number
        elif 'kun' in time_str:
            return number * 24 * 60
        elif 'oy' in time_str:
            return number * 30 * 24 * 60
        elif 'soat' in time_str:
            return number * 60
        elif 'minut' in time_str:
            return number
        else:
            return number * 24 * 60
    except:
        return 366 * 24 * 60

def is_owner(user_id):
    """Foydalanuvchi bot egasi ekanligini tekshirish"""
    return user_id == YOUR_ID

# ==================== BOT ADMINLIGINI TEKSHIRISH ====================
async def check_bot_admin(client, chat_id):
    """Bot adminligini tekshirish"""
    me = await client.get_me()
    
    try:
        member = await client.get_chat_member(chat_id, me.id)
        if member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            return True, member.status
    except:
        pass
    
    return False, None

# ==================== ASOSIY TUGMALAR ====================
def get_main_keyboard():
    """Asosiy menyu tugmalari"""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Kanallar", callback_data="menu_channels")],
        [InlineKeyboardButton("👥 A'zolar", callback_data="menu_members")],
        [InlineKeyboardButton("⏰ Bloklashlar", callback_data="menu_bans")],
        [InlineKeyboardButton("📊 Statistika", callback_data="menu_stats")],
        [InlineKeyboardButton("🕐 Vaqt sozlash", callback_data="menu_time")],
        [InlineKeyboardButton("❓ Yordam", callback_data="menu_help")]
    ])
    return keyboard

# ==================== VAQT SOZLASH ====================
@app.on_message(filters.command("settime"))
async def set_time_command(client, message):
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        current = time_settings.get(user_id, 5)
        await message.reply_text(
            f"🕐 **VAQT SOZLARI**\n\n"
            f"Hozirgi sozlamalar:\n"
            f"• UTC+{current} (Toshkent vaqti)\n"
            f"📅 Hozir: {local_time(user_id).strftime('%d.%m.%Y %H:%M:%S')}\n\n"
            f"O'zgartirish uchun:\n"
            f"`/settime 5` - Toshkent vaqti (UTC+5)\n"
            f"`/settime 0` - UTC (server vaqti)\n"
            f"`/settime 3` - Moskva vaqti (UTC+3)\n"
            f"`/settime 6` - Ashxobod vaqti (UTC+6)"
        )
        return
    
    try:
        soat_farqi = int(args[1])
        time_settings[user_id] = soat_farqi
        save_data()
        
        await message.reply_text(
            f"✅ **VAQT SOZLANDI!**\n\n"
            f"🕐 UTC+{soat_farqi}\n"
            f"📅 Hozir: {local_time(user_id).strftime('%d.%m.%Y %H:%M:%S')}\n\n"
            f"Endi barcha vaqtlar shu zonada ko'rsatiladi."
        )
    except:
        await message.reply_text("❌ Noto'g'ri format! Masalan: `/settime 5`")

# ==================== START ====================
@app.on_message(filters.command("start"))
async def start_command(client, message):
    user_id = message.from_user.id
    
    if is_owner(user_id):
        # Tanlangan kanallar ro'yxati
        channels_text = ""
        if selected_channel:
            channels_text = "\n".join([f"✅ {data['title']} (`{data['chat_id']}`)" for data in selected_channel.values()])
        else:
            channels_text = "❌ Hech qanday kanal tanlanmagan"
        
        # Vaqt sozlamasi
        soat_farqi = time_settings.get(user_id, 5)
        
        await message.reply_text(
            f"✅ **ABADIY BLOKLASH BOTI**\n\n"
            f"👋 Xush kelibsiz, @maestro_o!\n"
            f"🕐 Vaqt zonasi: UTC+{soat_farqi} (hozir: {local_time(user_id).strftime('%H:%M')})\n\n"
            f"📌 **FAOLLASHTIRILGAN KANALLAR:**\n{channels_text}\n\n"
            f"🔽 Quyidagi tugmalardan foydalaning:",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.reply_text("❌ Sizga ruxsat yo'q!")

# ==================== MENU HANDLERLARI ====================
@app.on_callback_query()
async def handle_menu(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if user_id != YOUR_ID:
        await callback_query.answer("Bu tugmalar faqat bot egasi uchun!")
        return
    
    data = callback_query.data
    
    # ===== KANAL TANLASH MENUSI =====
    if data == "menu_channels":
        text = "📢 **KANALLAR**\n\n"
        
        if selected_channel:
            for user, data in selected_channel.items():
                text += f"✅ {data['title']}\n`{data['chat_id']}`\n\n"
        else:
            text += "❌ Hech qanday kanal tanlanmagan\n\n"
        
        text += "🆕 **Yangi kanal qo'shish:**\n"
        text += "• Kanal ID sini yozing: `-100123456789`\n"
        text += "• Yoki /select komandasi: `/select -100123456789`"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
        await callback_query.answer()
    
    # ===== A'ZOLAR MENUSI =====
    elif data == "menu_members":
        if not selected_channel:
            await callback_query.answer("❌ Avval kanal qo'shing! ID yozing: -100...", show_alert=True)
            return
        
        # Oxirgi tanlangan kanal
        last_channel = list(selected_channel.values())[-1]
        temp_data[user_id] = {"action": "members", "chat_id": last_channel["chat_id"]}
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 Barcha a'zolar", callback_data="members_all")],
            [InlineKeyboardButton("📱 Username borlar", callback_data="members_with_username")],
            [InlineKeyboardButton("❌ Username yo'qlar", callback_data="members_without_username")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]
        ])
        
        await callback_query.message.edit_text(
            f"👥 **A'ZOLAR**\n\n"
            f"📌 Kanal: {last_channel['title']}\n"
            f"🆔 ID: `{last_channel['chat_id']}`\n\n"
            f"Qanday a'zolarni ko'rmoqchisiz?",
            reply_markup=keyboard
        )
        await callback_query.answer()
    
    # ===== BLOKLASHLAR MENUSI =====
    elif data == "menu_bans":
        if not selected_channel:
            await callback_query.answer("❌ Avval kanal qo'shing! ID yozing: -100...", show_alert=True)
            return
        
        last_channel = list(selected_channel.values())[-1]
        chat_id = last_channel["chat_id"]
        
        if chat_id in scheduled and scheduled[chat_id]:
            text = f"⏰ **REJALASHTIRILGAN BLOKLASHLAR**\n📌 {last_channel['title']}\n\n"
            now = datetime.utcnow()
            
            for user_id, data in scheduled[chat_id].items():
                sana = format_time(data["time"], user_id)
                qolgan = data["time"] - now
                
                if qolgan.days > 0:
                    qolgan_text = f"(qoldi: {qolgan.days} kun)"
                else:
                    qolgan_text = f"(qoldi: {qolgan.seconds//3600} soat)"
                
                text += f"• {data['full_name']} (@{data['username']})\n  {sana} {qolgan_text}\n\n"
            
            text += f"📊 Jami: {len(scheduled[chat_id])} ta"
        else:
            text = f"📭 **BLOKLASHLAR YO'Q**\n📌 {last_channel['title']}\n\nHech qanday bloklash rejalashtirilmagan."
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Yangi bloklash", callback_data="new_ban")],
            [InlineKeyboardButton("❌ Bloklashni bekor qilish", callback_data="cancel_ban_menu")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
        await callback_query.answer()
    
    # ===== STATISTIKA =====
    elif data == "menu_stats":
        total_channels = len(selected_channel)
        total_scheduled = sum(len(users) for users in scheduled.values())
        total_history = sum(len(users) for users in user_history.values())
        
        text = f"📊 **STATISTIKA**\n\n"
        text += f"📢 Kanallar: {total_channels} ta\n"
        text += f"⏰ Rejalashtirilgan bloklashlar: {total_scheduled} ta\n"
        text += f"📋 Tarixdagi foydalanuvchilar: {total_history} ta\n"
        text += f"🕐 Vaqt zonasi: UTC+{time_settings.get(user_id, 5)}\n"
        
        if os.path.exists(DATA_FILE):
            size = os.path.getsize(DATA_FILE) / 1024
            text += f"📁 Fayl hajmi: {size:.2f} KB\n"
        
        text += f"\n🕐 {local_time(user_id).strftime('%d.%m.%Y %H:%M:%S')}"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Yangilash", callback_data="menu_stats")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
        await callback_query.answer()
    
    # ===== VAQT SOZLASH MENUSI =====
    elif data == "menu_time":
        current = time_settings.get(user_id, 5)
        
        text = f"🕐 **VAQT SOZLASH**\n\n"
        text += f"Hozirgi sozlama: UTC+{current}\n"
        text += f"Hozirgi vaqt: {local_time(user_id).strftime('%d.%m.%Y %H:%M:%S')}\n\n"
        text += "Tanlang:"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🕐 UTC+0 (London)", callback_data="settime_0")],
            [InlineKeyboardButton("🕐 UTC+3 (Moskva)", callback_data="settime_3")],
            [InlineKeyboardButton("🕐 UTC+5 (Toshkent)", callback_data="settime_5")],
            [InlineKeyboardButton("🕐 UTC+6 (Ashxobod)", callback_data="settime_6")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
        await callback_query.answer()
    
    elif data.startswith("settime_"):
        soat_farqi = int(data.split("_")[1])
        time_settings[user_id] = soat_farqi
        save_data()
        
        await callback_query.message.edit_text(
            f"✅ **VAQT SOZLANDI!**\n\n"
            f"🕐 UTC+{soat_farqi}\n"
            f"📅 Hozir: {local_time(user_id).strftime('%d.%m.%Y %H:%M:%S')}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]
            ])
        )
        await callback_query.answer()
    
    # ===== YORDAM =====
    elif data == "menu_help":
        text = "❓ **YORDAM**\n\n"
        text += "**📌 KANAL QO'SHISH:**\n"
        text += "• ID ni yozing: `-100123456789`\n"
        text += "• Yoki: `/select -100123456789`\n\n"
        
        text += "**📌 KOMMANDALAR:**\n"
        text += "• `/start` - Botni ishga tushirish\n"
        text += "• `/settime 5` - Vaqtni sozlash\n"
        text += "• `/members` - A'zolar ro'yxati\n"
        text += "• `/list` - Bloklashlar ro'yxati\n"
        text += "• `/setban @user 30k` - Bloklash\n\n"
        
        text += "**⏰ VAQT FORMATLARI:**\n"
        text += "• `5m` - 5 minut\n"
        text += "• `30m` - 30 minut\n"
        text += "• `1k` - 1 kun\n"
        text += "• `30k` - 30 kun\n"
        text += "• `1oy` - 1 oy\n"
        text += "• `3oy` - 3 oy\n\n"
        
        text += "📌 @uzdramadubbot - Bot statusi"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
        await callback_query.answer()
    
    # ===== ORQAGA =====
    elif data == "back_to_main":
        channels_text = ""
        if selected_channel:
            channels_text = "\n".join([f"✅ {data['title']} (`{data['chat_id']}`)" for data in selected_channel.values()])
        else:
            channels_text = "❌ Hech qanday kanal tanlanmagan"
        
        soat_farqi = time_settings.get(user_id, 5)
        
        await callback_query.message.edit_text(
            f"✅ **ABADIY BLOKLASH BOTI**\n\n"
            f"👋 Xush kelibsiz, @maestro_o!\n"
            f"🕐 Vaqt zonasi: UTC+{soat_farqi} (hozir: {local_time(user_id).strftime('%H:%M')})\n\n"
            f"📌 **FAOLLASHTIRILGAN KANALLAR:**\n{channels_text}\n\n"
            f"🔽 Quyidagi tugmalardan foydalaning:",
            reply_markup=get_main_keyboard()
        )
        await callback_query.answer()
    
    # ===== MEMBERS SUBMENU =====
    elif data.startswith("members_"):
        await handle_members_submenu(client, callback_query)
    
    # ===== BAN MENUSI =====
    elif data == "new_ban":
        await callback_query.message.edit_text(
            "⏰ **YANGI BLOKLASH**\n\n"
            "Bloklamoqchi bo'lgan foydalanuvchi @username yoki ID sini yuboring:\n\n"
            "Misol: `@user` yoki `123456789`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Orqaga", callback_data="menu_bans")]
            ])
        )
        await callback_query.answer()
        temp_data[user_id] = {"action": "awaiting_ban_user"}
    
    elif data == "cancel_ban_menu":
        if not selected_channel:
            await callback_query.answer("❌ Avval kanal qo'shing!", show_alert=True)
            return
        
        last_channel = list(selected_channel.values())[-1]
        chat_id = last_channel["chat_id"]
        
        if chat_id in scheduled and scheduled[chat_id]:
            text = f"❌ **BLOKLASHNI BEKOR QILISH**\n📌 {last_channel['title']}\n\n"
            text += "Bekor qilmoqchi bo'lgan bloklashni tanlang:\n\n"
            
            keyboard = []
            for user_id, data in list(scheduled[chat_id].items())[:10]:
                btn_text = f"{data['full_name']} (@{data['username']})"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"confirm_cancel_{chat_id}_{user_id}")])
            
            keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="menu_bans")])
            
            await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await callback_query.answer("❌ Hech qanday bloklash yo'q!", show_alert=True)
        
        await callback_query.answer()
    
    elif data.startswith("confirm_cancel_"):
        parts = data.split("_")
        chat_id = int(parts[2])
        target_user_id = int(parts[3])
        
        if chat_id in scheduled and target_user_id in scheduled[chat_id]:
            user_data = scheduled[chat_id][target_user_id]
            del scheduled[chat_id][target_user_id]
            save_data()
            
            await callback_query.message.edit_text(
                f"✅ **BLOKLASH BEKOR QILINDI**\n\n"
                f"👤 {user_data['full_name']}\n"
                f"🆔 `{target_user_id}`\n"
                f"📱 @{user_data['username']}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Bloklashlar menyusi", callback_data="menu_bans")]
                ])
            )
        else:
            await callback_query.message.edit_text(
                "❌ Bloklash topilmadi!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Orqaga", callback_data="menu_bans")]
                ])
            )
        
        await callback_query.answer()
    
    # ===== BAN TUGMALARI (YANGI A'ZO UCHUN) =====
    elif data.startswith("ban_"):
        await handle_ban_callback(client, callback_query)
    
    elif data.startswith("skip_"):
        await handle_skip_callback(client, callback_query)
    
    # ===== USER TANLASH (MEMBERS DAN KEYIN) =====
    elif data.startswith("select_user_"):
        parts = data.split("_")
        target_user_id = int(parts[2])
        
        # Foydalanuvchi ma'lumotlarini olish
        chat_id = temp_data.get(user_id, {}).get("chat_id")
        if not chat_id or chat_id not in user_history:
            await callback_query.answer("❌ Ma'lumot topilmadi!", show_alert=True)
            return
        
        user_info = None
        for uid, data in user_history[chat_id].items():
            if uid == target_user_id:
                user_info = data
                break
        
        if not user_info:
            await callback_query.answer("❌ Foydalanuvchi topilmadi!", show_alert=True)
            return
        
        # Foydalanuvchi ma'lumotlarini ko'rsatish
        join_time = user_info.get('join_time', datetime.utcnow())
        join_time_str = format_time(join_time, user_id)
        
        text = f"👤 **FOYDALANUVCHI MA'LUMOTLARI**\n\n"
        text += f"👤 Ism: {user_info.get('full_name', 'noma\'lum')}\n"
        text += f"🆔 ID: `{target_user_id}`\n"
        text += f"📱 Username: {user_info.get('username', 'noma\'lum')}\n"
        text += f"📅 Qo'shilgan: {join_time_str}\n"
        
        if user_info.get('leave_time'):
            leave_time_str = format_time(user_info['leave_time'], user_id)
            text += f"📅 Ketgan: {leave_time_str}\n"
        
        text += f"📊 Holat: {user_info.get('status', 'noma\'lum')}\n"
        
        # Bloklash tugmalari
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏰ Bloklash", callback_data=f"ban_user_{chat_id}_{target_user_id}")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="members_all")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
        await callback_query.answer()
    
    # ===== BAN USER (MEMBERS DAN) =====
    elif data.startswith("ban_user_"):
        parts = data.split("_")
        chat_id = int(parts[2])
        target_user_id = int(parts[3])
        
        # Bloklash vaqtlarini ko'rsatish
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏱️ 5 minut", callback_data=f"exec_ban_{chat_id}_{target_user_id}_5m")],
            [InlineKeyboardButton("⏱️ 10 minut", callback_data=f"exec_ban_{chat_id}_{target_user_id}_10m")],
            [InlineKeyboardButton("⏱️ 30 minut", callback_data=f"exec_ban_{chat_id}_{target_user_id}_30m")],
            [InlineKeyboardButton("📅 1 kun", callback_data=f"exec_ban_{chat_id}_{target_user_id}_1k")],
            [InlineKeyboardButton("📅 5 kun", callback_data=f"exec_ban_{chat_id}_{target_user_id}_5k")],
            [InlineKeyboardButton("📅 10 kun", callback_data=f"exec_ban_{chat_id}_{target_user_id}_10k")],
            [InlineKeyboardButton("📅 20 kun", callback_data=f"exec_ban_{chat_id}_{target_user_id}_20k")],
            [InlineKeyboardButton("📅 30 kun", callback_data=f"exec_ban_{chat_id}_{target_user_id}_30k")],
            [InlineKeyboardButton("📅 40 kun", callback_data=f"exec_ban_{chat_id}_{target_user_id}_40k")],
            [InlineKeyboardButton("📆 1 oy", callback_data=f"exec_ban_{chat_id}_{target_user_id}_1oy")],
            [InlineKeyboardButton("📆 2 oy", callback_data=f"exec_ban_{chat_id}_{target_user_id}_2oy")],
            [InlineKeyboardButton("📆 3 oy", callback_data=f"exec_ban_{chat_id}_{target_user_id}_3oy")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data=f"select_user_{target_user_id}")]
        ])
        
        await callback_query.message.edit_text(
            f"⏰ **BLOKLASH VAQTINI TANLANG**\n\n"
            f"👤 Foydalanuvchi ID: `{target_user_id}`",
            reply_markup=keyboard
        )
        await callback_query.answer()
    
    # ===== EXECUTE BAN =====
    elif data.startswith("exec_ban_"):
        parts = data.split("_")
        chat_id = int(parts[2])
        target_user_id = int(parts[3])
        time_str = parts[4]
        
        await execute_ban(client, callback_query, chat_id, target_user_id, time_str)

async def handle_members_submenu(client, callback_query):
    """A'zolar submenyusini boshqarish"""
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    chat_id = temp_data.get(user_id, {}).get("chat_id")
    if not chat_id:
        await callback_query.answer("❌ Kanal topilmadi!", show_alert=True)
        return
    
    try:
        msg = await callback_query.message.edit_text("⏳ A'zolar yuklanmoqda...")
        
        members_with_username = []
        members_without_username = []
        
        async for member in client.get_chat_members(chat_id):
            user = member.user
            user_info = {
                "id": user.id,
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
                "username": user.username,
                "full_name": f"{user.first_name or ''} {user.last_name or ''}".strip()
            }
            
            if user.username:
                members_with_username.append(user_info)
            else:
                members_without_username.append(user_info)
            
            # Tarixga saqlash
            if chat_id not in user_history:
                user_history[chat_id] = {}
            
            if user.id not in user_history[chat_id]:
                user_history[chat_id][user.id] = {
                    "username": f"@{user.username}" if user.username else "username yo'q",
                    "full_name": user_info["full_name"],
                    "join_time": datetime.utcnow(),
                    "status": "active"
                }
        
        if data == "members_all":
            text = f"📋 **BARCHA A'ZOLAR**\n📌 {selected_channel[user_id]['title']}\n\n"
            text += f"**📊 JAMI: {len(members_with_username) + len(members_without_username)} ta a'zo**\n\n"
            
            # Tugmalar yaratish
            keyboard = []
            for i, user in enumerate(members_with_username[:10] + members_without_username[:10]):
                display = f"{user['full_name'][:20]} (@{user['username']})" if user['username'] else f"{user['full_name'][:20]} (username yo'q)"
                keyboard.append([InlineKeyboardButton(display, callback_data=f"select_user_{user['id']}")])
            
            keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="menu_members")])
            
            await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
        elif data == "members_with_username":
            text = f"📱 **USERNAME BORLAR ({len(members_with_username)})**\n📌 {selected_channel[user_id]['title']}\n\n"
            
            keyboard = []
            for i, user in enumerate(members_with_username[:20]):
                text += f"{i+1}. @{user['username']}\n   {user['full_name'][:30]}\n   ID: `{user['id']}`\n\n"
                if i < 10:
                    keyboard.append([InlineKeyboardButton(f"@{user['username']}", callback_data=f"select_user_{user['id']}")])
            
            text += f"\n📊 Jami: {len(members_with_username)} ta"
            keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="menu_members")])
            
            await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
        elif data == "members_without_username":
            text = f"❌ **USERNAME YO'QLAR ({len(members_without_username)})**\n📌 {selected_channel[user_id]['title']}\n\n"
            
            keyboard = []
            for i, user in enumerate(members_without_username[:20]):
                text += f"{i+1}. {user['full_name'][:30]}\n   ID: `{user['id']}`\n\n"
                if i < 10:
                    keyboard.append([InlineKeyboardButton(f"{user['full_name'][:20]}", callback_data=f"select_user_{user['id']}")])
            
            text += f"\n📊 Jami: {len(members_without_username)} ta"
            keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="menu_members")])
            
            await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    except Exception as e:
        await callback_query.message.edit_text(f"❌ Xatolik: {str(e)}")

async def handle_ban_callback(client, callback_query):
    """Bloklash tugmasi bosilganda"""
    data = callback_query.data
    parts = data.split('_')
    
    if len(parts) == 4:
        chat_id = int(parts[1])
        target_user_id = int(parts[2])
        time_str = parts[3]
    elif len(parts) == 3:
        target_user_id = int(parts[1])
        time_str = parts[2]
        
        chat_id = None
        for cid, users in user_history.items():
            if target_user_id in users:
                chat_id = cid
                break
        
        if not chat_id:
            await callback_query.answer("❌ Chat ID topilmadi!", show_alert=True)
            return
    else:
        await callback_query.answer("❌ Noto'g'ri format!", show_alert=True)
        return
    
    await execute_ban(client, callback_query, chat_id, target_user_id, time_str)

async def execute_ban(client, callback_query, chat_id, target_user_id, time_str):
    """Bloklashni amalga oshirish"""
    user_id = callback_query.from_user.id
    
    try:
        user = await client.get_users(target_user_id)
        username = f"@{user.username}" if user.username else "username yo'q"
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    except:
        username = "noma'lum"
        full_name = "noma'lum"
    
    minutes = parse_time(time_str)
    ban_time = datetime.utcnow() + timedelta(minutes=minutes)
    
    if chat_id not in scheduled:
        scheduled[chat_id] = {}
        
    scheduled[chat_id][target_user_id] = {
        "username": username,
        "full_name": full_name,
        "time": ban_time,
        "user_id": target_user_id,
        "join_time": user_history.get(chat_id, {}).get(target_user_id, {}).get("join_time", datetime.utcnow()),
        "permanent": True,
        "chat_id": chat_id
    }
    
    if chat_id in user_history and target_user_id in user_history[chat_id]:
        user_history[chat_id][target_user_id]["scheduled_ban"] = ban_time
        user_history[chat_id][target_user_id]["ban_time_str"] = time_str
    
    save_data()
    
    sana = format_time(ban_time, user_id)
    qoshilgan_vaqt = format_time(
        user_history.get(chat_id, {}).get(target_user_id, {}).get("join_time", datetime.utcnow()),
        user_id
    )
    
    # Kanal sarlavhasini olish
    channel_title = "noma'lum"
    for data in selected_channel.values():
        if data["chat_id"] == chat_id:
            channel_title = data["title"]
            break
    
    await callback_query.message.edit_text(
        f"✅ **BLOKLASH REJALASHTIRILDI!**\n\n"
        f"📌 **Kanal:** {channel_title}\n"
        f"🆔 **Kanal ID:** `{chat_id}`\n"
        f"👤 **Foydalanuvchi:** {full_name}\n"
        f"🆔 **ID:** `{target_user_id}`\n"
        f"📱 **Username:** {username}\n"
        f"📅 **Qo'shilgan vaqt:** {qoshilgan_vaqt}\n"
        f"⏰ **Bloklash vaqti:** {time_str}\n"
        f"📅 **Bloklanadigan sana:** {sana}\n"
        f"🚫 **Tur:** {time_str} dan keyin ABADIY bloklanadi",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Bloklashlar menyusi", callback_data="menu_bans")]
        ])
    )
    await callback_query.answer("✅ Bloklash rejalashtirildi!")

async def handle_skip_callback(client, callback_query):
    """Skip tugmasi bosilganda"""
    data = callback_query.data
    parts = data.split('_')
    user_id = callback_query.from_user.id
    
    if len(parts) == 3:
        chat_id = int(parts[1])
        target_user_id = int(parts[2])
    elif len(parts) == 2:
        target_user_id = int(parts[1])
        chat_id = None
        for cid, users in user_history.items():
            if target_user_id in users:
                chat_id = cid
                break
        
        if not chat_id:
            await callback_query.answer("❌ Chat ID topilmadi!", show_alert=True)
            return
    else:
        await callback_query.answer("❌ Noto'g'ri format!", show_alert=True)
        return
    
    full_name = user_history.get(chat_id, {}).get(target_user_id, {}).get("full_name", "noma'lum")
    username = user_history.get(chat_id, {}).get(target_user_id, {}).get("username", "noma'lum")
    qoshilgan_vaqt = format_time(
        user_history.get(chat_id, {}).get(target_user_id, {}).get("join_time", datetime.utcnow()),
        user_id
    )
    
    # Kanal sarlavhasini olish
    channel_title = "noma'lum"
    for data in selected_channel.values():
        if data["chat_id"] == chat_id:
            channel_title = data["title"]
            break
    
    await callback_query.message.edit_text(
        f"❌ **BLOKLASH BEKOR QILINDI**\n\n"
        f"📌 **Kanal:** {channel_title}\n"
        f"🆔 **Kanal ID:** `{chat_id}`\n"
        f"👤 **Foydalanuvchi:** {full_name}\n"
        f"🆔 **ID:** `{target_user_id}`\n"
        f"📱 **Username:** {username}\n"
        f"📅 **Qo'shilgan vaqt:** {qoshilgan_vaqt}\n\n"
        f"✅ Hech qanday bloklash rejalashtirilmadi",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Asosiy menyu", callback_data="back_to_main")]
        ])
    )
    await callback_query.answer("❌ Bekor qilindi")

# ==================== YANGI FOYDALANUVCHI QO'SHILGANDA (TO'G'IRLANGAN) ====================
@app.on_chat_member_updated()
async def on_chat_member_update(client, chat_member_updated):
    """Kanalga yangi odam qo'shilganda habar berish (DUPLICATE NI OLDINI OLISH)"""
    
    # MUHIM: Faqat kanallarni tekshirish
    chat = chat_member_updated.chat
    if chat.type not in [enums.ChatType.CHANNEL, enums.ChatType.SUPERGROUP]:
        return
    
    # Yangi a'zo qo'shilganini tekshirish
    new_member = chat_member_updated.new_chat_member
    old_member = chat_member_updated.old_chat_member
    
    # DUPLICATE NI OLDINI OLISH:
    # 1. Agar old va yangi holat bir xil bo'lsa -> ignore
    if old_member and new_member and old_member.status == new_member.status:
        return
    
    # 2. Faqat "member" bo'lganlarni tekshirish (creator/administrator emas)
    if not new_member or new_member.status not in [enums.ChatMemberStatus.MEMBER]:
        return
    
    # 3. Agar oldingi holat ham MEMBER bo'lsa -> ignore (bu yangilanish emas)
    if old_member and old_member.status == enums.ChatMemberStatus.MEMBER:
        return
    
    # 4. Faqat RESTRICTED dan MEMBER ga o'tishlarni ham ignore qilish
    if old_member and old_member.status == enums.ChatMemberStatus.RESTRICTED:
        return
    
    user = new_member.user
    
    # Botlarni ignore qilish
    if user.is_bot:
        return
    
    # Bot adminligini tekshirish
    is_admin, _ = await check_bot_admin(client, chat.id)
    if not is_admin:
        return
    
    # UNIKAL KALIT YARATISH (cache uchun)
    cache_key = f"{chat.id}_{user.id}"
    current_time = time.time()
    
    # 5. So'nggi 10 soniyada xuddi shu hodisa bo'lganmi?
    if cache_key in last_check:
        if current_time - last_check[cache_key] < 10:
            print(f"⏭️ Duplicate habar oldini olindi: {user.id}")
            return
    
    # Vaqtni saqlash
    last_check[cache_key] = current_time
    
    user_id = user.id
    username = f"@{user.username}" if user.username else "username yo'q"
    first_name = user.first_name or ""
    last_name = user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()
    join_time = datetime.utcnow()
    
    print(f"✅ Yangi a'zo qo'shildi: {full_name} ({user_id}) - {chat.title}")
    
    # Foydalanuvchi tarixini saqlash
    if chat.id not in user_history:
        user_history[chat.id] = {}
        
    user_history[chat.id][user_id] = {
        "username": username,
        "full_name": full_name,
        "join_time": join_time,
        "leave_time": None,
        "status": "active",
        "chat_id": chat.id,
        "chat_title": chat.title
    }
    save_data()
    
    # Tugmalar
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏱️ 5 minut", callback_data=f"ban_{chat.id}_{user_id}_5m")],
        [InlineKeyboardButton("⏱️ 10 minut", callback_data=f"ban_{chat.id}_{user_id}_10m")],
        [InlineKeyboardButton("⏱️ 30 minut", callback_data=f"ban_{chat.id}_{user_id}_30m")],
        [InlineKeyboardButton("📅 1 kun", callback_data=f"ban_{chat.id}_{user_id}_1k")],
        [InlineKeyboardButton("📅 5 kun", callback_data=f"ban_{chat.id}_{user_id}_5k")],
        [InlineKeyboardButton("📅 10 kun", callback_data=f"ban_{chat.id}_{user_id}_10k")],
        [InlineKeyboardButton("📅 20 kun", callback_data=f"ban_{chat.id}_{user_id}_20k")],
        [InlineKeyboardButton("📅 30 kun", callback_data=f"ban_{chat.id}_{user_id}_30k")],
        [InlineKeyboardButton("📅 40 kun", callback_data=f"ban_{chat.id}_{user_id}_40k")],
        [InlineKeyboardButton("📆 1 oy", callback_data=f"ban_{chat.id}_{user_id}_1oy")],
        [InlineKeyboardButton("📆 2 oy", callback_data=f"ban_{chat.id}_{user_id}_2oy")],
        [InlineKeyboardButton("📆 3 oy", callback_data=f"ban_{chat.id}_{user_id}_3oy")],
        [InlineKeyboardButton("❌ Bloklamaslik", callback_data=f"skip_{chat.id}_{user_id}")]
    ])
    
    await client.send_message(
        YOUR_ID,
        f"👤 **YANGI A'ZO QO'SHILDI!**\n\n"
        f"📌 **Kanal:** {chat.title}\n"
        f"🆔 **Kanal ID:** `{chat.id}`\n"
        f"👤 **Foydalanuvchi:** {full_name}\n"
        f"🆔 **ID:** `{user_id}`\n"
        f"📱 **Username:** {username}\n"
        f"🔗 **Profil:** tg://user?id={user_id}\n\n"
        f"⏰ **Qo'shilgan vaqt:** {format_time(join_time, YOUR_ID)}",
        reply_markup=keyboard
    )

# ==================== @uzdramadubbot GA JAVOB ====================
@app.on_message(filters.text & filters.regex(r"^@uzdramadubbot$"))
async def bot_mention(client, message):
    """@uzdramadubbot yozilsa javob berish"""
    user_id = message.from_user.id
    chat = message.chat
    
    if chat.type == enums.ChatType.PRIVATE:
        if is_owner(user_id):
            channels_text = ""
            if selected_channel:
                channels_text = "\n".join([f"✅ {data['title']} (`{data['chat_id']}`)" for data in selected_channel.values()])
            else:
                channels_text = "❌ Hech qanday kanal tanlanmagan"
            
            soat_farqi = time_settings.get(user_id, 5)
            
            await message.reply_text(
                f"✅ **BOT ISHGA TUSHDI!**\n\n"
                f"📌 **FAOLLASHTIRILGAN KANALLAR:**\n{channels_text}\n\n"
                f"🕐 Vaqt zonasi: UTC+{soat_farqi}\n\n"
                f"🔽 Tugmalardan foydalaning:",
                reply_markup=get_main_keyboard()
            )
        else:
            await message.reply_text("🤖 Bu bot faqat egasi uchun!")
    
    elif chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        is_admin, status = await check_bot_admin(client, chat.id)
        
        if is_admin:
            await message.reply_text(f"✅ **Bot bu guruhda admin!**\nStatus: {status}")
        else:
            await message.reply_text(f"❌ **Bot bu guruhda admin emas!**")

# ==================== BOShQA XABARLARGA JAVOB (ID NI USHLASH) ====================
@app.on_message()
async def handle_other_messages(client, message):
    """Boshqa xabarlarni boshqarish (ID ni ushlash)"""
    if message.chat.type != enums.ChatType.PRIVATE:
        return
    
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        return
    
    if message.text and message.text.startswith('/'):
        return
    
    if message.text and message.text == "@uzdramadubbot":
        return
    
    if not message.text:
        return
    
    text = message.text.strip()
    
    # Kanal ID formatini tekshirish (-100... yoki 100...)
    if (text.startswith('-') and text[1:].isdigit()) or text.isdigit():
        try:
            chat_id = int(text)
            
            msg = await message.reply_text("⏳ Tekshirilmoqda...")
            
            try:
                chat = await client.get_chat(chat_id)
            except Exception as e:
                await msg.edit_text(
                    f"❌ **KANAL TOPILMADI!**\n\n"
                    f"ID: `{chat_id}`\n"
                    f"Sabab: {str(e)}\n\n"
                    f"📌 Tekshirib ko'ring:\n"
                    f"• ID to'g'ri yozilganmi?\n"
                    f"• Kanal mavjudmi?\n"
                    f"• Bot kanalga qo'shilganmi?"
                )
                return
            
            is_admin, admin_status = await check_bot_admin(client, chat_id)
            
            if not is_admin:
                await msg.edit_text(
                    f"❌ **BOT ADMIN EMAS!**\n\n"
                    f"📌 **Kanal:** {chat.title}\n"
                    f"🆔 **ID:** `{chat_id}`\n\n"
                    f"**Sabab:** Bot kanalda admin emas\n\n"
                    f"✅ **Yechim:**\n"
                    f"1. Kanalga o'ting\n"
                    f"2. Adminlar ro'yxatini oching\n"
                    f"3. @uzdramadubbot ni admin qiling\n"
                    f"4. 'Foydalanuvchilarni bloklash' huquqini bering\n"
                    f"5. 10 soniya kuting va ID ni qayta yozing"
                )
                return
            
            selected_channel[user_id] = {
                "chat_id": chat.id,
                "title": chat.title
            }
            
            members_count = chat.members_count if hasattr(chat, 'members_count') else "noma'lum"
            
            await msg.edit_text(
                f"✅ **KANAL MUVOFFAQIYATLI QO'SHILDI!**\n\n"
                f"📌 **Nomi:** {chat.title}\n"
                f"🆔 **ID:** `{chat.id}`\n"
                f"👥 **A'zolar:** {members_count}\n"
                f"🤖 **Bot status:** {admin_status}\n\n"
                f"📊 Endi bot to'liq ishlashga tayyor!\n"
                f"👥 A'zolar tugmasi orqali foydalanuvchilarni ko'ring.",
                reply_markup=get_main_keyboard()
            )
            
        except Exception as e:
            await message.reply_text(f"❌ Xatolik: {str(e)}")

# ==================== SELECT (ESKI USUL) ====================
@app.on_message(filters.command("select"))
async def select_channel_command(client, message):
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    args = message.text.split()
    
    if len(args) < 2:
        await message.reply_text(
            f"❌ **Kanal ID sini yozing!**\n\n"
            f"📌 Masalan: `/select -100123456789`\n"
            f"Yoki oddiygina ID ni o'zini yozing: `-100123456789`"
        )
        return
    
    try:
        chat_id = int(args[1])
        
        msg = await message.reply_text("⏳ Tekshirilmoqda...")
        
        try:
            chat = await client.get_chat(chat_id)
        except Exception as e:
            await msg.edit_text(f"❌ Kanal topilmadi! Xatolik: {str(e)}")
            return
        
        is_admin, admin_status = await check_bot_admin(client, chat_id)
        
        if not is_admin:
            await msg.edit_text(
                f"❌ **Bot admin emas!**\n\n"
                f"Kanal: {chat.title}\n"
                f"ID: `{chat_id}`\n\n"
                f"📌 **YECHIM:**\n"
                f"1. Kanalda adminlar ro'yxatini oching\n"
                f"2. @uzdramadubbot ni toping\n"
                f"3. Admin qiling va 'Foydalanuvchilarni bloklash' huquqini bering\n"
                f"4. 30 soniya kuting\n"
                f"5. /select {chat_id} ni qayta bosing"
            )
            return
        
        selected_channel[user_id] = {
            "chat_id": chat.id,
            "title": chat.title
        }
        
        members_count = chat.members_count if hasattr(chat, 'members_count') else "noma'lum"
        
        await msg.edit_text(
            f"✅ **KANAL TANLANDI!**\n\n"
            f"📌 **Nomi:** {chat.title}\n"
            f"🆔 **ID:** `{chat.id}`\n"
            f"👥 **A'zolar:** {members_count}\n"
            f"🤖 **Bot status:** {admin_status}\n\n"
            f"📋 **Endi tugmalardan foydalanishingiz mumkin!**",
            reply_markup=get_main_keyboard()
        )
        
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

# ==================== MEMBERS (ESKI USUL) ====================
@app.on_message(filters.command("members"))
async def get_members_command(client, message):
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    if user_id not in selected_channel:
        await message.reply_text("❌ Avval kanal qo'shing! ID yozing: -100...")
        return
    
    chat_id = selected_channel[user_id]["chat_id"]
    
    msg = await message.reply_text("⏳ A'zolar yuklanmoqda...")
    
    try:
        members_with_username = []
        members_without_username = []
        
        async for member in client.get_chat_members(chat_id):
            user = member.user
            user_info = {
                "id": user.id,
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
                "username": user.username,
                "full_name": f"{user.first_name or ''} {user.last_name or ''}".strip()
            }
            
            if user.username:
                members_with_username.append(user_info)
            else:
                members_without_username.append(user_info)
        
        text = f"📋 **KANAL A'ZOLARI**\n📌 {selected_channel[user_id]['title']}\n\n"
        
        text += f"**📱 USERNAME BORLAR ({len(members_with_username)}):**\n"
        for i, user in enumerate(members_with_username[:20]):
            text += f"{i+1}. @{user['username']}\n"
            text += f"   ID: `{user['id']}`\n"
            text += f"   {user['full_name'][:30]}\n\n"
        
        text += f"**❌ USERNAME YO'QLAR ({len(members_without_username)}):**\n"
        for i, user in enumerate(members_without_username[:20]):
            text += f"{i+1}. {user['full_name'][:30]}\n"
            text += f"   ID: `{user['id']}`\n\n"
        
        text += f"\n📊 **JAMI: {len(members_with_username) + len(members_without_username)} ta a'zo**"
        
        await msg.edit_text(text)
        
    except Exception as e:
        await msg.edit_text(f"❌ Xatolik: {str(e)}")

# ==================== SETBAN ====================
@app.on_message(filters.command("setban"))
async def set_ban_command(client, message):
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return

    args = message.text.split()
    if len(args) < 3:
        await message.reply_text(
            "❌ **Noto'g'ri format!**\n\n"
            "Misol: `/setban @user 30k`"
        )
        return

    username = args[1].replace("@", "")
    time_str = args[2]

    try:
        user = await client.get_users(username)
        
        if user_id not in selected_channel:
            await message.reply_text("❌ Avval kanal qo'shing! ID yozing: -100...")
            return
        
        chat_id = selected_channel[user_id]["chat_id"]
        
        minutes = parse_time(time_str)
        ban_time = datetime.utcnow() + timedelta(minutes=minutes)
        
        if chat_id not in scheduled:
            scheduled[chat_id] = {}
            
        scheduled[chat_id][user.id] = {
            "username": username,
            "full_name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
            "time": ban_time,
            "user_id": user.id,
            "join_time": datetime.utcnow(),
            "permanent": True,
            "chat_id": chat_id
        }
        
        save_data()
        
        sana = format_time(ban_time, user_id)
        
        await message.reply_text(
            f"✅ **BLOKLASH REJALASHTIRILDI**\n\n"
            f"👤 **Foydalanuvchi:** @{username}\n"
            f"🆔 **ID:** `{user.id}`\n"
            f"⏰ **Vaqt:** {time_str}\n"
            f"📅 **Sana:** {sana}\n"
            f"🚫 **Tur:** {time_str} dan keyin ABADIY bloklanadi",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Asosiy menyu", callback_data="back_to_main")]
            ])
        )

    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

# ==================== SETBANID ====================
@app.on_message(filters.command("setbanid"))
async def set_ban_by_id_command(client, message):
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    args = message.text.split()
    if len(args) < 3:
        await message.reply_text("❌ /setbanid 123456789 30k")
        return
    
    try:
        target_user_id = int(args[1])
        time_str = args[2]
        
        if user_id not in selected_channel:
            await message.reply_text("❌ Avval kanal qo'shing! ID yozing: -100...")
            return
        
        chat_id = selected_channel[user_id]["chat_id"]
        
        user = await client.get_users(target_user_id)
        
        minutes = parse_time(time_str)
        ban_time = datetime.utcnow() + timedelta(minutes=minutes)
        
        if chat_id not in scheduled:
            scheduled[chat_id] = {}
            
        scheduled[chat_id][user.id] = {
            "username": user.username or f"ID:{user.id}",
            "full_name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
            "time": ban_time,
            "user_id": user.id,
            "join_time": datetime.utcnow(),
            "permanent": True,
            "chat_id": chat_id
        }
        
        save_data()
        
        sana = format_time(ban_time, user_id)
        
        display_name = f"@{user.username}" if user.username else user.first_name
        
        await message.reply_text(
            f"✅ **BLOKLASH REJALASHTIRILDI**\n\n"
            f"👤 **Foydalanuvchi:** {display_name}\n"
            f"🆔 **ID:** `{user.id}`\n"
            f"⏰ **Vaqt:** {time_str}\n"
            f"📅 **Sana:** {sana}\n"
            f"🚫 **Tur:** {time_str} dan keyin ABADIY bloklanadi",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Asosiy menyu", callback_data="back_to_main")]
            ])
        )
        
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

# ==================== LIST ====================
@app.on_message(filters.command("list"))
async def list_bans_command(client, message):
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    if user_id not in selected_channel:
        await message.reply_text("❌ Avval kanal qo'shing! ID yozing: -100...")
        return
    
    chat_id = selected_channel[user_id]["chat_id"]
    
    if chat_id not in scheduled or not scheduled[chat_id]:
        await message.reply_text("📭 Bloklashlar yo'q")
        return

    text = f"📋 **REJALASHTIRILGAN BLOKLASHLAR**\n📌 {selected_channel[user_id]['title']}\n\n"
    now = datetime.utcnow()
    
    for data in scheduled[chat_id].values():
        sana = format_time(data["time"], user_id)
        
        qolgan = data["time"] - now
        if qolgan.days > 0:
            qolgan_text = f"(qoldi: {qolgan.days} kun)"
        else:
            qolgan_text = f"(qoldi: {qolgan.seconds//3600} soat)"
        
        text += f"• {data['full_name']} (@{data['username']}) - {sana} {qolgan_text}\n"
    
    text += f"\n📊 Jami: {len(scheduled[chat_id])} ta"
    await message.reply_text(text)

# ==================== HISTORY ====================
@app.on_message(filters.command("history"))
async def show_history_command(client, message):
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    if not user_history:
        await message.reply_text("📭 Hech qanday ma'lumot yo'q")
        return
    
    text = "📋 **FOYDALANUVCHILAR TARIXI**\n\n"
    
    for chat_id, users in list(user_history.items())[:5]:
        channel_title = "noma'lum"
        for data in selected_channel.values():
            if data["chat_id"] == chat_id:
                channel_title = data["title"]
                break
        
        text += f"📌 **{channel_title}** (`{chat_id}`)\n"
        
        for uid, data in list(users.items())[:5]:
            join_time = format_time(data.get("join_time", datetime.utcnow()), user_id)
            leave_time = data.get("leave_time", "Hali ketmagan")
            if isinstance(leave_time, datetime):
                leave_time = format_time(leave_time, user_id)
            
            status_emoji = "✅" if data.get("status") == "active" else "❌"
            
            text += f"{status_emoji} **ID:** `{uid}`\n"
            text += f"   👤 {data.get('full_name', 'noma\'lum')}\n"
            text += f"   📱 {data.get('username', 'noma\'lum')}\n"
            text += f"   📅 Qo'shilgan: {join_time}\n"
            
            if data.get("scheduled_ban"):
                if isinstance(data["scheduled_ban"], datetime):
                    ban_time = format_time(data["scheduled_ban"], user_id)
                    text += f"   ⏰ Bloklanadi: {ban_time} ({data.get('ban_time_str', 'noma\'lum')})\n"
            
            text += "\n"
        
        text += "---\n\n"
    
    text += f"\n📊 Jami: {sum(len(users) for users in user_history.values())} ta foydalanuvchi"
    await message.reply_text(text)

# ==================== CANCELBAN ====================
@app.on_message(filters.command("cancelban"))
async def cancel_ban_command(client, message):
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.reply_text("❌ /cancelban @user yoki /cancelban [user_id]")
        return

    identifier = args[1].replace("@", "")
    
    if user_id not in selected_channel:
        await message.reply_text("❌ Avval kanal qo'shing! ID yozing: -100...")
        return
    
    chat_id = selected_channel[user_id]["chat_id"]
    
    try:
        if identifier.isdigit():
            user_id_target = int(identifier)
            user = await client.get_users(user_id_target)
        else:
            user = await client.get_users(identifier)
        
        if chat_id in scheduled and user.id in scheduled[chat_id]:
            user_data = scheduled[chat_id][user.id]
            del scheduled[chat_id][user.id]
            save_data()
            await message.reply_text(f"✅ Bloklash bekor qilindi: {user_data['full_name']}")
        else:
            await message.reply_text(f"❌ Topilmadi")
            
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

# ==================== VAQTLI BLOKLASH TEKSHIRUVI ====================
def check_bans_background():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def check():
        while True:
            try:
                now = datetime.utcnow()
                for chat_id in list(scheduled.keys()):
                    for user_id in list(scheduled[chat_id].keys()):
                        if now >= scheduled[chat_id][user_id]["time"]:
                            try:
                                data = scheduled[chat_id][user_id]
                                print(f"⏰ Abadiy bloklash vaqti keldi: {data['full_name']}")
                                
                                until_date = now + timedelta(days=366)
                                await app.ban_chat_member(chat_id, user_id, until_date=until_date)
                                
                                if chat_id in user_history and user_id in user_history[chat_id]:
                                    user_history[chat_id][user_id]["leave_time"] = now
                                    user_history[chat_id][user_id]["status"] = "banned"
                                
                                join_time = data.get("join_time", now)
                                join_str = format_time(join_time, YOUR_ID)
                                ban_str = format_time(now, YOUR_ID)
                                
                                time_in_channel = now - join_time if isinstance(join_time, datetime) else timedelta(0)
                                days = time_in_channel.days
                                hours = time_in_channel.seconds // 3600
                                
                                if days > 0:
                                    time_str = f"{days} kun {hours} soat"
                                else:
                                    time_str = f"{hours} soat"
                                
                                print(f"✅ ABADIY bloklandi: {data['full_name']}")
                                
                                try:
                                    await app.send_message(
                                        YOUR_ID,
                                        f"🚫 **FOYDALANUVCHI BLOKLANDI!**\n\n"
                                        f"📌 **Kanal ID:** `{chat_id}`\n"
                                        f"👤 **Foydalanuvchi:** {data['full_name']}\n"
                                        f"🆔 **ID:** `{user_id}`\n"
                                        f"📱 **Username:** {data['username']}\n"
                                        f"📅 **Qo'shilgan vaqt:** {join_str}\n"
                                        f"📅 **Bloklangan vaqt:** {ban_str}\n"
                                        f"⏱️ **Kanalda bo'lgan vaqt:** {time_str}\n"
                                        f"🚫 **Holat:** ABADIY bloklandi"
                                    )
                                except:
                                    pass
                                
                                del scheduled[chat_id][user_id]
                                save_data()
                                
                            except Exception as e:
                                print(f"❌ Bloklash xatosi: {e}")
            except Exception as e:
                print(f"Tekshirish xatosi: {e}")
            await asyncio.sleep(60)
    
    loop.run_until_complete(check())

# Har soatda ma'lumotlarni saqlash
def auto_save_background():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def auto_save():
        while True:
            await asyncio.sleep(3600)  # 1 soat
            save_data()
    
    loop.run_until_complete(auto_save())

# Threadlarni ishga tushirish
ban_thread = threading.Thread(target=check_bans_background, daemon=True)
ban_thread.start()

save_thread = threading.Thread(target=auto_save_background, daemon=True)
save_thread.start()

print("=" * 60)
print("✅ ABADIY BLOKLASH BOTI ISHGA TUSHDI!")
print("=" * 60)
print(f"🤖 Bot: @uzdramadubbot")
print(f"👤 Egasi: @maestro_o (ID: {YOUR_ID})")
print("=" * 60)
print("📋 **YANGI XUSUSIYATLAR:**")
print("   • Kanal ID ni o'zi yozilsa qo'shiladi")
print("   • Vaqtni sozlash imkoniyati (/settime 5)")
print("   • Tugmalar bilan to'liq boshqarish")
print("   • Aniq xatolik habarlari")
print("   • DUPLICATE HABARLAR OLDINI OLINGAN!")
print("=" * 60)

app.run()
