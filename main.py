import logging
import os
import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import traceback

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes, 
    CallbackQueryHandler,
    ConversationHandler
)
from telegram.constants import ParseMode

# Loading environment variables
from dotenv import load_dotenv
load_dotenv()

# Bot configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))

# States for conversation handlers
(
    WAITING_CATEGORY_NAME,
    WAITING_PRODUCT_NAME,
    WAITING_PRODUCT_PHOTO,
    WAITING_PURCHASE_PRICE,
    WAITING_SELLING_PRICE,
    WAITING_QUANTITY,
    WAITING_SEARCH,
    WAITING_CONFIRM_DELETE
) = range(8)

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database setup
def init_database():
    conn = sqlite3.connect('shop_database.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            added_by INTEGER,
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Pending requests
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_requests (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Categories table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parent_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_id) REFERENCES categories (id) ON DELETE CASCADE
        )
    ''')
    
    # Products table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category_id INTEGER,
            photo_group_id INTEGER,
            photo_message_id INTEGER,
            photo_file_id TEXT,
            purchase_price_usd REAL NOT NULL,
            selling_price_usd REAL NOT NULL,
            quantity INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,
            FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE CASCADE
        )
    ''')
    
    # Groups table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            group_id INTEGER PRIMARY KEY,
            group_name TEXT,
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    conn.commit()
    conn.close()

