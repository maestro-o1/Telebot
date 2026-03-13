#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Do'kon boshqaruvi uchun Telegram bot
Muallif: @maestro_o
Versiya: 4.0 - To'liq tuzatilgan
"""

import logging
import os
import sys
from datetime import datetime
import pandas as pd
import shutil
from typing import Dict, List, Optional

# Telegram bot kutubxonasi
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

# ==================== KONFIGURATSIYA ====================
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

# ==================== MA'LUMOTLAR BAZASI ====================
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session

# Ma'lumotlar bazasini yaratish
os.makedirs('data', exist_ok=True)
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
    branch_type = Column(String, default='main')  # 'main', 'parasite'
    branch_name = Column(String, nullable=True)   # 'chiroqchi', 'shahrisabz'
    parent_id = Column(Integer, nullable=True)
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
    
    # Qaysi qatlamga tegishli
    owner_type = Column(String, default='main')  # 'main', 'parasite'
    owner_id = Column(Integer, nullable=True)
    
    # Narxlar
    purchase_price_usd = Column(Float, default=0)
    purchase_price_uzs = Column(Float, default=0)
    selling_price_usd = Column(Float, default=0)
    selling_price_uzs = Column(Float, default=0)
    
    quantity = Column(Integer, default=0)
    media_group_message_id = Column(Integer, nullable=True)
    media_file_id = Column(String, nullable=True)
    keywords = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
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
        Base.metadata.create_all(bind=engine)
        
        session = db_session()
        
        # Admin foydalanuvchini qo'shish
        admin = session.query(User).filter_by(telegram_id=ADMIN_ID).first()
        if not admin and ADMIN_ID != 0:
            admin = User(
                telegram_id=ADMIN_ID,
                username='admin',
                first_name='Admin',
                is_admin=True,
                is_authorized=True,
                branch_type='main',
                branch_name='admin'
            )
            session.add(admin)
            session.commit()
            logger.info(f"✅ Admin qo'shildi: {ADMIN_ID}")
        
        # Kategoriyalarni yaratish
        categories = ['Elektronika', 'Avto qismlar', 'Maishiy texnika', 'Qurilish', 'Boshqa']
        for cat_name in categories:
            cat = session.query(Category).filter_by(name=cat_name).first()
            if not cat:
                cat = Category(name=cat_name)
                session.add(cat)
        
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

# ==================== KEYBOARDS ====================

def get_main_keyboard(user_is_admin=False, user_branch_type=None, user_branch_name=None):
    """Asosiy menyu tugmalari"""
    buttons = [
        [InlineKeyboardButton("🔍 Qidirish", callback_data="search")],
        [InlineKeyboardButton("📂 Kategoriyalar", callback_data="categories")],
    ]
    
    if user_is_admin:
        buttons.extend([
            [InlineKeyboardButton("📊 Qatlamlar (Layers)", callback_data="layers")],
            [InlineKeyboardButton("📊 Statistika", callback_data="stats")],
            [InlineKeyboardButton("➕ Tovar qo'shish", callback_data="add_product")],
            [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="users")],
            [InlineKeyboardButton("📥 Eksport / 📤 Import", callback_data="export_import")],
            [InlineKeyboardButton("👤 Ruxsat berish", callback_data="grant_access")],
        ])
    elif user_branch_type == 'parasite':
        buttons.extend([
            [InlineKeyboardButton(f"🐝 {user_branch_name} tovarlari", callback_data="my_products")],
        ])
    
    buttons.append([InlineKeyboardButton("❌ Yopish", callback_data="close")])
    return InlineKeyboardMarkup(buttons)

def get_back_button(callback_data="main_menu"):
    """Orqaga tugmasi"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Orqaga", callback_data=callback_data)],
        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
    ])

