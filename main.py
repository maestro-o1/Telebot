import logging
import os
import json
import sqlite3
from datetime import datetime
import traceback
import pytz

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
from dotenv import load_dotenv

load_dotenv()

# Bot configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))

# Toshkent vaqti
TASHKENT_TZ = pytz.timezone('Asia/Tashkent')

def get_tashkent_time():
    return datetime.now(TASHKENT_TZ)

def format_tashkent_time(dt=None):
    if dt is None:
        dt = get_tashkent_time()
    return dt.strftime('%d.%m.%Y %H:%M')

# States
(
    WAITING_CATEGORY_NAME,
    WAITING_PRODUCT_NAME,
    WAITING_PRODUCT_PHOTO,
    WAITING_PURCHASE_PRICE,
    WAITING_SELLING_PRICE,
    WAITING_QUANTITY,
    WAITING_SEARCH,
    WAITING_SUBCATEGORY_NAME,
    WAITING_CONFIRM_DELETE,
    WAITING_EDIT_NAME,
    WAITING_EDIT_PURCHASE,
    WAITING_EDIT_SELLING,
    WAITING_EDIT_QUANTITY,
    WAITING_USER_ID,
    WAITING_IMPORT_FILE
) = range(15)

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database functions
def get_db_connection():
    return sqlite3.connect('shop_database.db')

def init_database():
    conn = get_db_connection()
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
    
    # Pending requests table
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
            category_id INTEGER NOT NULL,
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
            FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()

# Helper functions
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

def usd_to_uzs(usd: float) -> int:
    return int(usd * 13000)

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or "No username"
    full_name = user.full_name
    
    current_time = format_tashkent_time()
    
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
            f"📦 Rasmlar shu guruhga saqlanadi\n"
            f"🕐 Toshkent vaqti: {current_time}"
        )
        return
    
    # Private chat
    if is_admin(user_id):
        await show_admin_menu(update, context, current_time)
    elif is_allowed(user_id):
        await show_user_menu(update, context, current_time)
    else:
        await show_request_access(update, context, user_id, username, full_name)

