from datetime import datetime, timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import Message
import asyncio
import threading

# SOZLAMALAR
API_ID = 35058290
API_HASH = "d7cb549b10b8965c99673f8bd36c130a"
BOT_TOKEN = "8660286208:AAHssllobxtng0RDXfZ70fEkfFbjx13FyQE"

# ============= SIZNING ID INGIZ =============
YOUR_ID = 1700341163  # @maestro_o
# ===========================================

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Ma'lumotlar ombori
scheduled = {}
selected_channel = {}
bot_channels = {}
user_last_action = {}

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

# ==================== KANAL XABARLARINI USHLASH ====================
@app.on_message(filters.channel)
async def track_channels(client, message):
    """Bot kanalga xabar kelganda kanal ID sini saqlash"""
    chat = message.chat
    if chat.type in [enums.ChatType.CHANNEL]:
        bot_channels[chat.id] = {
            "title": chat.title,
            "username": chat.username,
            "id": chat.id,
            "last_seen": datetime.now()
        }
        print(f"✅ Kanal saqlandi: {chat.title} ({chat.id})")
        
        # Kanalga javob qaytarish
        try:
            await message.reply_text(
                f"✅ **KANAL QABUL QILINDI!**\n\n"
                f"📌 **{chat.title}**\n"
                f"🆔 ID: `{chat.id}`\n\n"
                f"Endi botda /myadminships yozib ko'ring!"
            )
        except Exception as e:
            print(f"Javob qaytarishda xatolik: {e}")

# ==================== START KOMANDASI ====================
@app.on_message(filters.command("start"))
async def start_command(client, message):
    """Start komandasi"""
    user_id = message.from_user.id
    
    if is_owner(user_id):
        await message.reply_text(
            "✅ **VAQTLI BLOKLASH BOTI**\n\n"
            "👤 **Xush kelibsiz, @maestro_o!**\n\n"
            "**📌 ASOSIY KOMANDALAR:**\n"
            "🔹 /myadminships - Kanallar ro'yxati\n"
            "🔹 /select [kanal_id] - Kanalni tanlash\n"
            "🔹 /members - A'zolar ro'yxati\n"
            "🔹 /members [qidiruv] - Qidirish\n\n"
            "**📌 BLOKLASH KOMANDALARI:**\n"
            "🔹 /setban @user 10kun - Username orqali\n"
            "🔹 /setbanid [user_id] 10kun - ID orqali\n"
            "🔹 /list - Bloklashlar ro'yxati\n"
            "🔹 /cancelban @user/ID - Bekor qilish\n\n"
            "**📌 YORDAM:**\n"
            "🔹 /help - To'liq yordam\n"
            "🔹 /myid - ID ingizni ko'rish"
        )
    else:
        await message.reply_text(
            "👋 **VAQTLI BLOKLASH BOTI**\n\n"
            "❌ **Kechirasiz, bu bot shaxsiy foydalanish uchun.**\n"
            "Faqat @maestro_o ishlata oladi.\n\n"
            "Agar siz bot egasi bo'lsangiz, ID ingizni tekshiring."
        )

# ==================== YORDAM KOMANDASI ====================
@app.on_message(filters.command("help"))
async def help_command(client, message):
    if not is_owner(message.from_user.id):
        return
    
    await message.reply_text(
        "📚 **TO'LIQ QO'LLANMA**\n\n"
        "**1. KANAL QO'SHISH:**\n"
        "• Botni kanalga admin qiling\n"
        "• Kanalda @uzdramadubbot salom deb yozing\n"
        "• /myadminships - Kanallar ro'yxati\n\n"
        "**2. KANAL TANLASH:**\n"
        "• /select -100123456789 - ID orqali tanlash\n"
        "• yoki /myadminships dan tanlang\n\n"
        "**3. A'ZOLARNI KO'RISH:**\n"
        "• /members - Barcha a'zolar\n"
        "• /members Alisher - Qidirish\n\n"
        "**4. BLOKLASH:**\n"
        "• /setban @user 30kun - Username orqali\n"
        "• /setbanid 123456789 30kun - ID orqali\n\n"
        "**5. BOSHQA:**\n"
        "• /list - Bloklashlar ro'yxati\n"
        "• /cancelban @user - Bekor qilish\n"
        "• /myid - ID ingizni ko'rish"
    )

