#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Do'kon boshqaruvi uchun Telegram bot
Muallif: @maestro_o
Versiya: 1.0
"""

import logging
import os
import sys
from datetime import datetime
import pandas as pd
import json
import aiofiles
import asyncio
from typing import Dict, List, Optional

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
MEDIA_CHANNEL_ID = int(os.getenv('MEDIA_CHANNEL_ID', 0))

# ==================== MA'LUMOTLAR BAZASI ====================
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import shutil

engine = create_engine('sqlite:///data/shop_bot.db', connect_args={'check_same_thread': False})
Base = declarative_base()
Session = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
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
    
    parent = relationship("Category", remote_side=[id], backref="subcategories")
    products = relationship("Product", back_populates="category")

class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    description = Column(Text, nullable=True)
    category_id = Column(Integer, ForeignKey('categories.id'))
    purchase_price_usd = Column(Float, default=0)
    purchase_price_uzs = Column(Float, default=0)
    selling_price_usd = Column(Float, default=0)
    selling_price_uzs = Column(Float, default=0)
    quantity = Column(Integer, default=0)
    media_channel_message_id = Column(Integer, nullable=True)
    media_file_id = Column(String, nullable=True)
    keywords = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    category = relationship("Category", back_populates="products")
    price_history = relationship("PriceHistory", back_populates="product")

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
    
    product = relationship("Product", back_populates="price_history")

class MediaChannel(Base):
    __tablename__ = 'media_channels'
    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, unique=True)
    channel_name = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)

def init_db():
    os.makedirs('data', exist_ok=True)
    Base.metadata.create_all(engine)
    
    session = Session()
    admin = session.query(User).filter_by(telegram_id=ADMIN_ID).first()
    if not admin:
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

def backup_database():
    backup_name = f"data/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2('data/shop_bot.db', backup_name)
    return backup_name

def restore_database(backup_file):
    shutil.copy2(backup_file, 'data/shop_bot.db')
    return True

# ==================== KEYBOARDS ====================

def get_main_keyboard(user_is_admin=False, user_can_edit=False):
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
        ])
    elif user_can_edit:
        buttons.extend([
            [InlineKeyboardButton("📊 Statistika", callback_data="stats")],
            [InlineKeyboardButton("📥 Eksport", callback_data="export_only")],
        ])
    
    buttons.append([InlineKeyboardButton("❌ Yopish", callback_data="close")])
    return InlineKeyboardMarkup(buttons)

def get_back_button(callback_data="main_menu"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Orqaga", callback_data=callback_data)]
    ])

def get_categories_keyboard(categories, parent_id=None):
    buttons = []
    for cat in categories:
        buttons.append([
            InlineKeyboardButton(f"📁 {cat['name']}", callback_data=f"cat_{cat['id']}")
        ])
    
    if parent_id is not None:
        buttons.append([
            InlineKeyboardButton("➕ Kategoriya qo'shish", callback_data=f"add_cat_{parent_id}")
        ])
    
    buttons.append([InlineKeyboardButton("🔙 Bosh menyu", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)

def get_product_actions_keyboard(product_id, is_admin=False):
    buttons = [
        [InlineKeyboardButton("📝 Tahrirlash", callback_data=f"edit_{product_id}")],
    ]
    
    if is_admin:
        buttons.extend([
            [InlineKeyboardButton("🗑 O'chirish", callback_data=f"delete_{product_id}")],
        ])
    
    buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data="categories")])
    return InlineKeyboardMarkup(buttons)

def get_edit_product_keyboard(product_id):
    buttons = [
        [InlineKeyboardButton("🖼 Rasm", callback_data=f"edit_photo_{product_id}")],
        [InlineKeyboardButton("📝 Nomi", callback_data=f"edit_name_{product_id}")],
        [InlineKeyboardButton("💰 Kelgan narxi ($)", callback_data=f"edit_purchase_usd_{product_id}")],
        [InlineKeyboardButton("💰 Kelgan narxi (so'm)", callback_data=f"edit_purchase_uzs_{product_id}")],
        [InlineKeyboardButton("💵 Sotilish narxi ($)", callback_data=f"edit_selling_usd_{product_id}")],
        [InlineKeyboardButton("💵 Sotilish narxi (so'm)", callback_data=f"edit_selling_uzs_{product_id}")],
        [InlineKeyboardButton("📦 Soni", callback_data=f"edit_quantity_{product_id}")],
        [InlineKeyboardButton("🔑 Kalit so'zlar", callback_data=f"edit_keywords_{product_id}")],
        [InlineKeyboardButton("📂 Kategoriya", callback_data=f"edit_category_{product_id}")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data=f"view_{product_id}")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_export_import_keyboard():
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
    buttons = []
    for user in users:
        status = "✅" if user['is_authorized'] else "⭕️"
        edit = "✏️" if user['can_edit'] else "👁"
        buttons.append([
            InlineKeyboardButton(
                f"{status} {edit} {user['first_name']} (@{user['username']})", 
                callback_data=f"user_{user['id']}"
            )
        ])
    
    buttons.append([InlineKeyboardButton("🔙 Bosh menyu", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)

def get_user_actions_keyboard(user_id):
    buttons = [
        [InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_{user_id}")],
        [InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{user_id}")],
        [InlineKeyboardButton("✏️ Tahrirlash huquqi", callback_data=f"toggle_edit_{user_id}")],
        [InlineKeyboardButton("🗑 O'chirish", callback_data=f"remove_user_{user_id}")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="users")]
    ]
    return InlineKeyboardMarkup(buttons)

def get_access_request_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Ruxsat so'rash", callback_data="request_access")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="main_menu")]
    ])

def get_approve_reject_keyboard(request_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_req_{request_id}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_req_{request_id}")
        ]
    ])

# ==================== UTILS ====================

async def export_to_excel():
    session = Session()
    products = session.query(Product).all()
    data = []
    
    for p in products:
        category = session.query(Category).filter_by(id=p.category_id).first()
        data.append({
            'ID': p.id,
            'Nomi': p.name,
            'Kategoriya': category.name if category else '',
            'Kelgan narxi ($)': p.purchase_price_usd,
            'Kelgan narxi (so\'m)': p.purchase_price_uzs,
            'Sotilish narxi ($)': p.selling_price_usd,
            'Sotilish narxi (so\'m)': p.selling_price_uzs,
            'Soni': p.quantity,
            'Kalit so\'zlar': p.keywords,
            'Rasm ID': p.media_channel_message_id,
            'Yaratilgan': p.created_at,
            'Yangilangan': p.updated_at
        })
    
    df = pd.DataFrame(data)
    filename = f"data/export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(filename, index=False)
    
    session.close()
    return filename

async def import_from_excel(file_path, clear_existing=True):
    session = Session()
    
    try:
        if clear_existing:
            session.query(PriceHistory).delete()
            session.query(Product).delete()
            session.query(Category).delete()
        
        df = pd.read_excel(file_path)
        categories_cache = {}
        
        for _, row in df.iterrows():
            category_name = row.get('Kategoriya', '')
            if category_name and category_name not in categories_cache:
                category = Category(name=category_name)
                session.add(category)
                session.flush()
                categories_cache[category_name] = category.id
            elif category_name:
                category_id = categories_cache[category_name]
            else:
                category_id = None
            
            product = Product(
                name=row['Nomi'],
                category_id=category_id,
                purchase_price_usd=float(row.get('Kelgan narxi ($)', 0)),
                purchase_price_uzs=float(row.get('Kelgan narxi (so\'m)', 0)),
                selling_price_usd=float(row.get('Sotilish narxi ($)', 0)),
                selling_price_uzs=float(row.get('Sotilish narxi (so\'m)', 0)),
                quantity=int(row.get('Soni', 0)),
                keywords=row.get('Kalit so\'zlar', ''),
                media_channel_message_id=row.get('Rasm ID')
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
    text = f"📦 <b>{product.name}</b>\n\n"
    
    if product.description:
        text += f"📝 {product.description}\n\n"
    
    text += f"💰 <b>Kelgan narxi:</b>\n"
    text += f"   • {product.purchase_price_usd:,.0f} $\n"
    if product.purchase_price_uzs > 0:
        text += f"   • {product.purchase_price_uzs:,.0f} so'm\n"
    
    text += f"\n💵 <b>Sotilish narxi:</b>\n"
    text += f"   • {product.selling_price_usd:,.0f} $\n"
    if product.selling_price_uzs > 0:
        text += f"   • {product.selling_price_uzs:,.0f} so'm\n"
    
    text += f"\n📦 <b>Soni:</b> {product.quantity} dona\n"
    
    if product.keywords:
        text += f"\n🔑 <b>Kalit so'zlar:</b> {product.keywords}\n"
    
    text += f"\n📅 <b>Qo'shilgan:</b> {product.created_at.strftime('%d.%m.%Y %H:%M')}"
    
    if include_history:
        session = Session()
        history = session.query(PriceHistory).filter_by(product_id=product.id).order_by(PriceHistory.changed_at.desc()).limit(5).all()
        if history:
            text += f"\n\n📊 <b>So'nggi o'zgarishlar:</b>\n"
            for h in history:
                text += f"• {h.changed_at.strftime('%d.%m.%Y %H:%M')}\n"
                text += f"  Kelgan: {h.old_purchase_usd}$ → {h.new_purchase_usd}$\n"
                text += f"  Sotilish: {h.old_selling_usd}$ → {h.new_selling_usd}$\n"
        session.close()
    
    return text

# ==================== HANDLERS ====================

# Conversation states
(SEARCH, ADD_PRODUCT_NAME, ADD_PRODUCT_PHOTO, ADD_PRODUCT_PURCHASE_USD,
 ADD_PRODUCT_PURCHASE_UZS, ADD_PRODUCT_SELLING_USD, ADD_PRODUCT_SELLING_UZS,
 ADD_PRODUCT_QUANTITY, ADD_PRODUCT_KEYWORDS, ADD_PRODUCT_CATEGORY,
 EDIT_WAITING, IMPORT_WAITING, RESTORE_WAITING, GRANT_ACCESS_WAITING) = range(14)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    session = Session()
    
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
    
    if update.message and update.message.chat.type in ['group', 'supergroup', 'channel']:
        channel = session.query(MediaChannel).filter_by(channel_id=update.message.chat.id).first()
        if not channel:
            channel = MediaChannel(
                channel_id=update.message.chat.id,
                channel_name=update.message.chat.title or "Media Group"
            )
            session.add(channel)
            session.commit()
        
        await update.message.reply_text("✅ Bot guruhda ishga tushdi! Rasmlar shu yerga saqlanadi.")
        session.close()
        return
    
    session.close()
    
    if db_user.is_admin:
        text = (f"👋 Xush kelibsiz Admin {user.first_name}!\n\n"
                f"🕐 Toshkent vaqti: {datetime.now().strftime('%H:%M:%S')}\n"
                f"📅 Sana: {datetime.now().strftime('%d.%m.%Y')}\n\n"
                f"Kerakli bo'limni tanlang:")
        await update.message.reply_text(
            text, 
            reply_markup=get_main_keyboard(user_is_admin=True)
        )
    elif db_user.is_authorized:
        text = (f"👋 Xush kelibsiz {user.first_name}!\n\n"
                f"Kerakli bo'limni tanlang:")
        await update.message.reply_text(
            text, 
            reply_markup=get_main_keyboard(user_can_edit=db_user.can_edit)
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

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🤖 <b>BOT HAQIDA MA'LUMOT</b>

<b>🔍 Qidirish:</b>
• Tovar nomi yoki kalit so'z bilan qidiring
• Barcha tovarlar orasidan tezkor qidiruv

<b>📂 Kategoriyalar:</b>
• Mahsulotlarni kategoriyalar bo'yicha ko'rish
• Ichma-ich kategoriyalar

<b>📊 Statistika:</b>
• Jami tovarlar soni
• Kategoriyalar soni
• Narxlar statistikasi
• O'zgarishlar tarixi

<b>➕ Tovar qo'shish (Admin):</b>
• Nomi, rasmi, narxlari
• Kelgan va sotilish narxi ($ va so'm)
• Kalit so'zlar

<b>👥 Foydalanuvchilar (Admin):</b>
• Ruxsat berish/olib tashlash
• Tahrirlash huquqini berish

<b>📥 Eksport/Import (Admin):</b>
• Excel formatida eksport
• Excel dan import
• Backup yuklab olish/tiklash

<b>🖼 Rasmlar:</b>
• Maxsus kanalda saqlanadi
• Xotira muammosi yo'q

<b>📞 Bog'lanish:</b>
• Admin: @maestro_o
• Bot versiyasi: 1.0

🕐 {datetime.now().strftime('%H:%M:%S')}
📅 {datetime.now().strftime('%d.%m.%Y')}
    """
    
    await update.message.reply_text(help_text, parse_mode='HTML')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    session = Session()
    db_user = session.query(User).filter_by(telegram_id=user.id).first()
    
    if not db_user:
        await query.edit_message_text("❌ Foydalanuvchi topilmadi! /start ni bosing.")
        session.close()
        return
    
    data = query.data
    
    # Yopish
    if data == "close":
        await query.delete_message()
        session.close()
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
                except:
                    pass
            
            await query.edit_message_text(
                "✅ So'rovingiz yuborildi! Tasdiqlanishini kuting."
            )
        
        session.close()
        return
    
    # So'rovni tasdiqlash/rad etish
    if data.startswith("approve_req_") or data.startswith("reject_req_"):
        if not db_user or not db_user.is_admin:
            await query.edit_message_text("❌ Bu amalni bajarish uchun admin huquqi kerak.")
            session.close()
            return
        
        request_id = int(data.split("_")[2])
        request = session.query(AccessRequest).filter_by(id=request_id).first()
        
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
            except:
                pass
            
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
            except:
                pass
            
            await query.edit_message_text(
                f"❌ Foydalanuvchi {request.user.first_name} rad etildi!"
            )
        
        session.close()
        return
    
    # Asosiy menyu
    if data == "main_menu":
        if db_user.is_admin:
            text = (f"👋 Xush kelibsiz Admin {user.first_name}!\n\n"
                    f"🕐 Toshkent vaqti: {datetime.now().strftime('%H:%M:%S')}\n"
                    f"📅 Sana: {datetime.now().strftime('%d.%m.%Y')}\n\n"
                    f"Kerakli bo'limni tanlang:")
            await query.edit_message_text(
                text, 
                reply_markup=get_main_keyboard(user_is_admin=True)
            )
        else:
            await query.edit_message_text(
                "Kerakli bo'limni tanlang:",
                reply_markup=get_main_keyboard(user_can_edit=db_user.can_edit)
            )
        session.close()
        return
    
    # Qidirish
    if data == "search":
        context.user_data['state'] = SEARCH
        await query.edit_message_text(
            "🔍 Qidirish uchun tovar nomi yoki kalit so'zni kiriting:",
            reply_markup=get_back_button()
        )
        session.close()
        return
    
    # Kategoriyalar
    if data == "categories":
        categories = session.query(Category).filter_by(parent_id=None).all()
        cat_list = [{'id': c.id, 'name': c.name} for c in categories]
        await query.edit_message_text(
            "📂 Kategoriyalar:",
            reply_markup=get_categories_keyboard(cat_list)
        )
        session.close()
        return
    
    # Kategoriya ichiga kirish
    if data.startswith("cat_"):
        category_id = int(data.split("_")[1])
        category = session.query(Category).filter_by(id=category_id).first()
        
        if not category:
            await query.edit_message_text("❌ Kategoriya topilmadi!")
            session.close()
            return
        
        subcats = session.query(Category).filter_by(parent_id=category_id).all()
        products = session.query(Product).filter_by(category_id=category_id).all()
        
        text = f"📂 {category.name}\n\n"
        
        if subcats:
            text += "📁 Pastki kategoriyalar:\n"
            for sc in subcats:
                text += f"• {sc.name}\n"
            text += "\n"
        
        if products:
            text += "📦 Tovarlar:\n"
            for p in products:
                text += f"• {p.name} - {p.quantity} dona\n"
        else:
            text += "Bu kategoriyada tovarlar yo'q."
        
        buttons = []
        for sc in subcats:
            buttons.append([InlineKeyboardButton(f"📁 {sc.name}", callback_data=f"cat_{sc.id}")])
        
        for p in products:
            buttons.append([InlineKeyboardButton(f"📦 {p.name}", callback_data=f"view_{p.id}")])
        
        if db_user.is_admin:
            buttons.append([InlineKeyboardButton("➕ Tovar qo'shish", callback_data=f"add_product_cat_{category_id}")])
            buttons.append([InlineKeyboardButton("➕ Subkategoriya", callback_data=f"add_cat_{category_id}")])
        
        buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data="categories")])
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        session.close()
        return
    
    # Tovarni ko'rish
    if data.startswith("view_"):
        product_id = int(data.split("_")[1])
        product = session.query(Product).filter_by(id=product_id).first()
        
        if not product:
            await query.edit_message_text("❌ Tovar topilmadi!")
            session.close()
            return
        
        text = await get_product_info_text(product, include_history=True)
        
        if product.media_channel_message_id:
            try:
                await context.bot.forward_message(
                    chat_id=user.id,
                    from_chat_id=MEDIA_CHANNEL_ID,
                    message_id=product.media_channel_message_id
                )
            except:
                await context.bot.send_message(
                    chat_id=user.id,
                    text="❌ Rasm topilmadi yoki kanaldan o'chirilgan!"
                )
        
        await query.edit_message_text(
            text,
            reply_markup=get_product_actions_keyboard(product_id, db_user.is_admin),
            parse_mode='HTML'
        )
        session.close()
        return
    
    # Tahrirlash
    if data.startswith("edit_"):
        if not db_user.is_admin and not db_user.can_edit:
            await query.edit_message_text("❌ Sizda tahrirlash huquqi yo'q!")
            session.close()
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
            
            field_names = {
                'photo': 'yangi rasm',
                'name': 'yangi nom',
                'purchase_usd': 'yangi kelgan narx ($)',
                'purchase_uzs': 'yangi kelgan narx (so\'m)',
                'selling_usd': 'yangi sotilish narxi ($)',
                'selling_uzs': 'yangi sotilish narxi (so\'m)',
                'quantity': 'yangi soni',
                'keywords': 'yangi kalit so\'zlar (vergul bilan)',
                'category': 'yangi kategoriya ID si'
            }
            
            await query.edit_message_text(
                f"📝 {field_names.get(field, 'yangi ma\'lumot')}ni kiriting:",
                reply_markup=get_back_button(f"edit_{product_id}")
            )
            context.user_data['state'] = EDIT_WAITING
        
        session.close()
        return
    
    # O'chirish
    if data.startswith("delete_"):
        if not db_user.is_admin:
            await query.edit_message_text("❌ Sizda o'chirish huquqi yo'q!")
            session.close()
            return
        
        product_id = int(data.split("_")[1])
        product = session.query(Product).filter_by(id=product_id).first()
        
        if product:
            session.delete(product)
            session.commit()
            await query.edit_message_text("✅ Tovar o'chirildi!")
        else:
            await query.edit_message_text("❌ Tovar topilmadi!")
        
        session.close()
        return
    
    # Tovar qo'shish
    if data == "add_product" or data.startswith("add_product_cat_"):
        if not db_user.is_admin:
            await query.edit_message_text("❌ Sizda tovar qo'shish huquqi yo'q!")
            session.close()
            return
        
        if data.startswith("add_product_cat_"):
            category_id = int(data.split("_")[3])
            context.user_data['new_product_category'] = category_id
        
        context.user_data['new_product'] = {}
        context.user_data['state'] = ADD_PRODUCT_NAME
        
        await query.edit_message_text(
            "📝 Tovar nomini kiriting:",
            reply_markup=get_back_button("categories")
        )
        session.close()
        return
    
    # Kategoriya qo'shish
    if data.startswith("add_cat_"):
        if not db_user.is_admin:
            await query.edit_message_text("❌ Sizda kategoriya qo'shish huquqi yo'q!")
            session.close()
            return
        
        parent_id = int(data.split("_")[2])
        context.user_data['new_category_parent'] = parent_id
        context.user_data['state'] = ADD_PRODUCT_CATEGORY
        
        await query.edit_message_text(
            "📝 Yangi kategoriya nomini kiriting:",
            reply_markup=get_back_button("categories")
        )
        session.close()
        return
    
    # Statistika
    if data == "stats":
        if not db_user.is_admin and not db_user.can_edit:
            await query.edit_message_text("❌ Sizda statistika ko'rish huquqi yo'q!")
            session.close()
            return
        
        products = session.query(Product).all()
        total_products = len(products)
        total_quantity = sum(p.quantity for p in products)
        total_purchase_usd = sum(p.purchase_price_usd * p.quantity for p in products)
        total_selling_usd = sum(p.selling_price_usd * p.quantity for p in products)
        potential_profit = total_selling_usd - total_purchase_usd
        categories = session.query(Category).count()
        
        text = (f"📊 STATISTIKA\n\n"
                f"📦 Jami tovarlar: {total_products}\n"
                f"📂 Kategoriyalar: {categories}\n"
                f"🔢 Jami soni: {total_quantity} dona\n\n"
                f"💰 Kelgan narxi (jami): ${total_purchase_usd:,.0f}\n"
                f"💵 Sotilish narxi (jami): ${total_selling_usd:,.0f}\n"
                f"📈 Potensial foyda: ${potential_profit:,.0f}\n\n"
                f"🕐 Yangilangan: {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}")
        
        await query.edit_message_text(text, reply_markup=get_back_button())
        session.close()
        return
    
    # Foydalanuvchilar
    if data == "users":
        if not db_user.is_admin:
            await query.edit_message_text("❌ Sizda foydalanuvchilar ro'yxatini ko'rish huquqi yo'q!")
            session.close()
            return
        
        users = session.query(User).all()
        user_list = [{'id': u.id, 'telegram_id': u.telegram_id, 'username': u.username or '-', 
                      'first_name': u.first_name, 'is_authorized': u.is_authorized, 
                      'can_edit': u.can_edit} for u in users]
        
        await query.edit_message_text(
            "👥 Foydalanuvchilar:",
            reply_markup=get_users_keyboard(user_list)
        )
        session.close()
        return
    
    # Foydalanuvchi ma'lumotlari
    if data.startswith("user_"):
        if not db_user.is_admin:
            await query.edit_message_text("❌ Ruxsat yo'q!")
            session.close()
            return
        
        user_id = int(data.split("_")[1])
        target_user = session.query(User).filter_by(id=user_id).first()
        
        if target_user:
            status = "✅ Tasdiqlangan" if target_user.is_authorized else "❌ Tasdiqlanmagan"
            edit_rights = "✏️ Tahrirlash huquqi bor" if target_user.can_edit else "👁 Faqat ko'rish"
            
            text = (f"👤 Foydalanuvchi ma'lumotlari:\n\n"
                    f"🆔 ID: {target_user.telegram_id}\n"
                    f"📝 Ism: {target_user.first_name}\n"
                    f"👤 Username: @{target_user.username or 'yoq'}\n"
                    f"📊 Status: {status}\n"
                    f"✏️ Huquq: {edit_rights}\n"
                    f"📅 Qo'shilgan: {target_user.created_at.strftime('%d.%m.%Y')}")
            
            await query.edit_message_text(
                text,
                reply_markup=get_user_actions_keyboard(target_user.id)
            )
        else:
            await query.edit_message_text("❌ Foydalanuvchi topilmadi!")
        
        session.close()
        return
    
    # Foydalanuvchini tasdiqlash/rad etish
    if data.startswith("approve_") and not data.startswith("approve_req_"):
        if not db_user.is_admin:
            await query.edit_message_text("❌ Ruxsat yo'q!")
            session.close()
            return
        
        user_id = int(data.split("_")[1])
        target_user = session.query(User).filter_by(id=user_id).first()
        
        if target_user:
            target_user.is_authorized = True
            session.commit()
            await query.edit_message_text(f"✅ Foydalanuvchi {target_user.first_name} tasdiqlandi!")
            
            try:
                await context.bot.send_message(
                    target_user.telegram_id,
                    "✅ Siz tasdiqlandingiz! Endi botdan foydalanishingiz mumkin.\n"
                    "/start ni bosing."
                )
            except:
                pass
        else:
            await query.edit_message_text("❌ Foydalanuvchi topilmadi!")
        
        session.close()
        return
    
    if data.startswith("reject_") and not data.startswith("reject_req_"):
        if not db_user.is_admin:
            await query.edit_message_text("❌ Ruxsat yo'q!")
            session.close()
            return
        
        user_id = int(data.split("_")[1])
        target_user = session.query(User).filter_by(id=user_id).first()
        
        if target_user:
            target_user.is_authorized = False
            session.commit()
            await query.edit_message_text(f"❌ Foydalanuvchi {target_user.first_name} rad etildi!")
            
            try:
                await context.bot.send_message(
                    target_user.telegram_id,
                    "❌ Sizning so'rovingiz rad etildi."
                )
            except:
                pass
        else:
            await query.edit_message_text("❌ Foydalanuvchi topilmadi!")
        
        session.close()
        return
    
    # Tahrirlash huquqini o'zgartirish
    if data.startswith("toggle_edit_"):
        if not db_user.is_admin:
            await query.edit_message_text("❌ Ruxsat yo'q!")
            session.close()
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
        
        session.close()
        return
    
    # Foydalanuvchini o'chirish
    if data.startswith("remove_user_"):
        if not db_user.is_admin:
            await query.edit_message_text("❌ Ruxsat yo'q!")
            session.close()
            return
        
        user_id = int(data.split("_")[2])
        target_user = session.query(User).filter_by(id=user_id).first()
        
        if target_user and target_user.telegram_id != ADMIN_ID:
            session.delete(target_user)
            session.commit()
            await query.edit_message_text("✅ Foydalanuvchi o'chirildi!")
        else:
            await query.edit_message_text("❌ Foydalanuvchi topilmadi yoki adminni o'chirib bo'lmaydi!")
        
        session.close()
        return
    
    # Ruxsat berish
    if data == "grant_access":
        if not db_user.is_admin:
            await query.edit_message_text("❌ Ruxsat yo'q!")
            session.close()
            return
        
        context.user_data['state'] = GRANT_ACCESS_WAITING
        await query.edit_message_text(
            "👤 Ruxsat bermoqchi bo'lgan foydalanuvchining Telegram ID sini kiriting:",
            reply_markup=get_back_button()
        )
        session.close()
        return
    
    # Eksport/Import
    if data == "export_import":
        if not db_user.is_admin:
            await query.edit_message_text("❌ Ruxsat yo'q!")
            session.close()
            return
        
        await query.edit_message_text(
            "📥 Eksport / Import bo'limi:",
            reply_markup=get_export_import_keyboard()
        )
        session.close()
        return
    
    if data == "export_excel":
        if not db_user.is_admin:
            await query.edit_message_text("❌ Ruxsat yo'q!")
            session.close()
            return
        
        await query.edit_message_text("⏳ Excel fayl tayyorlanmoqda...")
        
        filename = await export_to_excel()
        
        with open(filename, 'rb') as f:
            await context.bot.send_document(
                chat_id=user.id,
                document=f,
                filename=f"tovarlar_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                caption="✅ Tovarlar ro'yxati"
            )
        
        os.remove(filename)
        session.close()
        return
    
    if data == "import_excel":
        if not db_user.is_admin:
            await query.edit_message_text("❌ Ruxsat yo'q!")
            session.close()
            return
        
        context.user_data['state'] = IMPORT_WAITING
        await query.edit_message_text(
            "📤 Excel faylni yuboring (Eslatma: barcha eski ma'lumotlar o'chib, yangi ma'lumotlar yoziladi):",
            reply_markup=get_back_button()
        )
        session.close()
        return
    
    if data == "download_backup":
        if not db_user.is_admin:
            await query.edit_message_text("❌ Ruxsat yo'q!")
            session.close()
            return
        
        backup_file = backup_database()
        
        with open(backup_file, 'rb') as f:
            await context.bot.send_document(
                chat_id=user.id,
                document=f,
                filename=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                caption="✅ Ma'lumotlar bazasi backup fayli"
            )
        
        session.close()
        return
    
    if data == "restore_backup":
        if not db_user.is_admin:
            await query.edit_message_text("❌ Ruxsat yo'q!")
            session.close()
            return
        
        context.user_data['state'] = RESTORE_WAITING
        await query.edit_message_text(
            "🔄 Backup faylni yuboring (.db fayl):",
            reply_markup=get_back_button()
        )
        session.close()
        return
    
    if data == "clear_database":
        if not db_user.is_admin:
            await query.edit_message_text("❌ Ruxsat yo'q!")
            session.close()
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
        session.close()
        return
    
    if data == "confirm_clear":
        if not db_user.is_admin:
            await query.edit_message_text("❌ Ruxsat yo'q!")
            session.close()
            return
        
        session.query(PriceHistory).delete()
        session.query(Product).delete()
        session.query(Category).delete()
        session.commit()
        
        await query.edit_message_text(
            "✅ Barcha ma'lumotlar tozalandi!",
            reply_markup=get_back_button()
        )
        session.close()
        return
    
    if data == "export_only":
        if not db_user.can_edit:
            await query.edit_message_text("❌ Ruxsat yo'q!")
            session.close()
            return
        
        filename = await export_to_excel()
        
        with open(filename, 'rb') as f:
            await context.bot.send_document(
                chat_id=user.id,
                document=f,
                filename=f"tovarlar_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                caption="✅ Tovarlar ro'yxati"
            )
        
        os.remove(filename)
        session.close()
        return
    
    session.close()

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    
    session = Session()
    db_user = session.query(User).filter_by(telegram_id=user.id).first()
    
    if not db_user or (not db_user.is_authorized and not db_user.is_admin):
        await update.message.reply_text(
            "❌ Siz botdan foydalana olmaysiz. Avval ruxsat oling.",
            reply_markup=get_access_request_keyboard()
        )
        session.close()
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
            
            for product in products[:10]:
                text = await get_product_info_text(product)
                
                if product.media_channel_message_id:
                    try:
                        await context.bot.forward_message(
                            chat_id=user.id,
                            from_chat_id=MEDIA_CHANNEL_ID,
                            message_id=product.media_channel_message_id
                        )
                    except:
                        pass
                
                await update.message.reply_text(
                    text,
                    reply_markup=get_product_actions_keyboard(product.id, db_user.is_admin),
                    parse_mode='HTML'
                )
            
            if len(products) > 10:
                await update.message.reply_text(f"Yana {len(products) - 10} ta tovar bor...")
        
        context.user_data['state'] = None
        session.close()
        return
    
    # Tovar qo'shish - nom
    if state == ADD_PRODUCT_NAME:
        context.user_data['new_product']['name'] = text
        context.user_data['state'] = ADD_PRODUCT_PHOTO
        await update.message.reply_text(
            "🖼 Tovar rasmini yuboring (yoki /skip ni bosing):",
            reply_markup=get_back_button()
        )
        session.close()
        return
    
    # Tovar qo'shish - rasm
    if state == ADD_PRODUCT_PHOTO:
        if update.message.photo:
            photo = update.message.photo[-1]
            
            sent_message = await context.bot.send_photo(
                chat_id=MEDIA_CHANNEL_ID,
                photo=photo.file_id,
                caption=f"#{context.user_data['new_product']['name'].replace(' ', '_')}"
            )
            
            context.user_data['new_product']['media_message_id'] = sent_message.message_id
            context.user_data['new_product']['media_file_id'] = photo.file_id
        
        context.user_data['state'] = ADD_PRODUCT_PURCHASE_USD
        await update.message.reply_text(
            "💰 Kelgan narxini kiriting ($):",
            reply_markup=get_back_button()
        )
        session.close()
        return
    
    # Tovar qo'shish - kelgan narx $
    if state == ADD_PRODUCT_PURCHASE_USD:
        try:
            context.user_data['new_product']['purchase_usd'] = float(text.replace(',', '.'))
            context.user_data['state'] = ADD_PRODUCT_PURCHASE_UZS
            await update.message.reply_text(
                "💰 Kelgan narxini kiriting (so'm, 0 bo'lsa 0 yozing):",
                reply_markup=get_back_button()
            )
        except:
            await update.message.reply_text("❌ Noto'g'ri format! Qayta kiriting:")
        session.close()
        return
    
    # Tovar qo'shish - kelgan narx so'm
    if state == ADD_PRODUCT_PURCHASE_UZS:
        try:
            context.user_data['new_product']['purchase_uzs'] = float(text.replace(',', '.'))
            context.user_data['state'] = ADD_PRODUCT_SELLING_USD
            await update.message.reply_text(
                "💵 Sotilish narxini kiriting ($):",
                reply_markup=get_back_button()
            )
        except:
            await update.message.reply_text("❌ Noto'g'ri format! Qayta kiriting:")
        session.close()
        return
    
    # Tovar qo'shish - sotilish narx $
    if state == ADD_PRODUCT_SELLING_USD:
        try:
            context.user_data['new_product']['selling_usd'] = float(text.replace(',', '.'))
            context.user_data['state'] = ADD_PRODUCT_SELLING_UZS
            await update.message.reply_text(
                "💵 Sotilish narxini kiriting (so'm, 0 bo'lsa 0 yozing):",
                reply_markup=get_back_button()
            )
        except:
            await update.message.reply_text("❌ Noto'g'ri format! Qayta kiriting:")
        session.close()
        return
    
    # Tovar qo'shish - sotilish narx so'm
    if state == ADD_PRODUCT_SELLING_UZS:
        try:
            context.user_data['new_product']['selling_uzs'] = float(text.replace(',', '.'))
            context.user_data['state'] = ADD_PRODUCT_QUANTITY
            await update.message.reply_text(
                "📦 Soni (dona):",
                reply_markup=get_back_button()
            )
        except:
            await update.message.reply_text("❌ Noto'g'ri format! Qayta kiriting:")
        session.close()
        return
    
    # Tovar qo'shish - soni
    if state == ADD_PRODUCT_QUANTITY:
        try:
            context.user_data['new_product']['quantity'] = int(text)
            context.user_data['state'] = ADD_PRODUCT_KEYWORDS
            await update.message.reply_text(
                "🔑 Kalit so'zlar (vergul bilan ajrating):",
                reply_markup=get_back_button()
            )
        except:
            await update.message.reply_text("❌ Noto'g'ri format! Qayta kiriting:")
        session.close()
        return
    
    # Tovar qo'shish - kalit so'zlar
    if state == ADD_PRODUCT_KEYWORDS:
        context.user_data['new_product']['keywords'] = text
        
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
                reply_markup=get_back_button()
            )
        session.close()
        return
    
    # Kategoriya qo'shish
    if state == ADD_PRODUCT_CATEGORY:
        category_name = text
        parent_id = context.user_data.get('new_category_parent')
        
        category = Category(name=category_name, parent_id=parent_id)
        session.add(category)
        session.flush()
        
        if 'new_product' in context.user_data:
            context.user_data['new_product']['category_id'] = category.id
            
            product = Product(
                name=context.user_data['new_product']['name'],
                category_id=category.id,
                purchase_price_usd=context.user_data['new_product']['purchase_usd'],
                purchase_price_uzs=context.user_data['new_product']['purchase_uzs'],
                selling_price_usd=context.user_data['new_product']['selling_usd'],
                selling_price_uzs=context.user_data['new_product']['selling_uzs'],
                quantity=context.user_data['new_product']['quantity'],
                keywords=context.user_data['new_product'].get('keywords', ''),
                media_channel_message_id=context.user_data['new_product'].get('media_message_id')
            )
            session.add(product)
            session.commit()
            
            await update.message.reply_text(
                "✅ Tovar muvaffaqiyatli qo'shildi!",
                reply_markup=get_back_button()
            )
            
            del context.user_data['new_product']
            if 'new_category_parent' in context.user_data:
                del context.user_data['new_category_parent']
        else:
            session.commit()
            await update.message.reply_text(
                f"✅ Kategoriya qo'shildi: {category_name}",
                reply_markup=get_back_button("categories")
            )
            if 'new_category_parent' in context.user_data:
                del context.user_data['new_category_parent']
        
        context.user_data['state'] = None
        session.close()
        return
    
    # Tahrirlash
    if state == EDIT_WAITING:
        product_id = context.user_data.get('editing_product')
        field = context.user_data.get('editing_field')
        
        product = session.query(Product).filter_by(id=product_id).first()
        if not product:
            await update.message.reply_text("❌ Tovar topilmadi!")
            context.user_data['state'] = None
            session.close()
            return
        
        old_data = {
            'purchase_usd': product.purchase_price_usd,
            'purchase_uzs': product.purchase_price_uzs,
            'selling_usd': product.selling_price_usd,
            'selling_uzs': product.selling_price_uzs,
            'quantity': product.quantity
        }
        
        if field == 'name':
            product.name = text
        elif field == 'purchase_usd':
            try:
                product.purchase_price_usd = float(text.replace(',', '.'))
            except:
                await update.message.reply_text("❌ Noto'g'ri format!")
                session.close()
                return
        elif field == 'purchase_uzs':
            try:
                product.purchase_price_uzs = float(text.replace(',', '.'))
            except:
                await update.message.reply_text("❌ Noto'g'ri format!")
                session.close()
                return
        elif field == 'selling_usd':
            try:
                product.selling_price_usd = float(text.replace(',', '.'))
            except:
                await update.message.reply_text("❌ Noto'g'ri format!")
                session.close()
                return
        elif field == 'selling_uzs':
            try:
                product.selling_price_uzs = float(text.replace(',', '.'))
            except:
                await update.message.reply_text("❌ Noto'g'ri format!")
                session.close()
                return
        elif field == 'quantity':
            try:
                product.quantity = int(text)
            except:
                await update.message.reply_text("❌ Noto'g'ri format!")
                session.close()
                return
        elif field == 'keywords':
            product.keywords = text
        
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
        session.close()
        return
    
    # Import
    if state == IMPORT_WAITING:
        if update.message.document:
            file = await update.message.document.get_file()
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
        else:
            await update.message.reply_text("❌ Iltimos, Excel fayl yuboring!")
        
        context.user_data['state'] = None
        session.close()
        return
    
    # Backup tiklash
    if state == RESTORE_WAITING:
        if update.message.document:
            file = await update.message.document.get_file()
            filename = f"data/restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            await file.download_to_drive(filename)
            
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
        else:
            await update.message.reply_text("❌ Iltimos, .db fayl yuboring!")
        
        context.user_data['state'] = None
        session.close()
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
                    f"✅ Foydalanuvchi {target_user.first_name} ga ruxsat berildi!",
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
        session.close()
        return
    
    session.close()

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state')
    
    if state == ADD_PRODUCT_PHOTO:
        photo = update.message.photo[-1]
        
        sent_message = await context.bot.send_photo(
            chat_id=MEDIA_CHANNEL_ID,
            photo=photo.file_id,
            caption=f"#{context.user_data['new_product']['name'].replace(' ', '_')}"
        )
        
        context.user_data['new_product']['media_message_id'] = sent_message.message_id
        context.user_data['new_product']['media_file_id'] = photo.file_id
        
        context.user_data['state'] = ADD_PRODUCT_PURCHASE_USD
        await update.message.reply_text(
            "💰 Kelgan narxini kiriting ($):",
            reply_markup=get_back_button()
        )
    elif state == EDIT_WAITING:
        field = context.user_data.get('editing_field')
        if field == 'photo':
            product_id = context.user_data.get('editing_product')
            session = Session()
            product = session.query(Product).filter_by(id=product_id).first()
            
            if product:
                photo = update.message.photo[-1]
                sent_message = await context.bot.send_photo(
                    chat_id=MEDIA_CHANNEL_ID,
                    photo=photo.file_id,
                    caption=f"#{product.name.replace(' ', '_')}"
                )
                
                product.media_channel_message_id = sent_message.message_id
                session.commit()
                
                await update.message.reply_text(
                    "✅ Rasm yangilandi!",
                    reply_markup=get_back_button(f"view_{product_id}")
                )
            
            session.close()
            context.user_data['state'] = None

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Xatolik: {context.error}")
    
    try:
        if update and update.effective_chat:
            await context.bot.send_message(
                update.effective_chat.id,
                "❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring."
            )
    except:
        pass

# ==================== ASOSIY FUNKSIYA ====================

def main():
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
    
    if not MEDIA_CHANNEL_ID or MEDIA_CHANNEL_ID == 0:
        errors.append("❌ MEDIA_CHANNEL_ID noto'g'ri yoki kiritilmagan!")
    
    if not os.path.exists('data'):
        try:
            os.makedirs('data')
            logger.info("📁 'data' papkasi yaratildi")
        except:
            errors.append("❌ 'data' papkasini yaratib bo'lmadi!")
    
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
