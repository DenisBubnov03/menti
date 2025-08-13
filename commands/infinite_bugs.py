import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ConversationHandler, ContextTypes

from commands.base_function import back_to_main_menu
from commands.rules_checker import check_rules_accepted
from commands.states import INFINITE_BUGS_CHAPTER, INFINITE_BUGS_TASK, INFINITE_BUGS_LINK
from data_base.db import session
from data_base.models import Student
from utils.request_logger import log_request, log_conversation_handler

logger = logging.getLogger(__name__)

INFINITE_BUGS_TASKS = {
    "Глава 1": {
        "Задание 1": "https://thankful-candy-c57.notion.site/1-1-24694f774aab80c7a760c8136e542367?source=copy_link",
        "Задание 2": "https://thankful-candy-c57.notion.site/1-2-24694f774aab80ab91a0df3a21abac30?source=copy_link",
        "Задание 3": "https://thankful-candy-c57.notion.site/1-3-24694f774aab80679969c5725b2bc7f8?source=copy_link",
        "Задание 4": "https://thankful-candy-c57.notion.site/1-4-24694f774aab80a2aebad23c1a5c0261?source=copy_link"
    },
    "Глава 2": {
        "Задание 1": "https://thankful-candy-c57.notion.site/2-1-24694f774aab803aa470d4c36b578e4c?source=copy_link",
        "Задание 2": "https://thankful-candy-c57.notion.site/2-2-24694f774aab80b4a1fbcc8684d8a145?source=copy_link"
    }
}

@log_request("infinite_bugs_entry")
@check_rules_accepted
async def infinite_bugs_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Входная точка для функционала 'Бесконечные баги'"""
    user_id = update.message.from_user.id
    student_telegram = f"@{update.message.from_user.username}"
    
    # Проверяем, что пользователь - студент
    student = session.query(Student).filter_by(telegram=student_telegram).first()
    if not student:
        await update.message.reply_text("❌ Вы не зарегистрированы как студент!")
        return ConversationHandler.END

    # Проверяем наличие прогресса в базе данных
    from data_base.models import ManualProgress, AutoProgress
    
    manual_progress = session.query(ManualProgress).filter_by(student_id=student.id).first()
    auto_progress = session.query(AutoProgress).filter_by(student_id=student.id).first()
    
    if not manual_progress and not auto_progress:
        await update.message.reply_text(
            "❌ У вас нет прогресса в обучении. Обратитесь к ментору для начала обучения!"
        )
        return ConversationHandler.END

    # Проверяем, получил ли студент нужный модуль в зависимости от типа обучения
    has_required_module = False
    training_type = student.training_type.strip().lower() if student.training_type else ""
    
    if manual_progress:
        # Для ручного тестирования проверяем m5_start_date
        if manual_progress.m5_start_date:
            has_required_module = True
    
    if auto_progress:
        # Для автотестирования проверяем m8_start_date
        if auto_progress.m8_start_date:
            has_required_module = True
    
    if not has_required_module:
        # Формируем сообщение в зависимости от типа обучения
        if "фуллстек" in training_type:
            message = (
                "❌ Функция 'Бесконечные баги' доступна только после получения 5 модуля по ручному тестированию "
                "ИЛИ 8 модуля по автотестированию!\n\n"
                "Продолжайте обучение и получите нужный модуль, чтобы открыть доступ к этой функции."
            )
        elif "ручн" in training_type:
            message = (
                "❌ Функция 'Бесконечные баги' доступна только после получения 5 модуля!\n\n"
                "Продолжайте обучение и получите 5 модуль, чтобы открыть доступ к этой функции."
            )
        elif "авто" in training_type:
            message = (
                "❌ Функция 'Бесконечные баги' доступна только после получения 8 модуля!\n\n"
                "Продолжайте обучение и получите 8 модуль, чтобы открыть доступ к этой функции."
            )
        else:
            message = (
                "❌ Функция 'Бесконечные баги' доступна только после получения 5 модуля по ручному тестированию "
                "ИЛИ 8 модуля по автотестированию!\n\n"
                "Продолжайте обучение и получите нужный модуль, чтобы открыть доступ к этой функции."
            )
        
        await update.message.reply_text(message)
        return ConversationHandler.END

    # Создаём клавиатуру с главами
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("Глава 1")], [KeyboardButton("Глава 2")], [KeyboardButton("🔙 В главное меню")]],
        resize_keyboard=True
    )
    
    await update.message.reply_text(
        "🐛 Бесконечные баги\n\n"
        "Выберите главу, в которой хотите найти баги:",
        reply_markup=keyboard
    )
    
    return INFINITE_BUGS_CHAPTER


@log_conversation_handler("select_chapter")
async def select_chapter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора главы"""
    user_input = update.message.text.strip()
    
    if user_input == "🔙 В главное меню":
        return await back_to_main_menu(update, context)
    
    if user_input not in INFINITE_BUGS_TASKS:
        await update.message.reply_text("❌ Выберите главу из списка!")
        return INFINITE_BUGS_CHAPTER
    
    # Сохраняем выбранную главу
    context.user_data["selected_chapter"] = user_input
    
    # Создаём клавиатуру с заданиями для выбранной главы
    tasks = list(INFINITE_BUGS_TASKS[user_input].keys())
    keyboard_buttons = [[KeyboardButton(task)] for task in tasks]
    keyboard_buttons.append([KeyboardButton("🔙 Назад к главам")])
    
    keyboard = ReplyKeyboardMarkup(keyboard_buttons, resize_keyboard=True)
    
    await update.message.reply_text(
        f"📖 {user_input}\n\n"
        f"Выберите задание:",
        reply_markup=keyboard
    )
    
    return INFINITE_BUGS_TASK