# ==================== ID NI KO'RSATISH ====================
@app.on_message(filters.command("myid"))
async def my_id(client, message):
    await message.reply_text(f"🆔 Sizning Telegram ID ingiz: `{message.from_user.id}`")

# ==================== KANALLAR RO'YXATI ====================
@app.on_message(filters.command("myadminships"))
async def my_adminships(client, message):
    """Bot admin bo'lgan kanallar ro'yxati"""
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    await message.reply_text("⏳ Kanallar tekshirilmoqda...")
    
    active_channels = []
    
    for chat_id, data in list(bot_channels.items()):
        try:
            # Bot adminligini tekshirish
            bot_member = await client.get_chat_member(chat_id, "me")
            if bot_member.status in ["administrator", "creator"]:
                try:
                    chat = await client.get_chat(chat_id)
                    active_channels.append({
                        "id": chat_id,
                        "title": chat.title or data['title'],
                        "username": chat.username,
                        "members": chat.members_count if hasattr(chat, 'members_count') else "noma'lum"
                    })
                except:
                    continue
        except:
            continue
    
    if not active_channels:
        await message.reply_text(
            "❌ **Hech qanday faol kanal topilmadi!**\n\n"
            "📌 **QO'LLANMA:**\n"
            "1. Botni kanalga admin qiling\n"
            "2. Kanalda @uzdramadubbot salom deb yozing\n"
            "3. Bu xabarni yozganingizda bot javob qaytaradi\n"
            "4. So'ng /myadminships ni qayta bosing\n\n"
            "💡 Agar kanal ID sini bilsangiz:\n"
            "/select -100123456789 - To'g'ridan-to'g'ri tanlang"
        )
        return
    
    text = "📋 **BOT ADMIN BO'LGAN KANALLAR:**\n\n"
    for i, channel in enumerate(active_channels, 1):
        username = f"@{channel['username']}" if channel['username'] else "yo'q"
        text += f"**{i}. {channel['title']}**\n"
        text += f"🆔 ID: `{channel['id']}`\n"
        text += f"👥 A'zolar: {channel['members']}\n"
        text += f"🔗 /select {channel['id']} - Tanlash\n\n"
    
    text += f"\n📊 Jami: {len(active_channels)} ta kanal"
    await message.reply_text(text)

# ==================== KANALNI TANLASH ====================
@app.on_message(filters.command("select"))
async def select_channel(client, message):
    """Ishlash uchun kanalni tanlash"""
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    args = message.text.split()
    
    if len(args) < 2:
        await message.reply_text(
            "❌ **Kanal ID sini yozing!**\n\n"
            "Misol: /select -100123456789\n\n"
            "📌 Kanal ID sini topish:\n"
            "• Kanalda @uzdramadubbot salom deb yozing\n"
            "• Bot javobida ID ko'rinadi\n"
            "• Yoki @getidsbot dan foydalaning"
        )
        return
    
    try:
        chat_id = int(args[1]) if args[1].lstrip('-').isdigit() else args[1]
        
        # Kanalni tekshirish
        try:
            chat = await client.get_chat(chat_id)
        except:
            await message.reply_text(f"❌ Kanal topilmadi! ID: {args[1]} noto'g'ri.")
            return
        
        # Bot adminligini tekshirish
        try:
            bot_member = await client.get_chat_member(chat_id, "me")
            if bot_member.status not in ["administrator", "creator"]:
                await message.reply_text(
                    f"❌ **Bu kanalda bot admin emas!**\n\n"
                    f"Kanal: {chat.title}\n\n"
                    f"Botni kanalga admin qilib, qayta urinib ko'ring."
                )
                return
        except Exception as e:
            await message.reply_text(f"❌ Bot adminligini tekshirishda xatolik: {str(e)}")
            return
        
        # Tanlangan kanalni saqlash
        selected_channel[user_id] = {
            "chat_id": chat.id,
            "title": chat.title
        }
        
        # Kanalni bot_channels ga qo'shish (agar yo'q bo'lsa)
        if chat.id not in bot_channels:
            bot_channels[chat.id] = {
                "title": chat.title,
                "username": chat.username,
                "id": chat.id,
                "last_seen": datetime.now()
            }
        
        members_count = chat.members_count if hasattr(chat, 'members_count') else "noma'lum"
        
        await message.reply_text(
            f"✅ **KANAL TANLANDI**\n\n"
            f"📌 **Nomi:** {chat.title}\n"
            f"🆔 **ID:** `{chat.id}`\n"
            f"👥 **A'zolar:** {members_count}\n\n"
            f"📋 **Endi quyidagilarni qilishingiz mumkin:**\n"
            f"🔹 /members - A'zolar ro'yxati\n"
            f"🔹 /members Alisher - Qidirish\n"
            f"🔹 /setbanid [user_id] 30kun - Bloklash\n"
            f"🔹 /list - Bloklashlar ro'yxati"
        )
        
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

