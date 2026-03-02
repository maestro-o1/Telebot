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
AUTHORIZED_USERS = [YOUR_ID]
user_channels = {}
all_channels = {}
scheduled = {}
user_history = {}
time_settings = {}
temp_data = {}
last_check = {}
processed_events = defaultdict(lambda: {"time": 0, "count": 0})

# ==================== VAQT FUNKSIYALARI ====================
def local_time(user_id=None):
    utc_now = datetime.utcnow()
    soat_farqi = time_settings.get(user_id, 5) if user_id else 5
    return utc_now + timedelta(hours=soat_farqi)

def format_time(dt, user_id=None):
    if isinstance(dt, datetime):
        soat_farqi = time_settings.get(user_id, 5) if user_id else 5
        local_dt = dt + timedelta(hours=soat_farqi)
        return local_dt.strftime("%H:%M %d.%m.%Y")
    return "noma'lum"

# ==================== MA'LUMOTLARNI SAQLASH ====================
DATA_FILE = "bot_data.json"

def save_data():
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
        
        for uid, channel in user_channels.items():
            data["user_channels"][str(uid)] = channel
        
        for cid, info in all_channels.items():
            data["all_channels"][str(cid)] = info
        
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
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
            
            AUTHORIZED_USERS.clear()
            AUTHORIZED_USERS.extend(data.get("authorized_users", [YOUR_ID]))
            
            for uid, channel in data.get("user_channels", {}).items():
                user_channels[int(uid)] = channel
            
            for cid, info in data.get("all_channels", {}).items():
                all_channels[int(cid)] = info
            
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
            
            time_settings.update(data.get("time_settings", {}))
            print(f"✅ Ma'lumotlar yuklandi")
    except Exception as e:
        print(f"❌ Yuklash xatosi: {e}")

load_data()

# ==================== FOYDALANUVCHI FUNKSIYALARI ====================
def is_owner(user_id):
    return user_id == YOUR_ID

def is_authorized(user_id):
    return user_id in AUTHORIZED_USERS

def can_access_channel(user_id, chat_id):
    if user_id == YOUR_ID:
        return True
    return user_id in user_channels and user_channels[user_id]["chat_id"] == chat_id

def get_channel_owner(chat_id):
    return all_channels.get(chat_id, {}).get("owner_id")

# ==================== VAQTNI PARSE QILISH ====================
def parse_time(time_str):
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
    me = await client.get_me()
    
    try:
        member = await client.get_chat_member(chat_id, me.id)
        print(f"🔍 Bot status: {member.status}")
        
        if member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            if hasattr(member, 'privileges') and member.privileges:
                if member.privileges.can_restrict_members:
                    print(f"✅ Bloklash huquqi bor")
                    return True, member.status
                else:
                    print(f"❌ Bloklash huquqi yo'q")
                    return False, "Bloklash huquqi yo'q"
            else:
                print(f"✅ Admin")
                return True, member.status
    except Exception as e:
        print(f"❌ Xato: {e}")
    
    try:
        async for member in client.get_chat_members(chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
            if member.user.id == me.id:
                print(f"✅ Adminlar ro'yxatida topildi")
                return True, member.status
    except:
        pass
    
    print(f"❌ Bot admin emas!")
    return False, None

# ==================== KANAL QO'SHISH ====================
async def add_channel_for_user(client, user_id, chat_id, chat_title):
    try:
        if user_id in user_channels:
            old_chat_id = user_channels[user_id]["chat_id"]
            if old_chat_id in all_channels:
                del all_channels[old_chat_id]
            if old_chat_id in scheduled:
                del scheduled[old_chat_id]
            print(f"📌 Eski kanal o'chirildi: {old_chat_id}")
        
        user_channels[user_id] = {
            "chat_id": chat_id,
            "title": chat_title,
            "monitor": True
        }
        
        all_channels[chat_id] = {
            "owner_id": user_id,
            "title": chat_title,
            "monitor": True
        }
        
        save_data()
        print(f"✅ Kanal qo'shildi: {chat_title} (user: {user_id})")
        return True
    except Exception as e:
        print(f"❌ Kanal qo'shish xatosi: {e}")
        return False

# ==================== KANALNI O'CHIRISH ====================
async def remove_channel_for_user(client, user_id):
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
def get_main_menu_keyboard():
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Kanallarim", callback_data="my_channels_list")],
        [InlineKeyboardButton("📊 Statistika", callback_data="my_stats"),
         InlineKeyboardButton("👑 Admin panel", callback_data="admin_panel")],
        [InlineKeyboardButton("❓ Yordam", callback_data="help"),
         InlineKeyboardButton("🔄 Yangilash", callback_data="refresh_all")]
    ])
    return keyboard

def get_back_keyboard(target):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Orqaga", callback_data=f"back_to_{target}")]
    ])

