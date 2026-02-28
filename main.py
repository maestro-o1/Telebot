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
app = Client("kanal_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Rejalashtirilgan bloklashlar
scheduled_bans = {}

def parse_time(time_str: str) -> int:
    """
    Vaqtni minutlarga o'tkazish
    Qo'llab-quvvatlanadigan formatlar:
    - 10kun, 20kun, 30kun, 40kun, 50kun, 60kun
    - 1oy, 2oy, 3oy, 4oy, 5oy, 6oy
    - 1soat, 2soat, 5soat, 10soat
    - 30minut, 45minut, 60minut
    """
    try:
        time_str = time_str.lower()
        # Raqamlarni ajratib olish
        number = int(''.join(filter(str.isdigit, time_str)))
        
        if 'oy' in time_str:
            # 1 oy = 30 kun
            minutes = number * 30 * 24 * 60
            return minutes
        elif 'kun' in time_str:
            minutes = number * 24 * 60
            return minutes
        elif 'soat' in time_str:
            minutes = number * 60
            return minutes
        elif 'minut' in time_str:
            return number
        else:
            # Agar faqat raqam bo'lsa, minut deb hisobla
            return number
    except Exception as e:
        logger.error(f"Vaqtni parse qilishda xatolik: {e}")
        return 30  # Xato bo'lsa 30 minut

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    """Start komandasi"""
    await message.reply_text(
        "👋 **VAQTLI BLOKLASH BOTI**\n\n"
        "✅ Bot ishga tushdi!\n\n"
        "📌 **KUNLIK BLOKLASH:**\n"
        "🔹 /setban @user 10kun - 10 kun\n"
        "🔹 /setban @user 20kun - 20 kun\n"
        "🔹 /setban @user 30kun - 30 kun\n"
        "🔹 /setban @user 40kun - 40 kun\n"
        "🔹 /setban @user 50kun - 50 kun\n"
        "🔹 /setban @user 60kun - 60 kun\n\n"
        "📌 **OYLIK BLOKLASH:**\n"
        "🔹 /setban @user 1oy - 1 oy (30 kun)\n"
        "🔹 /setban @user 2oy - 2 oy (60 kun)\n"
        "🔹 /setban @user 3oy - 3 oy (90 kun)\n"
        "🔹 /setban @user 4oy - 4 oy (120 kun)\n"
        "🔹 /setban @user 5oy - 5 oy (150 kun)\n"
        "🔹 /setban @user 6oy - 6 oy (180 kun)\n\n"
        "📌 **SOATLIK BLOKLASH:**\n"
        "🔹 /setban @user 1soat - 1 soat\n"
        "🔹 /setban @user 2soat - 2 soat\n"
        "🔹 /setban @user 5soat - 5 soat\n"
        "🔹 /setban @user 10soat - 10 soat\n\n"
        "📌 **BOSHQA KOMANDALAR:**\n"
        "🔹 /list - Barcha rejalashtirilganlar ro'yxati\n"
        "🔹 /cancelban @user - Bloklashni bekor qilish\n\n"
        "⚡️ Bot muammosiz ishlayapti!"
    )

@app.on_message(filters.command("setban"))
async def set_ban(client: Client, message: Message):
    """Vaqtli bloklashni rejalashtirish"""
    
    # Kanalda adminlikni tekshirish
    try:
        chat_member = await client.get_chat_member(message.chat.id, "me")
        if chat_member.status not in ["administrator", "creator"]:
            await message.reply_text(
                "❌ **XATOLIK: Bot kanalda ADMIN emas!**\n\n"
                "1. Kanal sozlamalariga o'ting\n"
                "2. Administratorlar bo'limi\n"
                "3. Admin qo'shish → @uzdramadubbot\n"
                "4. 'Foydalanuvchilarni bloklash' huquqini bering"
            )
            return
    except Exception as e:
        await message.reply_text("❌ Bot kanalda admin emas!")
        return

    # Komandani tekshirish
    args = message.text.split()
    if len(args) < 3:
        await message.reply_text(
            "❌ **Noto'g'ri format!**\n\n"
            "Misol: /setban @user 30kun\n"
            "Misol: /setban @user 2oy\n"
            "Misol: /setban @user 5soat"
        )
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
        
        if minutes == 0:
            await message.reply_text("❌ Noto'g'ri vaqt formati!")
            return
            
        ban_time = datetime.now() + timedelta(minutes=minutes)

        # Ma'lumotlarni saqlash
        chat_id = message.chat.id
        if chat_id not in scheduled_bans:
            scheduled_bans[chat_id] = {}
        
        scheduled_bans[chat_id][user.id] = {
            "username": username,
            "ban_time": ban_time,
            "set_by": message.from_user.id,
            "set_at": datetime.now()
        }

        # Vaqtni formatlash
        sana = ban_time.strftime("%Y-%m-%d")
        soat = ban_time.strftime("%H:%M")
        
        # Qancha vaqt qolganini hisoblash
        qolgan = ban_time - datetime.now()
        kun = qolgan.days
        soat_q = qolgan.seconds // 3600
        minut_q = (qolgan.seconds % 3600) // 60
        
        if kun > 0:
            qolgan_text = f"{kun} kun {soat_q} soat"
        elif soat_q > 0:
            qolgan_text = f"{soat_q} soat {minut_q} minut"
        else:
            qolgan_text = f"{minut_q} minut"

        # Qaysi vaqt birligi ishlatilganini aniqlash
        if 'oy' in time_str:
            vaqt_turi = "oy"
        elif 'kun' in time_str:
            vaqt_turi = "kun"
        elif 'soat' in time_str:
            vaqt_turi = "soat"
        else:
            vaqt_turi = "minut"

        await message.reply_text(
            f"✅ **BLOKLASH REJALASHTIRILDI**\n\n"
            f"👤 **Foydalanuvchi:** @{username}\n"
            f"⏰ **Vaqt:** {time_str}\n"
            f"📅 **Sana:** {sana}\n"
            f"🕒 **Soat:** {soat}\n"
            f"⏳ **Qoldi:** {qolgan_text}\n\n"
            f"🔍 Vaqt turi: {vaqt_turi}"
        )

        logger.info(f"✅ Rejalashtirildi: @{username} -> {ban_time} ({time_str})")

    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

@app.on_message(filters.command("cancelban"))
async def cancel_ban(client: Client, message: Message):
    """Bloklashni bekor qilish"""
    
    args = message.text.split()
    if len(args) < 2:
        await message.reply_text(
            "❌ **Username yozing!**\n\n"
            "Misol: /cancelban @user"
        )
        return

    username = args[1].replace("@", "")
    chat_id = message.chat.id

    try:
        user = await client.get_users(username)
        
        if chat_id in scheduled_bans and user.id in scheduled_bans[chat_id]:
            # Bloklash haqida ma'lumot
            data = scheduled_bans[chat_id][user.id]
            ban_time = data["ban_time"].strftime("%Y-%m-%d %H:%M")
            
            # O'chirish
            del scheduled_bans[chat_id][user.id]
            
            await message.reply_text(
                f"✅ **BLOKLASH BEKOR QILINDI**\n\n"
                f"👤 **Foydalanuvchi:** @{username}\n"
                f"📅 **Rejalashtirilgan vaqt:** {ban_time}"
            )
            
            logger.info(f"✅ Bekor qilindi: @{username}")
        else:
            await message.reply_text(f"❌ @{username} uchun rejalashtirilgan bloklash topilmadi!")
            
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: @{username} topilmadi!")

@app.on_message(filters.command("list"))
async def list_bans(client: Client, message: Message):
    """Barcha rejalashtirilgan bloklashlar ro'yxati"""
    
    chat_id = message.chat.id
    
    if chat_id not in scheduled_bans or not scheduled_bans[chat_id]:
        await message.reply_text("📭 **REJALASHTIRILGAN BLOKLASHLAR YO'Q**")
        return

    text = "📋 **REJALASHTIRILGAN BLOKLASHLAR**\n\n"
    
    for user_id, data in scheduled_bans[chat_id].items():
        # Vaqtni formatlash
        sana = data["ban_time"].strftime("%d.%m.%Y")
        soat = data["ban_time"].strftime("%H:%M")
        
        # Qancha vaqt qolganini hisoblash
        qolgan = data["ban_time"] - datetime.now()
        if qolgan.total_seconds() > 0:
            kun = qolgan.days
            soat_q = qolgan.seconds // 3600
            minut_q = (qolgan.seconds % 3600) // 60
            
            if kun > 0:
                qolgan_text = f"(qoldi: {kun} kun {soat_q} soat)"
            elif soat_q > 0:
                qolgan_text = f"(qoldi: {soat_q} soat {minut_q} minut)"
            else:
                qolgan_text = f"(qoldi: {minut_q} minut)"
        else:
            qolgan_text = "(kutilmoqda)"
        
        text += f"• @{data['username']} - {sana} {soat} {qolgan_text}\n"
    
    # Nechta bloklash borligini ko'rsatish
    soni = len(scheduled_bans[chat_id])
    text += f"\n📊 Jami: {soni} ta bloklash"
    
    await message.reply_text(text)

async def check_bans():
    """
    Har daqiqada vaqti kelganlarni tekshirib, bloklash
    """
    while True:
        try:
            now = datetime.now()
            bloklanganlar = []

            for chat_id in list(scheduled_bans.keys()):
                if chat_id not in scheduled_bans:
                    continue
                
                for user_id in list(scheduled_bans[chat_id].keys()):
                    data = scheduled_bans[chat_id][user_id]
                    
                    # Vaqti kelganmi?
                    if now >= data["ban_time"]:
                        try:
                            # Bloklash
                            await app.ban_chat_member(chat_id, user_id)
                            
                            # Kanalga xabar
                            try:
                                await app.send_message(
                                    chat_id,
                                    f"🚫 **FOYDALANUVCHI BLOKLANDI**\n\n"
                                    f"👤 **Username:** @{data['username']}\n"
                                    f"⏰ **Vaqt:** {data['ban_time'].strftime('%Y-%m-%d %H:%M')}\n\n"
                                    f"Bloklash vaqti tugadi."
                                )
                            except:
                                pass
                            
                            logger.info(f"✅ Bloklandi: @{data['username']}")
                            bloklanganlar.append((chat_id, user_id))
                            
                        except Exception as e:
                            logger.error(f"Bloklashda xatolik: {e}")

            # Bloklanganlarni ro'yxatdan o'chirish
            for chat_id, user_id in bloklanganlar:
                if chat_id in scheduled_bans and user_id in scheduled_bans[chat_id]:
                    del scheduled_bans[chat_id][user_id]

        except Exception as e:
            logger.error(f"Tekshirishda xatolik: {e}")

        # Har 60 sekundda tekshirish
        await asyncio.sleep(60)

async def main():
    """Botni ishga tushirish"""
    print("=" * 50)
    print("🤖 VAQTLI BLOKLASH BOTI")
    print("=" * 50)
    print(f"📊 API ID: {API_ID}")
    print(f"🤖 Bot: @uzdramadubbot")
    print(f"📅 Sana: {datetime.now().strftime('%Y-%m-%d')}")
    print(f"⏰ Vaqt: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 50)
    
    # Qo'llab-quvvatlanadigan vaqtlar
    print("📌 QO'LLAB-QUVVATLANADIGAN VAQTLAR:")
    print("   • 10kun, 20kun, 30kun, 40kun, 50kun, 60kun")
    print("   • 1oy, 2oy, 3oy, 4oy, 5oy, 6oy")
    print("   • 1soat, 2soat, 5soat, 10soat")
    print("   • 30minut, 45minut, 60minut")
    print("=" * 50)
    
    # Tekshirish funksiyasini ishga tushirish
    asyncio.create_task(check_bans())
    
    print("✅ Bot muvaffaqiyatli ishga tushdi!")
    print("📝 Kanalda /start yozib tekshiring")
    print("=" * 50)
    
    # Botni ishga tushirish
    await app.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Bot to'xtatildi")
    except Exception as e:
        print(f"\n❌ Xatolik: {e}")
