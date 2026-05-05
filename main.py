import os
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, CallbackQueryHandler, filters
)

TOKEN = os.getenv("TOKEN")

ADMIN_ID = 123456789
TARGET_CHANNEL = -1003993758461
SOURCE_CHANNEL = -1002668690958

AUTO_MODE = False
user_states = {}
pending_posts = {}

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


# --- SCHEDULE ---
async def schedule_post(context, chat_id, content, send_time):
    delay = (send_time - datetime.now()).total_seconds()

    if delay > 0:
        await asyncio.sleep(delay)

    await send_content(context, chat_id, content)


# --- CHANNEL DINLEME ---
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

    # AUTO MODE
    if AUTO_MODE:
        await send_content(context, TARGET_CHANNEL, content)
        return

    # MANUEL MODE
    keyboard = [[
        InlineKeyboardButton("✅ Paylaş", callback_data="approve"),
        InlineKeyboardButton("✏️ Düzenle", callback_data="edit"),
        InlineKeyboardButton("⏱ Zamanla", callback_data="schedule"),
        InlineKeyboardButton("❌ Sil", callback_data="delete")
    ]]

    pending_posts[ADMIN_ID] = content

    await context.bot.send_message(
        ADMIN_ID,
        f"Yeni içerik:\n\n{content['text']}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# --- BUTONLAR ---
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    content = pending_posts.get(ADMIN_ID)
    if not content:
        return

    if query.data == "approve":
        await send_content(context, TARGET_CHANNEL, content)

    elif query.data == "edit":
        user_states[ADMIN_ID] = "editing"
        await query.message.reply_text("Yeni metni gönder:")

    elif query.data == "schedule":
        user_states[ADMIN_ID] = "scheduling"
        await query.message.reply_text("Saat gir (18:30)")

    elif query.data == "delete":
        await query.message.reply_text("Silindi")


# --- TEXT INPUT ---
async def text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id != ADMIN_ID:
        return

    state = user_states.get(user_id)

    if state == "editing":
        content = pending_posts[user_id]
        content["text"] = process_text(update.message.text)

        await send_content(context, TARGET_CHANNEL, content)
        user_states[user_id] = None

    elif state == "scheduling":
        try:
            hour, minute = map(int, update.message.text.split(":"))
            now = datetime.now()

            send_time = now.replace(hour=hour, minute=minute, second=0)

            if send_time < now:
                send_time = send_time.replace(day=now.day + 1)

            content = pending_posts[user_id]

            asyncio.create_task(schedule_post(context, TARGET_CHANNEL, content, send_time))

            await update.message.reply_text("Zamanlandı")

        except:
            await update.message.reply_text("Hatalı saat formatı")


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


# --- DURUM KOMUTU ---
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    mode = "AÇIK" if AUTO_MODE else "KAPALI"

    await update.message.reply_text(
        f"🤖 Bot Durumu:\n\n"
        f"AUTO MODE: {mode}\n"
        f"Bot aktif ve çalışıyor."
    )


# --- APP ---
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.ALL, handle_channel))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_input))

app.add_handler(CommandHandler("auto_on", auto_on))
app.add_handler(CommandHandler("auto_off", auto_off))
app.add_handler(CommandHandler("durum", status))

print("Bot çalışıyor...")
app.run_polling()
