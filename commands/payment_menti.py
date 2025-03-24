from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ConversationHandler

from commands.base_function import back_to_main_menu
from commands.states import PAYMENT_WAITING, PAYMENT_CONFIRMATION
from data_base.db import session
from data_base.models import Student


async def request_payment(update: Update, context):
    """Студент нажимает 'Оплата за обучение'"""
    await update.message.reply_text("📩 Отправьте чек (фото или документ) и укажите сумму платежа (например, '15000').")
    return PAYMENT_WAITING


async def forward_payment(update: Update, context):
    """Студент отправляет чек или сумму, и бот сразу проверяет корректность суммы"""
    student_telegram = "@" + update.message.from_user.username
    message = update.message

    file_id = None
    payment_text = None

    # Получаем текст и файл
    if message.photo:
        file_id = message.photo[-1].file_id
        payment_text = message.caption
    elif message.document:
        file_id = message.document.file_id
        payment_text = message.caption
    elif message.text:
        payment_text = message.text

    # Проверка суммы
    if not payment_text or not payment_text.strip().isdigit():
        await update.message.reply_text("❌ Укажите сумму числом (например, '15000').")
        return PAYMENT_WAITING

    amount = float(payment_text)

    # Находим студента в БД
    student = session.query(Student).filter(Student.telegram == student_telegram).first()
    if not student:
        await update.message.reply_text("⚠ Не удалось найти вас в базе. Обратитесь к ментору.")
        return ConversationHandler.END

    # Проверка переплаты
    total_paid = student.payment_amount or 0
    total_cost = student.total_cost or 0
    if total_paid + amount > total_cost:
        await update.message.reply_text(
            f"❌ Ошибка: введённая сумма превышает стоимость обучения.\n"
            f"💰 Уже оплачено: {total_paid} руб.\n"
            f"📚 Стоимость курса: {total_cost} руб.\n"
            f"Введите корректную сумму (не больше {total_cost - total_paid} руб.)"
        )
        return PAYMENT_WAITING

    # Отправка ментору
    mentor_chat_id = 325531224  # TODO: динамический ID

    keyboard = ReplyKeyboardMarkup(
        [["✅ Подтвердить платеж"], ["❌ Отклонить платеж"]],
        one_time_keyboard=True,
        resize_keyboard=True
    )

    await context.bot.send_message(
        chat_id=mentor_chat_id,
        text=f"📩 Студент {student_telegram} отправил платёж на сумму {amount:.2f} руб.",
        reply_markup=keyboard
    )

    if file_id:
        await context.bot.send_photo(chat_id=mentor_chat_id, photo=file_id, caption=f"📩 Чек от {student_telegram}")

    context.bot_data["student_telegram"] = student_telegram
    context.bot_data["payment_text"] = str(amount)

    await update.message.reply_text("✅ Запрос на оплату отправлен ментору.")
    return ConversationHandler.END



