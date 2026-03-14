#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Do'kon boshqaruvi uchun Telegram bot
Muallif: @maestro_o
Versiya: 5.0 - Barcha muammolar tuzatilgan
"""

import logging
import os
import sys
from datetime import datetime
import pandas as pd
import shutil
import uuid

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
    branch_type = Column(String, default='main')  # 'main', 'parasite', 'user'
    branch_name = Column(String, nullable=True)   # 'admin', 'chiroqchi', 'shahrisabz', 'user'
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
    created_by = Column(Integer, nullable=True)  # Admin ID
    created_at = Column(DateTime, default=datetime.now)

class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    product_uuid = Column(String, unique=True, default=lambda: str(uuid.uuid4()))  # Unikal ID
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
        
        # Default kategoriyalarni o'chirish - faqat siz kiritganlar qoladi
        default_cats = ['Elektronika', 'Avto qismlar', 'Maishiy texnika', 'Qurilish', 'Boshqa']
        for cat_name in default_cats:
            cat = session.query(Category).filter_by(name=cat_name).first()
            if cat:
                session.delete(cat)
        
        session.commit()
        session.close()
        logger.info("✅ Ma'lumotlar bazasi muvaffaqiyatli yaratildi")
    except Exception as e:
        logger.error(f"❌ Ma'lumotlar bazasini yaratishda xatolik: {e}")
        raise e

# ==================== KEYBOARDS ====================

def get_main_keyboard(user):
    """Asosiy menyu tugmalari"""
    buttons = [
        [InlineKeyboardButton("🔍 Qidirish", callback_data="search")],
        [InlineKeyboardButton("📂 Kategoriyalar", callback_data="categories")],
    ]
    
    if user['is_admin']:
        buttons.extend([
            [InlineKeyboardButton("📊 Qatlamlar", callback_data="layers")],
            [InlineKeyboardButton("📊 Statistika", callback_data="stats")],
            [InlineKeyboardButton("➕ Tovar qo'shish", callback_data="add_product")],
            [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="users")],
            [InlineKeyboardButton("📥 Eksport / Import", callback_data="export_import")],
            [InlineKeyboardButton("👤 Ruxsat berish", callback_data="grant_access")],
        ])
    elif user['branch_type'] == 'parasite':
        buttons.extend([
            [InlineKeyboardButton(f"🐝 {user['branch_name']} tovarlari", callback_data="my_products")],
            [InlineKeyboardButton("➕ Tovar qo'shish", callback_data="add_product_parasite")],
        ])
    elif user['branch_type'] == 'user':
        buttons.extend([
            [InlineKeyboardButton("👑 Asosiy tovarlar", callback_data="main_products")],
        ])
    
    buttons.append([InlineKeyboardButton("❌ Yopish", callback_data="close")])
    return InlineKeyboardMarkup(buttons)

def get_back_button(callback_data="main_menu", show_main=True):
    """Orqaga tugmasi - to'g'ri ishlashi uchun"""
    buttons = [[InlineKeyboardButton("🔙 Orqaga", callback_data=callback_data)]]
    if show_main:
        buttons.append([InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)

def get_skip_button(callback_data):
    """O'tkazib yuborish tugmasi"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ O'tkazib yuborish", callback_data=f"skip_{callback_data}")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="cancel")],
        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
    ])