# ==================== KANAL A'ZOLARI ====================
@app.on_message(filters.command("members"))
async def get_members(client, message):
    """Tanlangan kanal a'zolarini ko'rsatish"""
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    if user_id not in selected_channel:
        await message.reply_text(
            "❌ **Avval kanal tanlang!**\n\n"
            "🔹 /myadminships - Kanallar ro'yxati\n"
            "🔹 /select [kanal_id] - Kanalni tanlash"
        )
        return
    
    chat_id = selected_channel[user_id]["chat_id"]
    channel_title = selected_channel[user_id]["title"]
    
    # Adminlikni qayta tekshirish
    try:
        bot_member = await client.get_chat_member(chat_id, "me")
        if bot_member.status not in ["administrator", "creator"]:
            await message.reply_text("❌ Bu kanalda bot admin emas! Qayta kanal tanlang.")
            del selected_channel[user_id]
            return
    except:
        await message.reply_text("❌ Kanalga kirish imkoni yo'q!")
        del selected_channel[user_id]
        return
    
    args = message.text.split()
    query = args[1] if len(args) > 1 else ""
    
    await message.reply_text(f"⏳ A'zolar yuklanmoqda...\nKanal: {channel_title}")
    
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
            
            # Qidiruv filtri
            if query:
                query_lower = query.lower()
                name = f"{user.first_name or ''} {user.last_name or ''}".lower()
                username = (user.username or "").lower()
                
                if query_lower not in name and query_lower not in username and query_lower not in str(user.id):
                    continue
            
            user_info = {
                "id": user.id,
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
                "username": user.username,
                "is_bot": user.is_bot
            }
            
            if user.username:
                members_with_username.append(user_info)
            else:
                members_without_username.append(user_info)
        
        # Natijalarni ko'rsatish
        text = f"📋 **KANAL A'ZOLARI**\n📌 **{channel_title}**\n\n"
        
        if owner:
            name = f"{owner.first_name or ''} {owner.last_name or ''}".strip()
            text += f"👑 **EGASI:** @{owner.username if owner.username else name} (ID: `{owner.id}`)\n\n"
        
        if admins:
            text += f"🔰 **ADMINLAR ({len(admins)}):**\n"
            for i, admin in enumerate(admins[:5]):
                name = f"{admin.first_name or ''} {admin.last_name or ''}".strip()
                text += f"  {i+1}. @{admin.username if admin.username else name}\n"
            if len(admins) > 5:
                text += f"  ... va yana {len(admins)-5} ta\n"
            text += "\n"
        
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
        
        if members_without_username:
            text += f"\n💡 **Username yo'qni bloklash:**\n"
            text += f"/setbanid {members_without_username[0]['id']} 30kun"
        
        await message.reply_text(text)
        
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

# ==================== USERNAME ORQALI BLOKLASH ====================
@app.on_message(filters.command("setban"))
async def set_ban(client, message):
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return

    args = message.text.split()
    if len(args) < 3:
        await message.reply_text("❌ /setban @user 10kun")
        return

    username = args[1].replace("@", "")
    time_str = args[2]

    try:
        # Adminlikni tekshirish
        try:
            chat_member = await client.get_chat_member(message.chat.id, "me")
            if chat_member.status not in ["administrator", "creator"]:
                await message.reply_text("❌ Bot kanalda ADMIN EMAS!")
                return
        except:
            await message.reply_text("❌ Bot kanalda admin emas!")
            return

        user = await client.get_users(username)
        minutes = parse_time(time_str)
        
        if minutes <= 0:
            await message.reply_text("❌ Noto'g'ri vaqt formati!")
            return
            
        ban_time = datetime.now() + timedelta(minutes=minutes)

        if message.chat.id not in scheduled:
            scheduled[message.chat.id] = {}
            
        scheduled[message.chat.id][user.id] = {
            "username": username,
            "time": ban_time,
            "user_id": user.id
        }

        toshkent_vaqt = toshkent_vaqti(ban_time)
        sana = toshkent_vaqt.strftime("%d.%m.%Y %H:%M")
        
        qolgan = ban_time - datetime.now()
        qolgan_text = f"{qolgan.days} kun, {qolgan.seconds//3600} soat" if qolgan.days > 0 else f"{qolgan.seconds//3600} soat, {(qolgan.seconds//60)%60} minut"

        await message.reply_text(
            f"✅ **BLOKLASH REJALASHTIRILDI**\n\n"
            f"👤 **Foydalanuvchi:** @{username}\n"
            f"🆔 **ID:** `{user.id}`\n"
            f"⏰ **Vaqt:** {time_str}\n"
            f"📅 **Sana:** {sana}\n"
            f"⏳ **Qoldi:** {qolgan_text}"
        )

    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