# ==================== START (TO'G'IRLANGAN) ====================
@app.on_message(filters.command("start"))
async def start_command(client, message):
    user_id = message.from_user.id
    
    if not is_authorized(user_id):
        await message.reply_text(
            f"❌ **Sizga ruxsat berilmagan!**\n\n"
            f"Botdan foydalanish uchun @maestro_o ga murojaat qiling.\n\n"
            f"🆔 **Sizning ID:** `{user_id}`"
        )
        return
    
    # Admin panel (siz uchun)
    if is_owner(user_id):
        my_channels = len([c for uid, c in user_channels.items() if uid == YOUR_ID])
        total_users = len(AUTHORIZED_USERS) - 1
        total_channels = len(user_channels)
        
        text = f"👤 **Xush kelibsiz, @maestro_o!**\n\n"
        text += f"📊 **Statistika:**\n"
        text += f"• Kanallaringiz: {my_channels} ta\n"
        text += f"• Ruxsat berganlar: {total_users} ta\n"
        text += f"• Faol kanallar: {total_channels} ta\n\n"
        text += f"🔽 Quyidagi tugmalardan foydalaning:"
        
        await message.reply_text(text, reply_markup=get_main_menu_keyboard())
        return
    
    # Oddiy foydalanuvchi
    if user_id in user_channels:
        channel = user_channels[user_id]
        text = f"✅ **SIZNING KANALINGIZ**\n\n"
        text += f"📌 {channel['title']}\n"
        text += f"🆔 `{channel['chat_id']}`\n\n"
        text += "Quyidagi tugmalar orqali boshqaring:"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 A'zolar", callback_data="members")],
            [InlineKeyboardButton("⏰ Bloklashlar", callback_data="bans")],
            [InlineKeyboardButton("📊 Statistika", callback_data="stats")],
            [InlineKeyboardButton("🔄 Kanalni almashtirish", callback_data="change_channel"),
             InlineKeyboardButton("🗑 O'chirish", callback_data="delete_channel_confirm")],
            [InlineKeyboardButton("🕐 Vaqt sozlash", callback_data="menu_time")]
        ])
    else:
        text = "👋 **XUSH KELIBSIZ!**\n\n"
        text += "Botdan foydalanish uchun kanalingizni qo'shing:"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_channel")],
            [InlineKeyboardButton("🕐 Vaqt sozlash", callback_data="menu_time")]
        ])
    
    await message.reply_text(text, reply_markup=keyboard)

# ==================== KANALDA @uzdramadubbot YOZILSA ====================
@app.on_message(filters.text & filters.regex(r"^@uzdramadubbot$") & filters.channel)
async def bot_mention_channel(client, message):
    chat = message.chat
    print(f"🔍 Kanalda @uzdramadubbot yozildi: {chat.title} ({chat.id})")
    
    is_admin, status = await check_bot_admin(client, chat.id)
    
    if is_admin:
        await message.reply_text(
            f"✅ **Bot bu kanalda admin!**\n\n"
            f"📌 Kanal: {chat.title}\n"
            f"🆔 ID: `{chat.id}`\n"
            f"🤖 Status: {status}\n"
            f"⏰ Vaqt: {datetime.utcnow().strftime('%H:%M %d.%m.%Y')}\n\n"
            f"🔍 Endi kanal ID sini botga yuboring yoki forward qiling."
        )
    else:
        await message.reply_text(
            f"❌ **Bot bu kanalda admin emas!**\n\n"
            f"📌 Kanal: {chat.title}\n"
            f"🆔 ID: `{chat.id}`\n\n"
            f"✅ **Yechim:**\n"
            f"1. Kanal sozlamalariga o'ting\n"
            f"2. Adminlar bo'limiga kiring\n"
            f"3. @uzdramadubbot ni admin qiling\n"
            f"4. 'Foydalanuvchilarni bloklash' huquqini bering\n"
            f"5. Qayta @uzdramadubbot yozing"
        )

# ==================== GRUPPADA @uzdramadubbot YOZILSA ====================
@app.on_message(filters.text & filters.regex(r"^@uzdramadubbot$") & filters.group)
async def bot_mention_group(client, message):
    chat = message.chat
    is_admin, status = await check_bot_admin(client, chat.id)
    
    if is_admin:
        await message.reply_text(f"✅ **Bot bu guruhda admin!**\nStatus: {status}")
    else:
        await message.reply_text(f"❌ **Bot bu guruhda admin emas!**")

# ==================== TEST KOMANDASI ====================
@app.on_message(filters.command("test"))
async def test_add_channel(client, message):
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Ruxsat yo'q!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.reply_text("❌ /test [kanal_id] - Masalan: /test -1003726881716")
        return
    
    try:
        chat_id = int(args[1])
        msg = await message.reply_text("⏳ Tekshirilmoqda...")
        
        try:
            chat = await client.get_chat(chat_id)
            await msg.edit_text(f"✅ Kanal topildi: {chat.title}")
        except Exception as e:
            await msg.edit_text(f"❌ Kanal topilmadi: {e}")
            return
        
        is_admin, status = await check_bot_admin(client, chat_id)
        if is_admin:
            await msg.edit_text(f"✅ Bot admin! Status: {status}")
            
            success = await add_channel_for_user(client, user_id, chat_id, chat.title)
            if success:
                await msg.edit_text(
                    f"✅ **KANAL MUVOFFAQIYATLI QO'SHILDI!**\n\n"
                    f"📌 {chat.title}\n"
                    f"🆔 `{chat_id}`\n"
                    f"👥 A'zolar: {chat.members_count if hasattr(chat, 'members_count') else '?'}\n\n"
                    f"Endi /start ni bosing"
                )
        else:
            await msg.edit_text(
                f"❌ **Bot admin emas!**\n\n"
                f"📌 Kanal: {chat.title}\n"
                f"🆔 ID: `{chat_id}`\n\n"
                f"✅ **Yechim:**\n"
                f"1. Kanalga admin qiling\n"
                f"2. 'Bloklash' huquqini bering\n"
                f"3. Qayta /test {chat_id} yozing"
            )
            
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {e}")

