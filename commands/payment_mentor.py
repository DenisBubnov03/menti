import re
from telegram import Update
from telegram.ext import ConversationHandler

from commands.base_function import back_to_main_menu
from data_base.db import session
from data_base.models import Student
from data_base.operations import update_student_payment, get_student_by_fio_or_telegram


async def confirm_or_reject_payment(update: Update, context):
    """Ментор подтверждает или отклоняет платеж."""
    print("🟢 confirm_or_reject_payment вызван!")  # Для отладки

    student_telegram = context.bot_data.get("student_telegram")
    payment_text = context.bot_data.get("payment_text")
    mentor_telegram = "@" + update.message.from_user.username  # Получаем Telegram ник ментора

    if not student_telegram:
        await update.message.reply_text("⚠ Ошибка! Не найден студент.")
        return ConversationHandler.END

    # ✅ Получаем chat_id студента из БД
    student = session.query(Student).filter(Student.telegram == student_telegram).first()
    if not student or not student.chat_id:
        await update.message.reply_text("⚠ Ошибка! Не удалось найти chat_id студента.")
        return ConversationHandler.END
    try:
        amount = float(payment_text)  # Преобразуем сумму в число
        if amount <= 0:
            raise ValueError("❌ Ошибка! Сумма должна быть больше 0.")
    except ValueError:
        await update.message.reply_text("❌ Ошибка! Введите корректную сумму (например, '15000').")
        return ConversationHandler.END

    try:
        update_student_payment(student_telegram, amount, mentor_telegram)
    except RuntimeError as e:
        # ✅ Обработка ошибки превышения стоимости обучения
        error_message = str(e)
        if "превышает стоимость обучения" in error_message:
            await update.message.reply_text(f"⚠ Ошибка! {error_message}")
            await context.bot.send_message(
                chat_id=student.chat_id,
                text="❌ Ваш платёж не принят, так как общая сумма оплаты превышает стоимость обучения. "
                     "Пожалуйста, уточните сумму и попробуйте снова."
            )
        else:
            await update.message.reply_text(f"⚠ Произошла ошибка: {error_message}")
        return await back_to_main_menu(update, context)

    # ✅ Платёж подтверждён — уведомляем студента и ментора
    await context.bot.send_message(chat_id=student.chat_id, text=f"✅ Ваш платеж {payment_text} подтверждён!")
    await update.message.reply_text(f"✅ Платеж {payment_text} подтверждён.")
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
