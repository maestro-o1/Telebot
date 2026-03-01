from datetime import datetime, timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import json
import os

# ==================== 1. SOZLAMALAR ====================
API_ID = 35058290
API_HASH = "d7cb549b10b8965c99673f8bd36c130a"
BOT_TOKEN = "8660286208:AAHssllobxtng0RDXfZ70fEkfFbjx13FyQE"
YOUR_ID = 1700341163  # @maestro_o

app = Client("kanal_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ==================== 2. MA'LUMOTLAR OMBORI ====================
scheduled = {}  # Rejalashtirilgan bloklashlar
user_history = {}  # Foydalanuvchilar tarixi
bot_channel = None  # Bot ulangan kanal ID si
setup_done = False  # Sozlanganligi

# ==================== 3. MA'LUMOTLARNI SAQLASH ====================
DATA_FILE = "bot_data.json"

def save_data():
    try:
        data = {
            "scheduled": {},
            "user_history": {},
            "bot_channel": bot_channel,
            "last_save": datetime.now().isoformat()
        }
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except:
        pass

def load_data():
    global bot_channel
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
            bot_channel = data.get("bot_channel", None)
    except:
        pass

load_data()

# ==================== 4. VAQT FUNKSIYALARI ====================
def parse_time(time_str):
    """5m, 30k, 1oy -> minut"""
    try:
        time_str = time_str.lower().strip()
        number = ''.join(filter(str.isdigit, time_str))
        if not number:
            return 366 * 24 * 60
        number = int(number)
        
        if 'k' in time_str or 'kun' in time_str:
            return number * 24 * 60
        elif 'm' in time_str or 'minut' in time_str:
            return number
        elif 'oy' in time_str:
            return number * 30 * 24 * 60
        elif 'soat' in time_str:
            return number * 60
        else:
            return number * 24 * 60
    except:
        return 366 * 24 * 60

def toshkent_vaqti(vaqt):
    return vaqt + timedelta(hours=5)

def is_owner(user_id):
    return user_id == YOUR_ID

# ==================== 5. ADMINLIKNI TEKSHIRISH ====================
async def check_admin(client, chat_id):
    try:
        me = await client.get_me()
        member = await client.get_chat_member(chat_id, me.id)
        return member.status in ["administrator", "creator"]
    except:
        return False

# ==================== 6. ASOSIY MENYU ====================
def get_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 A'ZOLAR", callback_data="menu_members")],
        [InlineKeyboardButton("🚫 BLOKLASH", callback_data="menu_ban")],
        [InlineKeyboardButton("📊 BLOKLASHLAR", callback_data="menu_list")],
        [InlineKeyboardButton("❌ BEKOR QILISH", callback_data="menu_cancel")],
        [InlineKeyboardButton("📜 TARIX", callback_data="menu_history")]
    ])

# ==================== 7. START KOMANDASI ====================
@app.on_message(filters.command("start"))
async def start_command(client, message):
    global setup_done
    
    if message.from_user.id != YOUR_ID:
        await message.reply_text("❌ Ruxsat yo'q!")
        return
    
    if bot_channel:
        is_admin = await check_admin(client, bot_channel)
        if is_admin:
            setup_done = True
            await message.reply_text(
                f"✅ **ASOSIY MENYU**\n\n"
                f"📌 Kanal ID: `{bot_channel}`",
                reply_markup=get_main_menu()
            )
        else:
            await message.reply_text(
                f"❌ **Bot kanalda admin emas!**\n\n"
                f"1. Botni kanalga admin qiling\n"
                f"2. 'Foydalanuvchilarni bloklash' huquqini bering\n"
                f"3. Qayta /start bosing"
            )
    else:
        await message.reply_text(
            "👋 **XUSH KELIBSIZ!**\n\n"
            "Bot ishlashi uchun **kanal ID** sini yuboring.\n\n"
            "Misol: `-1003726881716`"
        )