def get_cancel_button():
    """Bekor qilish tugmasi"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel")],
        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
    ])

def get_layers_keyboard():
    """Qatlamlar menyusi"""
    buttons = [
        [InlineKeyboardButton("👑 Asosiy qatlam", callback_data="layer_main")],
        [InlineKeyboardButton("🐝 Chiroqchi qatlami", callback_data="layer_chiroqchi")],
        [InlineKeyboardButton("🔙 Bosh menyu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_categories_keyboard(categories, parent_id=None, is_admin=False, branch=None):
    """Kategoriyalar ro'yxati"""
    buttons = []
    
    for cat in categories:
        buttons.append([
            InlineKeyboardButton(f"📁 {cat['name']}", callback_data=f"cat_{cat['id']}")
        ])
    
    if is_admin and parent_id is not None:
        buttons.append([
            InlineKeyboardButton("➕ Kategoriya qo'shish", callback_data=f"add_cat_{parent_id}")
        ])
    
    buttons.append([InlineKeyboardButton("🔙 Bosh menyu", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)

def get_category_detail_keyboard(category_id, subcats, products, is_admin=False, branch=None):
    """Kategoriya ichidagi tugmalar"""
    buttons = []
    
    # Pastki kategoriyalar
    for sc in subcats:
        buttons.append([InlineKeyboardButton(f"📁 {sc.name}", callback_data=f"cat_{sc.id}")])
    
    # Tovarlar
    for p in products:
        emoji = "👑" if p.owner_type == 'main' else "🐝"
        buttons.append([InlineKeyboardButton(f"{emoji} {p.name}", callback_data=f"view_{p.id}")])
    
    # Qo'shish tugmalari
    if is_admin:
        buttons.append([InlineKeyboardButton("➕ Kategoriya qo'shish", callback_data=f"add_cat_{category_id}")])
        buttons.append([InlineKeyboardButton("➕ Tovar qo'shish", callback_data=f"add_product_cat_{category_id}")])
    elif branch:
        buttons.append([InlineKeyboardButton(f"➕ {branch} uchun tovar qo'shish", callback_data=f"add_product_cat_{category_id}_{branch}")])
    
    buttons.append([InlineKeyboardButton("🔙 Kategoriyalar", callback_data="categories")])
    buttons.append([InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(buttons)

def get_product_actions_keyboard(product_id, category_id, can_edit=False, can_delete=False):
    """Tovar amallari"""
    buttons = []
    
    if can_edit:
        buttons.append([InlineKeyboardButton("📝 Tahrirlash", callback_data=f"edit_{product_id}")])
    
    if can_delete:
        buttons.append([InlineKeyboardButton("🗑 O'chirish", callback_data=f"delete_{product_id}")])
    
    back_callback = f"cat_{category_id}" if category_id else "categories"
    buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data=back_callback)])
    buttons.append([InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")])
    
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
        [InlineKeyboardButton("🔙 Orqaga", callback_data=f"view_{product_id}")],
        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_price_type_keyboard(product_id, price_type):
    """Narx turini tanlash"""
    buttons = [
        [InlineKeyboardButton("💵 USD ($)", callback_data=f"set_{price_type}_usd_{product_id}")],
        [InlineKeyboardButton("💰 UZS (so'm)", callback_data=f"set_{price_type}_uzs_{product_id}")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data=f"edit_{product_id}")],
        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
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
        branch = f"[{user['branch_name']}]" if user['branch_name'] else ""
        name = user['first_name'] or f"User{user['id']}"
        username = user['username'] or 'no username'
        buttons.append([
            InlineKeyboardButton(
                f"{status} {branch} {name} (@{username})", 
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
        [InlineKeyboardButton("🔄 Qatlamni o'zgartirish", callback_data=f"change_branch_{user_id}")],
        [InlineKeyboardButton("🗑 O'chirish", callback_data=f"remove_user_{user_id}")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="users")],
        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_branch_keyboard(user_id):
    """Qatlam tanlash"""
    buttons = [
        [InlineKeyboardButton("👑 Asosiy (Admin)", callback_data=f"set_branch_main_{user_id}")],
        [InlineKeyboardButton("🐝 Chiroqchi", callback_data=f"set_branch_chiroqchi_{user_id}")],
        [InlineKeyboardButton("🏛 Shahrisabz", callback_data=f"set_branch_shahrisabz_{user_id}")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data=f"user_{user_id}")],
        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_access_request_keyboard():
    """Ruxsat so'rash tugmasi"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Ruxsat so'rash", callback_data="request_access")],
        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
    ])

def get_approve_reject_keyboard(request_id):
    """Tasdiqlash/Rad etish tugmalari"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_req_{request_id}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_req_{request_id}")
        ],
        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
    ])

# ==================== UTILS ====================

async def export_to_excel():
    """Excel formatida eksport qilish"""
    session = db_session()
    products = session.query(Product).filter_by(is_active=True).all()
    data = []
    
    for p in products:
        category = session.query(Category).filter_by(id=p.category_id).first()
        
        # Egani aniqlash
        owner_name = "Asosiy"
        if p.owner_type == 'parasite' and p.owner_id:
            owner = session.query(User).filter_by(id=p.owner_id).first()
            owner_name = owner.branch_name if owner else "Noma'lum"
        
        data.append({
            'ID': p.id,
            'Nomi': p.name or '',
            'Kategoriya': category.name if category else '',
            'Qatlam': 'Asosiy' if p.owner_type == 'main' else owner_name,
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
            
            # Qatlamni aniqlash
            owner_type = 'main'
            owner_id = None
            qatlam = str(row.get('Qatlam', 'Asosiy'))
            if qatlam != 'Asosiy':
                owner = session.query(User).filter_by(branch_name=qatlam).first()
                if owner:
                    owner_type = 'parasite'
                    owner_id = owner.id
            
            # Tovarni yaratish
            product = Product(
                name=str(row.get('Nomi', '')),
                category_id=category_id,
                owner_type=owner_type,
                owner_id=owner_id,
                purchase_price_usd=float(row.get('Kelgan narxi ($)', 0) or 0),
                purchase_price_uzs=float(row.get('Kelgan narxi (so\'m)', 0) or 0),
                selling_price_usd=float(row.get('Sotilish narxi ($)', 0) or 0),
                selling_price_uzs=float(row.get('Sotilish narxi (so\'m)', 0) or 0),
                quantity=int(row.get('Soni', 0) or 0),
                keywords=str(row.get('Kalit so\'zlar', '')),
                media_group_message_id=row.get('Rasm ID') if pd.notna(row.get('Rasm ID')) else None,
                is_active=True
            )
            session.add(product)
        
        session.commit()
        return True, "Import muvaffaqiyatli yakunlandi"
    
    except Exception as e:
        session.rollback()
        return False, f"Xatolik: {str(e)}"
    
    finally:
        session.close()

async def get_product_info_text(product, owner_name="Asosiy"):
    """Tovar ma'lumotlarini matn ko'rinishida olish"""
    text = f"📦 <b>{product.name}</b>\n\n"
    
    text += f"👤 <b>Egasi:</b> {owner_name}\n"
    text += f"📊 <b>Qatlam:</b> {'Asosiy' if product.owner_type == 'main' else 'Chiroqchi'}\n\n"
    
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
    
    text += f"\n📅 <b>Qo'shilgan:</b> {product.created_at.strftime('%d.%m.%Y %H:%M')}"
    
    return text

# ==================== HANDLERS ====================

# Conversation states
(SEARCH, ADD_PRODUCT_NAME, ADD_PRODUCT_PHOTO, ADD_PRODUCT_PURCHASE_USD,
 ADD_PRODUCT_PURCHASE_UZS, ADD_PRODUCT_SELLING_USD, ADD_PRODUCT_SELLING_UZS,
 ADD_PRODUCT_QUANTITY, ADD_PRODUCT_KEYWORDS, ADD_PRODUCT_CATEGORY,
 EDIT_WAITING, IMPORT_WAITING, RESTORE_WAITING, GRANT_ACCESS_WAITING) = range(14)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start komandasi"""
    user = update.effective_user
    if not user:
        return
    
    session = db_session()
    
    try:
        db_user = session.query(User).filter_by(telegram_id=user.id).first()
        
        if not db_user:
            db_user = User(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                is_authorized=False,
                branch_type='main',
                branch_name='main'
            )
            session.add(db_user)
            session.commit()
            logger.info(f"✅ Yangi foydalanuvchi qo'shildi: {user.id}")
        
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
                logger.info(f"✅ Yangi guruh qo'shildi: {update.message.chat.id}")
            
            await update.message.reply_text(
                f"✅ Bot guruhga qo'shildi!\n"
                f"📌 Guruh ID: {update.message.chat.id}\n"
                f"📝 Guruh nomi: {update.message.chat.title}"
            )
            return
        
        # Shaxsiy chat
        if db_user.is_admin:
            # Asosiy qatlam statistikasi
            main_products = session.query(Product).filter_by(owner_type='main', is_active=True).count()
            chiroqchi_products = session.query(Product).filter_by(owner_type='parasite', is_active=True).count()
            
            # Chiroqchi foydalanuvchilar
            chiroqchi_users = session.query(User).filter_by(branch_type='parasite', is_authorized=True).all()
            
            text = (f"👋 Xush kelibsiz Admin!\n\n"
                    f"📊 <b>QATLAMLAR STATISTIKASI</b>\n"
                    f"👑 Asosiy qatlam: {main_products} ta tovar\n")
            
            if chiroqchi_users:
                for cu in chiroqchi_users:
                    user_products = session.query(Product).filter_by(
                        owner_type='parasite', 
                        owner_id=cu.id,
                        is_active=True
                    ).count()
                    text += f"🐝 {cu.branch_name}: {user_products} ta tovar\n"
            else:
                text += f"🐝 Chiroqchi qatlami: {chiroqchi_products} ta tovar\n"
            
            text += f"\n📌 <b>Qatlamlar haqida:</b>\n"
            text += f"• Asosiy qatlam - siz va Shahrisabz ko'rasiz\n"
            text += f"• Chiroqchi qatlami - faqat Chiroqchi o'zi ko'radi\n\n"
            text += f"Kerakli bo'limni tanlang:"
            
            await update.message.reply_text(
                text, 
                reply_markup=get_main_keyboard(user_is_admin=True),
                parse_mode='HTML'
            )
            logger.info(f"✅ Admin bosh menyu: {user.id}")
            
        elif db_user.branch_type == 'parasite':
            # Parazit (Chiroqchi) uchun
            my_products = session.query(Product).filter_by(
                owner_type='parasite', 
                owner_id=db_user.id,
                is_active=True
            ).count()
            
            main_products = session.query(Product).filter_by(
                owner_type='main',
                is_active=True
            ).count()
            
            text = (f"👋 Xush kelibsiz {db_user.branch_name}!\n\n"
                    f"📊 <b>SIZNING STATISTIKANGIZ</b>\n"
                    f"🐝 Sizning tovarlaringiz: {my_products} ta\n"
                    f"👑 Asosiy tovarlar: {main_products} ta\n\n"
                    f"📌 <b>Ma'lumot:</b>\n"
                    f"• Asosiy tovarlar - Admin qo'shgan, hamma ko'radi\n"
                    f"• Sizning tovarlaringiz - faqat siz ko'rasiz\n\n"
                    f"Kerakli bo'limni tanlang:")
            
            await update.message.reply_text(
                text, 
                reply_markup=get_main_keyboard(
                    user_is_admin=False, 
                    user_branch_type='parasite',
                    user_branch_name=db_user.branch_name
                ),
                parse_mode='HTML'
            )
            logger.info(f"✅ Chiroqchi bosh menyu: {db_user.branch_name}")
            
        elif db_user.is_authorized:
            # Shahrisabz yoki boshqa foydalanuvchilar
            text = (f"👋 Xush kelibsiz {user.first_name}!\n\n"
                    f"Kerakli bo'limni tanlang:")
            await update.message.reply_text(
                text, 
                reply_markup=get_main_keyboard(user_is_admin=False)
            )
            logger.info(f"✅ Foydalanuvchi bosh menyu: {user.id}")
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
            logger.info(f"❌ Ruxsatsiz foydalanuvchi: {user.id}")
    
    except Exception as e:
        logger.error(f"Start handlerda xatolik: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")
    
    finally:
        session.close()

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yordam komandasi"""
    help_text = """
🤖 <b>BOT HAQIDA MA'LUMOT</b>

<b>🔍 Qidirish:</b>
• Tovar nomi yoki kalit so'z bilan qidiring

<b>📂 Kategoriyalar:</b>
• Kategoriyalar bo'yicha tovarlarni ko'rish
• Kategoriya ichida kategoriya ochish
• Kategoriyaga tovar qo'shish

<b>📊 Qatlamlar (Admin):</b>
• 👑 Asosiy qatlam - Admin va Shahrisabz
• 🐝 Chiroqchi qatlami - faqat Chiroqchi

<b>➕ Tovar qo'shish (Admin):</b>
• Nomi, rasmi, narxlari
• USD yoki UZS tanlash

<b>👥 Foydalanuvchilar (Admin):</b>
• Ruxsat berish/olib tashlash
• Qatlamni o'zgartirish

<b>📥 Eksport/Import (Admin):</b>
• Excel formatida eksport/import
• Backup yuklab olish/tiklash

📞 <b>Admin:</b> @maestro_o
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
        logger.info(f"Tugma bosildi: {data} - User: {user.id}")
        
        # Yopish
        if data == "close":
            await query.delete_message()
            return
        
        # Bekor qilish
        if data == "cancel":
            context.user_data.clear()
            await query.edit_message_text(
                "❌ Bekor qilindi.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
                ])
            )
            return
        
        # Asosiy menyu
        if data == "main_menu":
            await start(update, context)
            return
        
        # Ruxsat so'rash
        if data == "request_access":
            existing = session.query(AccessRequest).filter_by(
                user_id=db_user.id, status='pending'
            ).first()
            
            if existing:
                await query.edit_message_text(
                    "⏳ Sizning so'rovingiz already yuborilgan. Tasdiqlanishini kuting.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
                    ])
                )
            else:
                request = AccessRequest(user_id=db_user.id)
                session.add(request)
                session.commit()
                logger.info(f"Yangi ruxsat so'rovi: {db_user.id}")
                
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
                    "✅ So'rovingiz yuborildi! Tasdiqlanishini kuting.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
                    ])
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
                logger.info(f"So'rov tasdiqlandi: {request.user.id}")
                
                try:
                    await context.bot.send_message(
                        request.user.telegram_id,
                        "✅ Sizning so'rovingiz tasdiqlandi! Endi botdan foydalanishingiz mumkin.\n"
                        "Ishlatish uchun /start ni bosing."
                    )
                except Exception as e:
                    logger.error(f"Foydalanuvchiga xabar yuborishda xatolik: {e}")
                
                await query.edit_message_text(
                    f"✅ Foydalanuvchi {request.user.first_name} tasdiqlandi!",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="users")],
                        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
                    ])
                )
            else:
                request.status = 'rejected'
                session.commit()
                logger.info(f"So'rov rad etildi: {request.user.id}")
                
                try:
                    await context.bot.send_message(
                        request.user.telegram_id,
                        "❌ Sizning so'rovingiz rad etildi."
                    )
                except Exception as e:
                    logger.error(f"Foydalanuvchiga xabar yuborishda xatolik: {e}")
                
                await query.edit_message_text(
                    f"❌ Foydalanuvchi {request.user.first_name} rad etildi!",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="users")],
                        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
                    ])
                )
            return
        
        # Qatlamlar (faqat admin)
        if data == "layers":
            if not db_user.is_admin:
                await query.edit_message_text("❌ Bu bo'lim faqat Admin uchun!")
                return
            
            # Qatlamlar statistikasi
            main_count = session.query(Product).filter_by(owner_type='main', is_active=True).count()
            chiroqchi_count = session.query(Product).filter_by(owner_type='parasite', is_active=True).count()
            
            # Chiroqchi foydalanuvchilarni topish
            chiroqchi_users = session.query(User).filter_by(branch_type='parasite', is_authorized=True).all()
            
            text = (f"📊 <b>QATLAMLAR (LAYERS)</b>\n\n"
                    f"👑 <b>Asosiy qatlam:</b>\n"
                    f"   • Tovarlar soni: {main_count} ta\n"
                    f"   • Kimlar ko'radi: Admin, Shahrisabz\n\n"
                    f"🐝 <b>Chiroqchi qatlami:</b>\n"
                    f"   • Jami tovarlar: {chiroqchi_count} ta\n")
            
            if chiroqchi_users:
                text += f"   • Foydalanuvchilar:\n"
                for cu in chiroqchi_users:
                    user_products = session.query(Product).filter_by(
                        owner_type='parasite', 
                        owner_id=cu.id,
                        is_active=True
                    ).count()
                    text += f"      - {cu.branch_name}: {user_products} ta tovar\n"
            else:
                text += "   • Hali foydalanuvchilar yo'q\n"
            
            text += f"\n📌 Qaysi qatlamni ko'rmoqchisiz?"
            
            await query.edit_message_text(
                text,
                reply_markup=get_layers_keyboard(),
                parse_mode='HTML'
            )
            return
        
        # Asosiy qatlam
        if data == "layer_main":
            await layer_main_handler(update, context, session, db_user)
            return
        
        # Chiroqchi qatlami
        if data == "layer_chiroqchi":
            await layer_chiroqchi_handler(update, context, session, db_user)
            return
        
        # Mening tovarlarim (parazit uchun)
        if data == "my_products":
            if db_user.branch_type != 'parasite':
                await query.edit_message_text("❌ Bu bo'lim faqat Chiroqchi uchun!")
                return
            
            products = session.query(Product).filter_by(
                owner_type='parasite',
                owner_id=db_user.id,
                is_active=True
            ).all()
            
            text = f"🐝 <b>{db_user.branch_name} tovarlari</b>\n\n"
            text += f"Jami tovarlar: {len(products)} ta\n\n"
            
            if not products:
                text += "Sizning tovarlaringiz yo'q."
                await query.edit_message_text(text, reply_markup=get_back_button(), parse_mode='HTML')
                return
            
            # Kategoriyalar bo'yicha guruhlash
            categories = {}
            for p in products:
                cat_name = "Kategoriyasiz"
                if p.category_id:
                    cat = session.query(Category).filter_by(id=p.category_id).first()
                    if cat:
                        cat_name = cat.name
                
                if cat_name not in categories:
                    categories[cat_name] = []
                categories[cat_name].append(p)
            
            for cat_name, cat_products in categories.items():
                text += f"\n📂 <b>{cat_name}</b> ({len(cat_products)} ta):\n"
                for p in cat_products[:5]:
                    text += f"   • {p.name} - {p.quantity} dona\n"
                if len(cat_products) > 5:
                    text += f"     ... va yana {len(cat_products) - 5} ta\n"
            
            # Tugmalar
            buttons = []
            for p in products[:10]:
                buttons.append([InlineKeyboardButton(f"🐝 {p.name}", callback_data=f"view_{p.id}")])
            
            buttons.append([InlineKeyboardButton("➕ Tovar qo'shish", callback_data=f"add_product_parasite")])
            buttons.append([InlineKeyboardButton("🔙 Bosh menyu", callback_data="main_menu")])
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode='HTML'
            )
            return
        
        # Kategoriyalar
        if data == "categories":
            categories = session.query(Category).filter_by(parent_id=None).all()
            cat_list = [{'id': c.id, 'name': c.name} for c in categories]
            
            text = "📂 <b>Kategoriyalar</b>\n\n"
            if not cat_list:
                text += "Hali kategoriyalar mavjud emas."
            
            await query.edit_message_text(
                text,
                reply_markup=get_categories_keyboard(
                    cat_list, 
                    parent_id=None, 
                    is_admin=db_user.is_admin,
                    branch=db_user.branch_name if db_user.branch_type == 'parasite' else None
                ),
                parse_mode='HTML'
            )
            return
        
        # Kategoriya ichiga kirish
        if data.startswith("cat_"):
            category_id = int(data.split("_")[1])
            await category_detail_handler(update, context, session, db_user, category_id)
            return
        
        # Tovarni ko'rish
        if data.startswith("view_"):
            await view_product_handler(update, context, session, db_user)
            return
        
        # Tahrirlash
        if data.startswith("edit_"):
            await edit_product_handler(update, context, session, db_user)
            return
        
        # Narx turini tanlash
        if data.startswith("set_purchase_usd_") or data.startswith("set_purchase_uzs_") or \
           data.startswith("set_selling_usd_") or data.startswith("set_selling_uzs_"):
            await set_price_handler(update, context, session, db_user)
            return
        
        # O'chirish
        if data.startswith("delete_"):
            await delete_product_handler(update, context, session, db_user)
            return
        
        # Tovar qo'shish
        if data.startswith("add_product_"):
            await add_product_start_handler(update, context, session, db_user)
            return
        
        # Kategoriya qo'shish
        if data.startswith("add_cat_"):
            await add_category_handler(update, context, session, db_user)
            return
        
        # Foydalanuvchilar
        if data == "users":
            if not db_user.is_admin:
                await query.edit_message_text("❌ Ruxsat yo'q!")
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
                    'branch_name': u.branch_name or 'main'
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
            
            await user_detail_handler(update, context, session, db_user)
            return
        
        # Foydalanuvchini tasdiqlash
        if data.startswith("approve_") and not data.startswith("approve_req_"):
            if not db_user.is_admin:
                await query.edit_message_text("❌ Ruxsat yo'q!")
                return
            
            await approve_user_handler(update, context, session, db_user)
            return
        
        # Foydalanuvchini rad etish
        if data.startswith("reject_") and not data.startswith("reject_req_"):
            if not db_user.is_admin:
                await query.edit_message_text("❌ Ruxsat yo'q!")
                return
            
            await reject_user_handler(update, context, session, db_user)
            return
        
        # Qatlamni o'zgartirish
        if data.startswith("change_branch_"):
            if not db_user.is_admin:
                await query.edit_message_text("❌ Ruxsat yo'q!")
                return
            
            await change_branch_handler(update, context, session, db_user)
            return
        
        # Qatlamni o'rnatish
        if data.startswith("set_branch_"):
            if not db_user.is_admin:
                await query.edit_message_text("❌ Ruxsat yo'q!")
                return
            
            await set_branch_handler(update, context, session, db_user)
            return
        
        # Foydalanuvchini o'chirish
        if data.startswith("remove_user_"):
            if not db_user.is_admin:
                await query.edit_message_text("❌ Ruxsat yo'q!")
                return
            
            await remove_user_handler(update, context, session, db_user)
            return
        
        # Statistika
        if data == "stats":
            if not db_user.is_admin and not db_user.can_edit:
                await query.edit_message_text("❌ Sizda statistika ko'rish huquqi yo'q!")
                return
            
            await stats_handler(update, context, session, db_user)
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
            
            await export_excel_handler(update, context, session, db_user)
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
            
            await download_backup_handler(update, context, session, db_user)
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
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
                ])
            )
            logger.info(f"Baza tozalandi: {user.id}")
            return
        
    except Exception as e:
        logger.error(f"Button handlerda xatolik: {e}")
        await query.edit_message_text(f"❌ Xatolik: {str(e)}")
    
    finally:
        session.close()

# ==================== KATEGORIYA HANDLERLARI ====================

async def category_detail_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session, db_user, category_id):
    """Kategoriya ichidagi tovarlarni ko'rsatish"""
    query = update.callback_query
    
    category = session.query(Category).filter_by(id=category_id).first()
    
    if not category:
        await query.edit_message_text("❌ Kategoriya topilmadi!")
        return
    
    # Foydalanuvchi turiga qarab tovarlarni filterlash
    if db_user.is_admin:
        products = session.query(Product).filter_by(category_id=category_id, is_active=True).all()
    elif db_user.branch_type == 'parasite':
        products = session.query(Product).filter(
            (Product.category_id == category_id) & 
            (Product.is_active == True) &
            ((Product.owner_type == 'main') | 
             ((Product.owner_type == 'parasite') & (Product.owner_id == db_user.id)))
        ).all()
    else:
        products = session.query(Product).filter_by(
            category_id=category_id, 
            owner_type='main',
            is_active=True
        ).all()
    
    subcats = session.query(Category).filter_by(parent_id=category_id).all()
    
    text = f"📂 <b>{category.name}</b>\n\n"
    
    if subcats:
        text += "📁 <b>Pastki kategoriyalar:</b>\n"
        for sc in subcats:
            # Pastki kategoriyadagi tovarlar soni
            if db_user.is_admin:
                sc_products = session.query(Product).filter_by(category_id=sc.id, is_active=True).count()
            elif db_user.branch_type == 'parasite':
                sc_products = session.query(Product).filter(
                    (Product.category_id == sc.id) & 
                    (Product.is_active == True) &
                    ((Product.owner_type == 'main') | 
                     ((Product.owner_type == 'parasite') & (Product.owner_id == db_user.id)))
                ).count()
            else:
                sc_products = session.query(Product).filter_by(
                    category_id=sc.id, 
                    owner_type='main',
                    is_active=True
                ).count()
            
            text += f"• {sc.name} ({sc_products} ta tovar)\n"
        text += "\n"
    
    if products:
        text += "📦 <b>Tovarlar:</b>\n"
        for p in products:
            emoji = "👑" if p.owner_type == 'main' else "🐝"
            text += f"• {emoji} {p.name} - {p.quantity} dona\n"
            if p.selling_price_usd > 0:
                text += f"  💵 {p.selling_price_usd:,.0f}$"
            if p.selling_price_uzs > 0:
                text += f"  💰 {p.selling_price_uzs:,.0f} so'm"
            text += "\n"
    else:
        text += "Bu kategoriyada tovarlar yo'q."
    
    await query.edit_message_text(
        text, 
        reply_markup=get_category_detail_keyboard(
            category_id, 
            subcats, 
            products, 
            is_admin=db_user.is_admin,
            branch=db_user.branch_name if db_user.branch_type == 'parasite' else None
        ),
        parse_mode='HTML'
    )

async def add_category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session, db_user):
    """Kategoriya qo'shish"""
    query = update.callback_query
    data = query.data
    parent_id = int(data.split("_")[2])
    
    context.user_data['new_category_parent'] = parent_id
    context.user_data['state'] = ADD_PRODUCT_CATEGORY
    
    await query.edit_message_text(
        "📝 Yangi kategoriya nomini kiriting:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Orqaga", callback_data=f"cat_{parent_id}")],
            [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
        ])
    )

