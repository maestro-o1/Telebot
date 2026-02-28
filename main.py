from datetime import datetime, timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import asyncio
import threading
import json
import os

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
        
        for chat_id, users in scheduled.items():
            data["scheduled"][str(chat_id)] = {}
            for user_id, user_data in users.items():
                data["scheduled"][str(chat_id)][str(user_id)] = {
                    "username": user_data.get("username", ""),
                    "full_name": user_data.get("full_name", ""),
                    "time": user_data["time"].isoformat(),
                    "user_id": user_data["user_id"],
                    "join_time": user_data.get("join_time", datetime.now()).isoformat(),
                    "permanent": user_data.get("permanent", False)
                }
        
        for user_id, hist_data in user_history.items():
            data["user_history"][str(user_id)] = {
                "username": hist_data.get("username", ""),
                "full_name": hist_data.get("full_name", ""),
                "join_time": hist_data["join_time"].isoformat(),
                "leave_time": hist_data.get("leave_time", "").isoformat() if hist_data.get("leave_time") else "",
                "status": hist_data.get("status", ""),
                "scheduled_ban": hist_data.get("scheduled_ban", "").isoformat() if hist_data.get("scheduled_ban") else "",
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
            
            print(f"✅ Ma'lumotlar yuklandi")
    except Exception as e:
        print(f"❌ Ma'lumotlarni yuklashda xatolik: {e}")

load_data()

# ==================== 60 KUNDAN KEYIN O'CHIRISH ====================
def clean_old_data():
    """60 kundan eski ma'lumotlarni o'chirish"""
    try:
        now = datetime.now()
        cutoff = now - timedelta(days=60)
        cleaned = 0
        
        for chat_id in list(scheduled.keys()):
            for user_id in list(scheduled[chat_id].keys()):
                ban_time = scheduled[chat_id][user_id]["time"]
                if ban_time < cutoff:
                    del scheduled[chat_id][user_id]
                    cleaned += 1
        
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
            print(f"🧹 {cleaned} ta eski ma'lumot o'chirildi")
            save_data()
    except Exception as e:
        print(f"❌ Tozalashda xatolik: {e}")

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

def toshkent_vaqti(vaqt):
    return vaqt + timedelta(hours=5)

def is_owner(user_id):
    return user_id == YOUR_ID

# ==================== BOT ADMINLIGINI TEKSHIRISH ====================
async def check_bot_admin(client, chat_id):
    me = await client.get_me()
    
    for i in range(3):
        try:
            member = await client.get_chat_member(chat_id, me.id)
            if member.status in ["administrator", "creator"]:
                return True, member.status
        except:
            pass
        await asyncio.sleep(2)
    
    try:
        async for member in client.get_chat_members(chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
            if member.user.id == me.id:
                return True, member.status
    except:
        pass
    
    return False, None

# ==================== ASOSIY MENYU TUGMALARI ====================
def get_main_menu():
    """Asosiy menyu tugmalarini qaytarish"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 KANAL TANLASH", callback_data="menu_select")],
        [InlineKeyboardButton("👥 A'ZOLAR", callback_data="menu_members")],
        [InlineKeyboardButton("🚫 BLOKLASH", callback_data="menu_ban")],
        [InlineKeyboardButton("📊 BLOKLASHLAR", callback_data="menu_list")],
        [InlineKeyboardButton("❌ BEKOR QILISH", callback_data="menu_cancel")],
        [InlineKeyboardButton("📜 TARIX", callback_data="menu_history")],
        [InlineKeyboardButton("🔄 QAYTA YUKLASH", callback_data="menu_reload")]
    ])

# ==================== START KOMANDASI (TUGMALAR BILAN) ====================
@app.on_message(filters.command("start"))
async def start_command(client, message):
    user_id = message.from_user.id
    
    if is_owner(user_id):
        await message.reply_text(
            f"✅ **ABADIY BLOKLASH BOTI**\n\n"
            f"👤 **Xush kelibsiz, @maestro_o!**\n\n"
            f"📌 **SIZNING KANALINGIZ:** `{YOUR_CHANNEL_ID}`\n\n"
            f"📊 **MA'LUMOTLAR:**\n"
            f"• Bloklashlar: {len(scheduled.get(YOUR_CHANNEL_ID, {}))} ta\n"
            f"• Tarix: {len(user_history)} ta foydalanuvchi\n\n"
            f"Quyidagi tugmalardan birini tanlang:",
            reply_markup=get_main_menu()
        )
    else:
        await message.reply_text("❌ Sizga ruxsat yo'q!")

# ==================== TUGMALARGA JAVOB ====================
@app.on_callback_query()
async def handle_callbacks(client, callback_query: CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id
    
    if user_id != YOUR_ID:
        await callback_query.answer("Bu tugmalar faqat bot egasi uchun!")
        return
    
    # ASOSIY MENYU
    if data == "back_to_menu":
        await callback_query.message.edit_text(
            f"✅ **ABADIY BLOKLASH BOTI**\n\n"
            f"👤 **Xush kelibsiz, @maestro_o!**\n\n"
            f"📌 **SIZNING KANALINGIZ:** `{YOUR_CHANNEL_ID}`\n\n"
            f"📊 **MA'LUMOTLAR:**\n"
            f"• Bloklashlar: {len(scheduled.get(YOUR_CHANNEL_ID, {}))} ta\n"
            f"• Tarix: {len(user_history)} ta foydalanuvchi\n\n"
            f"Quyidagi tugmalardan birini tanlang:",
            reply_markup=get_main_menu()
        )
        await callback_query.answer()
    
    # KANAL TANLASH
    elif data == "menu_select":
        is_admin, status = await check_bot_admin(client, YOUR_CHANNEL_ID)
        
        if is_admin:
            selected_channel[user_id] = {
                "chat_id": YOUR_CHANNEL_ID,
                "title": "Luli vip kanal"
            }
            await callback_query.message.edit_text(
                f"✅ **KANAL TANLANDI!**\n\n"
                f"📌 **Kanal:** Luli vip kanal\n"
                f"🆔 **ID:** `{YOUR_CHANNEL_ID}`\n"
                f"🤖 **Bot status:** {status}\n\n"
                f"Endi /members yozib a'zolarni ko'rishingiz mumkin!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👥 A'ZOLAR", callback_data="menu_members")],
                    [InlineKeyboardButton("◀️ ORQAGA", callback_data="back_to_menu")]
                ])
            )
        else:
            await callback_query.message.edit_text(
                f"❌ **Bot admin emas!**\n\n"
                f"📌 **YECHIM:**\n"
                f"1. Kanalda adminlar ro'yxatiga kiring\n"
                f"2. @uzdramadubbot ni admin qiling\n"
                f"3. 30 soniya kuting\n"
                f"4. Qayta urinib ko'ring",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 QAYTA TEKSHIRISH", callback_data="menu_select")],
                    [InlineKeyboardButton("◀️ ORQAGA", callback_data="back_to_menu")]
                ])
            )
        await callback_query.answer()
    
    # A'ZOLAR
    elif data == "menu_members":
        if user_id not in selected_channel:
            await callback_query.message.edit_text(
                f"❌ **Avval kanal tanlang!**\n\n"
                f"📌 Kanalni tanlash uchun tugmani bosing:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 KANAL TANLASH", callback_data="menu_select")],
                    [InlineKeyboardButton("◀️ ORQAGA", callback_data="back_to_menu")]
                ])
            )
        else:
            await callback_query.message.edit_text(
                f"👥 **A'ZOLAR RO'YXATI**\n\n"
                f"Kanal a'zolarini ko'rish uchun:\n"
                f"`/members`\n\n"
                f"Yoki qidirish uchun:\n"
                f"`/members Alisher`\n\n"
                f"Username yo'qlarni ID bilan bloklash:\n"
                f"`/setbanid 123456789 30k`",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 A'ZOLARNI YANGILASH", callback_data="refresh_members")],
                    [InlineKeyboardButton("◀️ ORQAGA", callback_data="back_to_menu")]
                ])
            )
        await callback_query.answer()
    
    # BLOKLASH MENYUSI
    elif data == "menu_ban":
        ban_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏱️ 5 minut", callback_data="ban_5m")],
            [InlineKeyboardButton("⏱️ 10 minut", callback_data="ban_10m")],
            [InlineKeyboardButton("⏱️ 30 minut", callback_data="ban_30m")],
            [InlineKeyboardButton("📅 1 kun", callback_data="ban_1k")],
            [InlineKeyboardButton("📅 5 kun", callback_data="ban_5k")],
            [InlineKeyboardButton("📅 10 kun", callback_data="ban_10k")],
            [InlineKeyboardButton("📅 20 kun", callback_data="ban_20k")],
            [InlineKeyboardButton("📅 30 kun", callback_data="ban_30k")],
            [InlineKeyboardButton("📅 40 kun", callback_data="ban_40k")],
            [InlineKeyboardButton("📆 1 oy", callback_data="ban_1oy")],
            [InlineKeyboardButton("📆 2 oy", callback_data="ban_2oy")],
            [InlineKeyboardButton("📆 3 oy", callback_data="ban_3oy")],
            [InlineKeyboardButton("◀️ ORQAGA", callback_data="back_to_menu")]
        ])
        
        await callback_query.message.edit_text(
            f"🚫 **BLOKLASH VAQTI TANLANG**\n\n"
            f"Qaysi vaqtni tanlaysiz?\n\n"
            f"Keyin foydalanuvchi nomini yozishingiz kerak:\n"
            f"`/setban @user 30k`\n\n"
            f"Yoki ID orqali:\n"
            f"`/setbanid 123456789 30k`",
            reply_markup=ban_keyboard
        )
        await callback_query.answer()
    
    # BLOKLASH VAQTI TANLANGANDA
    elif data.startswith("ban_"):
        time_str = data.replace("ban_", "")
        await callback_query.message.edit_text(
            f"✅ **{time_str} TANLANDI**\n\n"
            f"Endi bloklamoqchi bo'lgan foydalanuvchi nomini yozing:\n"
            f"`/setban @user {time_str}`\n\n"
            f"Yoki ID orqali:\n"
            f"`/setbanid 123456789 {time_str}`\n\n"
            f"Username yo'q foydalanuvchilar uchun ID ishlating.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ ORQAGA", callback_data="menu_ban")]
            ])
        )
        await callback_query.answer()
    
    # BLOKLASHLAR RO'YXATI
    elif data == "menu_list":
        if YOUR_CHANNEL_ID not in scheduled or not scheduled[YOUR_CHANNEL_ID]:
            text = "📭 Bloklashlar yo'q"
        else:
            text = f"📊 **BLOKLASHLAR RO'YXATI:**\n\n"
            now = datetime.now()
            for user_id, data in scheduled[YOUR_CHANNEL_ID].items():
                qolgan = data["time"] - now
                sana = toshkent_vaqti(data["time"]).strftime("%d.%m %H:%M")
                if qolgan.days > 0:
                    qolgan_text = f"(qoldi: {qolgan.days} kun)"
                else:
                    qolgan_text = f"(qoldi: {qolgan.seconds//3600} soat)"
                text += f"• {data['full_name']} - {sana} {qolgan_text}\n"
        
        await callback_query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 YANGILASH", callback_data="menu_list")],
                [InlineKeyboardButton("◀️ ORQAGA", callback_data="back_to_menu")]
            ])
        )
        await callback_query.answer()
    
    # BEKOR QILISH
    elif data == "menu_cancel":
        await callback_query.message.edit_text(
            f"❌ **BLOKLASHNI BEKOR QILISH**\n\n"
            f"Bloklashni bekor qilish uchun:\n"
            f"`/cancelban @user`\n"
            f"yoki\n"
            f"`/cancelban 123456789`\n\n"
            f"ID orqali bekor qilish username yo'qlar uchun qulay.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 BLOKLASHLAR", callback_data="menu_list")],
                [InlineKeyboardButton("◀️ ORQAGA", callback_data="back_to_menu")]
            ])
        )
        await callback_query.answer()
    
    # TARIX
    elif data == "menu_history":
        if not user_history:
            text = "📭 Hech qanday ma'lumot yo'q"
        else:
            text = "📜 **FOYDALANUVCHILAR TARIXI:**\n\n"
            for uid, data in list(user_history.items())[:10]:
                join_time = data["join_time"].strftime("%d.%m")
                status = "✅" if data.get("status") == "active" else "❌"
                text += f"{status} `{uid}` - {data['full_name'][:20]} - {join_time}\n"
        
        await callback_query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 YANGILASH", callback_data="menu_history")],
                [InlineKeyboardButton("◀️ ORQAGA", callback_data="back_to_menu")]
            ])
        )
        await callback_query.answer()
    
    # QAYTA YUKLASH
    elif data == "menu_reload":
        load_data()
        await callback_query.message.edit_text(
            f"✅ **MA'LUMOTLAR QAYTA YUKLANDI!**\n\n"
            f"📊 **YANGI MA'LUMOTLAR:**\n"
            f"• Bloklashlar: {len(scheduled.get(YOUR_CHANNEL_ID, {}))} ta\n"
            f"• Tarix: {len(user_history)} ta foydalanuvchi",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ ORQAGA", callback_data="back_to_menu")]
            ])
        )
        await callback_query.answer()
    
    # A'ZOLARNI YANGILASH
    elif data == "refresh_members":
        if user_id in selected_channel:
            await callback_query.message.edit_text(
                f"👥 A'zolar yuklanmoqda...\n"
                f"Kanal: {selected_channel[user_id]['title']}\n\n"
                f"`/members` komandasini ishlating.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ ORQAGA", callback_data="menu_members")]
                ])
            )
        await callback_query.answer()

# ==================== YANGI FOYDALANUVCHI QO'SHILGANDA ====================
@app.on_chat_member_updated()
async def on_chat_member_update(client, chat_member_updated):
    chat = chat_member_updated.chat
    new_member = chat_member_updated.new_chat_member
    old_member = chat_member_updated.old_chat_member
    
    if chat.type != enums.ChatType.CHANNEL or chat.id != YOUR_CHANNEL_ID:
        return
    
    if new_member and not old_member:
        user = new_member.user
        if user.is_bot:
            return
        
        join_time = datetime.now()
        user_id = user.id
        username = f"@{user.username}" if user.username else "username yo'q"
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        
        user_history[user_id] = {
            "username": username,
            "full_name": full_name,
            "join_time": join_time,
            "leave_time": None,
            "status": "active"
        }
        save_data()
        
        ban_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏱️ 5 minut", callback_data=f"quick_ban_{user_id}_5m")],
            [InlineKeyboardButton("⏱️ 30 minut", callback_data=f"quick_ban_{user_id}_30m")],
            [InlineKeyboardButton("📅 1 kun", callback_data=f"quick_ban_{user_id}_1k")],
            [InlineKeyboardButton("📅 7 kun", callback_data=f"quick_ban_{user_id}_7k")],
            [InlineKeyboardButton("📅 30 kun", callback_data=f"quick_ban_{user_id}_30k")],
            [InlineKeyboardButton("❌ Bekor qilish", callback_data=f"quick_skip_{user_id}")]
        ])
        
        await client.send_message(
            YOUR_ID,
            f"👤 **YANGI A'ZO QO'SHILDI!**\n\n"
            f"🆔 ID: `{user_id}`\n"
            f"📱 Username: {username}\n"
            f"👤 Ism: {full_name}\n"
            f"⏰ Vaqt: {join_time.strftime('%H:%M %d.%m.%Y')}\n\n"
            f"Bloklash vaqtini tanlang:",
            reply_markup=ban_keyboard
        )

# ==================== TEZKOR BLOKLASH ====================
@app.on_callback_query(filters.regex(r"^quick_(ban|skip)_"))
async def quick_ban_handler(client, callback_query):
    data = callback_query.data
    user_id = callback_query.from_user.id
    
    if user_id != YOUR_ID:
        await callback_query.answer("Ruxsat yo'q!")
        return
    
    parts = data.split('_')
    action = parts[1]
    target_id = int(parts[2])
    
    if action == "ban":
        time_str = parts[3]
        minutes = parse_time(time_str)
        ban_time = datetime.now() + timedelta(minutes=minutes)
        
        if YOUR_CHANNEL_ID not in scheduled:
            scheduled[YOUR_CHANNEL_ID] = {}
        
        user_info = user_history.get(target_id, {})
        scheduled[YOUR_CHANNEL_ID][target_id] = {
            "username": user_info.get("username", f"ID:{target_id}"),
            "full_name": user_info.get("full_name", "Noma'lum"),
            "time": ban_time,
            "user_id": target_id,
            "join_time": user_info.get("join_time", datetime.now()),
            "permanent": True
        }
        
        save_data()
        
        await callback_query.message.edit_text(
            f"✅ **BLOKLASH REJALASHTIRILDI!**\n\n"
            f"👤 {user_info.get('full_name', 'Noma\'lum')}\n"
            f"🆔 ID: `{target_id}`\n"
            f"⏰ Vaqt: {time_str}\n"
            f"📅 Sana: {toshkent_vaqti(ban_time).strftime('%d.%m.%Y %H:%M')}"
        )
    else:
        await callback_query.message.edit_text(
            f"❌ Bloklash bekor qilindi\n"
            f"🆔 ID: `{target_id}`"
        )
    
    await callback_query.answer()

# ==================== QOLGAN KOMANDALAR ====================
@app.on_message(filters.command("select"))
async def select_channel_cmd(client, message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        return await message.reply_text("❌ Ruxsat yo'q!")
    
    is_admin, status = await check_bot_admin(client, YOUR_CHANNEL_ID)
    if is_admin:
        selected_channel[user_id] = {"chat_id": YOUR_CHANNEL_ID, "title": "Luli vip kanal"}
        await message.reply_text(f"✅ Kanal tanlandi! Bot status: {status}")
    else:
        await message.reply_text("❌ Bot admin emas!")

@app.on_message(filters.command("members"))
async def members_cmd(client, message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        return await message.reply_text("❌ Ruxsat yo'q!")
    
    if user_id not in selected_channel:
        return await message.reply_text("❌ Avval /select ni bosing!")
    
    await message.reply_text("👥 /members komandasi ishlatildi\nA'zolar yuklanmoqda...")

@app.on_message(filters.command("setban"))
async def setban_cmd(client, message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        return await message.reply_text("❌ Ruxsat yo'q!")
    
    args = message.text.split()
    if len(args) < 3:
        return await message.reply_text("❌ /setban @user 30k")
    
    await message.reply_text(f"✅ Bloklash rejalashtirildi: {args[1]} {args[2]}")

@app.on_message(filters.command("list"))
async def list_cmd(client, message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        return await message.reply_text("❌ Ruxsat yo'q!")
    
    if YOUR_CHANNEL_ID not in scheduled or not scheduled[YOUR_CHANNEL_ID]:
        return await message.reply_text("📭 Bloklashlar yo'q")
    
    text = "📋 **BLOKLASHLAR:**\n"
    for data in scheduled[YOUR_CHANNEL_ID].values():
        text += f"• {data['full_name']} - {toshkent_vaqti(data['time']).strftime('%d.%m %H:%M')}\n"
    await message.reply_text(text)

@app.on_message(filters.command("cancelban"))
async def cancelban_cmd(client, message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        return await message.reply_text("❌ Ruxsat yo'q!")
    
    args = message.text.split()
    if len(args) < 2:
        return await message.reply_text("❌ /cancelban @user")
    
    await message.reply_text(f"✅ Bekor qilindi: {args[1]}")

@app.on_message(filters.command("history"))
async def history_cmd(client, message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        return await message.reply_text("❌ Ruxsat yo'q!")
    
    await message.reply_text(f"📜 Tarix: {len(user_history)} ta foydalanuvchi")

# ==================== VAQTLI BLOKLASH TEKSHIRUVI ====================
async def check_bans():
    while True:
        try:
            now = datetime.now()
            for chat_id in list(scheduled.keys()):
                for user_id in list(scheduled[chat_id].keys()):
                    if now >= scheduled[chat_id][user_id]["time"]:
                        try:
                            data = scheduled[chat_id][user_id]
                            until_date = now + timedelta(days=366)
                            await app.ban_chat_member(chat_id, user_id, until_date=until_date)
                            
                            if user_id in user_history:
                                user_history[user_id]["leave_time"] = now
                                user_history[user_id]["status"] = "banned"
                            
                            join_time = data.get("join_time", now)
                            time_in_channel = now - join_time
                            
                            await app.send_message(
                                YOUR_ID,
                                f"🚫 **BLOKLANDI!**\n\n"
                                f"👤 {data['full_name']}\n"
                                f"🆔 ID: `{user_id}`\n"
                                f"⏱️ Kanalda: {time_in_channel.days} kun\n"
                                f"📅 {now.strftime('%d.%m.%Y %H:%M')}"
                            )
                            
                            del scheduled[chat_id][user_id]
                            save_data()
                        except Exception as e:
                            print(f"Bloklash xatosi: {e}")
        except Exception as e:
            print(f"Tekshirish xatosi: {e}")
        await asyncio.sleep(60)

# ==================== MA'LUMOTLARNI AVTOMATIK SAQLASH ====================
async def auto_save():
    while True:
        await asyncio.sleep(3600)
        save_data()

async def auto_clean():
    while True:
        await asyncio.sleep(86400)
        clean_old_data()

# ==================== BOTNI ISHGA TUSHIRISH ====================
async def main():
    asyncio.create_task(check_bans())
    asyncio.create_task(auto_save())
    asyncio.create_task(auto_clean())
    
    print("=" * 60)
    print("✅ ABADIY BLOKLASH BOTI ISHGA TUSHDI!")
    print("=" * 60)
    print(f"🤖 Bot: @uzdramadubbot")
    print(f"👤 Egasi: @maestro_o (ID: {YOUR_ID})")
    print(f"📌 Kanal ID: {YOUR_CHANNEL_ID}")
    print("=" * 60)
    print("📋 **TUGMALI MENYU:**")
    print("   • /start - Tugmali menyu")
    print("   • Barcha komandalar tugmalarda")
    print("=" * 60)
    
    await app.run()

if __name__ == "__main__":
    asyncio.run(main())
