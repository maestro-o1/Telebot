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
BOT_TOKEN = "8660286208:AAGQlKj9yni5HNoWCeGW7x_1V6vdWFiTdlc"

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
scheduled_bans = {}

def parse_time(time_str: str) -> int:
    try:
        time_str = time_str.lower()
        if 'oy' in time_str:
            return int(''.join(filter(str.isdigit, time_str))) * 30 * 24 * 60
        elif 'kun' in time_str:
            return int(''.join(filter(str.isdigit, time_str))) * 24 * 60
        elif 'soat' in time_str:
            return int(''.join(filter(str.isdigit, time_str))) * 60
        elif 'minut' in time_str:
            return int(''.join(filter(str.isdigit, time_str)))
        else:
            return int(time_str)
    except:
        return 30

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "👋 **Vaqtli bloklash boti ishga tushdi!**\n\n"
        "📝 **Komandalar:**\n"
        "/setban @user 10kun - 10 kun\n"
        "/setban @user 1oy - 1 oy\n"
        "/list - Ro'yxat\n"
        "/cancelban @user - Bekor qilish"
    )

@app.on_message(filters.command("setban"))
async def set_ban(client: Client, message: Message):
    if len(message.command) < 3:
        return await message.reply_text("❌ /setban @user 10kun")
    
    username = message.command[1].replace("@", "")
    time_str = message.command[2]
    
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
        
        vaqt = ban_time.strftime("%H:%M %d.%m.%Y")
        await message.reply_text(f"✅ @{username} {time_str} dan keyin bloklanadi\n⏰ {vaqt}")
        
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

@app.on_message(filters.command("list"))
async def list_bans(client: Client, message: Message):
    chat_id = message.chat.id
    
    if chat_id not in scheduled_bans or not scheduled_bans[chat_id]:
        return await message.reply_text("📭 Bloklashlar yo'q")
    
    text = "📋 **Bloklashlar:**\n"
    for data in scheduled_bans[chat_id].values():
        vaqt = data["ban_time"].strftime("%d.%m %H:%M")
        text += f"• @{data['username']} - {vaqt}\n"
    
    await message.reply_text(text)

@app.on_message(filters.command("cancelban"))
async def cancel_ban(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("❌ /cancelban @user")
    
    username = message.command[1].replace("@", "")
    
    try:
        user = await client.get_users(username)
        chat_id = message.chat.id
        
        if chat_id in scheduled_bans and user.id in scheduled_bans[chat_id]:
            del scheduled_bans[chat_id][user.id]
            await message.reply_text(f"✅ @{username} bekor qilindi")
    except:
        await message.reply_text("❌ @{username} topilmadi")

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
                            logger.info(f"Bloklandi")
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