@log_conversation_handler("select_task")
async def select_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора задания"""
    user_input = update.message.text.strip()
    
    if user_input == "🔙 Назад к главам":
        # Возвращаемся к выбору главы
        keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("Глава 1")], [KeyboardButton("Глава 2")], [KeyboardButton("🔙 В главное меню")]],
            resize_keyboard=True
        )
        
        await update.message.reply_text(
            "🐛 Бесконечные баги\n\n"
            "Выберите главу, в которой хотите найти баги:",
            reply_markup=keyboard
        )
        return INFINITE_BUGS_CHAPTER
    
    selected_chapter = context.user_data.get("selected_chapter")
    if not selected_chapter or user_input not in INFINITE_BUGS_TASKS[selected_chapter]:
        await update.message.reply_text("❌ Выберите задание из списка!")
        return INFINITE_BUGS_TASK
    
    # Сохраняем выбранное задание
    context.user_data["selected_task"] = user_input
    
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("🔙 Назад к заданиям")]],
        resize_keyboard=True
    )
    
    await update.message.reply_text(
        f"📝 {selected_chapter} - {user_input}\n\n"
        f"Отправьте ссылку на ваш баг репорт:",
        reply_markup=keyboard
    )
    
    return INFINITE_BUGS_LINK


@log_conversation_handler("process_bug_report")
async def process_bug_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка отправленного баг репорта"""
    user_input = update.message.text.strip()
    
    if user_input == "🔙 Назад к заданиям":
        # Возвращаемся к выбору задания
        selected_chapter = context.user_data.get("selected_chapter")
        tasks = list(INFINITE_BUGS_TASKS[selected_chapter].keys())
        keyboard_buttons = [[KeyboardButton(task)] for task in tasks]
        keyboard_buttons.append([KeyboardButton("🔙 Назад к главам")])
        
        keyboard = ReplyKeyboardMarkup(keyboard_buttons, resize_keyboard=True)
        
        await update.message.reply_text(
            f"📖 {selected_chapter}\n\n"
            f"Выберите задание:",
            reply_markup=keyboard
        )
        return INFINITE_BUGS_TASK
    
    # Проверяем, что это похоже на ссылку
    if not (user_input.startswith('http') or user_input.startswith('https')):
        await update.message.reply_text(
            "❌ Пожалуйста, отправьте корректную ссылку на ваш баг репорт!"
        )
        return INFINITE_BUGS_LINK
    
    selected_chapter = context.user_data.get("selected_chapter")
    selected_task = context.user_data.get("selected_task")
    
    # Получаем ссылку для самопроверки
    check_link = INFINITE_BUGS_TASKS[selected_chapter][selected_task]
    
    await update.message.reply_text(
        f"✅ Спасибо за баг репорт!\n\n"
        f"📋 {selected_chapter} - {selected_task}\n\n"
        f"🔍 Вот ссылка для самопроверки:\n"
        f"{check_link}\n\n"
        f"Сравните ваши находки с нашим списком багов!",
        parse_mode="HTML"
    )
    
    # Очищаем данные контекста
    context.user_data.clear()
    
    return await back_to_main_menu(update, context) 