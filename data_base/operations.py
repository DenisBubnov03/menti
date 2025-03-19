from datetime import datetime
from decimal import Decimal

from data_base.db import session, Session
from data_base.models import Student, Mentor, Homework, Payment


def is_admin(username):
    """Проверяет, является ли пользователь админом"""
    mentor = session.query(Mentor).filter(Mentor.telegram == str(username)).first()
    if mentor and mentor.is_admin:  # Проверяем поле is_admin
        return True
    return False

def is_mentor(telegram):
    mentor = session.query(Mentor).filter(Mentor.telegram == str(telegram)).first()
    return mentor is not None

def get_student_by_fio_or_telegram(value):
    """
    Ищет студента по ФИО или Telegram.
    """
    try:
        return session.query(Student).filter(
            (Student.fio == value) | (Student.telegram == value)
        ).first()
    except Exception as e:
        return None

async def get_pending_homework(mentor_telegram):
    """Функция получения списка домашних заданий для конкретного ментора"""
    mentor = session.query(Mentor).filter(Mentor.telegram == mentor_telegram).first()

    if not mentor:
        return None

    # Фильтруем домашки по mentor_id и статусу "ожидает проверки"
    homework_list = session.query(Homework).filter(
        Homework.mentor_id == mentor.id,
        Homework.status == "ожидает проверки"
    ).all()

    return homework_list

def approve_homework(hw_id):
    """Обновляет статус домашки на "принято" в БД"""
    hw = session.query(Homework).filter(Homework.id == hw_id).first()
    if hw:
        hw.status = "принято"
        session.commit()


def update_homework_status(hw_id, comment):
    """Обновляет статус домашки на 'отклонено' и сохраняет комментарий"""
    homework = session.query(Homework).filter(Homework.id == hw_id).first()
    if homework:
        homework.status = "отклонено"
        homework.comment = comment  # Добавляем комментарий
        session.commit()
        return homework.student.telegram  # Возвращаем Telegram студента
    return None



def get_all_mentors():
    """Возвращает список всех менторов"""
    return session.query(Mentor).all()


def get_mentor_chat_id(mentor_username):
    """Возвращает chat_id ментора по его Telegram username"""
    mentor = session.query(Mentor).filter(Mentor.telegram == mentor_username).first()

    if not mentor:
        return None

    return mentor.chat_id

def update_student_payment(student_telegram, amount, mentor_telegram, comment="Доплата"):
    """Добавляет платеж студента в таблицу payments и обновляет сумму в students"""
    student = session.query(Student).filter(Student.telegram == student_telegram).first()
    mentor = session.query(Mentor).filter(Mentor.telegram == mentor_telegram).first()

    if not student:
        raise ValueError("❌ Ошибка: студент не найден в базе.")
    if not mentor:
        raise ValueError("❌ Ошибка: ментор не найден в базе.")
    if amount <= 0:
        raise ValueError("❌ Ошибка: сумма платежа должна быть больше 0.")

    try:
        # ✅ Проверяем текущие оплаты студента (приводим к Decimal)
        total_paid = session.query(Payment.amount).filter(Payment.student_id == student.id).all()
        total_paid = sum(Decimal(str(p[0])) for p in total_paid) if total_paid else Decimal("0")

        new_total_paid = total_paid + Decimal(str(amount))  # ✅ Приводим к Decimal

        # ❌ Ошибка, если платеж превышает `total_cost`
        if new_total_paid > student.total_cost:
            raise ValueError(
                f"❌ Ошибка: сумма всех платежей ({new_total_paid} руб.) "
                f"превышает стоимость обучения ({student.total_cost} руб.)."
            )

        # ✅ Создаем новый платеж
        new_payment = Payment(
            student_id=student.id,
            mentor_id=mentor.id,
            amount=Decimal(str(amount)),  # ✅ Приводим float к Decimal
            payment_date=datetime.now().date(),
            comment=comment
        )
        session.add(new_payment)

        # ✅ Обновляем `payment_amount` в `students`
        student.payment_amount = new_total_paid

        # ✅ Проверяем, полностью ли оплачен курс
        student.fully_paid = "Да" if new_total_paid >= student.total_cost else "Нет"

        session.commit()
        print(f"✅ DEBUG: Платёж {amount} руб. записан в payments!")
    except Exception as e:
        session.rollback()
        print(f"❌ DEBUG: Ошибка при записи платежа: {e}")
        raise


def get_all_students():
    """Возвращает список всех студентов из БД"""
    return session.query(Student).all()

def get_student_chat_id(student_telegram):
    """Возвращает chat_id студента по его username"""
    student = session.query(Student).filter(Student.telegram == student_telegram).first()
    return student.chat_id if student else None

def get_student_id(student_telegram):
    """Возвращает chat_id студента по его username"""
    student = session.query(Student).filter(Student.telegram == student_telegram).first()
    return student.id if student else None

def get_mentor_by_student(student_telegram):
    """
    Получает информацию о менторе студента по его Telegram-нику.
    :param student_telegram: Telegram студента (@username)
    :return: Объект ментора или None, если не найден.
    """
    student = session.query(Student).filter_by(telegram=student_telegram).first()

    if not student or not student.mentor_id:
        return None  # Если студент не найден или у него нет ментора

    mentor = session.query(Mentor).filter_by(id=student.mentor_id).first()
    return mentor

def get_student_by_id(student_id: int) -> Student:
    """
    Получает студента из базы данных по его ID.
    :param student_id: ID студента
    :return: Объект Student или None, если студент не найден
    """
    with Session() as session:  # Открываем сессию SQLAlchemy
        student = session.query(Student).filter_by(id=student_id).first()
        return student