# ==================== 8. KANAL ID NI QABUL QILISH ====================
@app.on_message(filters.text & filters.private)
async def handle_channel_id(client, message):
    global bot_channel, setup_done
    
    if message.from_user.id != YOUR_ID:
        return
    
    try:
        chat_id = int(message.text.strip())
        msg = await message.reply_text("⏳ Tekshirilmoqda...")
        
        is_admin = await check_admin(client, chat_id)
        
        if is_admin:
            bot_channel = chat_id
            setup_done = True
            save_data()
            
            chat = await client.get_chat(chat_id)
            
            await msg.edit_text(
                f"✅ **KANAL MUVOFFAQIYATLI ULANDI!**\n\n"
                f"📌 **Kanal:** {chat.title}\n"
                f"🆔 **ID:** `{chat_id}`\n\n"
                f"Endi /start yozib menyuni oching."
            )
        else:
            await msg.edit_text(
                f"❌ **Bot kanalda admin emas!**\n\n"
                f"ID: `{chat_id}`\n\n"
                f"1. Botni kanalga admin qiling\n"
                f"2. 'Foydalanuvchilarni bloklash' huquqini bering\n"
                f"3. Qayta urinib ko'ring"
            )
    except ValueError:
        await message.reply_text(
            "❌ **Noto'g'ri format!**\n\n"
            "Kanal ID raqam bo'lishi kerak.\n"
            "Misol: `-1003726881716`"
        )
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

# ==================== 9. TUGMALARGA JAVOB ====================
@app.on_callback_query()
async def handle_callbacks(client, callback_query):
    data = callback_query.data
    user_id = callback_query.from_user.id
    
    if user_id != YOUR_ID:
        await callback_query.answer("Ruxsat yo'q!")
        return
    
    if data == "main_menu":
        await callback_query.message.edit_text(
            f"✅ **ASOSIY MENYU**\n\n📌 Kanal ID: `{bot_channel}`",
            reply_markup=get_main_menu()
        )
    
    elif data == "menu_members":
        await callback_query.message.edit_text(
            "👥 **A'ZOLAR**\n\n"
            "`/members` - barcha a'zolarni ko'rish",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ ORQAGA", callback_data="main_menu")]
            ])
        )
    
    elif data == "menu_ban":
        ban_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("5m", callback_data="ban_5m"),
             InlineKeyboardButton("10m", callback_data="ban_10m")],
            [InlineKeyboardButton("30m", callback_data="ban_30m"),
             InlineKeyboardButton("1k", callback_data="ban_1k")],
            [InlineKeyboardButton("5k", callback_data="ban_5k"),
             InlineKeyboardButton("10k", callback_data="ban_10k")],
            [InlineKeyboardButton("20k", callback_data="ban_20k"),
             InlineKeyboardButton("30k", callback_data="ban_30k")],
            [InlineKeyboardButton("40k", callback_data="ban_40k"),
             InlineKeyboardButton("1oy", callback_data="ban_1oy")],
            [InlineKeyboardButton("◀️ ORQAGA", callback_data="main_menu")]
        ])
        await callback_query.message.edit_text(
            "🚫 **BLOKLASH VAQTI TANLANG**",
            reply_markup=ban_keyboard
        )
    
    elif data.startswith("ban_"):
        time_str = data.replace("ban_", "")
        await callback_query.message.edit_text(
            f"✅ **{time_str} TANLANDI**\n\n"
            f"Endi bloklamoqchi bo'lgan foydalanuvchi nomini yozing:\n"
            f"`/setban @user {time_str}`\n\n"
            f"Yoki ID orqali:\n"
            f"`/setbanid 123456789 {time_str}`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ ORQAGA", callback_data="menu_ban")]
            ])
        )
    
    elif data == "menu_list":
        await callback_query.message.edit_text(
            "📊 **BLOKLASHLAR**\n\n"
            "`/list` - bloklashlar ro'yxatini ko'rish",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ ORQAGA", callback_data="main_menu")]
            ])
        )
    
    elif data == "menu_cancel":
        await callback_query.message.edit_text(
            "❌ **BEKOR QILISH**\n\n"
            "`/cancelban @user` - username orqali\n"
            "`/cancelban 123456789` - ID orqali",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ ORQAGA", callback_data="main_menu")]
            ])
        )
    
    elif data == "menu_history":
        await callback_query.message.edit_text(
            f"📜 **TARIX:** {len(user_history)} ta foydalanuvchi",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ ORQAGA", callback_data="main_menu")]
            ])
        )
    
    await callback_query.answer()

