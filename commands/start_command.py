from datetime import datetime

from commands.homework_mentor import *
from data_base.models import Mentor, ManualProgress
from data_base.operations import is_mentor, get_student_by_fio_or_telegram, is_admin
from telegram import  ReplyKeyboardMarkup, KeyboardButton, Update
from telegram.ext import ContextTypes
from data_base.db import session
from data_base.models import Student, ManualProgress, AutoProgress
from commands.get_new_topic import MANUAL_MODULE_2_LINKS, MANUAL_MODULE_3_LINKS, MANUAL_MODULE_4_LINKS, AUTO_MODULE_LINKS


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
                [KeyboardButton("📌 Подтверждение сдачи темы")],
                [KeyboardButton("📊 Проверить успеваемость")],
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
                [KeyboardButton("📌 Подтверждение сдачи темы")],
                [KeyboardButton("📅 Записи на звонки")],
                [KeyboardButton("📊 Проверить успеваемость")],
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
        auto_mentor = session.query(Mentor).get(getattr(student, 'auto_mentor_id', None)) if getattr(student, 'auto_mentor_id', None) else None

        training_type = student.training_type.strip().lower() if student.training_type else ""
        mentor_info = ""

        if training_type == "фуллстек":
            mentor_info = "\n👨‍🏫 Менторы для ваших направлений:\n"
            mentor_info += f"💼 Ручное тестирование: {manual_mentor.full_name if manual_mentor else 'Не назначен'} {manual_mentor.telegram if manual_mentor else ''}\n"
            mentor_info += f"💻 Автотестирование: {auto_mentor.full_name if auto_mentor else 'Не назначен'} {auto_mentor.telegram if auto_mentor else ''}"
        elif training_type == "ручное тестирование":
            mentor_info = f"\n👨‍🏫 Ваш ментор по ручному тестированию: {mentor.full_name if mentor else 'Не назначен'} {mentor.telegram if mentor else ''}"
        elif training_type == "автотестирование":
            mentor_info = f"\n👨‍🏫 Ваш ментор по автотестированию: {auto_mentor.full_name if mentor else 'Не назначен'} {auto_mentor.telegram if mentor else ''}"
        else:
            mentor_info = "\n⚠ Обратите внимание: У вас не указан тип обучения."

        keyboard_buttons = [
            [KeyboardButton("🆕 Получить новую тему")],
            [KeyboardButton("📅 Записаться на звонок")],
            [KeyboardButton("📚 Отправить домашку")],
            [KeyboardButton("📜 Мои темы и ссылки")],
            [KeyboardButton("💳 Оплата за обучение")],
        ]

        # 🔍 Добавляем кнопку, если студент устроился
        if student.training_status.strip().lower() == "устроился":
            keyboard_buttons.append([KeyboardButton("💸 Выплата комиссии")])

        keyboard = ReplyKeyboardMarkup(keyboard_buttons, resize_keyboard=True)
        await update.message.reply_text(f"🔹 Привет, {student.fio}! Вы вошли как ученик.{mentor_info}",
                                        reply_markup=keyboard)
        return


async def my_topics_and_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    student_telegram = f"@{update.message.from_user.username}"
    student = session.query(Student).filter_by(telegram=student_telegram).first()
    if not student:
        await update.message.reply_text("❌ Вы не зарегистрированы как студент!")
        return
    msg = []
    # Ручное тестирование
    if student.training_type.lower().startswith("ручн") or student.training_type.lower().startswith("фулл"):
        progress = session.query(ManualProgress).filter_by(student_id=student.id).first()
        if progress:
            msg.append("<b>Ручное тестирование:</b>")
            # 2 модуль
            if progress.m2_1_start_date:
                msg.append(f"- Тема 2.1: {MANUAL_MODULE_2_LINKS.get('Тема 2.1','-')}")
            if progress.m2_3_start_date:
                msg.append(f"- Тема 2.3: {MANUAL_MODULE_2_LINKS.get('Тема 2.3','-')}")
            # 3 модуль
            if progress.m3_1_start_date:
                msg.append(f"- Тема 3.1: {MANUAL_MODULE_3_LINKS.get('Тема 3.1','-')}")
            if progress.m3_2_start_date:
                msg.append(f"- Тема 3.2: {MANUAL_MODULE_3_LINKS.get('Тема 3.2','-')}")
            if progress.m3_3_start_date:
                msg.append(f"- Тема 3.3: {MANUAL_MODULE_3_LINKS.get('Тема 3.3','-')}")
            # 4 модуль
            if progress.m4_1_start_date:
                msg.append(f"- Тема 4.1: {MANUAL_MODULE_4_LINKS.get('Тема 4.1','-')}")
            if progress.m4_2_start_date:
                msg.append(f"- Тема 4.2: {MANUAL_MODULE_4_LINKS.get('Тема 4.2','-')}")
            if progress.m4_3_start_date:
                msg.append(f"- Тема 4.3: {MANUAL_MODULE_4_LINKS.get('Тема 4.3','-')}")
            # Доп. темы 4 модуля
            if getattr(progress, 'm4_4_start_date', None):
                msg.append(f"- Тема 4.4: {MANUAL_MODULE_4_LINKS.get('Тема 4.4','-')}")
            if getattr(progress, 'm4_5_start_date', None):
                msg.append(f"- Тема 4.5: {MANUAL_MODULE_4_LINKS.get('Тема 4.5','-')}")
            if getattr(progress, 'm4_mock_exam_start_date', None):
                msg.append(f"- Мок экзамен: {MANUAL_MODULE_4_LINKS.get('Мок экзамен','-')}")
    # Автотестирование
    if student.training_type.lower().startswith("авто") or student.training_type.lower().startswith("фулл"):
        progress = session.query(AutoProgress).filter_by(student_id=student.id).first()
        if progress:
            msg.append("\n<b>Автотестирование:</b>")
            for i in range(1, 9):
                if getattr(progress, f"m{i}_start_date", None):
                    msg.append(f"- Модуль {i}: {AUTO_MODULE_LINKS.get(i,'-')}")
    if not msg:
        await update.message.reply_text("У вас пока нет открытых тем.")
    else:
        await update.message.reply_text("\n".join(msg), parse_mode="HTML")
