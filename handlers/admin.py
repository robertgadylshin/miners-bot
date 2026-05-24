from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import date
import logging

from db import get_db

logger = logging.getLogger(__name__)


def is_super_admin(telegram_id, db):
    return db.execute(
        "SELECT * FROM admins WHERE telegram_id = ?", (telegram_id,)
    ).fetchone() is not None


async def cmd_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = get_db()

    if chat.type not in ('group', 'supergroup'):
        await update.message.reply_text("This command only works in group chats.")
        return

    if not is_super_admin(user.id, db):
        await update.message.reply_text("Only the super-admin can set up locations.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /setup Location Name")
        return

    name = ' '.join(context.args)
    existing = db.execute(
        "SELECT * FROM locations WHERE chat_id = ?", (chat.id,)
    ).fetchone()

    if existing:
        await update.message.reply_text(
            f"This group is already set up as {existing['name']}.\n"
            "To rename use /renamelocation <new name>"
        )
        return

    db.execute("INSERT INTO locations (chat_id, name) VALUES (?, ?)", (chat.id, name))
    db.commit()

    await update.message.reply_text(
        f"Location registered: {name}\n\n"
        "Next: /addmanager @username"
    )


async def cmd_locations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = get_db()

    if not is_super_admin(user.id, db):
        await update.message.reply_text("Super-admin only.")
        return

    locations = db.execute(
        "SELECT l.*, COUNT(u.id) as staff_count FROM locations l "
        "LEFT JOIN users u ON u.location_id = l.id "
        "GROUP BY l.id ORDER BY l.name"
    ).fetchall()

    if not locations:
        await update.message.reply_text("No locations registered yet.")
        return

    lines = [f"All locations ({len(locations)} total)\n"]
    for loc in locations:
        lines.append(f"• {loc['name']} — {loc['staff_count']} staff")
        lines.append(f"  ID: {loc['id']} | Chat: {loc['chat_id']}")

    await update.message.reply_text('\n'.join(lines))


async def cmd_addlocation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = get_db()

    if not is_super_admin(user.id, db):
        await update.message.reply_text("Super-admin only.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /addlocation <chat_id> <Location Name>")
        return

    try:
        chat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid chat_id.")
        return

    name = ' '.join(context.args[1:])
    db.execute("INSERT OR IGNORE INTO locations (chat_id, name) VALUES (?, ?)", (chat_id, name))
    db.commit()
    await update.message.reply_text(f"Location {name} added.")


async def cmd_renamelocation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rename current group's location. Use in group chat."""
    chat = update.effective_chat
    user = update.effective_user
    db = get_db()

    if not is_super_admin(user.id, db):
        await update.message.reply_text("Super-admin only.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /renamelocation New Name")
        return

    new_name = ' '.join(context.args)
    result = db.execute(
        "UPDATE locations SET name = ? WHERE chat_id = ?", (new_name, chat.id)
    )
    db.commit()

    if result.rowcount:
        await update.message.reply_text(f"Location renamed to: {new_name}")
    else:
        await update.message.reply_text("This group is not registered. Use /setup first.")


async def cmd_deletelocation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete current group's location and all its data."""
    chat = update.effective_chat
    user = update.effective_user
    db = get_db()

    if not is_super_admin(user.id, db):
        await update.message.reply_text("Super-admin only.")
        return

    location = db.execute(
        "SELECT * FROM locations WHERE chat_id = ?", (chat.id,)
    ).fetchone()

    if not location:
        await update.message.reply_text("This group is not registered.")
        return

    # Ask for confirmation
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            f"Yes, delete {location['name']}",
            callback_data=f"deleteloc_{location['id']}"
        ),
        InlineKeyboardButton("Cancel", callback_data="deleteloc_cancel"),
    ]])

    await update.message.reply_text(
        f"Are you sure you want to delete {location['name']}?\n\n"
        "This will remove all staff, submissions and data for this location.",
        reply_markup=keyboard
    )


