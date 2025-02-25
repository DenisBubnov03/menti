from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import MessageHandler, ConversationHandler

from commands.base_function import back_to_main_menu
from data_base.db import session

from commands.states import HOMEWORK_MODULE, HOMEWORK_TOPIC, HOMEWORK_MENTOR, HOMEWORK_MESSAGE, HOMEWORK_SELECT_TYPE
from data_base.models import Homework, Student, Mentor
from data_base.operations import get_pending_homework, approve_homework, \
    get_student_by_fio_or_telegram, get_all_mentors, get_mentor_chat_id

MODULES_TOPICS = {
    "Ручное тестирование": {
        "Модуль 1": ["Тема 1.3", "Тема 1.4", 'Отмена'],
        "Модуль 2": ["Тема 2.1", "Тема 2.2", "Тема 2.3", "Тема 2.4", "Тема 2.5", 'Отмена'],
        "Модуль 3": ["Тема 3.1", "Тема 3.2", 'Отмена'],
        "Модуль 4": ["Тема 4.1", "Тема 4.2", "Тема 4.3", 'Отмена'],
        "Модуль 5": ["Резюме/Легенда, 'Отмена'"],
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
    date_text = update.message.text.strip()
    if date_text.lower() == "отмена":
        await back_to_main_menu(update, context)  # Возврат в меню
        return ConversationHandler.END
    if direction_choice == "Ручное тестирование":
        mentor_id = 1
    elif direction_choice == "Автотестирование":
        mentor_id = 3
    else:
        await update.message.reply_text("❌ Ошибка! Выберите одно из предложенных направлений.")
        return HOMEWORK_SELECT_TYPE

    mentor = session.query(Mentor).filter(Mentor.id == mentor_id).first()

    if not mentor:
        await update.message.reply_text("❌ Ошибка! Выбранный ментор не найден.")
        return HOMEWORK_SELECT_TYPE

    context.user_data["mentor_id"] = mentor.id
    context.user_data["mentor_telegram"] = mentor.telegram
    context.user_data["training_type"] = direction_choice  # ✅ Сохраняем выбранное направление!

    # ✅ Теперь предлагаем выбрать модуль, а не сразу сдавать домашку
    keyboard = [[KeyboardButton(mod)] for mod in MODULES_TOPICS[direction_choice].keys()]

    await update.message.reply_text(
        f"✅ Вы выбрали направление {direction_choice}. Теперь выберите модуль:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )

    return HOMEWORK_MODULE  # 📌 Отправляем на выбор модуля!


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

    topics = MODULES_TOPICS[training_type][module]
    keyboard = [[KeyboardButton(topic)] for topic in topics]

    await update.message.reply_text(
        "📌 Выберите тему:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )

    return HOMEWORK_TOPIC  # ✅ Больше не спрашиваем направление!




async def choose_mentor(update: Update, context):
    """Определяет ментора для отправки домашки в зависимости от направления обучения."""
    student_telegram = f"@{update.message.from_user.username}"
    student = get_student_by_fio_or_telegram(student_telegram)
    date_text = update.message.text.strip()
    if date_text.lower() == "отмена":
        await back_to_main_menu(update, context)  # Возврат в меню
        return ConversationHandler.END
    if not student:
        await update.message.reply_text("❌ Вы не зарегистрированы как студент!")
        return ConversationHandler.END

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
        return ConversationHandler.END

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
    # Создаем запись в БД
    new_homework = Homework(
        student_id=student.id,
        module=module,
        topic=topic,
        status="ожидает проверки"
    )
    session.add(new_homework)
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
    await context.bot.send_message(
        chat_id=mentor_chat_id,
        text=(
            f"📚 Ученик {student.fio} прислал домашку по {module} / {topic}\n"
            f"📜 ID: {homework_id}\n"
            "✉ Следующее сообщение — сама домашка:"
        )
    )

    # ✅ Пересылаем сообщение студента
    await context.bot.forward_message(
        chat_id=mentor_chat_id,
        from_chat_id=update.message.chat_id,
        message_id=update.message.message_id
    )

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("📅 Записаться на звонок")],
            [KeyboardButton("📚 Отправить домашку")],
            [KeyboardButton("💳 Оплата за обучение")]
        ],
        resize_keyboard=True
    )
    await update.message.reply_text("✅ Домашка отправлена ментору!", reply_markup=keyboard)
    return ConversationHandler.END

