#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Do'kon boshqaruvi uchun Telegram bot
Muallif: @maestro_o
Versiya: 4.0
"""

import logging
import os
from datetime import datetime
import pandas as pd
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

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session

os.makedirs("data", exist_ok=True)

engine = create_engine(
    "sqlite:///data/shop_bot.db",
    connect_args={"check_same_thread": False}
)

db_session = scoped_session(
    sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )
)

Base = declarative_base()
Base.query = db_session.query_property()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)

    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)

    is_admin = Column(Boolean, default=False)
    is_authorized = Column(Boolean, default=False)

    branch_type = Column(String, default="main")
    branch_name = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)
    class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)

    name = Column(String)
    description = Column(Text)

    price = Column(Float)

    category_id = Column(Integer, ForeignKey("categories.id"))

    photo_file_id = Column(String)
    media_group_message_id = Column(Integer)

    created_at = Column(DateTime, default=datetime.utcnow)


class AccessRequest(Base):
    __tablename__ = "access_requests"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer)
    username = Column(String)

    branch_name = Column(String)

    status = Column(String, default="pending")

    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


ADD_PRODUCT_NAME, ADD_PRODUCT_DESC, ADD_PRODUCT_PRICE, ADD_PRODUCT_PHOTO = range(4)


def get_main_keyboard(is_admin=False):

    keyboard = [
        [
            InlineKeyboardButton("📦 Tovarlar", callback_data="products")
        ]
    ]

    if is_admin:
        keyboard.append(
            [InlineKeyboardButton("➕ Tovar qo‘shish", callback_data="add_product")]
        )

    keyboard.append(
        [InlineKeyboardButton("ℹ️ Yordam", callback_data="help")]
    )

    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    session = db_session()

    db_user = session.query(User).filter_by(telegram_id=user.id).first()

    if not db_user:

        db_user = User(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )

        if user.id == ADMIN_ID:
            db_user.is_admin = True
            db_user.is_authorized = True

        session.add(db_user)
        session.commit()

    if not db_user.is_authorized:

        request = AccessRequest(
            user_id=db_user.id,
            username=user.username,
            branch_name="unknown"
        )

        session.add(request)
        session.commit()

        await update.message.reply_text(
            "⏳ Admin tasdiqlashini kuting."
        )

        return

    await update.message.reply_text(
        "🏠 Bosh menyu",
        reply_markup=get_main_keyboard(db_user.is_admin)
    )
    async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    session = db_session()

    user = session.query(User).filter_by(
        telegram_id=query.from_user.id
    ).first()

    if not user:
        return ConversationHandler.END

    if not user.is_admin and user.branch_type != "parasite":
        await query.message.reply_text("❌ Sizda ruxsat yo‘q")
        return ConversationHandler.END

    await query.message.reply_text("📝 Tovar nomini kiriting")

    return ADD_PRODUCT_NAME


async def add_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["product"] = {}

    context.user_data["product"]["name"] = update.message.text

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ O‘tkazib yuborish", callback_data="skip_desc")]
    ])

    await update.message.reply_text(
        "📄 Tavsif kiriting yoki o'tkazib yuboring",
        reply_markup=keyboard
    )

    return ADD_PRODUCT_DESC


async def add_product_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["product"]["description"] = update.message.text

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ O‘tkazib yuborish", callback_data="skip_price")]
    ])

    await update.message.reply_text(
        "💰 Narx kiriting",
        reply_markup=keyboard
    )

    return ADD_PRODUCT_PRICE


async def add_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:
        price = float(update.message.text)
    except:
        await update.message.reply_text("❌ Narx raqam bo‘lishi kerak")
        return ADD_PRODUCT_PRICE

    context.user_data["product"]["price"] = price

    await update.message.reply_text(
        "🖼 Rasm yuboring"
    )

    return ADD_PRODUCT_PHOTO


async def add_product_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    session = db_session()

    photo = update.message.photo[-1]

    product = Product(
        name=context.user_data["product"]["name"],
        description=context.user_data["product"].get("description"),
        price=context.user_data["product"].get("price", 0),
        photo_file_id=photo.file_id
    )

    session.add(product)
    session.commit()

    caption = f"🆔 ID: {product.id}\n📦 {product.name}"

    await update.message.reply_photo(
        photo.file_id,
        caption=caption
    )

    await update.message.reply_text("✅ Tovar saqlandi")

    return ConversationHandler.END
    async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    data = query.data

    session = db_session()

    user = session.query(User).filter_by(
        telegram_id=query.from_user.id
    ).first()

    if data == "main_menu":

        await query.message.delete()

        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="🏠 Bosh menyu",
            reply_markup=get_main_keyboard(user.is_admin)
        )

        return

    if data == "add_product":

        return await add_product_start(update, context)

    if data.startswith("approve_"):

        request_id = int(data.split("_")[1])

        request = session.query(AccessRequest).filter_by(
            id=request_id
        ).first()

        if not request:
            await query.message.reply_text("❌ So‘rov topilmadi")
            return

        user_obj = session.query(User).filter_by(
            id=request.user_id
        ).first()

        if not user_obj:
            await query.message.reply_text("❌ Foydalanuvchi topilmadi")
            return

        user_obj.is_authorized = True

        session.commit()

        await context.bot.send_message(
            chat_id=user_obj.telegram_id,
            text="✅ Sizga ruxsat berildi"
        )

        await query.message.edit_text("✅ Tasdiqlandi")

        return
        async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text("❌ Bekor qilindi")

    return ConversationHandler.END


def main():

    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(

        entry_points=[
            CallbackQueryHandler(add_product_start, pattern="add_product")
        ],

        states={

            ADD_PRODUCT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_name)
            ],

            ADD_PRODUCT_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_desc)
            ],

            ADD_PRODUCT_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_price)
            ],

            ADD_PRODUCT_PHOTO: [
                MessageHandler(filters.PHOTO, add_product_photo)
            ],

        },

        fallbacks=[
            CommandHandler("cancel", cancel)
        ]

    )

    application.add_handler(CommandHandler("start", start))

    application.add_handler(conv_handler)

    application.add_handler(CallbackQueryHandler(button_handler))

    application.run_polling()


if __name__ == "__main__":
    main()
    