async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, current_time=None):
    if current_time is None:
        current_time = format_tashkent_time()
    
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
        f"👋 Xush kelibsiz, Admin!\n"
        f"🕐 {current_time}\n\n"
        f"Kerakli bo'limni tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_user_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, current_time=None):
    if current_time is None:
        current_time = format_tashkent_time()
    
    keyboard = [
        [InlineKeyboardButton("🔍 Qidirish", callback_data="search")],
        [InlineKeyboardButton("📂 Kategoriyalar", callback_data="view_categories")],
        [InlineKeyboardButton("📊 Statistika", callback_data="stats")]
    ]
    
    await update.message.reply_text(
        f"👋 Xush kelibsiz!\n"
        f"🕐 {current_time}\n\n"
        f"Kerakli bo'limni tanlang:",
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
        f"👤 @{username}\n\n"
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
        current_time = format_tashkent_time()
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
            await query.edit_message_text(
                f"👋 Admin menyusi\n🕐 {current_time}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            keyboard = [
                [InlineKeyboardButton("🔍 Qidirish", callback_data="search")],
                [InlineKeyboardButton("📂 Kategoriyalar", callback_data="view_categories")],
                [InlineKeyboardButton("📊 Statistika", callback_data="stats")]
            ]
            await query.edit_message_text(
                f"👋 Bosh menyu\n🕐 {current_time}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    # View categories
    elif data == "view_categories":
        await show_categories(query, context, None)
    
    # Add category
    elif data == "add_category" and is_admin(user_id):
        context.user_data['adding_category'] = True
        context.user_data['parent_category'] = None
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
        context.user_data['adding_category'] = True
        context.user_data['parent_category'] = parent_id
        await query.edit_message_text("➕ Yangi ichki kategoriya nomini kiriting:")
        return WAITING_CATEGORY_NAME
    
    # Add product to this category
    elif data.startswith("add_product_"):
        cat_id = int(data.split('_')[2])
        context.user_data['product_category'] = cat_id
        context.user_data['adding_product'] = True
        await query.edit_message_text("📝 Tovar nomini kiriting:")
        return WAITING_PRODUCT_NAME
    
    # Delete category
    elif data.startswith("delete_cat_"):
        cat_id = int(data.split('_')[2])
        await confirm_delete_category(query, context, cat_id)
    
    # Confirm delete category
    elif data.startswith("confirm_delete_"):
        cat_id = int(data.split('_')[2])
        await delete_category(query, cat_id)
    
    # Cancel delete
    elif data.startswith("cancel_delete_"):
        cat_id = int(data.split('_')[2])
        await show_categories(query, context, cat_id)
    
    # View product
    elif data.startswith("prod_"):
        prod_id = int(data.split('_')[1])
        await show_product(query, context, prod_id)
    
    # Edit product
    elif data.startswith("edit_name_"):
        prod_id = int(data.split('_')[2])
        context.user_data['editing_product'] = prod_id
        context.user_data['edit_field'] = 'name'
        await query.edit_message_text("✏️ Yangi nomni kiriting:")
        return WAITING_EDIT_NAME
    
    elif data.startswith("edit_purchase_"):
        prod_id = int(data.split('_')[2])
        context.user_data['editing_product'] = prod_id
        context.user_data['edit_field'] = 'purchase'
        await query.edit_message_text("💰 Yangi kelgan narxni kiriting ($):")
        return WAITING_EDIT_PURCHASE
    
    elif data.startswith("edit_selling_"):
        prod_id = int(data.split('_')[2])
        context.user_data['editing_product'] = prod_id
        context.user_data['edit_field'] = 'selling'
        await query.edit_message_text("💵 Yangi sotilish narxni kiriting ($):")
        return WAITING_EDIT_SELLING
    
    elif data.startswith("edit_quantity_"):
        prod_id = int(data.split('_')[2])
        context.user_data['editing_product'] = prod_id
        context.user_data['edit_field'] = 'quantity'
        await query.edit_message_text("🔢 Yangi sonini kiriting:")
        return WAITING_EDIT_QUANTITY
    
    elif data.startswith("edit_photo_"):
        prod_id = int(data.split('_')[2])
        context.user_data['editing_product'] = prod_id
        context.user_data['edit_field'] = 'photo'
        await query.edit_message_text("🖼 Yangi rasm yuboring:")
        return WAITING_PRODUCT_PHOTO
    
    elif data.startswith("delete_product_"):
        prod_id = int(data.split('_')[2])
        await confirm_delete_product(query, context, prod_id)
    
    elif data.startswith("confirm_delete_prod_"):
        prod_id = int(data.split('_')[3])
        await delete_product(query, prod_id)
    
    # Back to product
    elif data.startswith("back_to_product_"):
        prod_id = int(data.split('_')[3])
        await show_product(query, context, prod_id)
    
    # Search
    elif data == "search":
        context.user_data['searching'] = True
        await query.edit_message_text("🔍 Qidirish so'zini kiriting:")
        return WAITING_SEARCH
    
    # Statistics
    elif data == "stats":
        await show_statistics(query)
    
    # Users
    elif data == "users" and is_admin(user_id):
        await show_users_menu(query)
    
    # Export/Import
    elif data == "export_import" and is_admin(user_id):
        await show_export_import_menu(query)
    
    elif data == "export_data" and is_admin(user_id):
        await export_data(query, context)
    
    elif data == "import_data" and is_admin(user_id):
        context.user_data['importing'] = True
        await query.edit_message_text(
            "📥 JSON faylni yuboring.\n\n"
            "⚠️ Ogohlantirish: Import qilganda barcha eski ma'lumotlar o'chadi!"
        )
        return WAITING_IMPORT_FILE
    
    elif data == "clear_data" and is_admin(user_id):
        await show_clear_menu(query)
    
    elif data == "clear_all" and is_admin(user_id):
        await clear_all_data(query)
    
    elif data == "clear_products" and is_admin(user_id):
        await clear_products_data(query)
    
    elif data == "clear_users" and is_admin(user_id):
        await clear_users_data(query)
    
    # List pending requests
    elif data == "list_pending" and is_admin(user_id):
        await show_pending_requests(query)
    
    # List all users
    elif data == "list_users" and is_admin(user_id):
        await show_all_users(query)
    
    # Add user
    elif data == "add_user" and is_admin(user_id):
        context.user_data['adding_user'] = True
        await query.edit_message_text("👤 Foydalanuvchi ID sini kiriting:")
        return WAITING_USER_ID
    
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

# Category functions
async def show_categories(query, context, parent_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if parent_id:
        cursor.execute('SELECT name FROM categories WHERE id = ?', (parent_id,))
        parent = cursor.fetchone()
        if not parent:
            await query.edit_message_text("❌ Kategoriya topilmadi")
            conn.close()
            return
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
        back_parent = cursor.fetchone()
        if back_parent and back_parent[0]:
            keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data=f"cat_{back_parent[0]}")])
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

