from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import MessageHandler, ConversationHandler

from commands.base_function import back_to_main_menu
from data_base.db import session

from commands.states import HOMEWORK_MODULE, HOMEWORK_TOPIC, HOMEWORK_MENTOR, HOMEWORK_MESSAGE, HOMEWORK_SELECT_TYPE, \
    CALL_SCHEDULE
from data_base.models import Homework, Student, Mentor
from data_base.operations import get_pending_homework, approve_homework, \
    get_student_by_fio_or_telegram, get_all_mentors, get_mentor_chat_id, get_mentor_by_direction

# Импорт для AI проверки темы 4.5
import asyncio
from commands.ai_check_45 import review_45_async, AICheckRepository, extract_text


async def get_submission_payload(submission_id: int) -> dict:
    """Получает данные сдачи для AI проверки"""
    homework = session.query(Homework).filter_by(id=submission_id).first()
    if not homework:
        raise ValueError(f"Сдача {submission_id} не найдена")
    
    student = session.query(Student).filter_by(id=homework.student_id).first()
    mentor = session.query(Mentor).filter_by(id=homework.mentor_id).first()
    
    return {
        "submission_id": submission_id,
        "student_id": homework.student_id,
        "student_username": student.telegram if student else None,
        "mentor_id": homework.mentor_id,
        "topic": homework.topic,
        "module": homework.module,
        "filename": "homework.txt",  # Будет переопределено
        "file_bytes": b"",  # Будет переопределено
    }


async def notify_student(student_id: int, message: str, bot=None):
    """Отправляет уведомление студенту"""
    student = session.query(Student).filter_by(id=student_id).first()
    if student and student.chat_id and bot:
        try:
            await bot.send_message(chat_id=student.chat_id, text=message)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Ошибка отправки уведомления студенту {student_id}: {e}")


async def notify_mentor(mentor_id: int, message: str, bot=None):
    """Отправляет уведомление ментору"""
    mentor = session.query(Mentor).filter_by(id=mentor_id).first()
    if mentor and mentor.chat_id and bot:
        try:
            await bot.send_message(chat_id=mentor.chat_id, text=message)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Ошибка отправки уведомления ментору {mentor_id}: {e}")


async def get_file_from_message(update: Update, context) -> tuple:
    """Извлекает файл из сообщения Telegram"""
    message = update.message
    
    if message.document:
        # Документ
        file = await context.bot.get_file(message.document.file_id)
        file_bytes = await file.download_as_bytearray()
        filename = message.document.file_name or "document"
        return filename, bytes(file_bytes)
    
    elif message.photo:
        # Фото
        file = await context.bot.get_file(message.photo[-1].file_id)
        file_bytes = await file.download_as_bytearray()
        filename = "photo.jpg"
        return filename, bytes(file_bytes)
    
    elif message.text:
        # Текст
        text_content = message.text.encode('utf-8')
        filename = "text.txt"
        return filename, text_content
    
    elif message.voice:
        # Голосовое сообщение
        file = await context.bot.get_file(message.voice.file_id)
        file_bytes = await file.download_as_bytearray()
        filename = "voice.ogg"
        return filename, bytes(file_bytes)
    
    else:
        # Неподдерживаемый тип
        raise ValueError("Неподдерживаемый тип файла")


