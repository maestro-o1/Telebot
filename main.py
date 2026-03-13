import logging
import os
import json
import sqlite3
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import aiofiles
from PIL import Image
from io import BytesIO
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
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
CHANNEL_ID = int(os.getenv('CHANNEL_ID', '0'))

# States for conversation handlers
(
    WAITING_NAME, 
    WAITING_PHOTO, 
    WAITING_PURCHASE_PRICE, 
    WAITING_SELLING_PRICE,
    WAITING_QUANTITY,
    WAITING_CATEGORY,
    WAITING_SUBCATEGORY,
    WAITING_PRODUCT_ID,
    WAITING_USER_ID,
    WAITING_SEARCH,
    WAITING_EDIT_NAME,
    WAITING_EDIT_PURCHASE,
    WAITING_EDIT_SELLING,
    WAITING_EDIT_QUANTITY,
    WAITING_EDIT_CATEGORY,
    WAITING_EDIT_PHOTO,
    WAITING_IMPORT_FILE
) = range(17)

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
    
    # Users table (allowed users)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            added_by INTEGER,
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    # Pending requests table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_requests (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Categories table (with parent-child relationship)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parent_id INTEGER,
            level INTEGER DEFAULT 0,
            FOREIGN KEY (parent_id) REFERENCES categories (id)
        )
    ''')
    
    # Products table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category_id INTEGER,
            photo_channel_id INTEGER,
            photo_message_id INTEGER,
            photo_status TEXT DEFAULT 'active',
            photo_file_id TEXT,
            purchase_price_usd REAL NOT NULL,
            purchase_price_uzs REAL,
            selling_price_usd REAL NOT NULL,
            selling_price_uzs REAL,
            quantity INTEGER NOT NULL,
            total_purchase_usd REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,
            notes TEXT,
            FOREIGN KEY (category_id) REFERENCES categories (id)
        )
    ''')
    
    # Price history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            old_purchase_usd REAL,
            new_purchase_usd REAL,
            old_selling_usd REAL,
            new_selling_usd REAL,
            changed_by INTEGER,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')
    
    # Groups table (for photo storage)
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