async def handle_deletelocation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    db = get_db()

    if not is_super_admin(user.id, db):
        await query.answer("Super-admin only.", show_alert=True)
        return

    if query.data == "deleteloc_cancel":
        await query.edit_message_text("Cancelled.")
        return

    location_id = int(query.data.split('_')[1])
    location = db.execute("SELECT * FROM locations WHERE id = ?", (location_id,)).fetchone()
    if not location:
        await query.edit_message_text("Location not found.")
        return

    name = location['name']
    db.execute("DELETE FROM task_submissions WHERE location_id = ?", (location_id,))
    db.execute("DELETE FROM users WHERE location_id = ?", (location_id,))
    db.execute("DELETE FROM locations WHERE id = ?", (location_id,))
    db.commit()

    await query.edit_message_text(f"Location {name} deleted.")


async def cmd_changemanager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove old manager and set new one. Usage: /changemanager @newusername"""
    chat = update.effective_chat
    user = update.effective_user
    db = get_db()

    if not is_super_admin(user.id, db):
        await update.message.reply_text("Super-admin only.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /changemanager @newusername")
        return

    location = db.execute(
        "SELECT * FROM locations WHERE chat_id = ?", (chat.id,)
    ).fetchone()
    if not location:
        await update.message.reply_text("This group is not registered.")
        return

    new_username = context.args[0].lstrip('@')

    # Demote all current managers in this location to barista
    db.execute(
        "UPDATE users SET role = 'barista' WHERE location_id = ? AND role = 'manager'",
        (location['id'],)
    )

    # Insert or promote new manager
    db.execute(
        "INSERT OR IGNORE INTO users (telegram_id, username, full_name, location_id, role) "
        "VALUES (0, ?, ?, ?, 'barista')",
        (new_username, new_username, location['id'])
    )
    db.execute(
        "UPDATE users SET role = 'manager' WHERE username = ? AND location_id = ?",
        (new_username, location['id'])
    )
    db.commit()

    await update.message.reply_text(
        f"Manager updated for {location['name']}.\n"
        f"Previous managers demoted to barista.\n"
        f"New manager: @{new_username}\n\n"
        "Ask them to write /start to the bot in DMs."
    )


async def cmd_resetlocation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset all submissions for this location (keeps staff). Use in group."""
    chat = update.effective_chat
    user = update.effective_user
    db = get_db()

    if not is_super_admin(user.id, db):
        await update.message.reply_text("Super-admin only.")
        return

    location = db.execute(
        "SELECT * FROM locations WHERE chat_id = ?", (chat.id,)
    ).fetchone()
    if not location:
        await update.message.reply_text("This group is not registered.")
        return

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            f"Yes, reset {location['name']}",
            callback_data=f"resetloc_{location['id']}"
        ),
        InlineKeyboardButton("Cancel", callback_data="resetloc_cancel"),
    ]])

    await update.message.reply_text(
        f"Reset {location['name']}?\n\n"
        "This will clear all submissions and points but keep the staff list.",
        reply_markup=keyboard
    )


async def handle_resetlocation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    db = get_db()

    if not is_super_admin(user.id, db):
        await query.answer("Super-admin only.", show_alert=True)
        return

    if query.data == "resetloc_cancel":
        await query.edit_message_text("Cancelled.")
        return

    location_id = int(query.data.split('_')[1])
    location = db.execute("SELECT * FROM locations WHERE id = ?", (location_id,)).fetchone()
    if not location:
        await query.edit_message_text("Location not found.")
        return

    db.execute("DELETE FROM task_submissions WHERE location_id = ?", (location_id,))
    db.execute("UPDATE users SET tokens = 0, total_earned = 0 WHERE location_id = ?", (location_id,))
    db.commit()

    await query.edit_message_text(
        f"Location {location['name']} reset.\n"
        "All submissions and points cleared. Staff list kept."
    )


