import logging
from datetime import datetime, date

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from db import get_db

logger = logging.getLogger(__name__)


def is_manager(telegram_id, location_id, db):
    user = db.execute(
        "SELECT role FROM users WHERE telegram_id = ? AND location_id = ?",
        (telegram_id, location_id)
    ).fetchone()
    if user and user['role'] == 'manager':
        return True
    return db.execute(
        "SELECT * FROM admins WHERE telegram_id = ?", (telegram_id,)
    ).fetchone() is not None


def _reviewer_label(tg_user):
    if tg_user.username:
        return f"@{tg_user.username}"
    return tg_user.full_name or 'manager'


async def cmd_addmanager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db = get_db()

    if chat.type not in ('group', 'supergroup'):
        await update.message.reply_text("Use this command in the group chat.")
        return

    is_admin = db.execute(
        "SELECT * FROM admins WHERE telegram_id = ?", (user.id,)
    ).fetchone()
    if not is_admin:
        await update.message.reply_text("Only super-admins can use this command.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /addmanager @username")
        return

    username = context.args[0].lstrip('@').lower()
    location = db.execute(
        "SELECT * FROM locations WHERE chat_id = ?", (chat.id,)
    ).fetchone()
    if not location:
        await update.message.reply_text("Location not set up.")
        return

    existing = db.execute(
        "SELECT * FROM users WHERE LOWER(username) = ? AND location_id = ?",
        (username, location['id'])
    ).fetchone()

    if existing:
        db.execute(
            "UPDATE users SET role = 'manager' WHERE LOWER(username) = ? AND location_id = ?",
            (username, location['id'])
        )
    else:
        import hashlib
        placeholder_id = -(int(hashlib.sha256(
            f"{username}_{location['id']}".encode()
        ).hexdigest()[:14], 16) % (2 ** 31))
        db.execute(
            "INSERT INTO users (telegram_id, username, full_name, location_id, role) "
            "VALUES (?, ?, ?, ?, 'manager')",
            (placeholder_id, username, username, location['id'])
        )
    db.commit()

    await update.message.reply_text(
        f"@{username} is now a manager for {location['name']}.\n\n"
        "Ask them to write /start to the bot in DMs so they receive photo notifications."
    )


async def handle_approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    submission_id = int(query.data.split('_')[1])
    reviewer_id = query.from_user.id
    db = get_db()

    submission = db.execute(
        "SELECT * FROM task_submissions WHERE id = ?", (submission_id,)
    ).fetchone()
    if not submission:
        await query.answer("Submission not found.", show_alert=True)
        return

    if not is_manager(reviewer_id, submission['location_id'], db):
        await query.answer("Only managers can approve tasks.", show_alert=True)
        return

    barista = db.execute("SELECT * FROM users WHERE id = ?", (submission['user_id'],)).fetchone()

    if barista and barista['telegram_id'] == reviewer_id:
        await query.answer("You cannot approve your own submission.", show_alert=True)
        return

    await query.answer()

    cursor = db.execute(
        "UPDATE task_submissions SET status = 'approved', reviewed_at = ?, reviewed_by = ? "
        "WHERE id = ? AND status = 'pending'",
        (datetime.now().isoformat(), reviewer_id, submission_id)
    )
    if cursor.rowcount == 0:
        try:
            await query.edit_message_text("Already processed.")
        except Exception:
            pass
        return

    db.execute(
        "UPDATE users SET tokens = tokens + ?, total_earned = total_earned + ? WHERE id = ?",
        (submission['tokens_awarded'], submission['tokens_awarded'], submission['user_id'])
    )
    db.commit()

    new_balance = db.execute(
        "SELECT tokens FROM users WHERE id = ?", (submission['user_id'],)
    ).fetchone()['tokens']

    task_key = submission['task_key']
    task_name = submission['task_name']
    points = submission['tokens_awarded']
    reviewer = _reviewer_label(query.from_user)

    try:
        await query.edit_message_text(
            f"✅ Approved!\n\n"
            f"{barista['full_name']}\n"
            f"{task_key} — {task_name}\n"
            f"+{points} points\n"
            f"Balance: {new_balance} points\n"
            f"By: {reviewer}"
        )
    except Exception:
        pass

    try:
        await context.bot.send_message(
            chat_id=barista['telegram_id'],
            text=(
                f"🎉 Task approved!\n\n"
                f"✅ {task_key} — {task_name}\n"
                f"+{points} points\n"
                f"Total balance: {new_balance} points"
            )
        )
    except Exception:
        pass

    if submission['group_chat_id'] and submission['group_message_id']:
        try:
            await context.bot.edit_message_text(
                chat_id=submission['group_chat_id'],
                message_id=submission['group_message_id'],
                text=(
                    f"✅ Approved!\n\n"
                    f"{task_key} — {task_name}\n"
                    f"+{points} points\n"
                    f"By: {reviewer}"
                )
            )
        except Exception:
            pass