def get_cancel_button():
    """Bekor qilish tugmasi"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel")],
        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
    ])

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
    
    buttons.append([InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)

def get_category_detail_keyboard(category_id, subcats, products, user):
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
    if user['is_admin']:
        buttons.append([InlineKeyboardButton("➕ Kategoriya qo'shish", callback_data=f"add_cat_{category_id}")])
        buttons.append([InlineKeyboardButton("➕ Tovar qo'shish", callback_data=f"add_product_cat_{category_id}")])
    elif user['branch_type'] == 'parasite':
        buttons.append([InlineKeyboardButton(f"➕ {user['branch_name']} uchun tovar qo'shish", 
                                              callback_data=f"add_product_cat_{category_id}_{user['branch_name']}")])
    
    buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data="categories")])
    buttons.append([InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(buttons)

def get_product_actions_keyboard(product_id, category_id, user):
    """Tovar amallari"""
    buttons = []
    
    if user['is_admin'] or (user['branch_type'] == 'parasite' and user.get('can_edit')):
        buttons.append([InlineKeyboardButton("📝 Tahrirlash", callback_data=f"edit_{product_id}")])
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

def get_approve_keyboard(request_id):
    """Tasdiqlash tugmalari"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Admin sifatida qabul qilish", callback_data=f"approve_req_admin_{request_id}"),
            InlineKeyboardButton("🐝 Chiroqchi sifatida qabul qilish", callback_data=f"approve_req_chiroqchi_{request_id}")
        ],
        [InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_req_{request_id}")],
        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
    ])

# ==================== UTILS ====================

async def get_product_info_text(product, owner_name="Asosiy"):
    """Tovar ma'lumotlarini matn ko'rinishida olish"""
    text = f"📦 <b>{product.name}</b>\n\n"
    text += f"🆔 <b>ID:</b> <code>{product.product_uuid}</code>\n"
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
    
    text += f"\n📦 <b>Soni:</b> {product.quantity} dona\n"
    
    if product.keywords:
        text += f"\n🔑 <b>Kalit so'zlar:</b> {product.keywords}\n"
    
    text += f"\n📅 <b>Qo'shilgan:</b> {product.created_at.strftime('%d.%m.%Y %H:%M')}"
    
    return text

