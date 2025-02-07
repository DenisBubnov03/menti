from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import MessageHandler, ConversationHandler

from commands.base_function import back_to_main_menu
from commands.states import HOMEWORK_WAITING
from data_base.db import session
from data_base.models import Homework
from data_base.operations import get_pending_homework, approve_homework, update_homework_status


async def homework_list(update: Update, context):
    """Ментор смотрит список домашних заданий"""
    homework_list = get_pending_homework("@"+update.message.from_user.username)

    if not homework_list:
        await update.message.reply_text("✅ Нет ожидающих проверку домашних заданий.")
        return ConversationHandler.END

    response = "📌 Домашние задания на проверке:\n"
    for hw in homework_list:
        response += f"🏷 ID: {hw.id}, @{hw.student.telegram} – {hw.module} / {hw.topic}\n"

    response += "\n✏ Введите ID домашнего задания, чтобы проверить."

    # 🔹 Добавляем кнопку "🔙 В главное меню"
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("🔙 В главное меню")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await update.message.reply_text(response, reply_markup=keyboard)
    return HOMEWORK_WAITING


async def check_homework(update: Update, context):
    """Ментор выбирает домашку по ID"""
    hw_id = update.message.text.strip()

    # Проверяем, что введено число (ID домашки)
    if not hw_id.isdigit():
        await update.message.reply_text("❌ Введите корректный ID домашки (число).")
        return HOMEWORK_WAITING

    homework = session.query(Homework).filter(Homework.id == hw_id).first()

    if not homework:
        await update.message.reply_text("❌ Ошибка! Домашка с таким ID не найдена.")
        return HOMEWORK_WAITING

    context.user_data["homework_id"] = hw_id
    context.user_data["module"] = homework.module  # ✅ Запоминаем модуль
    context.user_data["topic"] = homework.topic  # ✅ Запоминаем тему

    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("✅ Принять")], [KeyboardButton("❌ Отклонить")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await update.message.reply_text(f"🏷 ID: {hw_id}\nМодуль: {homework.module}, Тема: {homework.topic}\nВыберите действие:", reply_markup=keyboard)
    return "CHECKING"




async def accept_homework(update: Update, context):
    """Ментор принимает домашку"""
    hw_id = context.user_data["homework_id"]
    approve_homework(hw_id)
    await update.message.reply_text(f"✅ Домашка {hw_id} принята!")
    return await back_to_main_menu(update, context)


async def reject_homework(update: Update, context):
    """Ментор отклоняет домашку"""
    hw_id = context.user_data["homework_id"]
    await update.message.reply_text("❌ Введите комментарий, почему отклоняете.")
    return "COMMENT_WAITING"


async def save_rejection_comment(update: Update, context):
    """Сохраняем причину отклонения и уведомляем студента"""
    comment = update.message.text
    hw_id = context.user_data["homework_id"]

    # Получаем данные студента
    homework = session.query(Homework).filter(Homework.id == hw_id).first()

    if not homework or not homework.student.chat_id:
        await update.message.reply_text("⚠ Ошибка! Не удалось найти chat_id студента.")
        return ConversationHandler.END

    student_chat_id = homework.student.chat_id  # 👈 Получаем числовой `chat_id`
    module = context.user_data.get("module", "Неизвестный модуль")
    topic = context.user_data.get("topic", "Неизвестная тема")

    message_text = (
        f"❌ Домашка по модулю {module} "
        f"тема {topic} требует доработок.\n"
        f"💬 Комментарий ментора: {comment}"
    )

    # Отправляем студенту уведомление через `chat_id`
    await context.bot.send_message(chat_id=student_chat_id, text=message_text)

    await update.message.reply_text(f"✅ Отклонение отправлено студенту {homework.student.telegram}.")
    return await back_to_main_menu(update, context)





