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
            return 30
            
        number = int(number)
        
        if 'kun' in time_str:
            return number * 24 * 60
        elif 'oy' in time_str:
            return number * 30 * 24 * 60
        elif 'soat' in time_str:
            return number * 60
        elif 'minut' in time_str:
            return number
        else:
            return number
    except:
        return 30

def toshkent_vaqti(vaqt):
    """Server vaqtini Toshkent vaqtiga o'tkazish (+5 soat)"""
    return vaqt + timedelta(hours=5)

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
            "✅ **VAQTLI BLOKLASH BOTI**\n\n"
            "👤 **Xush kelibsiz, @maestro_o!**\n\n"
            "**📌 SIZNING KANALINGIZ:**\n"
            f"🆔 ID: `{YOUR_CHANNEL_ID}`\n"
            f"🔹 /select - Kanalni tanlash\n\n"
            "**📌 BOSHQA KOMANDALAR:**\n"
            "🔹 /members - A'zolar ro'yxati\n"
            "🔹 /setbanid [user_id] 30kun - Bloklash\n"
            "🔹 /list - Bloklashlar ro'yxati\n"
            "🔹 /cancelban @user/ID - Bekor qilish"
        )
    else:
        await message.reply_text("❌ Sizga ruxsat yo'q!")

# ==================== KANALNI TANLASH (TO'G'RILANGAN) ====================
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
        # Kanal ma'lumotlarini olish
        chat = await client.get_chat(chat_id)
        
        # MUHIM: Cache'ni tozalash uchun bir necha marta tekshirish
        is_admin = False
        admin_status = None
        
        # 1-usul: get_chat_member bilan tekshirish (3 marta)
        for i in range(3):
            try:
                bot_member = await client.get_chat_member(chat_id, "me")
                print(f"Tekshirish {i+1}: {bot_member.status}")
                if bot_member.status in ["administrator", "creator"]:
                    is_admin = True
                    admin_status = bot_member.status
                    break
                await asyncio.sleep(2)  # 2 soniya kutish
            except Exception as e:
                print(f"Xatolik {i+1}: {e}")
        
        # 2-usul: Agar topilmasa, adminlar ro'yxatidan qidirish
        if not is_admin:
            async for member in client.get_chat_members(chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
                if member.user.is_self:
                    is_admin = True
                    admin_status = member.status
                    print(f"Adminlar ro'yxatidan topildi: {member.status}")
                    break
        
        if not is_admin:
            # Adminlar ro'yxatini ko'rsatish
            admins_text = "👥 **KANAL ADMINLARI:**\n"
            admin_count = 0
            
            async for member in client.get_chat_members(chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
                admin_count += 1
                user = member.user
                status_text = "✅" if user.is_self else "•"
                name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                admins_text += f"{status_text} @{user.username if user.username else 'no username'} - {member.status}\n"
            
            await message.reply_text(
                f"❌ **BOT ADMIN EMAS!**\n\n"
                f"Kanal: {chat.title}\n"
                f"ID: `{chat_id}`\n\n"
                f"{admins_text}\n\n"
                f"📌 **YECHIM:**\n"
                f"1. Bot adminlar ro'yxatida bormi? Yuqoriga qarang\n"
                f"2. Agar 'ChatMemberStatus.ADMINISTRATOR' deb yozilgan bo'lsa,\n"
                f"   bu xato - Telegram cache muammosi\n"
                f"3. 1-2 daqiqa kuting va /select ni qayta bosing"
            )
            return
        
        # Agar shu yerga kelsa, bot admin ekan
        selected_channel[user_id] = {
            "chat_id": chat.id,
            "title": chat.title
        }
        
        # Kanalni bot_channels ga qo'shish
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
            f"👥 **A'zolar:** {members_count}\n"
            f"🤖 **Bot status:** {admin_status}\n\n"
            f"📋 **Endi quyidagilarni qilishingiz mumkin:**\n"
            f"🔹 /members - A'zolar ro'yxati\n"
            f"🔹 /setbanid [user_id] 30kun - Bloklash\n"
            f"🔹 /list - Bloklashlar ro'yxati"
        )
        
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

# ==================== A'ZOLAR RO'YXATI ====================
@app.on_message(filters.command("members"))
async def get_members(client, message):
    """Kanal a'zolarini ko'rsatish"""
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
            text += f"{i+1}. @{user['username']} - {name[:30]}\n"
        
        if len(members_with_username) > 20:
            text += f"... va yana {len(members_with_username)-20} ta\n"
        
        text += f"\n**❌ USERNAME YO'QLAR ({len(members_without_username)}):**\n"
        for i, user in enumerate(members_without_username[:20]):
            name = f"{user['first_name']} {user['last_name']}".strip()
            text += f"{i+1}. ID: `{user['id']}` - {name[:30]}\n"
        
        if len(members_without_username) > 20:
            text += f"... va yana {len(members_without_username)-20} ta\n"
        
        text += f"\n📊 **JAMI: {len(members_with_username) + len(members_without_username)} ta a'zo**\n"
        
        await message.reply_text(text)
        
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

# ==================== ID ORQALI BLOKLASH ====================
@app.on_message(filters.command("setbanid"))
async def set_ban_by_id(client, message):
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    args = message.text.split()
    if len(args) < 3:
        await message.reply_text("❌ /setbanid [user_id] [vaqt]\nMisol: /setbanid 123456789 30kun")
        return
    
    try:
        target_user_id = int(args[1])
        time_str = args[2]
        
        # Kanal ID ni aniqlash
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
        
        minutes = parse_time(time_str)
        ban_time = datetime.now() + timedelta(minutes=minutes)
        
        if chat_id not in scheduled:
            scheduled[chat_id] = {}
            
        scheduled[chat_id][user.id] = {
            "username": user.username or f"ID:{user.id}",
            "time": ban_time,
            "user_id": user.id,
            "chat_title": chat.title
        }
        
        toshkent_vaqt = toshkent_vaqti(ban_time)
        sana = toshkent_vaqt.strftime("%d.%m.%Y %H:%M")
        
        display_name = f"@{user.username}" if user.username else f"{user.first_name}"
        
        await message.reply_text(
            f"✅ **BLOKLASH REJALASHTIRILDI**\n\n"
            f"📌 **Kanal:** {chat.title}\n"
            f"👤 **Foydalanuvchi:** {display_name}\n"
            f"🆔 **ID:** `{user.id}`\n"
            f"⏰ **Vaqt:** {time_str}\n"
            f"📅 **Sana:** {sana}"
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

    try:
        chat = await client.get_chat(chat_id)
        channel_title = chat.title
    except:
        channel_title = "Kanal"

    text = f"📋 **BLOKLASHLAR**\n📌 **{channel_title}**\n\n"
    now = datetime.now()
    
    for data in scheduled[chat_id].values():
        toshkent_vaqt = toshkent_vaqti(data["time"])
        sana = toshkent_vaqt.strftime("%d.%m.%Y %H:%M")
        
        qolgan = data["time"] - now
        if qolgan.days > 0:
            qolgan_text = f"(qoldi: {qolgan.days} kun)"
        else:
            qolgan_text = f"(qoldi: {qolgan.seconds//3600} soat)"
        
        display_name = f"@{data['username']}" if data['username'] and not str(data['username']).startswith('ID:') else data['username']
        text += f"• {display_name} - {sana} {qolgan_text}\n"
    
    text += f"\n📊 Jami: {len(scheduled[chat_id])} ta"
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

# ==================== VAQTLI BLOKLASH ====================
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
                                await app.ban_chat_member(chat_id, user_id)
                                print(f"✅ Bloklandi: {data['username']}")
                                del scheduled[chat_id][user_id]
                            except Exception as e:
                                print(f"Xato: {e}")
            except:
                pass
            await asyncio.sleep(60)
    
    loop.run_until_complete(check())

# Threadda ishga tushirish
thread = threading.Thread(target=check_bans_background, daemon=True)
thread.start()

print("=" * 50)
print("✅ BOT ISHGA TUSHDI!")
print("=" * 50)
print(f"🤖 Bot: @uzdramadubbot")
print(f"👤 Egasi: @maestro_o")
print(f"📌 Kanal ID: {YOUR_CHANNEL_ID}")
print("=" * 50)
print("📋 KOMANDALAR:")
print("   /select - Kanalni tanlash")
print("   /members - A'zolar ro'yxati")
print("   /setbanid ID 30kun - Bloklash")
print("   /list - Bloklashlar")
print("=" * 50)

app.run()
