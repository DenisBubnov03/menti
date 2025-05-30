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
                [KeyboardButton("💰 Платежи")],
                [KeyboardButton("📚 Домашние задания")],
                [KeyboardButton("➕ Добавить ментора")],
                [KeyboardButton("📢 Сделать рассылку")],
                [KeyboardButton("🗑 Удалить ментора")],
                [KeyboardButton("📅 Записи на звонки")]
            ],
            resize_keyboard=True
        )
        await update.message.reply_text("🔹 Вы вошли как админ-ментор. Выберите действие:", reply_markup=keyboard)
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
                [KeyboardButton("📅 Записи на звонки")],
                [KeyboardButton("📌Подтверждение сдачи темы (еще не реализовано)")],
            ],
            resize_keyboard=True
        )
        await update.message.reply_text("🔹 Вы вошли как ментор. Выберите действие:", reply_markup=keyboard)
        return

    # Проверяем, студент ли это
    student = get_student_by_fio_or_telegram(username)
    if student:
        if not student.chat_id:
            student.chat_id = chat_id
            session.commit()
            # ✅ Хардкод менторов

        manual_mentor = session.query(Mentor).get(1)  # Ментор по ручному тестированию
        mentor = session.query(Mentor).get(student.mentor_id) if student.mentor_id else None

        training_type = student.training_type.strip().lower() if student.training_type else ""
        mentor_info = ""

        if training_type == "фуллстек":
            # Показываем обоих: ручной (жестко) + закреплённый (auto)
            mentor_info = "\n👨‍🏫 Менторы для ваших направлений:\n"
            mentor_info += f"💼 Ручное тестирование: {manual_mentor.full_name if manual_mentor else 'Не назначен'} {manual_mentor.telegram if manual_mentor else ''}\n"
            mentor_info += f"💻 Автотестирование: {mentor.full_name if mentor else 'Не назначен'} {mentor.telegram if mentor else ''}"
        elif training_type == "ручное тестирование":
            mentor_info = f"\n👨‍🏫 Ваш ментор по ручному тестированию: {mentor.full_name if mentor else 'Не назначен'} {mentor.telegram if mentor else ''}"
        elif training_type == "автотестирование":
            mentor_info = f"\n👨‍🏫 Ваш ментор по автотестированию: {mentor.full_name if mentor else 'Не назначен'} {mentor.telegram if mentor else ''}"
        else:
            mentor_info = "\n⚠ Обратите внимание: У вас не указан тип обучения."

        keyboard_buttons = [
            [KeyboardButton("📅 Записаться на звонок")],
            [KeyboardButton("📚 Отправить домашку")],
            [KeyboardButton("💳 Оплата за обучение")]
        ]

        # 🔍 Добавляем кнопку, если студент устроился
        if student.training_status.strip().lower() == "устроился":
            keyboard_buttons.append([KeyboardButton("💸 Выплата комиссии")])

        keyboard = ReplyKeyboardMarkup(keyboard_buttons, resize_keyboard=True)
        await update.message.reply_text(f"🔹 Привет, {student.fio}! Вы вошли как ученик.{mentor_info}",
                                        reply_markup=keyboard)
        return
