from datetime import datetime, timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import asyncio
import threading
import json
import os
import time
import hashlib
from collections import defaultdict

# SOZLAMALAR - ENVIRONMENT VARIABLES
API_ID = int(os.environ.get("API_ID", 35058290))
API_HASH = os.environ.get("API_HASH", "d7cb549b10b8965c99673f8bd36c130a")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8660286208:AAHssllobxtng0RDXfZ70fEkfFbjx13FyQE")

# ============= SIZNING ID INGIZ =============
YOUR_ID = 1700341163  # @maestro_o (ADMIN)
# ===========================================

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ==================== MA'LUMOTLAR OMBIORI ====================
AUTHORIZED_USERS = [YOUR_ID]  # Ruxsat berilgan foydalanuvchilar
user_channels = {}  # {user_id: {"chat_id": ..., "title": ...}} - har bir user o'z kanali
all_channels = {}   # {chat_id: {"owner_id": ..., "title": ...}} - barcha kanallar
scheduled = {}      # {chat_id: {user_id: {...}}} - rejalashtirilgan bloklashlar
user_history = {}   # {chat_id: {user_id: {...}}} - foydalanuvchilar tarixi
time_settings = {}  # {user_id: soat_farqi} - vaqt sozlamalari
temp_data = {}      # vaqtinchalik ma'lumotlar (action va boshqalar)
last_check = {}     # duplicate habarlar uchun
processed_events = defaultdict(lambda: {"time": 0, "count": 0})  # event dublikatlarini bloklash

# ==================== VAQT FUNKSIYALARI ====================
def local_time(user_id=None):
    """Foydalanuvchi uchun lokal vaqtni qaytarish"""
    utc_now = datetime.utcnow()
    soat_farqi = time_settings.get(user_id, 5) if user_id else 5
    return utc_now + timedelta(hours=soat_farqi)

def format_time(dt, user_id=None):
    """Vaqtni formatlash (lokal vaqt bilan)"""
    if isinstance(dt, datetime):
        soat_farqi = time_settings.get(user_id, 5) if user_id else 5
        local_dt = dt + timedelta(hours=soat_farqi)
        return local_dt.strftime("%H:%M %d.%m.%Y")
    return "noma'lum"

# ==================== MA'LUMOTLARNI SAQLASH ====================
DATA_FILE = "bot_data.json"

def save_data():
    """Ma'lumotlarni faylga saqlash"""
    try:
        data = {
            "authorized_users": AUTHORIZED_USERS,
            "user_channels": {},
            "all_channels": {},
            "scheduled": {},
            "user_history": {},
            "time_settings": time_settings,
            "last_save": datetime.utcnow().isoformat()
        }
        
        # user_channels ni saqlash
        for uid, channel in user_channels.items():
            data["user_channels"][str(uid)] = channel
        
        # all_channels ni saqlash
        for cid, info in all_channels.items():
            data["all_channels"][str(cid)] = {
                "owner_id": info["owner_id"],
                "title": info["title"]
            }
        
        # scheduled ni saqlash
        for chat_id, users in scheduled.items():
            data["scheduled"][str(chat_id)] = {}
            for user_id, user_data in users.items():
                data["scheduled"][str(chat_id)][str(user_id)] = {
                    "username": user_data.get("username", ""),
                    "full_name": user_data.get("full_name", ""),
                    "time": user_data["time"].isoformat(),
                    "user_id": user_data["user_id"],
                    "join_time": user_data.get("join_time", datetime.utcnow()).isoformat(),
                    "permanent": user_data.get("permanent", False),
                    "chat_id": chat_id
                }
        
        # user_history ni saqlash
        for chat_id, users in user_history.items():
            data["user_history"][str(chat_id)] = {}
            for user_id, hist_data in users.items():
                data["user_history"][str(chat_id)][str(user_id)] = {
                    "username": hist_data.get("username", ""),
                    "full_name": hist_data.get("full_name", ""),
                    "join_time": hist_data["join_time"].isoformat(),
                    "leave_time": hist_data.get("leave_time", "").isoformat() if hist_data.get("leave_time") else "",
                    "status": hist_data.get("status", ""),
                    "scheduled_ban": hist_data.get("scheduled_ban", "").isoformat() if hist_data.get("scheduled_ban") else "",
                    "ban_time_str": hist_data.get("ban_time_str", ""),
                    "chat_id": chat_id,
                    "chat_title": hist_data.get("chat_title", "")
                }
        
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"✅ Ma'lumotlar saqlandi: {datetime.utcnow().strftime('%H:%M:%S')}")
    except Exception as e:
        print(f"❌ Saqlash xatosi: {e}")

def load_data():
    """Ma'lumotlarni fayldan yuklash"""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
            
            # authorized_users ni yuklash
            AUTHORIZED_USERS.clear()
            AUTHORIZED_USERS.extend(data.get("authorized_users", [YOUR_ID]))
            
            # user_channels ni yuklash
            for uid, channel in data.get("user_channels", {}).items():
                user_channels[int(uid)] = channel
            
            # all_channels ni yuklash
            for cid, info in data.get("all_channels", {}).items():
                all_channels[int(cid)] = info
            
            # scheduled ni yuklash
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
                        "chat_id": int(chat_id)
                    }
            
            # user_history ni yuklash
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
                        "chat_id": int(chat_id),
                        "chat_title": hist_data.get("chat_title", "")
                    }
            
            # time_settings ni yuklash
            time_settings.update(data.get("time_settings", {}))
            
            print(f"✅ Ma'lumotlar yuklandi")
    except Exception as e:
        print(f"❌ Yuklash xatosi: {e}")

load_data()

# ==================== FOYDALANUVCHI FUNKSIYALARI ====================
def is_owner(user_id):
    """Foydalanuvchi bot egasimi?"""
    return user_id == YOUR_ID

def is_authorized(user_id):
    """Foydalanuvchi ruxsatlanganmi?"""
    return user_id in AUTHORIZED_USERS

def can_access_channel(user_id, chat_id):
    """Foydalanuvchi bu kanalga kirish huquqiga egami?"""
    if user_id == YOUR_ID:
        return True
    return user_id in user_channels and user_channels[user_id]["chat_id"] == chat_id

