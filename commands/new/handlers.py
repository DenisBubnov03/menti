# commands/submit_topic/handlers.py

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from commands.states import SUBMIT_TOPIC_SELECT, SUBMIT_TOPIC_STUDENTS
from data_base.db import session
from data_base.models import Student, Mentor, Homework, ManualProgress
from datetime import datetime

TOPIC_FIELD_MAPPING = {
    "1 модуль": "m1_submission_date",
    "Тема 2.1 + 2.2": "m2_1_2_2_submission_date",
    "Тема 2.3 + 3.1": "m2_3_3_1_submission_date",
    "Тема 3.2": "m3_2_submission_date",
    "Тема 3.3": "m3_3_submission_date",
    "Тема 4.1": "m4_1_submission_date",
    "Тема 4.2 + 4.3": "m4_2_4_3submission_date",
}


async def start_topic_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор темы (уже с модулем)"""
    keyboard = [[KeyboardButton(name)] for name in TOPIC_FIELD_MAPPING.keys()]
    await update.message.reply_text(
        "Выберите тему, которую сдаёт студент:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return SUBMIT_TOPIC_SELECT


async def select_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["selected_topic_label"] = update.message.text.strip()
    await update.message.reply_text("Введите Telegram юзернеймы студентов через запятую (например: @user1, @user2):")
    return SUBMIT_TOPIC_STUDENTS



async def submit_topic_students(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usernames = [u.strip() for u in update.message.text.split(",")]
    topic = context.user_data["selected_topic_label"]
    field_name = TOPIC_FIELD_MAPPING.get(topic)
    now = datetime.now().date()

    mentor_tg = "@" + update.message.from_user.username
    mentor = session.query(Mentor).filter_by(telegram=mentor_tg).first()

    if not mentor:
        await update.message.reply_text("❌ Вы не зарегистрированы как ментор.")
        return ConversationHandler.END

    found = []
    not_found = []

    for username in usernames:
        student = session.query(Student).filter_by(telegram=username).first()
        if student:
            progress = session.query(ManualProgress).filter_by(student_id=student.id).first()

            if progress and field_name and hasattr(progress, field_name):
                setattr(progress, field_name, now)
                found.append(username)
            else:
                not_found.append(username + " (нет поля)")
        else:
            not_found.append(username + " (не найден)")

    session.commit()

    msg = ""
    if found:
        msg += f"✅ Дата сдачи темы '{topic}' проставлена: {', '.join(found)}\n"
    if not_found:
        msg += f"⚠️ Проблемы с: {', '.join(not_found)}"

    await update.message.reply_text(msg)
    return ConversationHandler.END
