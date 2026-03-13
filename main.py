#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Do'kon boshqaruvi uchun Telegram bot
Muallif: @maestro_o
Versiya: 2.0
"""

import logging
import os
import sys
from datetime import datetime, timedelta
import pandas as pd
import shutil
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler, 
    MessageHandler, 
    filters,
    ContextTypes,
    ConversationHandler
)

# Logging sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Toshkent vaqti uchun timezone
TASHKENT_TZ = pytz.timezone('Asia/Tashkent')

# ==================== KONFIGURATSIYA ====================
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
MEDIA_CHANNEL_ID = int(os.getenv('MEDIA_CHANNEL_ID', 0))  # Bu endi guruh ID si bo'ladi

# ==================== MA'LUMOTLAR BAZASI ====================
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session

engine = create_engine('sqlite:///data/shop_bot.db', connect_args={'check_same_thread': False})
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)
    is_authorized = Column(Boolean, default=False)
    can_edit = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)

class AccessRequest(Base):
    __tablename__ = 'access_requests'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    status = Column(String, default='pending')
    created_at = Column(DateTime, default=datetime.now)

class Category(Base):
    __tablename__ = 'categories'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    parent_id = Column(Integer, ForeignKey('categories.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.now)

class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    description = Column(Text, nullable=True)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=True)
    purchase_price_usd = Column(Float, default=0)
    purchase_price_uzs = Column(Float, default=0)
    selling_price_usd = Column(Float, default=0)
    selling_price_uzs = Column(Float, default=0)
    quantity = Column(Integer, default=0)
    media_group_message_id = Column(Integer, nullable=True)  # Guruhdagi xabar ID si
    media_file_id = Column(String, nullable=True)
    keywords = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class PriceHistory(Base):
    __tablename__ = 'price_history'
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'))
    old_purchase_usd = Column(Float)
    old_purchase_uzs = Column(Float)
    old_selling_usd = Column(Float)
    old_selling_uzs = Column(Float)
    old_quantity = Column(Integer)
    new_purchase_usd = Column(Float)
    new_purchase_uzs = Column(Float)
    new_selling_usd = Column(Float)
    new_selling_uzs = Column(Float)
    new_quantity = Column(Integer)
    changed_at = Column(DateTime, default=datetime.now)
    changed_by = Column(Integer)

class BotGroup(Base):
    __tablename__ = 'bot_groups'
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, unique=True)
    group_name = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)

# ==================== BAZA FUNKSIYALARI ====================

def init_db():
    """Ma'lumotlar bazasini ishga tushirish"""
    try:
        os.makedirs('data', exist_ok=True)
        Base.metadata.create_all(bind=engine)
        
        session = db_session()
        admin = session.query(User).filter_by(telegram_id=ADMIN_ID).first()
        if not admin and ADMIN_ID != 0:
            admin = User(
                telegram_id=ADMIN_ID,
                username='admin',
                first_name='Admin',
                is_admin=True,
                is_authorized=True,
                can_edit=True
            )
            session.add(admin)
            session.commit()
        session.close()
        logger.info("✅ Ma'lumotlar bazasi muvaffaqiyatli yaratildi")
    except Exception as e:
        logger.error(f"❌ Ma'lumotlar bazasini yaratishda xatolik: {e}")
        raise e

def backup_database():
    """Ma'lumotlar bazasini backup qilish"""
    backup_name = f"data/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2('data/shop_bot.db', backup_name)
    return backup_name

def restore_database(backup_file):
    """Backupdan tiklash"""
    shutil.copy2(backup_file, 'data/shop_bot.db')
    return True

def get_tashkent_time():
    """Toshkent vaqtini qaytarish"""
    return datetime.now(TASHKENT_TZ)

# ==================== KEYBOARDS ====================

def get_main_keyboard(user_is_admin=False, user_can_edit=False):
    """Asosiy menyu tugmalari"""
    buttons = [
        [InlineKeyboardButton("🔍 Qidirish", callback_data="search")],
        [InlineKeyboardButton("📂 Kategoriyalar", callback_data="categories")],
    ]
    
    if user_is_admin:
        buttons.extend([
            [InlineKeyboardButton("📊 Statistika", callback_data="stats")],
            [InlineKeyboardButton("➕ Tovar qo'shish", callback_data="add_product")],
            [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="users")],
            [InlineKeyboardButton("📥 Eksport / 📤 Import", callback_data="export_import")],
            [InlineKeyboardButton("👤 Ruxsat berish", callback_data="grant_access")],
            [InlineKeyboardButton("👥 Guruhlar", callback_data="groups")],
        ])
    elif user_can_edit:
        buttons.extend([
            [InlineKeyboardButton("📊 Statistika", callback_data="stats")],
            [InlineKeyboardButton("📥 Eksport", callback_data="export_only")],
        ])
    
    return InlineKeyboardMarkup(buttons)

def get_back_button(callback_data="main_menu"):
    """Orqaga tugmasi"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Orqaga", callback_data=callback_data)]
    ])

def get_cancel_button():
    """Bekor qilish tugmasi"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel")]
    ])

def get_categories_keyboard(categories, parent_id=None, is_admin=False):
    """Kategoriyalar ro'yxati"""
    buttons = []
    
    # Kategoriyalar
    for cat in categories:
        buttons.append([
            InlineKeyboardButton(f"📁 {cat['name']}", callback_data=f"cat_{cat['id']}")
        ])
    
    # Admin uchun tugmalar
    if is_admin:
        if parent_id is not None:
            buttons.append([
                InlineKeyboardButton("➕ Kategoriya qo'shish", callback_data=f"add_cat_{parent_id}")
            ])
            buttons.append([
                InlineKeyboardButton("➕ Tovar qo'shish", callback_data=f"add_product_cat_{parent_id}")
            ])
    
    buttons.append([InlineKeyboardButton("🔙 Bosh menyu", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)

def get_product_actions_keyboard(product_id, is_admin=False):
    """Tovar amallari"""
    buttons = [
        [InlineKeyboardButton("📝 Tahrirlash", callback_data=f"edit_{product_id}")],
    ]
    
    if is_admin:
        buttons.append([InlineKeyboardButton("🗑 O'chirish", callback_data=f"delete_{product_id}")])
    
    buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data="categories")])
    return InlineKeyboardMarkup(buttons)

