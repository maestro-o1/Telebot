import asyncio
import uvloop
from datetime import datetime, timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import json
import os

# uvloop ni ishga tushirish (MUHIM!)
uvloop.install()

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
user_history = {}

# ==================== MA'LUMOTLARNI SAQLASH ====================
DATA_FILE = "bot_data.json"

def save_data():
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
                    "user_id": user_data["user_id"]
                }
        
        for user_id, hist_data in user_history.items():
            data["user_history"][str(user_id)] = {
                "username": hist_data.get("username", ""),
                "full_name": hist_data.get("full_name", ""),
                "join_time": hist_data["join_time"].isoformat(),
                "status": hist_data.get("status", "")
            }
        
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except:
        pass

def load_data():
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
                        "user_id": user_data["user_id"]
                    }
            
            for user_id, hist_data in data.get("user_history", {}).items():
                user_history[int(user_id)] = {
                    "username": hist_data.get("username", ""),
                    "full_name": hist_data.get("full_name", ""),
                    "join_time": datetime.fromisoformat(hist_data["join_time"]),
                    "status": hist_data.get("status", "")
                }
    except:
        pass

load_data()

def parse_time(time_str):
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

# ==================== ASOSIY MENYU ====================
def get_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 KANAL TANLASH", callback_data="menu_select")],
        [InlineKeyboardButton("👥 A'ZOLAR", callback_data="menu_members")],
        [InlineKeyboardButton("🚫 BLOKLASH", callback_data="menu_ban")],
        [InlineKeyboardButton("📊 BLOKLASHLAR", callback_data="menu_list")],
        [InlineKeyboardButton("❌ BEKOR QILISH", callback_data="menu_cancel")],
        [InlineKeyboardButton("📜 TARIX", callback_data="menu_history")]
    ])

# ==================== START ====================
@app.on_message(filters.command("start"))
async def start_command(client, message):
    if not is_owner(message.from_user.id):
        await message.reply_text("❌ Ruxsat yo'q!")
        return
    
    await message.reply_text(
        f"✅ **ABADIY BLOKLASH BOTI**\n\n"
        f"👤 Xush kelibsiz, @maestro_o!\n\n"
        f"📌 Kanal ID: `{YOUR_CHANNEL_ID}`\n\n"
        f"Quyidagi tugmalardan birini tanlang:",
        reply_markup=get_main_menu()
    )

# ==================== TUGMALAR ====================
@app.on_callback_query()
async def handle_callbacks(client, callback_query):
    data = callback_query.data
    user_id = callback_query.from_user.id
    
    if user_id != YOUR_ID:
        await callback_query.answer("Ruxsat yo'q!")
        return
    
    if data == "back_to_menu":
        await callback_query.message.edit_text(
            f"✅ **ABADIY BLOKLASH BOTI**\n\n"
            f"👤 Xush kelibsiz, @maestro_o!\n\n"
            f"📌 Kanal ID: `{YOUR_CHANNEL_ID}`",
            reply_markup=get_main_menu()
        )
        await callback_query.answer()
    
    elif data == "menu_select":
        selected_channel[user_id] = {
            "chat_id": YOUR_CHANNEL_ID,
            "title": "Luli vip kanal"
        }
        await callback_query.message.edit_text(
            f"✅ **KANAL TANLANDI!**\n\n"
            f"📌 {selected_channel[user_id]['title']}\n"
            f"🆔 `{YOUR_CHANNEL_ID}`\n\n"
            f"Endi /members yozib a'zolarni ko'ring.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ ORQAGA", callback_data="back_to_menu")]
            ])
        )
        await callback_query.answer()
    
    elif data == "menu_members":
        if user_id not in selected_channel:
            await callback_query.message.edit_text(
                "❌ Avval kanal tanlang!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 KANAL TANLASH", callback_data="menu_select")],
                    [InlineKeyboardButton("◀️ ORQAGA", callback_data="back_to_menu")]
                ])
            )
        else:
            await callback_query.message.edit_text(
                f"👥 **A'ZOLAR**\n\n"
                f"Kanal: {selected_channel[user_id]['title']}\n\n"
                f"`/members` - barcha a'zolar\n"
                f"`/members Alisher` - qidirish",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ ORQAGA", callback_data="back_to_menu")]
                ])
            )
        await callback_query.answer()
    
    elif data == "menu_ban":
        ban_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏱️ 5 minut", callback_data="ban_5m"),
             InlineKeyboardButton("⏱️ 10 minut", callback_data="ban_10m")],
            [InlineKeyboardButton("⏱️ 30 minut", callback_data="ban_30m"),
             InlineKeyboardButton("📅 1 kun", callback_data="ban_1k")],
            [InlineKeyboardButton("📅 5 kun", callback_data="ban_5k"),
             InlineKeyboardButton("📅 10 kun", callback_data="ban_10k")],
            [InlineKeyboardButton("📅 20 kun", callback_data="ban_20k"),
             InlineKeyboardButton("📅 30 kun", callback_data="ban_30k")],
            [InlineKeyboardButton("📅 40 kun", callback_data="ban_40k"),
             InlineKeyboardButton("📆 1 oy", callback_data="ban_1oy")],
            [InlineKeyboardButton("📆 2 oy", callback_data="ban_2oy"),
             InlineKeyboardButton("📆 3 oy", callback_data="ban_3oy")],
            [InlineKeyboardButton("◀️ ORQAGA", callback_data="back_to_menu")]
        ])
        
        await callback_query.message.edit_text(
            "🚫 **BLOKLASH VAQTI TANLANG**",
            reply_markup=ban_keyboard
        )
        await callback_query.answer()
    
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
        await callback_query.answer()
    
    elif data == "menu_list":
        if YOUR_CHANNEL_ID not in scheduled or not scheduled[YOUR_CHANNEL_ID]:
            text = "📭 Bloklashlar yo'q"
        else:
            text = "📊 **BLOKLASHLAR:**\n\n"
            for data in scheduled[YOUR_CHANNEL_ID].values():
                sana = toshkent_vaqti(data["time"]).strftime("%d.%m %H:%M")
                text += f"• {data['full_name']} - {sana}\n"
        
        await callback_query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ ORQAGA", callback_data="back_to_menu")]
            ])
        )
        await callback_query.answer()
    
    elif data == "menu_cancel":
        await callback_query.message.edit_text(
            f"❌ **BEKOR QILISH**\n\n"
            f"`/cancelban @user`\n"
            f"`/cancelban 123456789`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ ORQAGA", callback_data="back_to_menu")]
            ])
        )
        await callback_query.answer()
    
    elif data == "menu_history":
        text = f"📜 **TARIX:** {len(user_history)} ta foydalanuvchi"
        await callback_query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ ORQAGA", callback_data="back_to_menu")]
            ])
        )
        await callback_query.answer()

