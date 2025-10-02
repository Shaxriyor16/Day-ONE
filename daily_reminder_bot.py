import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from datetime import time

# Kundalik ishlar ro‘yxati (xotira ichida saqlanadi)
tasks = []

# Start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Assalomu alaykum! 👋\n"
        "Men sizning kundalik eslatma botingizman.\n\n"
        "Buyruqlar:\n"
        "/add <ish> – yangi ish qo‘shish\n"
        "/remove <raqam> – ro‘yxatdan ishni o‘chirish\n"
        "/list – barcha ishlarni ko‘rish"
    )

# Yangi ish qo‘shish
async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task = " ".join(context.args)
    if not task:
        await update.message.reply_text("❗ Foydalanish: /add <ish>")
        return
    tasks.append(task)
    await update.message.reply_text(f"✅ Ish qo‘shildi: {task}")

# Ishni o‘chirish
async def remove_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ Foydalanish: /remove <raqam>")
        return
    try:
        index = int(context.args[0]) - 1
        if 0 <= index < len(tasks):
            removed = tasks.pop(index)
            await update.message.reply_text(f"❌ O‘chirildi: {removed}")
        else:
            await update.message.reply_text("❗ Noto‘g‘ri raqam kiritildi.")
    except ValueError:
        await update.message.reply_text("❗ Raqamni to‘g‘ri kiriting.")

# Ishlar ro‘yxatini ko‘rish
async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not tasks:
        await update.message.reply_text("📭 Sizda hali hech qanday ish yo‘q.")
        return
    msg = "📋 Kundalik ishlaringiz:\n"
    for i, task in enumerate(tasks, start=1):
        msg += f"{i}. {task}\n"
    await update.message.reply_text(msg)

# Har kuni eslatma yuborish
async def daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    if tasks:
        msg = "⏰ Bugungi ishlaringiz:\n"
        for i, task in enumerate(tasks, start=1):
            msg += f"{i}. {task}\n"
    else:
        msg = "📭 Sizda bugun hech qanday ish yo‘q."
    await context.bot.send_message(chat_id, msg)

# Eslatma o‘rnatish
async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Masalan, soat 9:00 da eslatadi
    job_queue = context.job_queue
    job_queue.run_daily(daily_reminder, time(hour=9, minute=0), chat_id=chat_id)

    await update.message.reply_text("✅ Har kuni soat 09:00 da eslatma yuboraman!")

# Noma’lum komandalar
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Kechirasiz, bu komanda menga tushunarli emas.")

# Asosiy qism
def main():
    TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TOKEN:
        print("❗ TELEGRAM_TOKEN topilmadi. Renderda Environment Variables ga qo‘shing.")
        return

    app = Application.builder().token(TOKEN).build()

    # Komandalar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_task))
    app.add_handler(CommandHandler("remove", remove_task))
    app.add_handler(CommandHandler("list", list_tasks))
    app.add_handler(CommandHandler("remind", set_reminder))

    # Noma’lum komandalarni ushlash
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    print("🤖 Bot ishlayapti...")
    app.run_polling()

if __name__ == "__main__":
    main()