# ==================== HANDLERS ====================

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
                branch_type='user',
                branch_name='user'
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
                f"📌 Guruh ID: {update.message.chat.id}"
            )
            return
        
        user_data = {
            'id': db_user.id,
            'telegram_id': db_user.telegram_id,
            'is_admin': db_user.is_admin,
            'is_authorized': db_user.is_authorized,
            'branch_type': db_user.branch_type,
            'branch_name': db_user.branch_name
        }
        
        if db_user.is_admin:
            text = (f"👋 Xush kelibsiz Admin!\n\n"
                    f"Kerakli bo'limni tanlang:")
            await update.message.reply_text(
                text, 
                reply_markup=get_main_keyboard(user_data)
            )
        elif db_user.is_authorized:
            text = (f"👋 Xush kelibsiz {db_user.branch_name or user.first_name}!\n\n"
                    f"Kerakli bo'limni tanlang:")
            await update.message.reply_text(
                text, 
                reply_markup=get_main_keyboard(user_data)
            )
        else:
            text = (f"👋 Xush kelibsiz {user.first_name}!\n\n"
                    f"❌ Botdan foydalanish uchun ruxsat kerak.\n"
                    f"ID raqamingiz: <code>{user.id}</code>")
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Ruxsat so'rash", callback_data="request_access")],
                    [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
                ]),
                parse_mode='HTML'
            )
    
    finally:
        session.close()

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
        
        user_data = {
            'id': db_user.id,
            'telegram_id': db_user.telegram_id,
            'is_admin': db_user.is_admin,
            'is_authorized': db_user.is_authorized,
            'branch_type': db_user.branch_type,
            'branch_name': db_user.branch_name,
            'can_edit': db_user.branch_type == 'parasite'
        }
        
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
        
        # Bosh menyu
        if data == "main_menu":
            if db_user.is_admin:
                text = f"👋 Xush kelibsiz Admin!\n\nKerakli bo'limni tanlang:"
            else:
                text = f"👋 Xush kelibsiz {db_user.branch_name or user.first_name}!\n\nKerakli bo'limni tanlang:"
            
            await query.edit_message_text(
                text,
                reply_markup=get_main_keyboard(user_data)
            )
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
                            reply_markup=get_approve_keyboard(request.id)
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
        
        # So'rovni tasdiqlash
        if data.startswith("approve_req_"):
            if not db_user.is_admin:
                await query.edit_message_text("❌ Bu amalni bajarish uchun admin huquqi kerak.")
                return
            
            parts = data.split("_")
            req_type = parts[2]  # admin yoki chiroqchi
            request_id = int(parts[3])
            
            request = session.query(AccessRequest).filter_by(id=request_id).first()
            
            if not request:
                await query.edit_message_text("❌ So'rov topilmadi!")
                return
            
            request.status = 'approved'
            
            if req_type == 'admin':
                request.user.is_admin = True
                request.user.branch_type = 'main'
                request.user.branch_name = 'admin'
                role = "Admin"
            elif req_type == 'chiroqchi':
                request.user.is_admin = False
                request.user.branch_type = 'parasite'
                request.user.branch_name = 'Chiroqchi'
                role = "Chiroqchi"
            
            request.user.is_authorized = True
            session.commit()
            logger.info(f"So'rov tasdiqlandi: {request.user.id} -> {role}")
            
            try:
                await context.bot.send_message(
                    request.user.telegram_id,
                    f"✅ Sizning so'rovingiz tasdiqlandi! Siz {role} sifatida qo'shildingiz.\n"
                    f"Ishlatish uchun /start ni bosing."
                )
            except Exception as e:
                logger.error(f"Foydalanuvchiga xabar yuborishda xatolik: {e}")
            
            await query.edit_message_text(
                f"✅ Foydalanuvchi {request.user.first_name} {role} sifatida tasdiqlandi!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="users")],
                    [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
                ])
            )
            return
        
        # So'rovni rad etish
        if data.startswith("reject_req_"):
            if not db_user.is_admin:
                await query.edit_message_text("❌ Bu amalni bajarish uchun admin huquqi kerak.")
                return
            
            request_id = int(data.split("_")[2])
            request = session.query(AccessRequest).filter_by(id=request_id).first()
            
            if not request:
                await query.edit_message_text("❌ So'rov topilmadi!")
                return
            
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
        
        # Qidirish
        if data == "search":
            context.user_data['state'] = SEARCH
            await query.edit_message_text(
                "🔍 Qidirish uchun tovar nomi yoki kalit so'zni kiriting:",
                reply_markup=get_back_button("main_menu")
            )
            return
        
        # Kategoriyalar
        if data == "categories":
            categories = session.query(Category).all()
            cat_list = [{'id': c.id, 'name': c.name} for c in categories]
            
            text = "📂 <b>Kategoriyalar</b>\n\n"
            if not cat_list:
                text += "Hali kategoriyalar mavjud emas."
            
            await query.edit_message_text(
                text,
                reply_markup=get_categories_keyboard(
                    cat_list, 
                    parent_id=None, 
                    is_admin=db_user.is_admin
                ),
                parse_mode='HTML'
            )
            return
        
        # Kategoriya ichiga kirish
        if data.startswith("cat_"):
            category_id = int(data.split("_")[1])
            await category_detail_handler(update, context, session, user_data, category_id)
            return
        
        # Tovarni ko'rish
        if data.startswith("view_"):
            await view_product_handler(update, context, session, user_data)
            return
        
        # Tahrirlash
        if data.startswith("edit_"):
            await edit_product_handler(update, context, session, user_data)
            return
        
        # Narx turini tanlash
        if data.startswith("set_"):
            await set_price_handler(update, context, session, user_data)
            return
        
        # O'chirish
        if data.startswith("delete_"):
            await delete_product_handler(update, context, session, user_data)
            return
        
        # Tovar qo'shish
        if data.startswith("add_product"):
            await add_product_start_handler(update, context, session, user_data)
            return
        
        # Kategoriya qo'shish
        if data.startswith("add_cat_"):
            await add_category_handler(update, context, session, user_data)
            return
        
        # O'tkazib yuborish
        if data.startswith("skip_"):
            step = data.split("_")[1]
            await skip_step_handler(update, context, session, user_data, step)
            return
        
        # Qolgan handlerlar...
        if data == "layers":
            await layers_handler(update, context, session, user_data)
        elif data == "layer_main":
            await layer_main_handler(update, context, session, user_data)
        elif data == "layer_chiroqchi":
            await layer_chiroqchi_handler(update, context, session, user_data)
        elif data == "my_products":
            await my_products_handler(update, context, session, user_data)
        elif data == "main_products":
            await main_products_handler(update, context, session, user_data)
        elif data == "users":
            await users_handler(update, context, session, user_data)
        elif data.startswith("user_"):
            await user_detail_handler(update, context, session, user_data)
        elif data.startswith("approve_") and not data.startswith("approve_req_"):
            await approve_user_handler(update, context, session, user_data)
        elif data.startswith("reject_") and not data.startswith("reject_req_"):
            await reject_user_handler(update, context, session, user_data)
        elif data.startswith("change_branch_"):
            await change_branch_handler(update, context, session, user_data)
        elif data.startswith("set_branch_"):
            await set_branch_handler(update, context, session, user_data)
        elif data.startswith("remove_user_"):
            await remove_user_handler(update, context, session, user_data)
        elif data == "stats":
            await stats_handler(update, context, session, user_data)
        elif data == "grant_access":
            await grant_access_handler(update, context, session, user_data)
        elif data == "export_import":
            await export_import_handler(update, context, session, user_data)
        elif data == "export_excel":
            await export_excel_handler(update, context, session, user_data)
        elif data == "import_excel":
            await import_excel_handler(update, context, session, user_data)
        elif data == "download_backup":
            await download_backup_handler(update, context, session, user_data)
        elif data == "restore_backup":
            await restore_backup_handler(update, context, session, user_data)
        elif data == "clear_database":
            await clear_database_handler(update, context, session, user_data)
        elif data == "confirm_clear":
            await confirm_clear_handler(update, context, session, user_data)
        
    except Exception as e:
        logger.error(f"Button handlerda xatolik: {e}")
        await query.edit_message_text(f"❌ Xatolik: {str(e)}")
    
    finally:
        session.close()