# ==================== ADMIN UCHUN ID QABUL QILISH ====================
@app.on_message()
async def handle_admin_input(client, message):
    if message.chat.type != enums.ChatType.PRIVATE:
        return
    
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        return
    
    if user_id not in temp_data or temp_data[user_id].get("action") != "awaiting_user_id":
        return
    
    if message.text and message.text.startswith('/'):
        return
    
    if not message.text:
        await message.reply_text("❌ Iltimos, faqat ID raqamini yuboring!")
        return
    
    text = message.text.strip()
    
    if not text.isdigit():
        await message.reply_text("❌ **Noto'g'ri format!** Faqat raqam yuboring.")
        return
    
    try:
        new_user_id = int(text)
        
        if new_user_id == YOUR_ID:
            await message.reply_text("❌ Bu o'zingiz!")
            temp_data.pop(user_id, None)
            return
        
        try:
            user = await client.get_users(new_user_id)
            user_name = user.first_name or "Foydalanuvchi"
        except:
            await message.reply_text(f"❌ Foydalanuvchi topilmadi! ID: `{new_user_id}`")
            temp_data.pop(user_id, None)
            return
        
        if new_user_id not in AUTHORIZED_USERS:
            AUTHORIZED_USERS.append(new_user_id)
            save_data()
            
            await message.reply_text(f"✅ **RUXSAT BERILDI!**\n👤 {user_name}\n🆔 `{new_user_id}`")
            
            try:
                await client.send_message(
                    new_user_id,
                    f"✅ **Sizga botdan foydalanish uchun ruxsat berildi!**\n\n👤 Admin: @maestro_o\n🆔 ID: `{new_user_id}`\n\n🔽 /start ni bosing"
                )
            except:
                await message.reply_text("⚠️ Foydalanuvchiga xabar yuborilmadi")
        else:
            await message.reply_text(f"❌ Bu foydalanuvchi allaqachon ruxsat olgan!")
        
        temp_data.pop(user_id, None)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Admin panel", callback_data="admin_panel")]
        ])
        await message.reply_text("🔽 Admin panelga qaytish:", reply_markup=keyboard)
        
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")
        temp_data.pop(user_id, None)

# ==================== KANAL QO'SHISH (ID VA FORWARD) - TO'G'IRLANGAN ====================
@app.on_message()
async def handle_other_messages(client, message):
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
                    f"✅ Kanalda @uzdramadubbot yozib tekshiring"
                )
                return
            
            # Kanalni qo'shish
            success = await add_channel_for_user(client, user_id, chat_id, chat.title)
            
            if success:
                reply_markup = get_main_menu_keyboard() if is_owner(user_id) else None
                await msg.edit_text(
                    f"✅ **KANAL MUVOFFAQIYATLI QO'SHILDI!**\n\n"
                    f"📌 {chat.title}\n"
                    f"🆔 `{chat_id}`\n"
                    f"👥 A'zolar: {chat.members_count if hasattr(chat, 'members_count') else '?'}\n\n"
                    f"Endi /start ni bosing",
                    reply_markup=reply_markup
                )
            else:
                await msg.edit_text("❌ Kanal qo'shilmadi! Noma'lum xatolik.")
            
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
            except Exception as e:
                await msg.edit_text(f"❌ **KANAL TOPILMADI!**\nID: `{chat_id}`\nXato: {e}")
                return
            
            is_admin, status = await check_bot_admin(client, chat_id)
            
            if not is_admin:
                await msg.edit_text(
                    f"❌ **BOT ADMIN EMAS!**\n\n"
                    f"📌 Kanal: {chat.title}\n"
                    f"🆔 ID: `{chat_id}`\n\n"
                    f"✅ Kanalda @uzdramadubbot yozib tekshiring"
                )
                return
            
            # Kanalni qo'shish
            success = await add_channel_for_user(client, user_id, chat_id, chat.title)
            
            if success:
                members = chat.members_count if hasattr(chat, 'members_count') else "?"
                reply_markup = get_main_menu_keyboard() if is_owner(user_id) else None
                
                await msg.edit_text(
                    f"✅ **KANAL MUVOFFAQIYATLI QO'SHILDI!**\n\n"
                    f"📌 {chat.title}\n"
                    f"🆔 `{chat_id}`\n"
                    f"👥 A'zolar: {members}\n\n"
                    f"Endi /start ni bosing",
                    reply_markup=reply_markup
                )
            else:
                await msg.edit_text("❌ Kanal qo'shilmadi! Noma'lum xatolik.")
            
            return
            
        except Exception as e:
            await message.reply_text(f"❌ Xatolik: {str(e)}")
            return