def get_channel_owner(chat_id):
    """Kanal egasini qaytarish"""
    return all_channels.get(chat_id, {}).get("owner_id")

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
        
        if 'k' in time_str:
            return number * 24 * 60
        elif 'm' in time_str:
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

# ==================== KANAL QO'SHISH ====================
async def add_channel_for_user(client, user_id, chat_id, chat_title):
    """Foydalanuvchi uchun kanal qo'shish"""
    
    if user_id in user_channels:
        old_chat_id = user_channels[user_id]["chat_id"]
        if old_chat_id in all_channels:
            del all_channels[old_chat_id]
        # Eski kanaldagi bloklashlarni ham o'chirish
        if old_chat_id in scheduled:
            del scheduled[old_chat_id]
    
    user_channels[user_id] = {
        "chat_id": chat_id,
        "title": chat_title
    }
    
    all_channels[chat_id] = {
        "owner_id": user_id,
        "title": chat_title
    }
    
    save_data()
    print(f"✅ Kanal qo'shildi: {chat_title} (user: {user_id})")

# ==================== KANALNI O'CHIRISH ====================
async def remove_channel_for_user(client, user_id):
    """Foydalanuvchi kanalini o'chirish"""
    if user_id in user_channels:
        chat_id = user_channels[user_id]["chat_id"]
        if chat_id in all_channels:
            del all_channels[chat_id]
        if chat_id in scheduled:
            del scheduled[chat_id]
        if chat_id in user_history:
            del user_history[chat_id]
        del user_channels[user_id]
        save_data()
        return True, chat_id
    return False, None

# ==================== TUGMALAR ====================
def get_main_keyboard(has_channel):
    """Asosiy menyu tugmalari (oddiy user uchun)"""
    if has_channel:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 A'zolar", callback_data="members")],
            [InlineKeyboardButton("⏰ Bloklashlar", callback_data="bans")],
            [InlineKeyboardButton("📊 Statistika", callback_data="stats")],
            [InlineKeyboardButton("🔄 Kanalni almashtirish", callback_data="change_channel"),
             InlineKeyboardButton("🗑 Kanalni o'chirish", callback_data="delete_channel_confirm")],
            [InlineKeyboardButton("🕐 Vaqt sozlash", callback_data="menu_time")]
        ])
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_channel")],
            [InlineKeyboardButton("🕐 Vaqt sozlash", callback_data="menu_time")]
        ])
    return keyboard

def get_admin_main_keyboard():
    """Admin uchun asosiy tugmalar"""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Mening kanallarim", callback_data="my_channels")],
        [InlineKeyboardButton("👥 Ruxsatlanganlar", callback_data="admin_users")],
        [InlineKeyboardButton("➕ Ruxsat berish", callback_data="admin_add_user")],
        [InlineKeyboardButton("❌ Ruxsatni bekor qilish", callback_data="admin_remove_user")],
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("🕐 Vaqt sozlash", callback_data="menu_time")],
        [InlineKeyboardButton("❓ Yordam", callback_data="admin_help")],
        [InlineKeyboardButton("🔙 Asosiy menyu", callback_data="back_to_user_menu")]
    ])
    return keyboard

