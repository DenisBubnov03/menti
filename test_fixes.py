#!/usr/bin/env python3
"""
Скрипт для тестирования исправлений транзакций
"""

from setup_logging import setup_logging
from data_base.operations import is_admin, is_mentor, get_student_by_fio_or_telegram
import logging

def test_operations():
    """Тестирует основные операции с правильным управлением сессиями"""
    logger = logging.getLogger(__name__)
    
    logger.info("=== ТЕСТИРОВАНИЕ ОПЕРАЦИЙ ===")
    
    # Тестируем поиск админа
    logger.info("Тестируем is_admin...")
    try:
        result = is_admin("@test_admin")
        logger.info(f"is_admin result: {result}")
    except Exception as e:
        logger.error(f"Error in is_admin: {e}")
    
    # Тестируем поиск ментора
    logger.info("Тестируем is_mentor...")
    try:
        result = is_mentor("@test_mentor")
        logger.info(f"is_mentor result: {result}")
    except Exception as e:
        logger.error(f"Error in is_mentor: {e}")
    
    # Тестируем поиск студента
    logger.info("Тестируем get_student_by_fio_or_telegram...")
    try:
        result = get_student_by_fio_or_telegram("@test_student")
        logger.info(f"get_student result: {result is not None}")
    except Exception as e:
        logger.error(f"Error in get_student_by_fio_or_telegram: {e}")
    
    logger.info("=== ТЕСТИРОВАНИЕ ЗАВЕРШЕНО ===")

if __name__ == "__main__":
    # Настраиваем логирование
    setup_logging()
    
    # Запускаем тесты
    test_operations() 