def get_db_connection():
    return sqlite3.connect('shop_database.db')

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def is_allowed(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or "No username"
    full_name = user.full_name
    
    # Check if in group
    if update.effective_chat.type in ['group', 'supergroup']:
        chat_id = update.effective_chat.id
        chat_name = update.effective_chat.title
        
        # Check if bot is admin
        try:
            bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
            if bot_member.status not in ['administrator', 'creator']:
                await update.message.reply_text(
                    "❌ Bot guruhda admin emas!\n\n"
                    "Iltimos, botni admin qiling:\n"
                    "1. Guruh sozlamalari\n"
                    "2. Adminlar qo'shish\n"
                    "3. @gazzapchastbot ni admin qiling"
                )
                return
        except Exception as e:
            await update.message.reply_text("❌ Bot guruhda admin emas!")
            return
        
        # Save group info
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO groups (group_id, group_name, is_active)
            VALUES (?, ?, 1)
        ''', (chat_id, chat_name))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            f"✅ Bot ishga tushdi!\n"
            f"📦 Rasmlar shu guruhga saqlanadi"
        )
        return
    
    # Private chat
    if is_admin(user_id):
        await show_admin_menu(update, context)
    elif is_allowed(user_id):
        await show_user_menu(update, context)
    else:
        await show_request_access(update, context, user_id, username, full_name)

async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔍 Qidirish", callback_data="search")],
        [InlineKeyboardButton("📂 Kategoriyalar", callback_data="view_categories")],
        [InlineKeyboardButton("📊 Statistika", callback_data="stats")],
        [InlineKeyboardButton("➕ Tovar qo'shish", callback_data="add_product_start")],
        [InlineKeyboardButton("➕ Kategoriya qo'shish", callback_data="add_category")],
        [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="users")],
        [InlineKeyboardButton("📤 Eksport / Import", callback_data="export_import")]
    ]
    
    await update.message.reply_text(
        f"👋 Xush kelibsiz, Admin!\n\nKerakli bo'limni tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_user_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔍 Qidirish", callback_data="search")],
        [InlineKeyboardButton("📂 Kategoriyalar", callback_data="view_categories")],
        [InlineKeyboardButton("📊 Statistika", callback_data="stats")]
    ]
    
    await update.message.reply_text(
        "👋 Xush kelibsiz!\n\nKerakli bo'limni tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_request_access(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, username: str, full_name: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM pending_requests WHERE user_id = ?', (user_id,))
    if cursor.fetchone():
        await update.message.reply_text("⏳ So'rovingiz allaqachon yuborilgan. Admin tasdiqlashini kuting.")
        conn.close()
        return
    
    cursor.execute('INSERT INTO pending_requests (user_id, username, full_name) VALUES (?, ?, ?)',
                  (user_id, username, full_name))
    conn.commit()
    conn.close()
    
    keyboard = [[InlineKeyboardButton("🟢 Ruxsat so'rash", callback_data=f"request_{user_id}")]]
    
    await update.message.reply_text(
        f"❌ Botdan foydalanish uchun ruxsat kerak.\n\n"
        f"Sizning ID: `{user_id}`\n"
        f"Ruxsat so'rash tugmasini bosing:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

# Callback handler
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if not data.startswith('request_') and not is_admin(user_id) and not is_allowed(user_id):
        await query.edit_message_text("❌ Ruxsat yo'q")
        return
    
    # Main menu
    if data == "main_menu":
        if is_admin(user_id):
            keyboard = [
                [InlineKeyboardButton("🔍 Qidirish", callback_data="search")],
                [InlineKeyboardButton("📂 Kategoriyalar", callback_data="view_categories")],
                [InlineKeyboardButton("📊 Statistika", callback_data="stats")],
                [InlineKeyboardButton("➕ Tovar qo'shish", callback_data="add_product_start")],
                [InlineKeyboardButton("➕ Kategoriya qo'shish", callback_data="add_category")],
                [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="users")],
                [InlineKeyboardButton("📤 Eksport / Import", callback_data="export_import")]
            ]
            await query.edit_message_text("Bosh menyu:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            keyboard = [
                [InlineKeyboardButton("🔍 Qidirish", callback_data="search")],
                [InlineKeyboardButton("📂 Kategoriyalar", callback_data="view_categories")],
                [InlineKeyboardButton("📊 Statistika", callback_data="stats")]
            ]
            await query.edit_message_text("Bosh menyu:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # View categories
    elif data == "view_categories":
        await show_categories(query, context, None)
    
    # Add category
    elif data == "add_category" and is_admin(user_id):
        context.user_data['adding_category'] = True
        await query.edit_message_text("➕ Yangi kategoriya nomini kiriting:")
        return WAITING_CATEGORY_NAME
    
    # Start add product
    elif data == "add_product_start" and is_admin(user_id):
        await show_category_for_product(query, context)
    
    # Category click
    elif data.startswith("cat_"):
        cat_id = int(data.split('_')[1])
        await show_categories(query, context, cat_id)
    
    # Select category for product
    elif data.startswith("select_cat_"):
        cat_id = int(data.split('_')[2])
        context.user_data['product_category'] = cat_id
        context.user_data['adding_product'] = True
        await query.edit_message_text("📝 Tovar nomini kiriting:")
        return WAITING_PRODUCT_NAME
    
    # Add subcategory
    elif data.startswith("add_subcat_"):
        parent_id = int(data.split('_')[2])
        context.user_data['parent_category'] = parent_id
        context.user_data['adding_category'] = True
        await query.edit_message_text("➕ Yangi ichki kategoriya nomini kiriting:")
        return WAITING_CATEGORY_NAME
    
    # Add product to this category
    elif data.startswith("add_product_"):
        cat_id = int(data.split('_')[2])
        context.user_data['product_category'] = cat_id
        context.user_data['adding_product'] = True
        await query.edit_message_text("📝 Tovar nomini kiriting:")
        return WAITING_PRODUCT_NAME
    
    # Delete category confirmation
    elif data.startswith("delete_cat_"):
        cat_id = int(data.split('_')[2])
        context.user_data['delete_category'] = cat_id
        
        # Get category info
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM categories WHERE id = ?', (cat_id,))
        cat_name = cursor.fetchone()[0]
        
        # Count subcategories and products
        cursor.execute('SELECT COUNT(*) FROM categories WHERE parent_id = ?', (cat_id,))
        sub_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM products WHERE category_id = ?', (cat_id,))
        prod_count = cursor.fetchone()[0]
        
        conn.close()
        
        keyboard = [
            [InlineKeyboardButton("❌ Ha, o'chir", callback_data=f"confirm_delete_{cat_id}")],
            [InlineKeyboardButton("⬅️ Yo'q, orqaga", callback_data=f"cat_{cat_id}")]
        ]
        
        await query.edit_message_text(
            f"⚠️ **Ogohlantirish!**\n\n"
            f"Siz \"{cat_name}\" kategoriyasini o'chirmoqchisiz.\n\n"
            f"Bu kategoriya ichida:\n"
            f"- {sub_count} ta ichki kategoriya\n"
            f"- {prod_count} ta tovar\n\n"
            f"**HAMMASI BIRGA O'CHADI!**\n\n"
            f"Haqiqatan ham o'chirmoqchimisiz?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Confirm delete category
    elif data.startswith("confirm_delete_"):
        cat_id = int(data.split('_')[2])
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get category name
        cursor.execute('SELECT name FROM categories WHERE id = ?', (cat_id,))
        cat_name = cursor.fetchone()[0]
        
        # Delete all subcategories and products (cascade)
        cursor.execute('DELETE FROM categories WHERE id = ?', (cat_id,))
        
        conn.commit()
        conn.close()
        
        await query.edit_message_text(f"✅ \"{cat_name}\" kategoriyasi va uning barcha ichki kategoriyalari, tovarlari o'chirildi!")
        
        # Show parent category
        await show_categories(query, context, None)
    
    # Request access
    elif data.startswith("request_"):
        req_user_id = int(data.split('_')[1])
        await send_request_to_admin(query, context, req_user_id)
    
    # Approve user
    elif data.startswith("approve_"):
        await approve_user(query, context, data)
    
    # Reject user
    elif data.startswith("reject_"):
        await reject_user(query, context, data)

async def show_categories(query, context, parent_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if parent_id:
        cursor.execute('SELECT name FROM categories WHERE id = ?', (parent_id,))
        parent = cursor.fetchone()
        title = f"📂 {parent[0]}\n\n"
        
        # Get subcategories
        cursor.execute('SELECT id, name FROM categories WHERE parent_id = ? ORDER BY name', (parent_id,))
        categories = cursor.fetchall()
        
        # Get products in this category
        cursor.execute('SELECT id, name, quantity, selling_price_usd FROM products WHERE category_id = ? ORDER BY name', (parent_id,))
        products = cursor.fetchall()
    else:
        title = "📂 Bosh kategoriyalar\n\n"
        cursor.execute('SELECT id, name FROM categories WHERE parent_id IS NULL ORDER BY name')
        categories = cursor.fetchall()
        products = []
    
    keyboard = []
    
    # Add categories
    for cat_id, cat_name in categories:
        keyboard.append([InlineKeyboardButton(f"📁 {cat_name}", callback_data=f"cat_{cat_id}")])
    
    # Add products
    for prod_id, prod_name, qty, price in products:
        keyboard.append([InlineKeyboardButton(f"📦 {prod_name} ({qty} dona) - ${price}", callback_data=f"prod_{prod_id}")])
    
    # Add action buttons for admin
    if is_admin(query.from_user.id):
        if parent_id:
            keyboard.append([
                InlineKeyboardButton("➕ Ichki kategoriya", callback_data=f"add_subcat_{parent_id}"),
                InlineKeyboardButton("➕ Tovar", callback_data=f"add_product_{parent_id}")
            ])
            keyboard.append([InlineKeyboardButton("🗑 Kategoriyani o'chirish", callback_data=f"delete_cat_{parent_id}")])
        else:
            keyboard.append([InlineKeyboardButton("➕ Kategoriya qo'shish", callback_data="add_category")])
    
    # Back button
    if parent_id:
        cursor.execute('SELECT parent_id FROM categories WHERE id = ?', (parent_id,))
        back_parent = cursor.fetchone()[0]
        if back_parent:
            keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data=f"cat_{back_parent}")])
        else:
            keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="view_categories")])
    else:
        keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")])
    
    conn.close()
    
    await query.edit_message_text(title, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_category_for_product(query, context):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name FROM categories ORDER BY name')
    categories = cursor.fetchall()
    conn.close()
    
    if not categories:
        await query.edit_message_text("❌ Avval kategoriya yarating!")
        return
    
    keyboard = []
    for cat_id, cat_name in categories:
        keyboard.append([InlineKeyboardButton(cat_name, callback_data=f"select_cat_{cat_id}")])
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")])
    
    await query.edit_message_text(
        "📦 Tovar qaysi kategoriyaga tegishli?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Message handlers
async def handle_category_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('adding_category'):
        return
    
    category_name = update.message.text
    parent_id = context.user_data.get('parent_category')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if parent_id:
        cursor.execute('INSERT INTO categories (name, parent_id) VALUES (?, ?)',
                      (category_name, parent_id))
    else:
        cursor.execute('INSERT INTO categories (name) VALUES (?)', (category_name,))
    
    conn.commit()
    conn.close()
    
    context.user_data['adding_category'] = False
    context.user_data.pop('parent_category', None)
    
    await update.message.reply_text(f"✅ '{category_name}' kategoriyasi qo'shildi!")
    
    if is_admin(update.effective_user.id):
        await show_admin_menu(update, context)
    else:
        await show_user_menu(update, context)
    
    return ConversationHandler.END

async def handle_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('adding_product'):
        return
    
    context.user_data['product_name'] = update.message.text
    
    await update.message.reply_text(
        "🖼 Rasm yuboring yoki 'skip' deb yozing:"
    )
    return WAITING_PRODUCT_PHOTO

async def handle_product_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('adding_product'):
        return
    
    if update.message.photo:
        # Check if group exists
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT group_id FROM groups WHERE is_active = 1 LIMIT 1')
        group = cursor.fetchone()
        
        if not group:
            await update.message.reply_text(
                "❌ Rasm saqlash uchun guruh topilmadi!\n\n"
                "1. Guruh yarating\n"
                "2. Botni admin qiling\n"
                "3. Guruhda /start yozing"
            )
            return WAITING_PRODUCT_PHOTO
        
        group_id = group[0]
        conn.close()
        
        # Check if bot is admin
        try:
            bot_member = await context.bot.get_chat_member(group_id, context.bot.id)
            if bot_member.status not in ['administrator', 'creator']:
                await update.message.reply_text(
                    "❌ Bot guruhda admin emas!\n\n"
                    "Iltimos, botni guruhda admin qiling!"
                )
                return WAITING_PRODUCT_PHOTO
            
            # Send photo
            photo = update.message.photo[-1]
            sent = await context.bot.send_photo(
                chat_id=group_id,
                photo=photo.file_id,
                caption=f"#{context.user_data['product_name']}"
            )
            
            context.user_data['photo_group_id'] = group_id
            context.user_data['photo_message_id'] = sent.message_id
            context.user_data['photo_file_id'] = photo.file_id
            
            await update.message.reply_text("✅ Rasm saqlandi!")
            
        except Exception as e:
            await update.message.reply_text("❌ Rasm saqlashda xatolik! Bot guruhda admin emas.")
            return WAITING_PRODUCT_PHOTO
    else:
        context.user_data['photo_group_id'] = None
        context.user_data['photo_message_id'] = None
        context.user_data['photo_file_id'] = None
        await update.message.reply_text("✅ Rasmsiz davom etamiz")
    
    await update.message.reply_text("💰 Kelgan narxini kiriting ($):")
    return WAITING_PURCHASE_PRICE

async def handle_purchase_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text)
        context.user_data['purchase_price'] = price
        await update.message.reply_text("💵 Sotilish narxini kiriting ($):")
        return WAITING_SELLING_PRICE
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri format. Faqat son kiriting (masalan: 15.5):")
        return WAITING_PURCHASE_PRICE

async def handle_selling_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text)
        context.user_data['selling_price'] = price
        await update.message.reply_text("🔢 Soni (dona) ni kiriting:")
        return WAITING_QUANTITY
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri format. Faqat son kiriting:")
        return WAITING_SELLING_PRICE

async def handle_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        quantity = int(update.message.text)
        
        # Save product
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO products (
                name, category_id, photo_group_id, photo_message_id,
                photo_file_id, purchase_price_usd, selling_price_usd,
                quantity, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            context.user_data['product_name'],
            context.user_data['product_category'],
            context.user_data.get('photo_group_id'),
            context.user_data.get('photo_message_id'),
            context.user_data.get('photo_file_id'),
            context.user_data['purchase_price'],
            context.user_data['selling_price'],
            quantity,
            update.effective_user.id
        ))
        
        conn.commit()
        conn.close()
        
        # Clear user data
        keys = ['adding_product', 'product_name', 'product_category',
                'photo_group_id', 'photo_message_id', 'photo_file_id',
                'purchase_price', 'selling_price']
        for key in keys:
            context.user_data.pop(key, None)
        
        await update.message.reply_text("✅ Tovar muvaffaqiyatli qo'shildi!")
        
        if is_admin(update.effective_user.id):
            await show_admin_menu(update, context)
        else:
            await show_user_menu(update, context)
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri format. Butun son kiriting:")
        return WAITING_QUANTITY

async def send_request_to_admin(query, context, user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT username, full_name FROM pending_requests WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        username, full_name = user
        keyboard = [
            [
                InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_{user_id}"),
                InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{user_id}")
            ]
        ]
        
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🆕 Yangi ruxsat so'rovi!\n\n"
                 f"👤 Foydalanuvchi: @{username}\n"
                 f"📝 Ism: {full_name}\n"
                 f"🆔 ID: {user_id}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        await query.edit_message_text("✅ So'rovingiz yuborildi. Admin tasdiqlashini kuting.")

async def approve_user(query, context, data):
    user_id = int(data.split('_')[1])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT username, full_name FROM pending_requests WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if user:
        username, full_name = user
        cursor.execute('INSERT INTO users (user_id, username, full_name, added_by) VALUES (?, ?, ?, ?)',
                      (user_id, username, full_name, ADMIN_ID))
        cursor.execute('DELETE FROM pending_requests WHERE user_id = ?', (user_id,))
        conn.commit()
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ Ruxsatingiz tasdiqlandi! /start"
            )
        except:
            pass
        
        await query.edit_message_text(f"✅ @{username} tasdiqlandi!")
    
    conn.close()

async def reject_user(query, context, data):
    user_id = int(data.split('_')[1])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT username FROM pending_requests WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if user:
        username = user[0]
        cursor.execute('DELETE FROM pending_requests WHERE user_id = ?', (user_id,))
        conn.commit()
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ So'rovingiz rad etildi."
            )
        except:
            pass
        
        await query.edit_message_text(f"❌ @{username} rad etildi")
    
    conn.close()

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Xatolik: {context.error}")
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"❌ Xatolik yuz berdi: {str(context.error)[:200]}"
        )
    except:
        pass

# Main function
def main():
    init_database()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Category conversation
    category_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern="^add_category$|^add_subcat_")],
        states={
            WAITING_CATEGORY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category_name)]
        },
        fallbacks=[CommandHandler('cancel', lambda u,c: ConversationHandler.END)]
    )
    
    # Product conversation
    product_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(button_callback, pattern="^add_product_start$"),
            CallbackQueryHandler(button_callback, pattern="^add_product_")
        ],
        states={
            WAITING_PRODUCT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_product_name)],
            WAITING_PRODUCT_PHOTO: [
                MessageHandler(filters.PHOTO, handle_product_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_product_photo)
            ],
            WAITING_PURCHASE_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_purchase_price)],
            WAITING_SELLING_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_selling_price)],
            WAITING_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quantity)]
        },
        fallbacks=[CommandHandler('cancel', lambda u,c: ConversationHandler.END)]
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(category_conv)
    app.add_handler(product_conv)
    app.add_error_handler(error_handler)
    
    print("🤖 Bot ishga tushdi...")
    app.run_polling()

if __name__ == '__main__':
    main()