MODULES_TOPICS = {
    "Ручное тестирование": {
        "Модуль 1": ["Тема 1.4", 'Отмена'],
        "Модуль 2": ["Тема 2.1", "Тема 2.3", 'Отмена'],
        "Модуль 3": ["Тема 3.1", "Тема 3.2", "Тема 3.3", 'Отмена'],
        "Модуль 4": ["Тема 4.5", 'Отмена'],
        "Модуль 5": ["Резюме/Легенда", "Отмена"],

        "Отмена": []
    },
    "Автотестирование": {
        "Модуль 1": ["Тема 1.1", "Тема 1.2", "Тема 1.3", 'Отмена'],
        "Модуль 2": ["Тема 2.1", "Тема 2.2", "Тема 2.3", "Тема 2.4", "Тема 2.5", "Тема 2.6", "Тема 2.7", "Экзамен 2", 'Отмена'],
        "Модуль 3": ["Тема 3.1", "Тема 3.2", "Тема 3.3", "Тема 3.4", "Тема 3.5", "Тема 3.6", "Экзамен 3", 'Отмена'],
        "Модуль 4": ["Тема 4.1", "Тема 4.2", "Тема 4.3", "Тема 4.4", "Тема 4.5", "Экзамен 4", 'Отмена'],
        "Модуль 5": ["Тема 5.1", "Тема 5.2", "Тема 5.3", "Тема 5.4", "Тема 5.5", "Тема 5.6", "Экзамен 5", 'Отмена'],
        "Отмена": []
    }
}


