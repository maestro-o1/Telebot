from datetime import datetime, timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import asyncio
import threading

# SOZLAMALAR
API_ID = 35058290
API_HASH = "d7cb549b10b8965c99673f8bd36c130a"
BOT_TOKEN = "8660286208:AAHssllobxtng0RDXfZ70fEkfFbjx13FyQE"

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
scheduled = {}

# Foydalanuvchi tanlagan kanalni saqlash
selected_channel = {}

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

# ==================== START KOMANDASI ====================
@app.on_message(filters.command("start"))
async def start_command(client, message):
    await message.reply_text(
        "✅ **VAQTLI BLOKLASH BOTI**\n\n"
        "**📌 ASOSIY KOMANDALAR:**\n"
        "🔹 /myadminships - Bot admin bo'lgan kanallar ro'yxati\n"
        "🔹 /select [kanal_id] - Kanalni tanlash\n"
        "🔹 /members - Tanlangan kanal a'zolari ro'yxati\n"
        "🔹 /members [qidiruv] - A'zolarni qidirish\n\n"
        "**📌 BLOKLASH KOMANDALARI:**\n"
        "🔹 /setban @user 10kun - Username orqali bloklash\n"
        "🔹 /setbanid [user_id] 10kun - ID orqali bloklash\n"
        "🔹 /list - Bloklashlar ro'yxati\n"
        "🔹 /cancelban @user/ID - Bekor qilish\n\n"
        "**📌 YANGI FUNKSIYA:**\n"
        "✅ Bot admin bo'lgan kanallarni ko'rish va tanlash\n"
        "✅ Tanlangan kanalda username yo'qlarni ID bilan bloklash\n"
        "✅ A'zolarni username bor/yo'q qilib ko'rsatish"
    )

# ==================== YANGI: BOT ADMIN BO'LGAN KANALLAR ====================
@app.on_message(filters.command("myadminships"))
async def my_adminships(client, message):
    """Bot admin bo'lgan kanallar ro'yxati"""
    try:
        await message.reply_text("⏳ Kanallar tekshirilmoqda...")
        
        channels_text = "📋 **BOT ADMIN BO'LGAN KANALLAR:**\n\n"
        count = 0
        
        # Bot a'zo bo'lgan chatlarni olish
        async for dialog in client.get_dialogs():
            chat = dialog.chat
            
            # Faqat kanallarni olish
            if chat.type in [enums.ChatType.CHANNEL]:
                try:
                    # Botning adminlik statusini tekshirish
                    bot_member = await client.get_chat_member(chat.id, "me")
                    
                    if bot_member.status in ["administrator", "creator"]:
                        count += 1
                        title = chat.title or "Nomsiz kanal"
                        username = f"@{chat.username}" if chat.username else "username yo'q"
                        
                        channels_text += f"**{count}. {title}**\n"
                        channels_text += f"🆔 ID: `{chat.id}`\n"
                        channels_text += f"📱 Username: {username}\n"
                        channels_text += f"👥 A'zolar: {await get_member_count(client, chat.id)}\n"
                        channels_text += f"🔗 /select {chat.id} - Tanlash\n\n"
                        
                except:
                    continue
        
        if count == 0:
            await message.reply_text("❌ Bot hech qanday kanalda admin emas!")
        else:
            channels_text += f"\n📊 Jami: {count} ta kanal"
            channels_text += "\n\n💡 Kanalni tanlash uchun: /select [kanal_id]"
            await message.reply_text(channels_text)
            
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

async def get_member_count(client, chat_id):
    """Kanal a'zolari sonini olish"""
    try:
        chat = await client.get_chat(chat_id)
        return chat.members_count
    except:
        return "noma'lum"

