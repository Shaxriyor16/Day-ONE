"""
Daily Reminder Telegram Bot
- Python 3.10+
- Uses python-telegram-bot v20 (async) built-in JobQueue for scheduling

Features:
- /start - introduce the bot
- /add HH:MM reminder text - add a daily reminder at local time HH:MM
- /list - list active reminders for the chat
- /remove ID - remove a reminder by its ID
- /help - quick usage

Storage: SQLite (reminders.db)

Run:
1) pip install python-telegram-bot==20.3
2) Set TELEGRAM_TOKEN env var or paste token into TOKEN variable
3) python daily_reminder_bot.py

Note: This is a simple starting point. Timezone behavior uses system local time.
"""

import os
import sqlite3
import logging
from datetime import datetime, time as dtime

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# ---------- CONFIG ----------
TOKEN = os.environ.get("TELEGRAM_TOKEN") or "PUT_YOUR_TOKEN_HERE"
DB_PATH = "reminders.db"
LOGLEVEL = logging.INFO
# ----------------------------

logging.basicConfig(level=LOGLEVEL, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ---------- DB UTIL ----------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            rem_time TEXT NOT NULL, -- stored as HH:MM
            text TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def add_reminder_to_db(chat_id: int, rem_time: str, text: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO reminders (chat_id, rem_time, text) VALUES (?,?,?)", (chat_id, rem_time, text))
    rid = cur.lastrowid
    conn.commit()
    conn.close()
    return rid


def remove_reminder_from_db(rid: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM reminders WHERE id = ?", (rid,))
    changed = cur.rowcount
    conn.commit()
    conn.close()
    return changed > 0


def list_reminders_from_db(chat_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, rem_time, text FROM reminders WHERE chat_id = ? ORDER BY rem_time", (chat_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def all_reminders():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, chat_id, rem_time, text FROM reminders")
    rows = cur.fetchall()
    conn.close()
    return rows

# ---------- SCHEDULING HELPERS ----------

def parse_time_hhmm(s: str):
    """Parse HH:MM (24-hour) and return datetime.time or None"""
    try:
        parts = s.strip().split(":")
        if len(parts) != 2:
            return None
        hh = int(parts[0])
        mm = int(parts[1])
        if not (0 <= hh < 24 and 0 <= mm < 60):
            return None
        return dtime(hour=hh, minute=mm)
    except Exception:
        return None


async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    chat_id = job_data["chat_id"]
    text = job_data["text"]
    try:
        await context.bot.send_message(chat_id=chat_id, text=f"🔔 Esingizga tushurish: {text}")
    except Exception as e:
        logger.exception("Failed to send reminder: %s", e)


def schedule_reminder(job_queue, rid: int, chat_id: int, rem_time_str: str, text: str):
    t = parse_time_hhmm(rem_time_str)
    if t is None:
        return False
    # store job name so we can cancel later
    job_name = f"reminder_{rid}"
    job_queue.run_daily(send_reminder, time=t, days=(0,1,2,3,4,5,6), name=job_name, data={"chat_id": chat_id, "text": text})
    logger.info("Scheduled reminder %s for chat %s at %s", rid, chat_id, rem_time_str)
    return True

# ---------- BOT COMMANDS ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! Men kundalik eslatma botiman.\n\n" 
        "Foydalanish: /add HH:MM tekst - yangi kunlik eslatma qo'shish\n"
        "/list - eslatmalar ro'yxati\n"
        "/remove ID - eslatmani o'chirish\n"
        "/help - yordam"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Expected: /add 08:30 Buy groceries
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Foydalanish: /add HH:MM tekst. Masalan: /add 08:30 Non olib kelish")
        return
    rem_time = context.args[0]
    text = " ".join(context.args[1:])
    t = parse_time_hhmm(rem_time)
    if t is None:
        await update.message.reply_text("Vaqt noto'g'ri formatda. Iltimos HH:MM (24-soat) formatida kiriting.")
        return
    chat_id = update.effective_chat.id
    rid = add_reminder_to_db(chat_id, rem_time, text)
    # schedule it
    scheduled = schedule_reminder(context.job_queue, rid, chat_id, rem_time, text)
    if scheduled:
        await update.message.reply_text(f"Eslatma qo'shildi (ID: {rid}) — {rem_time} — {text}")
    else:
        await update.message.reply_text("Eslatma qo'shildi lekin rejalashtirishda xato yuz berdi.")


async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    rows = list_reminders_from_db(chat_id)
    if not rows:
        await update.message.reply_text("Sizda hech qanday eslatma yo'q.")
        return
    msg_lines = [f"ID | Vaqt | Matn"]
    for r in rows:
        msg_lines.append(f"{r[0]} | {r[1]} | {r[2]}")
    await update.message.reply_text("\n".join(msg_lines))


async def remove_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Foydalanish: /remove ID")
        return
    try:
        rid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID butun son bo'lishi kerak.")
        return
    # cancel scheduled job if exists
    job_name = f"reminder_{rid}"
    jobs = context.job_queue.get_jobs_by_name(job_name)
    for j in jobs:
        j.schedule_removal()
    removed = remove_reminder_from_db(rid)
    if removed:
        await update.message.reply_text(f"Eslatma (ID: {rid}) o'chirildi.")
    else:
        await update.message.reply_text("Bunday ID topilmadi.")


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Noma'lum buyruq. /help bilan yordamni ko'ring.")


# ---------- STARTUP ----------

async def on_startup(application):
    logger.info("Bot ishga tushmoqda — DB init va mavjud eslatmalarni yuklash...")
    init_db()
    # schedule existing reminders
    for rid, chat_id, rem_time, text in all_reminders():
        try:
            schedule_reminder(application.job_queue, rid, chat_id, rem_time, text)
        except Exception:
            logger.exception("Failed to schedule reminder id=%s", rid)


def main():
    if TOKEN == "PUT_YOUR_TOKEN_HERE":
        logger.error("Iltimos TELEGRAM tokenini TOKEN o'zgaruvchisiga yoki TELEGRAM_TOKEN muhit o'zgaruvchisiga qo'ying")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("list", list_cmd))
    app.add_handler(CommandHandler("remove", remove_cmd))
    app.add_handler(CommandHandler(None, unknown))

    # run startup tasks (schedule existing reminders)
    app.post_init(on_startup)

    logger.info("Bot ishga tushdi — polling boshlanmoqda...")
    app.run_polling()


if __name__ == "__main__":
    main()