async def handle_custom_approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split('_')   # custom_200_42
    points = int(parts[1])
    submission_id = int(parts[2])
    reviewer_id = query.from_user.id
    db = get_db()

    submission = db.execute(
        "SELECT * FROM task_submissions WHERE id = ?", (submission_id,)
    ).fetchone()
    if not submission:
        await query.answer("Submission not found.", show_alert=True)
        return

    if not is_manager(reviewer_id, submission['location_id'], db):
        await query.answer("Only managers can approve tasks.", show_alert=True)
        return

    barista = db.execute("SELECT * FROM users WHERE id = ?", (submission['user_id'],)).fetchone()

    if barista and barista['telegram_id'] == reviewer_id:
        await query.answer("You cannot approve your own submission.", show_alert=True)
        return

    await query.answer()

    cursor = db.execute(
        "UPDATE task_submissions SET status = 'approved', tokens_awarded = ?, "
        "reviewed_at = ?, reviewed_by = ? WHERE id = ? AND status = 'pending'",
        (points, datetime.now().isoformat(), reviewer_id, submission_id)
    )
    if cursor.rowcount == 0:
        try:
            await query.edit_message_text("Already processed.")
        except Exception:
            pass
        return

    db.execute(
        "UPDATE users SET tokens = tokens + ?, total_earned = total_earned + ? WHERE id = ?",
        (points, points, submission['user_id'])
    )
    db.commit()

    new_balance = db.execute(
        "SELECT tokens FROM users WHERE id = ?", (submission['user_id'],)
    ).fetchone()['tokens']

    reviewer = _reviewer_label(query.from_user)
    description = submission['custom_description'] or submission['task_name']

    try:
        await query.edit_message_text(
            f"✅ Custom task approved!\n\n"
            f"{barista['full_name']}\n"
            f"{description}\n"
            f"+{points} points\n"
            f"Balance: {new_balance} points\n"
            f"By: {reviewer}"
        )
    except Exception:
        pass

    try:
        await context.bot.send_message(
            chat_id=barista['telegram_id'],
            text=(
                f"🎉 Custom task approved!\n\n"
                f"📝 {description}\n"
                f"+{points} points\n"
                f"Total balance: {new_balance} points"
            )
        )
    except Exception:
        pass

    if submission['group_chat_id'] and submission['group_message_id']:
        try:
            await context.bot.edit_message_text(
                chat_id=submission['group_chat_id'],
                message_id=submission['group_message_id'],
                text=(
                    f"✅ Custom task approved!\n\n"
                    f"{description}\n"
                    f"+{points} points\n"
                    f"By: {reviewer}"
                )
            )
        except Exception:
            pass


async def handle_reject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    submission_id = int(query.data.split('_')[1])
    reviewer_id = query.from_user.id
    db = get_db()

    submission = db.execute(
        "SELECT * FROM task_submissions WHERE id = ?", (submission_id,)
    ).fetchone()
    if not submission:
        await query.answer("Submission not found.", show_alert=True)
        return

    if not is_manager(reviewer_id, submission['location_id'], db):
        await query.answer("Only managers can reject tasks.", show_alert=True)
        return

    barista = db.execute("SELECT * FROM users WHERE id = ?", (submission['user_id'],)).fetchone()

    if barista and barista['telegram_id'] == reviewer_id:
        await query.answer("You cannot reject your own submission.", show_alert=True)
        return

    await query.answer()

    cursor = db.execute(
        "UPDATE task_submissions SET status = 'rejected', reviewed_at = ?, reviewed_by = ? "
        "WHERE id = ? AND status = 'pending'",
        (datetime.now().isoformat(), reviewer_id, submission_id)
    )
    if cursor.rowcount == 0:
        try:
            await query.edit_message_text("Already processed.")
        except Exception:
            pass
        return

    db.commit()

    reviewer = _reviewer_label(query.from_user)
    task_key = submission['task_key']
    task_name = submission['custom_description'] or submission['task_name']

    try:
        await query.edit_message_text(
            f"❌ Rejected\n\n"
            f"{barista['full_name']}\n"
            f"{task_key} — {task_name}\n"
            f"By: {reviewer}"
        )
    except Exception:
        pass

    try:
        await context.bot.send_message(
            chat_id=barista['telegram_id'],
            text=(
                f"Task rejected\n\n"
                f"{task_key} — {task_name}\n\n"
                f"Please redo the task and resubmit."
            )
        )
    except Exception:
        pass

    if submission['group_chat_id'] and submission['group_message_id']:
        try:
            await context.bot.edit_message_text(
                chat_id=submission['group_chat_id'],
                message_id=submission['group_message_id'],
                text=(
                    f"❌ Rejected\n\n"
                    f"{task_key} — {task_name}\n\n"
                    f"Please redo and resubmit."
                )
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
        await update.message.reply_text("This group is not set up.")
        return

    if not is_manager(user.id, location['id'], db):
        await update.message.reply_text("Only managers can view stats.")
        return

    today = date.today().strftime('%d/%m/%Y')

    today_stats = db.execute(
        "SELECT status, COUNT(*) as cnt FROM task_submissions "
        "WHERE location_id = ? AND date(submitted_at) = date('now') GROUP BY status",
        (location['id'],)
    ).fetchall()

    pending = db.execute(
        "SELECT COUNT(*) as cnt FROM task_submissions WHERE location_id = ? AND status = 'pending'",
        (location['id'],)
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
    """, (location['id'],)).fetchall()

    status_map = {'approved': '✅', 'pending': '⏳', 'rejected': '❌'}
    lines = [f"Stats — {location['name']}", f"Today {today}", ""]

    for row in today_stats:
        icon = status_map.get(row['status'], '•')
        lines.append(f"{icon} {row['status'].capitalize()}: {row['cnt']}")

    if pending > 0:
        lines.append(f"\n⚠️ {pending} pending approval")

    lines.append("\nTop this week")
    medals = ['🥇', '🥈', '🥉']
    for i, b in enumerate(top):
        medal = medals[i] if i < 3 else f"{i+1}."
        name = _first_name(b['full_name'], b['username'])
        lines.append(f"{medal} {name} — {b['tasks_done']} tasks · {b['tokens']} pts")

    await update.message.reply_text('\n'.join(lines))


def _first_name(full_name, username=''):
    s = (full_name or '').strip()
    if s:
        return s.split()[0]
    return username or 'Unknown'
