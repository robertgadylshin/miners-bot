import logging
import os
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from datetime import datetime

from db import init_db, get_db
from tasks import get_tokens_for_task
from handlers.barista import (
    cmd_tasks, cmd_balance, cmd_leaderboard,
    handle_task_photo, handle_new_member,
    handle_leaderboard_callback
)
from handlers.manager import (
    cmd_stats, cmd_addmanager,
    handle_approve_callback, handle_reject_callback
)
from handlers.admin import cmd_setup, cmd_locations, cmd_addlocation

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    if chat.type in ['group', 'supergroup']:
        db = get_db()
        location = db.execute(
            "SELECT * FROM locations WHERE chat_id = ?", (chat.id,)
        ).fetchone()

        if not location:
            await update.message.reply_text(
                "⚠️ This group is not registered yet.\n"
                "Ask your admin to run /setup to configure this location."
            )
            return

        db.execute("""
            INSERT OR IGNORE INTO users (telegram_id, username, full_name, location_id, role)
            VALUES (?, ?, ?, ?, 'barista')
        """, (user.id, user.username or '', user.full_name, location['id']))
        db.commit()

        await update.message.reply_text(
            f"☕ Welcome to *The Miners* task system, {user.first_name}!\n\n"
            f"📍 Location: *{location['name']}*\n\n"
            "Commands:\n"
            "• /tasks — today's task list\n"
            "• /balance — your tokens & stats\n"
            "• /leaderboard — team ranking\n\n"
            "Pick a task, complete it, take a photo and send it here "
            "with the task key as caption. Your manager approves it and you earn tokens! 🪙",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "👋 Hi! I'm The Miners task bot.\n"
            "Add me to your coffee shop group and run /setup to get started."
        )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "☕ *The Miners Task Bot*\n\n"
        "*Barista commands:*\n"
        "/tasks — today's checklist with token values\n"
        "/balance — your tokens, rank and recent history\n"
        "/leaderboard — team ranking (week / month)\n\n"
        "*How to submit a task:*\n"
        "1. Complete the task\n"
        "2. Take a photo\n"
        "3. Send the photo here\n"
        "4. Write the task key as caption (e.g. `mon_fridges`)\n"
        "5. Manager approves → tokens added ✅\n\n"
        "*Manager commands:*\n"
        "/stats — location stats and pending approvals\n"
        "/addmanager @username — promote to manager\n",
        parse_mode='Markdown'
    )


async def error_handler(update, context):
    logger.error(f"Exception: {context.error}", exc_info=context.error)


def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN environment variable not set")

    init_db()

    app = Application.builder().token(token).build()

    # General
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))

    # Barista
    app.add_handler(CommandHandler("tasks", cmd_tasks))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))

    # Manager
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("addmanager", cmd_addmanager))

    # Admin
    app.add_handler(CommandHandler("setup", cmd_setup))
    app.add_handler(CommandHandler("locations", cmd_locations))
    app.add_handler(CommandHandler("addlocation", cmd_addlocation))

    # Inline button callbacks
    app.add_handler(CallbackQueryHandler(handle_approve_callback,     pattern=r'^approve_'))
    app.add_handler(CallbackQueryHandler(handle_reject_callback,      pattern=r'^reject_'))
    app.add_handler(CallbackQueryHandler(handle_leaderboard_callback, pattern=r'^lb_'))

    # Photo submissions
    app.add_handler(MessageHandler(filters.PHOTO & filters.CaptionRegex(r'.+'), handle_task_photo))

    # Auto-register new group members
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_member))

    app.add_error_handler(error_handler)

    logger.info("Bot started...")
    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