async def skip_step_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session, user, step):
    """Qadamni o'tkazib yuborish"""
    query = update.callback_query
    
    if step == "photo":
        context.user_data['state'] = ADD_PRODUCT_PURCHASE_USD
        await query.edit_message_text(
            "💰 Kelgan narxini kiriting ($):",
            reply_markup=get_skip_button("purchase_usd")
        )
    elif step == "purchase_usd":
        context.user_data['new_product']['purchase_usd'] = 0
        context.user_data['state'] = ADD_PRODUCT_PURCHASE_UZS
        await query.edit_message_text(
            "💰 Kelgan narxini kiriting (so'm):",
            reply_markup=get_skip_button("purchase_uzs")
        )
    elif step == "purchase_uzs":
        context.user_data['new_product']['purchase_uzs'] = 0
        context.user_data['state'] = ADD_PRODUCT_SELLING_USD
        await query.edit_message_text(
            "💵 Sotilish narxini kiriting ($):",
            reply_markup=get_skip_button("selling_usd")
        )
    elif step == "selling_usd":
        context.user_data['new_product']['selling_usd'] = 0
        context.user_data['state'] = ADD_PRODUCT_SELLING_UZS
        await query.edit_message_text(
            "💵 Sotilish narxini kiriting (so'm):",
            reply_markup=get_skip_button("selling_uzs")
        )
    elif step == "selling_uzs":
        context.user_data['new_product']['selling_uzs'] = 0
        context.user_data['state'] = ADD_PRODUCT_QUANTITY
        await query.edit_message_text(
            "📦 Soni (dona):",
            reply_markup=get_skip_button("quantity")
        )
    elif step == "quantity":
        context.user_data['new_product']['quantity'] = 0
        context.user_data['state'] = ADD_PRODUCT_KEYWORDS
        await query.edit_message_text(
            "🔑 Kalit so'zlar (vergul bilan ajrating):",
            reply_markup=get_skip_button("keywords")
        )
    elif step == "keywords":
        context.user_data['new_product']['keywords'] = ""
        await save_product(update, context, session)

