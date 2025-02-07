from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ConversationHandler


async def back_to_main_menu(update: Update, context):
    """Возвращает ментора в главное меню"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("📚 Домашние задания")],
            [KeyboardButton("🎓 Выставление оценки")],
            [KeyboardButton("📅 Записи на звонки")],
            [KeyboardButton("📌 Подтверждение сдачи темы")],
            [KeyboardButton("✉ Уведомления")]
        ],
        resize_keyboard=True
    )

    await update.message.reply_text("🔙 Вы вернулись в главное меню.", reply_markup=keyboard)
    return ConversationHandler.END
