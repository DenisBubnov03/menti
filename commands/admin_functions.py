from telegram import Update

from commands.states import *
from data_base.db import session
from data_base.models import Mentor
from data_base.operations import get_all_students  # Импортируем функцию для получения всех студентов
from telegram.ext import ConversationHandler

from telegram.ext import ConversationHandler


async def add_mentor_request(update: Update, context):
    """Начинаем процесс добавления ментора."""
    await update.message.reply_text("📝 Введите ФИО нового ментора:")
    return WAITING_MENTOR_NAME


async def save_mentor_name(update: Update, context):
    """Сохраняем ФИО и запрашиваем Telegram username."""
    context.user_data["new_mentor_name"] = update.message.text  # ✅ Сохраняем ФИО
    await update.message.reply_text("📌 Теперь введите Telegram username нового ментора (пример: @username):")
    return WAITING_MENTOR_TG


async def save_mentor_tg(update: Update, context):
    """Сохраняем Telegram username и добавляем ментора в БД."""
    new_mentor_tg = update.message.text.strip()

    # ✅ Проверяем, начинается ли username с "@"
    if not new_mentor_tg.startswith("@"):
        await update.message.reply_text("❌ Ошибка: Telegram username должен начинаться с '@'. Попробуйте ещё раз.")
        return WAITING_MENTOR_TG

    new_mentor_name = context.user_data.get("new_mentor_name")

    # ✅ Проверяем, нет ли уже такого ментора в БД
    existing_mentor = session.query(Mentor).filter(Mentor.telegram == new_mentor_tg).first()

    if existing_mentor:
        await update.message.reply_text(f"⚠ Ментор {new_mentor_tg} уже существует в системе.")
        return ConversationHandler.END

    # ✅ Добавляем нового ментора в БД
    new_mentor = Mentor(telegram=new_mentor_tg, full_name=new_mentor_name, is_admin=False)
    session.add(new_mentor)
    session.commit()

    await update.message.reply_text(f"✅ Ментор добавлен: {new_mentor_name} - {new_mentor_tg}")
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


from telegram.ext import ConversationHandler

WAITING_MENTOR_TG_REMOVE = range(1)  # Состояние

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