# ==================== TOVAR HANDLERLARI ====================

async def view_product_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session, db_user):
    """Tovar ma'lumotlarini ko'rsatish"""
    query = update.callback_query
    data = query.data
    product_id = int(data.split("_")[1])
    
    product = session.query(Product).filter_by(id=product_id).first()
    
    if not product:
        await query.edit_message_text("❌ Tovar topilmadi!")
        return
    
    # Egani aniqlash
    owner_name = "Asosiy"
    if product.owner_type == 'parasite' and product.owner_id:
        owner = session.query(User).filter_by(id=product.owner_id).first()
        owner_name = owner.branch_name if owner else "Noma'lum"
    
    text = await get_product_info_text(product, owner_name)
    
    # Rasmni ko'rsatish
    if product.media_group_message_id:
        try:
            group = session.query(BotGroup).first()
            if group:
                await context.bot.forward_message(
                    chat_id=update.effective_user.id,
                    from_chat_id=group.group_id,
                    message_id=product.media_group_message_id
                )
        except Exception as e:
            logger.error(f"Rasmni forward qilishda xatolik: {e}")
    
    # Tahrirlash huquqini tekshirish
    can_edit = False
    can_delete = False
    
    if db_user.is_admin:
        can_edit = True
        can_delete = True
    elif db_user.branch_type == 'parasite' and product.owner_id == db_user.id:
        can_edit = True
        can_delete = True
    
    await query.edit_message_text(
        text,
        reply_markup=get_product_actions_keyboard(
            product_id, 
            product.category_id, 
            can_edit, 
            can_delete
        ),
        parse_mode='HTML'
    )

