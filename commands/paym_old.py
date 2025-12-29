import os
import sys
from datetime import date, datetime

# Добавляем путь к корневой директории проекта, чтобы импорты работали
sys.path.append(os.getcwd())

from data_base.db import session
from data_base.models import Student, Payment, Salary
from classes.salary_manager import SalaryManager

def fix_legacy_payments_with_original_date():
    manager = SalaryManager()

    # Период проверки: Ноябрь и Декабрь 2025
    start_period = datetime(2025, 11, 1)
    end_period = datetime(2025, 12, 31, 23, 59, 59)
    legacy_cutoff = date(2025, 12, 1)

    print(f"🔍 Запуск фиксации дат. Период платежей: {start_period.date()} - {end_period.date()}")

    # 1. Берем подтвержденные платежи "Доплата" и "Комиссия" за указанный период
    payments = session.query(Payment).filter(
        Payment.status == "подтвержден",
        Payment.comment.in_(["Доплата", "Комиссия"]),
        Payment.payment_date >= start_period,
        Payment.payment_date <= end_period
    ).all()

    print(f"📊 Найдено подтвержденных платежей: {len(payments)}")

    processed_count = 0
    updated_dates_count = 0

    for payment in payments:
        student = session.query(Student).get(payment.student_id)
        if not student:
            continue

        # Проверка на Legacy: ученик не фуллстек и начал до 1 декабря
        is_legacy = (
                student.start_date and
                student.start_date < legacy_cutoff and
                (student.training_type or "").strip().lower() != "фуллстек"
        )

        if not is_legacy:
            continue

        # 2. Проверяем наличие записей в Salary по этому платежу
        existing_salaries = session.query(Salary).filter_by(payment_id=payment.id).all()

        if existing_salaries:
            # Если записи уже есть (как на твоем скрине), исправляем им дату на дату платежа
            for s in existing_salaries:
                # ВНИМАНИЕ: Используем date_calculated, как в твоей БД
                if s.date_calculated != payment.payment_date:
                    s.date_calculated = payment.payment_date
                    updated_dates_count += 1
            continue

        # 3. Если записей о начислениях вообще нет — создаем их
        print(f"⚙️ Создание начислений: {student.telegram} | Дата платежа: {payment.payment_date}")

        try:
            # handle_legacy_payment_universal создает записи Salary
            new_entries = manager.handle_legacy_payment_universal(
                session=session,
                payment_id=payment.id,
                student_id=payment.student_id,
                payment_amount=payment.amount,
                payment_type=payment.comment
            )

            # 4. Принудительно ставим дату из платежа всем созданным записям
            if new_entries:
                for entry in new_entries:
                    entry.date_calculated = payment.payment_date
                processed_count += 1

        except Exception as e:
            print(f"❌ Ошибка при обработке платежа {payment.id}: {e}")
            session.rollback()

    session.commit()
    print(f"\n✅ Результаты:")
    print(f"— Исправлено дат у существующих записей: {updated_dates_count}")
    print(f"— Создано новых начислений для платежей: {processed_count}")
    print("📅 Теперь все даты в Salary синхронизированы с payment_date.")


if __name__ == "__main__":
    fix_legacy_payments_with_original_date()