async def confirm_delete_category(query, context, cat_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT name FROM categories WHERE id = ?', (cat_id,))
    cat_name = cursor.fetchone()
    if not cat_name:
        await query.edit_message_text("❌ Kategoriya topilmadi")
        conn.close()
        return
    
    # Count subcategories
    cursor.execute('SELECT COUNT(*) FROM categories WHERE parent_id = ?', (cat_id,))
    sub_count = cursor.fetchone()[0]
    
    # Count products
    cursor.execute('SELECT COUNT(*) FROM products WHERE category_id = ?', (cat_id,))
    prod_count = cursor.fetchone()[0]
    
    conn.close()
    
    keyboard = [
        [InlineKeyboardButton("❌ Ha, o'chir", callback_data=f"confirm_delete_{cat_id}")],
        [InlineKeyboardButton("⬅️ Yo'q, orqaga", callback_data=f"cat_{cat_id}")]
    ]
    
    await query.edit_message_text(
        f"⚠️ **Ogohlantirish!**\n\n"
        f"Siz \"{cat_name[0]}\" kategoriyasini o'chirmoqchisiz.\n\n"
        f"Bu kategoriya ichida:\n"
        f"- {sub_count} ta ichki kategoriya\n"
        f"- {prod_count} ta tovar\n\n"
        f"**HAMMASI BIRGA O'CHADI!**\n\n"
        f"Haqiqatan ham o'chirmoqchimisiz?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def delete_category(query, cat_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get category name
    cursor.execute('SELECT name FROM categories WHERE id = ?', (cat_id,))
    cat_name = cursor.fetchone()
    
    # Delete category (cascade will delete subcategories and products)
    cursor.execute('DELETE FROM categories WHERE id = ?', (cat_id,))
    conn.commit()
    conn.close()
    
    await query.edit_message_text(f"✅ '{cat_name[0]}' kategoriyasi va uning barcha ichki kategoriyalari, tovarlari o'chirildi!")
    
    # Go back to parent
    await show_categories(query, None, None)

# Product functions
async def show_product(query, context, product_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT p.*, c.name as category_name, c.parent_id 
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.id = ?
    ''', (product_id,))
    
    product_data = cursor.fetchone()
    conn.close()
    
    if not product_data:
        await query.edit_message_text("❌ Tovar topilmadi")
        return
    
    # Get column names
    columns = ['id', 'name', 'category_id', 'photo_group_id', 'photo_message_id',
               'photo_file_id', 'purchase_price_usd', 'selling_price_usd', 'quantity',
               'created_at', 'updated_at', 'created_by', 'category_name', 'parent_id']
    
    product = dict(zip(columns, product_data))
    
    # Try to forward photo if exists
    if product['photo_group_id'] and product['photo_message_id']:
        try:
            await context.bot.forward_message(
                chat_id=query.message.chat_id,
                from_chat_id=product['photo_group_id'],
                message_id=product['photo_message_id']
            )
        except:
            pass
    
    text = f"📦 **{product['name']}**\n\n"
    text += f"📂 Kategoriya: {product['category_name']}\n\n"
    text += f"💰 Kelgan: ${product['purchase_price_usd']} ({usd_to_uzs(product['purchase_price_usd']):,} so'm)\n"
    text += f"💵 Sotilish: ${product['selling_price_usd']} ({usd_to_uzs(product['selling_price_usd']):,} so'm)\n"
    text += f"📊 Soni: {product['quantity']} dona\n"
    text += f"💲 Jami kelgan: ${product['purchase_price_usd'] * product['quantity']}\n\n"
    text += f"📅 Qo'shilgan: {product['created_at'][:10]}\n"
    
    # Keyboard for admin
    keyboard = []
    if is_admin(query.from_user.id):
        keyboard = [
            [
                InlineKeyboardButton("🖼 Rasm", callback_data=f"edit_photo_{product['id']}"),
                InlineKeyboardButton("📝 Nomi", callback_data=f"edit_name_{product['id']}")
            ],
            [
                InlineKeyboardButton("💰 Kelgan", callback_data=f"edit_purchase_{product['id']}"),
                InlineKeyboardButton("💵 Sotilish", callback_data=f"edit_selling_{product['id']}")
            ],
            [
                InlineKeyboardButton("🔢 Soni", callback_data=f"edit_quantity_{product['id']}")
            ],
            [InlineKeyboardButton("🗑 O'chirish", callback_data=f"delete_product_{product['id']}")]
        ]
    
    # Back button
    if product['parent_id']:
        back_data = f"cat_{product['parent_id']}"
    else:
        back_data = f"cat_{product['category_id']}"
    
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data=back_data)])
    
    await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def confirm_delete_product(query, context, product_id):
    context.user_data['delete_product'] = product_id
    keyboard = [
        [InlineKeyboardButton("❌ Ha, o'chir", callback_data=f"confirm_delete_prod_{product_id}")],
        [InlineKeyboardButton("⬅️ Yo'q, orqaga", callback_data=f"back_to_product_{product_id}")]
    ]
    await query.edit_message_text("⚠️ Tovarni o'chirishni tasdiqlaysizmi?", reply_markup=InlineKeyboardMarkup(keyboard))

async def delete_product(query, product_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
    conn.commit()
    conn.close()
    
    await query.edit_message_text("✅ Tovar o'chirildi!")

# Statistics
async def show_statistics(query):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Total stats
    cursor.execute('''
        SELECT 
            COUNT(*) as total_products,
            SUM(quantity) as total_items,
            SUM(purchase_price_usd * quantity) as total_purchase,
            SUM(selling_price_usd * quantity) as total_selling
        FROM products
    ''')
    stats = cursor.fetchone()
    
    # Category stats
    cursor.execute('''
        SELECT c.name, COUNT(p.id), SUM(p.quantity)
        FROM categories c
        LEFT JOIN products p ON c.id = p.category_id
        GROUP BY c.id
        ORDER BY c.name
    ''')
    category_stats = cursor.fetchall()
    
    conn.close()
    
    current_time = format_tashkent_time()
    
    text = f"📊 **Statistika** ({current_time})\n\n"
    text += f"📦 Jami tovarlar: {stats[0] or 0} tur\n"
    text += f"🔢 Jami dona: {stats[1] or 0} dona\n"
    text += f"💰 Kelgan: ${stats[2] or 0:,.0f}\n"
    text += f"💵 Sotilish: ${stats[3] or 0:,.0f}\n\n"
    
    text += "📂 **Kategoriyalar:**\n"
    for name, count, items in category_stats:
        if count > 0:
            text += f"• {name}: {count} tur ({items or 0} dona)\n"
    
    keyboard = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# Search
async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('searching'):
        return
    
    search_text = update.message.text.lower()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT p.id, p.name, c.name, p.quantity, p.selling_price_usd
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE LOWER(p.name) LIKE ? OR LOWER(c.name) LIKE ?
        ORDER BY p.name
    ''', (f'%{search_text}%', f'%{search_text}%'))
    
    results = cursor.fetchall()
    conn.close()
    
    context.user_data['searching'] = False
    
    if not results:
        await update.message.reply_text("❌ Hech narsa topilmadi")
        return
    
    keyboard = []
    for prod_id, prod_name, cat_name, qty, price in results:
        keyboard.append([
            InlineKeyboardButton(f"{prod_name} ({cat_name}) - {qty} dona", callback_data=f"prod_{prod_id}")
        ])
    
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")])
    
    await update.message.reply_text(
        f"🔍 {len(results)} ta natija topildi:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Category name handler
async def handle_category_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('adding_category'):
        return ConversationHandler.END
    
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
    
    current_time = format_tashkent_time()
    await update.message.reply_text(f"✅ '{category_name}' kategoriyasi qo'shildi! ({current_time})")
    
    # Show categories
    if parent_id:
        # Go to parent category
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT parent_id FROM categories WHERE id = ?', (parent_id,))
        result = cursor.fetchone()
        conn.close()
        
        # Create a fake query to show categories
        class FakeQuery:
            def __init__(self, user_id):
                self.from_user.id = user_id
                self.message.chat_id = update.effective_chat.id
                self.data = f"cat_{parent_id}"
        
        fake_query = type('obj', (object,), {
            'from_user': type('obj', (object,), {'id': update.effective_user.id})(),
            'message': type('obj', (object,), {'chat_id': update.effective_chat.id})(),
            'data': f"cat_{parent_id}",
            'edit_message_text': lambda text, reply_markup: None
        })
        
        await show_categories(fake_query, context, parent_id)
    else:
        # Show admin menu
        if is_admin(update.effective_user.id):
            await show_admin_menu(update, context, current_time)
    
    return ConversationHandler.END

# Product name handler
async def handle_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('adding_product'):
        return ConversationHandler.END
    
    context.user_data['product_name'] = update.message.text
    
    await update.message.reply_text(
        "🖼 Rasm yuboring yoki 'skip' deb yozing:"
    )
    return WAITING_PRODUCT_PHOTO

# Product photo handler
async def handle_product_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('adding_product'):
        return ConversationHandler.END
    
    # Check if editing existing product
    editing_product_id = context.user_data.get('editing_product')
    
    if update.message.photo:
        # Check if group exists
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT group_id FROM groups WHERE is_active = 1 LIMIT 1')
        group = cursor.fetchone()
        conn.close()
        
        if not group:
            await update.message.reply_text(
                "❌ Rasm saqlash uchun guruh topilmadi!\n\n"
                "1. Guruh yarating\n"
                "2. Botni admin qiling\n"
                "3. Guruhda /start yozing"
            )
            return WAITING_PRODUCT_PHOTO
        
        group_id = group[0]
        
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
            product_name = context.user_data.get('product_name', 'product')
            sent = await context.bot.send_photo(
                chat_id=group_id,
                photo=photo.file_id,
                caption=f"#{product_name.replace(' ', '_')}"
            )
            
            context.user_data['photo_group_id'] = group_id
            context.user_data['photo_message_id'] = sent.message_id
            context.user_data['photo_file_id'] = photo.file_id
            
            await update.message.reply_text("✅ Rasm saqlandi!")
            
        except Exception as e:
            await update.message.reply_text("❌ Rasm saqlashda xatolik!")
            return WAITING_PRODUCT_PHOTO
    else:
        # Skip photo
        context.user_data['photo_group_id'] = None
        context.user_data['photo_message_id'] = None
        context.user_data['photo_file_id'] = None
        await update.message.reply_text("✅ Rasmsiz davom etamiz")
    
    if editing_product_id:
        # Update existing product
        await update_product_photo(update, context, editing_product_id)
        return ConversationHandler.END
    else:
        # New product - ask for price
        await update.message.reply_text("💰 Kelgan narxini kiriting ($):")
        return WAITING_PURCHASE_PRICE

# Purchase price handler
async def handle_purchase_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text)
        context.user_data['purchase_price'] = price
        await update.message.reply_text("💵 Sotilish narxini kiriting ($):")
        return WAITING_SELLING_PRICE
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri format. Faqat son kiriting (masalan: 15.5):")
        return WAITING_PURCHASE_PRICE

# Selling price handler
async def handle_selling_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text)
        context.user_data['selling_price'] = price
        await update.message.reply_text("🔢 Soni (dona) ni kiriting:")
        return WAITING_QUANTITY
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri format. Faqat son kiriting:")
        return WAITING_SELLING_PRICE

# Quantity handler
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
        
        current_time = format_tashkent_time()
        await update.message.reply_text(f"✅ Tovar muvaffaqiyatli qo'shildi! ({current_time})")
        
        if is_admin(update.effective_user.id):
            await show_admin_menu(update, context, current_time)
        else:
            await show_user_menu(update, context, current_time)
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri format. Butun son kiriting:")
        return WAITING_QUANTITY

# Edit handlers
async def handle_edit_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    product_id = context.user_data.get('editing_product')
    if not product_id:
        return ConversationHandler.END
    
    new_name = update.message.text
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE products SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                  (new_name, product_id))
    conn.commit()
    conn.close()
    
    context.user_data.pop('editing_product', None)
    
    await update.message.reply_text(f"✅ Nomi o'zgartirildi: {new_name}")
    
    # Show product
    class FakeQuery:
        def __init__(self, user_id, chat_id):
            self.from_user = type('obj', (object,), {'id': user_id})()
            self.message = type('obj', (object,), {'chat_id': chat_id})()
            self.data = f"prod_{product_id}"
    
    fake_query = FakeQuery(update.effective_user.id, update.effective_chat.id)
    await show_product(fake_query, context, product_id)
    
    return ConversationHandler.END

