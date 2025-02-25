from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ConversationHandler

from commands.base_function import back_to_main_menu
from commands.states import PAYMENT_WAITING, PAYMENT_CONFIRMATION


async def request_payment(update: Update, context):
    """Студент нажимает 'Оплата за обучение'"""
    await update.message.reply_text("📩 Отправьте чек (фото или документ) и укажите сумму платежа (например, '15000').")
    return PAYMENT_WAITING


async def forward_payment(update: Update, context):
    """Пересылаем чек и сумму ментору"""
    student_telegram = "@" + update.message.from_user.username
    message = update.message

    if message.photo:
        file_id = message.photo[-1].file_id
        payment_text = message.caption

        # ✅ Проверяем, указана ли сумма в подписи к фото
        if not payment_text or not payment_text.strip().isdigit():
            await update.message.reply_text("❌ Отправьте фото чека и в подписи укажите сумму (например, '15000').")
            return PAYMENT_WAITING

    elif message.document:
        file_id = message.document.file_id
        payment_text = message.caption

        # ✅ Проверяем, указана ли сумма в подписи к документу
        if not payment_text or not payment_text.strip().isdigit():
            await update.message.reply_text(
                "❌ Отправьте документ с чеком и в подписи укажите сумму (например, '15000').")
            return PAYMENT_WAITING

    elif message.text:
        file_id = None
        payment_text = message.text

        # ✅ Если пользователь отправил только текст — проверяем, это число или нет
        if not payment_text.strip().isdigit():
            await update.message.reply_text("❌ Укажите сумму числом (например, '15000').")
            return PAYMENT_WAITING

    else:
        await update.message.reply_text("❌ Отправьте фото, документ или текст с суммой!")
        return PAYMENT_WAITING

    mentor_chat_id = 1257163820  # Чат ID ментора

    # ✅ Обычные кнопки
    keyboard = ReplyKeyboardMarkup(
        [["✅ Подтвердить платеж"], ["❌ Отклонить платеж"]],
        one_time_keyboard=True,
        resize_keyboard=True
    )

    sent_message = await context.bot.send_message(
        chat_id=mentor_chat_id,
        text=f"📩 Студент {student_telegram} отправил платеж {payment_text}.",
        reply_markup=keyboard
    )

    if file_id:
        await context.bot.send_photo(chat_id=mentor_chat_id, photo=file_id, caption=f"📩 Чек от {student_telegram}")

    # ✅ Сохраняем данные в `context.bot_data`
    context.bot_data["student_telegram"] = student_telegram
    context.bot_data["payment_text"] = payment_text

    print(f"📩 context.bot_data перед завершением: {context.bot_data}")

    await update.message.reply_text("✅ Запрос на оплату отправлен. Теперь вы можете использовать другие функции.")

    return ConversationHandler.END  # ✅ Завершаем обработчик, студент может выполнять другие команды