def get_back_keyboard(target):
    """Orqaga qaytish tugmasi"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Orqaga", callback_data=f"back_to_{target}")]
    ])

# ==================== START (TO'G'IRLANGAN) ====================
@app.on_message(filters.command("start"))
async def start_command(client, message):
    user_id = message.from_user.id
    
    # Ruxsat tekshirish
    if not is_authorized(user_id):
        await message.reply_text(
            f"❌ **Sizga ruxsat berilmagan!**\n\n"
            f"Botdan foydalanish uchun @maestro_o ga murojaat qiling.\n\n"
            f"🆔 **Sizning ID:** `{user_id}`\n\n"
            f"📌 Iltimos, shu ID ni @maestro_o ga yuboring."
        )
        return
    
    # Admin panel (siz uchun)
    if is_owner(user_id):
        text = f"✅ **ADMIN PANEL**\n\n"
        text += f"👋 Xush kelibsiz, @maestro_o!\n"
        text += f"🕐 Vaqt: {local_time(user_id).strftime('%H:%M %d.%m.%Y')}\n\n"
        text += f"📊 **MA'LUMOT:**\n"
        text += f"👥 Ruxsatlanganlar: {len(AUTHORIZED_USERS)-1} ta\n"
        text += f"📌 Faol kanallar: {len(user_channels)} ta\n\n"
        text += f"🔽 Quyidagi tugmalardan foydalaning:"
        
        await message.reply_text(text, reply_markup=get_admin_main_keyboard())
        return  # MUHIM: return qilish kerak!
    
    # Oddiy user panel
    if user_id in user_channels:
        channel = user_channels[user_id]
        text = f"✅ **SIZNING KANALINGIZ**\n\n"
        text += f"📌 {channel['title']}\n"
        text += f"🆔 `{channel['chat_id']}`\n\n"
        text += "Quyidagi tugmalar orqali boshqaring:"
    else:
        text = "👋 **XUSH KELIBSIZ!**\n\n"
        text += "Botdan foydalanish uchun kanalingizni qo'shing:\n\n"
        text += "• Kanal ID sini yozing: `-100123456789`\n"
        text += "• Yoki kanaldan xabar forward qiling"
    
    await message.reply_text(text, reply_markup=get_main_keyboard(user_id in user_channels))

# ==================== @uzdramadubbot GA JAVOB (FAQAT GRUPPA) ====================
@app.on_message(filters.text & filters.regex(r"^@uzdramadubbot$") & filters.group)
async def bot_mention_group(client, message):
    """Guruhda @uzdramadubbot yozilsa javob berish"""
    chat = message.chat
    
    is_admin, status = await check_bot_admin(client, chat.id)
    
    if is_admin:
        await message.reply_text(f"✅ **Bot bu guruhda admin!**\nStatus: {status}")
    else:
        await message.reply_text(f"❌ **Bot bu guruhda admin emas!**")

# ==================== ADMIN UCHUN ID QABUL QILISH ====================
@app.on_message()
async def handle_admin_input(client, message):
    """Admin ID yozganda ruxsat berish"""
    if message.chat.type != enums.ChatType.PRIVATE:
        return
    
    user_id = message.from_user.id
    
    # Faqat admin uchun
    if not is_owner(user_id):
        return
    
    # Faqat "awaiting_user_id" holatida bo'lganida
    if user_id not in temp_data or temp_data[user_id].get("action") != "awaiting_user_id":
        return
    
    # Komandalarni ignore qilish
    if message.text and message.text.startswith('/'):
        return
    
    if not message.text:
        await message.reply_text("❌ Iltimos, faqat ID raqamini yuboring!")
        return
    
    text = message.text.strip()
    
    # Faqat raqam bo'lishi kerak
    if not text.isdigit():
        await message.reply_text(
            "❌ **Noto'g'ri format!**\n\n"
            "Faqat raqamlardan iborat ID yuboring.\n"
            "Misol: `123456789`"
        )
        return
    
    try:
        new_user_id = int(text)
        
        if new_user_id == YOUR_ID:
            await message.reply_text("❌ Bu o'zingizning ID ingiz!")
            temp_data.pop(user_id, None)
            return
        
        # Foydalanuvchi mavjudligini tekshirish
        try:
            user = await client.get_users(new_user_id)
            user_name = user.first_name or "Foydalanuvchi"
        except:
            await message.reply_text(
                f"❌ **Foydalanuvchi topilmadi!**\n\n"
                f"ID: `{new_user_id}`\n\n"
                f"Bu ID Telegramda mavjud emas yoki bot bloklangan."
            )
            temp_data.pop(user_id, None)
            return
        
        # Ruxsat berish
        if new_user_id not in AUTHORIZED_USERS:
            AUTHORIZED_USERS.append(new_user_id)
            save_data()
            
            await message.reply_text(
                f"✅ **RUXSAT BERILDI!**\n\n"
                f"👤 Foydalanuvchi: {user_name}\n"
                f"🆔 ID: `{new_user_id}`\n\n"
                f"Endi u botdan foydalanishi mumkin!"
            )
            
            # Yangi foydalanuvchiga xabar
            try:
                await client.send_message(
                    new_user_id,
                    f"✅ **Sizga botdan foydalanish uchun ruxsat berildi!**\n\n"
                    f"👤 Admin: @maestro_o\n"
                    f"🆔 Sizning ID: `{new_user_id}`\n\n"
                    f"🔽 /start ni bosing"
                )
            except:
                await message.reply_text("⚠️ Foydalanuvchiga xabar yuborilmadi (botni bloklagan bo'lishi mumkin)")
        else:
            await message.reply_text(f"❌ Bu foydalanuvchi (`{new_user_id}`) allaqachon ruxsat olgan!")
        
        # Holatni tozalash
        temp_data.pop(user_id, None)
        
        # Admin panelga qaytish tugmasi
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Admin panel", callback_data="back_admin_main")]
        ])
        await message.reply_text("🔽 Admin panelga qaytish:", reply_markup=keyboard)
        
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")
        temp_data.pop(user_id, None)

# ==================== BOShQA XABARLAR ====================
@app.on_message()
async def handle_other_messages(client, message):
    """ID yoki forward orqali kanal qo'shish"""
    
    if message.chat.type != enums.ChatType.PRIVATE:
        return
    
    user_id = message.from_user.id
    
    if not is_authorized(user_id):
        return
    
    if message.text and message.text.startswith('/'):
        return
    
    # Forward qilingan xabar
    if message.forward_from_chat:
        chat_id = message.forward_from_chat.id
        chat_title = message.forward_from_chat.title
        
        msg = await message.reply_text(f"⏳ Tekshirilmoqda: {chat_title}...")
        
        try:
            chat = await client.get_chat(chat_id)
            is_admin, status = await check_bot_admin(client, chat_id)
            
            if not is_admin:
                await msg.edit_text(
                    f"❌ **BOT ADMIN EMAS!**\n\n"
                    f"📌 Kanal: {chat.title}\n"
                    f"🆔 ID: `{chat_id}`\n\n"
                    f"✅ Yechim:\n"
                    f"1. Kanalga admin qiling\n"
                    f"2. 'Bloklash' huquqini bering\n"
                    f"3. Xabarni qayta forward qiling"
                )
                return
            
            await add_channel_for_user(client, user_id, chat_id, chat.title)
            
            await msg.edit_text(
                f"✅ **KANAL QO'SHILDI!**\n\n"
                f"📌 {chat.title}\n"
                f"🆔 `{chat_id}`\n"
                f"📎 Forward orqali\n\n"
                f"Endi /start ni bosing",
                reply_markup=get_main_keyboard(True)
            )
            return
            
        except Exception as e:
            await msg.edit_text(f"❌ Xatolik: {str(e)}")
            return
    
    # Oddiy matn (kanal ID)
    if not message.text:
        return
    
    text = message.text.strip()
    
    if (text.startswith('-') and text[1:].isdigit()) or text.isdigit():
        try:
            chat_id = int(text)
            msg = await message.reply_text("⏳ Tekshirilmoqda...")
            
            try:
                chat = await client.get_chat(chat_id)
            except:
                await msg.edit_text(
                    f"❌ **KANAL TOPILMADI!**\n\n"
                    f"ID: `{chat_id}`\n\n"
                    f"📌 Tekshiring:\n"
                    f"• ID to'g'rimi?\n"
                    f"• Bot kanalga qo'shilganmi?\n"
                    f"• Yoki forward qiling"
                )
                return
            
            is_admin, status = await check_bot_admin(client, chat_id)
            
            if not is_admin:
                await msg.edit_text(
                    f"❌ **BOT ADMIN EMAS!**\n\n"
                    f"📌 Kanal: {chat.title}\n"
                    f"🆔 ID: `{chat_id}`\n\n"
                    f"✅ Yechim:\n"
                    f"1. Kanalga admin qiling\n"
                    f"2. 'Bloklash' huquqini bering\n"
                    f"3. ID ni qayta yozing"
                )
                return
            
            await add_channel_for_user(client, user_id, chat_id, chat.title)
            
            members = chat.members_count if hasattr(chat, 'members_count') else "?"
            
            await msg.edit_text(
                f"✅ **KANAL QO'SHILDI!**\n\n"
                f"📌 {chat.title}\n"
                f"🆔 `{chat_id}`\n"
                f"👥 A'zolar: {members}\n"
                f"🤖 Status: {status}\n\n"
                f"Endi /start ni bosing",
                reply_markup=get_main_keyboard(True)
            )
            
        except Exception as e:
            await message.reply_text(f"❌ Xatolik: {str(e)}")