async def handle_edit_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    product_id = context.user_data.get('editing_product')
    if not product_id:
        return ConversationHandler.END
    
    try:
        new_price = float(update.message.text)
        
        # Get old price
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT purchase_price_usd FROM products WHERE id = ?', (product_id,))
        old_price = cursor.fetchone()[0]
        
        # Update
        cursor.execute('UPDATE products SET purchase_price_usd = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                      (new_price, product_id))
        
        # Save to history
        cursor.execute('''
            INSERT INTO price_history (product_id, old_purchase_usd, new_purchase_usd, changed_by)
            VALUES (?, ?, ?, ?)
        ''', (product_id, old_price, new_price, update.effective_user.id))
        
        conn.commit()
        conn.close()
        
        context.user_data.pop('editing_product', None)
        
        await update.message.reply_text(f"✅ Kelgan narx o'zgartirildi: ${old_price} → ${new_price}")
        
        # Show product
        class FakeQuery:
            def __init__(self, user_id, chat_id):
                self.from_user = type('obj', (object,), {'id': user_id})()
                self.message = type('obj', (object,), {'chat_id': chat_id})()
                self.data = f"prod_{product_id}"
        
        fake_query = FakeQuery(update.effective_user.id, update.effective_chat.id)
        await show_product(fake_query, context, product_id)
        
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri format. Qaytadan kiriting:")
        return WAITING_EDIT_PURCHASE
    
    return ConversationHandler.END

async def handle_edit_selling(update: Update, context: ContextTypes.DEFAULT_TYPE):
    product_id = context.user_data.get('editing_product')
    if not product_id:
        return ConversationHandler.END
    
    try:
        new_price = float(update.message.text)
        
        # Get old price
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT selling_price_usd FROM products WHERE id = ?', (product_id,))
        old_price = cursor.fetchone()[0]
        
        # Update
        cursor.execute('UPDATE products SET selling_price_usd = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                      (new_price, product_id))
        
        # Save to history
        cursor.execute('''
            INSERT INTO price_history (product_id, old_selling_usd, new_selling_usd, changed_by)
            VALUES (?, ?, ?, ?)
        ''', (product_id, old_price, new_price, update.effective_user.id))
        
        conn.commit()
        conn.close()
        
        context.user_data.pop('editing_product', None)
        
        await update.message.reply_text(f"✅ Sotilish narxi o'zgartirildi: ${old_price} → ${new_price}")
        
        # Show product
        class FakeQuery:
            def __init__(self, user_id, chat_id):
                self.from_user = type('obj', (object,), {'id': user_id})()
                self.message = type('obj', (object,), {'chat_id': chat_id})()
                self.data = f"prod_{product_id}"
        
        fake_query = FakeQuery(update.effective_user.id, update.effective_chat.id)
        await show_product(fake_query, context, product_id)
        
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri format. Qaytadan kiriting:")
        return WAITING_EDIT_SELLING
    
    return ConversationHandler.END

async def handle_edit_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    product_id = context.user_data.get('editing_product')
    if not product_id:
        return ConversationHandler.END
    
    try:
        new_quantity = int(update.message.text)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE products SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                      (new_quantity, product_id))
        conn.commit()
        conn.close()
        
        context.user_data.pop('editing_product', None)
        
        await update.message.reply_text(f"✅ Soni o'zgartirildi: {new_quantity} dona")
        
        # Show product
        class FakeQuery:
            def __init__(self, user_id, chat_id):
                self.from_user = type('obj', (object,), {'id': user_id})()
                self.message = type('obj', (object,), {'chat_id': chat_id})()
                self.data = f"prod_{product_id}"
        
        fake_query = FakeQuery(update.effective_user.id, update.effective_chat.id)
        await show_product(fake_query, context, product_id)
        
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri format. Butun son kiriting:")
        return WAITING_EDIT_QUANTITY
    
    return ConversationHandler.END

async def update_product_photo(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE products 
        SET photo_group_id = ?, photo_message_id = ?, photo_file_id = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (
        context.user_data.get('photo_group_id'),
        context.user_data.get('photo_message_id'),
        context.user_data.get('photo_file_id'),
        product_id
    ))
    conn.commit()
    conn.close()
    
    context.user_data.pop('editing_product', None)
    
    await update.message.reply_text("✅ Rasm yangilandi!")
    
    # Show product
    class FakeQuery:
        def __init__(self, user_id, chat_id):
            self.from_user = type('obj', (object,), {'id': user_id})()
            self.message = type('obj', (object,), {'chat_id': chat_id})()
            self.data = f"prod_{product_id}"
    
    fake_query = FakeQuery(update.effective_user.id, update.effective_chat.id)
    await show_product(fake_query, context, product_id)

# User management functions
async def show_users_menu(query):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    users_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM pending_requests')
    pending_count = cursor.fetchone()[0]
    
    conn.close()
    
    keyboard = [
        [InlineKeyboardButton(f"📋 Barcha foydalanuvchilar ({users_count})", callback_data="list_users")],
        [InlineKeyboardButton(f"⏳ So'rovlar ({pending_count})", callback_data="list_pending")],
        [InlineKeyboardButton("➕ Yangi qo'shish", callback_data="add_user")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        "👥 **Foydalanuvchilarni boshqarish**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def show_pending_requests(query):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, full_name, request_date FROM pending_requests ORDER BY request_date DESC')
    pending = cursor.fetchall()
    conn.close()
    
    if not pending:
        await query.edit_message_text("⏳ Kutayotgan so'rovlar yo'q")
        return
    
    text = "⏳ **Kutayotgan so'rovlar:**\n\n"
    for user_id, username, full_name, req_date in pending:
        text += f"• {full_name} (@{username})\n"
        text += f"  ID: `{user_id}`\n"
        text += f"  Sana: {req_date[:16]}\n\n"
    
    keyboard = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="users")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def show_all_users(query):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, full_name, added_date FROM users ORDER BY added_date DESC')
    users = cursor.fetchall()
    conn.close()
    
    if not users:
        await query.edit_message_text("👥 Foydalanuvchilar yo'q")
        return
    
    text = "👥 **Barcha foydalanuvchilar:**\n\n"
    for user_id, username, full_name, added_date in users[:10]:
        text += f"• {full_name} (@{username})\n"
        text += f"  ID: `{user_id}`\n"
        text += f"  Qo'shilgan: {added_date[:16]}\n\n"
    
    if len(users) > 10:
        text += f"... va yana {len(users) - 10} ta"
    
    keyboard = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="users")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def handle_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('adding_user'):
        return ConversationHandler.END
    
    try:
        user_id = int(update.message.text)
        
        # Check if user exists
        try:
            chat = await context.bot.get_chat(user_id)
            username = chat.username or "No username"
            full_name = chat.full_name or "No name"
        except:
            await update.message.reply_text("❌ Foydalanuvchi topilmadi. ID ni tekshiring.")
            return WAITING_USER_ID
        
        # Add to users
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (user_id, username, full_name, added_by) VALUES (?, ?, ?, ?)',
                      (user_id, username, full_name, ADMIN_ID))
        conn.commit()
        conn.close()
        
        context.user_data['adding_user'] = False
        
        await update.message.reply_text(f"✅ {full_name} (@{username}) qo'shildi!")
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ Sizga botdan foydalanish ruxsati berildi! /start"
            )
        except:
            pass
        
        if is_admin(update.effective_user.id):
            await show_admin_menu(update, context, format_tashkent_time())
        
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri format. ID raqam kiriting:")
        return WAITING_USER_ID
    
    return ConversationHandler.END

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
            text=f"🆕 **Yangi ruxsat so'rovi!**\n\n"
                 f"👤 Foydalanuvchi: @{username}\n"
                 f"📝 Ism: {full_name}\n"
                 f"🆔 ID: {user_id}\n"
                 f"🕐 {format_tashkent_time()}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
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
    else:
        await query.edit_message_text("❌ So'rov topilmadi")
    
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
    
    # Export pending requests
    cursor.execute('SELECT * FROM pending_requests')
    pending = cursor.fetchall()
    
    conn.close()
    
    export_data = {
        'export_date': format_tashkent_time(),
        'bot_version': '1.0',
        'categories': categories,
        'products': products,
        'users': users,
        'pending_requests': pending
    }
    
    # Save to file
    filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, default=str, ensure_ascii=False)
    
    # Send file
    await context.bot.send_document(
        chat_id=query.message.chat_id,
        document=open(filename, 'rb'),
        filename=filename,
        caption=f"📤 Eksport fayli ({format_tashkent_time()})"
    )
    
    # Clean up
    os.remove(filename)
    
    await query.edit_message_text("✅ Eksport muvaffaqiyatli yuborildi!")

