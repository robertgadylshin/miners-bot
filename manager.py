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
    admin = db.execute(
        "SELECT * FROM admins WHERE telegram_id = ?", (telegram_id,)
    ).fetchone()
    return admin is not None


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
            f"ℹ️ Already processed: {submission['status']}"
        )
        return

    location_id = submission['location_id']
    if not is_manager(reviewer_id, location_id, db):
        await query.answer("⛔ Only managers can approve tasks.", show_alert=True)
        return

    # Approve and award tokens
    db.execute("""
        UPDATE task_submissions
        SET status = 'approved', reviewed_at = ?, reviewed_by = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), reviewer_id, submission_id))

    db.execute("""
        UPDATE users
        SET tokens = tokens + ?, total_earned = total_earned + ?
        WHERE id = ?
    """, (submission['tokens_awarded'], submission['tokens_awarded'], submission['user_id']))

    db.commit()

    # Get barista info
    barista = db.execute(
        "SELECT * FROM users WHERE id = ?", (submission['user_id'],)
    ).fetchone()
    new_balance = db.execute(
        "SELECT tokens FROM users WHERE id = ?", (submission['user_id'],)
    ).fetchone()['tokens']

    await query.edit_message_caption(
        f"✅ *Approved!*\n\n"
        f"👤 {barista['full_name']}\n"
        f"Task: {submission['task_name']}\n"
        f"Awarded: +{submission['tokens_awarded']}🪙\n"
        f"New balance: {new_balance}🪙\n"
        f"Approved by: @{query.from_user.username or query.from_user.full_name}",
        parse_mode='Markdown'
    )

    # Notify the barista
    location = db.execute(
        "SELECT name FROM locations WHERE id = ?", (location_id,)
    ).fetchone()
    try:
        await context.bot.send_message(
            chat_id=barista['telegram_id'],
            text=(
                f"🎉 *Task approved!*\n\n"
                f"✅ {submission['task_name']}\n"
                f"+{submission['tokens_awarded']} 🪙 added to your balance!\n"
                f"Total balance: *{new_balance}🪙*\n\n"
                f"Keep it up! Use /balance to track your progress."
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
        await query.edit_message_caption(f"ℹ️ Already processed: {submission['status']}")
        return

    location_id = submission['location_id']
    if not is_manager(reviewer_id, location_id, db):
        await query.answer("⛔ Only managers can reject tasks.", show_alert=True)
        return

    db.execute("""
        UPDATE task_submissions
        SET status = 'rejected', reviewed_at = ?, reviewed_by = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), reviewer_id, submission_id))
    db.commit()

    barista = db.execute(
        "SELECT * FROM users WHERE id = ?", (submission['user_id'],)
    ).fetchone()

    await query.edit_message_caption(
        f"❌ *Rejected*\n\n"
        f"👤 {barista['full_name']}\n"
        f"Task: {submission['task_name']}\n"
        f"Rejected by: @{query.from_user.username or query.from_user.full_name}",
        parse_mode='Markdown'
    )

    try:
        await context.bot.send_message(
            chat_id=barista['telegram_id'],
            text=(
                f"❌ *Task submission rejected*\n\n"
                f"Task: {submission['task_name']}\n\n"
                f"Please check the photo quality and redo the task.\n"
                f"Contact your manager if you have questions."
            ),
            parse_mode='Markdown'
        )
    except Exception:
        pass


async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "To approve tasks, use the buttons sent to you when a barista submits a photo.\n"
        "Make sure you're set as a manager for this location."
    )


async def cmd_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "To reject tasks, use the buttons sent to you when a barista submits a photo."
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show location stats — managers only."""
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

    # Today's submissions
    today_stats = db.execute("""
        SELECT status, COUNT(*) as cnt FROM task_submissions
        WHERE location_id = ? AND date(submitted_at) = ?
        GROUP BY status
    """, (location['id'], today)).fetchall()

    # Top baristas this week
    top = db.execute("""
        SELECT u.full_name, u.tokens, u.total_earned,
               COUNT(s.id) as tasks_done
        FROM users u
        LEFT JOIN task_submissions s ON s.user_id = u.id AND s.status = 'approved'
            AND date(s.submitted_at) >= date('now', '-7 days')
        WHERE u.location_id = ? AND u.role = 'barista'
        GROUP BY u.id
        ORDER BY tasks_done DESC, u.tokens DESC
        LIMIT 5
    """, (location['id'],)).fetchall()

    # Pending count
    pending = db.execute("""
        SELECT COUNT(*) as cnt FROM task_submissions
        WHERE location_id = ? AND status = 'pending'
    """, (location['id'],)).fetchone()['cnt']

    lines = [f"📊 *Stats — {location['name']}*\n"]
    lines.append(f"📅 *Today ({today})*")

    status_map = {'approved': '✅ Approved', 'pending': '⏳ Pending', 'rejected': '❌ Rejected'}
    for row in today_stats:
        lines.append(f"  {status_map.get(row['status'], row['status'])}: {row['cnt']}")

    if pending > 0:
        lines.append(f"\n⚠️ *{pending} submissions waiting for your approval!*")

    lines.append(f"\n🏆 *Top baristas this week*")
    for i, b in enumerate(top, 1):
        lines.append(f"  {i}. {b['full_name']} — {b['tasks_done']} tasks, {b['tokens']}🪙")

    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')


async def cmd_addmanager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Promote a user to manager role."""
    chat = update.effective_chat
    user = update.effective_user
    db = get_db()

    is_admin = db.execute(
        "SELECT * FROM admins WHERE telegram_id = ?", (user.id,)
    ).fetchone()
    if not is_admin:
        await update.message.reply_text("⛔ Only super-admins can add managers.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: `/addmanager @username`\n"
            "The user must have sent at least one message in this group.",
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

    updated = db.execute("""
        UPDATE users SET role = 'manager'
        WHERE username = ? AND location_id = ?
    """, (username, location['id']))
    db.commit()

    if updated.rowcount:
        await update.message.reply_text(f"✅ @{username} is now a manager for {location['name']}.")
    else:
        await update.message.reply_text(
            f"❌ User @{username} not found in this location.\n"
            "They need to send /start in this group first."
        )
