import asyncio
from datetime import datetime, timedelta
from pyrogram import Client, filters

# SOZLAMALAR
API_ID = 35058290
API_HASH = "d7cb549b10b8965c99673f8bd36c130a"
BOT_TOKEN = "8660286208:AAHssllobxtng0RDXfZ70fEkfFbjx13FyQE"

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
scheduled = {}

def parse_time(time_str):
    try:
        if 'kun' in time_str:
            return int(time_str.replace('kun', '')) * 24 * 60
        elif 'oy' in time_str:
            return int(time_str.replace('oy', '')) * 30 * 24 * 60
        else:
            return 30
    except:
        return 30

def toshkent_vaqti(vaqt):
    """Server vaqtini Toshkent vaqtiga o'tkazish (+5 soat)"""
    return vaqt + timedelta(hours=5)

@app.on_message(filters.command("start"))
async def start_command(client, message):
    await message.reply_text(
        "✅ **VAQTLI BLOKLASH BOTI**\n\n"
        "🔹 /setban @user 10kun\n"
        "🔹 /setban @user 20kun\n"
        "🔹 /setban @user 30kun\n"
        "🔹 /setban @user 40kun\n"
        "🔹 /setban @user 1oy\n"
        "🔹 /list\n"
        "🔹 /cancelban @user"
    )

@app.on_message(filters.command("setban"))
async def set_ban(client, message):
    try:
        args = message.text.split()
        if len(args) < 3:
            await message.reply_text("❌ /setban @user 10kun")
            return
        
        username = args[1].replace("@", "")
        time_str = args[2]
        
        # Vaqtni hisoblash
        if 'kun' in time_str:
            kun = int(time_str.replace('kun', ''))
            minutes = kun * 24 * 60
        elif 'oy' in time_str:
            oy = int(time_str.replace('oy', ''))
            minutes = oy * 30 * 24 * 60
        else:
            minutes = 30
            
        user = await client.get_users(username)
        ban_time = datetime.now() + timedelta(minutes=minutes)
        
        if message.chat.id not in scheduled:
            scheduled[message.chat.id] = {}
            
        scheduled[message.chat.id][user.id] = {
            "username": username,
            "time": ban_time
        }
        
        # Toshkent vaqtida ko'rsatish
        toshkent_vaqt = toshkent_vaqti(ban_time)
        sana = toshkent_vaqt.strftime("%d.%m.%Y %H:%M")
        
        await message.reply_text(
            f"✅ @{username} {time_str} dan keyin bloklanadi\n"
            f"📅 Toshkent vaqti: {sana}"
        )
        
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

@app.on_message(filters.command("list"))
async def list_bans(client, message):
    if message.chat.id not in scheduled or not scheduled[message.chat.id]:
        await message.reply_text("📭 Bloklashlar yo'q")
        return
        
    text = "📋 **Bloklashlar (Toshkent vaqti):**\n\n"
    for data in scheduled[message.chat.id].values():
        toshkent_vaqt = toshkent_vaqti(data["time"])
        sana = toshkent_vaqt.strftime("%d.%m %H:%M")
        text += f"• @{data['username']} - {sana}\n"
    await message.reply_text(text)

@app.on_message(filters.command("cancelban"))
async def cancel_ban(client, message):
    try:
        args = message.text.split()
        if len(args) < 2:
            await message.reply_text("❌ /cancelban @user")
            return
            
        username = args[1].replace("@", "")
        user = await client.get_users(username)
        
        if message.chat.id in scheduled and user.id in scheduled[message.chat.id]:
            del scheduled[message.chat.id][user.id]
            await message.reply_text(f"✅ @{username} bekor qilindi")
        else:
            await message.reply_text(f"❌ @{username} topilmadi")
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

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
                            print(f"Bloklandi: {user_id}")
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
