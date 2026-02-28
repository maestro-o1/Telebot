from datetime import datetime, timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import Message
import asyncio
import threading

# SOZLAMALAR
API_ID = 35058290
API_HASH = "d7cb549b10b8965c99673f8bd36c130a"
BOT_TOKEN = "8660286208:AAHssllobxtng0RDXfZ70fEkfFbjx13FyQE"

# ============= FAQAT SIZ UCHUN =============
# SIZNING TELEGRAM ID INGIZ
YOUR_ID = 1700341163  # @maestro_o
# ===========================================

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
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

# ==================== BOT KANALGA QO'SHILGANDA ====================
@app.on_message(filters.channel)
async def track_channels(client, message):
    """Bot kanalga qo'shilganda kanal ID sini saqlash"""
    chat = message.chat
    if chat.type in [enums.ChatType.CHANNEL]:
        bot_channels[chat.id] = {
            "title": chat.title,
            "username": chat.username,
            "id": chat.id,
            "last_seen": datetime.now()
        }
        print(f"✅ Kanal saqlandi: {chat.title} ({chat.id})")

# ==================== START KOMANDASI ====================
@app.on_message(filters.command("start"))
async def start_command(client, message):
    """Start komandasi"""
    user_id = message.from_user.id
    
    if is_owner(user_id):
        # Bot egasi uchun
        await message.reply_text(
            "✅ **XUSH KELIBSIZ, @maestro_o!**\n\n"
            "**📌 ASOSIY KOMANDALAR:**\n"
            "🔹 /myadminships - Kanallar ro'yxati\n"
            "🔹 /select [kanal_id] - Kanalni tanlash\n"
            "🔹 /members - A'zolar ro'yxati\n\n"
            "**📌 BLOKLASH KOMANDALARI:**\n"
            "🔹 /setban @user 10kun - Username orqali\n"
            "🔹 /setbanid [user_id] 10kun - ID orqali\n"
            "🔹 /list - Bloklashlar ro'yxati\n"
            "🔹 /cancelban @user/ID - Bekor qilish\n\n"
            "✅ Bot faqat siz uchun ishlaydi!"
        )
    else:
        # Begonalar uchun
        await message.reply_text(
            "👋 **VAQTLI BLOKLASH BOTI**\n\n"
            "❌ **Kechirasiz, bu bot shaxsiy foydalanish uchun.**\n"
            "Faqat @maestro_o ishlata oladi.\n\n"
            "Agar siz bot egasi bo'lsangiz, ID ni tekshiring."
        )

# ==================== KANALLAR RO'YXATI ====================
@app.on_message(filters.command("myadminships"))
async def my_adminships(client, message):
    """Bot admin bo'lgan kanallar ro'yxati"""
    user_id = message.from_user.id
    
    # Ruxsat tekshirish
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q! Bu bot faqat @maestro_o uchun.")
        return
    
    await message.reply_text("⏳ Kanallar tekshirilmoqda...")
    
    active_channels = []
    
    for chat_id, data in list(bot_channels.items()):
        try:
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
            "❌ Hech qanday faol kanal topilmadi!\n\n"
            "💡 Botni kanalga admin qiling va kanalda botga xabar yozing."
        )
        return
    
    text = "📋 **BOT ADMIN BO'LGAN KANALLAR:**\n\n"
    for i, channel in enumerate(active_channels, 1):
        text += f"**{i}. {channel['title']}**\n"
        text += f"🆔 ID: `{channel['id']}`\n"
        text += f"📱 Username: @{channel['username'] if channel['username'] else 'yo\'q'}\n"
        text += f"👥 A'zolar: {channel['members']}\n"
        text += f"🔗 /select {channel['id']} - Tanlash\n\n"
    
    text += f"\n📊 Jami: {len(active_channels)} ta faol kanal"
    await message.reply_text(text)

# ==================== KANALNI TANLASH ====================
@app.on_message(filters.command("select"))
async def select_channel(client, message):
    """Ishlash uchun kanalni tanlash"""
    user_id = message.from_user.id
    
    # Ruxsat tekshirish
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    args = message.text.split()
    
    if len(args) < 2:
        await message.reply_text("❌ Kanal ID sini yozing!\nMisol: /select -100123456789")
        return
    
    try:
        chat_id = int(args[1]) if args[1].lstrip('-').isdigit() else args[1]
        chat = await client.get_chat(chat_id)
        
        bot_member = await client.get_chat_member(chat.id, "me")
        if bot_member.status not in ["administrator", "creator"]:
            await message.reply_text("❌ Bu kanalda bot admin emas!")
            return
        
        selected_channel[user_id] = {
            "chat_id": chat.id,
            "title": chat.title
        }
        
        members_count = chat.members_count if hasattr(chat, 'members_count') else "noma'lum"
        
        await message.reply_text(
            f"✅ **KANAL TANLANDI**\n\n"
            f"📌 **Kanal:** {chat.title}\n"
            f"🆔 **ID:** `{chat.id}`\n"
            f"👥 **A'zolar:** {members_count}\n\n"
            f"📋 Endi /members va /setbanid ishlatishingiz mumkin"
        )
        
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

