import logging
from datetime import date, datetime
from data_base.db import session
from data_base.models import Student, ManualProgress, AutoProgress, Salary
from classes.salary_manager import SalaryManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_tasks_with_final_logic():
    logger.info("🛠 ЗАПУСК МИГРАЦИИ (Точный текстовый поиск + Фильтр по старту)...")

    manager = SalaryManager()
    date_fs_start = date(2025, 9, 1)   # Фуллстек: с 1 ноября
    date_others_start = date(2025, 12, 1) # Ручное/Авто: с 1 декабря
    end_period = date(2025, 12, 31)

    # Твои словари маппинга
    TOPIC_FIELD_MAPPING = {
        "1 модуль": "m1_submission_date",
        "Тема 2.1 + 2.2": "m2_1_2_2_submission_date",
        "Тема 2.3 + 3.1": "m2_3_3_1_submission_date",
        "Тема 3.2": "m3_2_submission_date",
        "Тема 3.3": "m3_3_submission_date",
        "Тема 4.1": "m4_1_submission_date",
        "Тема 4.2 + 4.3": "m4_2_4_3_submission_date",
        "Мок экзамен 4 модуля": "m4_mock_exam_passed_date",
    }

    AUTO_MODULE_FIELD_MAPPING = {
        "Сдача 2 модуля": "m2_exam_passed_date",
        "Сдача 3 модуля": "m3_exam_passed_date",
        "Сдача 4 модуля": "m4_topic_passed_date",
        "Сдача 5 модуля": "m5_topic_passed_date",
        "Сдача 6 модуля": "m6_topic_passed_date",
        "Сдача 7 модуля": "m7_topic_passed_date",
    }

    count = 0

    students = session.query(Student).all()
    for st in students:
        training_type = (st.training_type or "").lower()

        # 1. ОПРЕДЕЛЯЕМ ОТСЕЧКУ ПО ТИПУ ОБУЧЕНИЯ
        if "фуллстек" in training_type:
            cutoff_date = date_fs_start
        elif "ручное" in training_type or "авто" in training_type:
            cutoff_date = date_others_start
        else:
            continue

        # 2. ФИЛЬТР ПО ДАТЕ СТАРТА: игнорируем тех, кто пришел раньше периода миграции
        if st.start_date and st.start_date < cutoff_date:
            continue

        # 3. MANUAL PROGRESS
        mp = session.query(ManualProgress).filter_by(student_id=st.id).first()
        if mp:
            for text_label, date_field in TOPIC_FIELD_MAPPING.items():
                pass_date = getattr(mp, date_field)
                mentor_field = date_field.replace("submission_date", "mentor_id").replace("passed_date", "mentor_id")
                m_id = getattr(mp, mentor_field)

                if pass_date and cutoff_date <= pass_date <= end_period and m_id:
                    # Поиск дубля по точному названию темы и нику
                    exists = session.query(Salary).filter(
                        Salary.mentor_id == m_id,
                        Salary.comment.ilike(f"%Принял {text_label}%"),
                        Salary.comment.ilike(f"%{st.telegram}%")
                    ).first()

                    if not exists:
                        amt, comm_txt = manager._calculate_amount_manual(st, m_id, 1.0)
                        session.add(Salary(
                            payment_id=None,
                            mentor_id=m_id,
                            calculated_amount=amt,
                            is_paid=False,
                            date_calculated=datetime.combine(pass_date, datetime.min.time()),
                            comment=f"Принял {text_label} у {st.telegram}. {comm_txt}"
                        ))
                        count += 1

        # 4. AUTO PROGRESS
        ap = session.query(AutoProgress).filter_by(student_id=st.id).first()
        if ap:
            for text_label, date_field in AUTO_MODULE_FIELD_MAPPING.items():
                pass_date = getattr(ap, date_field)
                mentor_field = date_field.replace("passed_date", "mentor_id")
                m_id = getattr(ap, mentor_field)

                if pass_date and cutoff_date <= pass_date <= end_period and m_id:
                    exists = session.query(Salary).filter(
                        Salary.mentor_id == m_id,
                        Salary.comment.ilike(f"%{text_label}%"), # Для авто обычно "Сдача X модуля"
                        Salary.comment.ilike(f"%{st.telegram}%")
                    ).first()

                    if not exists:
                        amt, comm_txt = manager._calculate_amount_auto(st, m_id, 1.0)
                        session.add(Salary(
                            payment_id=None,
                            mentor_id=m_id,
                            calculated_amount=amt,
                            is_paid=False,
                            date_calculated=datetime.combine(pass_date, datetime.min.time()),
                            comment=f"Принял {text_label} у {st.telegram}. {comm_txt}"
                        ))
                        count += 1

    session.commit()
    logger.info(f"🏁 Миграция завершена. Создано записей: {count}")

if __name__ == "__main__":
    migrate_tasks_with_final_logic()