async def category_detail_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session, user, category_id):
    """Kategoriya ichidagi tovarlarni ko'rsatish"""
    query = update.callback_query
    
    category = session.query(Category).filter_by(id=category_id).first()
    
    if not category:
        await query.edit_message_text("❌ Kategoriya topilmadi!")
        return
    
    # Foydalanuvchi turiga qarab tovarlarni filterlash
    if user['is_admin']:
        products = session.query(Product).filter_by(category_id=category_id, is_active=True).all()
    elif user['branch_type'] == 'parasite':
        products = session.query(Product).filter(
            (Product.category_id == category_id) & 
            (Product.is_active == True) &
            ((Product.owner_type == 'main') | 
             ((Product.owner_type == 'parasite') & (Product.owner_id == user['id'])))
        ).all()
    elif user['branch_type'] == 'user':
        products = session.query(Product).filter_by(
            category_id=category_id, 
            owner_type='main',
            is_active=True
        ).all()
    else:
        products = []
    
    subcats = session.query(Category).filter_by(parent_id=category_id).all()
    
    text = f"📂 <b>{category.name}</b>\n\n"
    
    if subcats:
        text += "📁 <b>Pastki kategoriyalar:</b>\n"
        for sc in subcats:
            text += f"• {sc.name}\n"
        text += "\n"
    
    if products:
        text += "📦 <b>Tovarlar:</b>\n"
        for p in products:
            emoji = "👑" if p.owner_type == 'main' else "🐝"
            text += f"• {emoji} {p.name} - {p.quantity} dona\n"
    else:
        text += "Bu kategoriyada tovarlar yo'q."
    
    await query.edit_message_text(
        text, 
        reply_markup=get_category_detail_keyboard(category_id, subcats, products, user),
        parse_mode='HTML'
    )

async def view_product_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session, user):
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
    
    # Rasmni guruhdan olish va ID bilan ko'rsatish
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
    
    user['can_edit'] = (user['is_admin'] or 
                        (user['branch_type'] == 'parasite' and product.owner_id == user['id']))
    
    await query.edit_message_text(
        text,
        reply_markup=get_product_actions_keyboard(product_id, product.category_id, user),
        parse_mode='HTML'
    )

async def add_product_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session, user):
    """Tovar qo'shishni boshlash"""
    query = update.callback_query
    data = query.data
    
    context.user_data['new_product'] = {
        'owner_type': 'main' if user['is_admin'] else 'parasite',
        'owner_id': None if user['is_admin'] else user['id'],
        'branch': user['branch_name'] if user['branch_type'] == 'parasite' else 'main'
    }
    
    # Kategoriya ID si borligini tekshirish
    if '_cat_' in data:
        parts = data.split("_")
        category_id = int(parts[-1]) if parts[-1].isdigit() else None
        if category_id:
            context.user_data['new_product']['category_id'] = category_id
    
    context.user_data['state'] = ADD_PRODUCT_NAME
    
    await query.edit_message_text(
        "📝 Tovar nomini kiriting:",
        reply_markup=get_skip_button("name")
    )