async def submit_homework(update: Update, context):
    """Студент начинает процесс сдачи домашки"""
    student_telegram = f"@{update.message.from_user.username}"
    student = get_student_by_fio_or_telegram(student_telegram)

    if not student:
        await update.message.reply_text("❌ Вы не зарегистрированы как студент!")
        return ConversationHandler.END

    context.user_data["student_id"] = student.id
    context.user_data["training_type"] = student.training_type  # ✅ Сохраняем направление

    # Если студент Фуллстек, даём ему выбор направления
    if student.training_type == "Фуллстек":
        keyboard = [
            [KeyboardButton("Ручное тестирование")],
            [KeyboardButton("Автотестирование")]
        ]
        await update.message.reply_text(
            "Выберите направление, по которому сдаёте домашку:",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
        return HOMEWORK_SELECT_TYPE

    # Если студент не фуллстек, сразу отправляем его на выбор модуля
    keyboard = [[KeyboardButton(mod)] for mod in MODULES_TOPICS[student.training_type].keys()]
    await update.message.reply_text(
        "📌 Выберите модуль:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )

    return HOMEWORK_MODULE  # ✅ Теперь студент НЕ выбирает направление после темы!



async def select_stack_type(update: Update, context):
    """Фуллстек-студент выбирает направление сдачи домашки."""
    direction_choice = update.message.text.strip()

    if direction_choice.lower() == "отмена":
        await back_to_main_menu(update, context)
        return await back_to_main_menu(update, context)

    if direction_choice not in ["Ручное тестирование", "Автотестирование"]:
        await update.message.reply_text("❌ Ошибка! Выберите направление из предложенных.")
        return HOMEWORK_SELECT_TYPE

    student_telegram = f"@{update.message.from_user.username}"
    student = get_student_by_fio_or_telegram(student_telegram)

    if not student:
        await update.message.reply_text("❌ Студент не найден.")
        return await back_to_main_menu(update, context)

    # Сохраняем направление
    context.user_data["training_type"] = direction_choice

    # Определяем ментора по направлению
    if direction_choice == "Ручное тестирование":
        context.user_data["mentor_id"] = 1  # manual_mentor
        context.user_data["mentor_telegram"] = session.query(Mentor).get(1).telegram if session.query(Mentor).get(1) else None
    else:  # Автотестирование
        context.user_data["mentor_id"] = getattr(student, 'auto_mentor_id', None)
        auto_mentor = session.query(Mentor).get(getattr(student, 'auto_mentor_id', None)) if getattr(student, 'auto_mentor_id', None) else None
        context.user_data["mentor_telegram"] = auto_mentor.telegram if auto_mentor else None

    # Показываем модули
    keyboard = [[KeyboardButton(mod)] for mod in MODULES_TOPICS[direction_choice].keys()]
    await update.message.reply_text(
        f"✅ Вы выбрали направление {direction_choice}. Теперь выберите модуль:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )

    return HOMEWORK_MODULE



async def choose_topic(update: Update, context):
    """Выбор темы из модуля"""
    module = update.message.text
    context.user_data["module"] = module  # Запоминаем модуль
    date_text = update.message.text.strip()
    if date_text.lower() == "отмена":
        await back_to_main_menu(update, context)  # Возврат в меню
        return ConversationHandler.END
    
    training_type = context.user_data.get("training_type")  # ✅ Берём уже сохранённое направление
    if not training_type or module not in MODULES_TOPICS.get(training_type, {}):
        await update.message.reply_text("❌ Ошибка! Такого модуля нет. Выберите из списка.")
        return HOMEWORK_MODULE

    # Получаем студента для проверки доступных тем
    student_telegram = f"@{update.message.from_user.username}"
    student = get_student_by_fio_or_telegram(student_telegram)
    if not student:
        await update.message.reply_text("❌ Вы не зарегистрированы как студент!")
        return ConversationHandler.END

    # Получаем доступные темы
    available_modules = get_available_topics(student.id, training_type)
    available_topics = available_modules.get(module, [])
    
    if not available_topics:
        await update.message.reply_text("❌ В этом модуле нет доступных тем для сдачи.")
        return HOMEWORK_MODULE

    keyboard = [[KeyboardButton(topic)] for topic in available_topics]

    await update.message.reply_text(
        "📌 Выберите тему:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )

    return HOMEWORK_TOPIC




async def choose_mentor(update: Update, context):
    """Определяет ментора для отправки домашки в зависимости от направления обучения."""
    student_telegram = f"@{update.message.from_user.username}"
    student = get_student_by_fio_or_telegram(student_telegram)
    date_text = update.message.text.strip()
    if date_text.lower() == "отмена":
        await back_to_main_menu(update, context)  # Возврат в меню
        return await back_to_main_menu(update, context)
    if not student:
        await update.message.reply_text("❌ Вы не зарегистрированы как студент!")
        return await back_to_main_menu(update, context)

    context.user_data["topic"] = update.message.text  # Запоминаем тему

    # ✅ Если студент НЕ фуллстэк, используем закреплённого ментора
    if student.training_type != "Фуллстек":
        mentor_id = student.mentor_id  # У студента уже есть закрепленный ментор
    else:
        # ✅ Если студент Фуллстек, используем выбранного ранее ментора
        mentor_id = context.user_data.get("mentor_id")

    mentor = session.query(Mentor).filter(Mentor.id == mentor_id).first()

    if not mentor:
        await update.message.reply_text("❌ Ошибка! Ваш ментор не найден.")
        return await back_to_main_menu(update, context)

    context.user_data["mentor_id"] = mentor.id
    context.user_data["mentor_telegram"] = mentor.telegram

    await update.message.reply_text(f"✅ Ваш ментор: {mentor.telegram}. Теперь отправьте домашнее задание.")
    return HOMEWORK_MESSAGE




async def wait_for_homework(update: Update, context):
    """Ждём, когда студент отправит сообщение с домашним заданием"""
    context.user_data["mentor"] = update.message.text  # Запоминаем ментора
    await update.message.reply_text("📩 Отправьте ваше домашнее задание (файл, фото, текст, голосовое и т.д.):")
    return HOMEWORK_MESSAGE

async def save_and_forward_homework(update: Update, context):
    """Сохранение и пересылка домашки"""
    student_telegram = f"@{update.message.from_user.username}"
    student = get_student_by_fio_or_telegram(student_telegram)
    mentor_id = context.user_data.get("mentor_id")
    if not student:
        await update.message.reply_text("❌ Вы не зарегистрированы как студент!")
        return ConversationHandler.END

    # ✅ Проверяем, есть ли module в context.user_data
    module = context.user_data.get("module")
    if not module:
        await update.message.reply_text("❌ Ошибка! Вы не выбрали модуль.")
        return HOMEWORK_MODULE

    topic = context.user_data.get("topic")
    mentor_telegram = context.user_data.get("mentor_telegram")
    
    # Локальный импорт для создания записи
    from data_base.models import Homework
    
    # Создаем запись в БД
    new_homework = Homework(
        student_id=student.id,
        mentor_id=mentor_id,
        module=module,
        topic=topic,
        status="ожидает проверки"
    )
    session.add(new_homework)

    # Обновляем прогресс: ставим True для соответствующего поля домашки
    from data_base.models import ManualProgress
    progress = session.query(ManualProgress).filter_by(student_id=student.id).first()
    PROGRESS_FIELD_MAPPING = {
        "Тема 1.4": "m1_homework",
        "Тема 2.1": "m2_1_homework",
        "Тема 2.3": "m2_3_homework",
        "Тема 3.1": "m3_1_homework",
        "Тема 3.2": "m3_2_homework",
        "Тема 3.3": "m3_3_homework",
        "Тема 4.5": "m4_5_homework",
    }
    field_name = PROGRESS_FIELD_MAPPING.get(topic)
    if progress and field_name and hasattr(progress, field_name):
        setattr(progress, field_name, True)
        session.commit()

    # ✅ Получаем chat_id ментора, если он отсутствует в context.user_data
    mentor_chat_id = context.user_data.get("chat_id")
    # ID домашки
    homework_id = new_homework.id

    if not mentor_chat_id:
        mentor = session.query(Mentor).filter(Mentor.telegram == mentor_telegram).first()
        if mentor:
            mentor_chat_id = mentor.chat_id
            context.user_data["chat_id"] = mentor_chat_id  # ✅ Сохраняем `mentor_chat_id`

    if not mentor_chat_id:
        await update.message.reply_text("❌ Ошибка! Не найден mentor_chat_id.")
        return ConversationHandler.END

    # 📝 Сообщение для ментора перед пересылкой
    mentor_text = f"📚 Ученик {student.fio} {student.telegram} прислал домашку по {module} / {topic}\n"
    mentor_text += f"📜 ID: {homework_id}\n"
    
    # Добавляем специальное уведомление для темы 4.5 после 2 попыток
    if topic == "Тема 4.5":
        from data_base.db import get_session
        with get_session() as db_session:
            from commands.ai_check_45 import TopicAttemptsRepository
            attempts_repo = TopicAttemptsRepository(db_session)
            attempts_info = attempts_repo.get_attempts(student.id, "Тема 4.5")
            if attempts_info["attempts_count"] >= 2:
                mentor_text += "⚠️ Исчерпаны попытки авто-проверки - требуется личная проверка\n"
    
    mentor_text += "✉ Следующее сообщение — сама домашка:"
    
    await context.bot.send_message(
        chat_id=mentor_chat_id,
        text=mentor_text
    )

    # ✅ Пересылаем сообщение студента
    await context.bot.forward_message(
        chat_id=mentor_chat_id,
        from_chat_id=update.message.chat_id,
        message_id=update.message.message_id
    )

    keyboard_buttons = [
        [KeyboardButton("🆕 Получить новую тему")],
        [KeyboardButton("🐛 Бесконечные баги")],
        [KeyboardButton("📚 Отправить домашку")],
        [KeyboardButton("📜 Мои темы и ссылки")],
        [KeyboardButton("📅 Записаться на звонок")],
        [KeyboardButton("💳 Оплата за обучение")],
        [KeyboardButton("💸 Выплата комиссии")],
    ]
    keyboard = ReplyKeyboardMarkup(
        keyboard=keyboard_buttons,
        resize_keyboard=True
    )
    # Разные сообщения для темы 4.5 и остальных тем
    if topic == "Тема 4.5":
        await update.message.reply_text("✅ Домашка отправлена на проверку!", reply_markup=keyboard)
    else:
        await update.message.reply_text("✅ Домашка отправлена ментору!", reply_markup=keyboard)
    
    # 🔄 Авто-проверка темы 4.5
    if topic == "Тема 4.5":
        try:
            # Проверяем попытки студента
            from data_base.db import get_session
            from commands.ai_check_45 import TopicAttemptsRepository
            
            with get_session() as db_session:
                attempts_repo = TopicAttemptsRepository(db_session)
                attempts_info = attempts_repo.get_attempts(student.id, "Тема 4.5")
            
            # Проверяем, нужно ли запускать авто-проверку
            current_attempt = attempts_info["attempts_count"]
            
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Тема 4.5: попыток {current_attempt}, завершена: {attempts_info['is_completed']}")
            
            if attempts_info["is_completed"]:
                await update.message.reply_text(
                    "🎉 Тема 4.5 уже завершена! Вы не можете сдавать её повторно.",
                    reply_markup=keyboard
                )
                return ConversationHandler.END
            elif current_attempt >= 2:
                # После 2 попыток переключаемся на обычную проверку ментором
                # Не запускаем авто-проверку, просто продолжаем обычный флоу
                logger.info(f"Тема 4.5: {current_attempt} попыток, переключаемся на ментора")
                
                # Уведомляем студента об исчерпании попыток
                await update.message.reply_text(
                    "⚠️ Вы исчерпали две попытки на самопроверку. Работа отправлена ментору для личной проверки.",
                    reply_markup=keyboard
                )
                
                # Уведомляем ментора
                mentor_message = (
                    f"Ученик {student.fio} {student.telegram} исчерпал 2 попытки авто-проверки по теме 4.5.\n"
                    f"Работа требует личной проверки.\n"
                    f"ID домашнего задания: {homework_id}"
                )
                await context.bot.send_message(chat_id=mentor_chat_id, text=mentor_message)
            else:
                # Меньше 2 попыток - запускаем авто-проверку
                logger.info(f"Тема 4.5: {current_attempt} попыток, запускаем авто-проверку")
                
                # Получаем файл из сообщения
                filename, file_bytes = await get_file_from_message(update, context)
                
                # Создаем функцию для получения данных сдачи с файлом
                async def get_submission_with_file(submission_id: int) -> dict:
                    payload = await get_submission_payload(submission_id)
                    payload["filename"] = filename
                    payload["file_bytes"] = file_bytes
                    return payload
                
                # Создаем функции уведомлений с ботом
                async def notify_student_with_bot(student_id: int, message: str):
                    await notify_student(student_id, message, context.bot)
                
                async def notify_mentor_with_bot(mentor_id: int, message: str):
                    await notify_mentor(mentor_id, message, context.bot)
                
                # Запускаем фоновую задачу авто-проверки
                asyncio.create_task(
                    review_45_async(
                        submission_id=homework_id,
                        extract_text_fn=extract_text,
                        get_submission_payload=get_submission_with_file,
                        repo=None,  # Будет создан внутри review_45_async
                        notify_student=notify_student_with_bot,
                        notify_mentor=notify_mentor_with_bot
                    )
                )
                
                logger.info(f"Запущена авто-проверка 4.5 для сдачи {homework_id}")
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Ошибка запуска авто-проверки 4.5 для сдачи {homework_id}: {e}")
            # Не прерываем основной флоу при ошибке авто-проверки
    
    return ConversationHandler.END


def get_available_topics(student_id: int, training_type: str) -> dict:
    """Получает доступные темы для студента на основе его прогресса"""
    from data_base.db import get_session
    from commands.ai_check_45 import TopicAttemptsRepository
    
    with get_session() as db_session:
        attempts_repo = TopicAttemptsRepository(db_session)
        available_modules = {}
        
        # Получаем все темы для направления
        all_topics = MODULES_TOPICS.get(training_type, {})
        
        for module, topics in all_topics.items():
            if module == "Отмена":
                continue
                
            available_topics = []
            for topic in topics:
                if topic == "Отмена":
                    continue
                    
                # Проверяем доступность темы 4.5
                if topic == "Тема 4.5":
                    attempts_info = attempts_repo.get_attempts(student_id, "Тема 4.5")
                    # Скрываем тему 4.5 только если она завершена (оценка >= 50)
                    # Тема остается доступной для всех попыток, включая 2-ю
                    if not attempts_info["is_completed"]:
                        available_topics.append(topic)
                else:
                    # Для остальных тем показываем всегда
                    available_topics.append(topic)
            
            if available_topics:
                available_modules[module] = available_topics
        
        return available_modules

