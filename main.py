import nest_asyncio
nest_asyncio.apply()
import asyncio
import logging
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import Message

# BOT SOZLAMALARI
API_ID = 35058290
API_HASH = "d7cb549b10b8965c99673f8bd36c130a"
BOT_TOKEN = "8660286208:AAHssllobxtng0RDXfZ70fEkfFbjx13FyQE"

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Botni yaratish
app = Client("kanal_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Rejalashtirilgan bloklashlar
scheduled_bans = {}

def parse_time(time_str: str) -> int:
    """Vaqtni minutlarga o'tkazish"""
    try:
        time_str = time_str.lower()
        number = int(''.join(filter(str.isdigit, time_str)))
        
        if 'oy' in time_str:
            return number * 30 * 24 * 60  # 1 oy = 30 kun
        elif 'kun' in time_str:
            return number * 24 * 60
        elif 'soat' in time_str:
            return number * 60
        else:  # minut
            return number
    except:
        return 30

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "👋 **VAQTLI BLOKLASH BOTI**\n\n"
        "✅ Bot ishga tushdi!\n\n"
        "📌 **KUNLIK:**\n"
        "🔹 /setban @user 10kun\n"
        "🔹 /setban @user 20kun\n"
        "🔹 /setban @user 30kun\n"
        "🔹 /setban @user 40kun\n"
        "🔹 /setban @user 50kun\n"
        "🔹 /setban @user 60kun\n\n"
        "📌 **OYLIK:**\n"
        "🔹 /setban @user 1oy\n"
        "🔹 /setban @user 2oy\n"
        "🔹 /setban @user 3oy\n"
        "🔹 /setban @user 4oy\n"
        "🔹 /setban @user 5oy\n"
        "🔹 /setban @user 6oy\n\n"
        "📌 **BOSHQA KOMANDALAR:**\n"
        "🔹 /list - Ro'yxat\n"
        "🔹 /cancelban @user - Bekor qilish"
    )

@app.on_message(filters.command("setban"))
async def set_ban(client: Client, message: Message):
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
        ban_time = datetime.now() + timedelta(minutes=minutes)

        chat_id = message.chat.id
        if chat_id not in scheduled_bans:
            scheduled_bans[chat_id] = {}
        
        scheduled_bans[chat_id][user.id] = {
            "username": username,
            "ban_time": ban_time
        }

        sana = ban_time.strftime("%Y-%m-%d %H:%M")
        await message.reply_text(f"✅ @{username} {time_str} dan keyin bloklanadi\n⏰ {sana}")

    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

@app.on_message(filters.command("list"))
async def list_bans(client: Client, message: Message):
    chat_id = message.chat.id
    
    if chat_id not in scheduled_bans or not scheduled_bans[chat_id]:
        await message.reply_text("📭 Bloklashlar yo'q")
        return

    text = "📋 **Bloklashlar:**\n"
    for data in scheduled_bans[chat_id].values():
        sana = data["ban_time"].strftime("%d.%m %H:%M")
        text += f"• @{data['username']} - {sana}\n"
    
    await message.reply_text(text)

@app.on_message(filters.command("cancelban"))
async def cancel_ban(client: Client, message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.reply_text("❌ /cancelban @user")
        return

    username = args[1].replace("@", "")
    
    try:
        user = await client.get_users(username)
        chat_id = message.chat.id
        
        if chat_id in scheduled_bans and user.id in scheduled_bans[chat_id]:
            del scheduled_bans[chat_id][user.id]
            await message.reply_text(f"✅ @{username} bekor qilindi")
    except:
        await message.reply_text("❌ Xatolik")

async def check_bans():
    while True:
        try:
            now = datetime.now()
            for chat_id in list(scheduled_bans.keys()):
                for user_id in list(scheduled_bans[chat_id].keys()):
                    if now >= scheduled_bans[chat_id][user_id]["ban_time"]:
                        try:
                            await app.ban_chat_member(chat_id, user_id)
                            del scheduled_bans[chat_id][user_id]
                            logger.info("Bloklandi")
                        except:
                            pass
        except:
            pass
        await asyncio.sleep(60)

async def main():
    print("✅ Bot ishga tushdi!")
    asyncio.create_task(check_bans())
    await app.run()

if __name__ == "__main__":
    asyncio.run(main())