async def add_product_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session, db_user):
    """Tovar qo'shishni boshlash"""
    query = update.callback_query
    data = query.data
    parts = data.split("_")
    
    context.user_data['new_product'] = {}
    
    if len(parts) >= 4 and parts[2] == 'cat':
        category_id = int(parts[3])
        context.user_data['new_product']['category_id'] = category_id
        
        if len(parts) >= 5:
            branch = parts[4]
            context.user_data['new_product']['branch'] = branch
        elif db_user.branch_type == 'parasite':
            context.user_data['new_product']['branch'] = db_user.branch_name
        else:
            context.user_data['new_product']['branch'] = 'main'
    elif parts[2] == 'parasite':
        context.user_data['new_product']['branch'] = db_user.branch_name
    
    context.user_data['new_product']['owner_type'] = 'main' if db_user.is_admin else 'parasite'
    context.user_data['new_product']['owner_id'] = None if db_user.is_admin else db_user.id
    
    context.user_data['state'] = ADD_PRODUCT_NAME
    
    back_callback = f"cat_{category_id}" if 'category_id' in context.user_data['new_product'] else "categories"
    
    await query.edit_message_text(
        "📝 Tovar nomini kiriting:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Orqaga", callback_data=back_callback)],
            [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
        ])
    )

async def edit_product_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session, db_user):
    """Tovarni tahrirlash"""
    query = update.callback_query
    data = query.data
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