# ==================== YANGI: KANALNI TANLASH ====================
@app.on_message(filters.command("select"))
async def select_channel(client, message):
    """Ishlash uchun kanalni tanlash"""
    args = message.text.split()
    
    if len(args) < 2:
        await message.reply_text(
            "❌ Kanal ID sini yozing!\n\n"
            "Misol: /select -100123456789\n"
            "Kanallar ro'yxati: /myadminships"
        )
        return
    
    try:
        chat_id = int(args[1]) if args[1].lstrip('-').isdigit() else args[1]
        
        # Kanalni tekshirish
        chat = await client.get_chat(chat_id)
        
        # Bot adminligini tekshirish
        bot_member = await client.get_chat_member(chat.id, "me")
        if bot_member.status not in ["administrator", "creator"]:
            await message.reply_text("❌ Bu kanalda bot admin emas!")
            return
        
        # Tanlangan kanalni saqlash
        user_id = message.from_user.id
        selected_channel[user_id] = {
            "chat_id": chat.id,
            "title": chat.title
        }
        
        # A'zolar sonini olish
        members_count = await get_member_count(client, chat.id)
        
        await message.reply_text(
            f"✅ **KANAL TANLANDI**\n\n"
            f"📌 **Kanal:** {chat.title}\n"
            f"🆔 **ID:** `{chat.id}`\n"
            f"👥 **A'zolar:** {members_count}\n\n"
            f"📋 **Endi quyidagilarni qilishingiz mumkin:**\n"
            f"🔹 /members - A'zolar ro'yxati\n"
            f"🔹 /members [qidiruv] - Qidirish\n"
            f"🔹 /setbanid [user_id] 10kun - ID orqali bloklash\n"
            f"🔹 /list - Bloklashlar ro'yxati"
        )
        
    except ValueError:
        await message.reply_text("❌ Noto'g'ri ID formati!")
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

# ==================== YANGI: KANAL A'ZOLARI (TAKMILASHTIRILGAN) ====================
@app.on_message(filters.command("members"))
async def get_members(client, message):
    """Tanlangan kanal a'zolarini ko'rsatish"""
    user_id = message.from_user.id
    
    # Tanlangan kanalni tekshirish
    if user_id not in selected_channel:
        await message.reply_text(
            "❌ Avval kanal tanlang!\n"
            "🔹 /myadminships - Kanallar ro'yxati\n"
            "🔹 /select [kanal_id] - Kanalni tanlash"
        )
        return
    
    chat_id = selected_channel[user_id]["chat_id"]
    channel_title = selected_channel[user_id]["title"]
    
    # Adminlikni tekshirish
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
    
    # Qidiruv so'zini olish
    args = message.text.split()
    query = args[1] if len(args) > 1 else ""
    
    await message.reply_text(f"⏳ Kanal a'zolari yuklanmoqda...\nKanal: {channel_title}")
    
    try:
        members_with_username = []
        members_without_username = []
        
        # Barcha a'zolarni olish
        async for member in client.get_chat_members(chat_id):
            user = member.user
            
            # Agar qidiruv so'zi bo'lsa, filtrlaymiz
            if query:
                query_lower = query.lower()
                name = f"{user.first_name or ''} {user.last_name or ''}".lower()
                username = (user.username or "").lower()
                
                if query_lower not in name and query_lower not in username and query_lower not in str(user.id):
                    continue
            
            # Foydalanuvchi ma'lumotlarini yig'ish
            user_info = {
                "id": user.id,
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
                "username": user.username,
                "status": member.status
            }
            
            if user.username:
                members_with_username.append(user_info)
            else:
                members_without_username.append(user_info)
        
        # Natijalarni ko'rsatish
        text = f"📋 **KANAL A'ZOLARI**\n"
        text += f"📌 **{channel_title}**\n"
        text += f"{'─'*30}\n\n"
        
        # Username borlar
        text += f"**📱 USERNAME BORLAR ({len(members_with_username)}):**\n"
        for i, user in enumerate(members_with_username[:20]):  # 20 tasini ko'rsatish
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
        text += f"\n💡 Username yo'q foydalanuvchini bloklash:\n"
        text += f"🔹 /setbanid [ID] 10kun\n"
        text += f"Masalan: /setbanid {members_without_username[0]['id'] if members_without_username else '123456789'} 10kun"
        
        await message.reply_text(text)
        
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