# ==================== YANGI A'ZO QO'SHILGANDA ====================
@app.on_chat_member_updated()
async def on_chat_member_update(client, chat_member_updated):
    """Kanalga yangi a'zo qo'shilganda habar berish"""
    
    chat = chat_member_updated.chat
    if chat.type not in [enums.ChatType.CHANNEL, enums.ChatType.SUPERGROUP]:
        return
    
    new_member = chat_member_updated.new_chat_member
    old_member = chat_member_updated.old_chat_member
    
    if old_member and new_member and old_member.status == new_member.status:
        return
    
    if not new_member or new_member.status != enums.ChatMemberStatus.MEMBER:
        return
    
    if old_member and old_member.status == enums.ChatMemberStatus.MEMBER:
        return
    
    user = new_member.user
    if user.is_bot:
        return
    
    is_admin, _ = await check_bot_admin(client, chat.id)
    if not is_admin:
        return
    
    event_str = f"{chat.id}_{user.id}_{datetime.utcnow().strftime('%Y%m%d%H%M')}"
    event_hash = hashlib.md5(event_str.encode()).hexdigest()
    current_time = time.time()
    
    if event_hash in processed_events:
        if current_time - processed_events[event_hash]["time"] < 30:
            processed_events[event_hash]["count"] += 1
            return
    
    processed_events[event_hash] = {"time": current_time, "count": 1}
    
    channel_owner_id = get_channel_owner(chat.id)
    if not channel_owner_id:
        return
    
    user_id = user.id
    username = f"@{user.username}" if user.username else "username yo'q"
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    join_time = datetime.utcnow()
    
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
    
    # Kanal egasiga xabar
    try:
        await client.send_message(
            channel_owner_id,
            f"👤 **YANGI A'ZO!**\n\n"
            f"📌 Kanal: {chat.title}\n"
            f"👤 {full_name}\n"
            f"🆔 `{user_id}`\n"
            f"📱 {username}\n"
            f"⏰ {format_time(join_time, channel_owner_id)}",
            reply_markup=keyboard
        )
    except:
        pass

# ==================== RUXSAT BERISH KOMANDALARI ====================
@app.on_message(filters.command("allow"))
async def allow_user(client, message):
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.reply_text("❌ /allow [user_id] - foydalanuvchiga ruxsat berish")
        return
    
    try:
        new_user_id = int(args[1])
        if new_user_id == YOUR_ID:
            await message.reply_text("❌ Bu o'zingiz!")
            return
            
        if new_user_id not in AUTHORIZED_USERS:
            AUTHORIZED_USERS.append(new_user_id)
            save_data()
            
            try:
                user = await client.get_users(new_user_id)
                name = user.first_name or "Noma'lum"
                await message.reply_text(f"✅ Ruxsat berildi: {name} (`{new_user_id}`)")
                
                try:
                    await client.send_message(
                        new_user_id,
                        "✅ **Sizga botdan foydalanish uchun ruxsat berildi!**\n\n"
                        "🔽 /start ni bosing"
                    )
                except:
                    pass
            except:
                await message.reply_text(f"✅ Ruxsat berildi: `{new_user_id}`")
        else:
            await message.reply_text("❌ Bu foydalanuvchi allaqachon ruxsat olgan!")
    except:
        await message.reply_text("❌ Noto'g'ri ID!")

@app.on_message(filters.command("disallow"))
async def disallow_user(client, message):
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.reply_text("❌ /disallow [user_id] - ruxsatni bekor qilish")
        return
    
    try:
        remove_user_id = int(args[1])
        if remove_user_id == YOUR_ID:
            await message.reply_text("❌ O'zingizni bekor qila olmaysiz!")
            return
            
        if remove_user_id in AUTHORIZED_USERS:
            AUTHORIZED_USERS.remove(remove_user_id)
            
            if remove_user_id in user_channels:
                chat_id = user_channels[remove_user_id]["chat_id"]
                if chat_id in all_channels:
                    del all_channels[chat_id]
                if chat_id in scheduled:
                    del scheduled[chat_id]
                del user_channels[remove_user_id]
            
            save_data()
            await message.reply_text(f"✅ Ruxsat bekor qilindi: `{remove_user_id}`")
        else:
            await message.reply_text("❌ Foydalanuvchi topilmadi!")
    except:
        await message.reply_text("❌ Noto'g'ri ID!")

@app.on_message(filters.command("users"))
async def list_users(client, message):
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    text = "👥 **RUXSATLANGAN FOYDALANUVCHILAR**\n\n"
    
    for uid in AUTHORIZED_USERS:
        if uid == YOUR_ID:
            continue
        try:
            user = await client.get_users(uid)
            name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            username = f"@{user.username}" if user.username else ""
            text += f"• {name} {username}\n  ID: `{uid}`\n"
            if uid in user_channels:
                text += f"  📌 Kanal: {user_channels[uid]['title']}\n"
            text += "\n"
        except:
            text += f"• Noma'lum foydalanuvchi\n  ID: `{uid}`\n\n"
    
    await message.reply_text(text)

