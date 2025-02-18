import asyncio
import tracemalloc

from telegram.ext import Application, CommandHandler, filters, CallbackQueryHandler

from commands.call_notifications import run_scheduler
from commands.call_scheduling import request_call, schedule_call_date, schedule_call_time, handle_direction_choice
from commands.admin_functions import request_broadcast_message, send_broadcast, add_mentor_request, save_mentor_name, \
    save_mentor_tg, remove_mentor_request, remove_mentor, WAITING_MENTOR_TG_REMOVE
from commands.start_command import start_command
from commands.homework_menti import *
from commands.homework_mentor import *
from commands.payment_menti import request_payment, forward_payment
from commands.payment_mentor import confirm_or_reject_payment
from commands.states import *

from telegram.ext import MessageHandler, ConversationHandler
import os
from dotenv import load_dotenv

load_dotenv()
tracemalloc.start()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")


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
                MessageHandler(filters.Regex("^(✅ Подтвердить платеж|❌ Отклонить платеж)$"), confirm_or_reject_payment)]
        },
        fallbacks=[],
        allow_reentry=True  # ✅ Разрешаем повторный вход в оплату, если студент решит отправить новый чек
    )
    broadcast_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📢 Сделать рассылку$"), request_broadcast_message)],
        states={
            BROADCAST_WAITING: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_broadcast)]
        },
        fallbacks=[]
    )
    mentor_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Добавить ментора$"), add_mentor_request)],
        states={
            WAITING_MENTOR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_mentor_name)],
            WAITING_MENTOR_TG: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_mentor_tg)]
        },
        fallbacks=[]
    )
    remove_mentor_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🗑 Удалить ментора$"), remove_mentor_request)],
        states={
            WAITING_MENTOR_TG_REMOVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_mentor)]
        },
        fallbacks=[]
    )

    call_scheduling_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📅 Записаться на звонок$"), request_call)],
        states={
            CALL_SCHEDULE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_direction_choice)],
            CALL_SCHEDULE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, schedule_call_date)],
            CALL_SCHEDULE_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, schedule_call_time)],
            CALL_CONFIRMATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda update, context: ConversationHandler.END)],
        },
        fallbacks=[MessageHandler(filters.Regex("^Отмена$"), lambda update, context: ConversationHandler.END)]
    )

    application.add_handler(call_scheduling_handler)
    application.add_handler(remove_mentor_handler)
    application.add_handler(mentor_handler)
    application.add_handler(broadcast_handler)
    application.add_handler(MessageHandler(filters.Regex("^(✅ Подтвердить платеж|❌ Отклонить платеж)$"), confirm_or_reject_payment))
    application.add_handler(payment_handler)
    application.add_handler(homework_handler)
    application.add_handler(homework_submission_handler)
    application.add_handler(CommandHandler("start", start_command))
    application.run_polling()


if __name__ == "__main__":
    main()
