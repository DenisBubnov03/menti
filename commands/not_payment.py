import asyncio
from datetime import datetime, timedelta
from telegram import Bot
from data_base.db import session
from data_base.operations import get_all_students
from data_base.models import Payment, Mentor
import os
from dotenv import load_dotenv
import logging

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
print(TELEGRAM_TOKEN)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/payment_debts.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# 🔇 Отключаем SQL-логи
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)



async def check_payment_debts():
    """Проверяет студентов с долгами и отсутствием платежей более 30 дней"""
    bot = Bot(token=TELEGRAM_TOKEN)
    students = get_all_students()
    today = datetime.today().date()
    missing_chat_ids = []
    no_payment_students = []
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    for student in students:
        if student.training_status.lower().strip() == "не учится":
            continue
        if not student.total_cost or not student.payment_amount:
            continue
        if student.payment_amount >= student.total_cost:
            continue

        # Получаем последний платёж
        last_payment = (
            session.query(Payment)
            .filter(Payment.student_id == student.id)
            .order_by(Payment.payment_date.desc())
            .first()
        )

        if not last_payment:
            logger.info(f"У студента {student.telegram} есть долг {student.total_cost - student.payment_amount}₽, но ни одного платежа в таблице payments — пропускаем.")

            continue

        if (today - last_payment.payment_date).days > 30:
            if not student.chat_id:
                missing_chat_ids.append(student.telegram)
                continue

            try:
                # await bot.send_message(
                #     chat_id=student.chat_id,
                #     text=(
                #         f"📢 Напоминание: вы ещё не закрыли оплату за обучение.\n"
                #         f"Прошло более месяца с последнего платежа — {last_payment.payment_date.strftime('%d.%m.%Y')}\n\n"
                #         f"Пожалуйста, внесите следующий платёж."
                #     )
                # )
                logger.info(f"Отправлено уведомление студенту {student.telegram} от {last_payment.payment_date}")
            except Exception as e:
                logger.error(f"Ошибка при отправке студенту {student.telegram}: {e}")

    if missing_chat_ids:
        admin_mentor = session.query(Mentor).get(1)
        if admin_mentor and admin_mentor.chat_id:
            try:
                text = "⚠ Студенты без chat_id:\n" + "\n".join(missing_chat_ids)
                await bot.send_message(chat_id=admin_mentor.chat_id, text=text)
            except Exception as e:
                logger.error(f"Ошибка при отправке списка без chat_id админу: {e}")

if __name__ == "__main__":
    asyncio.run(check_payment_debts())