# ==================== VAQT SOZLASH ====================
@app.on_message(filters.command("settime"))
async def set_time_command(client, message):
    user_id = message.from_user.id
    
    if not is_authorized(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        current = time_settings.get(user_id, 5)
        await message.reply_text(
            f"🕐 **VAQT SOZLARI**\n\n"
            f"Hozirgi: UTC+{current}\n"
            f"Vaqt: {local_time(user_id).strftime('%H:%M %d.%m.%Y')}\n\n"
            f"O'zgartirish: /settime [farq]\n"
            f"Misol: /settime 5"
        )
        return
    
    try:
        soat_farqi = int(args[1])
        time_settings[user_id] = soat_farqi
        save_data()
        
        await message.reply_text(
            f"✅ **VAQT SOZLANDI!**\n\n"
            f"🕐 UTC+{soat_farqi}\n"
            f"📅 Hozir: {local_time(user_id).strftime('%d.%m.%Y %H:%M:%S')}"
        )
    except:
        await message.reply_text("❌ Noto'g'ri format! Masalan: /settime 5")

# ==================== CALLBACK HANDLER ====================
@app.on_callback_query()
async def handle_callbacks(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if not is_authorized(user_id):
        await callback_query.answer("Ruxsat yo'q!")
        return
    
    data = callback_query.data
    
    # ===== ASOSIY MENYUGA QAYTISH (USER UCHUN) =====
    if data == "back_to_user_menu":
        if user_id in user_channels:
            channel = user_channels[user_id]
            text = f"✅ **SIZNING KANALINGIZ**\n\n"
            text += f"📌 {channel['title']}\n"
            text += f"🆔 `{channel['chat_id']}`\n\n"
            text += "Quyidagi tugmalar orqali boshqaring:"
        else:
            text = "👋 **XUSH KELIBSIZ!**\n\n"
            text += "Botdan foydalanish uchun kanalingizni qo'shing:"
        
        await callback_query.message.edit_text(text, reply_markup=get_main_keyboard(user_id in user_channels))
        await callback_query.answer()
        return
    
    # ===== ADMIN PANELGA QAYTISH =====
    if data == "back_admin_main":
        text = f"✅ **ADMIN PANEL**\n\n"
        text += f"👋 Xush kelibsiz, @maestro_o!\n"
        text += f"🕐 Vaqt: {local_time(user_id).strftime('%H:%M %d.%m.%Y')}\n\n"
        text += f"📊 **MA'LUMOT:**\n"
        text += f"👥 Ruxsatlanganlar: {len(AUTHORIZED_USERS)-1} ta\n"
        text += f"📌 Faol kanallar: {len(user_channels)} ta\n\n"
        text += f"🔽 Quyidagi tugmalardan foydalaning:"
        
        await callback_query.message.edit_text(text, reply_markup=get_admin_main_keyboard())
        await callback_query.answer()
        return
    
    # ===== ADMIN: MENING KANALLARIM =====
    if data == "my_channels":
        # Siz qo'shgan kanallar (o'zingizning user_id bo'yicha)
        my_channels_list = []
        for uid, channel in user_channels.items():
            if uid == YOUR_ID:  # Sizning ID ingiz bilan qo'shilgan kanallar
                my_channels_list.append((uid, channel))
        
        if not my_channels_list:
            text = "📭 **SIZNING KANALLARINGIZ YO'Q**\n\n"
            text += "Kanallaringizni qo'shish uchun:\n"
            text += "• Kanal ID sini yozing: `-100123456789`\n"
            text += "• Yoki kanaldan xabar forward qiling"
        else:
            text = "📋 **SIZNING KANALLARINGIZ**\n\n"
            for uid, channel in my_channels_list:
                text += f"📌 {channel['title']}\n"
                text += f"🆔 `{channel['chat_id']}`\n"
                bans = len(scheduled.get(channel['chat_id'], {}))
                text += f"⏰ Bloklashlar: {bans} ta\n\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Yangi kanal qo'shish", callback_data="add_channel")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back_admin_main")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
        await callback_query.answer()
        return
    
    # ===== ADMIN: RUXSAT BERISH TUGMASI =====
    if data == "admin_add_user":
        temp_data[user_id] = {"action": "awaiting_user_id"}
        await callback_query.message.edit_text(
            "➕ **RUXSAT BERISH**\n\n"
            "Foydalanuvchi ID sini yuboring:\n\n"
            "Misol: `123456789`\n\n"
            "ID ni @userinfobot dan olish mumkin.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Orqaga", callback_data="back_admin_main")]
            ])
        )
        await callback_query.answer()
        return
    
    # ===== ADMIN: RUXSATLANGANLAR =====
    if data == "admin_users":
        text = "👥 **RUXSATLANGANLAR**\n\n"
        if len(AUTHORIZED_USERS) <= 1:
            text += "Hali hech kimga ruxsat berilmagan."
        else:
            for uid in AUTHORIZED_USERS:
                if uid != YOUR_ID:
                    try:
                        user = await client.get_users(uid)
                        name = user.first_name or "Noma'lum"
                        text += f"• {name}\n  ID: `{uid}`\n"
                        if uid in user_channels:
                            text += f"  📌 {user_channels[uid]['title']}\n"
                        text += "\n"
                    except:
                        text += f"• Noma'lum\n  ID: `{uid}`\n\n"
        
        await callback_query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Orqaga", callback_data="back_admin_main")]
            ])
        )
        await callback_query.answer()
        return
    
    # ===== ADMIN: RUXSATNI BEKOR QILISH =====
    if data == "admin_remove_user":
        # Ruxsatlanganlar ro'yxatini ko'rsatish
        users_list = []
        for uid in AUTHORIZED_USERS:
            if uid != YOUR_ID:
                try:
                    user = await client.get_users(uid)
                    name = user.first_name or f"ID:{uid}"
                    users_list.append((uid, name))
                except:
                    users_list.append((uid, f"Noma'lum ({uid})"))
        
        if not users_list:
            await callback_query.message.edit_text(
                "📭 **RUXSATLANGANLAR YO'Q**\n\nHali hech kimga ruxsat bermagansiz.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Orqaga", callback_data="back_admin_main")]
                ])
            )
            await callback_query.answer()
            return
        
        text = "👥 **RUXSATLANGANLAR**\n\nBekor qilmoqchi bo'lgan foydalanuvchini tanlang:\n\n"
        keyboard = []
        
        for uid, name in users_list[:10]:
            btn_text = f"❌ {name[:20]}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"confirm_remove_{uid}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_admin_main")])
        
        await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        await callback_query.answer()
        return
    
    # ===== RUXSATNI BEKOR QILISH TASDIQLASH =====
    if data.startswith("confirm_remove_"):
        remove_user_id = int(data.split("_")[2])
        
        try:
            user = await client.get_users(remove_user_id)
            user_name = user.first_name or "Foydalanuvchi"
        except:
            user_name = "Noma'lum"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Ha, bekor qilish", callback_data=f"execute_remove_{remove_user_id}")],
            [InlineKeyboardButton("❌ Yo'q", callback_data="admin_remove_user")]
        ])
        
        await callback_query.message.edit_text(
            f"❓ **RUXSATNI BEKOR QILISH**\n\n"
            f"👤 Foydalanuvchi: {user_name}\n"
            f"🆔 ID: `{remove_user_id}`\n\n"
            f"Ruxsatni bekor qilishni tasdiqlaysizmi?",
            reply_markup=keyboard
        )
        await callback_query.answer()
        return
    
    # ===== RUXSATNI BEKOR QILISH BAJARISH =====
    if data.startswith("execute_remove_"):
        remove_user_id = int(data.split("_")[2])
        
        if remove_user_id in AUTHORIZED_USERS and remove_user_id != YOUR_ID:
            AUTHORIZED_USERS.remove(remove_user_id)
            
            # Foydalanuvchi kanalini o'chirish
            if remove_user_id in user_channels:
                chat_id = user_channels[remove_user_id]["chat_id"]
                if chat_id in all_channels:
                    del all_channels[chat_id]
                if chat_id in scheduled:
                    del scheduled[chat_id]
                del user_channels[remove_user_id]
            
            save_data()
            
            await callback_query.message.edit_text(
                f"✅ **RUXSAT BEKOR QILINDI!**\n\n"
                f"🆔 ID: `{remove_user_id}`\n\n"
                f"Foydalanuvchi endi botdan foydalana olmaydi.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Admin panel", callback_data="back_admin_main")]
                ])
            )
        else:
            await callback_query.message.edit_text(
                "❌ **XATOLIK!**\n\nFoydalanuvchi topilmadi.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Orqaga", callback_data="back_admin_main")]
                ])
            )
        await callback_query.answer()
        return
    
    # ===== ADMIN STATISTIKA =====
    if data == "admin_stats":
        total_channels = len(user_channels)
        total_bans = sum(len(bans) for bans in scheduled.values())
        total_history = sum(len(users) for users in user_history.values())
        
        text = f"📊 **STATISTIKA**\n\n"
        text += f"👥 Ruxsatlanganlar: {len(AUTHORIZED_USERS)-1} ta\n"
        text += f"📌 Faol kanallar: {total_channels} ta\n"
        text += f"⏰ Bloklashlar: {total_bans} ta\n"
        text += f"📋 Tarix: {total_history} ta\n"
        text += f"🕐 Vaqt: UTC+{time_settings.get(user_id, 5)}\n"
        text += f"📅 {local_time(user_id).strftime('%d.%m.%Y %H:%M:%S')}"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Yangilash", callback_data="admin_stats")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back_admin_main")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
        await callback_query.answer()
        return
    
    # ===== ADMIN YORDAM =====
    if data == "admin_help":
        text = "❓ **ADMIN YORDAM**\n\n"
        text += "📌 **Komandalar:**\n"
        text += "• /allow [id] - ruxsat berish\n"
        text += "• /disallow [id] - ruxsatni bekor qilish\n"
        text += "• /users - foydalanuvchilar ro'yxati\n"
        text += "• /settime [farq] - vaqt sozlash\n\n"
        text += "📌 **Tugmalar:**\n"
        text += "• 📋 Mening kanallarim - sizning kanallaringiz\n"
        text += "• 👥 Ruxsatlanganlar - ro'yxat\n"
        text += "• ➕ Ruxsat berish - ID orqali\n"
        text += "• ❌ Ruxsatni bekor qilish\n"
        text += "• 📊 Statistika - umumiy ma'lumot\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back_admin_main")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
        await callback_query.answer()
        return
    
    # ===== USER FUNKSIYALARI =====
    if data == "add_channel":
        await callback_query.message.edit_text(
            "➕ **KANAL QO'SHISH**\n\n"
            "Ikkita usul:\n\n"
            "1. Kanal ID sini yozing:\n"
            "`-100123456789`\n\n"
            "2. Kanaldan xabar forward qiling",
            reply_markup=get_back_keyboard("user_menu")
        )
        await callback_query.answer()
        return
    
    if data == "change_channel":
        await callback_query.message.edit_text(
            "🔄 **KANALNI ALMASHTIRISH**\n\n"
            "Yangi kanal ID sini yozing yoki forward qiling.\n\n"
            "Eski kanal avtomatik o'chadi.",
            reply_markup=get_back_keyboard("user_menu")
        )
        await callback_query.answer()
        return
    
    if data == "delete_channel_confirm":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Ha, o'chirish", callback_data="delete_channel_yes")],
            [InlineKeyboardButton("❌ Yo'q, bekor qilish", callback_data="back_to_user_menu")]
        ])
        await callback_query.message.edit_text(
            "🗑 **KANALNI O'CHIRISH**\n\n"
            "Kanalni botdan o'chirmoqchimisiz?\n\n"
            "⚠️ **Diqqat!** Kanal o'chirilsa:\n"
            "• Barcha bloklashlar o'chadi\n"
            "• Tarix saqlanmaydi\n"
            "• Qayta qo'shish kerak bo'ladi",
            reply_markup=keyboard
        )
        await callback_query.answer()
        return
    
    if data == "delete_channel_yes":
        success, chat_id = await remove_channel_for_user(client, user_id)
        if success:
            await callback_query.message.edit_text(
                "✅ **KANAL O'CHIRILDI!**\n\n"
                "Kanal muvaffaqiyatli o'chirildi.\n\n"
                "Endi /start orqali yangi kanal qo'shishingiz mumkin.",
                reply_markup=get_main_keyboard(False)
            )
        else:
            await callback_query.message.edit_text(
                "❌ **XATOLIK!**\n\n"
                "Kanal o'chirilmadi. Qaytadan urinib ko'ring.",
                reply_markup=get_back_keyboard("user_menu")
            )
        await callback_query.answer()
        return
    
    if data == "members":
        if user_id not in user_channels:
            await callback_query.answer("Avval kanal qo'shing!", show_alert=True)
            return
        
        chat_id = user_channels[user_id]["chat_id"]
        temp_data[user_id] = {"action": "members", "chat_id": chat_id}
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 Barcha a'zolar", callback_data="members_all")],
            [InlineKeyboardButton("📱 Username borlar", callback_data="members_with_username")],
            [InlineKeyboardButton("❌ Username yo'qlar", callback_data="members_without_username")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_user_menu")]
        ])
        
        await callback_query.message.edit_text(
            f"👥 **A'ZOLAR**\n\n"
            f"📌 {user_channels[user_id]['title']}\n\n"
            f"Qanday a'zolarni ko'rmoqchisiz?",
            reply_markup=keyboard
        )
        await callback_query.answer()
        return
    
    if data.startswith("members_"):
        await handle_members_submenu(client, callback_query)
        return
    
    if data == "bans":
        if user_id not in user_channels:
            await callback_query.answer("Avval kanal qo'shing!", show_alert=True)
            return
        
        chat_id = user_channels[user_id]["chat_id"]
        
        if chat_id in scheduled and scheduled[chat_id]:
            text = f"⏰ **BLOKLASHLAR**\n📌 {user_channels[user_id]['title']}\n\n"
            now = datetime.utcnow()
            
            for uid, info in scheduled[chat_id].items():
                sana = format_time(info["time"], user_id)
                qolgan = info["time"] - now
                if qolgan.days > 0:
                    qolgan_text = f"(qoldi: {qolgan.days} kun)"
                else:
                    qolgan_text = f"(qoldi: {qolgan.seconds//3600} soat)"
                
                text += f"• {info['full_name']}\n  {sana} {qolgan_text}\n\n"
            
            text += f"📊 Jami: {len(scheduled[chat_id])} ta"
        else:
            text = f"📭 **BLOKLASHLAR YO'Q**\n📌 {user_channels[user_id]['title']}"
        
        await callback_query.message.edit_text(text, reply_markup=get_back_keyboard("user_menu"))
        await callback_query.answer()
        return
    
    if data == "stats":
        if user_id not in user_channels:
            await callback_query.answer("Avval kanal qo'shing!", show_alert=True)
            return
        
        chat_id = user_channels[user_id]["chat_id"]
        bans = len(scheduled.get(chat_id, {}))
        history = len(user_history.get(chat_id, {}))
        
        text = f"📊 **STATISTIKA**\n\n"
        text += f"📌 {user_channels[user_id]['title']}\n"
        text += f"🆔 `{chat_id}`\n\n"
        text += f"⏰ Bloklashlar: {bans} ta\n"
        text += f"📋 Tarix: {history} ta\n"
        text += f"🕐 Vaqt: UTC+{time_settings.get(user_id, 5)}\n"
        text += f"📅 {local_time(user_id).strftime('%d.%m.%Y %H:%M:%S')}"
        
        await callback_query.message.edit_text(text, reply_markup=get_back_keyboard("user_menu"))
        await callback_query.answer()
        return
    
    if data == "menu_time":
        current = time_settings.get(user_id, 5)
        text = f"🕐 **VAQT SOZLASH**\n\nHozirgi: UTC+{current}\nVaqt: {local_time(user_id).strftime('%H:%M %d.%m.%Y')}"
        
        if is_owner(user_id):
            back_button = "back_admin_main"
        else:
            back_button = "back_to_user_menu"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("UTC+0", callback_data="settime_0"),
             InlineKeyboardButton("UTC+3", callback_data="settime_3")],
            [InlineKeyboardButton("UTC+5", callback_data="settime_5"),
             InlineKeyboardButton("UTC+6", callback_data="settime_6")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data=back_button)]
        ])
        await callback_query.message.edit_text(text, reply_markup=keyboard)
        await callback_query.answer()
        return
    
    if data.startswith("settime_"):
        soat = int(data.split("_")[1])
        time_settings[user_id] = soat
        save_data()
        await callback_query.answer(f"✅ Vaqt UTC+{soat} qilib sozlandi")
        
        if is_owner(user_id):
            back_button = "back_admin_main"
        else:
            back_button = "back_to_user_menu"
        
        await callback_query.message.edit_text(
            f"✅ **VAQT SOZLANDI!**\n\n🕐 UTC+{soat}\n📅 {local_time(user_id).strftime('%d.%m.%Y %H:%M:%S')}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Orqaga", callback_data=back_button)]
            ])
        )
        return
    
    if data.startswith("ban_"):
        await handle_ban_callback(client, callback_query)
        return
    
    if data.startswith("skip_"):
        await handle_skip_callback(client, callback_query)
        return

