from datetime import datetime, timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import Message
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
            return 366 * 24 * 60  # Abadiy (agar raqam bo'lmasa)
            
        number = int(number)
        
        if 'k' in time_str:  # kun (masalan: 5k, 10k, 20k, 30k, 40k)
            return number * 24 * 60
        elif 'm' in time_str:  # minut (masalan: 5m)
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
            return number * 24 * 60  # Agar birlik bo'lmasa, kun deb hisobla
    except:
        return 366 * 24 * 60  # Xato bo'lsa abadiy

def is_owner(user_id):
    """Foydalanuvchi bot egasi ekanligini tekshirish"""
    return user_id == YOUR_ID

# ==================== START KOMANDASI ====================
@app.on_message(filters.command("start"))
async def start_command(client, message):
    """Start komandasi"""
    user_id = message.from_user.id
    
    if is_owner(user_id):
        await message.reply_text(
            "✅ **ABADIY BLOKLASH BOTI**\n\n"
            "👤 **Xush kelibsiz, @maestro_o!**\n\n"
            "**📌 QISQA KOMANDALAR:**\n"
            "🔹 /setban @user 5m  - 5 minutdan keyin abadiy\n"
            "🔹 /setban @user 10k - 10 kundan keyin abadiy\n"
            "🔹 /setban @user 20k - 20 kundan keyin abadiy\n"
            "🔹 /setban @user 30k - 30 kundan keyin abadiy\n"
            "🔹 /setban @user 40k - 40 kundan keyin abadiy\n\n"
            "**📌 ID ORQALI:**\n"
            "🔹 /setbanid 123456789 5m  - 5 minut\n"
            "🔹 /setbanid 123456789 10k - 10 kun\n"
            "🔹 /setbanid 123456789 20k - 20 kun\n\n"
            "**📌 BOSHQA:**\n"
            "🔹 /select - Kanalni tanlash\n"
            "🔹 /members - A'zolar ro'yxati\n"
            "🔹 /list - Bloklashlar ro'yxati\n"
            "🔹 /cancelban @user/ID - Bekor qilish"
        )
    else:
        await message.reply_text("❌ Sizga ruxsat yo'q!")

