from datetime import datetime, timedelta
from pyrogram import Client, filters

# SOZLAMALAR
API_ID = 35058290
API_HASH = "d7cb549b10b8965c99673f8bd36c130a"
BOT_TOKEN = "8660286208:AAHssllobxtng0RDXfZ70fEkfFbjx13FyQE"

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
scheduled = {}

def parse_time(time_str):
    """
    Vaqt matnini minutlarga o'tkazish
    Misollar: 5minut -> 5, 10kun -> 14400, 1oy -> 43200
    """
    try:
        time_str = time_str.lower().strip()
        
        # Raqamlarni ajratib olish
        number = ''
        for char in time_str:
            if char.isdigit():
                number += char
            else:
                break
        
        if not number:
            return 30
            
        number = int(number)
        
        # Vaqt birligini aniqlash
        if 'kun' in time_str:
            return number * 24 * 60
        elif 'oy' in time_str:
            return number * 30 * 24 * 60
        elif 'soat' in time_str:
            return number * 60
        elif 'minut' in time_str:
            return number
        else:
            # Agar birlik ko'rsatilmagan bo'lsa, minut deb hisobla
            return number
            
    except Exception as e:
        print(f"Vaqtni parse qilishda xatolik: {e}")
        return 30  # Xato bo'lsa 30 minut

def toshkent_vaqti(vaqt):
    """Server vaqtini Toshkent vaqtiga o'tkazish (+5 soat)"""
    return vaqt + timedelta(hours=5)

@app.on_message(filters.command("start"))
async def start_command(client, message):
    await message.reply_text(
        "✅ **VAQTLI BLOKLASH BOTI**\n\n"
        "**📌 QO'LLANMA:**\n"
        "🔹 /setban @user 5minut\n"
        "🔹 /setban @user 2soat\n"
        "🔹 /setban @user 10kun\n"
        "🔹 /setban @user 20kun\n"
        "🔹 /setban @user 30kun\n"
        "🔹 /setban @user 40kun\n"
        "🔹 /setban @user 1oy\n"
        "🔹 /list - Ro'yxat\n"
        "🔹 /cancelban @user - Bekor qilish\n\n"
        "⚡️ Barcha vaqtlar Toshkent vaqtida ko'rsatiladi"
    )

@app.on_message(filters.command("setban"))
async def set_ban(client, message):
    try:
        args = message.text.split()
        if len(args) < 3:
            await message.reply_text("❌ /setban @user 5minut")
            return
        
        username = args[1].replace("@", "")
        time_str = args[2]
        
        # Vaqtni hisoblash
        minutes = parse_time(time_str)
        
        if minutes <= 0:
            await message.reply_text("❌ Noto'g'ri vaqt format!")
            return
            
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
        
        # Qancha minut qolganini hisoblash
        qolgan_minut = (ban_time - datetime.now()).total_seconds() / 60
        
        await message.reply_text(
            f"✅ **@{username}** {time_str} dan keyin bloklanadi\n\n"
            f"📅 **Sana:** {sana}\n"
            f"⏰ **Vaqt:** {time_str}\n"
            f"⏳ **Minut:** {int(minutes)} minut\n"
            f"🎯 **Holat:** Rejalashtirildi"
        )
        
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

@app.on_message(filters.command("list"))
async def list_bans(client, message):
    if message.chat.id not in scheduled or not scheduled[message.chat.id]:
        await message.reply_text("📭 Hech qanday bloklash rejalashtirilmagan")
        return
        
    text = "📋 **REJALASHTIRILGAN BLOKLASHLAR:**\n\n"
    now = datetime.now()
    
    for user_id, data in list(scheduled[message.chat.id].items()):
        toshkent_vaqt = toshkent_vaqti(data["time"])
        sana = toshkent_vaqt.strftime("%d.%m.%Y %H:%M")
        
        # Qancha vaqt qolganini hisoblash
        qolgan = data["time"] - now
        if qolgan.total_seconds() > 0:
            soat = qolgan.seconds // 3600
            minut = (qolgan.seconds % 3600) // 60
            if qolgan.days > 0:
                qolgan_text = f"(qoldi: {qolgan.days} kun {soat} soat)"
            elif soat > 0:
                qolgan_text = f"(qoldi: {soat} soat {minut} minut)"
            else:
                qolgan_text = f"(qoldi: {minut} minut)"
        else:
            qolgan_text = "(kutilmoqda)"
        
        text += f"• @{data['username']} - {sana} {qolgan_text}\n"
    
    text += f"\n📊 Jami: {len(scheduled[message.chat.id])} ta bloklash"
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
            # Bloklash haqida ma'lumot
            data = scheduled[message.chat.id][user.id]
            toshkent_vaqt = toshkent_vaqti(data["time"])
            sana = toshkent_vaqt.strftime("%d.%m.%Y %H:%M")
            
            # O'chirish
            del scheduled[message.chat.id][user.id]
            
            await message.reply_text(
                f"✅ **@{username}** uchun bloklash bekor qilindi\n"
                f"📅 Rejalashtirilgan vaqt: {sana}"
            )
        else:
            await message.reply_text(f"❌ @{username} rejalashtirilmagan")
            
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}")

# Vaqtli bloklash tekshiruvi
import asyncio
import threading

def check_bans_background():
    """Background thread orqali vaqtli bloklashni tekshirish"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def check():
        while True:
            try:
                now = datetime.now()
                for chat_id in list(scheduled.keys()):
                    for user_id in list(scheduled[chat_id].keys()):
                        if now >= scheduled[chat_id][user_id]["time"]:
                            try:
                                # Bloklash
                                await app.ban_chat_member(chat_id, user_id)
                                username = scheduled[chat_id][user_id]["username"]
                                print(f"✅ Bloklandi: @{username}")
                                
                                # Kanalga xabar (ixtiyoriy)
                                try:
                                    toshkent_vaqt = toshkent_vaqti(now)
                                    sana = toshkent_vaqt.strftime("%d.%m.%Y %H:%M")
                                    await app.send_message(
                                        chat_id,
                                        f"🚫 @{username} bloklandi\n📅 Vaqt: {sana}"
                                    )
                                except:
                                    pass
                                    
                                del scheduled[chat_id][user_id]
                            except Exception as e:
                                print(f"Bloklash xatosi: {e}")
            except Exception as e:
                print(f"Tekshirish xatosi: {e}")
            await asyncio.sleep(60)
    
    loop.run_until_complete(check())

# Threadda ishga tushirish
thread = threading.Thread(target=check_bans_background, daemon=True)
thread.start()

print("✅ Bot ishga tushdi!")
print(f"🤖 Bot: @uzdramadubbot")
print(f"⏰ Toshkent vaqti: {(datetime.now() + timedelta(hours=5)).strftime('%H:%M %d.%m.%Y')}")
app.run()