async def set_price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session, db_user):
    """Narx turini tanlash"""
    query = update.callback_query
    data = query.data
    parts = data.split("_")
    
    price_type = parts[1]
    currency = parts[2]
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

async def delete_product_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session, db_user):
    """Tovarni o'chirish"""
    query = update.callback_query
    data = query.data
    product_id = int(data.split("_")[1])
    
    product = session.query(Product).filter_by(id=product_id).first()
    
    if not product:
        await query.edit_message_text("❌ Tovar topilmadi!")
        return
    
    # O'chirish huquqini tekshirish
    if db_user.is_admin:
        product.is_active = False
        session.commit()
        await query.edit_message_text(
            "✅ Tovar o'chirildi!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Orqaga", callback_data=f"cat_{product.category_id}" if product.category_id else "categories")],
                [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
            ])
        )
        logger.info(f"Admin tovar o'chirdi: {product_id}")
    elif db_user.branch_type == 'parasite' and product.owner_id == db_user.id:
        product.is_active = False
        session.commit()
        await query.edit_message_text(
            f"✅ {db_user.branch_name} tovari o'chirildi!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Orqaga", callback_data=f"cat_{product.category_id}" if product.category_id else "categories")],
                [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
            ])
        )
        logger.info(f"{db_user.branch_name} tovar o'chirdi: {product_id}")
    else:
        await query.edit_message_text("❌ Siz bu tovarni o'chira olmaysiz!")

# ==================== QATLAM HANDLERLARI ====================