async def handle_members_submenu(client, callback_query):
    """A'zolar submenyusini boshqarish"""
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    if user_id not in user_channels:
        await callback_query.answer("Kanal topilmadi!", show_alert=True)
        return
    
    chat_id = user_channels[user_id]["chat_id"]
    
    try:
        await callback_query.message.edit_text("⏳ Yuklanmoqda...")
        
        members_with_username = []
        members_without_username = []
        
        async for member in client.get_chat_members(chat_id):
            user = member.user
            if not user.is_bot:
                info = {
                    "id": user.id,
                    "name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
                    "username": user.username
                }
                if user.username:
                    members_with_username.append(info)
                else:
                    members_without_username.append(info)
        
        if data == "members_all":
            text = f"👥 **BARCHA A'ZOLAR**\n📌 {user_channels[user_id]['title']}\n\n"
            text += f"📊 Jami: {len(members_with_username) + len(members_without_username)} ta\n\n"
            
            for i, user in enumerate((members_with_username + members_without_username)[:30]):
                if user['username']:
                    text += f"{i+1}. @{user['username']}\n   {user['name']}\n"
                else:
                    text += f"{i+1}. {user['name']}\n"
                text += f"   ID: `{user['id']}`\n\n"
        
        elif data == "members_with_username":
            text = f"📱 **USERNAME BORLAR** ({len(members_with_username)})\n"
            text += f"📌 {user_channels[user_id]['title']}\n\n"
            
            for i, user in enumerate(members_with_username[:30]):
                text += f"{i+1}. @{user['username']}\n   {user['name']}\n   ID: `{user['id']}`\n\n"
        
        elif data == "members_without_username":
            text = f"❌ **USERNAME YO'QLAR** ({len(members_without_username)})\n"
            text += f"📌 {user_channels[user_id]['title']}\n\n"
            
            for i, user in enumerate(members_without_username[:30]):
                text += f"{i+1}. {user['name']}\n   ID: `{user['id']}`\n\n"
        
        await callback_query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Orqaga", callback_data="members")]
            ])
        )
        await callback_query.answer()
        
    except Exception as e:
        await callback_query.message.edit_text(f"❌ Xatolik: {str(e)}")

