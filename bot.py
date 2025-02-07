from telegram.ext import Application, CommandHandler, filters

from commands.admin_functions import request_broadcast_message, send_broadcast
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
                MessageHandler(filters.Regex("^(✅ Подтвердить|❌ Отклонить)$"), confirm_or_reject_payment)]
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

    application.add_handler(broadcast_handler)


    application.add_handler(MessageHandler(filters.Regex(r"^(Принять|Отклонить) \d+$"), confirm_or_reject_payment))
    application.add_handler(MessageHandler(filters.Regex("^(✅ Подтвердить|❌ Отклонить)$"), confirm_or_reject_payment))

    application.add_handler(payment_handler)
    application.add_handler(homework_handler)
    application.add_handler(homework_submission_handler)
    application.add_handler(CommandHandler("start", start_command))
    application.run_polling()

if __name__ == "__main__":
    main()