# ==================== 10. MEMBERS KOMANDASI ====================
@app.on_message(filters.command("members"))
async def members_cmd(client, message):
    if message.from_user.id != YOUR_ID:
        return
    
    if not bot_channel:
        await message.reply_text("❌ Avval kanal ulang! /start ni bosing.")
        return
    
    msg = await message.reply_text("👥 A'zolar yuklanmoqda...")
    
    try:
        members_with_username = []
        members_without_username = []
        
        async for member in client.get_chat_members(bot_channel):
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
        
        chat = await client.get_chat(bot_channel)
        
        text = f"📋 **KANAL A'ZOLARI**\n"
        text += f"📌 **{chat.title}**\n"
        text += f"🆔 `{bot_channel}`\n"
        text += f"{'─'*40}\n\n"
        
        text += f"**📱 USERNAME BORLAR ({len(members_with_username)}):**\n"
        for i, user in enumerate(members_with_username[:10]):
            name = f"{user['first_name']} {user['last_name']}".strip()
            text += f"{i+1}. @{user['username']} - ID: `{user['id']}`\n"
        
        if len(members_with_username) > 10:
            text += f"... va yana {len(members_with_username)-10} ta\n\n"
        
        text += f"**❌ USERNAME YO'QLAR ({len(members_without_username)}):**\n"
        for i, user in enumerate(members_without_username[:10]):
            name = f"{user['first_name']} {user['last_name']}".strip()
            text += f"{i+1}. {name} - ID: `{user['id']}`\n"
        
        if len(members_without_username) > 10:
            text += f"... va yana {len(members_without_username)-10} ta\n\n"
        
        text += f"\n📊 **JAMI: {len(members_with_username) + len(members_without_username)} ta a'zo**"
        
        await msg.edit_text(text)
        
    except Exception as e:
        await msg.edit_text(f"❌ Xatolik: {str(e)}")

# ==================== 11. BLOKLASH KOMANDALARI ====================
@app.on_message(filters.command("setban"))
async def setban_cmd(client, message):
    if message.from_user.id != YOUR_ID:
        return
    
    if not bot_channel:
        await message.reply_text("❌ Avval kanal ulang!")
        return
    
    args = message.text.split()
    if len(args) < 3:
        await message.reply_text("❌ /setban @user 30k")
        return
    
    username = args[1].replace("@", "")
    time_str = args[2]
    
    try:
        user = await client.get_users(username)
        minutes = parse_time(time_str)
        ban_time = datetime.now() + timedelta(minutes=minutes)
        
        if bot_channel not in scheduled:
            scheduled[bot_channel] = {}
        
        scheduled[bot_channel][user.id] = {
            "username": username,
            "full_name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
            "time": ban_time,
            "user_id": user.id
        }
        save_data()
        
        sana = toshkent_vaqti(ban_time).strftime("%d.%m.%Y %H:%M")
        await message.reply_text(f"✅ @{username} {time_str} dan keyin bloklanadi\n📅 {sana}")
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

@app.on_message(filters.command("setbanid"))
async def setbanid_cmd(client, message):
    if message.from_user.id != YOUR_ID:
        return
    
    if not bot_channel:
        await message.reply_text("❌ Avval kanal ulang!")
        return
    
    args = message.text.split()
    if len(args) < 3:
        await message.reply_text("❌ /setbanid 123456789 30k")
        return
    
    try:
        user_id = int(args[1])
        time_str = args[2]
        user = await client.get_users(user_id)
        minutes = parse_time(time_str)
        ban_time = datetime.now() + timedelta(minutes=minutes)
        
        if bot_channel not in scheduled:
            scheduled[bot_channel] = {}
        
        scheduled[bot_channel][user.id] = {
            "username": user.username or f"ID:{user.id}",
            "full_name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
            "time": ban_time,
            "user_id": user.id
        }
        save_data()
        
        sana = toshkent_vaqti(ban_time).strftime("%d.%m.%Y %H:%M")
        await message.reply_text(f"✅ ID:{user_id} {time_str} dan keyin bloklanadi\n📅 {sana}")
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

@app.on_message(filters.command("list"))
async def list_cmd(client, message):
    if message.from_user.id != YOUR_ID:
        return
    
    if not bot_channel:
        await message.reply_text("❌ Kanal ulanmagan!")
        return
    
    if bot_channel not in scheduled or not scheduled[bot_channel]:
        await message.reply_text("📭 Bloklashlar yo'q")
        return
    
    text = "📊 **BLOKLASHLAR:**\n\n"
    for data in scheduled[bot_channel].values():
        sana = toshkent_vaqti(data["time"]).strftime("%d.%m %H:%M")
        text += f"• {data['full_name']} - {sana}\n"
    await message.reply_text(text)

