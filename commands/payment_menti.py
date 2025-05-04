from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ConversationHandler

from commands.base_function import back_to_main_menu
from commands.states import PAYMENT_WAITING, PAYMENT_CONFIRMATION
from data_base.db import session
from data_base.models import Student, Payment

from telegram import Update
from telegram.ext import ConversationHandler
from datetime import datetime
from decimal import Decimal
from data_base.models import Payment, Student
from data_base.db import session
from data_base.operations import get_mentor_by_student
from commands.states import PAYMENT_WAITING


async def request_payment(update: Update, context):
    """Студент нажимает 'Оплата за обучение'"""
    await update.message.reply_text("📩 Отправьте чек (фото или документ) и укажите сумму платежа (например, '15000').")
    return PAYMENT_WAITING


async def forward_payment(update: Update, context):
    student_telegram = f"@{update.message.from_user.username}"
    message = update.message

    file_id = None
    payment_text = None

    # Извлекаем сумму и файл (если есть)
    if message.photo:
        file_id = message.photo[-1].file_id
        payment_text = message.caption
    elif message.document:
        file_id = message.document.file_id
        payment_text = message.caption
    elif message.text:
        payment_text = message.text.strip()

    if not payment_text or not payment_text.isdigit():
        await update.message.reply_text("❌ Укажите сумму числом (например, '15000').")
        return PAYMENT_WAITING

    amount = float(payment_text)

    # Получаем студента и ментора
    student = session.query(Student).filter(Student.telegram == student_telegram).first()
    mentor = get_mentor_by_student(student_telegram)

    if not student or not mentor:
        await update.message.reply_text("⚠ Не удалось найти профиль или ментора.")
        return ConversationHandler.END

    total_paid = student.payment_amount or Decimal("0")
    total_cost = student.total_cost or Decimal("0")

    if total_paid + amount > total_cost:
        await update.message.reply_text(
            f"❌ Ошибка: введённая сумма превышает стоимость обучения.\n"
            f"💰 Уже оплачено: {total_paid} руб.\n"
            f"📚 Стоимость курса: {total_cost} руб.\n"
            f"Введите корректную сумму (не больше {total_cost - total_paid} руб.)"
        )
        return PAYMENT_WAITING

    comment = "Первоначальный платёж при регистрации" if total_paid == 0 else "Доплата"

    new_payment = Payment(
        student_id=student.id,
        mentor_id=mentor.id,
        amount=Decimal(str(amount)),
        payment_date=datetime.now().date(),
        comment=comment,
        status="не подтвержден"
    )
    session.add(new_payment)
    session.commit()

    # ✅ Уведомление студента
    await update.message.reply_text("✅ Ваш платёж отправлен на проверку ментору.")

    # ✅ Уведомление ментора
    mentor_chat_id = 1257163820  # 🔒 Жёстко заданный ID

    await context.bot.send_message(
        chat_id=mentor_chat_id,
        text=(
            f"📩 Ученик {student.telegram} отправил платёж на сумму {amount:.2f} руб.\n"
            f"🆔 ID платежа: {new_payment.id}\n"
            f"Статус: не подтвержден"
        )
    )

    if file_id:
        await context.bot.send_photo(
            chat_id=mentor.chat_id,
            photo=file_id,
            caption=f"🧾 Чек от {student.telegram}"
        )

    return ConversationHandler.END