# ==================== TAKMILASHTIRILGAN: ID ORQALI BLOKLASH ====================
@app.on_message(filters.command("setbanid"))
async def set_ban_by_id(client, message):
    """User ID orqali bloklashni rejalashtirish"""
    user_id = message.from_user.id
    chat_id = None
    
    # Tanlangan kanal borligini tekshirish
    if user_id in selected_channel:
        chat_id = selected_channel[user_id]["chat_id"]
    
    args = message.text.split()
    if len(args) < 3:
        await message.reply_text(
            "❌ /setbanid [user_id] [vaqt]\n"
            "Misol: /setbanid 123456789 10kun\n\n"
            "💡 Agar kanal tanlagan bo'lsangiz, o'sha kanalda bloklanadi\n"
            "Kanalsiz ishlatish: /setbanid [user_id] [vaqt] [kanal_id]"
        )
        return
    
    try:
        target_user_id = int(args[1])
        time_str = args[2]
        
        # Agar kanal ID berilmagan bo'lsa va tanlangan kanal bo'lmasa
        if len(args) < 4 and not chat_id:
            await message.reply_text("❌ Kanal ID sini ham yozing!\nMisol: /setbanid 123456789 10kun -100123456789")
            return
        elif len(args) >= 4:
            chat_id = int(args[3])
        
        # Kanalni tekshirish
        try:
            chat = await client.get_chat(chat_id)
            
            # Bot adminligini tekshirish
            bot_member = await client.get_chat_member(chat_id, "me")
            if bot_member.status not in ["administrator", "creator"]:
                await message.reply_text("❌ Bu kanalda bot admin emas!")
                return
        except:
            await message.reply_text("❌ Kanal topilmadi yoki bot a'zo emas!")
            return
        
        # Foydalanuvchini tekshirish
        try:
            user = await client.get_users(target_user_id)
        except:
            await message.reply_text(f"❌ ID {target_user_id} bo'lgan foydalanuvchi topilmadi!")
            return
        
        # Vaqtni hisoblash
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
        
        # Toshkent vaqtida ko'rsatish
        toshkent_vaqt = toshkent_vaqti(ban_time)
        sana = toshkent_vaqt.strftime("%d.%m.%Y %H:%M")
        
        user_name = user.first_name or ""
        user_display = f"@{user.username}" if user.username else f"{user_name} (ID:{user.id})"
        
        await message.reply_text(
            f"✅ **BLOKLASH REJALASHTIRILDI**\n\n"
            f"📌 **Kanal:** {chat.title}\n"
            f"👤 **Foydalanuvchi:** {user_display}\n"
            f"🆔 **User ID:** `{user.id}`\n"
            f"⏰ **Vaqt:** {time_str}\n"
            f"📅 **Sana:** {sana}\n"
            f"⏳ **Minut:** {int(minutes)} minut\n"
            f"🎯 **Holat:** Rejalashtirildi"
        )
        
    except ValueError:
        await message.reply_text("❌ User ID va Kanal ID raqam bo'lishi kerak!")
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

# ==================== TAKMILASHTIRILGAN: BLOKLASHLAR RO'YXATI ====================
@app.on_message(filters.command("list"))
async def list_bans(client, message):
    chat_id = message.chat.id
    
    # Tanlangan kanal borligini tekshirish
    if message.from_user.id in selected_channel:
        chat_id = selected_channel[message.from_user.id]["chat_id"]
    
    if chat_id not in scheduled or not scheduled[chat_id]:
        await message.reply_text(f"📭 {chat_id} kanalida bloklashlar yo'q")
        return

    text = f"📋 **REJALASHTIRILGAN BLOKLASHLAR**\n"
    text += f"📌 **Kanal ID:** `{chat_id}`\n"
    text += f"{'─'*30}\n\n"
    now = datetime.now()
    
    for user_id, data in list(scheduled[chat_id].items()):
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

