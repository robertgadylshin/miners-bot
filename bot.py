import logging
import os
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

from db import init_db, get_db
from handlers.barista import (
    cmd_tasks, cmd_balance, cmd_leaderboard,
    handle_task_photo, handle_new_member,
    handle_leaderboard_callback,
)
from handlers.manager import (
    cmd_stats, cmd_addmanager,
    handle_approve_callback, handle_reject_callback,
    handle_custom_approve_callback,
)
from handlers.admin import (
    cmd_setup, cmd_settimezone, cmd_locations, cmd_addlocation, cmd_mystats,
    handle_adminstats_callback, handle_adminstats_back_callback,
)

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
                "This group is not registered yet.\n"
                "Ask your admin to run /setup to configure this location."
            )
            return

        db.execute("""
            INSERT OR IGNORE INTO users (telegram_id, username, full_name, location_id, role)
            VALUES (?, ?, ?, ?, 'barista')
        """, (user.id, user.username or '', user.full_name or '', location['id']))
        db.commit()

        await update.message.reply_text(
            f"Welcome to The Miners task system, {user.first_name}!\n\n"
            f"Location: {location['name']}\n\n"
            "• /tasks — today's task list\n"
            "• /balance — your points & stats\n"
            "• /leaderboard — team ranking\n\n"
            "Complete a task → take a photo → send it here with the task key as caption.\n"
            "For a custom task: CUSTOM I cleaned the storage room"
        )

    else:
        db = get_db()

        if user.username:
            try:
                db.execute(
                    "UPDATE users SET telegram_id = ?, full_name = ? "
                    "WHERE LOWER(username) = ? AND (telegram_id = 0 OR telegram_id IS NULL)",
                    (user.id, user.full_name or '', user.username.lower())
                )
                db.commit()
                logger.info(f"Updated telegram_id for username={user.username} to {user.id}")
            except Exception as e:
                logger.error(f"Error updating manager telegram_id: {e}")

        try:
            is_admin = db.execute(
                "SELECT * FROM admins WHERE telegram_id = ?", (user.id,)
            ).fetchone()

            is_mgr = db.execute(
                "SELECT u.*, l.name as loc_name FROM users u "
                "JOIN locations l ON l.id = u.location_id "
                "WHERE u.telegram_id = ? AND u.role = 'manager'",
                (user.id,)
            ).fetchall()

            logger.info(f"DM /start from {user.username} (id={user.id}), is_admin={bool(is_admin)}, is_mgr={len(is_mgr)}")

            if is_admin:
                await update.message.reply_text(
                    f"Hi {user.first_name}!\n\n"
                    "• /mystats — stats for all locations\n"
                    "• /locations — list all locations\n"
                )
            elif is_mgr:
                loc_lines = "\n".join(f"- {m['loc_name']}" for m in is_mgr)
                await update.message.reply_text(
                    f"Hi {user.first_name}!\n\n"
                    f"You are a manager for:\n{loc_lines}\n\n"
                    "You will now receive task submissions here for approval."
                )
            else:
                await update.message.reply_text(
                    "Hi! I'm The Miners task bot.\n"
                    "Add me to your coffee shop group and run /setup to get started."
                )
        except Exception as e:
            logger.error(f"Error in DM /start handler: {e}")
            await update.message.reply_text("Something went wrong. Please try again.")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "The Miners Task Bot\n\n"
        "Barista commands:\n"
        "/tasks — today's checklist\n"
        "/balance — points, rank and history\n"
        "/leaderboard — team ranking\n\n"
        "How to submit:\n"
        "Photo + task key as caption\n"
        "FRIDGES or fridges — any case works\n"
        "Multiple photos — send as album with caption on first photo\n"
        "Custom task: CUSTOM I cleaned the storage room\n\n"
        "Manager commands:\n"
        "/stats — location stats\n"
        "/addmanager @username — promote to manager\n\n"
        "Admin commands:\n"
        "/mystats — stats for all locations\n"
        "/settimezone Europe/Kiev — set local time for this group\n"
    )


async def error_handler(update, context):
    logger.error(f"Exception: {context.error}", exc_info=context.error)


async def post_init(application):
    from telegram import (
        BotCommandScopeAllGroupChats,
        BotCommandScopeAllPrivateChats,
        BotCommandScopeChat,
    )

    await application.bot.set_my_commands(
        [
            ("tasks",       "Today's task checklist"),
            ("balance",     "Your points & stats"),
            ("leaderboard", "Team ranking"),
        ],
        scope=BotCommandScopeAllGroupChats()
    )

    await application.bot.set_my_commands(
        [("start", "Activate notifications")],
        scope=BotCommandScopeAllPrivateChats()
    )

    admin_id = os.environ.get("SUPER_ADMIN_ID")
    if admin_id:
        try:
            await application.bot.set_my_commands(
                [
                    ("mystats",  "Stats for all locations"),
                    ("help",     "All commands"),
                ],
                scope=BotCommandScopeChat(chat_id=int(admin_id))
            )
        except Exception:
            pass


def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN environment variable not set")

    init_db()

    app = Application.builder().token(token).post_init(post_init).build()

    app.add_handler(CommandHandler("start",       cmd_start))
    app.add_handler(CommandHandler("help",        cmd_help))
    app.add_handler(CommandHandler("tasks",       cmd_tasks))
    app.add_handler(CommandHandler("balance",     cmd_balance))
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    app.add_handler(CommandHandler("stats",       cmd_stats))
    app.add_handler(CommandHandler("addmanager",  cmd_addmanager))
    app.add_handler(CommandHandler("setup",       cmd_setup))
    app.add_handler(CommandHandler("settimezone", cmd_settimezone))
    app.add_handler(CommandHandler("locations",   cmd_locations))
    app.add_handler(CommandHandler("addlocation", cmd_addlocation))
    app.add_handler(CommandHandler("mystats",     cmd_mystats))

    app.add_handler(CallbackQueryHandler(handle_approve_callback,         pattern=r'^approve_\d+$'))
    app.add_handler(CallbackQueryHandler(handle_custom_approve_callback,  pattern=r'^custom_\d+_\d+$'))
    app.add_handler(CallbackQueryHandler(handle_reject_callback,          pattern=r'^reject_\d+$'))
    app.add_handler(CallbackQueryHandler(handle_leaderboard_callback,     pattern=r'^lb_'))
    app.add_handler(CallbackQueryHandler(handle_adminstats_back_callback, pattern=r'^adminstats_back$'))
    app.add_handler(CallbackQueryHandler(handle_adminstats_callback,      pattern=r'^adminstats_\d+$'))

    app.add_handler(MessageHandler(
        filters.PHOTO & filters.ChatType.GROUPS,
        handle_task_photo,
    ))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_member))

    app.add_error_handler(error_handler)

    logger.info("Bot started...")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