async def cmd_mystats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = get_db()

    if not is_super_admin(user.id, db):
        await update.message.reply_text("Super-admin only.")
        return

    locations = db.execute("SELECT * FROM locations ORDER BY name").fetchall()

    if not locations:
        await update.message.reply_text("No locations registered yet.")
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📍 {loc['name']}", callback_data=f"adminstats_{loc['id']}")]
        for loc in locations
    ])

    await update.message.reply_text(
        "Select a location to view stats:",
        reply_markup=keyboard
    )


async def handle_adminstats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    location_id = int(query.data.split('_')[1])
    user = query.from_user
    db = get_db()

    if not is_super_admin(user.id, db):
        await query.answer("Super-admin only.", show_alert=True)
        return

    location = db.execute("SELECT * FROM locations WHERE id = ?", (location_id,)).fetchone()
    if not location:
        return

    today = date.today().strftime('%d/%m/%Y')

    today_stats = db.execute("""
        SELECT status, COUNT(*) as cnt FROM task_submissions
        WHERE location_id = ? AND date(submitted_at) = date('now')
        GROUP BY status
    """, (location_id,)).fetchall()

    pending = db.execute(
        "SELECT COUNT(*) as cnt FROM task_submissions WHERE location_id = ? AND status = 'pending'",
        (location_id,)
    ).fetchone()['cnt']

    top = db.execute("""
        SELECT u.full_name, u.tokens, COUNT(s.id) as tasks_done
        FROM users u
        LEFT JOIN task_submissions s ON s.user_id = u.id AND s.status = 'approved'
            AND date(s.submitted_at) >= date('now', '-7 days')
        WHERE u.location_id = ? AND u.role = 'barista'
        GROUP BY u.id
        ORDER BY tasks_done DESC, u.tokens DESC
        LIMIT 5
    """, (location_id,)).fetchall()

    staff_count = db.execute(
        "SELECT COUNT(*) as c FROM users WHERE location_id = ? AND role = 'barista'",
        (location_id,)
    ).fetchone()['c']

    managers = db.execute(
        "SELECT username, full_name FROM users WHERE location_id = ? AND role = 'manager'",
        (location_id,)
    ).fetchall()

    status_map = {'approved': '✅', 'pending': '⏳', 'rejected': '❌'}

    lines = [
        f"{location['name']}",
        f"Staff: {staff_count}",
    ]

    if managers:
        mgr_names = ', '.join(f"@{m['username']}" if m['username'] else m['full_name'] for m in managers)
        lines.append(f"Manager: {mgr_names}")

    lines += ["", f"Today {today}"]

    for row in today_stats:
        icon = status_map.get(row['status'], '•')
        lines.append(f"{icon} {row['status'].capitalize()}: {row['cnt']}")

    if not today_stats:
        lines.append("No submissions today.")

    if pending > 0:
        lines.append(f"\n{pending} pending approval")

    lines.append("\nTop this week")
    medals = ['🥇', '🥈', '🥉']
    for i, b in enumerate(top):
        medal = medals[i] if i < 3 else f"{i+1}."
        name = b['full_name'].split()[0]
        lines.append(f"{medal} {name} — {b['tasks_done']} tasks · {b['tokens']} pts")

    if not top:
        lines.append("No activity yet.")

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("◀️ All locations", callback_data="adminstats_back")
    ]])

    await query.edit_message_text('\n'.join(lines), reply_markup=keyboard)


async def handle_adminstats_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    db = get_db()

    if not is_super_admin(user.id, db):
        return

    locations = db.execute("SELECT * FROM locations ORDER BY name").fetchall()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📍 {loc['name']}", callback_data=f"adminstats_{loc['id']}")]
        for loc in locations
    ])

    await query.edit_message_text(
        "Select a location to view stats:",
        reply_markup=keyboard
    )
