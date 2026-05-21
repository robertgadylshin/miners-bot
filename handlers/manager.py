from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime, date

from db import get_db


def is_manager(telegram_id, location_id, db):
    user = db.execute(
        "SELECT role FROM users WHERE telegram_id = ? AND location_id = ?",
        (telegram_id, location_id)
    ).fetchone()
    if user and user['role'] in ('manager', 'admin'):
        return True
    return db.execute(
        "SELECT * FROM admins WHERE telegram_id = ?", (telegram_id,)
    ).fetchone() is not None


async def cmd_addmanager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = get_db()

    is_admin = db.execute(
        "SELECT * FROM admins WHERE telegram_id = ?", (user.id,)
    ).fetchone()
    if not is_admin:
        await update.message.reply_text("⛔ Only super-admins can use this command.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: `/addmanager @username`",
            parse_mode='Markdown'
        )
        return

    username = context.args[0].lstrip('@')
    location = db.execute(
        "SELECT * FROM locations WHERE chat_id = ?", (chat.id,)
    ).fetchone()
    if not location:
        await update.message.reply_text("⚠️ Location not set up.")
        return

    # Insert stub if user never wrote /start, then promote
    db.execute(
        "INSERT OR IGNORE INTO users (telegram_id, username, full_name, location_id, role) "
        "VALUES (0, ?, ?, ?, 'barista')",
        (username, username, location['id'])
    )
    db.execute(
        "UPDATE users SET role = 'manager' WHERE username = ? AND location_id = ?",
        (username, location['id'])
    )
    db.commit()

    location_name = location['name']
    await update.message.reply_text(
        f"✅ @{username} is now a manager for *{location_name}*.\n\n"
        "⚠️ Ask them to write /start to the bot in DMs so they receive photo notifications.",
        parse_mode='Markdown'
    )


async def handle_approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    submission_id = int(query.data.split('_')[1])
    reviewer_id = query.from_user.id
    db = get_db()

    submission = db.execute(
        "SELECT * FROM task_submissions WHERE id = ?", (submission_id,)
    ).fetchone()
    if not submission:
        await query.edit_message_caption("❌ Submission not found.")
        return

    if submission['status'] != 'pending':
        await query.edit_message_caption(
            "ℹ️ Already processed: " + submission['status']
        )
        return

    if not is_manager(reviewer_id, submission['location_id'], db):
        await query.answer("⛔ Only managers can approve tasks.", show_alert=True)
        return

    db.execute(
        "UPDATE task_submissions SET status = 'approved', reviewed_at = ?, reviewed_by = ? WHERE id = ?",
        (datetime.now().isoformat(), reviewer_id, submission_id)
    )
    db.execute(
        "UPDATE users SET tokens = tokens + ?, total_earned = total_earned + ? WHERE id = ?",
        (submission['tokens_awarded'], submission['tokens_awarded'], submission['user_id'])
    )
    db.commit()

    barista = db.execute("SELECT * FROM users WHERE id = ?", (submission['user_id'],)).fetchone()
    new_balance = db.execute(
        "SELECT tokens FROM users WHERE id = ?", (submission['user_id'],)
    ).fetchone()['tokens']

    task_key = submission['task_key']
    task_name = submission['task_name']
    tokens = submission['tokens_awarded']
    reviewer_name = query.from_user.username or query.from_user.full_name

    await query.edit_message_caption(
        f"✅ *Approved!*\n\n"
        f"👤 {barista['full_name']}\n"
        f"Task: *{task_key}* — {task_name}\n"
        f"Awarded: +{tokens}🪙\n"
        f"Balance: {new_balance}🪙\n"
        f"By: @{reviewer_name}",
        parse_mode='Markdown'
    )

    try:
        await context.bot.send_message(
            chat_id=barista['telegram_id'],
            text=(
                f"🎉 *Task approved!*\n\n"
                f"✅ *{task_key}* — {task_name}\n"
                f"+{tokens} 🪙\n"
                f"Total balance: *{new_balance}🪙*"
            ),
            parse_mode='Markdown'
        )
    except Exception:
        pass


async def handle_reject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    submission_id = int(query.data.split('_')[1])
    reviewer_id = query.from_user.id
    db = get_db()

    submission = db.execute(
        "SELECT * FROM task_submissions WHERE id = ?", (submission_id,)
    ).fetchone()
    if not submission:
        await query.edit_message_caption("❌ Submission not found.")
        return

    if submission['status'] != 'pending':
        await query.edit_message_caption(
            "ℹ️ Already processed: " + submission['status']
        )
        return

    if not is_manager(reviewer_id, submission['location_id'], db):
        await query.answer("⛔ Only managers can reject tasks.", show_alert=True)
        return

    db.execute(
        "UPDATE task_submissions SET status = 'rejected', reviewed_at = ?, reviewed_by = ? WHERE id = ?",
        (datetime.now().isoformat(), reviewer_id, submission_id)
    )
    db.commit()

    barista = db.execute("SELECT * FROM users WHERE id = ?", (submission['user_id'],)).fetchone()
    task_key = submission['task_key']
    task_name = submission['task_name']

    await query.edit_message_caption(
        f"❌ *Rejected*\n\n"
        f"👤 {barista['full_name']}\n"
        f"Task: *{task_key}* — {task_name}",
        parse_mode='Markdown'
    )

    try:
        await context.bot.send_message(
            chat_id=barista['telegram_id'],
            text=(
                f"❌ *Task rejected*\n\n"
                f"*{task_key}* — {task_name}\n\n"
                f"Please redo the task and resubmit."
            ),
            parse_mode='Markdown'
        )
    except Exception:
        pass


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = get_db()

    location = db.execute(
        "SELECT * FROM locations WHERE chat_id = ?", (chat.id,)
    ).fetchone()
    if not location:
        await update.message.reply_text("⚠️ This group is not set up.")
        return

    if not is_manager(user.id, location['id'], db):
        await update.message.reply_text("⛔ Only managers can view stats.")
        return

    today = date.today().isoformat()

    today_stats = db.execute(
        "SELECT status, COUNT(*) as cnt FROM task_submissions "
        "WHERE location_id = ? AND date(submitted_at) = ? GROUP BY status",
        (location['id'], today)
    ).fetchall()

    pending = db.execute(
        "SELECT COUNT(*) as cnt FROM task_submissions WHERE location_id = ? AND status = 'pending'",
        (location['id'],)
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
    """, (location['id'],)).fetchall()

    status_map = {'approved': '✅', 'pending': '⏳', 'rejected': '❌'}
    location_name = location['name']
    lines = [f"📊 *Stats — {location_name}*\n📅 Today\n"]

    for row in today_stats:
        icon = status_map.get(row['status'], '•')
        lines.append(icon + " " + row['status'].capitalize() + ": " + str(row['cnt']))

    if pending > 0:
        lines.append(f"\n⚠️ *{pending} pending approval*")

    lines.append("\n🏆 *Top this week*")
    medals = ['🥇', '🥈', '🥉']
    for i, b in enumerate(top):
        medal = medals[i] if i < 3 else str(i + 1) + "."
        name = b['full_name'].split()[0]
        lines.append(medal + " " + name + " — " + str(b['tasks_done']) + " tasks · " + str(b['tokens']) + "🪙")

    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')