async def layer_main_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session, db_user):
    """Asosiy qatlam tovarlarini ko'rsatish"""
    query = update.callback_query
    
    try:
        # Asosiy qatlam tovarlari
        products = session.query(Product).filter_by(owner_type='main', is_active=True).all()
        
        text = "👑 <b>ASOSIY QATLAM (MAIN LAYER)</b>\n\n"
        text += f"Jami tovarlar: {len(products)} ta\n\n"
        
        if not products:
            text += "Asosiy qatlamda tovarlar yo'q."
            await query.edit_message_text(text, reply_markup=get_back_button("layers"), parse_mode='HTML')
            return
        
        # Kategoriyalar bo'yicha guruhlash
        categories = {}
        for p in products:
            cat_name = "Kategoriyasiz"
            if p.category_id:
                cat = session.query(Category).filter_by(id=p.category_id).first()
                if cat:
                    cat_name = cat.name
            
            if cat_name not in categories:
                categories[cat_name] = []
            categories[cat_name].append(p)
        
        for cat_name, cat_products in categories.items():
            text += f"\n📂 <b>{cat_name}</b> ({len(cat_products)} ta):\n"
            for p in cat_products[:5]:
                text += f"   • {p.name} - {p.quantity} dona\n"
            if len(cat_products) > 5:
                text += f"     ... va yana {len(cat_products) - 5} ta\n"
        
        # Tugmalar
        buttons = []
        for p in products[:10]:
            buttons.append([InlineKeyboardButton(f"👑 {p.name}", callback_data=f"view_{p.id}")])
        
        buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data="layers")])
        buttons.append([InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"Layer main handlerda xatolik: {e}")
        await query.edit_message_text("❌ Xatolik yuz berdi")

async def layer_chiroqchi_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session, db_user):
    """Chiroqchi qatlami tovarlarini ko'rsatish"""
    query = update.callback_query
    
    try:
        # Chiroqchi foydalanuvchilarni topish
        chiroqchi_users = session.query(User).filter_by(branch_type='parasite', is_authorized=True).all()
        
        text = "🐝 <b>CHIROQCHI QATLAMI</b>\n\n"
        
        if not chiroqchi_users:
            text += "Chiroqchi foydalanuvchilar yo'q."
            await query.edit_message_text(text, reply_markup=get_back_button("layers"), parse_mode='HTML')
            return
        
        for cu in chiroqchi_users:
            products = session.query(Product).filter_by(
                owner_type='parasite', 
                owner_id=cu.id,
                is_active=True
            ).all()
            
            text += f"\n👤 <b>{cu.branch_name}</b> ({len(products)} ta tovar):\n"
            
            if products:
                for p in products[:5]:
                    text += f"   • {p.name} - {p.quantity} dona\n"
                if len(products) > 5:
                    text += f"     ... va yana {len(products) - 5} ta\n"
            else:
                text += "   • Tovarlar yo'q\n"
        
        # Tugmalar - barcha parazit tovarlar
        buttons = []
        all_parasite = session.query(Product).filter_by(owner_type='parasite', is_active=True).all()
        for p in all_parasite[:10]:
            owner = session.query(User).filter_by(id=p.owner_id).first()
            owner_name = owner.branch_name if owner else "Noma'lum"
            buttons.append([InlineKeyboardButton(f"🐝 [{owner_name}] {p.name}", callback_data=f"view_{p.id}")])
        
        buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data="layers")])
        buttons.append([InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"Layer chiroqchi handlerda xatolik: {e}")
        await query.edit_message_text("❌ Xatolik yuz berdi")

# ==================== FOYDALANUVCHI HANDLERLARI ====================

async def user_detail_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session, db_user):
    """Foydalanuvchi ma'lumotlarini ko'rsatish"""
    query = update.callback_query
    data = query.data
    user_id = int(data.split("_")[1])
    
    target_user = session.query(User).filter_by(id=user_id).first()
    
    if target_user:
        status = "✅ Tasdiqlangan" if target_user.is_authorized else "❌ Tasdiqlanmagan"
        branch_type = "Asosiy" if target_user.branch_type == 'main' else target_user.branch_name
        
        # Tovar statistikasi
        if target_user.is_admin:
            products_count = session.query(Product).filter_by(is_active=True).count()
        elif target_user.branch_type == 'parasite':
            products_count = session.query(Product).filter_by(
                owner_type='parasite',
                owner_id=target_user.id,
                is_active=True
            ).count()
        else:
            products_count = session.query(Product).filter_by(
                owner_type='main',
                is_active=True
            ).count()
        
        text = (f"👤 <b>Foydalanuvchi ma'lumotlari</b>\n\n"
                f"🆔 ID: {target_user.telegram_id}\n"
                f"📝 Ism: {target_user.first_name or 'Noma\'lum'}\n"
                f"👤 Username: @{target_user.username or 'yoq'}\n"
                f"📊 Status: {status}\n"
                f"🏛 Qatlam: {branch_type}\n"
                f"📦 Tovarlari: {products_count} ta\n"
                f"📅 Qo'shilgan: {target_user.created_at.strftime('%d.%m.%Y')}")
        
        await query.edit_message_text(
            text,
            reply_markup=get_user_actions_keyboard(target_user.id),
            parse_mode='HTML'
        )
    else:
        await query.edit_message_text("❌ Foydalanuvchi topilmadi!")

async def approve_user_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session, db_user):
    """Foydalanuvchini tasdiqlash"""
    query = update.callback_query
    data = query.data
    user_id = int(data.split("_")[1])
    
    target_user = session.query(User).filter_by(id=user_id).first()
    
    if target_user:
        target_user.is_authorized = True
        session.commit()
        await query.edit_message_text(
            f"✅ Foydalanuvchi {target_user.first_name or 'User'} tasdiqlandi!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="users")],
                [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
            ])
        )
        logger.info(f"Foydalanuvchi tasdiqlandi: {target_user.id}")
        
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

async def reject_user_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session, db_user):
    """Foydalanuvchini rad etish"""
    query = update.callback_query
    data = query.data
    user_id = int(data.split("_")[1])
    
    target_user = session.query(User).filter_by(id=user_id).first()
    
    if target_user:
        target_user.is_authorized = False
        session.commit()
        await query.edit_message_text(
            f"❌ Foydalanuvchi {target_user.first_name or 'User'} rad etildi!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="users")],
                [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
            ])
        )
        logger.info(f"Foydalanuvchi rad etildi: {target_user.id}")
        
        try:
            await context.bot.send_message(
                target_user.telegram_id,
                "❌ Sizning so'rovingiz rad etildi."
            )
        except Exception as e:
            logger.error(f"Xabar yuborishda xatolik: {e}")
    else:
        await query.edit_message_text("❌ Foydalanuvchi topilmadi!")

async def change_branch_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session, db_user):
    """Foydalanuvchi qatlamini o'zgartirish"""
    query = update.callback_query
    data = query.data
    user_id = int(data.split("_")[2])
    
    target_user = session.query(User).filter_by(id=user_id).first()
    
    if target_user:
        await query.edit_message_text(
            f"👤 {target_user.first_name} uchun qatlamni tanlang:",
            reply_markup=get_branch_keyboard(target_user.id)
        )
    else:
        await query.edit_message_text("❌ Foydalanuvchi topilmadi!")

async def set_branch_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session, db_user):
    """Foydalanuvchi qatlamini o'rnatish"""
    query = update.callback_query
    data = query.data
    parts = data.split("_")
    
    branch = parts[2]
    user_id = int(parts[3])
    
    target_user = session.query(User).filter_by(id=user_id).first()
    
    if target_user:
        if branch == 'main':
            target_user.branch_type = 'main'
            target_user.branch_name = 'admin'
            target_user.is_admin = True
        elif branch == 'chiroqchi':
            target_user.branch_type = 'parasite'
            target_user.branch_name = 'Chiroqchi'
            target_user.is_admin = False
        elif branch == 'shahrisabz':
            target_user.branch_type = 'main'
            target_user.branch_name = 'Shahrisabz'
            target_user.is_admin = False
        
        target_user.is_authorized = True
        session.commit()
        logger.info(f"Qatlam o'zgartirildi: {target_user.id} -> {branch}")
        
        await query.edit_message_text(
            f"✅ {target_user.first_name} uchun qatlam o'zgartirildi: {branch}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="users")],
                [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
            ])
        )
        
        try:
            await context.bot.send_message(
                target_user.telegram_id,
                f"✅ Sizning qatlammingiz o'zgartirildi: {branch}\n"
                f"/start ni bosing."
            )
        except:
            pass
    else:
        await query.edit_message_text("❌ Foydalanuvchi topilmadi!")

async def remove_user_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session, db_user):
    """Foydalanuvchini o'chirish"""
    query = update.callback_query
    data = query.data
    user_id = int(data.split("_")[2])
    
    target_user = session.query(User).filter_by(id=user_id).first()
    
    if target_user and target_user.telegram_id != ADMIN_ID:
        # Foydalanuvchining tovarlarini o'chirish
        products = session.query(Product).filter_by(owner_id=target_user.id).all()
        for p in products:
            p.is_active = False
        
        session.delete(target_user)
        session.commit()
        await query.edit_message_text(
            "✅ Foydalanuvchi o'chirildi!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="users")],
                [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
            ])
        )
        logger.info(f"Foydalanuvchi o'chirildi: {target_user.id}")
    else:
        await query.edit_message_text("❌ Foydalanuvchi topilmadi yoki adminni o'chirib bo'lmaydi!")

# ==================== STATISTIKA HANDLERLARI ====================

