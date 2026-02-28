import nest_asyncio
nest_asyncio.apply()
import asyncio
import logging
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import Message

# BOT SOZLAMALARI - YANGI TOKEN KIRITILGAN
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
            return number * 30 * 24 * 60
        elif 'kun' in time_str:
            return number * 24 * 60
        elif 'soat' in time_str:
            return number * 60
        elif 'minut' in time_str:
            return number
        else:
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
        "🔹 /setban @user 40kun\n\n"
        "📌 **OYLIK:**\n"
        "🔹 /setban @user 1oy\n"
        "🔹 /setban @user 2oy\n\n"
        "📌 **BOSHQA:**\n"
        "🔹 /list - Ro'yxat\n"
        "🔹 /cancelban @user - Bekor qilish"
    )

@app.on_message(filters.command("setban"))
async def set_ban(client: Client, message: Message):
    # Adminlikni tekshirish
    try:
        chat_member = await client.get_chat_member(message.chat.id, "me")
        if chat_member.status not in ["administrator", "creator"]:
            await message.reply_text("❌ Bot kanalda ADMIN EMAS!\nKanal sozlamalarida admin qiling.")
            return
    except:
        await message.reply_text("❌ Bot kanalda admin emas!")
        return

    args = message.text.split()
    if len(args) < 3:
        await message.reply_text("❌ Noto'g'ri format!\nMisol: /setban @user 10kun")
        return

    username = args[1].replace("@", "")
    time_str = args[2]

    try:
        # Foydalanuvchini tekshirish
        try:
            user = await client.get_users(username)
        except:
            await message.reply_text(f"❌ @{username} topilmadi!")
            return

        # Vaqtni hisoblash
        minutes = parse_time(time_str)
        ban_time = datetime.now() + timedelta(minutes=minutes)

        # Ma'lumotlarni saqlash
        chat_id = message.chat.id
        if chat_id not in scheduled_bans:
            scheduled_bans[chat_id] = {}
        
        scheduled_bans[chat_id][user.id] = {
            "username": username,
            "ban_time": ban_time
        }

        # Vaqtni formatlash
        sana = ban_time.strftime("%Y-%m-%d %H:%M")
        
        await message.reply_text(
            f"✅ **BLOKLASH REJALASHTIRILDI**\n\n"
            f"👤 Foydalanuvchi: @{username}\n"
            f"⏰ Vaqt: {time_str}\n"
            f"📅 Sana: {sana}"
        )

        logger.info(f"Rejalashtirildi: @{username} -> {ban_time}")

    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

@app.on_message(filters.command("list"))
async def list_bans(client: Client, message: Message):
    chat_id = message.chat.id
    
    if chat_id not in scheduled_bans or not scheduled_bans[chat_id]:
        await message.reply_text("📭 Rejalashtirilgan bloklashlar yo'q.")
        return

    text = "📋 **REJALASHTIRILGAN BLOKLASHLAR:**\n\n"
    for user_id, data in scheduled_bans[chat_id].items():
        sana = data["ban_time"].strftime("%d.%m.%Y %H:%M")
        text += f"• @{data['username']} - {sana}\n"
    
    await message.reply_text(text)

@app.on_message(filters.command("cancelban"))
async def cancel_ban(client: Client, message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.reply_text("❌ Username yozing!\nMisol: /cancelban @user")
        return

    username = args[1].replace("@", "")
    chat_id = message.chat.id

    try:
        user = await client.get_users(username)
        
        if chat_id in scheduled_bans and user.id in scheduled_bans[chat_id]:
            del scheduled_bans[chat_id][user.id]
            await message.reply_text(f"✅ @{username} uchun bloklash bekor qilindi!")
        else:
            await message.reply_text(f"❌ @{username} rejalashtirilmagan!")
    except:
        await message.reply_text(f"❌ @{username} topilmadi!")

async def check_bans():
    """Har daqiqada vaqti kelganlarni bloklash"""
    while True:
        try:
            now = datetime.now()
            to_remove = []

            for chat_id in list(scheduled_bans.keys()):
                if chat_id not in scheduled_bans:
                    continue
                
                for user_id in list(scheduled_bans[chat_id].keys()):
                    data = scheduled_bans[chat_id][user_id]
                    if now >= data["ban_time"]:
                        try:
                            # Bloklash
                            await app.ban_chat_member(chat_id, user_id)
                            logger.info(f"Bloklandi: @{data['username']}")
                            to_remove.append((chat_id, user_id))
                        except Exception as e:
                            logger.error(f"Bloklashda xatolik: {e}")

            # Bloklanganlarni ro'yxatdan o'chirish
            for chat_id, user_id in to_remove:
                if chat_id in scheduled_bans and user_id in scheduled_bans[chat_id]:
                    del scheduled_bans[chat_id][user_id]

        except Exception as e:
            logger.error(f"Tekshirishda xatolik: {e}")

        await asyncio.sleep(60)

async def main():
    """Botni ishga tushirish"""
    print("=" * 40)
    print("🤖 VAQTLI BLOKLASH BOTI")
    print("=" * 40)
    print(f"📊 API ID: {API_ID}")
    print(f"🤖 Bot: @uzdramadubbot")
    print(f"⏰ Vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 40)
    
    # Tekshirish funksiyasini ishga tushirish
    asyncio.create_task(check_bans())
    
    print("✅ Bot muvaffaqiyatli ishga tushdi!")
    print("📝 Kanalda /start yozib tekshiring")
    print("=" * 40)
    
    # Botni ishga tushirish
    await app.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Bot to'xtatildi")
    except Exception as e:
        print(f"\n❌ Xatolik: {e}")
