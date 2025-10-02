import os
import sqlite3
from datetime import time, datetime
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# --- MA'LUMOTLAR BAZASI ---
DB_FILE = "tasks.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            chat_id INTEGER,
            task TEXT,
            PRIMARY KEY(chat_id, task)
        )
    """)
    conn.commit()
    conn.close()

def add_task_db(chat_id: int, task: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO tasks(chat_id, task) VALUES (?, ?)", (chat_id, task))
    conn.commit()
    conn.close()

def remove_task_db(chat_id: int, index: int) -> str:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT task FROM tasks WHERE chat_id=? ORDER BY rowid", (chat_id,))
    rows = cursor.fetchall()
    if 0 <= index < len(rows):
        task = rows[index][0]
        cursor.execute("DELETE FROM tasks WHERE chat_id=? AND task=?", (chat_id, task))
        conn.commit()
        conn.close()
        return task
    conn.close()
    return None

def list_tasks_db(chat_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT task FROM tasks WHERE chat_id=? ORDER BY rowid", (chat_id,))
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

# --- KOMANDALAR ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Assalomu alaykum! 👋\n"
        "Men sizning kundalik eslatma botingizman.\n\n"
        "Buyruqlar:\n"
        "/add <ish> – yangi ish qo‘shish\n"
        "/remove <raqam> – ro‘yxatdan ishni o‘chirish\n"
        "/list – barcha ishlarni ko‘rish\n"
        "/remind – har kuni eslatma o‘rnatish"
    )

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task = " ".join(context.args)
    if not task:
        await update.message.reply_text("❗ Foydalanish: /add <ish>")
        return
    add_task_db(update.effective_chat.id, task)
    await update.message.reply_text(f"✅ Ish qo‘shildi: {task}")

async def remove_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ Foydalanish: /remove <raqam>")
        return
    try:
        index = int(context.args[0]) - 1
        removed = remove_task_db(update.effective_chat.id, index)
        if removed:
            await update.message.reply_text(f"❌ O‘chirildi: {removed}")
        else:
            await update.message.reply_text("❗ Noto‘g‘ri raqam kiritildi.")
    except ValueError:
        await update.message.reply_text("❗ Raqamni to‘g‘ri kiriting.")

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = list_tasks_db(update.effective_chat.id)
    if not tasks:
        await update.message.reply_text("📭 Sizda hali hech qanday ish yo‘q.")
        return
    msg = "📋 Kundalik ishlaringiz:\n"
    for i, task in enumerate(tasks, start=1):
        msg += f"{i}. {task}\n"
    await update.message.reply_text(msg)

# --- HAR KUNI ESLATMA ---
async def daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT chat_id FROM tasks")
    chat_ids = [r[0] for r in cursor.fetchall()]
    conn.close()

    for chat_id in chat_ids:
        tasks = list_tasks_db(chat_id)
        if tasks:
            msg = "⏰ Bugungi ishlaringiz:\n" + "\n".join(f"{i+1}. {t}" for i, t in enumerate(tasks))
        else:
            msg = "📭 Sizda bugun hech qanday ish yo‘q."
        await context.bot.send_message(chat_id, msg)

async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    # Har kuni soat 9:00 da eslatma
    context.job_queue.run_daily(daily_reminder, time(hour=9, minute=0), chat_id=chat_id)
    await update.message.reply_text("✅ Har kuni soat 09:00 da eslatma yuboraman!")

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Kechirasiz, bu komanda menga tushunarli emas.")

# --- ASOSIY FUNKSIYA ---
def main():
    TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TOKEN:
        print("❗ TELEGRAM_TOKEN topilmadi.")
        return

    init_db()
    app = Application.builder().token(TOKEN).build()

    # Komandalar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_task))
    app.add_handler(CommandHandler("remove", remove_task))
    app.add_handler(CommandHandler("list", list_tasks))
    app.add_handler(CommandHandler("remind", set_reminder))

    # Noma’lum komandalar
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    print("🤖 Bot ishlayapti...")
    app.run_polling()

if __name__ == "__main__":
    main()