# ==================== YANGI A'ZO ====================
@app.on_chat_member_updated()
async def on_chat_member_update(client, chat_member_updated):
    try:
        chat = chat_member_updated.chat
        new_member = chat_member_updated.new_chat_member
        
        if chat.id != YOUR_CHANNEL_ID:
            return
        
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
        
        await client.send_message(
            YOUR_ID,
            f"👤 **YANGI A'ZO!**\n\n"
            f"🆔 ID: `{user_id}`\n"
            f"👤 Ism: {full_name}"
        )
    except Exception as e:
        print(f"Xatolik: {e}")

# ==================== KOMANDALAR ====================
@app.on_message(filters.command("select"))
async def select_cmd(client, message):
    if not is_owner(message.from_user.id):
        return
    await message.reply_text("✅ Kanal tanlandi!")

@app.on_message(filters.command("members"))
async def members_cmd(client, message):
    if not is_owner(message.from_user.id):
        return
    await message.reply_text("👥 A'zolar yuklanmoqda...")

@app.on_message(filters.command("setban"))
async def setban_cmd(client, message):
    if not is_owner(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 3:
        await message.reply_text("❌ /setban @user 30k")
        return
    await message.reply_text(f"✅ Bloklash rejalashtirildi: {args[1]} {args[2]}")

@app.on_message(filters.command("list"))
async def list_cmd(client, message):
    if not is_owner(message.from_user.id):
        return
    await message.reply_text("📊 Bloklashlar ro'yxati")

@app.on_message(filters.command("cancelban"))
async def cancel_cmd(client, message):
    if not is_owner(message.from_user.id):
        return
    await message.reply_text("✅ Bekor qilindi")

@app.on_message(filters.command("history"))
async def history_cmd(client, message):
    if not is_owner(message.from_user.id):
        return
    await message.reply_text(f"📜 Tarix: {len(user_history)} ta")

# ==================== BLOKLASH TEKSHIRUVI ====================
async def check_bans():
    while True:
        try:
            now = datetime.now()
            for chat_id in list(scheduled.keys()):
                for user_id in list(scheduled[chat_id].keys()):
                    if now >= scheduled[chat_id][user_id]["time"]:
                        try:
                            await app.ban_chat_member(chat_id, user_id, until_date=now + timedelta(days=366))
                            del scheduled[chat_id][user_id]
                            save_data()
                        except:
                            pass
        except:
            pass
        await asyncio.sleep(60)

# ==================== SAQLASH ====================
async def auto_save():
    while True:
        await asyncio.sleep(3600)
        save_data()

# ==================== MAIN ====================
async def main():
    asyncio.create_task(check_bans())
    asyncio.create_task(auto_save())
    
    print("=" * 40)
    print("✅ BOT ISHGA TUSHDI!")
    print("=" * 40)
    print(f"🤖 @uzdramadubbot")
    print(f"👤 @maestro_o")
    print(f"📌 {YOUR_CHANNEL_ID}")
    print("=" * 40)
    
    await app.run()

if __name__ == "__main__":
    asyncio.run(main())
