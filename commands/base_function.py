from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ConversationHandler
from data_base.db import session
from data_base.models import Mentor, Student


async def back_to_main_menu(update: Update, context):
    """
    Возвращает пользователя в главное меню в зависимости от его роли:
    - Админ-ментор: дополнительные права.
    - Обычный ментор.
    - Студент.
    """
    user_id = update.message.from_user.id
    username = "@" + update.message.from_user.username if update.message.from_user.username else None

    # ✅ Проверяем, является ли пользователь админом-ментором
    mentor = session.query(Mentor).filter(Mentor.chat_id == str(user_id)).first()

    if mentor:
        if mentor.is_admin:
            # Меню для админ-ментора
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton("💰 Платежи")],
                    [KeyboardButton("📚 Домашние задания")],
                    [KeyboardButton("➕ Добавить ментора")],
                    [KeyboardButton("📢 Сделать рассылку")],
                    [KeyboardButton("🗑 Удалить ментора")],
                    [KeyboardButton("📅 Записи на звонки")]
                ],
                resize_keyboard=True
            )
            await update.message.reply_text("🔙 Вы вернулись в главное меню.", reply_markup=keyboard)
            return ConversationHandler.END

        # Меню для обычного ментора
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton("📚 Домашние задания")],
                [KeyboardButton("🎓Выставление оценки (еще не реализовано)")],
                [KeyboardButton("📅 Записи на звонки")],
                [KeyboardButton("📌Подтверждение сдачи темы (еще не реализовано)")],
            ],
            resize_keyboard=True
        )
        await update.message.reply_text("🔙 Вы вернулись в главное меню.", reply_markup=keyboard)
        return ConversationHandler.END

    # ✅ Проверяем, является ли пользователь студентом
    student = session.query(Student).filter_by(telegram=username).first()
    if student:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton("📅 Записаться на звонок")],
                [KeyboardButton("📚 Отправить домашку")],
                [KeyboardButton("💳 Оплата за обучение")]
            ],
            resize_keyboard=True
        )
        await update.message.reply_text("🔙 Вы вернулись в главное меню.", reply_markup=keyboard)
        return ConversationHandler.END

    # ✅ Если пользователь не найден
    await update.message.reply_text("❌ Ошибка: ваш профиль не найден.")
    return ConversationHandler.END
