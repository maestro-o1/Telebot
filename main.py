import asyncio
from pyrogram import Client, filters

# BOT SOZLAMALARI
API_ID = 35058290
API_HASH = "d7cb549b10b8965c99673f8bd36c130a"
BOT_TOKEN = "8660286208:AAHssllobxtng0RDXfZ70fEkfFbjx13FyQE"

# Botni yaratish
app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.command("start"))
async def start_command(client, message):
    await message.reply_text("✅ Bot ishlayapti!")

@app.on_message(filters.command("test"))
async def test_command(client, message):
    await message.reply_text("Test ok")

print("🤖 Bot ishga tushmoqda...")
app.run()
