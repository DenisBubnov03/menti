#!/usr/bin/env python3
"""
Простой тест для проверки импортов без подключения к БД
"""

def test_basic_imports():
    """Тестирует базовые импорты без БД"""
    print("🔍 Тестирование базовых импортов...")
    
    try:
        # Тест импорта из utils.request_logger
        print("📦 Импорт из utils.request_logger...")
        from utils.request_logger import log_request, log_command, log_conversation_handler
        print("✅ utils.request_logger импортирован успешно")
        
        # Тест импорта из setup_logging
        print("📦 Импорт из setup_logging...")
        from setup_logging import setup_logging
        print("✅ setup_logging импортирован успешно")
        
        # Тест импорта из analyze_logs
        print("📦 Импорт из analyze_logs...")
        from analyze_logs import analyze_logs
        print("✅ analyze_logs импортирован успешно")
        
        print("\n🎉 Все базовые импорты работают корректно!")
        return True
        
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False

def test_syntax():
    """Тестирует синтаксис файлов без выполнения"""
    print("\n🔍 Тестирование синтаксиса файлов...")
    
    import ast
    import os
    
    files_to_test = [
        'data_base/db.py',
        'data_base/operations.py',
        'data_base/models.py',
        'utils/request_logger.py',
        'setup_logging.py',
        'analyze_logs.py',
        'commands/start_command.py',
        'commands/get_new_topic.py',
        'commands/new/handlers.py',
        'commands/homework_mentor.py'
    ]
    
    for file_path in files_to_test:
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                ast.parse(content)
                print(f"✅ {file_path} - синтаксис корректен")
            except SyntaxError as e:
                print(f"❌ {file_path} - ошибка синтаксиса: {e}")
                return False
            except Exception as e:
                print(f"❌ {file_path} - ошибка: {e}")
                return False
        else:
            print(f"⚠️ {file_path} - файл не найден")
    
    return True

if __name__ == "__main__":
    print("🚀 Запуск тестов...")
    
    success1 = test_basic_imports()
    success2 = test_syntax()
    
    if success1 and success2:
        print("\n✅ Все тесты пройдены успешно!")
    else:
        print("\n❌ Некоторые тесты провалены!")
        exit(1) 