def get_edit_product_keyboard(product_id):
    """Tahrirlash menyusi"""
    buttons = [
        [InlineKeyboardButton("🖼 Rasm", callback_data=f"edit_photo_{product_id}")],
        [InlineKeyboardButton("📝 Nomi", callback_data=f"edit_name_{product_id}")],
        [InlineKeyboardButton("💰 Kelgan narxi", callback_data=f"edit_purchase_{product_id}")],
        [InlineKeyboardButton("💵 Sotilish narxi", callback_data=f"edit_selling_{product_id}")],
        [InlineKeyboardButton("📦 Soni", callback_data=f"edit_quantity_{product_id}")],
        [InlineKeyboardButton("🔑 Kalit so'zlar", callback_data=f"edit_keywords_{product_id}")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data=f"view_{product_id}")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_price_type_keyboard(product_id, price_type):
    """Narx turini tanlash (USD yoki UZS)"""
    buttons = [
        [InlineKeyboardButton("💵 USD ($)", callback_data=f"set_{price_type}_usd_{product_id}")],
        [InlineKeyboardButton("💰 UZS (so'm)", callback_data=f"set_{price_type}_uzs_{product_id}")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data=f"edit_{product_id}")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_export_import_keyboard():
    """Eksport/Import menyusi"""
    buttons = [
        [InlineKeyboardButton("📤 Eksport (Excel)", callback_data="export_excel")],
        [InlineKeyboardButton("📥 Import (Excel)", callback_data="import_excel")],
        [InlineKeyboardButton("💾 Backup yuklab olish", callback_data="download_backup")],
        [InlineKeyboardButton("🔄 Backupdan tiklash", callback_data="restore_backup")],
        [InlineKeyboardButton("🗑 Bazani tozalash", callback_data="clear_database")],
        [InlineKeyboardButton("🔙 Bosh menyu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_users_keyboard(users):
    """Foydalanuvchilar ro'yxati"""
    buttons = []
    for user in users:
        status = "✅" if user['is_authorized'] else "⭕️"
        edit = "✏️" if user['can_edit'] else "👁"
        name = user['first_name'] or f"User{user['id']}"
        username = user['username'] or 'no username'
        buttons.append([
            InlineKeyboardButton(
                f"{status} {edit} {name} (@{username})", 
                callback_data=f"user_{user['id']}"
            )
        ])
    
    buttons.append([InlineKeyboardButton("🔙 Bosh menyu", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)

def get_user_actions_keyboard(user_id):
    """Foydalanuvchi amallari"""
    buttons = [
        [InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_{user_id}")],
        [InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{user_id}")],
        [InlineKeyboardButton("✏️ Tahrirlash huquqi", callback_data=f"toggle_edit_{user_id}")],
        [InlineKeyboardButton("🗑 O'chirish", callback_data=f"remove_user_{user_id}")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="users")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_access_request_keyboard():
    """Ruxsat so'rash tugmasi"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Ruxsat so'rash", callback_data="request_access")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="main_menu")]
    ])

def get_approve_reject_keyboard(request_id):
    """Tasdiqlash/Rad etish tugmalari"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_req_{request_id}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_req_{request_id}")
        ]
    ])

def get_groups_keyboard(groups):
    """Guruhlar ro'yxati"""
    buttons = []
    for group in groups:
        status = "✅" if group['is_active'] else "❌"
        buttons.append([
            InlineKeyboardButton(
                f"{status} {group['group_name']}", 
                callback_data=f"group_{group['id']}"
            )
        ])
    
    buttons.append([InlineKeyboardButton("🔙 Bosh menyu", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)

# ==================== UTILS ====================

async def export_to_excel():
    """Excel formatida eksport qilish"""
    session = db_session()
    products = session.query(Product).all()
    data = []
    
    for p in products:
        category = session.query(Category).filter_by(id=p.category_id).first()
        data.append({
            'ID': p.id,
            'Nomi': p.name or '',
            'Kategoriya': category.name if category else '',
            'Kelgan narxi ($)': p.purchase_price_usd or 0,
            'Kelgan narxi (so\'m)': p.purchase_price_uzs or 0,
            'Sotilish narxi ($)': p.selling_price_usd or 0,
            'Sotilish narxi (so\'m)': p.selling_price_uzs or 0,
            'Soni': p.quantity or 0,
            'Jami kelgan ($)': (p.purchase_price_usd or 0) * (p.quantity or 0),
            'Jami kelgan (so\'m)': (p.purchase_price_uzs or 0) * (p.quantity or 0),
            'Jami sotilish ($)': (p.selling_price_usd or 0) * (p.quantity or 0),
            'Jami sotilish (so\'m)': (p.selling_price_uzs or 0) * (p.quantity or 0),
            'Kalit so\'zlar': p.keywords or '',
            'Rasm ID': p.media_group_message_id or '',
            'Yaratilgan': p.created_at.strftime('%Y-%m-%d %H:%M:%S') if p.created_at else '',
            'Yangilangan': p.updated_at.strftime('%Y-%m-%d %H:%M:%S') if p.updated_at else ''
        })
    
    df = pd.DataFrame(data)
    filename = f"data/export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(filename, index=False)
    
    session.close()
    return filename

async def import_from_excel(file_path, clear_existing=True):
    """Excel fayldan import qilish"""
    session = db_session()
    
    try:
        if clear_existing:
            session.query(PriceHistory).delete()
            session.query(Product).delete()
            session.query(Category).delete()
            session.commit()
        
        df = pd.read_excel(file_path)
        categories_cache = {}
        
        for _, row in df.iterrows():
            # Kategoriyani yaratish yoki topish
            category_name = str(row.get('Kategoriya', ''))
            category_id = None
            
            if category_name and category_name != 'nan' and category_name.strip():
                if category_name not in categories_cache:
                    category = Category(name=category_name.strip())
                    session.add(category)
                    session.flush()
                    categories_cache[category_name] = category.id
                category_id = categories_cache.get(category_name)
            
            # Tovarni yaratish
            product = Product(
                name=str(row.get('Nomi', '')),
                category_id=category_id,
                purchase_price_usd=float(row.get('Kelgan narxi ($)', 0) or 0),
                purchase_price_uzs=float(row.get('Kelgan narxi (so\'m)', 0) or 0),
                selling_price_usd=float(row.get('Sotilish narxi ($)', 0) or 0),
                selling_price_uzs=float(row.get('Sotilish narxi (so\'m)', 0) or 0),
                quantity=int(row.get('Soni', 0) or 0),
                keywords=str(row.get('Kalit so\'zlar', '')),
                media_group_message_id=row.get('Rasm ID') if pd.notna(row.get('Rasm ID')) else None
            )
            session.add(product)
        
        session.commit()
        return True, "Import muvaffaqiyatli yakunlandi"
    
    except Exception as e:
        session.rollback()
        return False, f"Xatolik: {str(e)}"
    
    finally:
        session.close()

async def get_product_info_text(product, include_history=False):
    """Tovar ma'lumotlarini matn ko'rinishida olish"""
    text = f"📦 <b>{product.name}</b>\n\n"
    
    if product.description:
        text += f"📝 {product.description}\n\n"
    
    text += f"💰 <b>Kelgan narxi:</b>\n"
    if product.purchase_price_usd > 0:
        text += f"   • {product.purchase_price_usd:,.0f} $\n"
    if product.purchase_price_uzs > 0:
        text += f"   • {product.purchase_price_uzs:,.0f} so'm\n"
    
    text += f"\n💵 <b>Sotilish narxi:</b>\n"
    if product.selling_price_usd > 0:
        text += f"   • {product.selling_price_usd:,.0f} $\n"
    if product.selling_price_uzs > 0:
        text += f"   • {product.selling_price_uzs:,.0f} so'm\n"
    
    # Jami narxlar
    text += f"\n📊 <b>Jami (barcha tovarlar):</b>\n"
    if product.purchase_price_usd > 0:
        total_purchase_usd = product.purchase_price_usd * product.quantity
        text += f"   • Kelgan ($): {total_purchase_usd:,.0f} $\n"
    if product.purchase_price_uzs > 0:
        total_purchase_uzs = product.purchase_price_uzs * product.quantity
        text += f"   • Kelgan (so'm): {total_purchase_uzs:,.0f} so'm\n"
    if product.selling_price_usd > 0:
        total_selling_usd = product.selling_price_usd * product.quantity
        text += f"   • Sotilish ($): {total_selling_usd:,.0f} $\n"
    if product.selling_price_uzs > 0:
        total_selling_uzs = product.selling_price_uzs * product.quantity
        text += f"   • Sotilish (so'm): {total_selling_uzs:,.0f} so'm\n"
    
    text += f"\n📦 <b>Soni:</b> {product.quantity} dona\n"
    
    if product.keywords:
        text += f"\n🔑 <b>Kalit so'zlar:</b> {product.keywords}\n"
    
    tashkent_time = get_tashkent_time()
    text += f"\n📅 <b>Qo'shilgan:</b> {product.created_at.strftime('%d.%m.%Y %H:%M')}"
    text += f"\n🕐 <b>Toshkent vaqti:</b> {tashkent_time.strftime('%H:%M:%S %d.%m.%Y')}"
    
    return text

# ==================== HANDLERS ====================

# Conversation states
(SEARCH, ADD_PRODUCT_NAME, ADD_PRODUCT_PHOTO, ADD_PRODUCT_PURCHASE,
 ADD_PRODUCT_SELLING, ADD_PRODUCT_QUANTITY, ADD_PRODUCT_KEYWORDS, 
 ADD_PRODUCT_CATEGORY, EDIT_WAITING, IMPORT_WAITING, RESTORE_WAITING, 
 GRANT_ACCESS_WAITING, WAITING_FOR_PRICE) = range(13)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start komandasi"""
    user = update.effective_user
    if not user:
        return
    
    session = db_session()
    
    try:
        # Foydalanuvchini bazaga qo'shish
        db_user = session.query(User).filter_by(telegram_id=user.id).first()
        if not db_user:
            db_user = User(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                is_authorized=False
            )
            session.add(db_user)
            session.commit()
        
        # Guruh/kanalni tekshirish
        if update.message and update.message.chat.type in ['group', 'supergroup', 'channel']:
            group = session.query(BotGroup).filter_by(group_id=update.message.chat.id).first()
            if not group:
                group = BotGroup(
                    group_id=update.message.chat.id,
                    group_name=update.message.chat.title or "Media Group"
                )
                session.add(group)
                session.commit()
            
            await update.message.reply_text(
                f"✅ Bot guruhga qo'shildi!\n"
                f"📌 Guruh ID: {update.message.chat.id}\n"
                f"📝 Guruh nomi: {update.message.chat.title}\n\n"
                f"Endi bu guruhga yuborilgan rasmlar tovarlarga biriktiriladi."
            )
            return
        
        # Shaxsiy chat
        tashkent_time = get_tashkent_time()
        
        if db_user.is_admin:
            # Barcha tovarlar statistikasi
            products = session.query(Product).all()
            total_products = len(products)
            total_quantity = sum(p.quantity for p in products)
            total_purchase_usd = sum((p.purchase_price_usd or 0) * (p.quantity or 0) for p in products)
            total_purchase_uzs = sum((p.purchase_price_uzs or 0) * (p.quantity or 0) for p in products)
            total_selling_usd = sum((p.selling_price_usd or 0) * (p.quantity or 0) for p in products)
            total_selling_uzs = sum((p.selling_price_uzs or 0) * (p.quantity or 0) for p in products)
            
            text = (f"👋 Xush kelibsiz Admin {user.first_name}!\n\n"
                    f"🕐 Toshkent vaqti: {tashkent_time.strftime('%H:%M:%S')}\n"
                    f"📅 Sana: {tashkent_time.strftime('%d.%m.%Y')}\n\n"
                    f"📊 <b>SKLAD STATISTIKASI</b>\n"
                    f"📦 Jami tovarlar: {total_products}\n"
                    f"🔢 Jami soni: {total_quantity} dona\n\n"
                    f"💰 <b>Kelgan narxi:</b>\n")
            
            if total_purchase_usd > 0:
                text += f"   • Jami $: {total_purchase_usd:,.0f} $\n"
            if total_purchase_uzs > 0:
                text += f"   • Jami so'm: {total_purchase_uzs:,.0f} so'm\n"
            
            text += f"\n💵 <b>Sotilish narxi (potensial):</b>\n"
            if total_selling_usd > 0:
                text += f"   • Jami $: {total_selling_usd:,.0f} $\n"
            if total_selling_uzs > 0:
                text += f"   • Jami so'm: {total_selling_uzs:,.0f} so'm\n"
            
            if total_purchase_usd > 0 and total_selling_usd > 0:
                profit_usd = total_selling_usd - total_purchase_usd
                text += f"\n📈 Potensial foyda ($): {profit_usd:,.0f} $\n"
            
            text += f"\nKerakli bo'limni tanlang:"
            
            await update.message.reply_text(
                text, 
                reply_markup=get_main_keyboard(user_is_admin=True),
                parse_mode='HTML'
            )
        elif db_user.is_authorized:
            text = (f"👋 Xush kelibsiz {user.first_name}!\n\n"
                    f"🕐 Toshkent vaqti: {tashkent_time.strftime('%H:%M:%S')}\n"
                    f"📅 Sana: {tashkent_time.strftime('%d.%m.%Y')}\n\n"
                    f"Kerakli bo'limni tanlang:")
            await update.message.reply_text(
                text, 
                reply_markup=get_main_keyboard(user_can_edit=db_user.can_edit),
                parse_mode='HTML'
            )
        else:
            text = (f"👋 Xush kelibsiz {user.first_name}!\n\n"
                    f"❌ Botdan foydalanish uchun ruxsat kerak.\n"
                    f"ID raqamingiz: <code>{user.id}</code>\n\n"
                    f"Ruxsat so'rash uchun pastdagi tugmani bosing.")
            await update.message.reply_text(
                text,
                reply_markup=get_access_request_keyboard(),
                parse_mode='HTML'
            )
    
    finally:
        session.close()

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yordam komandasi"""
    tashkent_time = get_tashkent_time()
    
    help_text = f"""
🤖 <b>BOT HAQIDA MA'LUMOT</b>

<b>🔍 Qidirish:</b>
• Tovar nomi yoki kalit so'z bilan qidiring

<b>📂 Kategoriyalar:</b>
• Mahsulotlarni kategoriyalar bo'yicha ko'rish
• Kategoriya ichida kategoriya yaratish
• Kategoriyaga tovar qo'shish

<b>📊 Statistika (Admin):</b>
• Jami tovarlar, kategoriyalar
• Narxlar statistikasi
• Sklad jami ma'lumotlari

<b>➕ Tovar qo'shish (Admin):</b>
• Nomi, rasmi, narxlari
• USD yoki UZS tanlash
• Kalit so'zlar

<b>👥 Foydalanuvchilar (Admin):</b>
• Ruxsat berish/olib tashlash
• Tahrirlash huquqini berish

<b>📥 Eksport/Import (Admin):</b>
• Excel formatida eksport/import
• Backup yuklab olish/tiklash

<b>👥 Guruhlar (Admin):</b>
• Bot biriktirilgan guruhlar
• Rasm saqlanadigan guruh

🕐 <b>Toshkent vaqti:</b> {tashkent_time.strftime('%H:%M:%S %d.%m.%Y')}
    """
    
    await update.message.reply_text(help_text, parse_mode='HTML')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tugmalar bosilganda"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    if not user:
        return
    
    session = db_session()
    
    try:
        db_user = session.query(User).filter_by(telegram_id=user.id).first()
        
        if not db_user:
            await query.edit_message_text("❌ Foydalanuvchi topilmadi! /start ni bosing.")
            return
        
        data = query.data
        
        # Bekor qilish
        if data == "cancel":
            context.user_data.clear()
            await query.edit_message_text(
                "❌ Bekor qilindi.",
                reply_markup=get_back_button()
            )
            return
        
        # Ruxsat so'rash
        if data == "request_access":
            existing = session.query(AccessRequest).filter_by(
                user_id=db_user.id, status='pending'
            ).first()
            
            if existing:
                await query.edit_message_text(
                    "⏳ Sizning so'rovingiz already yuborilgan. Tasdiqlanishini kuting."
                )
            else:
                request = AccessRequest(user_id=db_user.id)
                session.add(request)
                session.commit()
                
                # Adminlarga xabar yuborish
                admins = session.query(User).filter_by(is_admin=True).all()
                for admin in admins:
                    try:
                        await context.bot.send_message(
                            admin.telegram_id,
                            f"🆕 Yangi ruxsat so'rovi!\n\n"
                            f"👤 Foydalanuvchi: {db_user.first_name}\n"
                            f"🆔 ID: {db_user.telegram_id}\n"
                            f"👤 Username: @{db_user.username or 'yoq'}",
                            reply_markup=get_approve_reject_keyboard(request.id)
                        )
                    except Exception as e:
                        logger.error(f"Admin ga xabar yuborishda xatolik: {e}")
                
                await query.edit_message_text(
                    "✅ So'rovingiz yuborildi! Tasdiqlanishini kuting."
                )
            return
        
        # So'rovni tasdiqlash/rad etish
        if data.startswith("approve_req_") or data.startswith("reject_req_"):
            if not db_user or not db_user.is_admin:
                await query.edit_message_text("❌ Bu amalni bajarish uchun admin huquqi kerak.")
                return
            
            request_id = int(data.split("_")[2])
            request = session.query(AccessRequest).filter_by(id=request_id).first()
            
            if not request:
                await query.edit_message_text("❌ So'rov topilmadi!")
                return
            
            if data.startswith("approve_req_"):
                request.status = 'approved'
                request.user.is_authorized = True
                session.commit()
                
                try:
                    await context.bot.send_message(
                        request.user.telegram_id,
                        "✅ Sizning so'rovingiz tasdiqlandi! Endi botdan foydalanishingiz mumkin.\n"
                        "Ishlatish uchun /start ni bosing."
                    )
                except Exception as e:
                    logger.error(f"Foydalanuvchiga xabar yuborishda xatolik: {e}")
                
                await query.edit_message_text(
                    f"✅ Foydalanuvchi {request.user.first_name} tasdiqlandi!"
                )
            else:
                request.status = 'rejected'
                session.commit()
                
                try:
                    await context.bot.send_message(
                        request.user.telegram_id,
                        "❌ Sizning so'rovingiz rad etildi."
                    )
                except Exception as e:
                    logger.error(f"Foydalanuvchiga xabar yuborishda xatolik: {e}")
                
                await query.edit_message_text(
                    f"❌ Foydalanuvchi {request.user.first_name} rad etildi!"
                )
            return
        
        # Guruhlar
        if data == "groups":
            if not db_user.is_admin:
                await query.edit_message_text("❌ Ruxsat yo'q!")
                return
            
            groups = session.query(BotGroup).all()
            group_list = []
            for g in groups:
                group_list.append({
                    'id': g.id,
                    'group_id': g.group_id,
                    'group_name': g.group_name or f"Group {g.group_id}",
                    'is_active': g.is_active
                })
            
            text = "👥 Bot biriktirilgan guruhlar:\n\n"
            if group_list:
                for g in group_list:
                    status = "✅ Faol" if g['is_active'] else "❌ Faol emas"
                    text += f"• {g['group_name']}\n  ID: {g['group_id']}\n  Status: {status}\n\n"
            else:
                text += "Hali hech qanday guruh biriktirilmagan."
            
            await query.edit_message_text(
                text,
                reply_markup=get_groups_keyboard(group_list)
            )
            return
        
        if data.startswith("group_"):
            if not db_user.is_admin:
                await query.edit_message_text("❌ Ruxsat yo'q!")
                return
            
            group_id = int(data.split("_")[1])
            group = session.query(BotGroup).filter_by(id=group_id).first()
            
            if group:
                text = (f"👥 <b>Guruh ma'lumotlari</b>\n\n"
                        f"📝 Nomi: {group.group_name}\n"
                        f"🆔 ID: {group.group_id}\n"
                        f"📊 Status: {'✅ Faol' if group.is_active else '❌ Faol emas'}\n"
                        f"📅 Qo'shilgan: {group.created_at.strftime('%d.%m.%Y')}\n\n"
                        f"Bu guruhga yuborilgan rasmlar tovarlarga biriktiriladi.")
                
                buttons = [
                    [InlineKeyboardButton("🔙 Orqaga", callback_data="groups")]
                ]
                await query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode='HTML'
                )
            else:
                await query.edit_message_text("❌ Guruh topilmadi!")
            return
        
        # Asosiy menyu
        if data == "main_menu":
            tashkent_time = get_tashkent_time()
            
            if db_user.is_admin:
                # Barcha tovarlar statistikasi
                products = session.query(Product).all()
                total_products = len(products)
                total_quantity = sum(p.quantity for p in products)
                total_purchase_usd = sum((p.purchase_price_usd or 0) * (p.quantity or 0) for p in products)
                total_purchase_uzs = sum((p.purchase_price_uzs or 0) * (p.quantity or 0) for p in products)
                total_selling_usd = sum((p.selling_price_usd or 0) * (p.quantity or 0) for p in products)
                total_selling_uzs = sum((p.selling_price_uzs or 0) * (p.quantity or 0) for p in products)
                
                text = (f"👋 Xush kelibsiz Admin {user.first_name}!\n\n"
                        f"🕐 Toshkent vaqti: {tashkent_time.strftime('%H:%M:%S')}\n"
                        f"📅 Sana: {tashkent_time.strftime('%d.%m.%Y')}\n\n"
                        f"📊 <b>SKLAD STATISTIKASI</b>\n"
                        f"📦 Jami tovarlar: {total_products}\n"
                        f"🔢 Jami soni: {total_quantity} dona\n\n"
                        f"💰 <b>Kelgan narxi:</b>\n")
                
                if total_purchase_usd > 0:
                    text += f"   • Jami $: {total_purchase_usd:,.0f} $\n"
                if total_purchase_uzs > 0:
                    text += f"   • Jami so'm: {total_purchase_uzs:,.0f} so'm\n"
                
                text += f"\n💵 <b>Sotilish narxi (potensial):</b>\n"
                if total_selling_usd > 0:
                    text += f"   • Jami $: {total_selling_usd:,.0f} $\n"
                if total_selling_uzs > 0:
                    text += f"   • Jami so'm: {total_selling_uzs:,.0f} so'm\n"
                
                if total_purchase_usd > 0 and total_selling_usd > 0:
                    profit_usd = total_selling_usd - total_purchase_usd
                    text += f"\n📈 Potensial foyda ($): {profit_usd:,.0f} $\n"
                
                text += f"\nKerakli bo'limni tanlang:"
                
                await query.edit_message_text(
                    text, 
                    reply_markup=get_main_keyboard(user_is_admin=True),
                    parse_mode='HTML'
                )
            else:
                await query.edit_message_text(
                    "Kerakli bo'limni tanlang:",
                    reply_markup=get_main_keyboard(user_can_edit=db_user.can_edit)
                )
            return
        
        # Qidirish
        if data == "search":
            context.user_data['state'] = SEARCH
            await query.edit_message_text(
                "🔍 Qidirish uchun tovar nomi yoki kalit so'zni kiriting:",
                reply_markup=get_cancel_button()
            )
            return
        
        # Kategoriyalar
        if data == "categories":
            categories = session.query(Category).filter_by(parent_id=None).all()
            cat_list = [{'id': c.id, 'name': c.name} for c in categories]
            await query.edit_message_text(
                "📂 Kategoriyalar:",
                reply_markup=get_categories_keyboard(cat_list, is_admin=db_user.is_admin)
            )
            return
        
        # Kategoriya ichiga kirish
        if data.startswith("cat_"):
            category_id = int(data.split("_")[1])
            category = session.query(Category).filter_by(id=category_id).first()
            
            if not category:
                await query.edit_message_text("❌ Kategoriya topilmadi!")
                return
            
            subcats = session.query(Category).filter_by(parent_id=category_id).all()
            products = session.query(Product).filter_by(category_id=category_id).all()
            
            text = f"📂 <b>{category.name}</b>\n\n"
            
            if subcats:
                text += "📁 <b>Pastki kategoriyalar:</b>\n"
                for sc in subcats:
                    text += f"• {sc.name}\n"
                text += "\n"
            
            if products:
                text += "📦 <b>Tovarlar:</b>\n"
                for p in products:
                    text += f"• {p.name} - {p.quantity} dona\n"
            else:
                text += "Bu kategoriyada tovarlar yo'q."
            
            # Tugmalar
            buttons = []
            for sc in subcats:
                buttons.append([InlineKeyboardButton(f"📁 {sc.name}", callback_data=f"cat_{sc.id}")])
            
            for p in products:
                buttons.append([InlineKeyboardButton(f"📦 {p.name}", callback_data=f"view_{p.id}")])
            
            if db_user.is_admin:
                buttons.append([InlineKeyboardButton("➕ Kategoriya qo'shish", callback_data=f"add_cat_{category_id}")])
                buttons.append([InlineKeyboardButton("➕ Tovar qo'shish", callback_data=f"add_product_cat_{category_id}")])
            
            buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data="categories")])
            
            await query.edit_message_text(
                text, 
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode='HTML'
            )
            return
        
        # Tovarni ko'rish
        if data.startswith("view_"):
            product_id = int(data.split("_")[1])
            product = session.query(Product).filter_by(id=product_id).first()
            
            if not product:
                await query.edit_message_text("❌ Tovar topilmadi!")
                return
            
            text = await get_product_info_text(product, include_history=True)
            
            # Rasmni guruhdan olish
            if product.media_group_message_id:
                try:
                    # Guruhdagi xabarni forward qilish
                    group = session.query(BotGroup).first()
                    if group:
                        await context.bot.forward_message(
                            chat_id=user.id,
                            from_chat_id=group.group_id,
                            message_id=product.media_group_message_id
                        )
                except Exception as e:
                    logger.error(f"Rasmni forward qilishda xatolik: {e}")
                    await context.bot.send_message(
                        chat_id=user.id,
                        text="❌ Rasm topilmadi yoki guruhdan o'chirilgan!"
                    )
            
            await query.edit_message_text(
                text,
                reply_markup=get_product_actions_keyboard(product_id, db_user.is_admin),
                parse_mode='HTML'
            )
            return
        
        # Tahrirlash
        if data.startswith("edit_"):
            if not db_user.is_admin and not db_user.can_edit:
                await query.edit_message_text("❌ Sizda tahrirlash huquqi yo'q!")
                return
            
            parts = data.split("_")
            if len(parts) == 2:
                product_id = int(parts[1])
                await query.edit_message_text(
                    "Qaysi ma'lumotni tahrirlash kerak?",
                    reply_markup=get_edit_product_keyboard(product_id)
                )
            elif len(parts) >= 3:
                field = parts[1]
                product_id = int(parts[2])
                
                context.user_data['editing_product'] = product_id
                context.user_data['editing_field'] = field
                
                if field == 'purchase':
                    await query.edit_message_text(
                        "💰 Kelgan narx turini tanlang:",
                        reply_markup=get_price_type_keyboard(product_id, 'purchase')
                    )
                elif field == 'selling':
                    await query.edit_message_text(
                        "💵 Sotilish narx turini tanlang:",
                        reply_markup=get_price_type_keyboard(product_id, 'selling')
                    )
                elif field == 'photo':
                    await query.edit_message_text(
                        "🖼 Yangi rasmni yuboring (yoki /cancel):",
                        reply_markup=get_cancel_button()
                    )
                    context.user_data['state'] = EDIT_WAITING
                elif field == 'name':
                    await query.edit_message_text(
                        "📝 Yangi nomni kiriting:",
                        reply_markup=get_cancel_button()
                    )
                    context.user_data['state'] = EDIT_WAITING
                elif field == 'quantity':
                    await query.edit_message_text(
                        "📦 Yangi sonini kiriting:",
                        reply_markup=get_cancel_button()
                    )
                    context.user_data['state'] = EDIT_WAITING
                elif field == 'keywords':
                    await query.edit_message_text(
                        "🔑 Yangi kalit so'zlarni kiriting (vergul bilan):",
                        reply_markup=get_cancel_button()
                    )
                    context.user_data['state'] = EDIT_WAITING
            return
        
        # Narx turini tanlash
        if data.startswith("set_purchase_usd_") or data.startswith("set_purchase_uzs_") or \
           data.startswith("set_selling_usd_") or data.startswith("set_selling_uzs_"):
            parts = data.split("_")
            price_type = parts[1]  # purchase yoki selling
            currency = parts[2]     # usd yoki uzs
            product_id = int(parts[3])
            
            context.user_data['editing_product'] = product_id
            context.user_data['editing_field'] = f"{price_type}_{currency}"
            context.user_data['state'] = EDIT_WAITING
            
            currency_text = "USD ($)" if currency == "usd" else "UZS (so'm)"
            price_text = "Kelgan" if price_type == "purchase" else "Sotilish"
            
            await query.edit_message_text(
                f"💰 {price_text} narxini {currency_text} da kiriting:",
                reply_markup=get_cancel_button()
            )
            return
        
        # O'chirish
        if data.startswith("delete_"):
            if not db_user.is_admin:
                await query.edit_message_text("❌ Sizda o'chirish huquqi yo'q!")
                return
            
            product_id = int(data.split("_")[1])
            product = session.query(Product).filter_by(id=product_id).first()
            
            if product:
                session.delete(product)
                session.commit()
                await query.edit_message_text("✅ Tovar o'chirildi!")
            else:
                await query.edit_message_text("❌ Tovar topilmadi!")
            return
        
        # Tovar qo'shish
        if data == "add_product" or data.startswith("add_product_cat_"):
            if not db_user.is_admin:
                await query.edit_message_text("❌ Sizda tovar qo'shish huquqi yo'q!")
                return
            
            context.user_data['new_product'] = {}
            
            if data.startswith("add_product_cat_"):
                category_id = int(data.split("_")[3])
                context.user_data['new_product']['category_id'] = category_id
            
            context.user_data['state'] = ADD_PRODUCT_NAME
            
            await query.edit_message_text(
                "📝 Tovar nomini kiriting:",
                reply_markup=get_cancel_button()
            )
            return
        
        # Kategoriya qo'shish
        if data.startswith("add_cat_"):
            if not db_user.is_admin:
                await query.edit_message_text("❌ Sizda kategoriya qo'shish huquqi yo'q!")
                return
            
            parent_id = int(data.split("_")[2])
            context.user_data['new_category_parent'] = parent_id
            context.user_data['state'] = ADD_PRODUCT_CATEGORY
            
            await query.edit_message_text(
                "📝 Yangi kategoriya nomini kiriting:",
                reply_markup=get_cancel_button()
            )
            return
        
        # Yangi kategoriya tanlash
        if data.startswith("select_cat_"):
            category_id = int(data.split("_")[2])
            
            if 'new_product' in context.user_data:
                context.user_data['new_product']['category_id'] = category_id
                
                # Tovarni saqlash
                session = db_session()
                try:
                    product = Product(
                        name=context.user_data['new_product']['name'],
                        category_id=category_id,
                        purchase_price_usd=context.user_data['new_product'].get('purchase_usd', 0),
                        purchase_price_uzs=context.user_data['new_product'].get('purchase_uzs', 0),
                        selling_price_usd=context.user_data['new_product'].get('selling_usd', 0),
                        selling_price_uzs=context.user_data['new_product'].get('selling_uzs', 0),
                        quantity=context.user_data['new_product'].get('quantity', 0),
                        keywords=context.user_data['new_product'].get('keywords', ''),
                        media_group_message_id=context.user_data['new_product'].get('media_message_id')
                    )
                    session.add(product)
                    session.commit()
                    
                    await query.edit_message_text(
                        "✅ Tovar muvaffaqiyatli qo'shildi!",
                        reply_markup=get_back_button()
                    )
                    
                    # Tozalash
                    context.user_data.pop('new_product', None)
                    
                except Exception as e:
                    session.rollback()
                    await query.edit_message_text(f"❌ Xatolik: {str(e)}")
                finally:
                    session.close()
            return
        
        if data == "add_new_category":
            context.user_data['state'] = ADD_PRODUCT_CATEGORY
            await query.edit_message_text(
                "📂 Yangi kategoriya nomini kiriting:",
                reply_markup=get_cancel_button()
            )
            return
        
        # Statistika
        if data == "stats":
            if not db_user.is_admin and not db_user.can_edit:
                await query.edit_message_text("❌ Sizda statistika ko'rish huquqi yo'q!")
                return
            
            products = session.query(Product).all()
            total_products = len(products)
            total_quantity = sum(p.quantity for p in products)
            total_purchase_usd = sum((p.purchase_price_usd or 0) * (p.quantity or 0) for p in products)
            total_purchase_uzs = sum((p.purchase_price_uzs or 0) * (p.quantity or 0) for p in products)
            total_selling_usd = sum((p.selling_price_usd or 0) * (p.quantity or 0) for p in products)
            total_selling_uzs = sum((p.selling_price_uzs or 0) * (p.quantity or 0) for p in products)
            categories = session.query(Category).count()
            
            tashkent_time = get_tashkent_time()
            
            text = (f"📊 <b>STATISTIKA</b>\n\n"
                    f"📦 Jami tovarlar: {total_products}\n"
                    f"📂 Kategoriyalar: {categories}\n"
                    f"🔢 Jami soni: {total_quantity} dona\n\n"
                    f"💰 <b>Kelgan narxi (jami):</b>\n")
            
            if total_purchase_usd > 0:
                text += f"   • $: {total_purchase_usd:,.0f}\n"
            if total_purchase_uzs > 0:
                text += f"   • so'm: {total_purchase_uzs:,.0f}\n"
            
            text += f"\n💵 <b>Sotilish narxi (jami):</b>\n"
            if total_selling_usd > 0:
                text += f"   • $: {total_selling_usd:,.0f}\n"
            if total_selling_uzs > 0:
                text += f"   • so'm: {total_selling_uzs:,.0f}\n"
            
            if total_purchase_usd > 0 and total_selling_usd > 0:
                profit_usd = total_selling_usd - total_purchase_usd
                text += f"\n📈 Potensial foyda ($): {profit_usd:,.0f}\n"
            
            text += f"\n🕐 Yangilangan: {tashkent_time.strftime('%H:%M:%S %d.%m.%Y')}"
            
            await query.edit_message_text(
                text, 
                reply_markup=get_back_button(),
                parse_mode='HTML'
            )
            return
        
        # Foydalanuvchilar
        if data == "users":
            if not db_user.is_admin:
                await query.edit_message_text("❌ Sizda foydalanuvchilar ro'yxatini ko'rish huquqi yo'q!")
                return
            
            users = session.query(User).all()
            user_list = []
            for u in users:
                user_list.append({
                    'id': u.id, 
                    'telegram_id': u.telegram_id, 
                    'username': u.username or '-', 
                    'first_name': u.first_name or f"User{u.id}", 
                    'is_authorized': u.is_authorized, 
                    'can_edit': u.can_edit
                })
            
            await query.edit_message_text(
                "👥 Foydalanuvchilar:",
                reply_markup=get_users_keyboard(user_list)
            )
            return
        
        # Foydalanuvchi ma'lumotlari
        if data.startswith("user_"):
            if not db_user.is_admin:
                await query.edit_message_text("❌ Ruxsat yo'q!")
                return
            
            user_id = int(data.split("_")[1])
            target_user = session.query(User).filter_by(id=user_id).first()
            
            if target_user:
                status = "✅ Tasdiqlangan" if target_user.is_authorized else "❌ Tasdiqlanmagan"
                edit_rights = "✏️ Tahrirlash huquqi bor" if target_user.can_edit else "👁 Faqat ko'rish"
                
                text = (f"👤 <b>Foydalanuvchi ma'lumotlari</b>\n\n"
                        f"🆔 ID: {target_user.telegram_id}\n"
                        f"📝 Ism: {target_user.first_name or 'Noma\'lum'}\n"
                        f"👤 Username: @{target_user.username or 'yoq'}\n"
                        f"📊 Status: {status}\n"
                        f"✏️ Huquq: {edit_rights}\n"
                        f"📅 Qo'shilgan: {target_user.created_at.strftime('%d.%m.%Y')}")
                
                await query.edit_message_text(
                    text,
                    reply_markup=get_user_actions_keyboard(target_user.id),
                    parse_mode='HTML'
                )
            else:
                await query.edit_message_text("❌ Foydalanuvchi topilmadi!")
            return
        
        # Foydalanuvchini tasdiqlash
        if data.startswith("approve_") and not data.startswith("approve_req_"):
            if not db_user.is_admin:
                await query.edit_message_text("❌ Ruxsat yo'q!")
                return
            
            user_id = int(data.split("_")[1])
            target_user = session.query(User).filter_by(id=user_id).first()
            
            if target_user:
                target_user.is_authorized = True
                session.commit()
                await query.edit_message_text(f"✅ Foydalanuvchi {target_user.first_name or 'User'} tasdiqlandi!")
                
                try:
                    await context.bot.send_message(
                        target_user.telegram_id,
                        "✅ Siz tasdiqlandingiz! Endi botdan foydalanishingiz mumkin.\n"
                        "/start ni bosing."
                    )
                except Exception as e:
                    logger.error(f"Xabar yuborishda xatolik: {e}")
            else:
                await query.edit_message_text("❌ Foydalanuvchi topilmadi!")
            return
        
        # Foydalanuvchini rad etish
        if data.startswith("reject_") and not data.startswith("reject_req_"):
            if not db_user.is_admin:
                await query.edit_message_text("❌ Ruxsat yo'q!")
                return
            
            user_id = int(data.split("_")[1])
            target_user = session.query(User).filter_by(id=user_id).first()
            
            if target_user:
                target_user.is_authorized = False
                session.commit()
                await query.edit_message_text(f"❌ Foydalanuvchi {target_user.first_name or 'User'} rad etildi!")
                
                try:
                    await context.bot.send_message(
                        target_user.telegram_id,
                        "❌ Sizning so'rovingiz rad etildi."
                    )
                except Exception as e:
                    logger.error(f"Xabar yuborishda xatolik: {e}")
            else:
                await query.edit_message_text("❌ Foydalanuvchi topilmadi!")
            return
        
        # Tahrirlash huquqini o'zgartirish
        if data.startswith("toggle_edit_"):
            if not db_user.is_admin:
                await query.edit_message_text("❌ Ruxsat yo'q!")
                return
            
            user_id = int(data.split("_")[2])
            target_user = session.query(User).filter_by(id=user_id).first()
            
            if target_user:
                target_user.can_edit = not target_user.can_edit
                session.commit()
                status = "berildi" if target_user.can_edit else "olib tashlandi"
                await query.edit_message_text(f"✏️ Tahrirlash huquqi {status}!")
            else:
                await query.edit_message_text("❌ Foydalanuvchi topilmadi!")
            return
        
        # Foydalanuvchini o'chirish
        if data.startswith("remove_user_"):
            if not db_user.is_admin:
                await query.edit_message_text("❌ Ruxsat yo'q!")
                return
            
            user_id = int(data.split("_")[2])
            target_user = session.query(User).filter_by(id=user_id).first()
            
            if target_user and target_user.telegram_id != ADMIN_ID:
                session.delete(target_user)
                session.commit()
                await query.edit_message_text("✅ Foydalanuvchi o'chirildi!")
            else:
                await query.edit_message_text("❌ Foydalanuvchi topilmadi yoki adminni o'chirib bo'lmaydi!")
            return
        
        # Ruxsat berish
        if data == "grant_access":
            if not db_user.is_admin:
                await query.edit_message_text("❌ Ruxsat yo'q!")
                return
            
            context.user_data['state'] = GRANT_ACCESS_WAITING
            await query.edit_message_text(
                "👤 Ruxsat bermoqchi bo'lgan foydalanuvchining Telegram ID sini kiriting:",
                reply_markup=get_cancel_button()
            )
            return
        
        # Eksport/Import
        if data == "export_import":
            if not db_user.is_admin:
                await query.edit_message_text("❌ Ruxsat yo'q!")
                return
            
            await query.edit_message_text(
                "📥 Eksport / Import bo'limi:",
                reply_markup=get_export_import_keyboard()
            )
            return
        
        if data == "export_excel":
            if not db_user.is_admin:
                await query.edit_message_text("❌ Ruxsat yo'q!")
                return
            
            await query.edit_message_text("⏳ Excel fayl tayyorlanmoqda...")
            
            try:
                filename = await export_to_excel()
                
                with open(filename, 'rb') as f:
                    await context.bot.send_document(
                        chat_id=user.id,
                        document=f,
                        filename=f"tovarlar_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        caption="✅ Tovarlar ro'yxati (barcha ma'lumotlar bilan)"
                    )
                
                os.remove(filename)
                await query.delete_message()
            except Exception as e:
                await query.edit_message_text(f"❌ Xatolik: {str(e)}")
            return
        
        if data == "import_excel":
            if not db_user.is_admin:
                await query.edit_message_text("❌ Ruxsat yo'q!")
                return
            
            context.user_data['state'] = IMPORT_WAITING
            await query.edit_message_text(
                "📤 Excel faylni yuboring (barcha eski ma'lumotlar o'chadi):",
                reply_markup=get_cancel_button()
            )
            return
        
        if data == "download_backup":
            if not db_user.is_admin:
                await query.edit_message_text("❌ Ruxsat yo'q!")
                return
            
            try:
                backup_file = backup_database()
                
                with open(backup_file, 'rb') as f:
                    await context.bot.send_document(
                        chat_id=user.id,
                        document=f,
                        filename=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                        caption="✅ Ma'lumotlar bazasi backup fayli"
                    )
                
                await query.delete_message()
            except Exception as e:
                await query.edit_message_text(f"❌ Xatolik: {str(e)}")
            return
        
        if data == "restore_backup":
            if not db_user.is_admin:
                await query.edit_message_text("❌ Ruxsat yo'q!")
                return
            
            context.user_data['state'] = RESTORE_WAITING
            await query.edit_message_text(
                "🔄 Backup faylni yuboring (.db fayl):",
                reply_markup=get_cancel_button()
            )
            return
        
        if data == "clear_database":
            if not db_user.is_admin:
                await query.edit_message_text("❌ Ruxsat yo'q!")
                return
            
            buttons = [
                [InlineKeyboardButton("✅ Ha, tozalash", callback_data="confirm_clear")],
                [InlineKeyboardButton("❌ Yo'q, bekor qilish", callback_data="main_menu")]
            ]
            await query.edit_message_text(
                "⚠️ DIQQAT! Barcha ma'lumotlar o'chiriladi!\n"
                "Davom etishni istaysizmi?",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            return
        
        if data == "confirm_clear":
            if not db_user.is_admin:
                await query.edit_message_text("❌ Ruxsat yo'q!")
                return
            
            session.query(PriceHistory).delete()
            session.query(Product).delete()
            session.query(Category).delete()
            session.commit()
            
            await query.edit_message_text(
                "✅ Barcha ma'lumotlar tozalandi!",
                reply_markup=get_back_button()
            )
            return
        
        if data == "export_only":
            if not db_user.can_edit:
                await query.edit_message_text("❌ Ruxsat yo'q!")
                return
            
            try:
                filename = await export_to_excel()
                
                with open(filename, 'rb') as f:
                    await context.bot.send_document(
                        chat_id=user.id,
                        document=f,
                        filename=f"tovarlar_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        caption="✅ Tovarlar ro'yxati"
                    )
                
                os.remove(filename)
                await query.delete_message()
            except Exception as e:
                await query.edit_message_text(f"❌ Xatolik: {str(e)}")
            return
    
    finally:
        session.close()

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xabarlarni qabul qilish"""
    user = update.effective_user
    if not user or not update.message or not update.message.text:
        return
    
    text = update.message.text
    
    # /skip komandasi
    if text == "/skip" or text == "/cancel":
        context.user_data['state'] = None
        await update.message.reply_text(
            "❌ Bekor qilindi.",
            reply_markup=get_back_button()
        )
        return
    
    session = db_session()
    
    try:
        db_user = session.query(User).filter_by(telegram_id=user.id).first()
        
        if not db_user or (not db_user.is_authorized and not db_user.is_admin):
            await update.message.reply_text(
                "❌ Siz botdan foydalana olmaysiz. Avval ruxsat oling.",
                reply_markup=get_access_request_keyboard()
            )
            return
        
        state = context.user_data.get('state')
        
        # Qidirish
        if state == SEARCH:
            query = text.strip()
            products = session.query(Product).filter(
                (Product.name.contains(query)) | 
                (Product.keywords.contains(query))
            ).all()
            
            if not products:
                await update.message.reply_text(
                    "❌ Hech narsa topilmadi!",
                    reply_markup=get_back_button()
                )
            else:
                await update.message.reply_text(f"🔍 {len(products)} ta tovar topildi:")
                
                for product in products[:5]:
                    prod_text = await get_product_info_text(product)
                    
                    # Rasmni guruhdan olish
                    if product.media_group_message_id:
                        try:
                            group = session.query(BotGroup).first()
                            if group:
                                await context.bot.forward_message(
                                    chat_id=user.id,
                                    from_chat_id=group.group_id,
                                    message_id=product.media_group_message_id
                                )
                        except:
                            pass
                    
                    await update.message.reply_text(
                        prod_text,
                        reply_markup=get_product_actions_keyboard(product.id, db_user.is_admin),
                        parse_mode='HTML'
                    )
                
                if len(products) > 5:
                    await update.message.reply_text(f"Yana {len(products) - 5} ta tovar bor...")
            
            context.user_data['state'] = None
            return
        
        # Tovar qo'shish - nom
        if state == ADD_PRODUCT_NAME:
            context.user_data['new_product']['name'] = text
            context.user_data['state'] = ADD_PRODUCT_PHOTO
            await update.message.reply_text(
                "🖼 Tovar rasmini yuboring (yoki /skip):",
                reply_markup=get_cancel_button()
            )
            return
        
        # Tovar qo'shish - kelgan narx
        if state == ADD_PRODUCT_PURCHASE:
            try:
                # USD yoki UZS ni aniqlash
                if 'price_currency' in context.user_data:
                    currency = context.user_data['price_currency']
                    value = float(text.replace(',', '.'))
                    
                    if currency == 'usd':
                        context.user_data['new_product']['purchase_usd'] = value
                    else:
                        context.user_data['new_product']['purchase_uzs'] = value
                    
                    context.user_data.pop('price_currency', None)
                    context.user_data['state'] = ADD_PRODUCT_SELLING
                    
                    await update.message.reply_text(
                        "💵 Sotilish narx turini tanlang:",
                        reply_markup=get_price_type_keyboard(0, 'selling')
                    )
                else:
                    await update.message.reply_text(
                        "❌ Xatolik. Qaytadan boshlang.",
                        reply_markup=get_back_button()
                    )
                    context.user_data['state'] = None
            except:
                await update.message.reply_text("❌ Noto'g'ri format! Qayta kiriting:")
            return
        
        # Tovar qo'shish - sotilish narx
        if state == ADD_PRODUCT_SELLING:
            try:
                if 'price_currency' in context.user_data:
                    currency = context.user_data['price_currency']
                    value = float(text.replace(',', '.'))
                    
                    if currency == 'usd':
                        context.user_data['new_product']['selling_usd'] = value
                    else:
                        context.user_data['new_product']['selling_uzs'] = value
                    
                    context.user_data.pop('price_currency', None)
                    context.user_data['state'] = ADD_PRODUCT_QUANTITY
                    
                    await update.message.reply_text(
                        "📦 Soni (dona):",
                        reply_markup=get_cancel_button()
                    )
                else:
                    await update.message.reply_text("❌ Xatolik. Qaytadan boshlang.")
                    context.user_data['state'] = None
            except:
                await update.message.reply_text("❌ Noto'g'ri format! Qayta kiriting:")
            return
        
        # Tovar qo'shish - soni
        if state == ADD_PRODUCT_QUANTITY:
            try:
                context.user_data['new_product']['quantity'] = int(text)
                context.user_data['state'] = ADD_PRODUCT_KEYWORDS
                await update.message.reply_text(
                    "🔑 Kalit so'zlar (vergul bilan ajrating, yoki /skip):",
                    reply_markup=get_cancel_button()
                )
            except:
                await update.message.reply_text("❌ Noto'g'ri format! Qayta kiriting:")
            return
        
        # Tovar qo'shish - kalit so'zlar
        if state == ADD_PRODUCT_KEYWORDS:
            context.user_data['new_product']['keywords'] = text if text != "/skip" else ""
            
            # Kategoriya tanlash
            categories = session.query(Category).all()
            if categories:
                buttons = []
                for cat in categories:
                    buttons.append([InlineKeyboardButton(cat.name, callback_data=f"select_cat_{cat.id}")])
                buttons.append([InlineKeyboardButton("➕ Yangi kategoriya", callback_data="add_new_category")])
                buttons.append([InlineKeyboardButton("🔙 Bekor qilish", callback_data="main_menu")])
                
                await update.message.reply_text(
                    "📂 Kategoriyani tanlang:",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                context.user_data['state'] = None
            else:
                context.user_data['state'] = ADD_PRODUCT_CATEGORY
                await update.message.reply_text(
                    "📂 Yangi kategoriya nomini kiriting:",
                    reply_markup=get_cancel_button()
                )
            return
        
        # Kategoriya qo'shish
        if state == ADD_PRODUCT_CATEGORY:
            category_name = text.strip()
            parent_id = context.user_data.get('new_category_parent')
            
            # Kategoriya mavjudligini tekshirish
            existing = session.query(Category).filter_by(name=category_name).first()
            if existing:
                category_id = existing.id
            else:
                category = Category(name=category_name, parent_id=parent_id)
                session.add(category)
                session.flush()
                category_id = category.id
            
            if 'new_product' in context.user_data:
                # Tovar qo'shish
                context.user_data['new_product']['category_id'] = category_id
                
                product = Product(
                    name=context.user_data['new_product']['name'],
                    category_id=category_id,
                    purchase_price_usd=context.user_data['new_product'].get('purchase_usd', 0),
                    purchase_price_uzs=context.user_data['new_product'].get('purchase_uzs', 0),
                    selling_price_usd=context.user_data['new_product'].get('selling_usd', 0),
                    selling_price_uzs=context.user_data['new_product'].get('selling_uzs', 0),
                    quantity=context.user_data['new_product'].get('quantity', 0),
                    keywords=context.user_data['new_product'].get('keywords', ''),
                    media_group_message_id=context.user_data['new_product'].get('media_message_id')
                )
                session.add(product)
                session.commit()
                
                await update.message.reply_text(
                    "✅ Tovar muvaffaqiyatli qo'shildi!",
                    reply_markup=get_back_button()
                )
                
                # Tozalash
                if 'new_product' in context.user_data:
                    del context.user_data['new_product']
                if 'new_category_parent' in context.user_data:
                    del context.user_data['new_category_parent']
            else:
                # Faqat kategoriya qo'shish
                session.commit()
                await update.message.reply_text(
                    f"✅ Kategoriya qo'shildi: {category_name}",
                    reply_markup=get_back_button("categories")
                )
                if 'new_category_parent' in context.user_data:
                    del context.user_data['new_category_parent']
            
            context.user_data['state'] = None
            return
        
        # Tahrirlash
        if state == EDIT_WAITING:
            product_id = context.user_data.get('editing_product')
            field = context.user_data.get('editing_field')
            
            product = session.query(Product).filter_by(id=product_id).first()
            if not product:
                await update.message.reply_text("❌ Tovar topilmadi!")
                context.user_data['state'] = None
                return
            
            # Eski ma'lumotlarni saqlash
            old_data = {
                'purchase_usd': product.purchase_price_usd,
                'purchase_uzs': product.purchase_price_uzs,
                'selling_usd': product.selling_price_usd,
                'selling_uzs': product.selling_price_uzs,
                'quantity': product.quantity
            }
            
            # Yangilash
            if field == 'name':
                product.name = text
            elif field in ['purchase_usd', 'purchase_uzs', 'selling_usd', 'selling_uzs']:
                try:
                    value = float(text.replace(',', '.'))
                    setattr(product, field, value)
                except:
                    await update.message.reply_text("❌ Noto'g'ri format!")
                    return
            elif field == 'quantity':
                try:
                    product.quantity = int(text)
                except:
                    await update.message.reply_text("❌ Noto'g'ri format!")
                    return
            elif field == 'keywords':
                product.keywords = text
            
            # Tarixga qo'shish
            if field in ['purchase_usd', 'purchase_uzs', 'selling_usd', 'selling_uzs', 'quantity']:
                history = PriceHistory(
                    product_id=product.id,
                    old_purchase_usd=old_data['purchase_usd'],
                    old_purchase_uzs=old_data['purchase_uzs'],
                    old_selling_usd=old_data['selling_usd'],
                    old_selling_uzs=old_data['selling_uzs'],
                    old_quantity=old_data['quantity'],
                    new_purchase_usd=product.purchase_price_usd,
                    new_purchase_uzs=product.purchase_price_uzs,
                    new_selling_usd=product.selling_price_usd,
                    new_selling_uzs=product.selling_price_uzs,
                    new_quantity=product.quantity,
                    changed_by=user.id
                )
                session.add(history)
            
            session.commit()
            
            await update.message.reply_text(
                "✅ Ma'lumot yangilandi!",
                reply_markup=get_back_button(f"view_{product_id}")
            )
            
            context.user_data['state'] = None
            return
        
        # Import
        if state == IMPORT_WAITING:
            await update.message.reply_text("❌ Iltimos, Excel fayl yuboring!")
            return
        
        # Backup tiklash
        if state == RESTORE_WAITING:
            await update.message.reply_text("❌ Iltimos, .db fayl yuboring!")
            return
        
        # Ruxsat berish
        if state == GRANT_ACCESS_WAITING:
            try:
                target_id = int(text.strip())
                target_user = session.query(User).filter_by(telegram_id=target_id).first()
                
                if target_user:
                    target_user.is_authorized = True
                    session.commit()
                    await update.message.reply_text(
                        f"✅ Foydalanuvchi {target_user.first_name or 'User'} ga ruxsat berildi!",
                        reply_markup=get_back_button()
                    )
                    
                    try:
                        await context.bot.send_message(
                            target_id,
                            "✅ Sizga botdan foydalanish uchun ruxsat berildi!\n"
                            "/start ni bosing."
                        )
                    except:
                        pass
                else:
                    await update.message.reply_text(
                        "❌ Bunday ID li foydalanuvchi topilmadi!",
                        reply_markup=get_back_button()
                    )
            except:
                await update.message.reply_text(
                    "❌ Noto'g'ri format! ID raqam kiriting.",
                    reply_markup=get_back_button()
                )
            
            context.user_data['state'] = None
            return
    
    finally:
        session.close()

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rasm qabul qilish"""
    user = update.effective_user
    if not user or not update.message or not update.message.photo:
        return
    
    session = db_session()
    
    try:
        db_user = session.query(User).filter_by(telegram_id=user.id).first()
        if not db_user or (not db_user.is_authorized and not db_user.is_admin):
            return
        
        state = context.user_data.get('state')
        
        # Guruhni tekshirish
        group = session.query(BotGroup).first()
        if not group:
            await update.message.reply_text(
                "❌ Bot hali hech qanday guruhga qo'shilmagan!\n"
                "Avval botni guruhga qo'shib, admin qiling."
            )
            return
        
        # Tovar qo'shish - rasm
        if state == ADD_PRODUCT_PHOTO:
            try:
                photo = update.message.photo[-1]
                
                # Rasmni guruhga yuborish
                sent_message = await context.bot.send_photo(
                    chat_id=group.group_id,
                    photo=photo.file_id,
                    caption=f"#{context.user_data['new_product']['name'].replace(' ', '_')}"
                )
                
                context.user_data['new_product']['media_message_id'] = sent_message.message_id
                context.user_data['new_product']['media_file_id'] = photo.file_id
                
                # Kelgan narxni so'rash
                context.user_data['state'] = ADD_PRODUCT_PURCHASE
                await update.message.reply_text(
                    "💰 Kelgan narx turini tanlang:",
                    reply_markup=get_price_type_keyboard(0, 'purchase')
                )
                
            except Exception as e:
                logger.error(f"Rasm yuborishda xatolik: {e}")
                await update.message.reply_text(
                    "❌ Rasmni saqlashda xatolik. Qaytadan urinib ko'ring.",
                    reply_markup=get_cancel_button()
                )
        
        # Tahrirlash - rasm
        elif state == EDIT_WAITING:
            field = context.user_data.get('editing_field')
            if field == 'photo':
                product_id = context.user_data.get('editing_product')
                product = session.query(Product).filter_by(id=product_id).first()
                
                if product:
                    try:
                        photo = update.message.photo[-1]
                        
                        # Yangi rasmni guruhga yuborish
                        sent_message = await context.bot.send_photo(
                            chat_id=group.group_id,
                            photo=photo.file_id,
                            caption=f"#{product.name.replace(' ', '_')}"
                        )
                        
                        product.media_group_message_id = sent_message.message_id
                        session.commit()
                        
                        await update.message.reply_text(
                            "✅ Rasm yangilandi!",
                            reply_markup=get_back_button(f"view_{product_id}")
                        )
                    except Exception as e:
                        logger.error(f"Rasm yangilashda xatolik: {e}")
                        await update.message.reply_text(
                            "❌ Rasmni yangilashda xatolik!",
                            reply_markup=get_back_button(f"view_{product_id}")
                        )
                
                context.user_data['state'] = None
    
    finally:
        session.close()

async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hujjat qabul qilish"""
    user = update.effective_user
    if not user or not update.message or not update.message.document:
        return
    
    session = db_session()
    
    try:
        db_user = session.query(User).filter_by(telegram_id=user.id).first()
        if not db_user or not db_user.is_admin:
            await update.message.reply_text("❌ Bu amal faqat admin uchun!")
            return
        
        document = update.message.document
        file_name = document.file_name or ""
        file_size = document.file_size or 0
        
        # 50 MB dan katta fayllarni qabul qilmaslik
        if file_size > 50 * 1024 * 1024:
            await update.message.reply_text("❌ Fayl hajmi 50 MB dan kichik bo'lishi kerak!")
            return
        
        state = context.user_data.get('state')
        
        # Excel fayl import
        if state == IMPORT_WAITING and (file_name.endswith('.xlsx') or file_name.endswith('.xls')):
            file = await document.get_file()
            filename = f"data/import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            await file.download_to_drive(filename)
            
            await update.message.reply_text("⏳ Import qilinmoqda...")
            
            success, message = await import_from_excel(filename, clear_existing=True)
            
            if success:
                await update.message.reply_text(
                    f"✅ {message}",
                    reply_markup=get_back_button()
                )
            else:
                await update.message.reply_text(
                    f"❌ {message}",
                    reply_markup=get_back_button()
                )
            
            os.remove(filename)
            context.user_data['state'] = None
        
        # Backup fayl tiklash
        elif state == RESTORE_WAITING and file_name.endswith('.db'):
            file = await document.get_file()
            filename = f"data/restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            await file.download_to_drive(filename)
            
            await update.message.reply_text("⏳ Backup tiklanmoqda...")
            
            try:
                restore_database(filename)
                await update.message.reply_text(
                    "✅ Backup tiklandi! Botni qayta ishga tushiring.",
                    reply_markup=get_back_button()
                )
            except Exception as e:
                await update.message.reply_text(
                    f"❌ Xatolik: {str(e)}",
                    reply_markup=get_back_button()
                )
            
            os.remove(filename)
            context.user_data['state'] = None
        
        else:
            await update.message.reply_text(
                "❌ Noto'g'ri format yoki holat!",
                reply_markup=get_back_button()
            )
    
    finally:
        session.close()

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xatoliklarni qayd etish"""
    logger.error(f"Xatolik yuz berdi: {context.error}")
    
    try:
        if update and update.effective_chat:
            await context.bot.send_message(
                update.effective_chat.id,
                                "❌ Xatolik yuz berdi. Admin bilan bog'laning."
            )
    except:
        pass

# ==================== ASOSIY FUNKSIYA ====================

def main():
    """Asosiy funksiya"""
    
    print("""
    ╔════════════════════════════════════╗
    ║     DO'KON BOSHQARUVI BOTI         ║
    ║         @maestro_o                  ║
    ╚════════════════════════════════════╝
    """)
    
    # Muhitni tekshirish
    logger.info("🔍 Muhit tekshirilmoqda...")
    
    errors = []
    
    if not BOT_TOKEN or BOT_TOKEN == "7847347173:AAF_cQ8p6UZbCQk5FqWXg9nIf0Q2jzzU-yY":
        errors.append("❌ BOT_TOKEN noto'g'ri yoki kiritilmagan!")
    
    if not ADMIN_ID or ADMIN_ID == 0:
        errors.append("❌ ADMIN_ID noto'g'ri yoki kiritilmagan!")
    
    if errors:
        logger.error("❌ Muhit tekshiruvida xatoliklar topildi:")
        for error in errors:
            logger.error(error)
        
        print("\n" + "="*50)
        print("❌ XATOLIK! Bot ishga tushirilmadi!")
        print("Sabablari:")
        for error in errors:
            print(f"  • {error}")
        print("\n💡 Yechim:")
        print("  1. .env faylini tekshiring")
        print("  2. Barcha kerakli o'zgaruvchilarni kiriting")
        print("  3. Qaytadan urinib ko'ring")
        print("="*50)
        
        sys.exit(1)
    
    logger.info("✅ Muhit tekshiruvi muvaffaqiyatli o'tdi")
    
    # Ma'lumotlar bazasini ishga tushirish
    logger.info("🗄 Ma'lumotlar bazasi ishga tushirilmoqda...")
    try:
        init_db()
        logger.info("✅ Ma'lumotlar bazasi tayyor")
    except Exception as e:
        logger.error(f"❌ Ma'lumotlar bazasi xatoligi: {e}")
        sys.exit(1)
    
    # Botni yaratish
    logger.info("🤖 Bot yaratilmoqda...")
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        logger.info("✅ Bot yaratildi")
    except Exception as e:
        logger.error(f"❌ Bot yaratishda xatolik: {e}")
        sys.exit(1)
    
    # Handlerlarni o'rnatish
    logger.info("🔧 Handlerlar o'rnatilmoqda...")
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    application.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    application.add_error_handler(error_handler)
    
    logger.info("✅ Handlerlar o'rnatildi")
    
    # Botni ishga tushirish
    print("\n" + "="*50)
    print("🚀 BOT ISHGA TUSHIRILMOQDA...")
    print("="*50)
    tashkent_time = get_tashkent_time()
    print(f"🕐 Vaqt: {tashkent_time.strftime('%H:%M:%S')}")
    print(f"📅 Sana: {tashkent_time.strftime('%d.%m.%Y')}")
    print("="*50 + "\n")
    
    logger.info("🎉 Bot muvaffaqiyatli ishga tushdi!")
    logger.info("📡 Polling boshlanmoqda...")
    
    try:
        application.run_polling(allowed_updates=['message', 'callback_query'], drop_pending_updates=True)
    except KeyboardInterrupt:
        logger.info("👋 Bot to'xtatildi (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ Bot ishga tushishda xatolik: {e}")
        sys.exit(1)
    finally:
        logger.info("👋 Bot ishdan to'xtadi")
        print("\n" + "="*50)
        print("👋 BOT TO'XTATILDI")
        print("="*50)

if __name__ == '__main__':
    main()
