from datetime import date
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from db import get_db


def is_super_admin(telegram_id, db):
    return db.execute(
        "SELECT * FROM admins WHERE telegram_id = ?", (telegram_id,)
    ).fetchone() is not None


def _first_name(full_name, username=''):
    s = (full_name or '').strip()
    if s:
        return s.split()[0]
    return username or 'Unknown'


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
        await update.message.reply_text(f"Already set up as: {existing['name']}")
        return

    db.execute("INSERT INTO locations (chat_id, name) VALUES (?, ?)", (chat.id, name))
    db.commit()

    await update.message.reply_text(
        f"Location registered: {name}\n\n"
        f"Next: /addmanager @username\n"
        f"Set timezone: /settimezone Europe/Kiev"
    )


async def cmd_settimezone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = get_db()

    if chat.type not in ('group', 'supergroup'):
        await update.message.reply_text("Use this command in the group chat.")
        return

    if not is_super_admin(user.id, db):
        await update.message.reply_text("Super-admin only.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: /settimezone Europe/Kiev\n"
            "Examples: UTC, Europe/London, Asia/Dubai, America/New_York"
        )
        return

    tz_name = context.args[0]
    try:
        ZoneInfo(tz_name)
    except Exception:
        await update.message.reply_text(
            f"Invalid timezone: {tz_name}\n"
            "Examples: UTC, Europe/London, Asia/Dubai, America/New_York"
        )
        return

    location = db.execute("SELECT * FROM locations WHERE chat_id = ?", (chat.id,)).fetchone()
    if not location:
        await update.message.reply_text("Location not set up yet. Run /setup first.")
        return

    db.execute("UPDATE locations SET timezone = ? WHERE chat_id = ?", (tz_name, chat.id))
    db.commit()
    await update.message.reply_text(f"✅ Timezone set to {tz_name} for {location['name']}.")


async def cmd_locations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = get_db()

    if not is_super_admin(user.id, db):
        await update.message.reply_text("Super-admin only.")
        return

    locations = db.execute(
        "SELECT l.*, COUNT(u.id) as staff_count FROM locations l "
        "LEFT JOIN users u ON u.location_id = l.id AND u.role = 'barista' "
        "GROUP BY l.id ORDER BY l.name"
    ).fetchall()

    if not locations:
        await update.message.reply_text("No locations registered yet.")
        return

    lines = [f"All locations ({len(locations)} total)\n"]
    for loc in locations:
        tz = loc['timezone'] or 'UTC'
        lines.append(f"• {loc['name']} — {loc['staff_count']} baristas · {tz}")

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
    user = query.from_user
    db = get_db()

    if not is_super_admin(user.id, db):
        await query.answer("Super-admin only.", show_alert=True)
        return

    await query.answer()

    location_id = int(query.data.split('_')[1])
    location = db.execute("SELECT * FROM locations WHERE id = ?", (location_id,)).fetchone()
    if not location:
        return

    today = date.today().strftime('%d/%m/%Y')

    today_stats = db.execute(
        "SELECT status, COUNT(*) as cnt FROM task_submissions "
        "WHERE location_id = ? AND date(submitted_at) = date('now') GROUP BY status",
        (location_id,)
    ).fetchall()

    pending = db.execute(
        "SELECT COUNT(*) as cnt FROM task_submissions WHERE location_id = ? AND status = 'pending'",
        (location_id,)
    ).fetchone()['cnt']

    top = db.execute("""
        SELECT u.full_name, u.username, u.tokens, COUNT(s.id) as tasks_done
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

    status_map = {'approved': '✅', 'pending': '⏳', 'rejected': '❌'}
    lines = [
        f"📊 {location['name']}",
        f"Staff: {staff_count} baristas",
        f"Today {today}",
        "",
    ]

    for row in today_stats:
        icon = status_map.get(row['status'], '•')
        lines.append(f"{icon} {row['status'].capitalize()}: {row['cnt']}")

    if not today_stats:
        lines.append("No submissions today.")

    if pending > 0:
        lines.append(f"\n⚠️ {pending} pending approval")

    lines.append("\nTop this week")
    medals = ['🥇', '🥈', '🥉']
    for i, b in enumerate(top):
        medal = medals[i] if i < 3 else f"{i+1}."
        name = _first_name(b['full_name'], b['username'])
        lines.append(f"{medal} {name} — {b['tasks_done']} tasks · {b['tokens']} pts")

    if not top:
        lines.append("No activity yet.")

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("◀️ All locations", callback_data="adminstats_back")
    ]])

    await query.edit_message_text('\n'.join(lines), reply_markup=keyboard)


async def handle_adminstats_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    db = get_db()

    if not is_super_admin(user.id, db):
        await query.answer("Super-admin only.", show_alert=True)
        return

    await query.answer()

    locations = db.execute("SELECT * FROM locations ORDER BY name").fetchall()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📍 {loc['name']}", callback_data=f"adminstats_{loc['id']}")]
        for loc in locations
    ])

    await query.edit_message_text(
        "Select a location to view stats:",
        reply_markup=keyboard
    )