async def handle_ban_callback(client, callback_query):
    """Bloklash tugmasi bosilganda"""
    data = callback_query.data
    parts = data.split('_')
    user_id = callback_query.from_user.id
    
    if len(parts) >= 4:
        chat_id = int(parts[1])
        target_user_id = int(parts[2])
        time_str = parts[3]
    else:
        await callback_query.answer("Noto'g'ri format!")
        return
    
    if not can_access_channel(user_id, chat_id):
        await callback_query.answer("Bu kanalga ruxsat yo'q!")
        return
    
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
    
    save_data()
    
    sana = format_time(ban_time, user_id)
    qoshilgan = format_time(
        user_history.get(chat_id, {}).get(target_user_id, {}).get("join_time", datetime.utcnow()),
        user_id
    )
    
    channel_title = user_channels.get(get_channel_owner(chat_id), {}).get("title", "Kanal")
    
    await callback_query.message.edit_text(
        f"✅ **BLOKLASH REJALASHTIRILDI!**\n\n"
        f"📌 {channel_title}\n"
        f"👤 {full_name}\n"
        f"🆔 `{target_user_id}`\n"
        f"📱 {username}\n"
        f"📅 Qo'shilgan: {qoshilgan}\n"
        f"⏰ Vaqt: {time_str}\n"
        f"📅 Sana: {sana}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Orqaga", callback_data="bans")]
        ])
    )
    await callback_query.answer("✅ Rejalashtirildi!")

