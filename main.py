import os
import asyncio
import logging
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import Message

# Bot sozlamalari
API_ID = 1234567  # KEYIN O'ZGARTIRASIZ
API_HASH = "your_api_hash_here"  # KEYIN O'ZGARTIRASIZ
BOT_TOKEN = "8660286208:AAGQlKj9yni5HNoWCeGW7x_1V6vdWFiTdlc"

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

scheduled_bans = {}

def parse_time(time_str: str) -> int:
    time_str = time_str.lower()
    if 'soat' in time_str or 'h' in time_str:
        return int(''.join(filter(str.isdigit, time_str))) * 60
    elif 'minut' in time_str or 'm' in time_str:
        return int(''.join(filter(str.isdigit, time_str)))
    elif 'kun' in time_str or 'd' in time_str:
        return int(''.join(filter(str.isdigit, time_str))) * 24 * 60
    return int(time_str)

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "👋 Xush kelibsiz! Vaqtli bloklash boti.\n\n"
        "📝 Komandalar:\n"
        "/setban @user 30minut - 30 daqiqadan keyin bloklash\n"
        "/setban @user 2soat - 2 soatdan keyin bloklash\n"
        "/setban @user 1kun - 1 kundan keyin bloklash\n"
        "/cancelban @user - bloklashni bekor qilish\n"
        "/list - rejalashtirilgan bloklashlar"
    )

@app.on_message(filters.command("setban"))
async def set_ban(client: Client, message: Message):
    if len(message.command) < 3:
        await message.reply_text("❌ Misol: /setban @user 30minut")
        return
    
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
        
        await message.reply_text(
            f"✅ @{username} {time_str} dan keyin bloklanadi\n"
            f"⏰ {ban_time.strftime('%H:%M %d.%m.%Y')}"
        )
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

@app.on_message(filters.command("cancelban"))
async def cancel_ban(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("❌ Username yozing: /cancelban @user")
        return
    
    username = message.command[1].replace("@", "")
    chat_id = message.chat.id
    
    try:
        user = await client.get_users(username)
        if chat_id in scheduled_bans and user.id in scheduled_bans[chat_id]:
            del scheduled_bans[chat_id][user.id]
            await message.reply_text(f"✅ @{username} uchun bloklash bekor qilindi")
        else:
            await message.reply_text(f"❌ @{username} rejalashtirilmagan")
    except:
        await message.reply_text(f"❌ @{username} topilmadi")

@app.on_message(filters.command("list"))
async def list_bans(client: Client, message: Message):
    chat_id = message.chat.id
    
    if chat_id not in scheduled_bans or not scheduled_bans[chat_id]:
        await message.reply_text("📭 Rejalashtirilgan bloklashlar yo'q")
        return
    
    text = "📋 Rejalashtirilgan bloklashlar:\n\n"
    for user_id, data in scheduled_bans[chat_id].items():
        time_str = data["ban_time"].strftime("%H:%M %d.%m.%Y")
        text += f"• @{data['username']} - {time_str}\n"
    
    await message.reply_text(text)

async def check_bans():
    while True:
        try:
            now = datetime.now()
            to_remove = []
            
            for chat_id in list(scheduled_bans.keys()):
                for user_id in list(scheduled_bans[chat_id].keys()):
                    data = scheduled_bans[chat_id][user_id]
                    if now >= data["ban_time"]:
                        try:
                            await app.ban_chat_member(chat_id, user_id)
                            logger.info(f"Bloklandi: @{data['username']}")
                            to_remove.append((chat_id, user_id))
                        except:
                            pass
            
            for chat_id, user_id in to_remove:
                if chat_id in scheduled_bans and user_id in scheduled_bans[chat_id]:
                    del scheduled_bans[chat_id][user_id]
        except:
            pass
        
        await asyncio.sleep(60)

async def main():
    asyncio.create_task(check_bans())
    print("✅ Bot ishga tushdi!")
    await app.run()

if __name__ == "__main__":
    asyncio.run(main())
