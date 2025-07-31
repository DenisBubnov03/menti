import logging
import os
from datetime import datetime

def setup_logging():
    """Настраивает логирование в файл и консоль"""
    
    # Создаем папку для логов, если её нет
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # Имя файла с текущей датой
    log_filename = f"logs/bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # Настраиваем форматирование
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Настраиваем корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Очищаем существующие обработчики
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Файловый обработчик
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Отключаем логи httpx и urllib3
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    # Отключаем логи SQLAlchemy (если нужно)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    print(f"📝 Логи будут записываться в файл: {log_filename}")
    
    return log_filename 