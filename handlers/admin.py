from telegram import Update
from telegram.ext import ContextTypes

from db import get_db


def is_super_admin(telegram_id, db):
    return db.execute(
        "SELECT * FROM admins WHERE telegram_id = ?", (telegram_id,)
    ).fetchone() is not None


async def cmd_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Register current group as a coffee shop location."""
    chat = update.effective_chat
    user = update.effective_user
    db = get_db()

    if chat.type not in ('group', 'supergroup'):
        await update.message.reply_text("⚠️ This command only works in group chats.")
        return

    if not is_super_admin(user.id, db):
        await update.message.reply_text(
            "⛔ Only the super-admin can set up locations.\n"
            "Contact the system administrator."
        )
        return

    if not context.args:
        await update.message.reply_text(
            "Please provide a location name.\n"
            "Usage: `/setup The Miners — Letna`",
            parse_mode='Markdown'
        )
        return

    name = ' '.join(context.args)

    existing = db.execute(
        "SELECT * FROM locations WHERE chat_id = ?", (chat.id,)
    ).fetchone()

    if existing:
        await update.message.reply_text(
            f"ℹ️ This group is already set up as *{existing['name']}*.\n"
            f"To rename: update the database directly.",
            parse_mode='Markdown'
        )
        return

    db.execute(
        "INSERT INTO locations (chat_id, name) VALUES (?, ?)",
        (chat.id, name)
    )
    db.commit()

    await update.message.reply_text(
        f"✅ Location registered!\n\n"
        f"📍 *{name}*\n"
        f"Chat ID: `{chat.id}`\n\n"
        f"Next steps:\n"
        f"1. Add a manager with `/addmanager @username`\n"
        f"2. Baristas can start using /tasks\n\n"
        f"The bot is ready to use!",
        parse_mode='Markdown'
    )


async def cmd_locations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all registered locations — super-admin only."""
    user = update.effective_user
    db = get_db()

    if not is_super_admin(user.id, db):
        await update.message.reply_text("⛔ Super-admin only.")
        return

    locations = db.execute(
        "SELECT l.*, COUNT(u.id) as staff_count FROM locations l "
        "LEFT JOIN users u ON u.location_id = l.id "
        "GROUP BY l.id ORDER BY l.name"
    ).fetchall()

    if not locations:
        await update.message.reply_text("No locations registered yet.")
        return

    lines = [f"📍 *All locations ({len(locations)} total)*\n"]
    for loc in locations:
        lines.append(f"• *{loc['name']}* — {loc['staff_count']} staff")
        lines.append(f"  Chat ID: `{loc['chat_id']}`")

    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')


async def cmd_addlocation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alias for setup — add a location by chat_id from DM."""
    user = update.effective_user
    db = get_db()

    if not is_super_admin(user.id, db):
        await update.message.reply_text("⛔ Super-admin only.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: `/addlocation <chat_id> <Location Name>`\n"
            "Example: `/addlocation -100123456789 The Miners — Vinohrady`",
            parse_mode='Markdown'
        )
        return

    try:
        chat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid chat_id. Must be a number.")
        return

    name = ' '.join(context.args[1:])

    db.execute(
        "INSERT OR IGNORE INTO locations (chat_id, name) VALUES (?, ?)",
        (chat_id, name)
    )
    db.commit()

    await update.message.reply_text(f"✅ Location *{name}* added.", parse_mode='Markdown')
