import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ConversationHandler, ContextTypes

from commands.base_function import back_to_main_menu
from commands.states import CURATOR_DIRECTION_SELECTION, CURATOR_CONFIRMATION
from data_base.db import session
from data_base.models import Student, Mentor
from data_base.operations import get_student_by_fio_or_telegram

logger = logging.getLogger(__name__)

# ID пользователя для уведомлений (из переменной окружения)
NOTIFICATION_USER_ID = int(os.getenv('NOTIFICATION_BOT_USER_ID', '0'))


async def request_curator_assignment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс запроса назначения куратора"""
    student_telegram = f"@{update.message.from_user.username}"
    student = get_student_by_fio_or_telegram(student_telegram)

    if not student:
        await update.message.reply_text("❌ Вы не зарегистрированы как студент!")
        return ConversationHandler.END

    # Проверяем, что студент фуллстек
    if not student.training_type or student.training_type.strip().lower() != "фуллстек":
        await update.message.reply_text("❌ Эта функция доступна только для студентов направления 'Фуллстек'.")
        return ConversationHandler.END

    # Получаем текущих кураторов
    manual_mentor = session.query(Mentor).get(student.mentor_id) if student.mentor_id else None
    auto_mentor = session.query(Mentor).get(student.auto_mentor_id) if student.auto_mentor_id else None

    # Проверяем, нужен ли куратор
    if manual_mentor and auto_mentor:
        await update.message.reply_text("✅ У вас уже назначены кураторы по всем направлениям!")
        return ConversationHandler.END

    # Показываем сообщение о необходимости куратора
    message = (
        "👨‍🏫 Куратор необходим для сдачи и проверки домашних заданий.\n\n"
        "Выберите направление, по которому хотите запросить куратора:"
    )

    # Создаем кнопки для выбора направления
    keyboard_buttons = []
    
    if not manual_mentor:
        keyboard_buttons.append([KeyboardButton("💼 Ручное тестирование")])
    
    if not auto_mentor:
        keyboard_buttons.append([KeyboardButton("💻 Автотестирование")])
    
    keyboard_buttons.append([KeyboardButton("🔙 В главное меню")])
    
    keyboard = ReplyKeyboardMarkup(keyboard_buttons, resize_keyboard=True)
    
    await update.message.reply_text(message, reply_markup=keyboard)
    return CURATOR_DIRECTION_SELECTION


async def select_curator_direction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор направления для запроса куратора"""
    message_text = update.message.text
    
    if message_text == "🔙 В главное меню":
        await back_to_main_menu(update, context)
        return ConversationHandler.END
    
    student_telegram = f"@{update.message.from_user.username}"
    student = get_student_by_fio_or_telegram(student_telegram)
    
    if not student:
        await update.message.reply_text("❌ Ошибка: студент не найден!")
        return ConversationHandler.END

    # Сохраняем выбранное направление
    if message_text == "💼 Ручное тестирование":
        context.user_data["requested_direction"] = "Ручное тестирование"
        direction_name = "ручному тестированию"
    elif message_text == "💻 Автотестирование":
        context.user_data["requested_direction"] = "Автотестирование"
        direction_name = "автотестированию"
    else:
        await update.message.reply_text("❌ Пожалуйста, выберите одно из предложенных направлений.")
        return CURATOR_DIRECTION_SELECTION

    confirmation_message = (
        f"📋 Запрос куратора по {direction_name}\n\n"
        f"Отправить запрос на назначение куратора?"
    )

    keyboard = ReplyKeyboardMarkup([
        [KeyboardButton("✅ Да, отправить запрос")],
        [KeyboardButton("❌ Отменить")],
        [KeyboardButton("🔙 В главное меню")]
    ], resize_keyboard=True)

    await update.message.reply_text(confirmation_message, reply_markup=keyboard)
    return CURATOR_CONFIRMATION


