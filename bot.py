from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import ADMIN_ID, AUTO_REPLY, BOT_TOKEN, CHANNEL_ID
from database import (
    add_subscriber,
    get_subscribers,
    init_db,
    remove_subscriber,
    subscriber_count,
)


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_subscriber(user)
    await update.message.reply_text(
        "Welcome! You are subscribed. Send /stop to unsubscribe."
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    remove_subscriber(update.effective_user.id)
    await update.message.reply_text("You have been unsubscribed.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Available commands:\n"
        "/start - Subscribe to updates\n"
        "/stop - Unsubscribe\n"
        "/help - Show help"
    )
    if is_admin(update.effective_user.id):
        text += (
            "\n\nAdmin commands:\n"
            "/stats - Subscriber count\n"
            "/broadcast MESSAGE - Send text to subscribers\n"
            "/post MESSAGE - Post text to the channel"
        )
    await update.message.reply_text(text)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(f"Subscribers: {subscriber_count()}")


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    message = " ".join(context.args).strip()
    if not message:
        await update.message.reply_text("Usage: /broadcast Your message")
        return

    sent = 0
    failed = 0
    for user_id in get_subscribers():
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(
        f"Broadcast complete. Sent: {sent}, failed: {failed}"
    )


async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    message = " ".join(context.args).strip()
    if not message:
        await update.message.reply_text("Usage: /post Your channel message")
        return
    await context.bot.send_message(chat_id=CHANNEL_ID, text=message)
    await update.message.reply_text("Posted to channel.")


async def admin_media_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(AUTO_REPLY)
        return
    await update.message.copy(chat_id=CHANNEL_ID)
    await update.message.reply_text("Copied to channel.")


async def user_auto_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user and not is_admin(update.effective_user.id):
        await update.message.reply_text(AUTO_REPLY)


def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("post", post))

    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & ~filters.COMMAND & filters.User(user_id=ADMIN_ID),
            admin_media_to_channel,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & ~filters.COMMAND,
            user_auto_reply,
        )
    )

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