@app.on_message(filters.command("cancelban"))
async def cancel_cmd(client, message):
    if message.from_user.id != YOUR_ID:
        return
    
    if not bot_channel:
        await message.reply_text("❌ Kanal ulanmagan!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.reply_text("❌ /cancelban @user")
        return
    
    identifier = args[1].replace("@", "")
    
    try:
        if identifier.isdigit():
            user_id = int(identifier)
            if bot_channel in scheduled and user_id in scheduled[bot_channel]:
                del scheduled[bot_channel][user_id]
                save_data()
                await message.reply_text("✅ Bloklash bekor qilindi")
        else:
            user = await client.get_users(identifier)
            if bot_channel in scheduled and user.id in scheduled[bot_channel]:
                del scheduled[bot_channel][user.id]
                save_data()
                await message.reply_text("✅ Bloklash bekor qilindi")
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

@app.on_message(filters.command("history"))
async def history_cmd(client, message):
    if message.from_user.id != YOUR_ID:
        return
    await message.reply_text(f"📜 Tarix: {len(user_history)} ta foydalanuvchi")

# ==================== 12. YANGI A'ZO QO'SHILGANDA ====================
@app.on_chat_member_updated()
async def on_chat_member_update(client, chat_member_updated):
    try:
        if not bot_channel:
            return
        if chat_member_updated.chat.id != bot_channel:
            return
        
        new_member = chat_member_updated.new_chat_member
        if not new_member:
            return
        
        user = new_member.user
        if user.is_bot:
            return
        
        user_id = user.id
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        
        user_history[user_id] = {
            "username": f"@{user.username}" if user.username else "no username",
            "full_name": full_name,
            "join_time": datetime.now(),
            "status": "active"
        }
        save_data()
        
        ban_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("5m", callback_data=f"quick_{user_id}_5m"),
             InlineKeyboardButton("30m", callback_data=f"quick_{user_id}_30m")],
            [InlineKeyboardButton("1k", callback_data=f"quick_{user_id}_1k"),
             InlineKeyboardButton("7k", callback_data=f"quick_{user_id}_7k")],
            [InlineKeyboardButton("30k", callback_data=f"quick_{user_id}_30k"),
             InlineKeyboardButton("❌ Skip", callback_data=f"quick_{user_id}_skip")]
        ])
        
        await client.send_message(
            YOUR_ID,
            f"👤 **YANGI A'ZO QO'SHILDI!**\n\n"
            f"🆔 ID: `{user_id}`\n"
            f"👤 Ism: {full_name}\n"
            f"⏰ {datetime.now().strftime('%H:%M %d.%m.%Y')}",
            reply_markup=ban_keyboard
        )
    except:
        pass

# ==================== 13. TEZKOR BLOKLASH ====================
@app.on_callback_query(filters.regex(r"^quick_"))
async def quick_ban_handler(client, callback_query):
    data = callback_query.data
    user_id = callback_query.from_user.id
    
    if user_id != YOUR_ID:
        await callback_query.answer("Ruxsat yo'q!")
        return
    
    parts = data.split('_')
    target_id = int(parts[1])
    action = parts[2]
    
    if action == "skip":
        await callback_query.message.edit_text(f"❌ Bekor qilindi\nID: `{target_id}`")
        await callback_query.answer()
        return
    
    minutes = parse_time(action)
    ban_time = datetime.now() + timedelta(minutes=minutes)
    
    if bot_channel not in scheduled:
        scheduled[bot_channel] = {}
    
    user_info = user_history.get(target_id, {})
    scheduled[bot_channel][target_id] = {
        "username": user_info.get("username", f"ID:{target_id}"),
        "full_name": user_info.get("full_name", "Noma'lum"),
        "time": ban_time,
        "user_id": target_id
    }
    save_data()
    
    sana = toshkent_vaqti(ban_time).strftime("%d.%m.%Y %H:%M")
    await callback_query.message.edit_text(
        f"✅ **BLOKLASH REJALASHTIRILDI!**\n\n"
        f"ID: `{target_id}`\n"
        f"⏰ {action}\n"
        f"📅 {sana}"
    )
    await callback_query.answer()

# ==================== 14. VAQTLI BLOKLASH TEKSHIRUVI ====================
async def check_bans():
    while True:
        try:
            now = datetime.now()
            for chat_id in list(scheduled.keys()):
                for user_id in list(scheduled[chat_id].keys()):
                    if now >= scheduled[chat_id][user_id]["time"]:
                        try:
                            await app.ban_chat_member(chat_id, user_id)
                            del scheduled[chat_id][user_id]
                            save_data()
                        except:
                            pass
        except:
            pass
        await asyncio.sleep(60)

# ==================== 15. BOTNI ISHGA TUSHIRISH ====================
import asyncio

async def main():
    print("=" * 50)
    print("✅ KANAL BOSHQARUV BOTI ISHGA TUSHDI!")
    print("=" * 50)
    print(f"🤖 Bot: @uzdramadubbot")
    print(f"👤 Egasi: @maestro_o")
    print(f"📌 ID: {YOUR_ID}")
    print("=" * 50)
    
    asyncio.create_task(check_bans())
    await app.run()

if __name__ == "__main__":
    asyncio.run(main())