# ==================== ID ORQALI BLOKLASH ====================
@app.on_message(filters.command("setbanid"))
async def set_ban_by_id(client, message):
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    chat_id = None
    
    if user_id in selected_channel:
        chat_id = selected_channel[user_id]["chat_id"]
    
    args = message.text.split()
    if len(args) < 3:
        await message.reply_text("❌ /setbanid [user_id] [vaqt]\nMisol: /setbanid 123456789 30kun")
        return
    
    try:
        target_user_id = int(args[1])
        time_str = args[2]
        
        # Kanal ID ni aniqlash
        if len(args) >= 4:
            chat_id = int(args[3])
        
        if not chat_id:
            await message.reply_text("❌ Kanal ID sini ham yozing yoki avval kanal tanlang!")
            return
        
        # Kanalni tekshirish
        try:
            chat = await client.get_chat(chat_id)
            
            # Bot adminligini tekshirish
            bot_member = await client.get_chat_member(chat_id, "me")
            if bot_member.status not in ["administrator", "creator"]:
                await message.reply_text("❌ Bu kanalda bot admin emas!")
                return
        except Exception as e:
            await message.reply_text(f"❌ Kanal topilmadi! {str(e)}")
            return
        
        # Foydalanuvchini tekshirish
        try:
            user = await client.get_users(target_user_id)
        except:
            await message.reply_text(f"❌ ID {target_user_id} bo'lgan foydalanuvchi topilmadi!")
            return
        
        minutes = parse_time(time_str)
        
        if minutes <= 0:
            await message.reply_text("❌ Noto'g'ri vaqt formati!")
            return
            
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
        
        user_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        display_name = f"@{user.username}" if user.username else user_name
        
        qolgan = ban_time - datetime.now()
        qolgan_text = f"{qolgan.days} kun, {qolgan.seconds//3600} soat" if qolgan.days > 0 else f"{qolgan.seconds//3600} soat, {(qolgan.seconds//60)%60} minut"
        
        await message.reply_text(
            f"✅ **BLOKLASH REJALASHTIRILDI**\n\n"
            f"📌 **Kanal:** {chat.title}\n"
            f"👤 **Foydalanuvchi:** {display_name}\n"
            f"🆔 **User ID:** `{user.id}`\n"
            f"⏰ **Vaqt:** {time_str}\n"
            f"📅 **Sana:** {sana}\n"
            f"⏳ **Qoldi:** {qolgan_text}"
        )
        
    except ValueError:
        await message.reply_text("❌ User ID raqam bo'lishi kerak!")
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

