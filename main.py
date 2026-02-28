from datetime import datetime, timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import asyncio
import threading
import time

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
user_history = {}  # Yangi: foydalanuvchilar tarixi

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

# ==================== YANGI FOYDALANUVCHI QO'SHILGANDA ====================
@app.on_chat_member_updated()
async def on_chat_member_update(client, chat_member_updated):
    """Kanalga yangi odam qo'shilganda habar berish"""
    chat = chat_member_updated.chat
    new_member = chat_member_updated.new_chat_member
    old_member = chat_member_updated.old_chat_member
    
    # Faqat kanallarni tekshirish
    if chat.type != enums.ChatType.CHANNEL:
        return
    
    # Faqat sizning kanalingizni tekshirish
    if chat.id != YOUR_CHANNEL_ID:
        return
    
    # Yangi a'zo qo'shilganini aniqlash
    if new_member and not old_member:
        user = new_member.user
        join_time = datetime.now()
        
        # Bot emasligini tekshirish
        if user.is_bot:
            return
        
        # Foydalanuvchi ma'lumotlari
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
        
        # Vaqtni belgilash uchun tugmalar
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
        
        # Sizga xabar yuborish
        await client.send_message(
            YOUR_ID,
            f"👤 **YANGI A'ZO QO'SHILDI!**\n\n"
            f"📌 **Kanal:** {chat.title}\n"
            f"🆔 **ID:** `{user_id}`\n"
            f"📱 **Username:** {username}\n"
            f"👤 **Ism:** {full_name}\n"
            f"🔗 **Profil:** tg://user?id={user_id}\n\n"
            f"⏰ **Qo'shilgan vaqt:** {join_time.strftime('%H:%M %d.%m.%Y')}\n\n"
            f"⚠️ **Bu foydalanuvchini bloklashni rejalashtirasizmi?**",
            reply_markup=keyboard
        )
        
        print(f"👤 Yangi a'zo: {full_name} ({user_id}) - {join_time}")

# ==================== TUGMALARGA JAVOB ====================
@app.on_callback_query()
async def handle_callback(client, callback_query: CallbackQuery):
    """Tugmalar bosilganda ishlaydi"""
    data = callback_query.data
    user_id = callback_query.from_user.id
    
    # Faqat siz bosgan tugmalarni qabul qilish
    if user_id != YOUR_ID:
        await callback_query.answer("Bu tugmalar faqat bot egasi uchun!")
        return
    
    # Ma'lumotlarni ajratish
    parts = data.split('_')
    
    if parts[0] == "ban":
        target_user_id = int(parts[1])
        time_str = parts[2]
        
        # Foydalanuvchi ma'lumotlarini olish
        try:
            user = await client.get_users(target_user_id)
            username = f"@{user.username}" if user.username else "username yo'q"
            full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        except:
            username = "noma'lum"
            full_name = "noma'lum"
        
        # Vaqtni hisoblash
        minutes = parse_time(time_str)
        ban_time = datetime.now() + timedelta(minutes=minutes)
        
        # Bloklashni rejalashtirish
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
        
        # Foydalanuvchi tarixini yangilash
        if target_user_id in user_history:
            user_history[target_user_id]["scheduled_ban"] = ban_time
            user_history[target_user_id]["ban_time_str"] = time_str
        
        # Vaqtni formatlash
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
            f"🚫 **Tur:** {time_str} dan keyin ABADIY bloklanadi\n\n"
            f"⚠️ Vaqt kelganda ABADIY bloklanadi!",
            reply_markup=None
        )
        await callback_query.answer("✅ Bloklash rejalashtirildi!")
        
    elif parts[0] == "skip":
        target_user_id = int(parts[1])
        
        # Foydalanuvchi ma'lumotlari
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

