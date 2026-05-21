from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from db import get_db


def is_super_admin(telegram_id, db):
    return db.execute(
        "SELECT * FROM admins WHERE telegram_id = ?", (telegram_id,)
    ).fetchone() is not None


async def cmd_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            f"ℹ️ This group is already set up as *{existing['name']}*.",
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
        f"📍 *{name}*\n\n"
        f"Next steps:\n"
        f"1. Add a manager: `/addmanager @username`\n"
        f"2. Baristas can start using /tasks",
        parse_mode='Markdown'
    )


async def cmd_locations(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')


async def cmd_addlocation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = get_db()

    if not is_super_admin(user.id, db):
        await update.message.reply_text("⛔ Super-admin only.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: `/addlocation <chat_id> <Location Name>`",
            parse_mode='Markdown'
        )
        return

    try:
        chat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid chat_id.")
        return

    name = ' '.join(context.args[1:])
    db.execute("INSERT OR IGNORE INTO locations (chat_id, name) VALUES (?, ?)", (chat_id, name))
    db.commit()
    await update.message.reply_text(f"✅ Location *{name}* added.", parse_mode='Markdown')


async def cmd_mystats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Super-admin: see all locations with inline buttons to drill into each."""
    user = update.effective_user
    db = get_db()

    if not is_super_admin(user.id, db):
        await update.message.reply_text("⛔ Super-admin only.")
        return

    locations = db.execute(
        "SELECT * FROM locations ORDER BY name"
    ).fetchall()

    if not locations:
        await update.message.reply_text("No locations registered yet.")
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📍 {loc['name']}", callback_data=f"adminstats_{loc['id']}")]
        for loc in locations
    ])

    await update.message.reply_text(
        "📊 *Select a location to view stats:*",
        parse_mode='Markdown',
        reply_markup=keyboard
    )


async def handle_adminstats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    location_id = int(query.data.split('_')[1])
    user = query.from_user
    db = get_db()

    if not is_super_admin(user.id, db):
        await query.answer("⛔ Super-admin only.", show_alert=True)
        return

    location = db.execute(
        "SELECT * FROM locations WHERE id = ?", (location_id,)
    ).fetchone()
    if not location:
        return

    from datetime import date
    today = date.today().isoformat()

    # Today's submissions
    today_stats = db.execute("""
        SELECT status, COUNT(*) as cnt FROM task_submissions
        WHERE location_id = ? AND date(submitted_at) = ?
        GROUP BY status
    """, (location_id, today)).fetchall()

    # Pending count
    pending = db.execute("""
        SELECT COUNT(*) as cnt FROM task_submissions
        WHERE location_id = ? AND status = 'pending'
    """, (location_id,)).fetchone()['cnt']

    # Top baristas this week
    top = db.execute("""
        SELECT u.full_name, u.tokens,
               COUNT(s.id) as tasks_done
        FROM users u
        LEFT JOIN task_submissions s ON s.user_id = u.id AND s.status = 'approved'
            AND date(s.submitted_at) >= date('now', '-7 days')
        WHERE u.location_id = ? AND u.role = 'barista'
        GROUP BY u.id
        ORDER BY tasks_done DESC, u.tokens DESC
        LIMIT 5
    """, (location_id,)).fetchall()

    # Total staff
    staff_count = db.execute(
        "SELECT COUNT(*) as c FROM users WHERE location_id = ? AND role = 'barista'",
        (location_id,)
    ).fetchone()['c']

    status_map = {'approved': '✅', 'pending': '⏳', 'rejected': '❌'}

    lines = [
        f"📊 *{location['name']}*",
        f"👥 Staff: {staff_count}",
        "",
        f"📅 *Today ({today})*",
    ]

    for row in today_stats:
        icon = status_map.get(row['status'], '•')
        lines.append(f"{icon} {row['status'].capitalize()}: {row['cnt']}")

    if not today_stats:
        lines.append("No submissions today yet.")

    if pending > 0:
        lines.append(f"\n⚠️ *{pending} pending approval*")

    lines.append("\n🏆 *Top this week*")
    medals = ['🥇', '🥈', '🥉']
    for i, b in enumerate(top):
        medal = medals[i] if i < 3 else f"{i+1}."
        name = b['full_name'].split()[0]
        lines.append(f"{medal} {name} — {b['tasks_done']} tasks · {b['tokens']}🪙")

    if not top:
        lines.append("No activity yet.")

    # Back button to location list
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("◀️ All locations", callback_data="adminstats_back")
    ]])

    await query.edit_message_text('\n'.join(lines), parse_mode='Markdown', reply_markup=keyboard)


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
        "📊 *Select a location to view stats:*",
        parse_mode='Markdown',
        reply_markup=keyboard
    )
