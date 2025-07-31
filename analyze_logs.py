#!/usr/bin/env python3
"""
Скрипт для анализа логов запросов к боту
"""

import re
import os
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import argparse

def parse_log_line(line):
    """Парсит строку лога и извлекает информацию"""
    # Паттерны для разных типов логов
    patterns = {
        'request_start': r'🚀 ЗАПРОС НАЧАТ \| Функция: (.+?) \| Пользователь: (.+?) \(ID: (.+?)\) \| Чат: (.+?) \| Текст: (.+)',
        'request_success': r'✅ ЗАПРОС УСПЕШЕН \| Функция: (.+?) \| Пользователь: (.+?) \| Время выполнения: (.+?)с',
        'request_error': r'❌ ЗАПРОС ОШИБКА \| Функция: (.+?) \| Пользователь: (.+?) \| Ошибка: (.+?) \| Время выполнения: (.+?)с',
        'command_start': r'🎯 КОМАНДА НАЧАТА \| Команда: (.+?) \| Функция: (.+?) \| Пользователь: (.+?) \(ID: (.+?)\) \| Чат: (.+)',
        'command_success': r'✅ КОМАНДА УСПЕШНА \| Команда: (.+?) \| Функция: (.+?) \| Пользователь: (.+?) \| Время выполнения: (.+?)с',
        'command_error': r'❌ КОМАНДА ОШИБКА \| Команда: (.+?) \| Функция: (.+?) \| Пользователь: (.+?) \| Ошибка: (.+?) \| Время выполнения: (.+?)с',
        'conversation_start': r'💬 РАЗГОВОР ОБРАБОТКА \| Обработчик: (.+?) \| Состояние: (.+?) \| Пользователь: (.+?) \(ID: (.+?)\) \| Текст: (.+)',
        'conversation_success': r'✅ РАЗГОВОР УСПЕШЕН \| Обработчик: (.+?) \| Состояние: (.+?) \| Пользователь: (.+?) \| Время выполнения: (.+?)с',
        'conversation_error': r'❌ РАЗГОВОР ОШИБКА \| Обработчик: (.+?) \| Состояние: (.+?) \| Пользователь: (.+?) \| Ошибка: (.+?) \| Время выполнения: (.+?)с'
    }
    
    for log_type, pattern in patterns.items():
        match = re.match(pattern, line)
        if match:
            return {
                'type': log_type,
                'data': match.groups(),
                'raw_line': line
            }
    
    return None

