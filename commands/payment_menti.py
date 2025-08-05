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
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("🔙 Отменить")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await update.message.reply_text(
        "📩 Отправьте чек (фото или документ) и укажите сумму платежа (например, '15000').",
        reply_markup=keyboard
    )
    return PAYMENT_WAITING


async def forward_payment(update: Update, context):
    student_telegram = f"@{update.message.from_user.username}"
    message = update.message

    # Проверяем кнопку отмены
    if message.text and message.text.strip().lower() in ["отменить", "🔙 отменить"]:
        await update.message.reply_text("❌ Оплата отменена.")
        return await back_to_main_menu(update, context)

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

    # --- Исправление mentor_id для авто и фуллстеков ---
    mentor_id = student.mentor_id  # по умолчанию ручной
    if student.training_type in ["Автотестирование", "Фуллстек"] and getattr(student, 'auto_mentor_id', None):
        mentor_id = student.auto_mentor_id
    # --- конец исправления ---

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
        mentor_id=mentor_id,
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
    # mentor_chat_id = 1257163820  # 🔒 Жёстко заданный ID
    mentor_chat_id = 325531224

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
            chat_id=mentor.mentor_chat_id,
            photo=file_id,
            caption=f"🧾 Чек от {student.telegram}"
        )

    return ConversationHandler.END

async def forward_commission_payment(update: Update, context):
    student_telegram = f"@{update.message.from_user.username}"
    message = update.message

    # Проверяем кнопку отмены
    if message.text and message.text.strip().lower() in ["отменить", "🔙 отменить"]:
        await update.message.reply_text("❌ Выплата комиссии отменена.")
        return await back_to_main_menu(update, context)

    file_id = None
    payment_text = None

    if message.photo:
        file_id = message.photo[-1].file_id
        payment_text = message.caption
    elif message.document:
        file_id = message.document.file_id
        payment_text = message.caption
    elif message.text:
        payment_text = message.text.strip()

    if not payment_text or not payment_text.strip().isdigit():
        await update.message.reply_text("❌ Укажите сумму числом (например, '15000').")
        return PAYMENT_WAITING

    amount = float(payment_text)

    remaining = context.user_data.get("commission_remaining")
    if amount > remaining:
        await update.message.reply_text(
            f"❌ Сумма превышает оставшуюся часть комиссии.\n"
            f"Осталось выплатить: {remaining:.2f} руб.\nВведите другую сумму:"
        )
        return PAYMENT_WAITING

    student = session.query(Student).filter(Student.telegram == student_telegram).first()
    mentor = get_mentor_by_student(student_telegram)

    if not student or not mentor:
        await update.message.reply_text("⚠ Не удалось найти профиль или ментора.")
        return ConversationHandler.END
    mentor_id = student.mentor_id
    auto_mentor_id = getattr(student, 'auto_mentor_id', None)
    if student.training_type in ["Автотестирование", "Фуллстек"] and auto_mentor_id:
        mentor_id = auto_mentor_id
    new_payment = Payment(
        student_id=student.id,
        mentor_id=mentor_id,
        amount=Decimal(str(amount)),
        payment_date=datetime.now().date(),
        comment="Комиссия",
        status="не подтвержден"
    )
    session.add(new_payment)
    session.commit()

    await update.message.reply_text("✅ Выплата комиссии отправлена на проверку ментору.")
    mentor_chat_id = 325531224

    if not mentor_chat_id:
        await update.message.reply_text("⚠ Ошибка: у ментора не указан chat_id.")
        return ConversationHandler.END

    await context.bot.send_message(
        chat_id=mentor_chat_id,
        text=(
            f"📩 Студент {student_telegram} отправил выплату комиссии на сумму {amount:.2f} руб.\n"
            f"🆔 ID платежа: {new_payment.id}\n"
            f"Статус: не подтвержден"
        )
    )

    if file_id:
        if message.photo:
            await context.bot.send_photo(chat_id=mentor_chat_id, photo=file_id, caption=f"🧾 Чек от {student.telegram}")
        elif message.document:
            await context.bot.send_document(chat_id=mentor_chat_id, document=file_id, caption=f"🧾 Чек от {student.telegram}")
    else:
        await context.bot.send_message(chat_id=mentor_chat_id, text=f"⚠️ Чек не был приложен студентом {student.telegram}.")

    return ConversationHandler.END


async def request_commission_payment(update: Update, context):
    """Студент инициирует выплату комиссии"""
    student_telegram = "@" + update.message.from_user.username
    student = session.query(Student).filter(Student.telegram == student_telegram).first()

    if not student:
        await update.message.reply_text("❌ Вы не зарегистрированы как студент!")
        return ConversationHandler.END

    # Проверяем статус обучения
    training_status = student.training_status.strip().lower() if student.training_status else ""
    
    if training_status != "устроился":
        await update.message.reply_text(
            "❌ Выплата комиссии доступна только после трудоустройства!\n\n"
            f"Ваш текущий статус: {student.training_status or 'Не указан'}\n"
            "Обратитесь к ментору для обновления статуса после трудоустройства."
        )
        return ConversationHandler.END

    if not student.commission:
        await update.message.reply_text("❌ У вас не указана информация о комиссии.")
        return ConversationHandler.END

    try:
        parts, percent = map(lambda x: x.strip().replace('%', ''), student.commission.split(","))
        total_parts = int(parts)
        percent = float(percent)

        total_commission = round((student.salary or 0) * (percent / 100) * total_parts, 2)
        already_paid = float(student.commission_paid or 0)
        remaining = round(total_commission - already_paid, 2)

        if remaining <= 0:
            await update.message.reply_text("✅ Вы уже полностью выплатили комиссию.")
            return ConversationHandler.END

        context.user_data["student_telegram"] = student_telegram
        context.user_data["commission_payment"] = True
        context.user_data["commission_remaining"] = remaining

        keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("🔙 Отменить")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await update.message.reply_text(
            f"💸 Общая комиссия: {total_commission} руб.\n"
            f"✅ Выплачено: {already_paid} руб.\n"
            f"📌 Осталось выплатить: {remaining} руб.\n\n"
            "Пожалуйста, отправьте чек и сумму комиссии:",
            reply_markup=keyboard
        )
        return PAYMENT_WAITING

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка разбора данных комиссии: {str(e)}")
        return ConversationHandler.END
