import re
from telegram import Update
from telegram.ext import ConversationHandler

from commands.base_function import back_to_main_menu
from data_base.db import session
from data_base.models import Student
from data_base.operations import update_student_payment, get_student_by_fio_or_telegram


async def confirm_or_reject_payment(update: Update, context):
    """Ментор подтверждает платеж студента и записывает его в базу."""
    student_telegram = context.bot_data.get("student_telegram")
    payment_text = context.bot_data.get("payment_text")

    if not student_telegram or not payment_text:
        await update.message.reply_text("⚠ Ошибка! Данные платежа не найдены.")
        return ConversationHandler.END

    # Получаем данные студента
    student = session.query(Student).filter(Student.telegram == student_telegram).first()
    if not student:
        await update.message.reply_text("⚠ Студент не найден.")
        return ConversationHandler.END

    if not student.mentor_id:
        await update.message.reply_text("⚠ У студента не назначен ментор.")
        return ConversationHandler.END

    if not student.chat_id:
        await update.message.reply_text("⚠ У студента не указан chat_id.")
        return ConversationHandler.END

    try:
        amount = float(payment_text)
    except ValueError:
        await update.message.reply_text("❌ Ошибка: сумма указана неверно.")
        return ConversationHandler.END

    try:
        # Записываем платёж
        update_student_payment(student.id, amount, student.mentor_id)
    except RuntimeError as e:
        await update.message.reply_text(f"⚠ Произошла ошибка: {e}")
        return await back_to_main_menu(update, context)

    # Уведомления
    await context.bot.send_message(
        chat_id=student.chat_id,
        text=f"✅ Ваш платёж на сумму {amount:.2f} руб. подтверждён!"
    )
    await update.message.reply_text(f"✅ Платёж на сумму {amount:.2f} руб. записан.")
    return await back_to_main_menu(update, context)




async def reject_payment(update: Update, context):
    """Ментор отклоняет платеж."""
    print("🔴 reject_payment вызван!")  # Для отладки
    student_telegram = context.bot_data.get("student_telegram")
    payment_text = context.bot_data.get("payment_text")

    if not student_telegram:
        await update.message.reply_text("⚠ Ошибка! Не найден студент.")
        return ConversationHandler.END

    # ✅ Получаем chat_id студента из БД
    student = session.query(Student).filter(Student.telegram == student_telegram).first()
    if not student or not student.chat_id:
        await update.message.reply_text("⚠ Ошибка! Не удалось найти chat_id студента.")
        return ConversationHandler.END

    # ✅ Уведомляем студента об отклонении платежа
    try:
        await context.bot.send_message(
            chat_id=student.chat_id,
            text=f"❌ Ваш платеж {payment_text} не принят. Проверьте чек и повторите попытку."
        )
    except Exception as e:
        await update.message.reply_text(f"⚠ Ошибка при отправке уведомления студенту: {str(e)}")

    await update.message.reply_text(f"❌ Платеж {payment_text} отклонён.")
    return await back_to_main_menu(update, context)
