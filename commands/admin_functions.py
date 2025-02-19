from telegram import Update, ReplyKeyboardMarkup

from commands.states import WAITING_MENTOR_NAME, WAITING_MENTOR_TG_NEW, WAITING_MENTOR_DIRECTION, BROADCAST_WAITING, WAITING_MENTOR_TG_REMOVE
from data_base.db import session
from data_base.models import Mentor
from data_base.operations import get_all_students  # Импортируем функцию для получения всех студентов
from telegram.ext import ConversationHandler, ContextTypes


async def add_mentor_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинаем процесс добавления ментора."""
    await update.message.reply_text("📝 Введите ФИО нового ментора:")
    return WAITING_MENTOR_NAME


async def save_mentor_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохраняем ФИО и запрашиваем Telegram username."""
    context.user_data["new_mentor_name"] = update.message.text
    await update.message.reply_text("📌 Теперь введите Telegram username нового ментора (пример: @username):")
    return WAITING_MENTOR_TG_NEW


async def save_mentor_tg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохраняем Telegram username и предлагаем выбрать направление."""
    new_mentor_tg = update.message.text.strip()

    if not new_mentor_tg.startswith("@"):
        await update.message.reply_text("❌ Ошибка: Telegram username должен начинаться с '@'. Попробуйте ещё раз.")
        return WAITING_MENTOR_TG_NEW  # ✅ Должно совпадать с states.py

    context.user_data["new_mentor_tg"] = new_mentor_tg

    await update.message.reply_text(
        "💼 Выберите направление ментора:",
        reply_markup=ReplyKeyboardMarkup([["Ручное тестирование", "Автотестирование"]], one_time_keyboard=True)
    )
    return WAITING_MENTOR_DIRECTION  # ✅ Убедись, что это состояние определено в states.py



async def save_mentor_direction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохраняем направление и добавляем ментора в БД."""
    direction = update.message.text.strip()

    if direction not in ["Ручное тестирование", "Автотестирование"]:
        await update.message.reply_text("❌ Ошибка: выберите одно из направлений: Ручное тестирование или Автотестирование.")
        return WAITING_MENTOR_DIRECTION

    new_mentor_name = context.user_data.get("new_mentor_name")
    new_mentor_tg = context.user_data.get("new_mentor_tg")

    # Проверяем, существует ли ментор
    existing_mentor = session.query(Mentor).filter(Mentor.telegram == new_mentor_tg).first()

    if existing_mentor:
        await update.message.reply_text(f"⚠ Ментор {new_mentor_tg} уже существует в системе.")
        return ConversationHandler.END

    # Добавляем ментора в базу данных
    new_mentor = Mentor(
        telegram=new_mentor_tg,
        full_name=new_mentor_name,
        is_admin=False,
        direction=direction
    )
    session.add(new_mentor)
    session.commit()

    await update.message.reply_text(f"✅ Ментор добавлен: {new_mentor_name} - {new_mentor_tg} ({direction})")
    return ConversationHandler.END


async def request_broadcast_message(update, context):
    """Запрашивает у админа текст рассылки"""
    await update.message.reply_text("📢 Введите текст рассылки для всех студентов:")
    return BROADCAST_WAITING

async def send_broadcast(update, context):
    """Отправляет сообщение всем студентам"""
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("⚠ Ошибка! Сообщение не может быть пустым.")
        return BROADCAST_WAITING

    students = get_all_students()  # Получаем список всех студентов

    sent_count = 0
    failed_count = 0

    for student in students:
        if student.chat_id:  # Проверяем, есть ли у студента chat_id
            try:
                await context.bot.send_message(chat_id=student.chat_id, text=f"📢 Сообщение от ментора:\n\n{text}")
                sent_count += 1
            except Exception as e:
                print(f"❌ Ошибка отправки студенту {student.telegram}: {e}")
                failed_count += 1

    await update.message.reply_text(f"✅ Сообщение отправлено {sent_count} студентам. Не доставлено: {failed_count}.")
    return ConversationHandler.END


async def remove_mentor_request(update: Update, context):
    """Запрашивает у админа username ментора для удаления."""
    await update.message.reply_text("📌 Введите Telegram username ментора, которого нужно удалить (пример: @username):")
    return WAITING_MENTOR_TG_REMOVE

async def remove_mentor(update: Update, context):
    """Удаляет ментора из базы по его Telegram username."""
    mentor_tg = update.message.text.strip()

    if not mentor_tg.startswith("@"):
        await update.message.reply_text("❌ Ошибка: Telegram username должен начинаться с '@'. Попробуйте ещё раз.")
        return WAITING_MENTOR_TG_REMOVE

    # ✅ Проверяем, существует ли ментор в БД
    mentor = session.query(Mentor).filter(Mentor.telegram == mentor_tg).first()

    if not mentor:
        await update.message.reply_text(f"⚠ Ошибка: Ментор {mentor_tg} не найден в системе.")
        return ConversationHandler.END

    # ✅ Удаляем ментора
    session.delete(mentor)
    session.commit()

    await update.message.reply_text(f"✅ Ментор {mentor_tg} удалён!")
    return ConversationHandler.END
