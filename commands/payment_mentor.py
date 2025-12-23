import re
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ConversationHandler, ContextTypes

from commands.base_function import back_to_main_menu
from commands.states import PAYMENT_CONFIRMATION
from data_base.db import session
from data_base.models import Student, Mentor, Payment
from data_base.operations import update_student_payment, get_student_by_fio_or_telegram
from classes.salary_manager import SalaryManager # <--- Убедитесь, что этот импорт есть


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
        # Получаем информацию о студенте
        student = session.query(Student).filter_by(id=p.student_id).first()
        
        # Исправление: проверяем, что student.telegram — строка
        if student and hasattr(student, 'telegram'):
            if isinstance(student.telegram, tuple):
                student_telegram = student.telegram[0]  # Берём первый элемент кортежа
            else:
                student_telegram = student.telegram
            
            # Проверяем, что telegram не пустой
            if not student_telegram or student_telegram.strip() in [".", ""]:
                student_telegram = f"ID:{p.student_id}"
        else:
            student_telegram = f"ID:{p.student_id}"
            
        message += f"🆔 ID: {p.id}, 👨‍🎓 Студент {student_telegram}, 💵 {p.amount} руб., 📅 {p.payment_date}\n"

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

    # Получаем информацию о студенте
    student = session.query(Student).filter_by(id=payment.student_id).first()
    
    # Исправление: проверяем, что student.telegram — строка
    if student and hasattr(student, 'telegram'):
        if isinstance(student.telegram, tuple):
            student_telegram = student.telegram[0]  # Берём первый элемент кортежа
        else:
            student_telegram = student.telegram
        
        # Проверяем, что telegram не пустой
        if not student_telegram or student_telegram.strip() in [".", ""]:
            student_telegram = f"ID:{payment.student_id}"
    else:
        student_telegram = f"ID:{payment.student_id}"
    
    await update.message.reply_text(
        f"🆔 Платёж {payment.id} на сумму {payment.amount:.2f} руб.\n"
        f"Студент: {student_telegram}\n\nВыберите действие:",
        reply_markup=keyboard
    )
    return "PAYMENT_DECISION"


async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Инициализация менеджера
    salary_manager = SalaryManager()

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
    if payment.comment == "Доплата":
        manager = SalaryManager()

        # Пытаемся обработать как старую доплату
        legacy_payouts = manager.handle_legacy_additional_payment(
            session=session,
            payment_id=payment.id,
            student_id=payment.student_id,
            payment_amount=payment.amount
        )

        if legacy_payouts:
            session.commit()
            print("✅ Начисление старого образца успешно выполнено.")
        else:
            # Если не старого образца, то вызываем стандартный обработчик,
            # который работает через CuratorCommission (по темам/модулям)
            manager.create_salary_entry_from_payment(
                session=session,
                payment_id=payment.id,
                student_id=payment.student_id,
                payment_amount=payment.amount
            )
            session.commit()
            print("✅ Начисление стандартного образца успешно выполнено.")
    # 🌟 БЛОК РАСЧЕТА КОМИССИИ (СОГЛАСНО ВАШЕЙ ЛОГИКЕ)
    if payment.comment == "Комиссия":

        # 🚀 ВЫЗОВ РАСЧЕТА КОМИССИИ И ЗАПИСИ
        # create_salary_entry_from_payment:
        # 1. Рассчитает ЗП куратору
        # 2. Создаст запись в таблице salary
        # 3. ОБНОВИТ student.commission_paid (КРИТИЧЕСКИЙ ШАГ)
        try:
            print('start count comission')
            salary_manager.create_salary_entry_from_payment(
                session=session,
                payment_id=payment_id,
                student_id=student_id,
                payment_amount=amount
            )
        except Exception as e:
            print(f"Warn: failed to create commission entry for payment {payment_id}: {e}")

        # Убираем: student.commission_paid = (student.commission_paid or 0) + amount
        # (Это предотвращает двойное увеличение, так как это делает manager.create_salary_entry_from_payment)
    else:
        # 🌟 БЛОК ОСНОВНОГО ПЛАТЕЖА (БЕЗ РАСЧЕТА ЗП КУРАТОРУ)
        student.payment_amount = (student.payment_amount or 0) + amount

        # ✅ Проверка полной оплаты
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