# ==================== ESKI FUNKSIYALAR (setban, cancelban) ====================
@app.on_message(filters.command("setban"))
async def set_ban(client, message):
    """Username orqali bloklashni rejalashtirish"""
    # Adminlikni tekshirish
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
            f"📅 **Sana:** {sana}\n"
            f"🆔 **User ID:** `{user.id}`\n"
            f"⏰ **Vaqt:** {time_str}\n"
            f"⏳ **Minut:** {int(minutes)} minut\n"
            f"🎯 **Holat:** Rejalashtirildi"
        )

    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

@app.on_message(filters.command("cancelban"))
async def cancel_ban(client, message):
    args = message.text.split()
    if len(args) < 2:
        await message.reply_text("❌ /cancelban @user yoki /cancelban [user_id] [kanal_id]")
        return

    identifier = args[1].replace("@", "")
    
    # Kanal ID ni aniqlash
    chat_id = message.chat.id
    if len(args) >= 3:
        chat_id = int(args[2])
    elif message.from_user.id in selected_channel:
        chat_id = selected_channel[message.from_user.id]["chat_id"]
    
    try:
        # Username yoki ID ekanligini aniqlash
        try:
            if identifier.isdigit():
                user_id = int(identifier)
                user = await client.get_users(user_id)
            else:
                user = await client.get_users(identifier)
        except:
            await message.reply_text(f"❌ {identifier} topilmadi!")
            return
        
        if chat_id in scheduled and user.id in scheduled[chat_id]:
            data = scheduled[chat_id][user.id]
            toshkent_vaqt = toshkent_vaqti(data["time"])
            sana = toshkent_vaqt.strftime("%d.%m.%Y %H:%M")
            
            del scheduled[chat_id][user.id]
            
            display_name = f"@{data['username']}" if data['username'] and not str(data['username']).startswith('ID:') else data['username']
            await message.reply_text(
                f"✅ **{display_name}** uchun bloklash bekor qilindi\n"
                f"📅 Rejalashtirilgan vaqt: {sana}\n"
                f"📌 Kanal ID: `{chat_id}`"
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
                                print(f"⏰ Bloklash vaqti keldi: {username} (Kanal: {chat_id})")
                                
                                # Bloklash
                                await app.ban_chat_member(chat_id, user_id)
                                
                                print(f"✅ Bloklandi: {username}")
                                
                                # Kanalga xabar
                                try:
                                    toshkent_vaqt = toshkent_vaqti(now)
                                    sana = toshkent_vaqt.strftime("%d.%m.%Y %H:%M")
                                    display_name = f"@{username}" if username and not str(username).startswith('ID:') else username
                                    await app.send_message(
                                        chat_id,
                                        f"🚫 **{display_name}** bloklandi\n📅 Vaqt: {sana}"
                                    )
                                except:
                                    pass
                                    
                                del scheduled[chat_id][user_id]
                                
                            except Exception as e:
                                print(f"❌ Bloklash xatosi: {e}")
                                try:
                                    await app.send_message(
                                        chat_id,
                                        f"❌ {username} bloklashda xatolik: {str(e)}"
                                    )
                                except:
                                    pass
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
print(f"⏰ Toshkent vaqti: {(datetime.now() + timedelta(hours=5)).strftime('%H:%M %d.%m.%Y')}")
print("=" * 50)
print("📌 YANGI FUNKSIYALAR:")
print("   • /myadminships - Bot admin bo'lgan kanallar")
print("   • /select [ID] - Kanalni tanlash")
print("   • /members - A'zolar (username bor/yo'q)")
print("   • /setbanid ID 10kun - ID orqali bloklash")
print("=" * 50)

app.run()
