from telegram import ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ConversationHandler

from commands.base_function import back_to_main_menu
from data_base.operations import get_student_by_fio_or_telegram, is_mentor
from data_base.models import Student, Homework, Payment, ManualProgress
from data_base.db import session
from commands.states import STUDENT_PROGRESS_WAITING
from datetime import datetime, date


async def request_student_progress(update, context):
    """Запрашивает Telegram студента для проверки успеваемости"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton("🔙 В главное меню")]],
        resize_keyboard=True
    )
    await update.message.reply_text(
        "📊 Проверка успеваемости студента\n\n"
        "Введите Telegram студента (например: @username или username):",
        reply_markup=keyboard
    )
    return STUDENT_PROGRESS_WAITING


async def show_student_progress(update, context):
    """Показывает информацию об успеваемости студента"""
    message = update.message.text
    
    if message == "🔙 В главное меню":
        # Возвращаемся в главное меню ментора
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton("📚 Домашние задания")],
                [KeyboardButton("📌 Подтверждение сдачи темы")],
                [KeyboardButton("📅 Записи на звонки")],
                [KeyboardButton("📊 Проверить успеваемость")],
            ],
            resize_keyboard=True
        )
        await update.message.reply_text(
            "🔹 Выберите действие:",
            reply_markup=keyboard
        )
        return ConversationHandler.END
    
    # Очищаем введенный текст от лишних символов
    student_telegram = message.strip()
    # if student_telegram.startswith("@"):
    #     student_telegram = student_telegram[1:]
    
    # Ищем студента
    student = get_student_by_fio_or_telegram(student_telegram)
    
    if not student:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton("🔙 В главное меню")]],
            resize_keyboard=True
        )
        await update.message.reply_text(
            f"❌ Студент с Telegram {student_telegram} не найден.\n"
            "Попробуйте еще раз или вернитесь в главное меню:",
            reply_markup=keyboard
        )
        return STUDENT_PROGRESS_WAITING
    
    # Получаем информацию о студенте
    progress_info = await get_student_progress_info(student)
    
    # Возвращаемся в главное меню ментора
    # keyboard = ReplyKeyboardMarkup(
    #     keyboard=[
    #         [KeyboardButton("📚 Домашние задания")],
    #         [KeyboardButton("📌 Подтверждение сдачи темы")],
    #         [KeyboardButton("📅 Записи на звонки")],
    #         [KeyboardButton("📊 Проверить успеваемость")],
    #     ],
    #     resize_keyboard=True
    # )
    await update.message.reply_text(
        progress_info,
        # reply_markup=keyboard
    )
    return await back_to_main_menu(update, context)


async def get_student_progress_info(student):
    """Формирует подробную информацию об успеваемости студента"""
    info = f"📊 Информация о студенте\n\n"
    info += f"👤 ФИО: {student.fio}\n"
    info += f"📱 Telegram: {student.telegram}\n"
    info += f"Договор подписан: {'Да' if student.contract_signed else 'Нет'}\n"
    info += f"📅 Дата начала обучения: {student.start_date.strftime('%d.%m.%Y') if student.start_date else 'Не указана'}\n"
    info += f"🎯 Тип обучения: {student.training_type or 'Не указан'}\n"
    info += f"📈 Статус обучения: {student.training_status or 'Не указан'}\n"
    info += f"💰 Стоимость обучения: {student.total_cost or 0} руб.\n"
    info += f"💳 Оплачено: {student.payment_amount or 0} руб.\n"
    info += f"✅ Полностью оплачено: {student.fully_paid or 'Нет'}\n"
    
    if student.company:
        info += f"🏢 Компания: {student.company}\n"
    if student.employment_date:
        info += f"📅 Дата трудоустройства: {student.employment_date.strftime('%d.%m.%Y')}\n"
    if student.salary:
        info += f"💵 Зарплата: {student.salary} руб.\n"
    if student.commission:
        info += f"💸 Комиссия: {student.commission}\n"
    if student.commission_paid:
        info += f"💸 Выплачено комиссии: {student.commission_paid} руб.\n"
    
    # Информация о домашних заданиях
    homeworks = session.query(Homework).filter(Homework.student_id == student.id).all()
    if homeworks:
        info += f"\n📚 Домашние задания:\n"
        accepted = len([hw for hw in homeworks if hw.status == "принято"])
        rejected = len([hw for hw in homeworks if hw.status == "отклонено"])
        pending = len([hw for hw in homeworks if hw.status == "ожидает проверки"])
        
        info += f"✅ Принято: {accepted}\n"
        info += f"❌ Отклонено: {rejected}\n"
        info += f"⏳ Ожидает проверки: {pending}\n"
        info += f"📊 Всего: {len(homeworks)}\n"
    else:
        info += f"\n📚 Домашние задания: Нет отправленных заданий\n"
    
    # Информация о платежах
    # payments = session.query(Payment).filter(Payment.student_id == student.id).all()
    # if payments:
    #     info += f"\n💳 Платежи:\n"
    #     total_paid = sum(payment.amount for payment in payments)
    #     confirmed_payments = [p for p in payments if p.status == "подтвержден"]
    #     pending_payments = [p for p in payments if p.status == "не подтвержден"]
        
    #     info += f"💰 Общая сумма: {total_paid} руб.\n"
    #     info += f"✅ Подтверждено: {len(confirmed_payments)}\n"
    #     info += f"⏳ Ожидает подтверждения: {len(pending_payments)}\n"
    # else:
    #     info += f"\n💳 Платежи: Нет платежей\n"
    
    # Информация о прогрессе по ручному тестированию
    if student.training_type and "ручное тестирование" in student.training_type.lower():
        manual_progress = session.query(ManualProgress).filter(ManualProgress.student_id == student.id).first()
        if manual_progress:
            info += f"\n🧠 Прогресс по ручному тестированию:\n"
            
            if manual_progress.m1_start_date:
                info += f"📅 Модуль 1 начат: {manual_progress.m1_start_date.strftime('%d.%m.%Y')}\n"
            if manual_progress.m1_submission_date:
                info += f"✅ Модуль 1 сдан: {manual_progress.m1_submission_date.strftime('%d.%m.%Y')}\n"
            if manual_progress.m1_homework:
                info += f"📚 ДЗ к модулю 1: ✅ Выполнено\n"
            else:
                info += f"📚 ДЗ к модулю 1: ❌ Не выполнено\n"
                
            if manual_progress.m2_1_start_date or manual_progress.m2_2_start_date:
                info += f"📅 Модули 2.1-2.2 начаты\n"
            if manual_progress.m2_1_2_2_submission_date:
                info += f"✅ Модули 2.1-2.2 сданы: {manual_progress.m2_1_2_2_submission_date.strftime('%d.%m.%Y')}\n"
            if manual_progress.m2_1_homework:
                info += f"📚 ДЗ к модулям 2.1-2.2: ✅ Выполнено\n"
            else:
                info += f"📚 ДЗ к модулям 2.1-2.2: ❌ Не выполнено\n"
                
            if manual_progress.m2_3_start_date or manual_progress.m3_1_start_date:
                info += f"📅 Модули 2.3-3.1 начаты\n"
            if manual_progress.m2_3_3_1_submission_date:
                info += f"✅ Модули 2.3-3.1 сданы: {manual_progress.m2_3_3_1_submission_date.strftime('%d.%m.%Y')}\n"
            if manual_progress.m2_3_homework and manual_progress.m3_1_homework:
                info += f"📚 ДЗ к модулям 2.3-3.1: ✅ Выполнено\n"
            else:
                info += f"📚 ДЗ к модулям 2.3-3.1: ❌ Не выполнено\n"
                
            if manual_progress.m3_2_start_date:
                info += f"📅 Модуль 3.2 начат: {manual_progress.m3_2_start_date.strftime('%d.%m.%Y')}\n"
            if manual_progress.m3_2_submission_date:
                info += f"✅ Модуль 3.2 сдан: {manual_progress.m3_2_submission_date.strftime('%d.%m.%Y')}\n"
            if manual_progress.m3_2_homework:
                info += f"📚 ДЗ к модулю 3.2: ✅ Выполнено\n"
            else:
                info += f"📚 ДЗ к модулю 3.2: ❌ Не выполнено\n"
                
            if manual_progress.m3_3_start_date:
                info += f"📅 Модуль 3.3 начат: {manual_progress.m3_3_start_date.strftime('%d.%m.%Y')}\n"
            if manual_progress.m3_3_submission_date:
                info += f"✅ Модуль 3.3 сдан: {manual_progress.m3_3_submission_date.strftime('%d.%m.%Y')}\n"
            if manual_progress.m3_3_homework:
                info += f"📚 ДЗ к модулю 3.3: ✅ Выполнено\n"
            else:
                info += f"📚 ДЗ к модулю 3.3: ❌ Не выполнено\n"
                
            if manual_progress.m4_1_start_date:
                info += f"📅 Модуль 4.1 начат: {manual_progress.m4_1_start_date.strftime('%d.%m.%Y')}\n"
            if manual_progress.m4_1_submission_date:
                info += f"✅ Модуль 4.1 сдан: {manual_progress.m4_1_submission_date.strftime('%d.%m.%Y')}\n"
                
            if manual_progress.m4_2_start_date or manual_progress.m4_3_start_date:
                info += f"📅 Модули 4.2-4.3 начаты\n"
            if manual_progress.m4_2_4_3_submission_date:
                info += f"✅ Модули 4.2-4.3 сданы: {manual_progress.m4_2_4_3_submission_date.strftime('%d.%m.%Y')}\n"
    
    # Информация о последнем звонке
    if student.last_call_date:
        last_call = student.last_call_date
        if isinstance(last_call, str):
            try:
                last_call = datetime.strptime(last_call, "%Y-%m-%d").date()
            except Exception:
                pass  # fallback: оставим строку как есть
        if isinstance(last_call, (datetime, date)):
            info += f"\n📞 Последний звонок: {last_call.strftime('%d.%m.%Y')}\n"
        else:
            info += f"\n📞 Последний звонок: {last_call}\n"
    else:
        info += f"\n📞 Последний звонок: Не записан\n"
    
    return info 