from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ConversationHandler, ContextTypes

from commands.base_function import back_to_main_menu
from commands.google_calendar import create_event
from data_base.models import Student, Mentor
from data_base.db import session
from commands.states import CALL_SCHEDULE_DATE, CALL_SCHEDULE_TIME, CALL_CONFIRMATION, CALL_SCHEDULE
from data_base.operations import get_mentor_by_direction


async def request_call(update: Update, context):
    """
    Начинает процесс записи на звонок.
    Если студент Фуллстек, предлагает выбрать направление.
    """
    user_id = update.message.from_user.id
    student = session.query(Student).filter_by(telegram=f"@{update.message.from_user.username}").first()

    if not student:
        await update.message.reply_text("Ошибка: ваш профиль не найден.")
        return ConversationHandler.END

    context.user_data["student_telegram"] = student.telegram

    # Если студент Фуллстек, предлагаем выбрать направление
    if student.training_type == "Фуллстек":
        await update.message.reply_text(
            "Выберите направление, по которому хотите записаться на звонок:",
            reply_markup=ReplyKeyboardMarkup(
                [["Ручное тестирование", "Автотестирование"]],
                one_time_keyboard=True
            )
        )
        return CALL_SCHEDULE  # Используем твое состояние

    # Если студент НЕ фуллстек, переходим сразу к выбору даты
    await update.message.reply_text(
        "Введите дату созвона (в формате ДД.ММ.ГГГГ) или нажмите 'Сегодня':",
        reply_markup=ReplyKeyboardMarkup([["Сегодня"], ["Отмена"]], one_time_keyboard=True)
    )
    return CALL_SCHEDULE_DATE  # Используем твое состояние


async def handle_direction_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает выбор направления для Фуллстек-менти и продолжает процесс записи.
    """
    direction = update.message.text
    student_telegram = context.user_data.get("student_telegram")

    # Получаем студента
    student = session.query(Student).filter_by(telegram=student_telegram).first()

    if not student:
        await update.message.reply_text("❌ Студент не найден.")
        return CALL_SCHEDULE

    if direction == "Ручное тестирование":
        mentor_id = 1
    elif direction == "Автотестирование":
        auto_mentor_id = getattr(student, 'auto_mentor_id', None)
        if not auto_mentor_id:
            await update.message.reply_text("❌ У вас не назначен ментор по автотестированию.")
            return CALL_SCHEDULE
        mentor_id = auto_mentor_id
    else:
        await update.message.reply_text("❌ Некорректный выбор, попробуйте снова.")
        return CALL_SCHEDULE

    # Сохраняем выбранного ментора в context.user_data (НЕ в базе)
    context.user_data["mentor_id"] = mentor_id

    await update.message.reply_text(
        "Введите дату созвона (в формате ДД.ММ.ГГГГ) или нажмите 'Сегодня':",
        reply_markup=ReplyKeyboardMarkup([["Сегодня"], ["Отмена"]], one_time_keyboard=True)
    )
    return CALL_SCHEDULE_DATE




async def schedule_call_date(update: Update, context):
    """
    Обрабатываем дату и запрашиваем время.
    """
    date_text = update.message.text.strip()

    if date_text.lower() == "сегодня":
        from datetime import datetime
        date_text = datetime.now().strftime("%d.%m.%Y")
    if date_text.lower() == "отмена":
        await back_to_main_menu(update, context)  # Возврат в меню
        return ConversationHandler.END

    try:
        from datetime import datetime
        call_date = datetime.strptime(date_text, "%d.%m.%Y").date()
        context.user_data["call_date"] = call_date.strftime("%d.%m.%Y")
    except ValueError:
        await update.message.reply_text("⏰ Введите время звонка по часовому поясу МСК в формате ЧЧ:ММ::",
        reply_markup=ReplyKeyboardMarkup([["Отмена"]], one_time_keyboard=True)
    )
        return CALL_SCHEDULE_DATE  # Оставляем пользователя на этом шаге

    await update.message.reply_text("⏰ Введите время звонка по часовому поясу МСК в формате ЧЧ:ММ:")
    return CALL_SCHEDULE_TIME  # Используем твое состояние



async def schedule_call_time(update: Update, context):
    """
    Обрабатывает ввод времени созвона, завершает запись.
    """
    time_text = update.message.text.strip()
    student_telegram = context.user_data.get("student_telegram")
    student = session.query(Student).filter_by(telegram=student_telegram).first()
    date_text = update.message.text.strip()
    if not student:
        await update.message.reply_text("❌ Ошибка: студент не найден.")
        return ConversationHandler.END
    if date_text.lower() == "отмена":
        await back_to_main_menu(update, context)  # Возврат в меню
        return ConversationHandler.END

    mentor_id = context.user_data.get("mentor_id", student.mentor_id)
    mentor = session.query(Mentor).filter_by(id=mentor_id).first()
    mentor_name = mentor.full_name if mentor else "Неизвестный ментор"
    mentor_tg = mentor.telegram if mentor else "Нет данных"

    call_date_time = f"{context.user_data['call_date']} {time_text}"

    # Записываем событие в Google Calendar (или просто сохраняем)
    create_event(student.fio, student_telegram, call_date_time)

    await update.message.reply_text(
        f"✅ Запись на звонок подтверждена!\n"
        f"📅 Дата и время: {call_date_time}\n"
        f"🧑‍🏫 Ваш ментор: {mentor_name} ({mentor_tg})"
    )

    return await back_to_main_menu(update, context)   # Финальный этап

