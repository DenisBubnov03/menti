from datetime import datetime
from decimal import Decimal

from data_base.db import session, Session
from data_base.models import Student, Mentor, Homework, Payment


def is_admin(username):
    """Проверяет, является ли пользователь админом"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"is_admin called with username: '{username}'")
    
    mentor = session.query(Mentor).filter(Mentor.telegram == str(username)).first()
    if mentor and mentor.is_admin:  # Проверяем поле is_admin
        logger.info(f"User is admin: {mentor.full_name}")
        return True
    logger.info(f"User is not admin")
    return False

def is_mentor(telegram):
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"is_mentor called with telegram: '{telegram}'")
    
    mentor = session.query(Mentor).filter(Mentor.telegram == str(telegram)).first()
    if mentor:
        logger.info(f"User is mentor: {mentor.full_name}")
    else:
        logger.info(f"User is not mentor")
    return mentor is not None

def get_student_by_fio_or_telegram(value):
    """
    Ищет студента по ФИО или Telegram.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"get_student_by_fio_or_telegram called with value: '{value}'")
    
    try:
        # Проверяем, что value не None и не пустая строка
        if not value:
            logger.warning(f"Empty value provided: '{value}'")
            return None
            
        # Ищем студента
        student = session.query(Student).filter(
            (Student.fio == value) | (Student.telegram == value)
        ).first()
        
        if student:
            logger.info(f"Student found: ID={student.id}, FIO='{student.fio}', Telegram='{student.telegram}'")
        else:
            logger.warning(f"No student found for value: '{value}'")
            
        return student
    except Exception as e:
        logger.error(f"Error in get_student_by_fio_or_telegram: {e}")
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

def update_student_payment(student_id, amount, mentor_id, comment="Доплата"):
    """Добавляет платеж студента в таблицу payments и обновляет сумму в students"""
    student = session.query(Student).filter(Student.id == student_id).first()
    mentor = session.query(Mentor).filter(Mentor.id == mentor_id).first()

    if not student:
        raise ValueError("❌ Ошибка: студент не найден в базе.")
    if not mentor:
        raise ValueError("❌ Ошибка: ментор не найден в базе.")
    if amount <= 0:
        raise ValueError("❌ Ошибка: сумма платежа должна быть больше 0.")

    try:
        current_paid = Decimal(student.payment_amount or 0)
        new_total_paid = current_paid + Decimal(str(amount))
        #
        # # ❌ Проверяем превышение стоимости
        # if new_total_paid > student.total_cost:
        #     raise ValueError(
        #         f"❌ Ошибка: сумма всех платежей ({new_total_paid} руб.) "
        #         f"превышает стоимость обучения ({student.total_cost} руб.)."
        #     )

        # ✅ Создаем новый платеж
        new_payment = Payment(
            student_id=student.id,
            mentor_id=mentor.id,
            amount=Decimal(str(amount)),
            payment_date=datetime.now().date(),
            comment=comment
        )
        session.add(new_payment)

        # ✅ Обновляем `payment_amount`
        student.payment_amount = new_total_paid

        # ✅ Обновляем статус оплаты
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

def get_mentor_by_direction(direction: str):
    """
    Возвращает ментора по направлению (например, 'Автотестирование').
    """
    return session.query(Mentor).filter_by(direction=direction).first()