# ==================== BLOKLASHLAR RO'YXATI ====================
@app.on_message(filters.command("list"))
async def list_bans(client, message):
    user_id = message.from_user.id
    
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    # Qaysi kanalni ko'rsatish kerak?
    chat_id = message.chat.id
    if user_id in selected_channel:
        chat_id = selected_channel[user_id]["chat_id"]
    
    if chat_id not in scheduled or not scheduled[chat_id]:
        await message.reply_text(f"📭 Bu kanalda bloklashlar yo'q")
        return

    try:
        chat = await client.get_chat(chat_id)
        channel_title = chat.title
    except:
        channel_title = "Noma'lum kanal"

    text = f"📋 **REJALASHTIRILGAN BLOKLASHLAR**\n📌 **{channel_title}**\n\n"
    now = datetime.now()
    
    for data in scheduled[chat_id].values():
        toshkent_vaqt = toshkent_vaqti(data["time"])
        sana = toshkent_vaqt.strftime("%d.%m.%Y %H:%M")
        
        qolgan = data["time"] - now
        if qolgan.total_seconds() > 0:
            soat = qolgan.seconds // 3600
            minut = (qolgan.seconds % 3600) // 60
            if qolgan.days > 0:
                qolgan_text = f"(qoldi: {qolgan.days} kun {soat} soat)"
            elif soat > 0:
                qolgan_text = f"(qoldi: {soat} soat {minut} minut)"
            else:
                qolgan_text = f"(qoldi: {minut} minut)"
        else:
            qolgan_text = "(kutilmoqda)"
        
        display_name = f"@{data['username']}" if data['username'] and not str(data['username']).startswith('ID:') else data['username']
        text += f"• {display_name} - {sana} {qolgan_text}\n"
    
    text += f"\n📊 Jami: {len(scheduled[chat_id])} ta bloklash"
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
    
    # Kanal ID ni aniqlash
    chat_id = message.chat.id
    if len(args) >= 3:
        chat_id = int(args[2])
    elif user_id in selected_channel:
        chat_id = selected_channel[user_id]["chat_id"]
    
    try:
        # Username yoki ID ekanligini aniqlash
        if identifier.isdigit():
            user_id_target = int(identifier)
            user = await client.get_users(user_id_target)
        else:
            user = await client.get_users(identifier)
        
        if chat_id in scheduled and user.id in scheduled[chat_id]:
            data = scheduled[chat_id][user.id]
            toshkent_vaqt = toshkent_vaqti(data["time"])
            sana = toshkent_vaqt.strftime("%d.%m.%Y %H:%M")
            
            del scheduled[chat_id][user.id]
            
            display_name = f"@{data['username']}" if data['username'] and not str(data['username']).startswith('ID:') else data['username']
            
            await message.reply_text(
                f"✅ **BLOKLASH BEKOR QILINDI**\n\n"
                f"👤 **Foydalanuvchi:** {display_name}\n"
                f"📅 Rejalashtirilgan vaqt: {sana}"
            )
        else:
            await message.reply_text(f"❌ {identifier} rejalashtirilmagan")
            
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

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
                                username = data['username']
                                print(f"⏰ Bloklash vaqti keldi: {username}")
                                
                                await app.ban_chat_member(chat_id, user_id)
                                print(f"✅ Bloklandi: {username}")
                                
                                del scheduled[chat_id][user_id]
                                
                            except Exception as e:
                                print(f"❌ Bloklash xatosi: {e}")
            except Exception as e:
                print(f"Tekshirish xatosi: {e}")
            await asyncio.sleep(60)
    
    loop.run_until_complete(check())

# ==================== KANAL XABARLARINI LOGGA YOZISH ====================
@app.on_message()
async def log_all_messages(client, message):
    """Barcha xabarlarni logga yozish (faqat egasi uchun)"""
    user_id = message.from_user.id if message.from_user else None
    
    # Faqat egasining xabarlarini logga yozish
    if user_id == YOUR_ID:
        chat_type = message.chat.type
        chat_title = getattr(message.chat, 'title', 'No title')
        chat_id = message.chat.id
        text = message.text or "No text"
        
        print(f"\n📨 XABAR KELDI")
        print(f"   Tur: {chat_type}")
        print(f"   Nomi: {chat_title}")
        print(f"   ID: {chat_id}")
        print(f"   Matn: {text[:50]}...")

# Threadda ishga tushirish
thread = threading.Thread(target=check_bans_background, daemon=True)
thread.start()

print("=" * 60)
print("✅ BOT ISHGA TUSHDI!")
print("=" * 60)
print(f"🤖 Bot: @uzdramadubbot")
print(f"👤 Egasi: @maestro_o (ID: {YOUR_ID})")
print(f"⏰ Toshkent vaqti: {(datetime.now() + timedelta(hours=5)).strftime('%H:%M %d.%m.%Y')}")
print("=" * 60)
print("📌 KANAL QO'SHISH UCHUN:")
print("   1. Botni kanalga admin qiling")
print("   2. Kanalda @uzdramadubbot salom deb yozing")
print("   3. /myadminships ni bosing")
print("=" * 60)

app.run()