async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session, db_user):
    """Statistika ko'rsatish"""
    query = update.callback_query
    
    products = session.query(Product).filter_by(is_active=True).all()
    total_products = len(products)
    total_quantity = sum(p.quantity for p in products)
    total_purchase_usd = sum((p.purchase_price_usd or 0) * (p.quantity or 0) for p in products)
    total_purchase_uzs = sum((p.purchase_price_uzs or 0) * (p.quantity or 0) for p in products)
    total_selling_usd = sum((p.selling_price_usd or 0) * (p.quantity or 0) for p in products)
    total_selling_uzs = sum((p.selling_price_uzs or 0) * (p.quantity or 0) for p in products)
    categories = session.query(Category).count()
    
    # Qatlamlar bo'yicha statistika
    main_products = session.query(Product).filter_by(owner_type='main', is_active=True).count()
    parasite_products = session.query(Product).filter_by(owner_type='parasite', is_active=True).count()
    
    text = (f"📊 <b>STATISTIKA</b>\n\n"
            f"📦 Jami tovarlar: {total_products}\n"
            f"📂 Kategoriyalar: {categories}\n"
            f"🔢 Jami soni: {total_quantity} dona\n\n"
            f"👑 Asosiy qatlam: {main_products} ta\n"
            f"🐝 Parazit qatlam: {parasite_products} ta\n\n"
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
    
    text += f"\n🕐 Yangilangan: {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}"
    
    await query.edit_message_text(
        text, 
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Orqaga", callback_data="main_menu")]
        ]),
        parse_mode='HTML'
    )

# ==================== EKSPORT/IMPORT HANDLERLARI ====================

async def export_excel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session, db_user):
    """Excel eksport qilish"""
    query = update.callback_query
    
    await query.edit_message_text("⏳ Excel fayl tayyorlanmoqda...")
    
    try:
        filename = await export_to_excel()
        
        with open(filename, 'rb') as f:
            await context.bot.send_document(
                chat_id=update.effective_user.id,
                document=f,
                filename=f"tovarlar_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                caption="✅ Tovarlar ro'yxati (barcha qatlamlar bilan)"
            )
        
        os.remove(filename)
        await query.delete_message()
        logger.info(f"Excel eksport qilindi: {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Eksport xatoligi: {e}")
        await query.edit_message_text(f"❌ Xatolik: {str(e)}")

async def download_backup_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session, db_user):
    """Backup yuklab olish"""
    query = update.callback_query
    
    try:
        backup_file = backup_database()
        
        with open(backup_file, 'rb') as f:
            await context.bot.send_document(
                chat_id=update.effective_user.id,
                document=f,
                filename=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                caption="✅ Ma'lumotlar bazasi backup fayli"
            )
        
        await query.delete_message()
        logger.info(f"Backup yuklab olindi: {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Backup xatoligi: {e}")
        await query.edit_message_text(f"❌ Xatolik: {str(e)}")

