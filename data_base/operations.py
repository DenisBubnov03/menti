from datetime import datetime

from data_base.db import session, Session
from data_base.models import Student, Mentor, Homework


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

def update_student_payment(student_telegram, amount):
    """Обновляет сумму оплаты студента, проверяя ограничения"""
    try:
        student = session.query(Student).filter(Student.telegram == student_telegram).first()
        if not student:
            raise ValueError(f"Студент {student_telegram} не найден!")

        new_payment = int(amount)
        if new_payment < 0:
            raise ValueError("Сумма не может быть отрицательной.")

        payment_date = datetime.today()

        # Проверяем, был ли платеж в этом же месяце
        # Проверяем, был ли платеж в этом месяце
        if student.extra_payment_date and student.extra_payment_date.strftime("%m.%Y") == payment_date.strftime(
                "%m.%Y"):
            # 🔹 Если уже был платёж в этом месяце → увеличиваем сумму и обновляем дату
            student.extra_payment_amount += new_payment
            student.extra_payment_date = payment_date  # 🔥 Теперь дата тоже обновляется!
        else:
            # 🔹 Если это первый платёж в новом месяце → записываем сумму и дату
            student.extra_payment_amount = new_payment
            student.extra_payment_date = payment_date

        # Обновляем общую сумму оплат
        updated_payment = (student.payment_amount or 0) + new_payment

        # Проверяем, не превышает ли оплата стоимость курса
        if updated_payment > (student.total_cost or 0):
            session.rollback()
            raise ValueError(
                f"Ошибка: общая сумма оплаты ({updated_payment:.2f} руб.) "
                f"превышает стоимость обучения ({student.total_cost:.2f} руб.)."
            )

        student.payment_amount = updated_payment
        student.fully_paid = "Да" if student.payment_amount >= student.total_cost else "Нет"

        session.commit()
        return True
    except Exception as e:
        session.rollback()
        raise RuntimeError(f"Ошибка обновления данных студента: {e}")


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