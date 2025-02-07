from commands.states import BROADCAST_WAITING
from data_base.operations import get_all_students  # Импортируем функцию для получения всех студентов
from telegram.ext import ConversationHandler


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
