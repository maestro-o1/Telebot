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

# Botni yaratish
app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Rejalashtirilgan bloklashlar
scheduled_bans = {}

def parse_time(time_str: str) -> int:
    """Vaqtni minutlarga o'tkazish"""
    try:
        time_str = time_str.lower()
        # Kunlar
        if 'kun' in time_str or 'k' in time_str:
            son = int(''.join(filter(str.isdigit, time_str)))
            return son * 24 * 60
        # Oylar (30 kun = 1 oy)
        elif 'oy' in time_str or 'month' in time_str:
            son = int(''.join(filter(str.isdigit, time_str)))
            return son * 30 * 24 * 60
        # Soatlar
        elif 'soat' in time_str or 'h' in time_str:
            son = int(''.join(filter(str.isdigit, time_str)))
            return son * 60
        # Minutlar
        elif 'minut' in time_str or 'm' in time_str:
            son = int(''.join(filter(str.isdigit, time_str)))
            return son
        # Agar faqat son bo'lsa - minut deb hisobla
        else:
            return int(time_str)
    except:
        return 30  # Agar xato bo'lsa, 30 minut

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "👋 **Vaqtli bloklash boti ishga tushdi!**\n\n"
        "📝 **Komandalar:**\n"
        "🔹 /setban @user 30minut - 30 daqiqa\n"
        "🔹 /setban @user 2soat - 2 soat\n"
        "🔹 /setban @user 5kun - 5 kun\n"
        "🔹 /setban @user 10kun - 10 kun\n"
        "🔹 /setban @user 20kun - 20 kun\n"
        "🔹 /setban @user 1oy - 1 oy\n"
        "🔹 /setban @user 2oy - 2 oy\n"
        "🔹 /list - Barcha rejalashtirilganlar\n"
        "🔹 /cancelban @user - Bekor qilish\n\n"
        "⚡️ Bot ishlayapti!"
    )

@app.on_message(filters.command("setban"))
async def set_ban(client: Client, message: Message):
    # Adminlikni tekshirish
    try:
        chat_member = await client.get_chat_member(message.chat.id, "me")
        if chat_member.status not in ["administrator", "creator"]:
            await message.reply_text("❌ Bot kanalda admin emas!\nKanal sozlamalarida admin qilib qo'shing.")
            return
    except:
        await message.reply_text("❌ Bot kanalda admin emas!")
        return

    # Komandani tekshirish
    if len(message.command) < 3:
        await message.reply_text("❌ Noto'g'ri format!\nMisol: /setban @user 10kun")
        return

    username = message.command[1].replace("@", "")
    time_str = message.command[2]

    try:
        # Username bo'yicha user ID ni olish
        try:
            user = await client.get_users(username)
        except:
            await message.reply_text(f"❌ @{username} topilmadi!")
            return

        # Vaqtni hisoblash
        minutes = parse_time(time_str)
        ban_time = datetime.now() + timedelta(minutes=minutes)

        # Rejalashtirilgan bloklashlarni saqlash
        chat_id = message.chat.id
        if chat_id not in scheduled_bans:
            scheduled_bans[chat_id] = {}
        
        scheduled_bans[chat_id][user.id] = {
            "username": username,
            "ban_time": ban_time,
            "set_by": message.from_user.id
        }

        # Vaqtni formatlash
        vaqt = ban_time.strftime("%H:%M %d.%m.%Y")
        
        # Qancha vaqt qolganini hisoblash
        qolgan = ban_time - datetime.now()
        kun = qolgan.days
        soat = qolgan.seconds // 3600
        minut = (qolgan.seconds % 3600) // 60
        
        if kun > 0:
            qolgan_text = f"{kun} kun {soat} soat"
        elif soat > 0:
            qolgan_text = f"{soat} soat {minut} minut"
        else:
            qolgan_text = f"{minut} minut"
        
        await message.reply_text(
            f"✅ **@{username}** {time_str} dan keyin bloklanadi.\n"
            f"⏰ Vaqt: {vaqt}\n"
            f"⏳ Qoldi: {qolgan_text}"
        )

        logger.info(f"Rejalashtirildi: @{username} -> {ban_time}")

    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

@app.on_message(filters.command("cancelban"))
async def cancel_ban(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("❌ Username ko'rsating!\nMisol: /cancelban @user")
        return

    username = message.command[1].replace("@", "")
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

@app.on_message(filters.command("list"))
async def list_bans(client: Client, message: Message):
    chat_id = message.chat.id
    
    if chat_id not in scheduled_bans or not scheduled_bans[chat_id]:
        await message.reply_text("📭 Rejalashtirilgan bloklashlar yo'q.")
        return

    text = "📋 **Rejalashtirilgan bloklashlar:**\n\n"
    for user_id, data in scheduled_bans[chat_id].items():
        vaqt = data["ban_time"].strftime("%H:%M %d.%m.%Y")
        
        # Qancha vaqt qolganini hisoblash
        qolgan = data["ban_time"] - datetime.now()
        if qolgan.total_seconds() > 0:
            kun = qolgan.days
            soat = qolgan.seconds // 3600
            if kun > 0:
                qolgan_text = f"(qoldi: {kun} kun)"
            elif soat > 0:
                qolgan_text = f"(qoldi: {soat} soat)"
            else:
                qolgan_text = f"(qoldi: {qolgan.seconds//60} min)"
        else:
            qolgan_text = "(kutilmoqda)"
        
        text += f"• @{data['username']} - {vaqt} {qolgan_text}\n"
    
    await message.reply_text(text)

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
                            logger.info(f"✅ Bloklandi: @{data['username']}")
                            
                            # Kanalga xabar (agar xohlasangiz)
                            try:
                                await app.send_message(
                                    chat_id, 
                                    f"🚫 @{data['username']} bloklandi (vaqt tugadi)"
                                )
                            except:
                                pass
                                
                            to_remove.append((chat_id, user_id))
                        except Exception as e:
                            logger.error(f"Bloklashda xatolik: {e}")

            # Bloklanganlarni ro'yxatdan o'chirish
            for chat_id, user_id in to_remove:
                if chat_id in scheduled_bans and user_id in scheduled_bans[chat_id]:
                    del scheduled_bans[chat_id][user_id]

        except Exception as e:
            logger.error(f"Tekshirishda xatolik: {e}")

        # Har 60 sekundda tekshirish
        await asyncio.sleep(60)

async def main():
    """Botni ishga tushirish"""
    print("🤖 Bot ishga tushmoqda...")
    print(f"🤖 Bot: @uzdramadubbot")
    print(f"⏰ Vaqt: {datetime.now().strftime('%H:%M %d.%m.%Y')}")
    
    # Tekshirish funksiyasini ishga tushirish
    asyncio.create_task(check_bans())
    
    print("✅ Bot muvaffaqiyatli ishga tushdi!")
    
    # Botni ishga tushirish
    await app.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("❌ Bot to'xtatildi")
    except Exception as e:
        print(f"❌ Xatolik: {e}")