# ==================== START KOMANDASI ====================
@app.on_message(filters.command("start"))
async def start_command(client, message):
    """Start komandasi"""
    user_id = message.from_user.id
    
    if is_owner(user_id):
        await message.reply_text(
            "✅ **ABADIY BLOKLASH BOTI**\n\n"
            "👤 **Xush kelibsiz, @maestro_o!**\n\n"
            f"📌 **SIZNING KANALINGIZ:** `{YOUR_CHANNEL_ID}`\n\n"
            "**📌 YANGI FUNKSIYA:**\n"
            "🔹 Kanalga yangi odam qo'shilganda SIZGA xabar keladi\n"
            "🔹 Tugmalar orqali bloklash vaqtini tanlaysiz\n"
            "🔹 Bloklanganda to'liq ma'lumot beriladi:\n"
            "   • Qachon qo'shilgani\n"
            "   • Qachon bloklangani\n"
            "   • ID va Username\n\n"
            "**📌 QISQA KOMANDALAR:**\n"
            "🔹 /setban @user 5m  - 5 minutdan keyin abadiy\n"
            "🔹 /setban @user 10k - 10 kundan keyin abadiy\n"
            "🔹 /setban @user 20k - 20 kundan keyin abadiy\n"
            "🔹 /setban @user 30k - 30 kundan keyin abadiy\n"
            "🔹 /setban @user 40k - 40 kundan keyin abadiy\n\n"
            "**📌 ID ORQALI:**\n"
            "🔹 /setbanid 123456789 5m  - 5 minut\n"
            "🔹 /setbanid 123456789 10k - 10 kun\n"
            "🔹 /setbanid 123456789 20k - 20 kun\n"
            "🔹 /setbanid 123456789 30k - 30 kun\n"
            "🔹 /setbanid 123456789 40k - 40 kun\n\n"
            "**📌 BOSHQA:**\n"
            "🔹 /select - Kanalni tanlash\n"
            "🔹 /members - A'zolar ro'yxati\n"
            "🔹 /list - Bloklashlar ro'yxati\n"
            "🔹 /history - Bloklanganlar tarixi\n"
            "🔹 /cancelban @user/ID - Bekor qilish"
        )
    else:
        await message.reply_text(
            "👋 **VAQTLI BLOKLASH BOTI**\n\n"
            "❌ **Kechirasiz, bu bot shaxsiy foydalanish uchun.**\n"
            "Faqat @maestro_o ishlata oladi."
        )

# ==================== BLOKLANGANLAR TARIXI ====================
@app.on_message(filters.command("history"))
async def show_history(client, message):
    """Bloklangan foydalanuvchilar tarixini ko'rsatish"""
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    if not user_history:
        await message.reply_text("📭 Hech qanday ma'lumot yo'q")
        return
    
    text = "📋 **FOYDALANUVCHILAR TARIXI**\n\n"
    
    for uid, data in list(user_history.items())[:20]:  # So'nggi 20 ta
        join_time = data.get("join_time", datetime.now()).strftime("%d.%m.%Y %H:%M")
        leave_time = data.get("leave_time", "Hali ketmagan")
        status = data.get("status", "active")
        
        status_emoji = "✅" if status == "active" else "❌"
        
        text += f"{status_emoji} **ID:** `{uid}`\n"
        text += f"   👤 {data.get('full_name', 'noma\'lum')}\n"
        text += f"   📱 {data.get('username', 'noma\'lum')}\n"
        text += f"   📅 Qo'shilgan: {join_time}\n"
        
        if data.get("scheduled_ban"):
            ban_time = data["scheduled_ban"].strftime("%d.%m.%Y %H:%M")
            text += f"   ⏰ Bloklanadi: {ban_time} ({data.get('ban_time_str', 'noma\'lum')})\n"
        
        text += "\n"
    
    text += f"\n📊 Jami: {len(user_history)} ta foydalanuvchi"
    await message.reply_text(text)

# ==================== KANAL XABARLARINI USHLASH ====================
@app.on_message(filters.channel & filters.text)
async def track_channels(client, message):
    """Bot kanalda mention qilinganda javob qaytarish"""
    chat = message.chat
    if chat.type in [enums.ChatType.CHANNEL]:
        if message.text and "@uzdramadubbot" in message.text.lower():
            bot_channels[chat.id] = {
                "title": chat.title,
                "username": chat.username,
                "id": chat.id,
                "last_seen": datetime.now()
            }
            print(f"✅ Kanal saqlandi: {chat.title} ({chat.id})")
            
            try:
                await message.reply_text(
                    f"✅ **KANAL QABUL QILINDI!**\n\n"
                    f"📌 **{chat.title}**\n"
                    f"🆔 ID: `{chat.id}`\n\n"
                    f"Endi botda /select {chat.id} yozib ko'ring!"
                )
            except:
                pass

