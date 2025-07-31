#!/usr/bin/env python3
"""
Скрипт для проверки данных в базе и диагностики проблем
"""

from data_base.db import get_session, close_session
from data_base.models import Student, Mentor
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_database_data():
    """Проверяет данные в базе и выводит диагностическую информацию"""
    session = get_session()
    
    try:
        logger.info("=== ПРОВЕРКА ДАННЫХ В БАЗЕ ===")
        
        # Проверяем студентов
        logger.info("\n--- СТУДЕНТЫ ---")
        students = session.query(Student).all()
        logger.info(f"Всего студентов: {len(students)}")
        
        for student in students:
            logger.info(f"ID: {student.id}, FIO: '{student.fio}', Telegram: '{student.telegram}', Chat ID: '{student.chat_id}'")
        
        # Проверяем менторов
        logger.info("\n--- МЕНТОРЫ ---")
        mentors = session.query(Mentor).all()
        logger.info(f"Всего менторов: {len(mentors)}")
        
        for mentor in mentors:
            logger.info(f"ID: {mentor.id}, Name: '{mentor.full_name}', Telegram: '{mentor.telegram}', Chat ID: '{mentor.chat_id}', Is Admin: {mentor.is_admin}")
        
        # Проверяем конкретные проблемы
        logger.info("\n--- ДИАГНОСТИКА ПРОБЛЕМ ---")
        
        # Студенты без username
        students_without_username = session.query(Student).filter(Student.telegram.is_(None)).all()
        logger.info(f"Студенты без Telegram username: {len(students_without_username)}")
        for student in students_without_username:
            logger.warning(f"Студент без username: ID={student.id}, FIO='{student.fio}'")
        
        # Студенты с пустым username
        students_empty_username = session.query(Student).filter(Student.telegram == "").all()
        logger.info(f"Студенты с пустым Telegram username: {len(students_empty_username)}")
        for student in students_empty_username:
            logger.warning(f"Студент с пустым username: ID={student.id}, FIO='{student.fio}'")
        
        # Студенты без @ в username
        students_without_at = session.query(Student).filter(
            Student.telegram.isnot(None),
            ~Student.telegram.startswith("@")
        ).all()
        logger.info(f"Студенты без @ в username: {len(students_without_at)}")
        for student in students_without_at:
            logger.warning(f"Студент без @: ID={student.id}, FIO='{student.fio}', Telegram='{student.telegram}'")
        
        # Менторы без @ в username
        mentors_without_at = session.query(Mentor).filter(
            Mentor.telegram.isnot(None),
            ~Mentor.telegram.startswith("@")
        ).all()
        logger.info(f"Менторы без @ в username: {len(mentors_without_at)}")
        for mentor in mentors_without_at:
            logger.warning(f"Ментор без @: ID={mentor.id}, Name='{mentor.full_name}', Telegram='{mentor.telegram}'")
        
        # Проверяем дубликаты username
        from sqlalchemy import func
        duplicate_usernames = session.query(Student.telegram, func.count(Student.id)).filter(
            Student.telegram.isnot(None)
        ).group_by(Student.telegram).having(func.count(Student.id) > 1).all()
        
        if duplicate_usernames:
            logger.warning(f"Дубликаты username: {len(duplicate_usernames)}")
            for username, count in duplicate_usernames:
                logger.warning(f"Username '{username}' встречается {count} раз")
        
        logger.info("\n=== ПРОВЕРКА ЗАВЕРШЕНА ===")
        
    except Exception as e:
        logger.error(f"Ошибка при проверке данных: {e}")
    finally:
        close_session()

def test_user_lookup(username):
    """Тестирует поиск пользователя по username"""
    session = get_session()
    
    try:
        logger.info(f"\n=== ТЕСТ ПОИСКА ПОЛЬЗОВАТЕЛЯ: '{username}' ===")
        
        # Ищем студента
        student = session.query(Student).filter(
            (Student.fio == username) | (Student.telegram == username)
        ).first()
        
        if student:
            logger.info(f"Студент найден: ID={student.id}, FIO='{student.fio}', Telegram='{student.telegram}'")
        else:
            logger.warning(f"Студент не найден для username: '{username}'")
        
        # Ищем ментора
        mentor = session.query(Mentor).filter(Mentor.telegram == username).first()
        
        if mentor:
            logger.info(f"Ментор найден: ID={mentor.id}, Name='{mentor.full_name}', Telegram='{mentor.telegram}', Is Admin: {mentor.is_admin}")
        else:
            logger.info(f"Ментор не найден для username: '{username}'")
        
        # Проверяем админа
        admin_mentor = session.query(Mentor).filter(
            Mentor.telegram == username,
            Mentor.is_admin == True
        ).first()
        
        if admin_mentor:
            logger.info(f"Админ найден: {admin_mentor.full_name}")
        else:
            logger.info(f"Админ не найден для username: '{username}'")
        
    except Exception as e:
        logger.error(f"Ошибка при тестировании поиска: {e}")
    finally:
        close_session()

if __name__ == "__main__":
    # Проверяем общие данные
    check_database_data()
    
    # Тестируем конкретные username (замените на реальные)
    test_usernames = ["@test_user", "@admin", "@mentor1"]
    for username in test_usernames:
        test_user_lookup(username) 