async def handle_import_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('importing'):
        return ConversationHandler.END
    
    document = update.message.document
    if not document.file_name.endswith('.json'):
        await update.message.reply_text("❌ Faqat JSON fayl yuboring!")
        return WAITING_IMPORT_FILE
    
    # Download file
    file = await document.get_file()
    filename = f"import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    await file.download_to_drive(filename)
    
    # Read and parse JSON
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            import_data = json.load(f)
    except Exception as e:
        await update.message.reply_text(f"❌ Faylni o'qishda xatolik: {e}")
        os.remove(filename)
        return WAITING_IMPORT_FILE
    
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
                    INSERT INTO categories (id, name, parent_id, created_at)
                    VALUES (?, ?, ?, ?)
                ''', cat[:4])
        
        if 'products' in import_data:
            for prod in import_data['products']:
                cursor.execute('''
                    INSERT INTO products (
                        id, name, category_id, photo_group_id, photo_message_id,
                        photo_file_id, purchase_price_usd, selling_price_usd, quantity,
                        created_at, updated_at, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', prod[:12])
        
        if 'users' in import_data:
            for user in import_data['users']:
                cursor.execute('''
                    INSERT INTO users (user_id, username, full_name, added_by, added_date)
                    VALUES (?, ?, ?, ?, ?)
                ''', user[:5])
        
        if 'pending_requests' in import_data:
            for req in import_data['pending_requests']:
                cursor.execute('''
                    INSERT INTO pending_requests (user_id, username, full_name, request_date)
                    VALUES (?, ?, ?, ?)
                ''', req[:4])
        
        conn.commit()
        
        context.user_data['importing'] = False
        
        await update.message.reply_text(
            f"✅ Import muvaffaqiyatli yakunlandi!\n"
            f"📦 {len(import_data.get('products', []))} ta tovar\n"
            f"📂 {len(import_data.get('categories', []))} ta kategoriya\n"
            f"👥 {len(import_data.get('users', []))} ta foydalanuvchi\n"
            f"🕐 {format_tashkent_time()}"
        )
        
        if is_admin(update.effective_user.id):
            await show_admin_menu(update, context, format_tashkent_time())
        
    except Exception as e:
        conn.rollback()
        await update.message.reply_text(f"❌ Importda xatolik: {e}")
        logger.error(f"Import error: {e}")
    finally:
        conn.close()
        os.remove(filename)
    
    return ConversationHandler.END

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

async def clear_all_data(query):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM products')
    cursor.execute('DELETE FROM categories')
    cursor.execute('DELETE FROM users')
    cursor.execute('DELETE FROM pending_requests')
    cursor.execute('DELETE FROM price_history')
    
    conn.commit()
    conn.close()
    
    await query.edit_message_text(f"✅ Barcha ma'lumotlar tozalandi! ({format_tashkent_time()})")

async def clear_products_data(query):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM products')
    cursor.execute('DELETE FROM price_history')
    
    conn.commit()
    conn.close()
    
    await query.edit_message_text(f"✅ Barcha tovarlar tozalandi! ({format_tashkent_time()})")

async def clear_users_data(query):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM users')
    cursor.execute('DELETE FROM pending_requests')
    
    conn.commit()
    conn.close()
    
    await query.edit_message_text(f"✅ Barcha foydalanuvchilar tozalandi! ({format_tashkent_time()})")

# Cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Bekor qilindi")
    
    if is_admin(update.effective_user.id):
        await show_admin_menu(update, context, format_tashkent_time())
    else:
        await show_user_menu(update, context, format_tashkent_time())
    
    return ConversationHandler.END

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Xatolik: {context.error}")
    try:
        error_msg = str(context.error)[:200]
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"❌ Xatolik yuz berdi ({format_tashkent_time()}):\n{error_msg}"
        )
    except:
        pass