# ==================== YANGI A'ZO QO'SHILGANDA ====================
@app.on_chat_member_updated()
async def on_chat_member_update(client, chat_member_updated):
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
    
    monitor = all_channels.get(chat.id, {}).get("monitor", True)
    if not monitor:
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
        [InlineKeyboardButton("⏱️ 5 minut", callback_data=f"ban_{chat.id}_{user_id}_5m"),
         InlineKeyboardButton("⏱️ 10 minut", callback_data=f"ban_{chat.id}_{user_id}_10m")],
        [InlineKeyboardButton("⏱️ 30 minut", callback_data=f"ban_{chat.id}_{user_id}_30m"),
         InlineKeyboardButton("📅 1 kun", callback_data=f"ban_{chat.id}_{user_id}_1k")],
        [InlineKeyboardButton("📅 5 kun", callback_data=f"ban_{chat.id}_{user_id}_5k"),
         InlineKeyboardButton("📅 10 kun", callback_data=f"ban_{chat.id}_{user_id}_10k")],
        [InlineKeyboardButton("📅 30 kun", callback_data=f"ban_{chat.id}_{user_id}_30k"),
         InlineKeyboardButton("📆 1 oy", callback_data=f"ban_{chat.id}_{user_id}_1oy")],
        [InlineKeyboardButton("❌ Bloklamaslik", callback_data=f"skip_{chat.id}_{user_id}")]
    ])
    
    try:
        await client.send_message(
            channel_owner_id,
            f"👤 **YANGI A'ZO!**\n\n📌 Kanal: {chat.title}\n👤 {full_name}\n🆔 `{user_id}`\n📱 {username}\n⏰ {format_time(join_time, channel_owner_id)}",
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
        await message.reply_text("❌ /allow [user_id]")
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
                    await client.send_message(new_user_id, "✅ Sizga ruxsat berildi! /start")
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
        await message.reply_text("❌ /disallow [user_id]")
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
    
    text = "👥 **RUXSATLANGANLAR**\n\n"
    
    for uid in AUTHORIZED_USERS:
        if uid == YOUR_ID:
            continue
        try:
            user = await client.get_users(uid)
            name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            text += f"• {name}\n  ID: `{uid}`\n"
            if uid in user_channels:
                text += f"  📌 {user_channels[uid]['title']}\n"
            text += "\n"
        except:
            text += f"• Noma'lum\n  ID: `{uid}`\n\n"
    
    await message.reply_text(text)

@app.on_message(filters.command("settime"))
async def set_time_command(client, message):
    user_id = message.from_user.id
    
    if not is_authorized(user_id):
        await message.reply_text("❌ Ruxsat yo'q!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        current = time_settings.get(user_id, 5)
        await message.reply_text(f"🕐 Hozirgi: UTC+{current}\nVaqt: {local_time(user_id).strftime('%H:%M %d.%m.%Y')}\n\n/settime [farq]")
        return
    
    try:
        soat_farqi = int(args[1])
        time_settings[user_id] = soat_farqi
        save_data()
        await message.reply_text(f"✅ Vaqt sozlandi: UTC+{soat_farqi}")
    except:
        await message.reply_text("❌ Xato! Masalan: /settime 5")

# ==================== CALLBACK HANDLER ====================
@app.on_callback_query()
async def handle_callbacks(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if not is_authorized(user_id):
        await callback_query.answer("Ruxsat yo'q!")
        return
    
    data = callback_query.data
    
    # ===== BARCHA MA'LUMOTLARNI YANGILASH =====
    if data == "refresh_all":
        await callback_query.message.edit_text("🔄 **Barcha ma'lumotlar yangilanmoqda...**")
        
        updated_users = 0
        for uid in AUTHORIZED_USERS:
            if uid != YOUR_ID:
                try:
                    user = await client.get_users(uid)
                    updated_users += 1
                except:
                    pass
        
        updated_channels = 0
        for chat_id in list(all_channels.keys()):
            try:
                chat = await client.get_chat(chat_id)
                for uid, ch in user_channels.items():
                    if ch['chat_id'] == chat_id:
                        user_channels[uid]['title'] = chat.title
                        break
                all_channels[chat_id]['title'] = chat.title
                updated_channels += 1
            except:
                if chat_id in all_channels:
                    del all_channels[chat_id]
                for uid, ch in list(user_channels.items()):
                    if ch['chat_id'] == chat_id:
                        del user_channels[uid]
        
        save_data()
        
        my_channels = len([c for uid, c in user_channels.items() if uid == YOUR_ID])
        total_users = len(AUTHORIZED_USERS) - 1
        total_channels = len(user_channels)
        
        text = f"👤 **Xush kelibsiz, @maestro_o!**\n\n"
        text += f"✅ **Barcha ma'lumotlar yangilandi!**\n"
        text += f"👥 {updated_users} ta foydalanuvchi\n"
        text += f"📌 {updated_channels} ta kanal\n\n"
        text += f"📊 **Statistika:**\n"
        text += f"• Kanallaringiz: {my_channels} ta\n"
        text += f"• Ruxsat berganlar: {total_users} ta\n"
        text += f"• Faol kanallar: {total_channels} ta\n\n"
        text += f"🔽 Quyidagi tugmalardan foydalaning:"
        
        await callback_query.message.edit_text(text, reply_markup=get_main_menu_keyboard())
        await callback_query.answer("✅ Barcha ma'lumotlar yangilandi!")
        return
    
    # ===== KANAL QO'SHISH =====
    if data == "add_channel":
        await callback_query.message.edit_text(
            "➕ **KANAL QO'SHISH**\n\n"
            "Ikkita usul:\n\n"
            "1. Kanal ID sini yozing: `-100123456789`\n"
            "2. Kanaldan xabar forward qiling",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Orqaga", callback_data="my_channels_list")]
            ])
        )
        await callback_query.answer()
        return
    
    # ===== BOSH MENYUGA QAYTISH =====
    if data == "back_to_main":
        my_channels = len([c for uid, c in user_channels.items() if uid == YOUR_ID])
        total_users = len(AUTHORIZED_USERS) - 1
        total_channels = len(user_channels)
        
        text = f"👤 **Xush kelibsiz, @maestro_o!**\n\n"
        text += f"📊 **Statistika:**\n"
        text += f"• Kanallaringiz: {my_channels} ta\n"
        text += f"• Ruxsat berganlar: {total_users} ta\n"
        text += f"• Faol kanallar: {total_channels} ta\n\n"
        text += f"🔽 Quyidagi tugmalardan foydalaning:"
        
        await callback_query.message.edit_text(text, reply_markup=get_main_menu_keyboard())
        await callback_query.answer()
        return
    
    # ===== KANALLARIM =====
    if data == "my_channels_list":
        await callback_query.message.edit_text("📋 **Kanallaringiz yuklanmoqda...**")
        
        my_channels = []
        for uid, channel in user_channels.items():
            if uid == YOUR_ID:
                try:
                    chat = await client.get_chat(channel['chat_id'])
                    channel['title'] = chat.title
                    my_channels.append(channel)
                except:
                    if uid in user_channels:
                        del user_channels[uid]
                    if channel['chat_id'] in all_channels:
                        del all_channels[channel['chat_id']]
                    continue
        
        save_data()
        
        text = "📋 **KANALLARIM**\n\n"
        
        if my_channels:
            for i, channel in enumerate(my_channels, 1):
                bans = len(scheduled.get(channel['chat_id'], {}))
                monitor = "🟢" if channel.get('monitor', True) else "🔴"
                text += f"{i}. {monitor} 📌 {channel['title']}\n"
                text += f"   🆔 `{channel['chat_id']}`\n"
                text += f"   ⏰ Bloklashlar: {bans} ta\n\n"
            
            keyboard = []
            for channel in my_channels:
                monitor_icon = "🟢" if channel.get('monitor', True) else "🔴"
                btn_text = f"{monitor_icon} {channel['title'][:30]}"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"my_channel_{channel['chat_id']}")])
            
            keyboard.append([InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_channel")])
            keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")])
        else:
            text += "📭 Sizda hali kanal yo'q.\n\nKanal qo'shish uchun pastdagi tugmani bosing:"
            keyboard = [
                [InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_channel")],
                [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]
            ]
        
        await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        await callback_query.answer()
        return
    
    # ===== KANAL INFO =====
    if data.startswith("my_channel_"):
        chat_id = int(data.split("_")[2])
        
        channel_title = "Kanal"
        monitor_status = True
        
        for uid, ch in user_channels.items():
            if ch['chat_id'] == chat_id:
                channel_title = ch['title']
                monitor_status = ch.get('monitor', True)
                break
        
        try:
            chat = await client.get_chat(chat_id)
            members = chat.members_count if hasattr(chat, 'members_count') else "?"
        except:
            members = "?"
        
        bans = len(scheduled.get(chat_id, {}))
        monitor_icon = "🟢" if monitor_status else "🔴"
        monitor_text = "Yoqilgan" if monitor_status else "O'chirilgan"
        
        text = f"📌 **{channel_title}**\n\n"
        text += f"🆔 `{chat_id}`\n"
        text += f"👥 A'zolar: {members}\n"
        text += f"⏰ Bloklashlar: {bans} ta\n"
        text += f"📡 Kuzatish: {monitor_icon} {monitor_text}\n\n"
        
        if bans > 0:
            text += "**Oxirgi bloklashlar:**\n"
            for uid, info in list(scheduled.get(chat_id, {}).items())[:3]:
                sana = format_time(info["time"], user_id)
                text += f"• {info['full_name']} - {sana}\n"
        
        if monitor_status:
            monitor_btn = InlineKeyboardButton("🔴 O'chirish", callback_data=f"monitor_off_{chat_id}")
        else:
            monitor_btn = InlineKeyboardButton("🟢 Yoqish", callback_data=f"monitor_on_{chat_id}")
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 A'zolar", callback_data=f"view_members_{chat_id}"),
             InlineKeyboardButton("⏰ Bloklashlar", callback_data=f"view_bans_{chat_id}")],
            [InlineKeyboardButton("📊 Statistika", callback_data=f"channel_stats_{chat_id}")],
            [monitor_btn, InlineKeyboardButton("🗑 O'chirish", callback_data=f"delete_channel_{chat_id}")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="my_channels_list")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
        await callback_query.answer()
        return
    
    # ===== MONITORNI O'CHIRISH/YOQISH =====
    if data.startswith("monitor_off_"):
        chat_id = int(data.split("_")[2])
        
        for uid, ch in user_channels.items():
            if ch['chat_id'] == chat_id:
                user_channels[uid]['monitor'] = False
                break
        
        if chat_id in all_channels:
            all_channels[chat_id]['monitor'] = False
        
        save_data()
        await callback_query.answer("✅ Kuzatish o'chirildi!")
        
        await callback_query.message.edit_text("🔄 Yangilanmoqda...")
        new_data = f"my_channel_{chat_id}"
        callback_query.data = new_data
        await handle_callbacks(client, callback_query)
        return
    
    if data.startswith("monitor_on_"):
        chat_id = int(data.split("_")[2])
        
        for uid, ch in user_channels.items():
            if ch['chat_id'] == chat_id:
                user_channels[uid]['monitor'] = True
                break
        
        if chat_id in all_channels:
            all_channels[chat_id]['monitor'] = True
        
        save_data()
        await callback_query.answer("✅ Kuzatish yoqildi!")
        
        await callback_query.message.edit_text("🔄 Yangilanmoqda...")
        new_data = f"my_channel_{chat_id}"
        callback_query.data = new_data
        await handle_callbacks(client, callback_query)
        return
    
    # ===== KANALNI O'CHIRISH =====
    if data.startswith("delete_channel_"):
        chat_id = int(data.split("_")[2])
        
        for uid, ch in list(user_channels.items()):
            if ch['chat_id'] == chat_id:
                await remove_channel_for_user(client, uid)
                break
        
        await callback_query.answer("✅ Kanal o'chirildi!")
        
        await callback_query.message.edit_text("🔄 Yangilanmoqda...")
        callback_query.data = "my_channels_list"
        await handle_callbacks(client, callback_query)
        return
    
    # ===== ADMIN PANEL =====
    if data == "admin_panel":
        await callback_query.message.edit_text("👑 **Admin panel yuklanmoqda...**")
        
        authorized_list = []
        for uid in AUTHORIZED_USERS:
            if uid != YOUR_ID:
                try:
                    user = await client.get_users(uid)
                    name = user.first_name or f"ID:{uid}"
                    authorized_list.append((uid, name))
                except:
                    authorized_list.append((uid, f"Noma'lum"))
        
        for uid, _ in authorized_list:
            if uid in user_channels:
                try:
                    chat = await client.get_chat(user_channels[uid]['chat_id'])
                    user_channels[uid]['title'] = chat.title
                except:
                    pass
        
        text = "👑 **ADMIN PANEL**\n\n"
        text += f"👥 Ruxsat berganlar: {len(authorized_list)} ta\n\n"
        
        if authorized_list:
            text += "**Ro'yxat:**\n"
            for uid, name in authorized_list[:5]:
                if uid in user_channels:
                    channel = user_channels[uid]
                    bans = len(scheduled.get(channel['chat_id'], {}))
                    monitor = "🟢" if channel.get('monitor', True) else "🔴"
                    text += f"• {monitor} {name} - 📌 {channel['title'][:20]} ({bans})\n"
                else:
                    text += f"• ❌ {name} - Kanalsiz\n"
            text += "\n"
        
        keyboard = [
            [InlineKeyboardButton("👥 Ruxsat berganlar", callback_data="admin_users_list")],
            [InlineKeyboardButton("➕ Ruxsat berish", callback_data="admin_add_user")],
            [InlineKeyboardButton("❌ Ruxsatni bekor qilish", callback_data="admin_remove_user")],
            [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]
        ]
        
        await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        await callback_query.answer()
        return
    
    # ===== RUXSAT BERGANLAR RO'YXATI =====
    if data == "admin_users_list":
        await callback_query.message.edit_text("👥 **Ruxsat berganlar yuklanmoqda...**")
        
        users_list = []
        for uid in AUTHORIZED_USERS:
            if uid != YOUR_ID:
                try:
                    user = await client.get_users(uid)
                    name = user.first_name or f"ID:{uid}"
                    users_list.append((uid, name))
                except:
                    users_list.append((uid, f"Noma'lum"))
        
        for uid, _ in users_list:
            if uid in user_channels:
                try:
                    chat = await client.get_chat(user_channels[uid]['chat_id'])
                    user_channels[uid]['title'] = chat.title
                except:
                    pass
        
        if not users_list:
            text = "📭 **RUXSAT BERGANLAR YO'Q**\n\nHali hech kimga ruxsat bermagansiz."
            keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")]]
        else:
            text = "👥 **RUXSAT BERGANLAR**\n\n"
            keyboard = []
            
            for uid, name in users_list:
                if uid in user_channels:
                    channel = user_channels[uid]
                    bans = len(scheduled.get(channel['chat_id'], {}))
                    monitor = "🟢" if channel.get('monitor', True) else "🔴"
                    btn_text = f"{monitor} {name} - {channel['title'][:15]} ({bans})"
                else:
                    btn_text = f"❌ {name} - Kanalsiz"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"user_channel_{uid}")])
            
            keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")])
        
        await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        await callback_query.answer()
        return
    
    # ===== FOYDALANUVCHI KANALI =====
    if data.startswith("user_channel_"):
        target_user_id = int(data.split("_")[2])
        
        await callback_query.message.edit_text("👤 **Foydalanuvchi kanali yuklanmoqda...**")
        
        if target_user_id not in user_channels:
            await callback_query.message.edit_text(
                "❌ Bu foydalanuvchi kanal qo'shmagan!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_users_list")]])
            )
            await callback_query.answer()
            return
        
        chat_id = user_channels[target_user_id]["chat_id"]
        channel_title = user_channels[target_user_id]["title"]
        monitor = user_channels[target_user_id].get('monitor', True)
        
        try:
            chat = await client.get_chat(chat_id)
            channel_title = chat.title
            user_channels[target_user_id]['title'] = chat.title
            members = chat.members_count if hasattr(chat, 'members_count') else "?"
        except:
            members = "?"
        
        try:
            user = await client.get_users(target_user_id)
            user_name = user.first_name or "Foydalanuvchi"
        except:
            user_name = "Noma'lum"
        
        bans = len(scheduled.get(chat_id, {}))
        monitor_icon = "🟢" if monitor else "🔴"
        
        text = f"👤 **{user_name} ning kanali**\n\n"
        text += f"{monitor_icon} 📌 {channel_title}\n"
        text += f"🆔 `{chat_id}`\n"
        text += f"👥 A'zolar: {members}\n"
        text += f"⏰ Bloklashlar: {bans} ta\n\n"
        
        if bans > 0:
            text += "**Oxirgi bloklashlar:**\n"
            for uid, info in list(scheduled.get(chat_id, {}).items())[:3]:
                sana = format_time(info["time"], user_id)
                text += f"• {info['full_name']} - {sana}\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 A'zolar", callback_data=f"view_members_{chat_id}"),
             InlineKeyboardButton("⏰ Bloklashlar", callback_data=f"view_bans_{chat_id}")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="admin_users_list")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
        await callback_query.answer()
        return
    
    # ===== ADMIN: RUXSAT BERISH =====
    if data == "admin_add_user":
        temp_data[user_id] = {"action": "awaiting_user_id"}
        await callback_query.message.edit_text(
            "➕ **RUXSAT BERISH**\n\nFoydalanuvchi ID sini yuboring:\nMisol: `123456789`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")]])
        )
        await callback_query.answer()
        return
    
    # ===== ADMIN: RUXSATNI BEKOR QILISH =====
    if data == "admin_remove_user":
        users_list = []
        for uid in AUTHORIZED_USERS:
            if uid != YOUR_ID:
                try:
                    user = await client.get_users(uid)
                    name = user.first_name or f"ID:{uid}"
                    users_list.append((uid, name))
                except:
                    users_list.append((uid, f"Noma'lum"))
        
        if not users_list:
            await callback_query.message.edit_text(
                "📭 **RUXSATLANGANLAR YO'Q**",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")]])
            )
            await callback_query.answer()
            return
        
        text = "👥 **RUXSATLANGANLAR**\n\nBekor qilmoqchi bo'lgan foydalanuvchini tanlang:\n\n"
        keyboard = []
        
        for uid, name in users_list:
            btn_text = f"❌ {name[:20]}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"confirm_remove_{uid}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")])
        
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
            [InlineKeyboardButton("✅ Ha", callback_data=f"execute_remove_{remove_user_id}"),
             InlineKeyboardButton("❌ Yo'q", callback_data="admin_remove_user")]
        ])
        
        await callback_query.message.edit_text(
            f"❓ **RUXSATNI BEKOR QILISH**\n\n👤 {user_name}\n🆔 `{remove_user_id}`\n\nTasdiqlaysizmi?",
            reply_markup=keyboard
        )
        await callback_query.answer()
        return
    
    # ===== RUXSATNI BEKOR QILISH BAJARISH =====
    if data.startswith("execute_remove_"):
        remove_user_id = int(data.split("_")[2])
        
        if remove_user_id in AUTHORIZED_USERS and remove_user_id != YOUR_ID:
            AUTHORIZED_USERS.remove(remove_user_id)
            
            if remove_user_id in user_channels:
                chat_id = user_channels[remove_user_id]["chat_id"]
                if chat_id in all_channels:
                    del all_channels[chat_id]
                if chat_id in scheduled:
                    del scheduled[chat_id]
                del user_channels[remove_user_id]
            
            save_data()
            
            await callback_query.message.edit_text(
                f"✅ **RUXSAT BEKOR QILINDI!**\n🆔 `{remove_user_id}`",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin panel", callback_data="admin_panel")]])
            )
        else:
            await callback_query.message.edit_text(
                "❌ **XATOLIK!**",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")]])
            )
        await callback_query.answer()
        return
    
    # ===== ADMIN STATISTIKA =====
    if data == "admin_stats":
        total_channels = len(user_channels)
        total_bans = sum(len(bans) for bans in scheduled.values())
        total_history = sum(len(users) for users in user_history.values())
        
        text = f"📊 **STATISTIKA**\n\n"
        text += f"👥 Ruxsat berganlar: {len(AUTHORIZED_USERS)-1} ta\n"
        text += f"📌 Faol kanallar: {total_channels} ta\n"
        text += f"⏰ Bloklashlar: {total_bans} ta\n"
        text += f"📋 Tarix: {total_history} ta\n"
        text += f"🕐 Vaqt: UTC+{time_settings.get(user_id, 5)}\n"
        text += f"📅 {local_time(user_id).strftime('%d.%m.%Y %H:%M:%S')}"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Yangilash", callback_data="admin_stats")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
        await callback_query.answer()
        return
    
    # ===== MY STATISTIKA =====
    if data == "my_stats":
        my_channels = len([c for uid, c in user_channels.items() if uid == YOUR_ID])
        my_bans = 0
        for uid, ch in user_channels.items():
            if uid == YOUR_ID:
                my_bans += len(scheduled.get(ch['chat_id'], {}))
        
        text = f"📊 **SHAXSIY STATISTIKA**\n\n"
        text += f"📋 Kanallaringiz: {my_channels} ta\n"
        text += f"⏰ Bloklashlaringiz: {my_bans} ta\n\n"
        text += f"🕐 {local_time(user_id).strftime('%H:%M %d.%m.%Y')}"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
        await callback_query.answer()
        return
    
    # ===== YORDAM =====
    if data == "help":
        text = "❓ **YORDAM**\n\n"
        text += "📌 **Komandalar:**\n"
        text += "• /allow [id] - ruxsat berish\n"
        text += "• /disallow [id] - ruxsatni bekor qilish\n"
        text += "• /users - ruxsatlanganlar\n"
        text += "• /settime [farq] - vaqt sozlash\n\n"
        text += "📌 **Tugmalar:**\n"
        text += "• 📋 Kanallarim - kanallaringiz\n"
        text += "• 👑 Admin panel - ruxsat berganlar\n"
        text += "• 🔄 Yangilash - ma'lumotlarni yangilash\n\n"
        text += "📌 **Kanalda:** @uzdramadubbot yozing - bot adminligini tekshirish"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
        await callback_query.answer()
        return
    
    # ===== VAQT SOZLASH =====
    if data == "menu_time":
        current = time_settings.get(user_id, 5)
        text = f"🕐 **VAQT SOZLASH**\n\nHozirgi: UTC+{current}\nVaqt: {local_time(user_id).strftime('%H:%M %d.%m.%Y')}"
        
        back_button = "back_to_main" if is_owner(user_id) else "back_to_user_menu"
        
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
        
        back_button = "back_to_main" if is_owner(user_id) else "back_to_user_menu"
        
        await callback_query.message.edit_text(
            f"✅ **VAQT SOZLANDI!**\n\n🕐 UTC+{soat}\n📅 {local_time(user_id).strftime('%d.%m.%Y %H:%M:%S')}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data=back_button)]])
        )
        return
    
    # ===== A'ZOLAR VA BLOKLASHLAR =====
    if data.startswith("view_members_"):
        chat_id = int(data.split("_")[2])
        await callback_query.message.edit_text("👥 **A'zolar yuklanmoqda...**")
        
        try:
            members_text = "👥 **A'ZOLAR**\n\n"
            count = 0
            async for member in client.get_chat_members(chat_id):
                if count < 50:
                    user = member.user
                    if user.username:
                        members_text += f"• @{user.username}\n"
                    else:
                        members_text += f"• {user.first_name or ''}\n"
                    count += 1
            members_text += f"\n📊 Jami: {count}+ ta"
            
            await callback_query.message.edit_text(
                members_text,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]])
            )
            await callback_query.answer()
        except Exception as e:
            await callback_query.message.edit_text(f"❌ Xatolik: {str(e)}")
        return
    
    if data.startswith("view_bans_"):
        chat_id = int(data.split("_")[2])
        
        if chat_id in scheduled and scheduled[chat_id]:
            text = "⏰ **BLOKLASHLAR**\n\n"
            for uid, info in scheduled[chat_id].items():
                sana = format_time(info["time"], user_id)
                text += f"• {info['full_name']} - {sana}\n"
        else:
            text = "📭 **BLOKLASHLAR YO'Q**"
        
        await callback_query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]])
        )
        await callback_query.answer()
        return
    
    if data.startswith("channel_stats_"):
        chat_id = int(data.split("_")[2])
        bans = len(scheduled.get(chat_id, {}))
        history = len(user_history.get(chat_id, {}))
        
        text = f"📊 **KANAL STATISTIKASI**\n\n"
        text += f"⏰ Bloklashlar: {bans} ta\n"
        text += f"📋 Tarix: {history} ta"
        
        await callback_query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]])
        )
        await callback_query.answer()
        return
    
    # ===== BAN CALLBACKLARI =====
    if data.startswith("ban_"):
        parts = data.split('_')
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
        
        await callback_query.message.edit_text(
            f"✅ **BLOKLASH REJALASHTIRILDI!**\n\n👤 {full_name}\n🆔 `{target_user_id}`\n⏰ {time_str}\n📅 {sana}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="bans")]])
        )
        await callback_query.answer("✅ Rejalashtirildi!")
        return
    
    if data.startswith("skip_"):
        parts = data.split('_')
        if len(parts) >= 3:
            chat_id = int(parts[1])
            target_user_id = int(parts[2])
        else:
            await callback_query.answer("Noto'g'ri format!")
            return
        
        await callback_query.message.edit_text(
            f"❌ **BLOKLASH BEKOR QILINDI**\n\n👤 `{target_user_id}`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="bans")]])
        )
        await callback_query.answer("❌ Bekor qilindi")
        return

# ==================== VAQTLI BLOKLASH TEKSHIRUVI ====================
async def check_bans():
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
                                        f"🚫 **BLOKLANDI!**\n\n👤 {data['full_name']}\n🆔 `{user_id}`\n📅 Qo'shilgan: {join_str}\n📅 Bloklangan: {ban_str}\n⏱️ Kanalda: {time_text}"
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
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(check_bans())

if __name__ == "__main__":
    print("=" * 60)
    print("✅ ABADIY BLOKLASH BOTI ISHGA TUSHDI!")
    print("=" * 60)
    print(f"🤖 Bot: @uzdramadubbot")
    print(f"👑 Admin: @maestro_o (ID: {YOUR_ID})")
    print("=" * 60)
    print("📋 **XUSUSIYATLAR:**")
    print("   • 📋 Kanallarim - monitoring bilan")
    print("   • 👑 Admin panel - ruxsat berganlar")
    print("   • 🔄 Yangilash - barcha ma'lumotlar")
    print("   • 📢 Kanalda @uzdramadubbot yozing - tekshirish")
    print("=" * 60)
    
    ban_thread = threading.Thread(target=run_ban_check, daemon=True)
    ban_thread.start()
    
    app.run()