async def handle_skip_callback(client, callback_query):
    """Skip tugmasi bosilganda"""
    data = callback_query.data
    parts = data.split('_')
    user_id = callback_query.from_user.id
    
    if len(parts) >= 3:
        chat_id = int(parts[1])
        target_user_id = int(parts[2])
    else:
        await callback_query.answer("Noto'g'ri format!")
        return
    
    if not can_access_channel(user_id, chat_id):
        await callback_query.answer("Bu kanalga ruxsat yo'q!")
        return
    
    full_name = user_history.get(chat_id, {}).get(target_user_id, {}).get("full_name", "noma'lum")
    username = user_history.get(chat_id, {}).get(target_user_id, {}).get("username", "noma'lum")
    
    await callback_query.message.edit_text(
        f"❌ **BLOKLASH BEKOR QILINDI**\n\n"
        f"👤 {full_name}\n"
        f"🆔 `{target_user_id}`\n"
        f"📱 {username}\n\n"
        f"✅ Hech qanday bloklash rejalashtirilmadi",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Orqaga", callback_data="bans")]
        ])
    )
    await callback_query.answer("❌ Bekor qilindi")

# ==================== VAQTLI BLOKLASH TEKSHIRUVI ====================
async def check_bans():
    """Bloklash vaqtini tekshirish"""
    while True:
        try:
            now = datetime.utcnow()
            for chat_id in list(scheduled.keys()):
                for user_id in list(scheduled[chat_id].keys()):
                    if now >= scheduled[chat_id][user_id]["time"]:
                        try:
                            data = scheduled[chat_id][user_id]
                            print(f"⏰ Bloklash: {data['full_name']}")
                            
                            until_date = now + timedelta(days=366)
                            await app.ban_chat_member(chat_id, user_id, until_date=until_date)
                            
                            if chat_id in user_history and user_id in user_history[chat_id]:
                                user_history[chat_id][user_id]["leave_time"] = now
                                user_history[chat_id][user_id]["status"] = "banned"
                            
                            owner_id = get_channel_owner(chat_id)
                            if owner_id:
                                join_time = data.get("join_time", now)
                                join_str = format_time(join_time, owner_id)
                                ban_str = format_time(now, owner_id)
                                
                                time_in = now - join_time
                                days = time_in.days
                                hours = time_in.seconds // 3600
                                time_text = f"{days} kun {hours} soat" if days > 0 else f"{hours} soat"
                                
                                try:
                                    await app.send_message(
                                        owner_id,
                                        f"🚫 **BLOKLANDI!**\n\n"
                                        f"👤 {data['full_name']}\n"
                                        f"🆔 `{user_id}`\n"
                                        f"📱 {data['username']}\n"
                                        f"📅 Qo'shilgan: {join_str}\n"
                                        f"📅 Bloklangan: {ban_str}\n"
                                        f"⏱️ Kanalda: {time_text}"
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

# ==================== BOTNI ISHGA TUSHIRISH ====================
def run_ban_check():
    """Bloklash tekshiruvini alohida threadda ishga tushirish"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(check_bans())

if __name__ == "__main__":
    print("=" * 60)
    print("✅ ABADIY BLOKLASH BOTI ISHGA TUSHDI!")
    print("=" * 60)
    print(f"🤖 Bot: @uzdramadubbot")
    print(f"👑 Admin: @maestro_o (ID: {YOUR_ID})")
    print(f"👥 Ruxsatlanganlar: {len(AUTHORIZED_USERS)-1} ta")
    print("=" * 60)
    print("📋 **XUSUSIYATLAR:**")
    print("   • 👤 Ruxsatsiz: ID chiqadi")
    print("   • 👥 Ruxsatli: kanal qo'shish")
    print("   • 👑 Admin: panel + barcha imkoniyatlar")
    print("   • 📋 Mening kanallarim - siz uchun")
    print("   • 🔙 Orqaga tugmalari")
    print("=" * 60)
    
    # Bloklash tekshiruvini alohida threadda ishga tushirish
    ban_thread = threading.Thread(target=run_ban_check, daemon=True)
    ban_thread.start()
    
    # Botni ishga tushirish
    app.run()
