from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler
from aiogram import Bot, Dispatcher, types
import os
from commands.base_function import back_to_main_menu
from commands.homework_menti import *
from commands.homework_mentor import *
from commands.payment_menti import request_payment, forward_payment
from commands.payment_mentor import confirm_payment, reject_payment, confirm_or_reject_payment
from commands.states import *
from data_base.models import Mentor
from data_base.operations import is_mentor, get_student_by_fio_or_telegram
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import MessageHandler, ConversationHandler
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

async def start_command(update, context):
    message = update.message
    username = str(message.from_user.username)

    # Добавляем @, если его нет
    if not username.startswith("@"):
        username = "@" + username  # ← Переопределяем username

    chat_id = message.chat_id  # Получаем chat_id


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

# Состояния для ConversationHandler

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    homework_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📚 Домашние задания$"), homework_list)],
        states={
            HOMEWORK_WAITING: [
                MessageHandler(filters.Regex(r"^\d+$"), check_homework),  # Ввод ID
                MessageHandler(filters.Regex("^🔙 В главное меню$"), back_to_main_menu)  # Выход в главное меню
            ],
            "CHECKING": [
                MessageHandler(filters.Regex("^✅ Принять$"), accept_homework),
                MessageHandler(filters.Regex("^❌ Отклонить$"), reject_homework),
            ],
            "COMMENT_WAITING": [MessageHandler(filters.TEXT & ~filters.COMMAND, save_rejection_comment)]
        },
        fallbacks=[]
    )
    homework_submission_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📚 Отправить домашку$"), submit_homework)],
        states={
            HOMEWORK_SELECT_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_stack_type)],  # Новый шаг!
            HOMEWORK_MODULE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_topic)],
            HOMEWORK_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_mentor)],
            HOMEWORK_MENTOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, wait_for_homework)],
            HOMEWORK_MESSAGE: [MessageHandler(filters.ALL, save_and_forward_homework)],
        },
        fallbacks=[]
    )
    payment_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💳 Оплата за обучение$"), request_payment)],
        states={
            PAYMENT_WAITING: [MessageHandler(filters.ALL, forward_payment)],  # Ожидаем чек и сумму
            PAYMENT_CONFIRMATION: [
                MessageHandler(filters.Regex("^(✅ Подтвердить|❌ Отклонить)$"), confirm_or_reject_payment)]
        },
        fallbacks=[],
        allow_reentry=True  # ✅ Разрешаем повторный вход в оплату, если студент решит отправить новый чек
    )
    application.add_handler(MessageHandler(filters.Regex(r"^(Принять|Отклонить) \d+$"), confirm_or_reject_payment))
    application.add_handler(MessageHandler(filters.Regex("^(✅ Подтвердить|❌ Отклонить)$"), confirm_or_reject_payment))

    application.add_handler(payment_handler)
    application.add_handler(homework_handler)
    application.add_handler(homework_submission_handler)
    application.add_handler(CommandHandler("start", start_command))
    application.run_polling()

if __name__ == "__main__":
    main()
