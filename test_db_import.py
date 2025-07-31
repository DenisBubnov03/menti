#!/usr/bin/env python3
"""
Простой тест для проверки импорта из data_base.db
"""

def test_db_import():
    """Тестирует импорт из data_base.db"""
    print("🔍 Тестирование импорта из data_base.db...")
    
    try:
        # Проверяем, что файл существует
        import os
        if not os.path.exists('data_base/db.py'):
            print("❌ Файл data_base/db.py не найден")
            return False
        
        # Читаем содержимое файла
        with open('data_base/db.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        print("📄 Содержимое data_base/db.py:")
        print("=" * 50)
        print(content)
        print("=" * 50)
        
        # Проверяем наличие функций
        if 'def get_session():' not in content:
            print("❌ Функция get_session() не найдена в файле")
            return False
        
        if 'def close_session():' not in content:
            print("❌ Функция close_session() не найдена в файле")
            return False
        
        if '__all__' not in content:
            print("❌ __all__ не найден в файле")
            return False
        
        print("✅ Файл содержит все необходимые функции")
        
        # Пробуем импорт
        print("📦 Пробуем импорт...")
        from data_base.db import get_session, close_session, Session, Base, engine
        print("✅ Импорт успешен!")
        
        # Пробуем вызвать функции
        print("🔧 Тестируем функции...")
        session = get_session()
        print("✅ get_session() работает")
        close_session()
        print("✅ close_session() работает")
        
        return True
        
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False

if __name__ == "__main__":
    success = test_db_import()
    if success:
        print("\n✅ Тест пройден успешно!")
    else:
        print("\n❌ Тест провален!")
        exit(1) 