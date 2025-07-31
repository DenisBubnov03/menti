import re
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ConversationHandler, ContextTypes

from commands.base_function import back_to_main_menu
from commands.states import PAYMENT_CONFIRMATION
from data_base.db import session
from data_base.models import Student, Mentor, Payment
from data_base.operations import update_student_payment, get_student_by_fio_or_telegram



async def show_pending_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    mentor = session.query(Mentor).filter(Mentor.chat_id == str(user_id)).first()

    if not mentor:
        await update.message.reply_text("❌ Ошибка: вы не зарегистрированы как ментор.")
        return ConversationHandler.END

    # Получаем платежи со статусом "не подтвержден"
    pending_payments = session.query(Payment).filter_by(status="не подтвержден").all()

    if not pending_payments:
        await update.message.reply_text("✅ У вас нет неподтверждённых платежей.")
        return ConversationHandler.END

    message = "💰 Платежи, ожидающие подтверждения:\n\n"
    for p in pending_payments:
        message += f"🆔 ID: {p.id}, 👨‍🎓 Студент ID {p.student_id}, 💵 {p.amount} руб., 📅 {p.payment_date}\n"

    message += "\n✏ Введите ID платежа, чтобы подтвердить или отклонить."

    # Сохраняем список в context
    context.user_data["pending_payment_ids"] = [p.id for p in pending_payments]

    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("🔙 В главное меню")]],
        resize_keyboard=True
    )
    await update.message.reply_text(
        message,
        reply_markup=keyboard
    )
    return PAYMENT_CONFIRMATION


async def check_payment_by_id(update: Update, context: ContextTypes.DEFAULT_TYPE):

    payment_id = update.message.text.strip()

    if payment_id.lower() in ["в главное меню", "🔙 в главное меню"]:
        return await back_to_main_menu(update, context)

    if not payment_id.isdigit():
        await update.message.reply_text("❌ Введите корректный ID платежа (число).")
        return PAYMENT_CONFIRMATION

    payment = session.query(Payment).filter_by(id=int(payment_id)).first()

    if not payment or payment.status != "не подтвержден":
        await update.message.reply_text("⚠ Платёж не найден или уже обработан.")
        return PAYMENT_CONFIRMATION

    # Сохраняем в context
    context.user_data["payment_id"] = payment.id
    context.user_data["student_id"] = payment.student_id
    context.user_data["amount"] = float(payment.amount)

    keyboard = ReplyKeyboardMarkup(
        [["✅ Подтвердить платёж"], ["❌ Отклонить платёж"], ["🔙 Отменить"]],
        resize_keyboard=True
    )

    await update.message.reply_text(
        f"🆔 Платёж {payment.id} на сумму {payment.amount:.2f} руб.\n"
        f"Студент ID: {payment.student_id}\n\nВыберите действие:",
        reply_markup=keyboard
    )
    return "PAYMENT_DECISION"


async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверяем кнопку отмены
    if update.message.text and update.message.text.strip().lower() in ["отменить", "🔙 отменить"]:
        await update.message.reply_text("❌ Подтверждение платежа отменено.")
        return await back_to_main_menu(update, context)
    
    payment_id = context.user_data.get("payment_id")
    student_id = context.user_data.get("student_id")
    amount = context.user_data.get("amount")

    payment = session.query(Payment).get(payment_id)
    student = session.query(Student).get(student_id)

    if not payment or not student:
        await update.message.reply_text("❌ Ошибка при подтверждении.")
        return ConversationHandler.END

    # Обновляем платёж
    payment.status = "подтвержден"
    if payment.comment == "Комиссия":
        student.commission_paid = (student.commission_paid or 0) + amount
    else:
        student.payment_amount = (student.payment_amount or 0) + amount
        if student.payment_amount >= (student.total_cost or 0):
            student.fully_paid = "Да"

    # student.payment_amount = (student.payment_amount or 0) + amount

    # ✅ Если студент оплатил всё — проставляем fully_paid = "Да"
    if student.payment_amount >= (student.total_cost or 0):
        student.fully_paid = "Да"

    session.commit()

    # Уведомление студенту
    if student.chat_id:
        await context.bot.send_message(
            chat_id=student.chat_id,
            text=f"✅ Ваш платёж {amount:.2f} руб. подтверждён!"
        )

    await update.message.reply_text("✅ Платёж подтверждён и добавлен к сумме оплаты.")
    return await back_to_main_menu(update, context)


async def reject_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверяем кнопку отмены
    if update.message.text and update.message.text.strip().lower() in ["отменить", "🔙 отменить"]:
        await update.message.reply_text("❌ Отклонение платежа отменено.")
        return await back_to_main_menu(update, context)
    
    payment_id = context.user_data.get("payment_id")
    amount = context.user_data.get("amount")
    student_id = context.user_data.get("student_id")

    payment = session.query(Payment).get(payment_id)
    student = session.query(Student).get(student_id)

    if not payment or not student:
        await update.message.reply_text("❌ Ошибка при отклонении.")
        return ConversationHandler.END

    payment.status = "отклонен"
    session.commit()

    if student.chat_id:
        await context.bot.send_message(
            chat_id=student.chat_id,
            text=f"❌ Ваш платёж {amount:.2f} руб. отклонён. Проверьте чек и повторите попытку."
        )

    await update.message.reply_text("❌ Платёж отклонён.")
    return await back_to_main_menu(update, context)
