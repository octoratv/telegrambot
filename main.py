import os
import asyncio
from datetime import datetime, timedelta
from collections import deque

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, CallbackQueryHandler, filters
)

# --- TOKEN ---
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise ValueError("TOKEN YOK!")

print("TOKEN OK")

# --- AYARLAR ---
ADMIN_ID = 1118580992
TARGET_CHANNEL = -1003993758461
SOURCE_CHANNEL = -1002668690958

AUTO_MODE = False

user_states = {}

# 🔥 FIFO QUEUE (EN ÖNEMLİ UPGRADE)
pending_queue = deque()

# --- METİN DEĞİŞTİRME ---
REPLACEMENTS = {
    "Titan Panel": "Octora Tv"
}

def replace_text(text):
    if not text:
        return text

    lower_text = text.lower()

    for old, new in REPLACEMENTS.items():
        if old in lower_text:
            start = lower_text.index(old)
            end = start + len(old)
            text = text[:start] + new + text[end:]

    return text


def process_text(text):
    return replace_text(text)


# --- GÖNDER ---
async def send_content(context, chat_id, content):
    try:
        if content["type"] == "text":
            await context.bot.send_message(chat_id, content["text"])

        elif content["type"] == "photo":
            await context.bot.send_photo(chat_id, content["file_id"], caption=content["text"])

        elif content["type"] == "video":
            await context.bot.send_video(chat_id, content["file_id"], caption=content["text"])

    except Exception as e:
        print("Gönderim hatası:", e)


# --- FIFO HELPERS ---
def add_to_queue(content):
    pending_queue.append(content)


def get_next_post():
    if pending_queue:
        return pending_queue.popleft()
    return None


# --- KANAL DİNLEME ---
async def handle_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global AUTO_MODE

    message = update.channel_post
    if not message:
        return

    if message.chat.id != SOURCE_CHANNEL:
        return

    text = message.text or message.caption or ""

    content = {
        "type": "text",
        "text": process_text(text)
    }

    if message.photo:
        content["type"] = "photo"
        content["file_id"] = message.photo[-1].file_id

    elif message.video:
        content["type"] = "video"
        content["file_id"] = message.video.file_id

    # --- AUTO MODE ---
    if AUTO_MODE:
        await send_content(context, TARGET_CHANNEL, content)
        return

    # 🔥 FIFO QUEUE'YA EKLE
    add_to_queue(content)

    keyboard = [[
        InlineKeyboardButton("✅ Gönder", callback_data="approve"),
        InlineKeyboardButton("⏭ Sonraki", callback_data="next"),
        InlineKeyboardButton("❌ Sil", callback_data="delete")
    ]]

    await context.bot.send_message(
        ADMIN_ID,
        f"Yeni içerik kuyruğa eklendi.\nQueue: {len(pending_queue)}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# --- BUTON ---
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    if query.data == "approve":
        content = get_next_post()
        if content:
            await send_content(context, TARGET_CHANNEL, content)

    elif query.data == "next":
        content = get_next_post()
        if content:
            await query.message.reply_text(f"Sıradaki:\n\n{content.get('text','')}")

    elif query.data == "delete":
        removed = get_next_post()
        await query.message.reply_text("Silindi")


# --- TEXT INPUT ---
async def text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id != ADMIN_ID:
        return

    state = user_states.get(user_id)

    if state == "editing":
        content = pending_queue[-1] if pending_queue else None

        if content:
            content["text"] = process_text(update.message.text)
            await send_content(context, TARGET_CHANNEL, content)

        user_states[user_id] = None


# --- AUTO MODE ---
async def auto_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global AUTO_MODE
    if update.effective_user.id == ADMIN_ID:
        AUTO_MODE = True
        await update.message.reply_text("AUTO AÇIK")


async def auto_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global AUTO_MODE
    if update.effective_user.id == ADMIN_ID:
        AUTO_MODE = False
        await update.message.reply_text("AUTO KAPALI")


# --- DURUM ---
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        f"🤖 BOT DURUMU\n\n"
        f"AUTO MODE: {'AÇIK' if AUTO_MODE else 'KAPALI'}\n"
        f"QUEUE: {len(pending_queue)}"
    )


# --- APP ---
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("auto_on", auto_on))
app.add_handler(CommandHandler("auto_off", auto_off))
app.add_handler(CommandHandler("durum", status))

app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_input))

app.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_channel))

print("Bot çalışıyor...")
app.run_polling()