def analyze_logs(log_file_path):
    """Анализирует логи и создает отчет"""
    
    if not os.path.exists(log_file_path):
        print(f"❌ Файл логов не найден: {log_file_path}")
        return
    
    print(f"📊 Анализ логов: {log_file_path}")
    print("=" * 80)
    
    # Статистика
    stats = {
        'total_requests': 0,
        'successful_requests': 0,
        'failed_requests': 0,
        'total_commands': 0,
        'successful_commands': 0,
        'failed_commands': 0,
        'total_conversations': 0,
        'successful_conversations': 0,
        'failed_conversations': 0,
        'users': set(),
        'functions': Counter(),
        'errors': Counter(),
        'execution_times': []
    }
    
    # Данные для анализа
    requests_data = []
    commands_data = []
    conversations_data = []
    
    with open(log_file_path, 'r', encoding='utf-8') as f:
        for line in f:
            parsed = parse_log_line(line.strip())
            if not parsed:
                continue
            
            log_type = parsed['type']
            data = parsed['data']
            
            if log_type == 'request_start':
                stats['total_requests'] += 1
                stats['users'].add(data[1])  # username
                stats['functions'][data[0]] += 1  # function name
                requests_data.append({
                    'function': data[0],
                    'user': data[1],
                    'user_id': data[2],
                    'chat_id': data[3],
                    'text': data[4],
                    'status': 'pending'
                })
                
            elif log_type == 'request_success':
                stats['successful_requests'] += 1
                execution_time = float(data[2])
                stats['execution_times'].append(execution_time)
                
                # Находим соответствующий запрос
                for req in requests_data:
                    if req['function'] == data[0] and req['user'] == data[1]:
                        req['status'] = 'success'
                        req['execution_time'] = execution_time
                        break
                        
            elif log_type == 'request_error':
                stats['failed_requests'] += 1
                execution_time = float(data[3])
                error_msg = data[2]
                stats['errors'][error_msg] += 1
                
                # Находим соответствующий запрос
                for req in requests_data:
                    if req['function'] == data[0] and req['user'] == data[1]:
                        req['status'] = 'error'
                        req['execution_time'] = execution_time
                        req['error'] = error_msg
                        break
                        
            elif log_type == 'command_start':
                stats['total_commands'] += 1
                commands_data.append({
                    'command': data[0],
                    'function': data[1],
                    'user': data[2],
                    'user_id': data[3],
                    'chat_id': data[4],
                    'status': 'pending'
                })
                
            elif log_type == 'command_success':
                stats['successful_commands'] += 1
                execution_time = float(data[3])
                
                # Находим соответствующую команду
                for cmd in commands_data:
                    if cmd['command'] == data[0] and cmd['user'] == data[2]:
                        cmd['status'] = 'success'
                        cmd['execution_time'] = execution_time
                        break
                        
            elif log_type == 'command_error':
                stats['failed_commands'] += 1
                execution_time = float(data[4])
                error_msg = data[3]
                stats['errors'][error_msg] += 1
                
                # Находим соответствующую команду
                for cmd in commands_data:
                    if cmd['command'] == data[0] and cmd['user'] == data[2]:
                        cmd['status'] = 'error'
                        cmd['execution_time'] = execution_time
                        cmd['error'] = error_msg
                        break
                        
            elif log_type == 'conversation_start':
                stats['total_conversations'] += 1
                conversations_data.append({
                    'handler': data[0],
                    'state': data[1],
                    'user': data[2],
                    'user_id': data[3],
                    'text': data[4],
                    'status': 'pending'
                })
                
            elif log_type == 'conversation_success':
                stats['successful_conversations'] += 1
                execution_time = float(data[3])
                
                # Находим соответствующий разговор
                for conv in conversations_data:
                    if conv['handler'] == data[0] and conv['user'] == data[2]:
                        conv['status'] = 'success'
                        conv['execution_time'] = execution_time
                        break
                        
            elif log_type == 'conversation_error':
                stats['failed_conversations'] += 1
                execution_time = float(data[4])
                error_msg = data[3]
                stats['errors'][error_msg] += 1
                
                # Находим соответствующий разговор
                for conv in conversations_data:
                    if conv['handler'] == data[0] and conv['user'] == data[2]:
                        conv['status'] = 'error'
                        conv['execution_time'] = execution_time
                        conv['error'] = error_msg
                        break
    
    # Выводим общую статистику
    print("📈 ОБЩАЯ СТАТИСТИКА:")
    print(f"   Всего запросов: {stats['total_requests']}")
    print(f"   Успешных запросов: {stats['successful_requests']}")
    print(f"   Ошибок запросов: {stats['failed_requests']}")
    print(f"   Успешность запросов: {(stats['successful_requests']/stats['total_requests']*100):.1f}%" if stats['total_requests'] > 0 else "   Успешность запросов: N/A")
    
    print(f"\n   Всего команд: {stats['total_commands']}")
    print(f"   Успешных команд: {stats['successful_commands']}")
    print(f"   Ошибок команд: {stats['failed_commands']}")
    print(f"   Успешность команд: {(stats['successful_commands']/stats['total_commands']*100):.1f}%" if stats['total_commands'] > 0 else "   Успешность команд: N/A")
    
    print(f"\n   Всего разговоров: {stats['total_conversations']}")
    print(f"   Успешных разговоров: {stats['successful_conversations']}")
    print(f"   Ошибок разговоров: {stats['failed_conversations']}")
    print(f"   Успешность разговоров: {(stats['successful_conversations']/stats['total_conversations']*100):.1f}%" if stats['total_conversations'] > 0 else "   Успешность разговоров: N/A")
    
    print(f"\n   Уникальных пользователей: {len(stats['users'])}")
    
    # Статистика по функциям
    print("\n🔧 СТАТИСТИКА ПО ФУНКЦИЯМ:")
    for func, count in stats['functions'].most_common(10):
        print(f"   {func}: {count} вызовов")
    
    # Статистика по ошибкам
    if stats['errors']:
        print("\n❌ СТАТИСТИКА ПО ОШИБКАМ:")
        for error, count in stats['errors'].most_common(5):
            print(f"   {error}: {count} раз")
    
    # Время выполнения
    if stats['execution_times']:
        avg_time = sum(stats['execution_times']) / len(stats['execution_times'])
        max_time = max(stats['execution_times'])
        min_time = min(stats['execution_times'])
        print(f"\n⏱ ВРЕМЯ ВЫПОЛНЕНИЯ:")
        print(f"   Среднее время: {avg_time:.2f}с")
        print(f"   Максимальное время: {max_time:.2f}с")
        print(f"   Минимальное время: {min_time:.2f}с")
    
    # Последние ошибки
    print("\n🚨 ПОСЛЕДНИЕ ОШИБКИ:")
    error_count = 0
    for req in requests_data:
        if req.get('status') == 'error' and error_count < 5:
            print(f"   {req['function']} - {req['user']}: {req.get('error', 'Unknown error')}")
            error_count += 1
    
    for cmd in commands_data:
        if cmd.get('status') == 'error' and error_count < 5:
            print(f"   {cmd['command']} - {cmd['user']}: {cmd.get('error', 'Unknown error')}")
            error_count += 1
    
    for conv in conversations_data:
        if conv.get('status') == 'error' and error_count < 5:
            print(f"   {conv['handler']} - {conv['user']}: {conv.get('error', 'Unknown error')}")
            error_count += 1

def main():
    parser = argparse.ArgumentParser(description='Анализ логов бота')
    parser.add_argument('--log-file', '-f', help='Путь к файлу логов')
    parser.add_argument('--latest', '-l', action='store_true', help='Анализировать самый свежий файл логов')
    
    args = parser.parse_args()
    
    if args.latest:
        # Находим самый свежий файл логов
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            print("❌ Папка logs не найдена")
            return
        
        log_files = [f for f in os.listdir(log_dir) if f.startswith('bot_') and f.endswith('.log')]
        if not log_files:
            print("❌ Файлы логов не найдены")
            return
        
        latest_log = max(log_files, key=lambda x: os.path.getctime(os.path.join(log_dir, x)))
        log_file_path = os.path.join(log_dir, latest_log)
        print(f"📁 Анализируем самый свежий файл: {latest_log}")
        
    elif args.log_file:
        log_file_path = args.log_file
    else:
        # По умолчанию ищем самый свежий файл
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            print("❌ Папка logs не найдена")
            return
        
        log_files = [f for f in os.listdir(log_dir) if f.startswith('bot_') and f.endswith('.log')]
        if not log_files:
            print("❌ Файлы логов не найдены")
            return
        
        latest_log = max(log_files, key=lambda x: os.path.getctime(os.path.join(log_dir, x)))
        log_file_path = os.path.join(log_dir, latest_log)
        print(f"📁 Анализируем самый свежий файл: {latest_log}")
    
    analyze_logs(log_file_path)

if __name__ == "__main__":
    main() 