# Helper functions
def get_db_connection():
    return sqlite3.connect('shop_database.db')

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def is_allowed(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE user_id = ? AND is_active = 1', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def usd_to_uzs(usd: float) -> int:
    # 1 USD = 13000 UZS (o'zgartirish mumkin)
    return int(usd * 13000)

def format_product_info(product: dict, include_edit_buttons: bool = False) -> Tuple[str, InlineKeyboardMarkup]:
    # Format product info
    text = f"📦 **{product['name']}**\n\n"
    
    # Category info
    if product.get('category_name'):
        text += f"📂 Kategoriya: {product['category_name']}\n"
    
    # Photo status
    if product['photo_status'] == 'deleted':
        text += "❌ Rasm topilmadi (kanaldan o'chirilgan)\n\n"
    elif product.get('photo_message_id'):
        text += "🖼 Rasm mavjud\n\n"
    else:
        text += "🖼 Rasm yo'q\n\n"
    
    # Prices
    text += f"💰 **Kelgan narxi:** {product['purchase_price_usd']}$ ({usd_to_uzs(product['purchase_price_usd']):,} so'm)\n"
    text += f"💵 **Sotilish narxi:** {product['selling_price_usd']}$ ({usd_to_uzs(product['selling_price_usd']):,} so'm)\n"
    text += f"📊 **Soni:** {product['quantity']} dona\n"
    text += f"💲 **Jami kelgan:** {product['purchase_price_usd'] * product['quantity']}$\n\n"
    
    # Additional info
    text += f"📅 Qo'shilgan: {product['created_at'][:10]}\n"
    if product.get('updated_at') != product.get('created_at'):
        text += f"✏️ Tahrirlangan: {product['updated_at'][:10]}\n"
    
    # Create keyboard
    keyboard = []
    
    # Back button always
    back_button = [InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_category")]
    
    if include_edit_buttons:
        # Edit buttons for admin
        edit_row1 = [
            InlineKeyboardButton("🖼 Rasm", callback_data=f"edit_photo_{product['id']}"),
            InlineKeyboardButton("📝 Nomi", callback_data=f"edit_name_{product['id']}")
        ]
        edit_row2 = [
            InlineKeyboardButton("💰 Kelgan", callback_data=f"edit_purchase_{product['id']}"),
            InlineKeyboardButton("💵 Sotilish", callback_data=f"edit_selling_{product['id']}")
        ]
        edit_row3 = [
            InlineKeyboardButton("🔢 Soni", callback_data=f"edit_quantity_{product['id']}"),
            InlineKeyboardButton("📂 Kategoriya", callback_data=f"edit_category_{product['id']}")
        ]
        delete_row = [InlineKeyboardButton("🗑 O'chirish", callback_data=f"delete_product_{product['id']}")]
        
        keyboard.extend([edit_row1, edit_row2, edit_row3, delete_row])
    else:
        # Only add photo upload button if photo is deleted and user is admin
        if product['photo_status'] == 'deleted' and include_edit_buttons:
            keyboard.append([InlineKeyboardButton("🔄 Yangi rasm yuklash", callback_data=f"upload_photo_{product['id']}")])
    
    keyboard.append(back_button)
    
    # Add home button
    keyboard.append([InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")])
    
    return text, InlineKeyboardMarkup(keyboard)

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or "No username"
    full_name = user.full_name
    
    # Check if this is in a group
    if update.effective_chat.type in ['group', 'supergroup']:
        chat_id = update.effective_chat.id
        chat_name = update.effective_chat.title
        
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
            f"🚀 Bot ishga tushdi!\n"
            f"✅ Guruh ID: {chat_id}\n"
            f"📦 Do'kon rasmlari shu yerda saqlanadi"
        )
        return
    
    # Check if user is admin
    if is_admin(user_id):
        await show_admin_menu(update, context)
        return
    
    # Check if user is allowed
    if is_allowed(user_id):
        await show_user_menu(update, context)
        return
    
    # New user - show request access
    await show_request_access(update, context, user_id, username, full_name)

async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔍 Qidirish", callback_data="search")],
        [InlineKeyboardButton("📦 Kategoriyalar", callback_data="categories")],
        [InlineKeyboardButton("📊 Statistika", callback_data="stats")],
        [InlineKeyboardButton("➕ Tovar qo'shish", callback_data="add_product")],
        [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="users")],
        [InlineKeyboardButton("📤 Eksport / Import", callback_data="export_import")]
    ]
    
    text = f"👋 Xush kelibsiz, Admin {update.effective_user.first_name}!\n\n"
    text += "🔽 Kerakli bo'limni tanlang:"
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_user_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔍 Qidirish", callback_data="search")],
        [InlineKeyboardButton("📦 Kategoriyalar", callback_data="categories")],
        [InlineKeyboardButton("📊 Statistika", callback_data="stats")]
    ]
    
    text = f"👋 Xush kelibsiz, {update.effective_user.first_name}!\n\n"
    text += "🔽 Kerakli bo'limni tanlang:"
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_request_access(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, username: str, full_name: str):
    # Check if already pending
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM pending_requests WHERE user_id = ?', (user_id,))
    pending = cursor.fetchone()
    
    if pending:
        await update.message.reply_text(
            "⏳ So'rovingiz allaqachon yuborilgan.\n"
            "Admin tasdiqlashini kuting."
        )
        conn.close()
        return
    
    # Save to pending requests
    cursor.execute('''
        INSERT INTO pending_requests (user_id, username, full_name)
        VALUES (?, ?, ?)
    ''', (user_id, username, full_name))
    conn.commit()
    conn.close()
    
    keyboard = [[InlineKeyboardButton("🟢 Ruxsat so'rash", callback_data=f"request_access_{user_id}")]]
    
    await update.message.reply_text(
        f"❌ Botdan foydalanish uchun ruxsat kerak.\n\n"
        f"Sizning ID raqamingiz: `{user_id}`\n"
        f"👤 @{username}\n\n"
        f"Ruxsat so'rash tugmasini bosing:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

# Callback query handler
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # Check permissions for all actions except request_access
    if not data.startswith('request_access'):
        if not is_admin(user_id) and not is_allowed(user_id):
            await query.edit_message_text("❌ Ruxsat yo'q")
            return
    
    # Handle different callback data
    if data == "main_menu":
        if is_admin(user_id):
            await show_admin_menu_callback(query)
        else:
            await show_user_menu_callback(query)
    
    elif data == "search":
        await start_search(query, context)
    
    elif data == "categories":
        await show_categories(query, context, parent_id=None)
    
    elif data == "stats":
        await show_statistics(query)
    
    elif data == "add_product" and is_admin(user_id):
        await start_add_product(query, context)
    
    elif data == "users" and is_admin(user_id):
        await show_users_menu(query)
    
    elif data == "export_import" and is_admin(user_id):
        await show_export_import_menu(query)
    
    elif data.startswith("request_access_"):
        await handle_request_access(query, context, data)
    
    elif data.startswith("approve_"):
        await approve_user(query, context, data)
    
    elif data.startswith("reject_"):
        await reject_user(query, context, data)
    
    elif data.startswith("category_"):
        await handle_category_click(query, context, data)
    
    elif data.startswith("product_"):
        await show_product(query, context, data)
    
    elif data == "back_to_categories":
        await show_categories(query, context, parent_id=None)
    
    elif data.startswith("back_to_subcategory_"):
        parent_id = int(data.split("_")[3])
        await show_categories(query, context, parent_id=parent_id)
    
    elif data == "export_data" and is_admin(user_id):
        await export_data(query, context)
    
    elif data == "import_data" and is_admin(user_id):
        await start_import(query, context)
    
    elif data == "clear_data" and is_admin(user_id):
        await show_clear_menu(query)
    
    elif data == "clear_all" and is_admin(user_id):
        await clear_all(query)
    
    elif data == "clear_products" and is_admin(user_id):
        await clear_products(query)
    
    elif data == "clear_users" and is_admin(user_id):
        await clear_users(query)

async def show_admin_menu_callback(query):
    keyboard = [
        [InlineKeyboardButton("🔍 Qidirish", callback_data="search")],
        [InlineKeyboardButton("📦 Kategoriyalar", callback_data="categories")],
        [InlineKeyboardButton("📊 Statistika", callback_data="stats")],
        [InlineKeyboardButton("➕ Tovar qo'shish", callback_data="add_product")],
        [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="users")],
        [InlineKeyboardButton("📤 Eksport / Import", callback_data="export_import")]
    ]
    
    await query.edit_message_text(
        f"👋 Xush kelibsiz, Admin!\n\n🔽 Kerakli bo'limni tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_user_menu_callback(query):
    keyboard = [
        [InlineKeyboardButton("🔍 Qidirish", callback_data="search")],
        [InlineKeyboardButton("📦 Kategoriyalar", callback_data="categories")],
        [InlineKeyboardButton("📊 Statistika", callback_data="stats")]
    ]
    
    await query.edit_message_text(
        "👋 Xush kelibsiz!\n\n🔽 Kerakli bo'limni tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_categories(query, context, parent_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if parent_id is None:
        # Get main categories
        cursor.execute('SELECT id, name FROM categories WHERE parent_id IS NULL ORDER BY name')
        categories = cursor.fetchall()
        title = "📦 Asosiy kategoriyalar:"
        back_button = None
    else:
        # Get subcategories
        cursor.execute('SELECT id, name FROM categories WHERE parent_id = ? ORDER BY name', (parent_id,))
        categories = cursor.fetchall()
        
        # Get parent name
        cursor.execute('SELECT name FROM categories WHERE id = ?', (parent_id,))
        parent = cursor.fetchone()
        title = f"📂 {parent[0]} ichidagi kategoriyalar:"
        back_button = [InlineKeyboardButton("⬅️ Orqaga", callback_data="categories")]
    
    keyboard = []
    for cat_id, cat_name in categories:
        # Check if this category has subcategories
        cursor.execute('SELECT COUNT(*) FROM categories WHERE parent_id = ?', (cat_id,))
        has_sub = cursor.fetchone()[0] > 0
        
        if has_sub:
            keyboard.append([InlineKeyboardButton(f"📁 {cat_name}", callback_data=f"category_{cat_id}")])
        else:
            # Check products in this category
            cursor.execute('SELECT COUNT(*) FROM products WHERE category_id = ?', (cat_id,))
            product_count = cursor.fetchone()[0]
            keyboard.append([InlineKeyboardButton(f"📦 {cat_name} ({product_count})", callback_data=f"category_products_{cat_id}")])
    
    if back_button:
        keyboard.append(back_button)
    
    keyboard.append([InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")])
    
    conn.close()
    
    await query.edit_message_text(
        title,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_category_click(query, context, data):
    parts = data.split('_')
    if len(parts) == 2:
        # Category with subcategories
        cat_id = int(parts[1])
        await show_categories(query, context, parent_id=cat_id)
    else:
        # Category with products
        cat_id = int(parts[2])
        await show_category_products(query, cat_id)

async def show_category_products(query, category_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get category name
    cursor.execute('SELECT name FROM categories WHERE id = ?', (category_id,))
    category_name = cursor.fetchone()[0]
    
    # Get products
    cursor.execute('''
        SELECT id, name, quantity, selling_price_usd 
        FROM products 
        WHERE category_id = ? 
        ORDER BY name
    ''', (category_id,))
    products = cursor.fetchall()
    
    keyboard = []
    for prod_id, prod_name, quantity, price in products:
        keyboard.append([
            InlineKeyboardButton(
                f"{prod_name} ({quantity} dona) - ${price}", 
                callback_data=f"product_{prod_id}"
            )
        ])
    
    # Add back button
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="categories")])
    keyboard.append([InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")])
    
    await query.edit_message_text(
        f"📦 {category_name} kategoriyasidagi tovarlar ({len(products)}):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    conn.close()

async def show_product(query, context, data):
    product_id = int(data.split('_')[1])
    user_id = query.from_user.id
    is_admin_user = is_admin(user_id)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT p.*, c.name as category_name 
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.id = ?
    ''', (product_id,))
    product_data = cursor.fetchone()
    conn.close()
    
    if not product_data:
        await query.edit_message_text("❌ Tovar topilmadi")
        return
    
    # Convert to dict for easier handling
    columns = ['id', 'name', 'category_id', 'photo_channel_id', 'photo_message_id', 
               'photo_status', 'photo_file_id', 'purchase_price_usd', 'purchase_price_uzs',
               'selling_price_usd', 'selling_price_uzs', 'quantity', 'total_purchase_usd',
               'created_at', 'updated_at', 'created_by', 'notes', 'category_name']
    
    product = dict(zip(columns, product_data))
    
    # Try to get photo if exists and active
    if product['photo_status'] == 'active' and product['photo_message_id'] and product['photo_channel_id']:
        try:
            # Forward photo from channel
            await context.bot.forward_message(
                chat_id=query.message.chat_id,
                from_chat_id=product['photo_channel_id'],
                message_id=product['photo_message_id']
            )
        except Exception as e:
            # Photo not found in channel
            logger.error(f"Error forwarding photo: {e}")
            product['photo_status'] = 'deleted'
            # Update database
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE products SET photo_status = ? WHERE id = ?', ('deleted', product_id))
            conn.commit()
            conn.close()
    
    text, keyboard = format_product_info(product, include_edit_buttons=is_admin_user)
    
    await query.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def show_statistics(query):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get total stats
    cursor.execute('''
        SELECT 
            COUNT(*) as total_products,
            SUM(quantity) as total_items,
            SUM(purchase_price_usd * quantity) as total_purchase,
            SUM(selling_price_usd * quantity) as total_selling,
            SUM((selling_price_usd - purchase_price_usd) * quantity) as total_profit
        FROM products
    ''')
    stats = cursor.fetchone()
    
    # Get category stats
    cursor.execute('''
        SELECT c.name, COUNT(p.id), SUM(p.quantity)
        FROM categories c
        LEFT JOIN products p ON c.id = p.category_id
        GROUP BY c.id
        ORDER BY c.name
    ''')
    category_stats = cursor.fetchall()
    
    # Get products without photos
    cursor.execute('SELECT COUNT(*) FROM products WHERE photo_status = "deleted"')
    no_photo_count = cursor.fetchone()[0]
    
    conn.close()
    
    text = "📊 **Umumiy hisobot**\n\n"
    text += f"📦 Jami tovarlar: {stats[0]} tur\n"
    text += f"🔢 Jami dona: {stats[1]} dona\n"
    text += f"💰 Kelgan: ${stats[2]:,.0f} ({usd_to_uzs(stats[2]):,} so'm)\n"
    text += f"💵 Sotilish: ${stats[3]:,.0f} ({usd_to_uzs(stats[3]):,} so'm)\n"
    text += f"📈 Kutilayotgan foyda: ${stats[4]:,.0f} ({usd_to_uzs(stats[4]):,} so'm)\n\n"
    
    text += "📂 **Kategoriyalar bo'yicha:**\n"
    for cat_name, count, items in category_stats:
        if count > 0:
            text += f"• {cat_name}: {count} tur ({items} dona)\n"
    
    if no_photo_count > 0:
        text += f"\n⚠️ Rasmsiz tovarlar: {no_photo_count} ta\n"
        keyboard = [[InlineKeyboardButton("📸 Rasmsiz tovarlar", callback_data="products_no_photo")]]
    else:
        keyboard = []
    
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")])
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def start_search(query, context):
    context.user_data['search_state'] = 'waiting'
    await query.edit_message_text(
        "🔍 Qidirish so'zini kiriting:\n\n"
        "Masalan: reduktor, propan, 50 litr"
    )

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'search_state' not in context.user_data:
        return
    
    search_text = update.message.text.lower()
    user_id = update.effective_user.id
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT p.id, p.name, c.name as category, p.quantity, p.selling_price_usd
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE LOWER(p.name) LIKE ? OR LOWER(c.name) LIKE ? OR LOWER(p.notes) LIKE ?
        ORDER BY p.name
    ''', (f'%{search_text}%', f'%{search_text}%', f'%{search_text}%'))
    
    results = cursor.fetchall()
    conn.close()
    
    if not results:
        await update.message.reply_text("❌ Hech narsa topilmadi")
        return
    
    keyboard = []
    for prod_id, prod_name, category, quantity, price in results:
        keyboard.append([
            InlineKeyboardButton(
                f"{prod_name} ({category}) - {quantity} dona - ${price}", 
                callback_data=f"product_{prod_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")])
    
    await update.message.reply_text(
        f"🔍 {len(results)} ta natija topildi:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    del context.user_data['search_state']

# Add product conversation
async def start_add_product(query, context):
    # Get categories for selection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name FROM categories WHERE parent_id IS NOT NULL ORDER BY name')
    subcategories = cursor.fetchall()
    conn.close()
    
    if not subcategories:
        await query.edit_message_text(
            "❌ Avval kategoriya yarating!\n"
            "Admin bilan bog'lanishingiz kerak."
        )
        return
    
    context.user_data['add_product'] = {'step': 'category'}
    
    keyboard = []
    for cat_id, cat_name in subcategories:
        keyboard.append([InlineKeyboardButton(cat_name, callback_data=f"select_cat_{cat_id}")])
    
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")])
    
    await query.edit_message_text(
        "📦 Tovar qaysi kategoriyaga tegishli?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return WAITING_CATEGORY

async def select_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    cat_id = int(query.data.split('_')[2])
    context.user_data['add_product']['category_id'] = cat_id
    context.user_data['add_product']['step'] = 'name'
    
    await query.edit_message_text(
        "📝 Tovar nomini kiriting:"
    )
    
    return WAITING_NAME

async def add_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data['add_product']['name'] = text
    context.user_data['add_product']['step'] = 'photo'
    
    await update.message.reply_text(
        "🖼 Rasm yuboring yoki 'skip' deb yozing:"
    )
    
    return WAITING_PHOTO

async def add_product_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if we have photo
    if update.message.photo:
        # Get the largest photo
        photo = update.message.photo[-1]
        photo_file = await photo.get_file()
        
        # Get channel ID (first active group)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT group_id FROM groups WHERE is_active = 1 LIMIT 1')
        group = cursor.fetchone()
        
        if not group:
            await update.message.reply_text("❌ Rasm saqlash uchun guruh topilmadi!")
            return WAITING_PHOTO
        
        channel_id = group[0]
        
        # Send photo to channel with hashtag
        timestamp = int(datetime.now().timestamp())
        hashtag = f"#product_{timestamp}"
        
        sent_message = await context.bot.send_photo(
            chat_id=channel_id,
            photo=photo_file.file_id,
            caption=hashtag
        )
        
        context.user_data['add_product']['photo_channel_id'] = channel_id
        context.user_data['add_product']['photo_message_id'] = sent_message.message_id
        context.user_data['add_product']['photo_status'] = 'active'
        context.user_data['add_product']['photo_file_id'] = photo_file.file_id
        
        conn.close()
        
        await update.message.reply_text("✅ Rasm saqlandi!")
    else:
        # No photo
        context.user_data['add_product']['photo_status'] = 'none'
        await update.message.reply_text("✅ Rasm saqlanmadi")
    
    context.user_data['add_product']['step'] = 'purchase_price'
    await update.message.reply_text("💰 Kelgan narxini kiriting ($):")
    
    return WAITING_PURCHASE_PRICE

async def add_product_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text)
        context.user_data['add_product']['purchase_price_usd'] = price
        context.user_data['add_product']['purchase_price_uzs'] = usd_to_uzs(price)
        context.user_data['add_product']['step'] = 'selling_price'
        
        await update.message.reply_text("💵 Sotilish narxini kiriting ($):")
        return WAITING_SELLING_PRICE
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri format. Faqat son kiriting (masalan: 15.5):")
        return WAITING_PURCHASE_PRICE

async def add_product_selling(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text)
        context.user_data['add_product']['selling_price_usd'] = price
        context.user_data['add_product']['selling_price_uzs'] = usd_to_uzs(price)
        context.user_data['add_product']['step'] = 'quantity'
        
        await update.message.reply_text("🔢 Soni (dona) ni kiriting:")
        return WAITING_QUANTITY
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri format. Faqat son kiriting (masalan: 10):")
        return WAITING_SELLING_PRICE

async def add_product_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        quantity = int(update.message.text)
        
        # Save all data
        data = context.user_data['add_product']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO products (
                name, category_id, photo_channel_id, photo_message_id, 
                photo_status, photo_file_id, purchase_price_usd, purchase_price_uzs,
                selling_price_usd, selling_price_uzs, quantity, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['name'], data['category_id'],
            data.get('photo_channel_id'), data.get('photo_message_id'),
            data.get('photo_status', 'none'), data.get('photo_file_id'),
            data['purchase_price_usd'], data['purchase_price_uzs'],
            data['selling_price_usd'], data['selling_price_uzs'],
            quantity, update.effective_user.id
        ))
        
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            f"✅ Tovar muvaffaqiyatli qo'shildi!\n\n"
            f"📦 Nomi: {data['name']}\n"
            f"💰 Kelgan: ${data['purchase_price_usd']}\n"
            f"💵 Sotilish: ${data['selling_price_usd']}\n"
            f"📊 Soni: {quantity} dona"
        )
        
        # Clear user data
        del context.user_data['add_product']
        
        # Show main menu
        if is_admin(update.effective_user.id):
            await show_admin_menu(update, context)
        else:
            await show_user_menu(update, context)
            
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri format. Butun son kiriting:")
        return WAITING_QUANTITY

# User management
async def show_users_menu(query):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get allowed users
    cursor.execute('SELECT user_id, username, full_name, added_date FROM users ORDER BY added_date DESC')
    users = cursor.fetchall()
    
    # Get pending requests
    cursor.execute('SELECT user_id, username, full_name, request_date FROM pending_requests ORDER BY request_date DESC')
    pending = cursor.fetchall()
    
    conn.close()
    
    text = "👥 **Foydalanuvchilarni boshqarish**\n\n"
    
    text += f"✅ **Ruxsat berilgan ({len(users)}):**\n"
    for user_id, username, full_name, added_date in users[:5]:  # Show first 5
        name = full_name or username or str(user_id)
        text += f"• {name} - `{user_id}`\n"
    if len(users) > 5:
        text += f"... va yana {len(users)-5} ta\n"
    
    text += f"\n⏳ **Kutayotgan so'rovlar ({len(pending)}):**\n"
    for user_id, username, full_name, req_date in pending[:3]:
        name = full_name or username or str(user_id)
        text += f"• {name} - `{user_id}`\n"
    
    keyboard = [
        [InlineKeyboardButton("📋 Barcha foydalanuvchilar", callback_data="list_users")],
        [InlineKeyboardButton("⏳ So'rovlar", callback_data="list_pending")],
        [InlineKeyboardButton("➕ Yangi qo'shish", callback_data="add_user")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_request_access(query, context, data):
    user_id = int(data.split('_')[2])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get user info from pending
    cursor.execute('SELECT username, full_name FROM pending_requests WHERE user_id = ?', (user_id,))
    user_info = cursor.fetchone()
    
    if not user_info:
        await query.edit_message_text("❌ So'rov topilmadi")
        conn.close()
        return
    
    username, full_name = user_info
    
    # Send notification to admin
    keyboard = [
        [
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{user_id}")
        ]
    ]
    
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🆕 **Yangi ruxsat so'rovi!**\n\n"
             f"👤 Foydalanuvchi: @{username}\n"
             f"📝 Ism: {full_name}\n"
             f"🆔 ID: `{user_id}`\n"
             f"📅 Sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    
    await query.edit_message_text(
        "✅ So'rovingiz yuborildi. Admin tasdiqlashini kuting."
    )
    
    conn.close()

async def approve_user(query, context, data):
    user_id = int(data.split('_')[1])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get user info from pending
    cursor.execute('SELECT username, full_name FROM pending_requests WHERE user_id = ?', (user_id,))
    user_info = cursor.fetchone()
    
    if user_info:
        username, full_name = user_info
        
        # Add to users table
        cursor.execute('''
            INSERT INTO users (user_id, username, full_name, added_by)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, full_name, ADMIN_ID))
        
        # Remove from pending
        cursor.execute('DELETE FROM pending_requests WHERE user_id = ?', (user_id,))
        
        conn.commit()
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ Ruxsatingiz tasdiqlandi!\n\nBotdan foydalanishingiz mumkin. /start"
            )
        except:
            pass
        
        await query.edit_message_text(
            f"✅ Foydalanuvchi @{username} tasdiqlandi!"
        )
    else:
        await query.edit_message_text("❌ So'rov topilmadi")
    
    conn.close()

async def reject_user(query, context, data):
    user_id = int(data.split('_')[1])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get user info
    cursor.execute('SELECT username FROM pending_requests WHERE user_id = ?', (user_id,))
    user_info = cursor.fetchone()
    
    # Remove from pending
    cursor.execute('DELETE FROM pending_requests WHERE user_id = ?', (user_id,))
    conn.commit()
    
    if user_info:
        username = user_info[0]
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ So'rovingiz rad etildi.\n\nAdmin bilan bog'lanishingiz mumkin."
            )
        except:
            pass
        
        await query.edit_message_text(f"❌ @{username} rad etildi")
    else:
        await query.edit_message_text("❌ So'rov topilmadi")
    
    conn.close()

# Export/Import functions
async def show_export_import_menu(query):
    keyboard = [
        [InlineKeyboardButton("📤 Eksport (JSON)", callback_data="export_data")],
        [InlineKeyboardButton("📥 Import (JSON)", callback_data="import_data")],
        [InlineKeyboardButton("🗑 Bazani tozalash", callback_data="clear_data")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        "📤 **Eksport / Import**\n\n"
        "Eksport: Barcha ma'lumotlarni JSON fayl sifatida yuklab olish\n"
        "Import: JSON fayl orqali ma'lumotlarni tiklash (eski ma'lumotlar o'chadi)",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def export_data(query, context):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Export categories
    cursor.execute('SELECT * FROM categories')
    categories = cursor.fetchall()
    
    # Export products
    cursor.execute('SELECT * FROM products')
    products = cursor.fetchall()
    
    # Export users
    cursor.execute('SELECT user_id, username, full_name, added_by, added_date FROM users')
    users = cursor.fetchall()
    
    conn.close()
    
    export_data = {
        'export_date': datetime.now().isoformat(),
        'bot_version': '1.0',
        'categories': categories,
        'products': products,
        'users': users
    }
    
    # Save to file
    filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    async with aiofiles.open(filename, 'w') as f:
        await f.write(json.dumps(export_data, indent=2, default=str))
    
    # Send file
    await context.bot.send_document(
        chat_id=query.message.chat_id,
        document=open(filename, 'rb'),
        filename=filename,
        caption="📤 Eksport fayli"
    )
    
    # Clean up
    os.remove(filename)
    
    await query.edit_message_text("✅ Eksport muvaffaqiyatli yuborildi!")

async def start_import(query, context):
    context.user_data['import_state'] = 'waiting'
    await query.edit_message_text(
        "📥 JSON faylni yuboring.\n\n"
        "⚠️ Ogohlantirish: Import qilganda barcha eski ma'lumotlar o'chib, faqat import qilingan ma'lumotlar qoladi!"
    )

async def handle_import_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'import_state' not in context.user_data:
        return
    
    document = update.message.document
    if not document.file_name.endswith('.json'):
        await update.message.reply_text("❌ Faqat JSON fayl yuboring!")
        return
    
    # Download file
    file = await document.get_file()
    filename = f"import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    await file.download_to_drive(filename)
    
    # Read and parse JSON
    try:
        async with aiofiles.open(filename, 'r') as f:
            content = await f.read()
            import_data = json.loads(content)
    except Exception as e:
        await update.message.reply_text(f"❌ Faylni o'qishda xatolik: {e}")
        os.remove(filename)
        return
    
    # Clear existing data
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM products')
    cursor.execute('DELETE FROM categories')
    cursor.execute('DELETE FROM users')
    cursor.execute('DELETE FROM pending_requests')
    cursor.execute('DELETE FROM price_history')
    
    # Import new data
    try:
        if 'categories' in import_data:
            for cat in import_data['categories']:
                cursor.execute('''
                    INSERT INTO categories (id, name, parent_id, level)
                    VALUES (?, ?, ?, ?)
                ''', cat[:4])
        
        if 'products' in import_data:
            for prod in import_data['products']:
                cursor.execute('''
                    INSERT INTO products (
                        id, name, category_id, photo_channel_id, photo_message_id,
                        photo_status, photo_file_id, purchase_price_usd, purchase_price_uzs,
                        selling_price_usd, selling_price_uzs, quantity, created_by,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', prod[:15])
        
        if 'users' in import_data:
            for user in import_data['users']:
                cursor.execute('''
                    INSERT INTO users (user_id, username, full_name, added_by, added_date)
                    VALUES (?, ?, ?, ?, ?)
                ''', user[:5])
        
        conn.commit()
        await update.message.reply_text(f"✅ Import muvaffaqiyatli yakunlandi!\n"
                                       f"📦 {len(import_data.get('products', []))} ta tovar, "
                                       f"📂 {len(import_data.get('categories', []))} ta kategoriya, "
                                       f"👥 {len(import_data.get('users', []))} ta foydalanuvchi")
    except Exception as e:
        conn.rollback()
        await update.message.reply_text(f"❌ Importda xatolik: {e}")
        logger.error(f"Import error: {e}")
    finally:
        conn.close()
        os.remove(filename)
        del context.user_data['import_state']

# Clear data functions
async def show_clear_menu(query):
    keyboard = [
        [InlineKeyboardButton("🗑 Hammasini tozalash", callback_data="clear_all")],
        [InlineKeyboardButton("📦 Faqat tovarlarni tozalash", callback_data="clear_products")],
        [InlineKeyboardButton("👥 Faqat foydalanuvchilarni tozalash", callback_data="clear_users")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="export_import")]
    ]
    
    await query.edit_message_text(
        "⚠️ **Ogohlantirish!** Bu amalni ortga qaytarib bo'lmaydi!\n\n"
        "Qaysi ma'lumotlarni tozalashni tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def clear_all(query):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM products')
    cursor.execute('DELETE FROM categories')
    cursor.execute('DELETE FROM users')
    cursor.execute('DELETE FROM pending_requests')
    cursor.execute('DELETE FROM price_history')
    
    conn.commit()
    conn.close()
    
    await query.edit_message_text("✅ Barcha ma'lumotlar tozalandi!")

async def clear_products(query):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM products')
    cursor.execute('DELETE FROM price_history')
    
    conn.commit()
    conn.close()
    
    await query.edit_message_text("✅ Barcha tovarlar tozalandi!")

async def clear_users(query):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM users')
    cursor.execute('DELETE FROM pending_requests')
    
    conn.commit()
    conn.close()
    
    await query.edit_message_text("✅ Barcha foydalanuvchilar tozalandi!")

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    
    # Send error to admin
    try:
        error_text = f"❌ Xatolik yuz berdi:\n```\n{traceback.format_exc()[:1000]}\n```"
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=error_text,
            parse_mode=ParseMode.MARKDOWN
        )
    except:
        pass

# Main function
def main():
    # Initialize database
    init_database()
    
    # Create default categories if not exist
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM categories')
    if cursor.fetchone()[0] == 0:
        # Insert main categories
        main_cats = ['Propan', 'Metan', 'Gaz balonlari']
        for cat in main_cats:
            cursor.execute('INSERT INTO categories (name, level) VALUES (?, 0)', (cat,))
            cat_id = cursor.lastrowid
            
            # Insert subcategories for Propan
            if cat == 'Propan':
                subcats = ['Reduktorlar', 'Shlanglar', 'Klapanlar', 'Boshqa propan qismlari']
                for sub in subcats:
                    cursor.execute('INSERT INTO categories (name, parent_id, level) VALUES (?, ?, 1)', (sub, cat_id))
            
            # Subcategories for Metan
            elif cat == 'Metan':
                subcats = ['Reduktorlar', 'Forunkalar', 'Elektronika', 'Boshqa metan qismlari']
                for sub in subcats:
                    cursor.execute('INSERT INTO categories (name, parent_id, level) VALUES (?, ?, 1)', (sub, cat_id))
            
            # Subcategories for Gaz balonlari
            elif cat == 'Gaz balonlari':
                subcats = ['50 litr', '80 litr', '100 litr', 'Boshqa hajmlar']
                for sub in subcats:
                    cursor.execute('INSERT INTO categories (name, parent_id, level) VALUES (?, ?, 1)', (sub, cat_id))
        
        conn.commit()
    conn.close()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler for adding product
    add_product_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_product, pattern="^add_product$")],
        states={
            WAITING_CATEGORY: [CallbackQueryHandler(select_category, pattern="^select_cat_")],
            WAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_name)],
            WAITING_PHOTO: [MessageHandler(filters.PHOTO, add_product_photo),
                           MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_photo)],
            WAITING_PURCHASE_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_purchase)],
            WAITING_SELLING_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_selling)],
            WAITING_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_quantity)],
        },
        fallbacks=[CommandHandler('cancel', lambda u,c: ConversationHandler.END)]
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(add_product_conv)
    
    # Search handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
    
    # Import file handler
    application.add_handler(MessageHandler(filters.Document.FileExtension("json"), handle_import_file))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Start bot
    print("🤖 Bot ishga tushdi...")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print(f"📸 Channel ID: {CHANNEL_ID}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