async def confirm_curator_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждает и отправляет запрос на назначение куратора"""
    message_text = update.message.text
    
    if message_text == "🔙 В главное меню":
        await back_to_main_menu(update, context)
        return ConversationHandler.END
    
    if message_text == "❌ Отменить":
        await update.message.reply_text("❌ Запрос отменен.")
        await back_to_main_menu(update, context)
        return ConversationHandler.END
    
    if message_text != "✅ Да, отправить запрос":
        await update.message.reply_text("❌ Пожалуйста, выберите одно из предложенных действий.")
        return CURATOR_CONFIRMATION

    student_telegram = f"@{update.message.from_user.username}"
    student = get_student_by_fio_or_telegram(student_telegram)
    
    if not student:
        await update.message.reply_text("❌ Ошибка: студент не найден!")
        return ConversationHandler.END

    requested_direction = context.user_data.get("requested_direction")
    
    if not requested_direction:
        await update.message.reply_text("❌ Ошибка: направление не выбрано!")
        return ConversationHandler.END

    try:
        # Отправляем уведомление в другой бот
        await send_curator_request_notification(context, student, requested_direction)
        
        await update.message.reply_text(
            f"✅ Запрос на назначение куратора по направлению '{requested_direction}' отправлен!\n"
            f"Администратор рассмотрит ваш запрос в ближайшее время."
        )
        
        logger.info(f"Curator request sent by student {student.telegram} for direction {requested_direction}")
        
    except Exception as e:
        logger.error(f"Error sending curator request notification: {e}")
        # Даже если уведомление не отправилось, сообщаем студенту что запрос принят
        await update.message.reply_text(
            f"✅ Запрос на назначение куратора по направлению '{requested_direction}' принят!\n"
            f"Администратор рассмотрит ваш запрос в ближайшее время."
        )
    
    await back_to_main_menu(update, context)
    return ConversationHandler.END


async def send_curator_request_notification(context: ContextTypes.DEFAULT_TYPE, student: Student, direction: str):
    """Отправляет уведомление о запросе куратора в другой бот"""
    try:
        # Получаем токен бота и ID пользователя из переменных окружения
        bot_token = os.getenv('NOTIFICATION_BOT_TOKEN')
        
        if not bot_token:
            logger.warning("NOTIFICATION_BOT_TOKEN not set, skipping notification")
            return
            
        if NOTIFICATION_USER_ID == 0:
            logger.warning("NOTIFICATION_BOT_USER_ID not set, skipping notification")
            return
        
        # Создаем сообщение для уведомления
        notification_message = (
            f"🔔 Запрос на назначение куратора\n\n"
            f"👤 Студент: {student.fio}\n"
            f"📱 Telegram: {student.telegram}\n"
            f"🎯 Направление: {direction}"
        )
        
        # Отправляем уведомление через API Telegram используя urllib
        import urllib.request
        import urllib.parse
        import json
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": NOTIFICATION_USER_ID,
            "text": notification_message,
            "parse_mode": "HTML"
        }
        
        # Преобразуем данные в JSON и отправляем POST запрос
        json_data = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(url, data=json_data, headers={'Content-Type': 'application/json'})
        
        with urllib.request.urlopen(req) as response:
            if response.getcode() == 200:
                logger.info(f"Curator request notification sent successfully to user {NOTIFICATION_USER_ID}")
            else:
                logger.error(f"Failed to send notification: {response.getcode()}")
                    
    except Exception as e:
        logger.error(f"Error in send_curator_request_notification: {e}")
        # Не поднимаем исключение, чтобы не прерывать основной процесс
        logger.warning("Notification failed, but continuing with the main process")


def check_curator_before_homework(student_telegram: str, training_type: str, direction: str = None) -> tuple[bool, str]:
    """
    Проверяет наличие куратора перед сдачей домашнего задания
    Возвращает (has_curator, message)
    
    Args:
        student_telegram: Telegram студента
        training_type: Тип обучения студента
        direction: Направление, по которому студент хочет сдать домашку (для фуллстеков)
                   Может быть "Ручное тестирование" или "Автотестирование"
    """
    student = get_student_by_fio_or_telegram(student_telegram)
    
    if not student:
        return False, "❌ Студент не найден!"
    
    if training_type.lower() == "фуллстек":
        manual_mentor = session.query(Mentor).get(student.mentor_id) if student.mentor_id else None
        auto_mentor = session.query(Mentor).get(student.auto_mentor_id) if student.auto_mentor_id else None
        
        # Если указано конкретное направление, проверяем только нужного куратора
        if direction:
            if direction == "Ручное тестирование":
                if not manual_mentor:
                    return False, (
                        "❌ У вас не назначен куратор по ручному тестированию!\n"
                        "Для сдачи домашних заданий необходимо запросить назначение куратора.\n"
                        "Используйте кнопку '👨‍🏫 Запросить назначение куратора' в главном меню."
                    )
                return True, "✅ Куратор назначен"
            elif direction == "Автотестирование":
                if not auto_mentor:
                    return False, (
                        "❌ У вас не назначен куратор по автотестированию!\n"
                        "Для сдачи домашних заданий необходимо запросить назначение куратора.\n"
                        "Используйте кнопку '👨‍🏫 Запросить назначение куратора' в главном меню."
                    )
                return True, "✅ Куратор назначен"
        
        # Если направление не указано, проверяем наличие хотя бы одного куратора
        if not manual_mentor and not auto_mentor:
            return False, (
                "❌ У вас не назначен ни один куратор!\n"
                "Для сдачи домашних заданий необходимо запросить назначение куратора.\n"
                "Используйте кнопку '👨‍🏫 Запросить назначение куратора' в главном меню."
            )
        
        return True, "✅ Куратор назначен"
    
    else:
        # Для других типов обучения проверяем основной куратор
        mentor = session.query(Mentor).get(student.mentor_id) if student.mentor_id else None
        
        if not mentor:
            return False, (
                "❌ У вас не назначен куратор!\n"
                "Для сдачи домашних заданий необходимо запросить назначение куратора.\n"
                "Обратитесь к администратору."
            )
        
        return True, "✅ Куратор назначен"