# ==================== KANALNI TANLASH ====================
@app.on_message(filters.command("select"))
async def select_channel(client, message):
    """Kanalni tanlash"""
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    chat_id = YOUR_CHANNEL_ID
    
    await message.reply_text("⏳ Tekshirilmoqda...")
    
    try:
        chat = await client.get_chat(chat_id)
        
        # Bot adminligini tekshirish
        is_admin = False
        for i in range(3):
            try:
                bot_member = await client.get_chat_member(chat_id, "me")
                if bot_member.status in ["administrator", "creator"]:
                    is_admin = True
                    break
                await asyncio.sleep(1)
            except:
                pass
        
        if not is_admin:
            await message.reply_text(
                f"❌ **BOT ADMIN EMAS!**\n\n"
                f"Kanal: {chat.title}\n"
                f"ID: `{chat_id}`\n\n"
                f"📌 Botni admin qiling va qayta urinib ko'ring."
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
        
        await message.reply_text(
            f"✅ **KANAL TANLANDI!**\n\n"
            f"📌 **Nomi:** {chat.title}\n"
            f"🆔 **ID:** `{chat.id}`\n"
            f"👥 **A'zolar:** {members_count}\n\n"
            f"📋 **Endi quyidagilarni qilishingiz mumkin:**\n"
            f"🔹 /members - A'zolar ro'yxati\n"
            f"🔹 /setban @user 30k - Bloklash (30 kundan keyin)\n"
            f"🔹 /setbanid 123456789 5m - ID orqali"
        )
        
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

# ==================== USERNAME ORQALI BLOKLASH (ABADIY) ====================
@app.on_message(filters.command("setban"))
async def set_ban(client, message):
    """Username orqali bloklashni rejalashtirish (abadiy)"""
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return

    args = message.text.split()
    if len(args) < 3:
        await message.reply_text(
            "❌ **Noto'g'ri format!**\n\n"
            "Misol:\n"
            "/setban @user 5m  - 5 minut\n"
            "/setban @user 10k - 10 kun\n"
            "/setban @user 20k - 20 kun\n"
            "/setban @user 30k - 30 kun\n"
            "/setban @user 40k - 40 kun"
        )
        return

    username = args[1].replace("@", "")
    time_str = args[2]

    try:
        # Foydalanuvchini tekshirish
        try:
            user = await client.get_users(username)
        except:
            await message.reply_text(f"❌ @{username} topilmadi!")
            return
        
        # Qaysi kanalda bloklash kerak?
        chat_id = YOUR_CHANNEL_ID
        if user_id in selected_channel:
            chat_id = selected_channel[user_id]["chat_id"]
        
        # Vaqtni hisoblash
        minutes = parse_time(time_str)
        
        # Abadiy bloklash uchun (366 kundan ortiq)
        if minutes < 366 * 24 * 60:
            # Agar berilgan vaqt 366 kundan kam bo'lsa, o'sha vaqtdan keyin abadiy
            ban_time = datetime.now() + timedelta(minutes=minutes)
            ban_type = f"{time_str} dan keyin abadiy"
        else:
            # To'g'ridan-to'g'ri abadiy
            ban_time = datetime.now() + timedelta(minutes=minutes)
            ban_type = "abadiy"
        
        # Bloklashni rejalashtirish
        if chat_id not in scheduled:
            scheduled[chat_id] = {}
            
        scheduled[chat_id][user.id] = {
            "username": username,
            "time": ban_time,
            "user_id": user.id,
            "permanent": True  # Abadiy bloklash
        }
        
        # Vaqtni formatlash
        sana = ban_time.strftime("%d.%m.%Y %H:%M")
        
        await message.reply_text(
            f"✅ **BLOKLASH REJALASHTIRILDI**\n\n"
            f"👤 **Foydalanuvchi:** @{username}\n"
            f"🆔 **ID:** `{user.id}`\n"
            f"⏰ **Vaqt:** {time_str}\n"
            f"📅 **Sana:** {sana}\n"
            f"🚫 **Tur:** {ban_type}\n\n"
            f"⚠️ Vaqt kelganda ABADIY bloklanadi!"
        )

    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

# ==================== ID ORQALI BLOKLASH (ABADIY) ====================
@app.on_message(filters.command("setbanid"))
async def set_ban_by_id(client, message):
    """ID orqali bloklashni rejalashtirish (abadiy)"""
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    args = message.text.split()
    if len(args) < 3:
        await message.reply_text(
            "❌ **Noto'g'ri format!**\n\n"
            "Misol:\n"
            "/setbanid 123456789 5m  - 5 minut\n"
            "/setbanid 123456789 10k - 10 kun\n"
            "/setbanid 123456789 20k - 20 kun\n"
            "/setbanid 123456789 30k - 30 kun\n"
            "/setbanid 123456789 40k - 40 kun"
        )
        return
    
    try:
        target_user_id = int(args[1])
        time_str = args[2]
        
        # Qaysi kanalda bloklash kerak?
        chat_id = YOUR_CHANNEL_ID
        if user_id in selected_channel:
            chat_id = selected_channel[user_id]["chat_id"]
        
        # Kanalni tekshirish
        try:
            chat = await client.get_chat(chat_id)
        except:
            await message.reply_text("❌ Kanal topilmadi!")
            return
        
        # Foydalanuvchini tekshirish
        try:
            user = await client.get_users(target_user_id)
        except:
            await message.reply_text(f"❌ ID {target_user_id} topilmadi!")
            return
        
        # Vaqtni hisoblash
        minutes = parse_time(time_str)
        
        # Abadiy bloklash uchun (366 kundan ortiq)
        if minutes < 366 * 24 * 60:
            # Agar berilgan vaqt 366 kundan kam bo'lsa, o'sha vaqtdan keyin abadiy
            ban_time = datetime.now() + timedelta(minutes=minutes)
            ban_type = f"{time_str} dan keyin abadiy"
        else:
            # To'g'ridan-to'g'ri abadiy
            ban_time = datetime.now() + timedelta(minutes=minutes)
            ban_type = "abadiy"
        
        # Bloklashni rejalashtirish
        if chat_id not in scheduled:
            scheduled[chat_id] = {}
            
        scheduled[chat_id][user.id] = {
            "username": user.username or f"ID:{user.id}",
            "time": ban_time,
            "user_id": user.id,
            "permanent": True  # Abadiy bloklash
        }
        
        # Vaqtni formatlash
        sana = ban_time.strftime("%d.%m.%Y %H:%M")
        
        display_name = f"@{user.username}" if user.username else f"{user.first_name}"
        
        await message.reply_text(
            f"✅ **BLOKLASH REJALASHTIRILDI**\n\n"
            f"📌 **Kanal:** {chat.title}\n"
            f"👤 **Foydalanuvchi:** {display_name}\n"
            f"🆔 **ID:** `{user.id}`\n"
            f"⏰ **Vaqt:** {time_str}\n"
            f"📅 **Sana:** {sana}\n"
            f"🚫 **Tur:** {ban_type}\n\n"
            f"⚠️ Vaqt kelganda ABADIY bloklanadi!"
        )
        
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

# ==================== A'ZOLAR RO'YXATI (ID BILAN) ====================
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
        admins = []
        owner = None
        
        async for member in client.get_chat_members(chat_id):
            user = member.user
            
            # Statusni aniqlash
            if member.status == enums.ChatMemberStatus.OWNER:
                owner = user
            elif member.status == enums.ChatMemberStatus.ADMINISTRATOR:
                admins.append(user)
            
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
        
        # Natijalarni ko'rsatish
        text = f"📋 **KANAL A'ZOLARI**\n📌 **{channel_title}**\n\n"
        
        if owner:
            name = f"{owner.first_name or ''} {owner.last_name or ''}".strip()
            text += f"👑 **EGASI:**\n"
            text += f"   • {name}\n"
            text += f"   • ID: `{owner.id}`\n"
            if owner.username:
                text += f"   • @{owner.username}\n"
            text += "\n"
        
        if admins:
            text += f"🔰 **ADMINLAR ({len(admins)}):**\n"
            for i, admin in enumerate(admins[:5]):
                name = f"{admin.first_name or ''} {admin.last_name or ''}".strip()
                text += f"  {i+1}. {name}\n"
                text += f"     ID: `{admin.id}`\n"
                if admin.username:
                    text += f"     @{admin.username}\n"
            if len(admins) > 5:
                text += f"  ... va yana {len(admins)-5} ta admin\n"
            text += "\n"
        
        text += f"**📱 USERNAME BORLAR ({len(members_with_username)}):**\n"
        for i, user in enumerate(members_with_username[:20]):
            name = f"{user['first_name']} {user['last_name']}".strip()
            text += f"{i+1}. @{user['username']}\n"
            text += f"   ID: `{user['id']}`\n"
            text += f"   {name}\n\n"
        
        if len(members_with_username) > 20:
            text += f"... va yana {len(members_with_username)-20} ta\n\n"
        
        text += f"**❌ USERNAME YO'QLAR ({len(members_without_username)}):**\n"
        for i, user in enumerate(members_without_username[:20]):
            name = f"{user['first_name']} {user['last_name']}".strip()
            text += f"{i+1}. {name}\n"
            text += f"   ID: `{user['id']}`\n\n"
        
        if len(members_without_username) > 20:
            text += f"... va yana {len(members_without_username)-20} ta\n\n"
        
        text += f"\n📊 **JAMI: {len(members_with_username) + len(members_without_username)} ta a'zo**\n"
        text += f"   • Username bor: {len(members_with_username)}\n"
        text += f"   • Username yo'q: {len(members_without_username)}\n"
        
        if members_without_username:
            text += f"\n💡 **Username yo'qni bloklash uchun:**\n"
            text += f"   /setbanid {members_without_username[0]['id']} 30k"
        
        await message.reply_text(text)
        
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

    try:
        chat = await client.get_chat(chat_id)
        channel_title = chat.title
    except:
        channel_title = "Kanal"

    text = f"📋 **REJALASHTIRILGAN BLOKLASHLAR**\n📌 **{channel_title}**\n\n"
    now = datetime.now()
    
    for data in scheduled[chat_id].values():
        toshkent_vaqt = data["time"] + timedelta(hours=5)
        sana = toshkent_vaqt.strftime("%d.%m.%Y %H:%M")
        
        qolgan = data["time"] - now
        if qolgan.total_seconds() > 0:
            if qolgan.days > 0:
                qolgan_text = f"(qoldi: {qolgan.days} kun)"
            else:
                qolgan_text = f"(qoldi: {qolgan.seconds//3600} soat)"
        else:
            qolgan_text = "(kutilmoqda)"
        
        display_name = f"@{data['username']}" if data['username'] and not str(data['username']).startswith('ID:') else data['username']
        text += f"• {display_name} - {sana} {qolgan_text}\n"
    
    text += f"\n📊 Jami: {len(scheduled[chat_id])} ta bloklash\n"
    text += f"⚠️ **Barchasi vaqt kelganda ABADIY bloklanadi!**"
    await message.reply_text(text)

# ==================== BEKOR QILISH ====================
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
                                print(f"⏰ Abadiy bloklash vaqti keldi: {data['username']}")
                                
                                # ABADIY BLOKLASH (366 kun = 527040 minut)
                                until_date = now + timedelta(days=366)
                                await app.ban_chat_member(chat_id, user_id, until_date=until_date)
                                
                                print(f"✅ ABADIY bloklandi: {data['username']}")
                                
                                # Kanalga xabar
                                try:
                                    await app.send_message(
                                        chat_id,
                                        f"🚫 **{data['username']} ABADIY bloklandi!**\n"
                                        f"📅 Vaqt: {now.strftime('%d.%m.%Y %H:%M')}"
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
print(f"👤 Egasi: @maestro_o")
print(f"📌 Kanal ID: {YOUR_CHANNEL_ID}")
print("=" * 60)
print("📋 QISQA KOMANDALAR:")
print("   • /setban @user 5m  - 5 minutdan keyin abadiy")
print("   • /setban @user 10k - 10 kundan keyin abadiy")
print("   • /setban @user 20k - 20 kundan keyin abadiy")
print("   • /setban @user 30k - 30 kundan keyin abadiy")
print("   • /setban @user 40k - 40 kundan keyin abadiy")
print("=" * 60)
print("📌 ID ORQALI: /setbanid 123456789 30k")
print("📌 A'ZOLAR: /members")
print("📌 RO'YXAT: /list")
print("=" * 60)

app.run()
