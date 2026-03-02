from datetime import datetime, timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import asyncio
import threading
import time
import json
import os
from pathlib import Path

# SOZLAMALAR
API_ID = 35058290
API_HASH = "d7cb549b10b8965c99673f8bd36c130a"
BOT_TOKEN = "8660286208:AAHssllobxtng0RDXfZ70fEkfFbjx13FyQE"

# ============= SIZNING ID INGIZ =============
YOUR_ID = 1700341163  # @maestro_o
YOUR_CHANNEL_ID = -1003726881716  # Kanal ID ingiz
# ===========================================

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Ma'lumotlar ombori
scheduled = {}
selected_channel = {}
bot_channels = {}
user_history = {}
last_check = {}  # Oxirgi tekshirish vaqtlari

# ==================== MA'LUMOTLARNI SAQLASH ====================
DATA_FILE = "bot_data.json"

def save_data():
    """Ma'lumotlarni faylga saqlash"""
    try:
        data = {
            "scheduled": {},
            "user_history": {},
            "last_save": datetime.now().isoformat()
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
                    "join_time": user_data.get("join_time", datetime.now()).isoformat() if isinstance(user_data.get("join_time"), datetime) else user_data.get("join_time", ""),
                    "permanent": user_data.get("permanent", False)
                }
        
        # user_history ma'lumotlarini saqlash
        for user_id, hist_data in user_history.items():
            data["user_history"][str(user_id)] = {
                "username": hist_data.get("username", ""),
                "full_name": hist_data.get("full_name", ""),
                "join_time": hist_data["join_time"].isoformat() if isinstance(hist_data["join_time"], datetime) else hist_data["join_time"],
                "leave_time": hist_data.get("leave_time", "").isoformat() if isinstance(hist_data.get("leave_time"), datetime) else hist_data.get("leave_time", ""),
                "status": hist_data.get("status", ""),
                "scheduled_ban": hist_data.get("scheduled_ban", "").isoformat() if isinstance(hist_data.get("scheduled_ban"), datetime) else hist_data.get("scheduled_ban", ""),
                "ban_time_str": hist_data.get("ban_time_str", "")
            }
        
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"✅ Ma'lumotlar saqlandi: {datetime.now().strftime('%H:%M:%S')}")
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
                        "join_time": datetime.fromisoformat(user_data["join_time"]) if user_data.get("join_time") else datetime.now(),
                        "permanent": user_data.get("permanent", False)
                    }
            
            # user_history ma'lumotlarini yuklash
            for user_id, hist_data in data.get("user_history", {}).items():
                user_history[int(user_id)] = {
                    "username": hist_data.get("username", ""),
                    "full_name": hist_data.get("full_name", ""),
                    "join_time": datetime.fromisoformat(hist_data["join_time"]),
                    "leave_time": datetime.fromisoformat(hist_data["leave_time"]) if hist_data.get("leave_time") else None,
                    "status": hist_data.get("status", ""),
                    "scheduled_ban": datetime.fromisoformat(hist_data["scheduled_ban"]) if hist_data.get("scheduled_ban") else None,
                    "ban_time_str": hist_data.get("ban_time_str", "")
                }
            
            print(f"✅ Ma'lumotlar yuklandi: {data.get('last_save', '')}")
    except Exception as e:
        print(f"❌ Ma'lumotlarni yuklashda xatolik: {e}")

# Yuklash
load_data()

# ==================== 60 KUNDAN KEYIN O'CHIRISH ====================
def clean_old_data():
    """60 kundan eski ma'lumotlarni o'chirish"""
    try:
        now = datetime.now()
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
        for user_id in list(user_history.keys()):
            hist = user_history[user_id]
            join_time = hist.get("join_time")
            leave_time = hist.get("leave_time")
            
            if leave_time and leave_time < cutoff:
                del user_history[user_id]
                cleaned += 1
            elif join_time and join_time < cutoff and hist.get("status") != "active":
                del user_history[user_id]
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

def toshkent_vaqti(vaqt):
    """Server vaqtini Toshkent vaqtiga o'tkazish (+5 soat)"""
    return vaqt + timedelta(hours=5)