# Main function
def main():
    # Initialize database
    init_database()
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Category conversation
    category_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern="^add_category$|^add_subcat_")],
        states={
            WAITING_CATEGORY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category_name)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Product conversation (add)
    product_add_conv = ConversationHandler(
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
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Edit conversations
    edit_name_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern="^edit_name_")],
        states={
            WAITING_EDIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_name)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    edit_purchase_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern="^edit_purchase_")],
        states={
            WAITING_EDIT_PURCHASE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_purchase)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    edit_selling_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern="^edit_selling_")],
        states={
            WAITING_EDIT_SELLING: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_selling)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    edit_quantity_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern="^edit_quantity_")],
        states={
            WAITING_EDIT_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_quantity)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    edit_photo_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern="^edit_photo_")],
        states={
            WAITING_PRODUCT_PHOTO: [
                MessageHandler(filters.PHOTO, handle_product_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_product_photo)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Search conversation
    search_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern="^search$")],
        states={
            WAITING_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Add user conversation
    add_user_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern="^add_user$")],
        states={
            WAITING_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_id)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Import conversation
    import_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern="^import_data$")],
        states={
            WAITING_IMPORT_FILE: [MessageHandler(filters.Document.FileExtension("json"), handle_import_file)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(category_conv)
    app.add_handler(product_add_conv)
    app.add_handler(edit_name_conv)
    app.add_handler(edit_purchase_conv)
    app.add_handler(edit_selling_conv)
    app.add_handler(edit_quantity_conv)
    app.add_handler(edit_photo_conv)
    app.add_handler(search_conv)
    app.add_handler(add_user_conv)
    app.add_handler(import_conv)
    app.add_error_handler(error_handler)
    
    print("🤖 Bot ishga tushdi...")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print(f"🕐 Toshkent vaqti: {format_tashkent_time()}")
    app.run_polling()

if __name__ == '__main__':
    main()