# ==================== KANALNI TANLASH ====================
@app.on_message(filters.command("select"))
async def select_channel(client, message):
    """Kanalni tanlash"""
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
        
        await message.reply_text("⏳ Tekshirilmoqda...")
        
        chat = await client.get_chat(chat_id)
        
        # Bot adminligini tekshirish
        is_admin = False
        me = await client.get_me()
        
        try:
            bot_member = await client.get_chat_member(chat_id, me.id)
            if bot_member.status in ["administrator", "creator"]:
                is_admin = True
        except:
            pass
        
        if not is_admin:
            await message.reply_text(
                f"❌ **Bot admin emas!**\n\n"
                f"Kanal: {chat.title}\n"
                f"ID: `{chat_id}`"
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
        
        await message.reply_text(
            f"✅ **KANAL TANLANDI!**\n\n"
            f"📌 **Nomi:** {chat.title}\n"
            f"🆔 **ID:** `{chat.id}`\n"
            f"👥 **A'zolar:** {chat.members_count if hasattr(chat, 'members_count') else 'noma\'lum'}\n\n"
            f"📋 **Endi quyidagilarni qilishingiz mumkin:**\n"
            f"🔹 /members - A'zolar ro'yxati\n"
            f"🔹 /setban @user 30k - Bloklash\n"
            f"🔹 /setbanid 123456789 30k - ID orqali"
        )
        
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

# ==================== A'ZOLAR RO'YXATI ====================
@app.on_message(filters.command("members"))
async def get_members(client, message):
    """Kanal a'zolarini ID bilan ko'rsatish"""
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    if user_id not in selected_channel:
        await message.reply_text("❌ Avval /select ni bosing!")
        return
    
    chat_id = selected_channel[user_id]["chat_id"]
    channel_title = selected_channel[user_id]["title"]
    
    await message.reply_text(f"⏳ A'zolar yuklanmoqda...")
    
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
        
        await message.reply_text(text)
        
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

# ==================== USERNAME ORQALI BLOKLASH ====================
@app.on_message(filters.command("setban"))
async def set_ban(client, message):
    """Username orqali bloklashni rejalashtirish"""
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return

    args = message.text.split()
    if len(args) < 3:
        await message.reply_text(
            "❌ **Noto'g'ri format!**\n\n"
            "Misol:\n"
            "/setban @user 5m\n"
            "/setban @user 30k"
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
        
        # Foydalanuvchi tarixini saqlash
        if user.id not in user_history:
            user_history[user.id] = {
                "username": f"@{user.username}" if user.username else "username yo'q",
                "full_name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
                "join_time": datetime.now(),
                "scheduled_ban": ban_time,
                "ban_time_str": time_str
            }
        
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

# ==================== ID ORQALI BLOKLASH ====================
@app.on_message(filters.command("setbanid"))
async def set_ban_by_id(client, message):
    """ID orqali bloklashni rejalashtirish"""
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    args = message.text.split()
    if len(args) < 3:
        await message.reply_text(
            "❌ **Noto'g'ri format!**\n\n"
            "Misol: /setbanid 123456789 30k"
        )
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
        
        # Foydalanuvchi tarixini saqlash
        if user.id not in user_history:
            user_history[user.id] = {
                "username": f"@{user.username}" if user.username else "username yo'q",
                "full_name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
                "join_time": datetime.now(),
                "scheduled_ban": ban_time,
                "ban_time_str": time_str
            }
        
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

# ==================== BLOKLASHLAR RO'YXATI ====================
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

# ==================== BLOKLASHNI BEKOR QILISH ====================
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
                                
                                # Foydalanuvchi tarixini yangilash
                                if user_id in user_history:
                                    user_history[user_id]["leave_time"] = now
                                    user_history[user_id]["status"] = "banned"
                                
                                # Qo'shilgan vaqtni olish
                                join_time = data.get("join_time", now)
                                join_str = join_time.strftime("%d.%m.%Y %H:%M")
                                ban_str = now.strftime("%d.%m.%Y %H:%M")
                                
                                # Kanalda qancha vaqt bo'lganini hisoblash
                                time_in_channel = now - join_time
                                days = time_in_channel.days
                                hours = time_in_channel.seconds // 3600
                                
                                if days > 0:
                                    time_str = f"{days} kun {hours} soat"
                                else:
                                    time_str = f"{hours} soat"
                                
                                print(f"✅ ABADIY bloklandi: {data['full_name']}")
                                
                                # Sizga xabar yuborish
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
                                        f"🚫 **Holat:** ABADIY bloklandi\n\n"
                                        f"⚠️ Foydalanuvchi kanalda {time_str} bo'lib, ABADIY bloklandi!"
                                    )
                                except:
                                    pass
                                
                                del scheduled[chat_id][user_id]
                                
                            except Exception as e:
                                print(f"❌ Bloklash xatosi: {e}")
            except Exception as e:
                print(f"Tekshirish xatosi: {e}")
            await asyncio.sleep(60)
    
    loop.run_until_complete(check())

# Threadda ishga tushirish
thread = threading.Thread(target=check_bans_background, daemon=True)
thread.start()

print("=" * 60)
print("✅ ABADIY BLOKLASH BOTI ISHGA TUSHDI!")
print("=" * 60)
print(f"🤖 Bot: @uzdramadubbot")
print(f"👤 Egasi: @maestro_o (ID: {YOUR_ID})")
print(f"📌 Kanal ID: {YOUR_CHANNEL_ID}")
print("=" * 60)
print("📋 **YANGI FUNKSIYALAR:**")
print("   👤 Kanalga yangi odam qo'shilganda xabar")
print("   📊 Bloklanganda to'liq statistika:")
print("      • Qachon qo'shilgani")
print("      • Qachon bloklangani")
print("      • Kanalda qancha vaqt bo'lgani")
print("      • ID va Username")
print("=" * 60)

app.run()
