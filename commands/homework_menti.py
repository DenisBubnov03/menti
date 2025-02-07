from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import MessageHandler, ConversationHandler
from data_base.db import session

from commands.states import HOMEWORK_MODULE, HOMEWORK_TOPIC, HOMEWORK_MENTOR, HOMEWORK_MESSAGE, HOMEWORK_SELECT_TYPE
from data_base.models import Homework
from data_base.operations import get_pending_homework, approve_homework, \
    get_student_by_fio_or_telegram, get_all_mentors, get_mentor_chat_id

MODULES_TOPICS = {
    "Ручное тестирование": {
        "Модуль 1": ["Тема 1.3", "Тема 1.4"],
        "Модуль 2": ["Тема 2.1", "Тема 2.2", "Тема 2.3", "Тема 2.4", "Тема 2.5"],
        "Модуль 3": ["Тема 3.1", "Тема 3.2"],
        "Модуль 4": ["Тема 4.1", "Тема 4.2", "Тема 4.3"],
        "Модуль 5": ["Резюме/Легенда"]
    },
    "Автотестирование": {
        "Модуль 1": ["Тема 1.1", "Тема 1.2", "Тема 1.3"],
        "Модуль 2": ["Тема 2.1", "Тема 2.2", "Тема 2.3", "Тема 2.4", "Тема 2.5", "Тема 2.6", "Тема 2.7", "Экзамен 2"],
        "Модуль 3": ["Тема 3.1", "Тема 3.2", "Тема 3.3", "Тема 3.4", "Тема 3.5", "Тема 3.6", "Экзамен 3"],
        "Модуль 4": ["Тема 4.1", "Тема 4.2", "Тема 4.3", "Тема 4.4", "Тема 4.5", "Экзамен 4"],
        "Модуль 5": ["Тема 5.1", "Тема 5.2", "Тема 5.3", "Тема 5.4", "Тема 5.5", "Тема 5.6", "Экзамен 5"]
    }
}



async def submit_homework(update: Update, context):
    """Начало процесса сдачи домашки с учётом направления"""
    student_telegram = "@" + update.message.from_user.username
    student = get_student_by_fio_or_telegram(student_telegram)

    if not student:
        await update.message.reply_text("❌ Вы не зарегистрированы как студент!")
        return ConversationHandler.END

    training_type = student.training_type  # Получаем направление
    print(f'Тип студента {training_type}')
    if training_type == "Фуллстек":
        # Если фуллстек — сначала спрашиваем, какое направление
        keyboard = [
            [KeyboardButton("Ручное тестирование")],
            [KeyboardButton("Автотестирование")]
        ]
        await update.message.reply_text(
            "Выберите направление:",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
        return HOMEWORK_SELECT_TYPE

    # Для manual и automation сразу показываем модули
    if training_type not in MODULES_TOPICS:
        await update.message.reply_text("❌ Ошибка! Ваше направление не поддерживается.")
        return ConversationHandler.END

    keyboard = [[KeyboardButton(mod)] for mod in MODULES_TOPICS[training_type].keys()]

    await update.message.reply_text(
        "📚 Выберите модуль:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return HOMEWORK_MODULE


async def select_stack_type(update: Update, context):
    """Фуллстек выбирает направление: manual или automation"""
    choice = update.message.text

    if "Ручное тестирование" in choice:
        context.user_data["training_type"] = "Ручное тестирование"
    elif "Автотестирование" in choice:
        context.user_data["training_type"] = "Автотестирование"
    else:
        await update.message.reply_text("❌ Ошибка! Выберите 'Ручное тестирование' или 'Автотестирование'.")
        return HOMEWORK_SELECT_TYPE

    training_type = context.user_data["training_type"]
    keyboard = [[KeyboardButton(mod)] for mod in MODULES_TOPICS[training_type].keys()]

    await update.message.reply_text(
        f"📚 Вы выбрали {choice}. Теперь выберите модуль:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return HOMEWORK_MODULE


async def choose_topic(update: Update, context):
    """Выбор темы из модуля"""
    student_telegram = "@" + update.message.from_user.username
    student = get_student_by_fio_or_telegram(student_telegram)

    if not student:
        await update.message.reply_text("❌ Вы не зарегистрированы как студент!")
        return HOMEWORK_MODULE

    # Получаем направление обучения студента
    training_type = context.user_data.get("training_type", student.training_type)

    if training_type not in MODULES_TOPICS:
        await update.message.reply_text("❌ Ошибка! Ваше направление не поддерживается.")
        return HOMEWORK_MODULE

    module = update.message.text
    context.user_data["module"] = module  # Запоминаем модуль

    # Теперь ищем модуль ВНУТРИ training_type
    if module not in MODULES_TOPICS[training_type]:
        await update.message.reply_text("❌ Ошибка! Такого модуля нет. Выберите из списка.")
        return HOMEWORK_MODULE

    topics = MODULES_TOPICS[training_type][module]  # Теперь модули берём правильно
    keyboard = [[KeyboardButton(topic)] for topic in topics]

    await update.message.reply_text(
        "📌 Выберите тему:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return HOMEWORK_TOPIC


async def choose_mentor(update: Update, context):
    """Выбор ментора"""
    context.user_data["topic"] = update.message.text  # Запоминаем тему
    mentors = get_all_mentors()  # Функция получения списка менторов
    keyboard = [[KeyboardButton(m.telegram)] for m in mentors]

    await update.message.reply_text(
        "👨‍🏫 Выберите ментора:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return HOMEWORK_MENTOR

async def wait_for_homework(update: Update, context):
    """Ждём, когда студент отправит сообщение с домашним заданием"""
    context.user_data["mentor"] = update.message.text  # Запоминаем ментора
    await update.message.reply_text("📩 Отправьте ваше домашнее задание (файл, фото, текст, голосовое и т.д.):")
    return HOMEWORK_MESSAGE

async def save_and_forward_homework(update: Update, context):
    """Сохранение домашки и пересылка её ментору"""
    student_telegram = "@" + update.message.from_user.username
    student = get_student_by_fio_or_telegram(student_telegram)

    if not student:
        await update.message.reply_text("❌ Вы не зарегистрированы как студент!")
        return ConversationHandler.END

    module = context.user_data["module"]
    topic = context.user_data["topic"]
    mentor = context.user_data["mentor"]

    # Создаем запись в БД
    new_homework = Homework(
        student_id=student.id,
        module=module,
        topic=topic,
        status="ожидает проверки"
    )
    session.add(new_homework)
    session.commit()

    # ID домашки
    homework_id = new_homework.id

    # Отправляем ментору уведомление
    mentor_chat_id = get_mentor_chat_id(mentor)

    message_text = (
        f"📚 *Ученик {student.fio} прислал домашку по {module} / {topic}*\n"
        f"🏷 ID: {homework_id}\n"
        f"✉ Следующее сообщение — сама домашка:"
    )

    await context.bot.send_message(chat_id=mentor_chat_id, text=message_text, parse_mode="Markdown")

    # Пересылаем сообщение студента ментору
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

