from commands.homework_mentor import *
from data_base.models import Mentor
from data_base.operations import is_mentor, get_student_by_fio_or_telegram, is_admin
from telegram import  ReplyKeyboardMarkup, KeyboardButton


async def start_command(update, context):
    message = update.message
    username = str(message.from_user.username)

    # Добавляем @, если его нет
    if not username.startswith("@"):
        username = "@" + username  # ← Переопределяем username

    chat_id = message.chat_id  # Получаем chat_id

    if is_admin(username):  # Проверяем, админ ли это
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton("📚 Домашние задания")],
                [KeyboardButton("🎓 Выставление оценки")],
                [KeyboardButton("📢 Сделать рассылку")],  # ✅ Добавляем рассылку
                [KeyboardButton("📅 Записи на звонки")],
                [KeyboardButton("📌 Подтверждение сдачи темы")],
                [KeyboardButton("✉ Уведомления")]
            ],
            resize_keyboard=True
        )
        await update.message.reply_text("🔹 Вы вошли как АДМИН-МЕНТОР. Выберите действие:", reply_markup=keyboard)
        return

    # Проверяем, ментор ли это
    if is_mentor(username):
        mentor = session.query(Mentor).filter(Mentor.telegram == username).first()
        if mentor:
            if not mentor.chat_id:
                mentor.chat_id = chat_id  # Сохраняем chat_id
                session.commit()
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton("📚 Домашние задания")],
                [KeyboardButton("🎓Выставление оценки")],
                [KeyboardButton("📅 Записи на звонки")],
                [KeyboardButton("📌Подтверждение сдачи темы")],
                [KeyboardButton("✉ Уведомления")]
            ],
            resize_keyboard=True
        )
        await update.message.reply_text("🔹 Вы вошли как МЕНТОР. Выберите действие:", reply_markup=keyboard)
        return

    # Проверяем, студент ли это
    student = get_student_by_fio_or_telegram(username)
    if student:
        if not student.chat_id:
            student.chat_id = chat_id
            session.commit()
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton("📅 Записаться на звонок")],
                [KeyboardButton("📚 Отправить домашку")],
                [KeyboardButton("💳 Оплата за обучение")]
            ],
            resize_keyboard=True
        )
        await update.message.reply_text(f"🔹 Привет, {student.fio}! Вы вошли как СТУДЕНТ.", reply_markup=keyboard)
        return

    await update.message.reply_text("❌ Вы не зарегистрированы в системе.")