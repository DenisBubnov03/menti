import logging
from decimal import Decimal
from datetime import date
from sqlalchemy import text  # 🔥 Добавили нужный импорт
from data_base.db import session
from data_base.models import Student, Payment

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


def restore_missing_payments():
    logger.info("🛠 ЗАПУСК ВОССТАНОВЛЕНИЯ ПЛАТЕЖЕЙ...")

    # Оборачиваем строку в text()
    query = text("""
        SELECT s.id, s.fio, s.payment_amount, s.start_date, s.telegram
        FROM students s
        LEFT JOIN payments p ON s.id = p.student_id
        WHERE s.payment_amount > 0 AND p.id IS NULL
    """)

    # Теперь execute сработает правильно
    missing_data = session.execute(query).fetchall()

    if not missing_data:
        logger.info("✅ Все платежи в порядке, фантомов не найдено.")
        return

    restored_count = 0

    for row in missing_data:
        # В новых версиях SQLAlchemy к полям в row можно обращаться по именам или индексам
        s_id, fio, amount, start_date, telegram = row

        # Создаем подтвержденный платеж
        new_payment = Payment(
            student_id=s_id,
            amount=Decimal(str(amount)),
            payment_date=start_date or date.today(),
            status="подтвержден",
            comment=f"Системное восстановление: платеж из карточки @{telegram}"
        )

        session.add(new_payment)
        restored_count += 1
        logger.info(f"🆕 Восстановлен платеж для {fio} (@{telegram}) на сумму {amount} руб.")

    try:
        session.commit()
        logger.info(f"🏁 ИТОГО: Восстановлено {restored_count} платежей.")
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Ошибка при сохранении: {e}")


if __name__ == "__main__":
    restore_missing_payments()