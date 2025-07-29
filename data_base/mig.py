from data_base.db import session
from data_base.models import Homework, ManualProgress, Student
from sqlalchemy import or_

TOPICS_ORDER = [
    ("Тема 1.4", "m1_homework", "m1_start_date", "m1_submission_date"),
    ("Тема 2.1", "m2_1_homework", "m2_1_start_date", "m2_1_2_2_submission_date"),
    ("Тема 2.3", "m2_3_homework", "m2_3_start_date", "m2_3_3_1_submission_date"),
    ("Тема 3.1", "m3_1_homework", "m3_1_start_date", "m2_3_3_1_submission_date"),
    ("Тема 3.2", "m3_2_homework", "m3_2_start_date", "m3_2_submission_date"),
    ("Тема 3.3", "m3_3_homework", "m3_3_start_date", "m3_3_submission_date"),
    ("Тема 4.5", "m4_5_homework", "m4_5_start_date", None),
]

homeworks = session.query(Homework).join(Student).filter(
    or_(
        Student.training_type.ilike("%Ручн%"),
        Student.training_type.ilike("%Фулл%")
    )
).order_by(Homework.created_at).all()

topic_indices = {t[0]: i for i, t in enumerate(TOPICS_ORDER)}

for hw in homeworks:
    student = hw.student
    if not student:
        continue
    progress = session.query(ManualProgress).filter_by(student_id=student.id).first()
    if not progress:
        progress = ManualProgress(student_id=student.id)
        session.add(progress)
    idx = topic_indices.get(hw.topic)
    if idx is not None and hw.status == "принято":
        for i in range(idx + 1):
            _, hw_field, date_field, submission_field = TOPICS_ORDER[i]
            if hw_field and hasattr(progress, hw_field):
                setattr(progress, hw_field, True)
            if date_field and hasattr(progress, date_field) and getattr(progress, date_field) is None and hw.created_at:
                setattr(progress, date_field, hw.created_at.date())
            if submission_field and hasattr(progress, submission_field) and getattr(progress, submission_field) is None and hw.created_at:
                setattr(progress, submission_field, hw.created_at.date())
        print(f"OK: {student.telegram} {hw.topic} — все предыдущие отмечены")
    else:
        print(f"SKIP: {student.telegram} {hw.topic} — не принята или нет в списке")
session.commit()
print("Миграция завершена!")