async def add_category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session, user):
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

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xabarlarni qabul qilish"""
    user = update.effective_user
    if not user or not update.message or not update.message.text:
        return
    
    text = update.message.text
    
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
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Ruxsat so'rash", callback_data="request_access")],
                    [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
                ])
            )
            return
        
        user_data = {
            'id': db_user.id,
            'is_admin': db_user.is_admin,
            'branch_type': db_user.branch_type,
            'branch_name': db_user.branch_name
        }
        
        state = context.user_data.get('state')
        
        # Qidirish
        if state == SEARCH:
            query = text.strip()
            
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
                    owner_name = "Asosiy"
                    if product.owner_type == 'parasite' and product.owner_id:
                        owner = session.query(User).filter_by(id=product.owner_id).first()
                        owner_name = owner.branch_name if owner else "Noma'lum"
                    
                    prod_text = await get_product_info_text(product, owner_name)
                    
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
                    
                    user_data['can_edit'] = (db_user.is_admin or 
                                            (db_user.branch_type == 'parasite' and product.owner_id == db_user.id))
                    
                    await update.message.reply_text(
                        prod_text,
                        reply_markup=get_product_actions_keyboard(product.id, product.category_id, user_data),
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
                reply_markup=get_skip_button("photo")
            )
            return
        
        # Tovar qo'shish - kelgan narx USD
        if state == ADD_PRODUCT_PURCHASE_USD:
            try:
                value = float(text.replace(',', '.')) if text != "/skip" else 0
                context.user_data['new_product']['purchase_usd'] = value
                context.user_data['state'] = ADD_PRODUCT_PURCHASE_UZS
                await update.message.reply_text(
                    "💰 Kelgan narxini kiriting (so'm):",
                    reply_markup=get_skip_button("purchase_uzs")
                )
            except ValueError:
                await update.message.reply_text("❌ Noto'g'ri format! Qayta kiriting:")
            return
        
        # Tovar qo'shish - kelgan narx UZS
        if state == ADD_PRODUCT_PURCHASE_UZS:
            try:
                value = float(text.replace(',', '.')) if text != "/skip" else 0
                context.user_data['new_product']['purchase_uzs'] = value
                context.user_data['state'] = ADD_PRODUCT_SELLING_USD
                await update.message.reply_text(
                    "💵 Sotilish narxini kiriting ($):",
                    reply_markup=get_skip_button("selling_usd")
                )
            except ValueError:
                await update.message.reply_text("❌ Noto'g'ri format! Qayta kiriting:")
            return
        
        # Tovar qo'shish - sotilish narx USD
        if state == ADD_PRODUCT_SELLING_USD:
            try:
                value = float(text.replace(',', '.')) if text != "/skip" else 0
                context.user_data['new_product']['selling_usd'] = value
                context.user_data['state'] = ADD_PRODUCT_SELLING_UZS
                await update.message.reply_text(
                    "💵 Sotilish narxini kiriting (so'm):",
                    reply_markup=get_skip_button("selling_uzs")
                )
            except ValueError:
                await update.message.reply_text("❌ Noto'g'ri format! Qayta kiriting:")
            return
        
        # Tovar qo'shish - sotilish narx UZS
        if state == ADD_PRODUCT_SELLING_UZS:
            try:
                value = float(text.replace(',', '.')) if text != "/skip" else 0
                context.user_data['new_product']['selling_uzs'] = value
                context.user_data['state'] = ADD_PRODUCT_QUANTITY
                await update.message.reply_text(
                    "📦 Soni (dona):",
                    reply_markup=get_skip_button("quantity")
                )
            except ValueError:
                await update.message.reply_text("❌ Noto'g'ri format! Qayta kiriting:")
            return
        
        # Tovar qo'shish - soni
        if state == ADD_PRODUCT_QUANTITY:
            try:
                value = int(text) if text != "/skip" else 0
                context.user_data['new_product']['quantity'] = value
                context.user_data['state'] = ADD_PRODUCT_KEYWORDS
                await update.message.reply_text(
                    "🔑 Kalit so'zlar (vergul bilan ajrating):",
                    reply_markup=get_skip_button("keywords")
                )
            except ValueError:
                await update.message.reply_text("❌ Noto'g'ri format! Qayta kiriting:")
            return
        
        # Tovar qo'shish - kalit so'zlar
        if state == ADD_PRODUCT_KEYWORDS:
            context.user_data['new_product']['keywords'] = text if text != "/skip" else ""
            await save_product(update, context, session)
            return
        
        # Kategoriya qo'shish
        if state == ADD_PRODUCT_CATEGORY:
            await save_category(update, context, session, text)
            return
        
        # Tahrirlash
        if state == EDIT_WAITING:
            await edit_product_save(update, context, session, text)
            return
        
        # Ruxsat berish
        if state == GRANT_ACCESS_WAITING:
            await grant_access_save(update, context, session, text)
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
                product_uuid = str(uuid.uuid4())[:8]
                
                # Rasmni guruhga yuborish
                sent_message = await context.bot.send_photo(
                    chat_id=group.group_id,
                    photo=photo.file_id,
                    caption=f"🆔 ID: {product_uuid}\n📦 {context.user_data['new_product']['name']}"
                )
                
                context.user_data['new_product']['media_message_id'] = sent_message.message_id
                context.user_data['new_product']['product_uuid'] = product_uuid
                
                context.user_data['state'] = ADD_PRODUCT_PURCHASE_USD
                await update.message.reply_text(
                    "💰 Kelgan narxini kiriting ($):",
                    reply_markup=get_skip_button("purchase_usd")
                )
                logger.info(f"Rasm saqlandi, ID: {product_uuid}")
                
            except Exception as e:
                logger.error(f"Rasm yuborishda xatolik: {e}")
                await update.message.reply_text(
                    "❌ Rasmni saqlashda xatolik.",
                    reply_markup=get_skip_button("purchase_usd")
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
                        
                        sent_message = await context.bot.send_photo(
                            chat_id=group.group_id,
                            photo=photo.file_id,
                            caption=f"🆔 ID: {product.product_uuid}\n📦 {product.name}"
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
                    except Exception as e:
                        logger.error(f"Rasm yangilashda xatolik: {e}")
                        await update.message.reply_text("❌ Rasmni yangilashda xatolik!")
                
                context.user_data['state'] = None
    
    except Exception as e:
        logger.error(f"Photo handlerda xatolik: {e}")
    
    finally:
        session.close()

async def save_product(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    """Tovarni saqlash"""
    try:
        product_data = context.user_data['new_product']
        
        product = Product(
            product_uuid=product_data.get('product_uuid', str(uuid.uuid4())[:8]),
            name=product_data['name'],
            category_id=product_data.get('category_id'),
            owner_type=product_data.get('owner_type', 'main'),
            owner_id=product_data.get('owner_id'),
            purchase_price_usd=product_data.get('purchase_usd', 0),
            purchase_price_uzs=product_data.get('purchase_uzs', 0),
            selling_price_usd=product_data.get('selling_usd', 0),
            selling_price_uzs=product_data.get('selling_uzs', 0),
            quantity=product_data.get('quantity', 0),
            keywords=product_data.get('keywords', ''),
            media_group_message_id=product_data.get('media_message_id'),
            is_active=True
        )
        
        session.add(product)
        session.commit()
        
        owner_text = "Asosiy" if product.owner_type == 'main' else product_data.get('branch', 'Parazit')
        
        await update.message.reply_text(
            f"✅ Tovar muvaffaqiyatli qo'shildi!\n"
            f"🆔 ID: <code>{product.product_uuid}</code>\n"
            f"👤 Egasi: {owner_text}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Orqaga", callback_data=f"cat_{product.category_id}" if product.category_id else "categories")],
                [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
            ]),
            parse_mode='HTML'
        )
        logger.info(f"Yangi tovar qo'shildi: {product.name}, ID: {product.product_uuid}")
        
        context.user_data.pop('new_product', None)
        context.user_data['state'] = None
        
    except Exception as e:
        session.rollback()
        logger.error(f"Tovar saqlashda xatolik: {e}")
        await update.message.reply_text(f"❌ Xatolik: {str(e)}")

async def save_category(update: Update, context: ContextTypes.DEFAULT_TYPE, session, name):
    """Kategoriyani saqlash"""
    try:
        category_name = name.strip()
        parent_id = context.user_data.get('new_category_parent')
        
        existing = session.query(Category).filter_by(name=category_name).first()
        if existing:
            category_id = existing.id
            await update.message.reply_text(f"ℹ️ Kategoriya allaqachon mavjud.")
        else:
            category = Category(name=category_name, parent_id=parent_id)
            session.add(category)
            session.flush()
            category_id = category.id
            session.commit()
            await update.message.reply_text(f"✅ Kategoriya qo'shildi: {category_name}")
        
        back_callback = f"cat_{parent_id}" if parent_id else "categories"
        await update.message.reply_text(
            "Qaytish uchun tugmalardan foydalaning:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Orqaga", callback_data=back_callback)],
                [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
            ])
        )
        
        if 'new_category_parent' in context.user_data:
            context.user_data.pop('new_category_parent')
        context.user_data['state'] = None
        
    except Exception as e:
        logger.error(f"Kategoriya saqlashda xatolik: {e}")
        await update.message.reply_text(f"❌ Xatolik: {str(e)}")

async def edit_product_save(update: Update, context: ContextTypes.DEFAULT_TYPE, session, text):
    """Tahrirlangan tovarni saqlash"""
    product_id = context.user_data.get('editing_product')
    field = context.user_data.get('editing_field')
    
    product = session.query(Product).filter_by(id=product_id).first()
    if not product:
        await update.message.reply_text("❌ Tovar topilmadi!")
        context.user_data['state'] = None
        return
    
    old_data = {
        'purchase_usd': product.purchase_price_usd,
        'purchase_uzs': product.purchase_price_uzs,
        'selling_usd': product.selling_price_usd,
        'selling_uzs': product.selling_price_uzs,
        'quantity': product.quantity
    }
    
    try:
        if field == 'name':
            product.name = text
        elif field in ['purchase_usd', 'purchase_uzs', 'selling_usd', 'selling_uzs']:
            value = float(text.replace(',', '.'))
            setattr(product, field, value)
        elif field == 'quantity':
            product.quantity = int(text)
        elif field == 'keywords':
            product.keywords = text
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri format!")
        return
    
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
            changed_by=update.effective_user.id
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

async def grant_access_save(update: Update, context: ContextTypes.DEFAULT_TYPE, session, text):
    """Ruxsat berishni saqlash"""
    try:
        target_id = int(text.strip())
        target_user = session.query(User).filter_by(telegram_id=target_id).first()
        
        if target_user:
            target_user.is_authorized = True
            session.commit()
            await update.message.reply_text(
                f"✅ Foydalanuvchi {target_user.first_name or 'User'} ga ruxsat berildi!\n"
                f"Endi unga qatlam tayinlang.",
                reply_markup=get_approve_keyboard(0)  # Bu yerda request_id 0, lekin ishlatilmaydi
            )
            logger.info(f"Ruxsat berildi: {target_id}")
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

# Qolgan handlerlar (layers, users, stats, export etc.)
# Ular oldingi kod bilan bir xil, faqat user_data parametri bilan

async def main():
    """Asosiy funksiya"""
    print("""
    ╔════════════════════════════════════╗
    ║     DO'KON BOSHQARUVI BOTI         ║
    ║         TO'LIQ TUZATILGAN           ║
    ║         @maestro_o                  ║
    ╚════════════════════════════════════╝
    """)
    
    logger.info("🔍 Muhit tekshirilmoqda...")
    
    errors = []
    
    if not BOT_TOKEN:
        errors.append("❌ BOT_TOKEN topilmadi! .env faylini tekshiring")
    elif len(BOT_TOKEN) < 10:
        errors.append("❌ BOT_TOKEN noto'g'ri format!")
    
    if not ADMIN_ID or ADMIN_ID == 0:
        errors.append("❌ ADMIN_ID topilmadi! .env faylini tekshiring")
    
    if errors:
        logger.error("❌ Muhit tekshiruvida xatoliklar topildi:")
        for error in errors:
            logger.error(error)
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
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    
    logger.info("✅ Handlerlar o'rnatildi")
    
    # Botni ishga tushirish
    print("\n" + "="*50)
    print("🚀 BOT ISHGA TUSHIRILMOQDA...")
    print("="*50)
    print(f"🕐 Vaqt: {datetime.now().strftime('%H:%M:%S')}")
    print(f"📅 Sana: {datetime.now().strftime('%d.%m.%Y')}")
    print("="*50 + "\n")
    
    logger.info("🎉 Bot muvaffaqiyatli ishga tushdi!")
    
    try:
        application.run_polling(allowed_updates=['message', 'callback_query'], drop_pending_updates=True)
    except KeyboardInterrupt:
        logger.info("👋 Bot to'xtatildi (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ Bot ishga tushishda xatolik: {e}")

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