# ==================== MESSAGE HANDLERS ====================

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xabarlarni qabul qilish"""
    user = update.effective_user
    if not user or not update.message or not update.message.text:
        return
    
    text = update.message.text
    
    # /skip yoki /cancel komandasi
    if text == "/skip" or text == "/cancel":
        context.user_data['state'] = None
        await update.message.reply_text(
            "❌ Bekor qilindi.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
            ])
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
            
            # Foydalanuvchi turiga qarab qidirish
            if db_user.is_admin:
                products = session.query(Product).filter(
                    (Product.name.contains(query)) | 
                    (Product.keywords.contains(query)),
                    Product.is_active == True
                ).all()
            elif db_user.branch_type == 'parasite':
                products = session.query(Product).filter(
                    (Product.name.contains(query)) | 
                    (Product.keywords.contains(query)),
                    Product.is_active == True,
                    ((Product.owner_type == 'main') | 
                     ((Product.owner_type == 'parasite') & (Product.owner_id == db_user.id)))
                ).all()
            else:
                products = session.query(Product).filter(
                    (Product.name.contains(query)) | 
                    (Product.keywords.contains(query)),
                    Product.owner_type == 'main',
                    Product.is_active == True
                ).all()
            
            if not products:
                await update.message.reply_text(
                    "❌ Hech narsa topilmadi!",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
                    ])
                )
            else:
                await update.message.reply_text(f"🔍 {len(products)} ta tovar topildi:")
                
                for product in products[:5]:
                    # Egani aniqlash
                    owner_name = "Asosiy"
                    if product.owner_type == 'parasite' and product.owner_id:
                        owner = session.query(User).filter_by(id=product.owner_id).first()
                        owner_name = owner.branch_name if owner else "Noma'lum"
                    
                    prod_text = await get_product_info_text(product, owner_name)
                    
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
                        except Exception as e:
                            logger.error(f"Rasmni forward qilishda xatolik: {e}")
                    
                    # Tahrirlash huquqini tekshirish
                    can_edit = False
                    can_delete = False
                    
                    if db_user.is_admin:
                        can_edit = True
                        can_delete = True
                    elif db_user.branch_type == 'parasite' and product.owner_id == db_user.id:
                        can_edit = True
                        can_delete = True
                    
                    await update.message.reply_text(
                        prod_text,
                        reply_markup=get_product_actions_keyboard(
                            product.id, 
                            product.category_id, 
                            can_edit, 
                            can_delete
                        ),
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
        
        # Tovar qo'shish - kelgan narx USD
        if state == ADD_PRODUCT_PURCHASE_USD:
            try:
                value = float(text.replace(',', '.'))
                context.user_data['new_product']['purchase_usd'] = value
                context.user_data['state'] = ADD_PRODUCT_PURCHASE_UZS
                await update.message.reply_text(
                    "💰 Kelgan narxini kiriting (so'm, 0 bo'lsa 0 yozing):",
                    reply_markup=get_cancel_button()
                )
            except ValueError:
                await update.message.reply_text("❌ Noto'g'ri format! Qayta kiriting:")
            return
        
        # Tovar qo'shish - kelgan narx UZS
        if state == ADD_PRODUCT_PURCHASE_UZS:
            try:
                value = float(text.replace(',', '.'))
                context.user_data['new_product']['purchase_uzs'] = value
                context.user_data['state'] = ADD_PRODUCT_SELLING_USD
                await update.message.reply_text(
                    "💵 Sotilish narxini kiriting ($):",
                    reply_markup=get_cancel_button()
                )
            except ValueError:
                await update.message.reply_text("❌ Noto'g'ri format! Qayta kiriting:")
            return
        
        # Tovar qo'shish - sotilish narx USD
        if state == ADD_PRODUCT_SELLING_USD:
            try:
                value = float(text.replace(',', '.'))
                context.user_data['new_product']['selling_usd'] = value
                context.user_data['state'] = ADD_PRODUCT_SELLING_UZS
                await update.message.reply_text(
                    "💵 Sotilish narxini kiriting (so'm, 0 bo'lsa 0 yozing):",
                    reply_markup=get_cancel_button()
                )
            except ValueError:
                await update.message.reply_text("❌ Noto'g'ri format! Qayta kiriting:")
            return
        
        # Tovar qo'shish - sotilish narx UZS
        if state == ADD_PRODUCT_SELLING_UZS:
            try:
                value = float(text.replace(',', '.'))
                context.user_data['new_product']['selling_uzs'] = value
                context.user_data['state'] = ADD_PRODUCT_QUANTITY
                await update.message.reply_text(
                    "📦 Soni (dona):",
                    reply_markup=get_cancel_button()
                )
            except ValueError:
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
            except ValueError:
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
                context.user_data['new_product']['category_id'] = category_id
                
                # Tovarni saqlash
                product = Product(
                    name=context.user_data['new_product']['name'],
                    description=context.user_data['new_product'].get('description', ''),
                    category_id=category_id,
                    owner_type=context.user_data['new_product'].get('owner_type', 'main'),
                    owner_id=context.user_data['new_product'].get('owner_id'),
                    purchase_price_usd=context.user_data['new_product'].get('purchase_usd', 0),
                    purchase_price_uzs=context.user_data['new_product'].get('purchase_uzs', 0),
                    selling_price_usd=context.user_data['new_product'].get('selling_usd', 0),
                    selling_price_uzs=context.user_data['new_product'].get('selling_uzs', 0),
                    quantity=context.user_data['new_product'].get('quantity', 0),
                    keywords=context.user_data['new_product'].get('keywords', ''),
                    media_group_message_id=context.user_data['new_product'].get('media_message_id'),
                    is_active=True
                )
                session.add(product)
                session.commit()
                
                owner_text = "Asosiy" if product.owner_type == 'main' else context.user_data['new_product'].get('branch', 'Parazit')
                
                await update.message.reply_text(
                    f"✅ Tovar muvaffaqiyatli qo'shildi!\n"
                    f"👤 Egasi: {owner_text}\n"
                    f"📊 Qatlam: {'Asosiy' if product.owner_type == 'main' else 'Chiroqchi'}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Orqaga", callback_data=f"cat_{category_id}")],
                        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
                    ])
                )
                logger.info(f"Yangi tovar qo'shildi: {product.name} - {owner_text}")
                
                # Tozalash
                context.user_data.pop('new_product', None)
                if 'new_category_parent' in context.user_data:
                    context.user_data.pop('new_category_parent')
            else:
                session.commit()
                back_callback = f"cat_{parent_id}" if parent_id else "categories"
                await update.message.reply_text(
                    f"✅ Kategoriya qo'shildi: {category_name}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Orqaga", callback_data=back_callback)],
                        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
                    ])
                )
            
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
                except ValueError:
                    await update.message.reply_text("❌ Noto'g'ri format!")
                    return
            elif field == 'quantity':
                try:
                    product.quantity = int(text)
                except ValueError:
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
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Orqaga", callback_data=f"view_{product_id}")],
                    [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
                ])
            )
            
            context.user_data['state'] = None
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
                        f"✅ Foydalanuvchi {target_user.first_name or 'User'} ga ruxsat berildi!\n"
                        f"Endi unga qatlam tayinlang.",
                        reply_markup=get_branch_keyboard(target_user.id)
                    )
                    logger.info(f"Ruxsat berildi: {target_id}")
                    
                    try:
                        await context.bot.send_message(
                            target_id,
                            "✅ Sizga botdan foydalanish uchun ruxsat berildi!\n"
                            "Admin sizga qatlam tayinlaydi."
                        )
                    except Exception as e:
                        logger.error(f"Xabar yuborishda xatolik: {e}")
                else:
                    await update.message.reply_text(
                        "❌ Bunday ID li foydalanuvchi topilmadi!",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
                        ])
                    )
            except ValueError:
                await update.message.reply_text(
                    "❌ Noto'g'ri format! ID raqam kiriting.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
                    ])
                )
            
            context.user_data['state'] = None
            return
        
    except Exception as e:
        logger.error(f"Message handlerda xatolik: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi")
    
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
                
                context.user_data['state'] = ADD_PRODUCT_PURCHASE_USD
                await update.message.reply_text(
                    "💰 Kelgan narxini kiriting ($):",
                    reply_markup=get_cancel_button()
                )
                logger.info(f"Rasm saqlandi: {user.id}")
                
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
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("🔙 Orqaga", callback_data=f"view_{product_id}")],
                                [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
                            ])
                        )
                        logger.info(f"Rasm yangilandi: {product_id}")
                    except Exception as e:
                        logger.error(f"Rasm yangilashda xatolik: {e}")
                        await update.message.reply_text(
                            "❌ Rasmni yangilashda xatolik!",
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("🔙 Orqaga", callback_data=f"view_{product_id}")],
                                [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
                            ])
                        )
                
                context.user_data['state'] = None
    
    except Exception as e:
        logger.error(f"Photo handlerda xatolik: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi")
    
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
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
                    ])
                )
                logger.info(f"Excel import qilindi: {user.id}")
            else:
                await update.message.reply_text(
                    f"❌ {message}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
                    ])
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
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
                    ])
                )
                logger.info(f"Backup tiklandi: {user.id}")
            except Exception as e:
                logger.error(f"Backup tiklashda xatolik: {e}")
                await update.message.reply_text(
                    f"❌ Xatolik: {str(e)}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
                    ])
                )
            
            os.remove(filename)
            context.user_data['state'] = None
        
        else:
            await update.message.reply_text(
                "❌ Noto'g'ri format yoki holat!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
                ])
            )
    
    except Exception as e:
        logger.error(f"Document handlerda xatolik: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi")
    
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
    except Exception as e:
        logger.error(f"Error handlerda xatolik: {e}")

# ==================== ASOSIY FUNKSIYA ====================

def main():
    """Asosiy funksiya"""
    
    print("""
    ╔════════════════════════════════════╗
    ║     DO'KON BOSHQARUVI BOTI         ║
    ║         QATLAMLI TIZIM              ║
    ║         @maestro_o                  ║
    ╚════════════════════════════════════╝
    """)
    
    # MUHIM: .env faylini tekshirish
    logger.info("🔍 Muhit tekshirilmoqda...")
    
    errors = []
    
    # BOT_TOKEN ni tekshirish
    if not BOT_TOKEN:
        errors.append("❌ BOT_TOKEN topilmadi! .env faylini tekshiring")
    elif BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        errors.append("❌ BOT_TOKEN o'zgartirilmagan! O'z tokeningizni yozing")
    elif len(BOT_TOKEN) < 10:
        errors.append("❌ BOT_TOKEN noto'g'ri format!")
    
    # ADMIN_ID ni tekshirish
    if not ADMIN_ID or ADMIN_ID == 0:
        errors.append("❌ ADMIN_ID topilmadi! .env faylini tekshiring")
    elif ADMIN_ID == 123456789:
        errors.append("❌ ADMIN_ID o'zgartirilmagan! O'z ID-ingizni yozing")
    
    if errors:
        logger.error("❌ Muhit tekshiruvida xatoliklar topildi:")
        for error in errors:
            logger.error(error)
        
        print("\n" + "="*60)
        print("❌ XATOLIK! Bot ishga tushirilmadi!")
        print("Sabablari:")
        for error in errors:
            print(f"  • {error}")
        print("\n💡 Yechim:")
        print("  1. .env faylini oching")
        print("  2. BOT_TOKEN va ADMIN_ID ni to'g'ri yozing")
        print("  3. Bot tokenni @BotFather dan oling")
        print("  4. ID ni @userinfobot dan oling")
        print("="*60)
        
        sys.exit(1)
    
    logger.info("✅ Muhit tekshiruvi muvaffaqiyatli o'tdi")
    logger.info(f"🤖 Bot token: {BOT_TOKEN[:10]}...")
    logger.info(f"👤 Admin ID: {ADMIN_ID}")
    
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
        print(f"Xatolik: {e}")
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
    print(f"🕐 Vaqt: {datetime.now().strftime('%H:%M:%S')}")
    print(f"📅 Sana: {datetime.now().strftime('%d.%m.%Y')}")
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
