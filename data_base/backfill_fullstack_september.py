from datetime import datetime, date
from sqlalchemy import text

from data_base.db import get_session
from data_base.models import Student


# Отображение полей AutoProgress -> человекочитаемое название для topic_auto
AUTO_FIELD_TO_LABEL = {
    "m2_exam_passed_date": "Сдача 2 модуля",
    "m3_exam_passed_date": "Сдача 3 модуля",
    "m4_topic_passed_date": "Сдача 4 модуля",
    "m5_topic_passed_date": "Сдача 5 модуля",
    "m6_topic_passed_date": "Сдача 6 модуля",
    "m7_topic_passed_date": "Сдача 7 модуля",
}

# Отображение полей ManualProgress -> человекочитаемое название для topic_manual
MANUAL_FIELD_TO_LABEL = {
    "m1_submission_date": "1 модуль",
    "m2_1_2_2_submission_date": "Тема 2.1 + 2.2",
    "m2_3_3_1_submission_date": "Тема 2.3 + 3.1",
    "m3_2_submission_date": "Тема 3.2",
    "m3_3_submission_date": "Тема 3.3",
    "m4_1_submission_date": "Тема 4.1",
    "m4_2_4_3_submission_date": "Тема 4.2 + 4.3",
    "m4_mock_exam_passed_date": "Мок экзамен 4 модуля",
}


def is_in_month(d: date, month: int, year: int) -> bool:
    try:
        return d is not None and isinstance(d, (date, datetime)) and d.month == month and d.year == year
    except Exception:
        return False


def main():
    # По умолчанию текущий год, сентябрь (9)
    today = datetime.now()
    target_month = int((os.getenv("BACKFILL_MONTH") or 9))
    target_year = int((os.getenv("BACKFILL_YEAR") or today.year))

    inserted = 0
    skipped = 0

    with get_session() as session:
        # Берём только фуллстек студентов
        students = (
            session.query(Student)
            .filter(Student.training_type.ilike("%Фулл%"))
            .all()
        )

        # Импортируем прогрессы после инициализации сессии, чтобы избежать циклов
        from data_base.models import AutoProgress, ManualProgress, Mentor

        for student in students:
            # AUTO
            auto: AutoProgress | None = session.query(AutoProgress).filter_by(student_id=student.id).first()
            if auto:
                for field, label in AUTO_FIELD_TO_LABEL.items():
                    if hasattr(auto, field):
                        dt = getattr(auto, field)
                        if dt and is_in_month(dt, target_month, target_year):
                            # mentor_id берём авто-ментора, иначе пропускаем
                            mentor_id = student.auto_mentor_id
                            if not mentor_id:
                                skipped += 1
                                continue
                            session.execute(
                                text(
                                    """
                                    INSERT INTO fullstack_topic_assignments (student_id, mentor_id, topic_manual, topic_auto, assigned_at)
                                    VALUES (:student_id, :mentor_id, NULL, :topic_auto, :assigned_at)
                                    ON CONFLICT DO NOTHING
                                    """
                                ),
                                {
                                    "student_id": student.id,
                                    "mentor_id": mentor_id,
                                    "topic_auto": label,
                                    "assigned_at": dt if isinstance(dt, datetime) else datetime(dt.year, dt.month, dt.day),
                                },
                            )
                            inserted += 1

            # MANUAL
            manual: ManualProgress | None = session.query(ManualProgress).filter_by(student_id=student.id).first()
            if manual:
                for field, label in MANUAL_FIELD_TO_LABEL.items():
                    if hasattr(manual, field):
                        dt = getattr(manual, field)
                        if dt and is_in_month(dt, target_month, target_year):
                            mentor_id = student.mentor_id
                            if not mentor_id:
                                skipped += 1
                                continue
                            session.execute(
                                text(
                                    """
                                    INSERT INTO fullstack_topic_assignments (student_id, mentor_id, topic_manual, topic_auto, assigned_at)
                                    VALUES (:student_id, :mentor_id, :topic_manual, NULL, :assigned_at)
                                    ON CONFLICT DO NOTHING
                                    """
                                ),
                                {
                                    "student_id": student.id,
                                    "mentor_id": mentor_id,
                                    "topic_manual": label,
                                    "assigned_at": dt if isinstance(dt, datetime) else datetime(dt.year, dt.month, dt.day),
                                },
                            )
                            inserted += 1

        session.commit()
        print(f"Inserted: {inserted}, skipped: {skipped}, month={target_month}, year={target_year}")


if __name__ == "__main__":
    import os
    main()

