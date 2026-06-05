#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بوت تليغرام لتحويل الصور إلى WebP محسّنة لووردبريس.
نسخة Webhook للنشر على Render كـ Web Service (الخطة المجانية).
"""

import io
import os
import asyncio
import logging
from PIL import Image

from telegram import Update, InputFile
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ============= الإعدادات =============
# تُقرأ من متغيرات البيئة على Render (لا تكتب التوكن داخل الكود)
BOT_TOKEN = os.environ["BOT_TOKEN"]                 # من إعدادات Render
# Render يوفّر هذا المتغير تلقائياً ويحتوي رابط الخدمة العام
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL")
PORT = int(os.environ.get("PORT", "10000"))         # Render يحدّد المنفذ تلقائياً

MAX_WIDTH = 1200        # أقصى عرض مناسب لقوالب ووردبريس
MAX_HEIGHT = 1200       # أقصى ارتفاع
WEBP_QUALITY = 80       # جودة WebP
# ====================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلاً بك!\n\n"
        "أرسل لي أي صورة وسأحوّلها إلى صيغة WebP محسّنة لمواقع ووردبريس "
        "(حجم صغير وأبعاد مناسبة).\n\n"
        "📌 لتحويل أفضل (بدون ضغط من تليغرام) أرسل الصورة كـ «ملف / Document»."
    )


def convert_to_webp(image_bytes: bytes) -> bytes:
    """تحويل الصورة إلى WebP محسّن."""
    img = Image.open(io.BytesIO(image_bytes))

    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")

    img.thumbnail((MAX_WIDTH, MAX_HEIGHT), Image.LANCZOS)

    out = io.BytesIO()
    img.save(out, format="WEBP", quality=WEBP_QUALITY, method=6)
    out.seek(0)
    return out.read()


async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    status = await msg.reply_text("⏳ جارٍ التحويل...")

    try:
        if msg.photo:
            file = await msg.photo[-1].get_file()
            base_name = "image"
        elif msg.document:
            file = await msg.document.get_file()
            base_name = (msg.document.file_name or "image").rsplit(".", 1)[0]
        else:
            await status.edit_text("⚠️ أرسل لي صورة من فضلك.")
            return

        image_bytes = bytes(await file.download_as_bytearray())
        original_kb = len(image_bytes) / 1024

        webp_bytes = convert_to_webp(image_bytes)
        new_kb = len(webp_bytes) / 1024

        bio = io.BytesIO(webp_bytes)
        bio.name = f"{base_name}.webp"

        await msg.reply_document(
            document=InputFile(bio, filename=f"{base_name}.webp"),
            caption=(
                f"✅ تم التحويل إلى WebP\n"
                f"📦 الحجم: {original_kb:.0f}KB ← {new_kb:.0f}KB\n"
                f"📐 الجودة: {WEBP_QUALITY}%"
            ),
        )
        await status.delete()

    except Exception as e:
        logger.exception("خطأ في التحويل")
        await status.edit_text(f"❌ حدث خطأ أثناء التحويل:\n{e}")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))
    app.add_handler(MessageHandler(filters.Document.IMAGE, handle_image))

    if not WEBHOOK_URL:
        # احتياطي: التشغيل محلياً بالـ polling إذا لم يوجد رابط Render
        logger.info("لا يوجد RENDER_EXTERNAL_URL — التشغيل بـ polling محلياً.")
        app.run_polling()
        return

    # التشغيل بـ webhook على Render
    logger.info("تشغيل webhook على %s", WEBHOOK_URL)
    # ضمان وجود event loop في الخيط الرئيسي (متوافق مع Python 3.12+ و3.14)
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,                        # مسار سرّي لاستقبال التحديثات
        webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
    )


if __name__ == "__main__":
    main()
