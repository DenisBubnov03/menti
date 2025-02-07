import re

from telegram import Update
from telegram.ext import ConversationHandler

from commands.base_function import back_to_main_menu
from data_base.operations import update_student_payment, get_student_by_fio_or_telegram


async def confirm_or_reject_payment(update: Update, context):
    text = update.message.text.strip()

    print(f"📩 Получен текст кнопки: {text}")  # Логируем

    student_telegram = context.bot_data.get("student_telegram")  # Берём данные из `bot_data`
    payment_text = context.bot_data.get("payment_text")

    if not student_telegram:
        print("❌ Ошибка: Не найден student_telegram в bot_data!")
        await update.message.reply_text("❌ Ошибка: Не найден студент для этого платежа.")
        return

    if text == "✅ Подтвердить":
        print("✅ Подтверждение платежа!")
        return await confirm_payment(update, context, student_telegram, payment_text)
    elif text == "❌ Отклонить":
        print("❌ Отклонение платежа!")
        return await reject_payment(update, context, student_telegram)




async def confirm_payment(update: Update, context, student_telegram, payment_text):
    """Функция подтверждения платежа"""
    student_telegram = context.bot_data.get("student_telegram")
    payment_text = context.bot_data.get("payment_text")

    if not student_telegram:
        await update.message.reply_text("⚠ Ошибка! Не найден студент.")
        return ConversationHandler.END

    # Вносим оплату в базу (логика редактирования студента)
    update_student_payment(student_telegram, payment_text)

    # await context.bot.send_message(chat_id=student_telegram, text=f"✅ Ваш платеж {payment_text} подтверждён!")

    await update.message.reply_text(f"✅ Платеж {payment_text} подтверждён.")
    return await back_to_main_menu(update, context)


async def reject_payment(update: Update, context, student):
    """Ментор отклоняет платеж"""
    student_telegram = context.bot_data.get("student_telegram")
    payment_text = context.bot_data.get("payment_text")

    if not student_telegram:
        await update.message.reply_text("⚠ Ошибка! Не найден студент.")
        return ConversationHandler.END

    await context.bot.send_message(chat_id=student_telegram, text=f"❌ Ваш платеж {payment_text} не найден. Проверьте чек и повторите попытку.")

    await update.message.reply_text(f"❌ Платеж {payment_text} отклонён.")
    return await back_to_main_menu(update, context)