# ==================== KANAL A'ZOLARI ====================
@app.on_message(filters.command("members"))
async def get_members(client, message):
    """Tanlangan kanal a'zolarini ko'rsatish"""
    user_id = message.from_user.id
    
    # Ruxsat tekshirish
    if not is_owner(user_id):
        await message.reply_text("❌ Sizga ruxsat yo'q!")
        return
    
    if user_id not in selected_channel:
        await message.reply_text("❌ Avval kanal tanlang!\n/select [kanal_id]")
        return
    
    chat_id = selected_channel[user_id]["chat_id"]
    channel_title = selected_channel[user_id]["title"]
    
    try:
        bot_member = await client.get_chat_member(chat_id, "me")
        if bot_member.status not in ["administrator", "creator"]:
            await message.reply_text("❌ Bu kanalda bot admin emas!")
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
        
        async for member in client.get_chat_members(chat_id):
            user = member.user
            
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
        
        if members_without_username:
            text += f"\n💡 Username yo'qni bloklash:\n/setbanid {members_without_username[0]['id']} 10kun"
        
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

    try:
        chat_member = await client.get_chat_member(message.chat.id, "me")
        if chat_member.status not in ["administrator", "creator"]:
            await message.reply_text("❌ Bot kanalda ADMIN EMAS!")
            return
    except:
        await message.reply_text("❌ Bot kanalda admin emas!")
        return

    args = message.text.split()
    if len(args) < 3:
        await message.reply_text("❌ /setban @user 10kun")
        return

    username = args[1].replace("@", "")
    time_str = args[2]

    try:
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

        await message.reply_text(
            f"✅ **@{username}** {time_str} dan keyin bloklanadi\n\n"
            f"📅 **Sana:** {sana}"
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
        await message.reply_text("❌ /setbanid [user_id] [vaqt]")
        return
    
    try:
        target_user_id = int(args[1])
        time_str = args[2]
        
        if len(args) < 4 and not chat_id:
            await message.reply_text("❌ Kanal ID sini ham yozing!\nMisol: /setbanid 123456789 10kun -100123456789")
            return
        elif len(args) >= 4:
            chat_id = int(args[3])
        
        try:
            chat = await client.get_chat(chat_id)
            bot_member = await client.get_chat_member(chat_id, "me")
            if bot_member.status not in ["administrator", "creator"]:
                await message.reply_text("❌ Bu kanalda bot admin emas!")
                return
        except:
            await message.reply_text("❌ Kanal topilmadi!")
            return
        
        try:
            user = await client.get_users(target_user_id)
        except:
            await message.reply_text(f"❌ ID {target_user_id} topilmadi!")
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
        
        await message.reply_text(
            f"✅ **BLOKLASH REJALASHTIRILDI**\n\n"
            f"📌 **Kanal:** {chat.title}\n"
            f"👤 **User:** {user.first_name}\n"
            f"🆔 **ID:** `{user.id}`\n"
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
    
    chat_id = message.chat.id
    
    if user_id in selected_channel:
        chat_id = selected_channel[user_id]["chat_id"]
    
    if chat_id not in scheduled or not scheduled[chat_id]:
        await message.reply_text(f"📭 Bloklashlar yo'q")
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
    
    chat_id = message.chat.id
    if len(args) >= 3:
        chat_id = int(args[2])
    elif user_id in selected_channel:
        chat_id = selected_channel[user_id]["chat_id"]
    
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
            await message.reply_text(f"❌ {identifier} rejalashtirilmagan")
            
    except:
        await message.reply_text(f"❌ {identifier} topilmadi!")

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

# Threadda ishga tushirish
thread = threading.Thread(target=check_bans_background, daemon=True)
thread.start()

print("=" * 50)
print("✅ BOT ISHGA TUSHDI!")
print("=" * 50)
print(f"🤖 Bot: @uzdramadubbot")
print(f"👤 Egasi: @maestro_o (ID: {YOUR_ID})")
print(f"⏰ Vaqt: {(datetime.now() + timedelta(hours=5)).strftime('%H:%M %d.%m.%Y')}")
print("=" * 50)
print("✅ Bot FAQAT siz uchun ishlaydi!")
print("=" * 50)

app.run()