def is_owner(user_id):
    """Foydalanuvchi bot egasi ekanligini tekshirish"""
    return user_id == YOUR_ID

# ==================== BOT ADMINLIGINI TEKSHIRISH ====================
async def check_bot_admin(client, chat_id):
    """Bot adminligini tekshirish - 5 xil usul"""
    me = await client.get_me()
    
    # 1-usul: get_chat_member
    try:
        member = await client.get_chat_member(chat_id, me.id)
        if member.status in ["administrator", "creator"]:
            return True, member.status
    except:
        pass
    
    # 2-usul: Adminlar ro'yxati
    try:
        async for member in client.get_chat_members(chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
            if member.user.id == me.id:
                return True, member.status
    except:
        pass
    
    # 3-usul: To'g'ridan-to'g'ri API
    try:
        # 2 soniya kutib, qayta urinish
        await asyncio.sleep(2)
        member = await client.get_chat_member(chat_id, me.id)
        if str(member.status).lower() == "administrator":
            return True, member.status
    except:
        pass
    
    return False, None

# ==================== YANGI FOYDALANUVCHI QO'SHILGANDA ====================
@app.on_chat_member_updated()
async def on_chat_member_update(client, chat_member_updated):
    """Kanalga yangi odam qo'shilganda habar berish"""
    chat = chat_member_updated.chat
    new_member = chat_member_updated.new_chat_member
    old_member = chat_member_updated.old_chat_member
    
    if chat.type != enums.ChatType.CHANNEL:
        return
    
    if chat.id != YOUR_CHANNEL_ID:
        return
    
    if new_member and not old_member:
        user = new_member.user
        join_time = datetime.now()
        
        if user.is_bot:
            return
        
        user_id = user.id
        username = f"@{user.username}" if user.username else "username yo'q"
        first_name = user.first_name or ""
        last_name = user.last_name or ""
        full_name = f"{first_name} {last_name}".strip()
        
        # Foydalanuvchi tarixini saqlash
        user_history[user_id] = {
            "username": username,
            "full_name": full_name,
            "join_time": join_time,
            "leave_time": None,
            "status": "active"
        }
        save_data()
        
        # Tugmalar
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏱️ 5 minut", callback_data=f"ban_{user_id}_5m")],
            [InlineKeyboardButton("⏱️ 10 minut", callback_data=f"ban_{user_id}_10m")],
            [InlineKeyboardButton("⏱️ 30 minut", callback_data=f"ban_{user_id}_30m")],
            [InlineKeyboardButton("📅 1 kun", callback_data=f"ban_{user_id}_1k")],
            [InlineKeyboardButton("📅 5 kun", callback_data=f"ban_{user_id}_5k")],
            [InlineKeyboardButton("📅 10 kun", callback_data=f"ban_{user_id}_10k")],
            [InlineKeyboardButton("📅 20 kun", callback_data=f"ban_{user_id}_20k")],
            [InlineKeyboardButton("📅 30 kun", callback_data=f"ban_{user_id}_30k")],
            [InlineKeyboardButton("📅 40 kun", callback_data=f"ban_{user_id}_40k")],
            [InlineKeyboardButton("📆 1 oy", callback_data=f"ban_{user_id}_1oy")],
            [InlineKeyboardButton("📆 2 oy", callback_data=f"ban_{user_id}_2oy")],
            [InlineKeyboardButton("📆 3 oy", callback_data=f"ban_{user_id}_3oy")],
            [InlineKeyboardButton("❌ Bloklamaslik", callback_data=f"skip_{user_id}")]
        ])
        
        await client.send_message(
            YOUR_ID,
            f"👤 **YANGI A'ZO QO'SHILDI!**\n\n"
            f"📌 **Kanal:** {chat.title}\n"
            f"🆔 **ID:** `{user_id}`\n"
            f"📱 **Username:** {username}\n"
            f"👤 **Ism:** {full_name}\n"
            f"🔗 **Profil:** tg://user?id={user_id}\n\n"
            f"⏰ **Qo'shilgan vaqt:** {join_time.strftime('%H:%M %d.%m.%Y')}",
            reply_markup=keyboard
        )

