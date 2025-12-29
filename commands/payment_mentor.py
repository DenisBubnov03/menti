import re
from datetime import date

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
    salary_manager = SalaryManager()

    # Проверяем кнопку отмены
    if update.message.text and update.message.text.strip().lower() in ["отменить", "🔙 отменить"]:
        await update.message.reply_text("❌ Подтверждение платежа отменено.")
        return await back_to_main_menu(update, context)

    payment_id = context.user_data.get("payment_id")
    student_id = context.user_data.get("student_id")
    amount = float(context.user_data.get("amount") or 0)

    payment = session.query(Payment).get(payment_id)
    student = session.query(Student).get(student_id)

    if not payment or not student:
        await update.message.reply_text("❌ Ошибка: платеж или студент не найдены.")
        return ConversationHandler.END

    # ПРОВЕРКА: Если платеж уже был подтвержден ранее, не обрабатываем второй раз
    if payment.status == "подтвержден":
        await update.message.reply_text("⚠️ Этот платёж уже был подтвержден ранее.")
        return await back_to_main_menu(update, context)

    # ========================================================
    # 1. ГЛАВНОЕ: МЕНЯЕМ СТАТУС В БАЗЕ
    # ========================================================
    payment.status = "подтвержден"
    session.add(payment)  # Фиксируем изменение статуса

    # Определяем "старый" ли студент
    CUTOFF_DATE = date(2025, 12, 1)
    is_legacy = (
            student.start_date and
            student.start_date < CUTOFF_DATE and
            (student.training_type or "").strip().lower() != "фуллстек"
    )

    # ========================================================
    # 2. РАСПРЕДЕЛЕНИЕ ЛОГИКИ ПО ТИПУ ПЛАТЕЖА
    # ========================================================

    # Если это платеж, за который полагается ЗП кураторам (Комиссия или Доплата)
    if payment.comment in ["Комиссия", "Доплата"]:
        if is_legacy:
            print(f"🚀 Обработка Legacy-платежа ({payment.comment}) для {student.telegram}")
            salary_manager.handle_legacy_payment_universal(
                session=session,
                payment_id=payment.id,
                student_id=payment.student_id,
                payment_amount=payment.amount,
                payment_type=payment.comment
            )
        else:
            print(f"🚀 Обработка стандартного платежа через долги для {student.telegram}")
            salary_manager.create_salary_entry_from_payment(
                session=session,
                payment_id=payment.id,
                student_id=payment.student_id,
                payment_amount=payment.amount
            )

        # Бонус для КК (только если комментарий именно "Комиссия")
        if payment.comment == "Комиссия":
            try:
                print('start count kk commission')
                salary_manager.add_kk_salary_record(session=session, payment_id=payment.id)
            except Exception as e:
                print(f"Warn: failed to create KK commission: {e}")

    else:
        # Если это обычная оплата обучения (не комиссия)
        print(f"💰 Обработка основной оплаты обучения для {student.telegram}")
        student.payment_amount = (student.payment_amount or 0) + amount

        # Проверка полной оплаты курса
        if student.payment_amount >= (student.total_cost or 0):
            student.fully_paid = "Да"
        session.add(student)

    # ========================================================
    # 3. СОХРАНЕНИЕ И УВЕДОМЛЕНИЕ
    # ========================================================
    try:
        session.commit()
        print(f"✅ Успешно подтверждено: Платёж {payment_id}, Студент {student.telegram}")
    except Exception as e:
        session.rollback()
        print(f"❌ Ошибка при сохранении в БД: {e}")
        await update.message.reply_text("❌ Произошла ошибка при сохранении данных.")
        return ConversationHandler.END

    # Уведомление студенту
    if student.chat_id:
        try:
            await context.bot.send_message(
                chat_id=student.chat_id,
                text=f"✅ Ваш платёж {amount:.2f} руб. подтверждён!"
            )
        except Exception as e:
            print(f"Warn: не удалось отправить сообщение студенту: {e}")

    await update.message.reply_text(f"✅ Платёж {amount} руб. ({payment.comment}) подтверждён.")
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
