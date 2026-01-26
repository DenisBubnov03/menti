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
                    [KeyboardButton("📌 Подтверждение сдачи темы")],
                    [KeyboardButton("📊 Проверить успеваемость")],
                    [KeyboardButton("➕ Добавить ментора")],
                    [KeyboardButton("📢 Сделать рассылку")],
                    [KeyboardButton("🗑 Удалить ментора")],
                    [KeyboardButton("📅 Записи на звонки")],
                    [KeyboardButton("📹 Создание встречи")]
                ],
                resize_keyboard=True
            )
            await update.message.reply_text("🔙 Вы вернулись в главное меню.", reply_markup=keyboard)
            return ConversationHandler.END

        # Меню для обычного ментора
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton("📚 Домашние задания")],
                [KeyboardButton("📌 Подтверждение сдачи темы")],
                [KeyboardButton("📅 Записи на звонки")],
                [KeyboardButton("📊 Проверить успеваемость")],
                [KeyboardButton("📹 Создание встречи")],
            ],
            resize_keyboard=True
        )
        await update.message.reply_text("🔙 Вы вернулись в главное меню.", reply_markup=keyboard)
        return ConversationHandler.END

    # ✅ Проверяем, является ли пользователь студентом
    student = session.query(Student).filter_by(telegram=username).first()
    if student:
        keyboard_buttons = [
            [KeyboardButton("🆕 Получить новую тему")],
            [KeyboardButton("🐛 Бесконечные баги")],
        ]
        training_type = student.training_type.strip().lower() if student.training_type else ""
        auto_mentor = session.query(Mentor).get(getattr(student, 'auto_mentor_id', None)) if getattr(student, 'auto_mentor_id', None) else None

        # Добавляем кнопку "Отправить домашку" только для ручного тестирования и фуллстеков
        if student.training_type in ["Ручное тестирование", "Фуллстек"]:
            keyboard_buttons.append([KeyboardButton("📚 Отправить домашку")])
        # Добавляем кнопку "Запросить назначение куратора" для фуллстеков, если не назначен какой-либо куратор
        if training_type == "фуллстек" and (not mentor or not auto_mentor):
            keyboard_buttons.append([KeyboardButton("👨‍🏫 Запросить назначение куратора")])
        keyboard_buttons.extend([
            [KeyboardButton("📜 Мои темы и ссылки")],
           # [KeyboardButton("📅 Записаться на звонок")],
            [KeyboardButton("💳 Оплата за обучение")],
            [KeyboardButton("💸 Выплата комиссии")],
            [KeyboardButton("📋 Правила")],
        ])
        keyboard = ReplyKeyboardMarkup(
            keyboard=keyboard_buttons,
            resize_keyboard=True
        )
        await update.message.reply_text("🔙 Вы вернулись в главное меню.", reply_markup=keyboard)
        return ConversationHandler.END

    # ✅ Если пользователь не найден
    await update.message.reply_text("❌ Ошибка: ваш профиль не найден.")
    return ConversationHandler.END


from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

def update_student_data(handler):
    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            return

        # 1. Берем текущие данные из Telegram
        current_chat_id = str(user.id) # В модели у тебя String(50)
        current_username = f"@{user.username}" if user.username else None

        # 2. Ищем студента по chat_id (это надежнее, чем по нику)
        student = session.query(Student).filter(Student.chat_id == current_chat_id).first()

        # 3. Если по chat_id не нашли, пробуем найти по нику
        # (это нужно для "первой связки", если chat_id еще не был записан)
        if not student and current_username:
            student = session.query(Student).filter(Student.telegram == current_username).first()
            if student:
                # Если нашли по нику, сразу привязываем chat_id на будущее
                student.chat_id = current_chat_id
                session.commit()

        # 4. Проверка регистрации
        if not student:
            if update.message:
                await update.message.reply_text("❌ Вы не зарегистрированы как студент!")
            return

        # 5. САМАЯ ВАЖНАЯ ЧАСТЬ: Обновляем ник, если он изменился
        if current_username and student.telegram != current_username:
            print(f"🔄 Обновляем ник студента ID {student.id}: {student.telegram} -> {current_username}")
            student.telegram = current_username
            session.commit()

        return await handler(update, context, *args, **kwargs)

    return wrapper