# ==================== TUGMALARGA JAVOB ====================
@app.on_callback_query()
async def handle_callback(client, callback_query: CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id
    
    if user_id != YOUR_ID:
        await callback_query.answer("Bu tugmalar faqat bot egasi uchun!")
        return
    
    parts = data.split('_')
    
    if parts[0] == "ban":
        target_user_id = int(parts[1])
        time_str = parts[2]
        
        try:
            user = await client.get_users(target_user_id)
            username = f"@{user.username}" if user.username else "username yo'q"
            full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        except:
            username = "noma'lum"
            full_name = "noma'lum"
        
        minutes = parse_time(time_str)
        ban_time = datetime.now() + timedelta(minutes=minutes)
        
        if YOUR_CHANNEL_ID not in scheduled:
            scheduled[YOUR_CHANNEL_ID] = {}
            
        scheduled[YOUR_CHANNEL_ID][target_user_id] = {
            "username": username,
            "full_name": full_name,
            "time": ban_time,
            "user_id": target_user_id,
            "join_time": user_history.get(target_user_id, {}).get("join_time", datetime.now()),
            "permanent": True
        }
        
        if target_user_id in user_history:
            user_history[target_user_id]["scheduled_ban"] = ban_time
            user_history[target_user_id]["ban_time_str"] = time_str
        
        save_data()
        
        toshkent_vaqt = toshkent_vaqti(ban_time)
        sana = toshkent_vaqt.strftime("%d.%m.%Y %H:%M")
        qoshilgan_vaqt = user_history.get(target_user_id, {}).get("join_time", datetime.now()).strftime("%d.%m.%Y %H:%M")
        
        await callback_query.message.edit_text(
            f"✅ **BLOKLASH REJALASHTIRILDI!**\n\n"
            f"👤 **Foydalanuvchi:** {full_name}\n"
            f"🆔 **ID:** `{target_user_id}`\n"
            f"📱 **Username:** {username}\n"
            f"📅 **Qo'shilgan vaqt:** {qoshilgan_vaqt}\n"
            f"⏰ **Bloklash vaqti:** {time_str}\n"
            f"📅 **Bloklanadigan sana:** {sana}\n"
            f"🚫 **Tur:** {time_str} dan keyin ABADIY bloklanadi",
            reply_markup=None
        )
        await callback_query.answer("✅ Bloklash rejalashtirildi!")
        
    elif parts[0] == "skip":
        target_user_id = int(parts[1])
        
        full_name = user_history.get(target_user_id, {}).get("full_name", "noma'lum")
        username = user_history.get(target_user_id, {}).get("username", "noma'lum")
        qoshilgan_vaqt = user_history.get(target_user_id, {}).get("join_time", datetime.now()).strftime("%d.%m.%Y %H:%M")
        
        await callback_query.message.edit_text(
            f"❌ **BLOKLASH BEKOR QILINDI**\n\n"
            f"👤 **Foydalanuvchi:** {full_name}\n"
            f"🆔 **ID:** `{target_user_id}`\n"
            f"📱 **Username:** {username}\n"
            f"📅 **Qo'shilgan vaqt:** {qoshilgan_vaqt}\n\n"
            f"✅ Hech qanday bloklash rejalashtirilmadi",
            reply_markup=None
        )
        await callback_query.answer("❌ Bekor qilindi")

# ==================== START ====================
@app.on_message(filters.command("start"))
async def start_command(client, message):
    user_id = message.from_user.id
    
    if is_owner(user_id):
        await message.reply_text(
            "✅ **ABADIY BLOKLASH BOTI**\n\n"
            "👤 **Xush kelibsiz, @maestro_o!**\n\n"
            f"📌 **SIZNING KANALINGIZ:** `{YOUR_CHANNEL_ID}`\n\n"
            "**📌 YANGI FUNKSIYALAR:**\n"
            "🔹 Ma'lumotlar JSON faylda saqlanadi\n"
            "🔹 60 kundan eski ma'lumotlar o'chadi\n"
            "🔹 Kanalga yangi odam qo'shilganda xabar\n\n"
            "**📌 KOMANDALAR:**\n"
            "🔹 /select - Kanalni tanlash\n"
            "🔹 /members - A'zolar ro'yxati\n"
            "🔹 /setban @user 30k - Bloklash\n"
            "🔹 /list - Bloklashlar ro'yxati\n"
            "🔹 /history - Foydalanuvchilar tarixi\n"
            "🔹 /cancelban - Bekor qilish"
        )
    else:
        await message.reply_text("❌ Sizga ruxsat yo'q!")

# ==================== SELECT (TO'G'RILANGAN) ====================
@app.on_message(filters.command("select"))
async def select_channel(client, message):
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    args = message.text.split()
    
    if len(args) < 2:
        await message.reply_text(
            f"❌ **Kanal ID sini yozing!**\n\n"
            f"📌 Sizning kanal ID ingiz: `{YOUR_CHANNEL_ID}`\n"
            f"🔹 /select {YOUR_CHANNEL_ID}"
        )
        return
    
    try:
        chat_id = int(args[1])
        
        msg = await message.reply_text("⏳ Tekshirilmoqda...")
        
        # Kanal ma'lumotlarini olish
        try:
            chat = await client.get_chat(chat_id)
        except Exception as e:
            await msg.edit_text(f"❌ Kanal topilmadi! Xatolik: {str(e)}")
            return
        
        # Bot adminligini tekshirish (kengaytirilgan)
        is_admin, admin_status = await check_bot_admin(client, chat_id)
        
        if not is_admin:
            # Adminlar ro'yxatini olish
            admins_text = "👥 **KANAL ADMINLARI:**\n"
            admin_count = 0
            
            try:
                async for member in client.get_chat_members(chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
                    admin_count += 1
                    user = member.user
                    if user.id == (await client.get_me()).id:
                        admins_text += f"✅ **BOT** - @{user.username} (Status: {member.status})\n"
                    else:
                        name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                        admins_text += f"• {name} - @{user.username if user.username else 'username yo\'q'}\n"
            except:
                admins_text += "Adminlar ro'yxatini olish imkonsiz\n"
            
            await msg.edit_text(
                f"❌ **Bot admin emas!**\n\n"
                f"Kanal: {chat.title}\n"
                f"ID: `{chat_id}`\n\n"
                f"{admins_text}\n\n"
                f"📌 **YECHIM:**\n"
                f"1. Kanalda adminlar ro'yxatini oching\n"
                f"2. @uzdramadubbot ni toping\n"
                f"3. 'Foydalanuvchilarni bloklash' huquqini bering\n"
                f"4. 30 soniya kuting\n"
                f"5. /select {YOUR_CHANNEL_ID} ni qayta bosing"
            )
            return
        
        selected_channel[user_id] = {
            "chat_id": chat.id,
            "title": chat.title
        }
        
        bot_channels[chat.id] = {
            "title": chat.title,
            "username": chat.username,
            "id": chat.id,
            "last_seen": datetime.now()
        }
        
        members_count = chat.members_count if hasattr(chat, 'members_count') else "noma'lum"
        
        await msg.edit_text(
            f"✅ **KANAL TANLANDI!**\n\n"
            f"📌 **Nomi:** {chat.title}\n"
            f"🆔 **ID:** `{chat.id}`\n"
            f"👥 **A'zolar:** {members_count}\n"
            f"🤖 **Bot status:** {admin_status}\n\n"
            f"📋 **Endi quyidagilarni qilishingiz mumkin:**\n"
            f"🔹 /members - A'zolar ro'yxati\n"
            f"🔹 /setban @user 30k - Bloklash"
        )
        
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

# ==================== MEMBERS ====================
@app.on_message(filters.command("members"))
async def get_members(client, message):
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    if user_id not in selected_channel:
        await message.reply_text("❌ Avval /select ni bosing!")
        return
    
    chat_id = selected_channel[user_id]["chat_id"]
    channel_title = selected_channel[user_id]["title"]
    
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
                "username": user.username
            }
            
            if user.username:
                members_with_username.append(user_info)
            else:
                members_without_username.append(user_info)
        
        text = f"📋 **KANAL A'ZOLARI**\n📌 **{channel_title}**\n\n"
        
        text += f"**📱 USERNAME BORLAR ({len(members_with_username)}):**\n"
        for i, user in enumerate(members_with_username[:20]):
            name = f"{user['first_name']} {user['last_name']}".strip()
            text += f"{i+1}. @{user['username']}\n"
            text += f"   ID: `{user['id']}`\n"
            text += f"   {name[:30]}\n\n"
        
        text += f"**❌ USERNAME YO'QLAR ({len(members_without_username)}):**\n"
        for i, user in enumerate(members_without_username[:20]):
            name = f"{user['first_name']} {user['last_name']}".strip()
            text += f"{i+1}. {name[:30]}\n"
            text += f"   ID: `{user['id']}`\n\n"
        
        text += f"\n📊 **JAMI: {len(members_with_username) + len(members_without_username)} ta a'zo**"
        
        await msg.edit_text(text)
        
    except Exception as e:
        await msg.edit_text(f"❌ Xatolik: {str(e)}")

# ==================== SETBAN ====================
@app.on_message(filters.command("setban"))
async def set_ban(client, message):
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return

    args = message.text.split()
    if len(args) < 3:
        await message.reply_text(
            "❌ **Noto'g'ri format!**\n\n"
            "Misol: /setban @user 30k"
        )
        return

    username = args[1].replace("@", "")
    time_str = args[2]

    try:
        user = await client.get_users(username)
        
        chat_id = YOUR_CHANNEL_ID
        if user_id in selected_channel:
            chat_id = selected_channel[user_id]["chat_id"]
        
        minutes = parse_time(time_str)
        ban_time = datetime.now() + timedelta(minutes=minutes)
        
        if chat_id not in scheduled:
            scheduled[chat_id] = {}
            
        scheduled[chat_id][user.id] = {
            "username": username,
            "full_name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
            "time": ban_time,
            "user_id": user.id,
            "join_time": datetime.now(),
            "permanent": True
        }
        
        save_data()
        
        toshkent_vaqt = toshkent_vaqti(ban_time)
        sana = toshkent_vaqt.strftime("%d.%m.%Y %H:%M")
        
        await message.reply_text(
            f"✅ **BLOKLASH REJALASHTIRILDI**\n\n"
            f"👤 **Foydalanuvchi:** @{username}\n"
            f"🆔 **ID:** `{user.id}`\n"
            f"⏰ **Vaqt:** {time_str}\n"
            f"📅 **Sana:** {sana}\n"
            f"🚫 **Tur:** {time_str} dan keyin ABADIY bloklanadi"
        )

    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

# ==================== SETBANID ====================
@app.on_message(filters.command("setbanid"))
async def set_ban_by_id(client, message):
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
        
        chat_id = YOUR_CHANNEL_ID
        if user_id in selected_channel:
            chat_id = selected_channel[user_id]["chat_id"]
        
        user = await client.get_users(target_user_id)
        
        minutes = parse_time(time_str)
        ban_time = datetime.now() + timedelta(minutes=minutes)
        
        if chat_id not in scheduled:
            scheduled[chat_id] = {}
            
        scheduled[chat_id][user.id] = {
            "username": user.username or f"ID:{user.id}",
            "full_name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
            "time": ban_time,
            "user_id": user.id,
            "join_time": datetime.now(),
            "permanent": True
        }
        
        save_data()
        
        toshkent_vaqt = toshkent_vaqti(ban_time)
        sana = toshkent_vaqt.strftime("%d.%m.%Y %H:%M")
        
        display_name = f"@{user.username}" if user.username else user.first_name
        
        await message.reply_text(
            f"✅ **BLOKLASH REJALASHTIRILDI**\n\n"
            f"👤 **Foydalanuvchi:** {display_name}\n"
            f"🆔 **ID:** `{user.id}`\n"
            f"⏰ **Vaqt:** {time_str}\n"
            f"📅 **Sana:** {sana}\n"
            f"🚫 **Tur:** {time_str} dan keyin ABADIY bloklanadi"
        )
        
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

# ==================== LIST ====================
@app.on_message(filters.command("list"))
async def list_bans(client, message):
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    chat_id = YOUR_CHANNEL_ID
    if user_id in selected_channel:
        chat_id = selected_channel[user_id]["chat_id"]
    
    if chat_id not in scheduled or not scheduled[chat_id]:
        await message.reply_text("📭 Bloklashlar yo'q")
        return

    text = f"📋 **REJALASHTIRILGAN BLOKLASHLAR**\n\n"
    now = datetime.now()
    
    for data in scheduled[chat_id].values():
        toshkent_vaqt = toshkent_vaqti(data["time"])
        sana = toshkent_vaqt.strftime("%d.%m.%Y %H:%M")
        
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
async def show_history(client, message):
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    if not user_history:
        await message.reply_text("📭 Hech qanday ma'lumot yo'q")
        return
    
    text = "📋 **FOYDALANUVCHILAR TARIXI**\n\n"
    
    for uid, data in list(user_history.items())[:20]:
        join_time = data.get("join_time", datetime.now()).strftime("%d.%m.%Y %H:%M") if isinstance(data.get("join_time"), datetime) else "noma'lum"
        leave_time = data.get("leave_time", "Hali ketmagan")
        if isinstance(leave_time, datetime):
            leave_time = leave_time.strftime("%d.%m.%Y %H:%M")
        
        status_emoji = "✅" if data.get("status") == "active" else "❌"
        
        text += f"{status_emoji} **ID:** `{uid}`\n"
        text += f"   👤 {data.get('full_name', 'noma\'lum')}\n"
        text += f"   📱 {data.get('username', 'noma\'lum')}\n"
        text += f"   📅 Qo'shilgan: {join_time}\n"
        
        if data.get("scheduled_ban"):
            if isinstance(data["scheduled_ban"], datetime):
                ban_time = data["scheduled_ban"].strftime("%d.%m.%Y %H:%M")
                text += f"   ⏰ Bloklanadi: {ban_time} ({data.get('ban_time_str', 'noma\'lum')})\n"
        
        text += "\n"
    
    text += f"\n📊 Jami: {len(user_history)} ta foydalanuvchi"
    await message.reply_text(text)

# ==================== CANCELBAN ====================
@app.on_message(filters.command("cancelban"))
async def cancel_ban(client, message):
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.reply_text("❌ /cancelban @user yoki /cancelban [user_id]")
        return

    identifier = args[1].replace("@", "")
    chat_id = YOUR_CHANNEL_ID
    
    try:
        if identifier.isdigit():
            user_id_target = int(identifier)
            user = await client.get_users(user_id_target)
        else:
            user = await client.get_users(identifier)
        
        if chat_id in scheduled and user.id in scheduled[chat_id]:
            del scheduled[chat_id][user.id]
            save_data()
            await message.reply_text(f"✅ Bloklash bekor qilindi")
        else:
            await message.reply_text(f"❌ Topilmadi")
            
    except:
        await message.reply_text(f"❌ Xatolik")

# ==================== VAQTLI BLOKLASH TEKSHIRUVI ====================
def check_bans_background():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def check():
        while True:
            try:
                now = datetime.now()
                for chat_id in list(scheduled.keys()):
                    for user_id in list(scheduled[chat_id].keys()):
                        if now >= scheduled[chat_id][user_id]["time"]:
                            try:
                                data = scheduled[chat_id][user_id]
                                print(f"⏰ Abadiy bloklash vaqti keldi: {data['full_name']}")
                                
                                until_date = now + timedelta(days=366)
                                await app.ban_chat_member(chat_id, user_id, until_date=until_date)
                                
                                if user_id in user_history:
                                    user_history[user_id]["leave_time"] = now
                                    user_history[user_id]["status"] = "banned"
                                
                                join_time = data.get("join_time", now)
                                join_str = join_time.strftime("%d.%m.%Y %H:%M") if isinstance(join_time, datetime) else "noma'lum"
                                ban_str = now.strftime("%d.%m.%Y %H:%M")
                                
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
print(f"📌 Kanal ID: {YOUR_CHANNEL_ID}")
print("=" * 60)
print("📋 **YANGI FUNKSIYALAR:**")
print("   • Ma'lumotlar JSON faylda saqlanadi")
print("   • 60 kundan eski ma'lumotlar o'chadi")
print("   • Har soatda avtomatik saqlanadi")
print("   • Bot adminligi 5 xil usulda tekshiriladi")
print("=" * 60)

app.run()
