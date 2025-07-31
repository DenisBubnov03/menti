import asyncio
import tracemalloc
import threading
import logging

# Отключаем логи httpx и urllib3
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

from telegram.ext import Application, CommandHandler, filters, CallbackQueryHandler, MessageHandler, ConversationHandler

from commands.call_notifications import run_scheduler, show_mentor_calls
from commands.call_scheduling import request_call, schedule_call_date, schedule_call_time, handle_direction_choice
from commands.admin_functions import request_broadcast_message, send_broadcast, add_mentor_request, save_mentor_name, \
    save_mentor_tg, remove_mentor_request, remove_mentor, WAITING_MENTOR_TG_REMOVE, save_mentor_direction
from commands.new.handlers import start_topic_submission, select_topic, submit_topic_students
from commands.start_command import start_command, my_topics_and_links
from commands.homework_menti import *
from commands.homework_mentor import *
from commands.payment_menti import request_payment, forward_payment, request_commission_payment, \
    forward_commission_payment
from commands.payment_mentor import reject_payment, show_pending_payments, check_payment_by_id, confirm_payment
from commands.student_progress import request_student_progress, show_student_progress
from commands.states import *
from commands.get_new_topic import get_new_topic_entry, get_new_topic_direction, GET_TOPIC_DIRECTION
from commands.homework_notifications import schedule_homework_notifications, schedule_weekly_reports

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
        },
        fallbacks=[],
        allow_reentry=True  # ✅ Студент может снова зайти в оплату
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
            WAITING_MENTOR_TG_NEW: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_mentor_tg)],
            WAITING_MENTOR_DIRECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_mentor_direction)]
        },
        fallbacks=[MessageHandler(filters.Regex("^Отмена$"), lambda update, context: ConversationHandler.END)]
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
    payment_review_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💰 Платежи$"), show_pending_payments)],
        states={
            PAYMENT_CONFIRMATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, check_payment_by_id)
            ],
            "PAYMENT_DECISION": [
                MessageHandler(filters.Regex("^✅ Подтвердить платёж$"), confirm_payment),
                MessageHandler(filters.Regex("^❌ Отклонить платёж$"), reject_payment)
            ]
        },
        fallbacks=[],
        allow_reentry=True
    )
    commission_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💸 Выплата комиссии$"), request_commission_payment)],
        states={
            PAYMENT_WAITING: [MessageHandler(filters.ALL, forward_commission_payment)],
        },
        fallbacks=[],
        allow_reentry=True
    )
    submit_topic_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Text(["📌 Подтверждение сдачи темы"]), start_topic_submission)],
        states={
            SUBMIT_TOPIC_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_topic)],
            SUBMIT_TOPIC_STUDENTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_topic_students)],
        },
        fallbacks=[]
    )
    
    student_progress_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📊 Проверить успеваемость$"), request_student_progress)],
        states={
            STUDENT_PROGRESS_WAITING: [MessageHandler(filters.TEXT & ~filters.COMMAND, show_student_progress)]
        },
        fallbacks=[]
    )
    
    get_new_topic_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🆕 Получить новую тему$"), get_new_topic_entry)],
        states={
            GET_TOPIC_DIRECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_topic_direction)]
        },
        fallbacks=[]
    )

    application.add_handler(student_progress_handler)
    application.add_handler(submit_topic_handler)
    application.add_handler(get_new_topic_handler)

    application.add_handler(commission_handler)

    application.add_handler(payment_review_handler)
    application.add_handler(MessageHandler(filters.Regex("^📅 Записи на звонки$"), show_mentor_calls))
    application.add_handler(MessageHandler(filters.Regex("^💸 Выплата комиссии$"), request_commission_payment))
    application.add_handler(call_scheduling_handler)
    application.add_handler(remove_mentor_handler)
    application.add_handler(mentor_handler)
    application.add_handler(broadcast_handler)
    application.add_handler(payment_handler)
    application.add_handler(homework_handler)
    application.add_handler(homework_submission_handler)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("📜 Мои темы и ссылки"), my_topics_and_links))
    
    # # Запускаем планировщики уведомлений в отдельных потоках
    # def run_notification_scheduler():
    #     asyncio.run(schedule_homework_notifications(application.bot))
    #
    # def run_weekly_reports_scheduler():
    #     asyncio.run(schedule_weekly_reports(application.bot))
    #
    # # Запускаем планировщики в фоновых потоках
    # notification_thread = threading.Thread(target=run_notification_scheduler, daemon=True)
    # weekly_reports_thread = threading.Thread(target=run_weekly_reports_scheduler, daemon=True)
    #
    # notification_thread.start()
    # weekly_reports_thread.start()
    
    print("🚀 Бот запущен! Система уведомлений активирована.")
    application.run_polling()


if __name__ == "__main__":
    main()
