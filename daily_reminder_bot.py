import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)
from datetime import time

# States
ASK_TASK_NAME, ASK_HOUR, ASK_MINUTE = range(3)

# Foydalanuvchilar ishlarini saqlash
user_tasks = {}

# /add bosilganda ish nomi so'raladi
async def add_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 Iltimos ish nomini kiriting (bo‘sh qoldirish mumkin):"
    )
    return ASK_TASK_NAME

# Ish nomini olamiz, soatni so'raymiz
async def ask_hour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task_name = update.message.text.strip() or "Ishingiz"
    context.user_data["task_name"] = task_name
    await update.message.reply_text("⏰ Eslatma yuboriladigan soatni kiriting (0-23):")
    return ASK_HOUR

# Soatni olamiz, daqiqani so'raymiz
async def ask_minute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        hour = int(update.message.text.strip())
        if not (0 <= hour <= 23):
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Iltimos, 0 dan 23 gacha bo‘lgan raqam kiriting.")
        return ASK_HOUR
    context.user_data["task_hour"] = hour
    await update.message.reply_text("⏰ Eslatma yuboriladigan daqiqani kiriting (0-59):")
    return ASK_MINUTE

# Daqiqani olamiz va ishni saqlaymiz
async def set_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    try:
        minute = int(update.message.text.strip())
        if not (0 <= minute <= 59):
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Iltimos, 0 dan 59 gacha bo‘lgan raqam kiriting.")
        return ASK_MINUTE

    task_name = context.user_data["task_name"]
    hour = context.user_data["task_hour"]

    if user_id not in user_tasks:
        user_tasks[user_id] = []

    job = context.job_queue.run_daily(
        daily_reminder, time(hour=hour, minute=minute), chat_id=user_id, name=f"{user_id}_{task_name}"
    )

    user_tasks[user_id].append({"name": task_name, "hour": hour, "minute": minute, "job": job})

    await update.message.reply_text(f"✅ Ish qo‘shildi: {task_name}\n⏰ Eslatma vaqti: {hour:02d}:{minute:02d}")
    return ConversationHandler.END

# Har kuni eslatma yuborish
async def daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    await context.bot.send_message(chat_id, "⏰ Esingizda bo‘lsin, bugun ishlaringiz bor!")

# Ishlar ro‘yxati
async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    tasks = user_tasks.get(user_id, [])
    if not tasks:
        await update.message.reply_text("📭 Sizda hali hech qanday ish yo‘q.")
        return
    msg = "📋 Kundalik ishlaringiz:\n"
    for i, t in enumerate(tasks, start=1):
        msg += f"{i}. {t['name']} – {t['hour']:02d}:{t['minute']:02d}\n"
    await update.message.reply_text(msg)

# Ishni o‘chirish
async def remove_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not context.args:
        await update.message.reply_text("❗ Foydalanish: /remove <raqam>")
        return
    try:
        index = int(context.args[0]) - 1
        tasks = user_tasks.get(user_id, [])
        if 0 <= index < len(tasks):
            removed = tasks.pop(index)
            if removed["job"]:
                removed["job"].schedule_removal()
            await update.message.reply_text(f"❌ O‘chirildi: {removed['name']}")
        else:
            await update.message.reply_text("❗ Noto‘g‘ri raqam kiritildi.")
    except ValueError:
        await update.message.reply_text("❗ Raqamni to‘g‘ri kiriting.")

# Bekor qilish
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Ish qo‘shish bekor qilindi.")
    return ConversationHandler.END

# Start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Assalomu alaykum! 👋\n"
        "Men sizning kundalik eslatma botingizman.\n\n"
        "Buyruqlar:\n"
        "/add – yangi ish qo‘shish\n"
        "/remove <raqam> – ishni o‘chirish\n"
        "/list – barcha ishlarni ko‘rish\n"
        "/cancel – ish qo‘shishni bekor qilish"
    )

def main():
    TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TOKEN:
        print("❗ TELEGRAM_TOKEN topilmadi. Environment Variables ga qo‘shing.")
        return

    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add", add_task_start)],
        states={
            ASK_TASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_hour)],
            ASK_HOUR: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_minute)],
            ASK_MINUTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_task)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_tasks))
    app.add_handler(CommandHandler("remove", remove_task))
    app.add_handler(conv_handler)

    print("🤖 Bot ishlayapti...")
    app.run_polling()

if __name__ == "__main__":
    main()
