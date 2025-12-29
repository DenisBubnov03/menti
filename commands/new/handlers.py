# commands/submit_topic/handlers.py
from classes.salary_manager import SalaryManager
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime, date
from sqlalchemy import text

from commands.base_function import back_to_main_menu
from commands.states import SUBMIT_TOPIC_SELECT, SUBMIT_TOPIC_STUDENTS
from data_base.db import session
from data_base.models import Student, Mentor, Homework, ManualProgress, AutoProgress
from utils.request_logger import log_request, log_conversation_handler

""" При изменении маппинга, поменять их и в боте админа"""

TOPIC_FIELD_MAPPING = {
    "1 модуль": "m1_submission_date",
    "Тема 2.1 + 2.2": "m2_1_2_2_submission_date",
    "Тема 2.3 + 3.1": "m2_3_3_1_submission_date",
    "Тема 3.2": "m3_2_submission_date",
    "Тема 3.3": "m3_3_submission_date",
    "Тема 4.1": "m4_1_submission_date",
    "Тема 4.2 + 4.3": "m4_2_4_3_submission_date",
    "Мок экзамен 4 модуля": "m4_mock_exam_passed_date",
}

AUTO_MODULE_FIELD_MAPPING = {
    "Сдача 2 модуля": "m2_exam_passed_date",
    "Сдача 3 модуля": "m3_exam_passed_date",
    "Сдача 4 модуля": "m4_topic_passed_date",
    "Сдача 5 модуля": "m5_topic_passed_date",
    "Сдача 6 модуля": "m6_topic_passed_date",
    "Сдача 7 модуля": "m7_topic_passed_date",
}


@log_request("start_topic_submission")
async def start_topic_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор темы (уже с модулем)"""
    mentor_tg = "@" + update.message.from_user.username
    mentor = session.query(Mentor).filter_by(telegram=mentor_tg).first()
    if not mentor:
        await update.message.reply_text("❌ Вы не зарегистрированы как ментор.")
        return await back_to_main_menu(update, context)

    if "автотестирование" in mentor.direction.lower():
        # Авто-флоу: выбор модуля 2-7
        auto_modules = [f"Сдача {i} модуля" for i in range(2, 8)]
        keyboard = [[KeyboardButton(name)] for name in auto_modules]
        keyboard.append([KeyboardButton("🔙 Вернуться в меню")])
        await update.message.reply_text(
            "Выберите модуль автотестирования, который сдал студент:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        context.user_data["auto_flow"] = True
        return SUBMIT_TOPIC_SELECT
    else:
        # Ручной флоу (старый)
        keyboard = [[KeyboardButton(name)] for name in TOPIC_FIELD_MAPPING.keys()]
        keyboard.append([KeyboardButton("🔙 Вернуться в меню")])
        await update.message.reply_text(
            "Выберите тему, которую сдаёт студент:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        context.user_data["auto_flow"] = False
        return SUBMIT_TOPIC_SELECT


@log_conversation_handler("select_topic")
async def select_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    if user_input == "🔙 Вернуться в меню":
        return await back_to_main_menu(update, context)
    if context.user_data.get("auto_flow"):
        auto_modules = [f"Сдача {i} модуля" for i in range(2, 8)]
        if user_input not in auto_modules:
            keyboard = [[KeyboardButton(name)] for name in auto_modules]
            keyboard.append([KeyboardButton("🔙 Вернуться в меню")])
            await update.message.reply_text(
                "❌ Выберите модуль из списка или нажмите 'Вернуться в меню':",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return SUBMIT_TOPIC_SELECT
        context.user_data["selected_auto_module"] = int(user_input.split()[1])
        await update.message.reply_text(
            "Введите Telegram юзернеймы студентов через запятую (например: @user1, @user2):")
        return SUBMIT_TOPIC_STUDENTS
    else:
        if user_input not in TOPIC_FIELD_MAPPING:
            keyboard = [[KeyboardButton(name)] for name in TOPIC_FIELD_MAPPING.keys()]
            keyboard.append([KeyboardButton("🔙 Вернуться в меню")])
            await update.message.reply_text(
                "❌ Выберите нужную тему из списка или нажмите 'Вернуться в меню':",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return SUBMIT_TOPIC_SELECT
        context.user_data["selected_topic_label"] = user_input
        await update.message.reply_text(
            "Введите Telegram юзернеймы студентов через запятую (например: @user1, @user2):")
        return SUBMIT_TOPIC_STUDENTS


@log_conversation_handler("submit_topic_students")
async def submit_topic_students(update: Update, context: ContextTypes.DEFAULT_TYPE):
    salary_manager = SalaryManager()
    usernames = [u.strip() for u in update.message.text.split(",")]
    mentor_tg = "@" + update.message.from_user.username
    TARGET_DATE = date(2025, 12, 1)

    mentor = session.query(Mentor).filter_by(telegram=mentor_tg).first()
    if not mentor:
        await update.message.reply_text("❌ Вы не зарегистрированы как ментор.")
        return await back_to_main_menu(update, context)

    # === МАППИНГ ПОЛЕЙ МЕНТОРОВ (ВАРИАНТ 3: ИМЕННАЯ МЕТКА) ===
    AUTO_MENTOR_FIELDS = {
        'm2_exam_passed_date': 'm2_exam_mentor_id',
        'm3_exam_passed_date': 'm3_exam_mentor_id',
        'm4_topic_passed_date': 'm4_topic_mentor_id',
        'm5_topic_passed_date': 'm5_topic_mentor_id',
        'm6_topic_passed_date': 'm6_topic_mentor_id',
        'm7_topic_passed_date': 'm7_topic_mentor_id'
    }

    MANUAL_MENTOR_FIELDS = {
        'm1_submission_date': 'm1_mentor_id',
        'm2_1_2_2_submission_date': 'm2_1_2_2_mentor_id',
        'm2_3_3_1_submission_date': 'm2_3_3_1_mentor_id',
        'm3_2_submission_date': 'm3_2_mentor_id',
        'm3_3_submission_date': 'm3_3_mentor_id',
        'm4_1_submission_date': 'm4_1_mentor_id',
        'm4_2_4_3_submission_date': 'm4_2_4_3_mentor_id',
        'm4_mock_exam_passed_date': 'm4_mock_exam_mentor_id'
    }

    found = []
    not_found = []
    already_submitted = []

    # ---------------- АВТО ФЛОУ ----------------
    if context.user_data.get("auto_flow"):
        auto_modules = [f"Сдача {i} модуля" for i in range(2, 8)]
        selected_label = None
        for label in auto_modules:
            if context.user_data.get("selected_auto_module") == int(label.split()[1]):
                selected_label = label
                break

        field = AUTO_MODULE_FIELD_MAPPING.get(selected_label)

        for username in usernames:
            student = session.query(Student).filter_by(telegram=username).first()
            if student:
                if student.auto_mentor_id != mentor.id:
                    not_found.append(username + " (не ваш студент)")
                    continue

                progress = session.query(AutoProgress).filter_by(student_id=student.id).first()
                if not progress:
                    progress = AutoProgress(student_id=student.id)
                    session.add(progress)

                # 🔥 НОВАЯ ЛОГИКА: Проверка, является ли это первой активностью в Авто
                # Проверяем все поля автотестирования. Если все они None - значит это первая сдача.
                all_auto_fields = AUTO_MODULE_FIELD_MAPPING.values()
                has_any_progress = any(getattr(progress, f) is not None for f in all_auto_fields)
                is_first_activity = not has_any_progress

                if field and hasattr(progress, field):
                    current_date = getattr(progress, field)
                    if current_date:
                        existing_date = current_date.strftime("%d.%m.%Y") if hasattr(current_date, 'strftime') else str(
                            current_date)
                        already_submitted.append(f"{username} (сдал {existing_date})")
                        continue

                    # 1. Ставим дату
                    setattr(progress, field, datetime.now().date())

                    # 2. Ставим метку ментора
                    mentor_field_name = AUTO_MENTOR_FIELDS.get(field)
                    if mentor_field_name and hasattr(progress, mentor_field_name):
                        setattr(progress, mentor_field_name, mentor.id)

                    # 3. Бонус директору (ID 3)
                    # Условие: Фуллстек + Это ПЕРВАЯ активность в авто-направлении + Ментор не сам директор
                    if student.training_type and student.training_type.strip().lower() == "фуллстек" and is_first_activity and student.auto_mentor_id != 3:
                        try:
                            salary_manager.calculate_bonus_dir(
                                session=session,
                                mentor_id=3,
                                telegram=student.telegram,
                                student_id=student.id
                            )
                        except Exception as e:
                            print(f"Warn: failed to create director auto bonus for {username}: {e}")

                    # 4. Комиссия за тему
                    if student.start_date >= TARGET_DATE or (
                            student.training_type == 'Фуллстек' and student.start_date >= date(2025, 9, 1)):
                        try:
                            salary_manager.create_commission_for_auto_task(
                                session=session,
                                mentor_id=student.auto_mentor_id,
                                telegram=student.telegram,
                                topic_name=selected_label,
                                student_id=student.id
                            )
                        except Exception as e:
                            print(f"Warn: failed to create auto commission for {username}: {e}")

                    # Дублирование для фуллстека
                    if student.training_type and student.training_type.strip().lower() == "фуллстек":
                        try:
                            session.execute(
                                text(
                                    """
                                    INSERT INTO fullstack_topic_assignments (student_id, mentor_id, topic_manual, topic_auto, assigned_at)
                                    VALUES (:student_id, :mentor_id, NULL, :topic_auto, NOW())
                                    """
                                ),
                                {
                                    "student_id": student.id,
                                    "mentor_id": mentor.id,
                                    "topic_auto": selected_label,
                                },
                            )
                        except Exception:
                            print(f"Warn: failed to insert auto assignment for {username}")

                    found.append(username)
            else:
                not_found.append(username + " (не найден)")

        session.commit()

        msg_parts = []
        if found: msg_parts.append(f"✅ Модуль сдан: {', '.join(found)}")
        if already_submitted: msg_parts.append(f"ℹ️ Уже отмечены: {', '.join(already_submitted)}")
        if not_found: msg_parts.append(f"⚠️ Проблемы: {', '.join(not_found)}")
        await update.message.reply_text("\n".join(msg_parts) if msg_parts else "ℹ️ Нет студентов")
        return await back_to_main_menu(update, context)

    # ---------------- РУЧНОЙ ФЛОУ ----------------
    else:
        usernames = [u.strip() for u in update.message.text.split(",")]
        topic = context.user_data["selected_topic_label"]
        field_name = TOPIC_FIELD_MAPPING.get(topic)
        now = datetime.now().date()
        found = []
        not_found = []
        already_submitted = []

        for username in usernames:
            student = session.query(Student).filter_by(telegram=username).first()
            if student:
                if not (student.mentor_id == mentor.id or student.auto_mentor_id == mentor.id):
                    not_found.append(username + " (не ваш студент)")
                    continue

                progress = session.query(ManualProgress).filter_by(student_id=student.id).first()
                if progress and field_name and hasattr(progress, field_name):

                    # 🔥 НОВАЯ ЛОГИКА: Проверка, является ли это первой активностью в Ручном
                    # Проверяем все поля ручного прогресса ДО записи текущей даты.
                    all_manual_fields = TOPIC_FIELD_MAPPING.values()
                    has_any_progress = any(getattr(progress, f) is not None for f in all_manual_fields)
                    is_first_activity = not has_any_progress

                    current_date = getattr(progress, field_name)
                    if current_date:
                        existing_date = current_date.strftime("%d.%m.%Y") if hasattr(current_date, 'strftime') else str(
                            current_date)
                        already_submitted.append(f"{username} (сдал {existing_date})")
                        continue

                    # 1. Ставим дату
                    setattr(progress, field_name, now)

                    # 2. Ставим метку ментора
                    mentor_field_name = MANUAL_MENTOR_FIELDS.get(field_name)
                    if mentor_field_name and hasattr(progress, mentor_field_name):
                        setattr(progress, mentor_field_name, mentor.id)

                    # 3. Бонус директору (ID 1)
                    # Условие: Фуллстек + ПЕРВАЯ активность в ручном + Ментор не сам директор
                    if student.training_type and student.training_type.strip().lower() == "фуллстек" and is_first_activity and student.mentor_id != 1:
                        try:
                            salary_manager.calculate_bonus_dir(
                                session=session,
                                mentor_id=1,
                                telegram=student.telegram,
                                student_id=student.id
                            )
                        except Exception as e:
                            print(f"Warn: failed to create director manual bonus for {username}: {e}")

                    # Обновляем звонок
                    student.last_call_date = now

                    # 4. Комиссия
                    if student.start_date >= TARGET_DATE or (
                            student.training_type == 'Фуллстек' and student.start_date >= date(2025, 9, 1)):
                        try:
                            salary_manager.create_commission_for_manual_task(
                                session=session,
                                mentor_id=mentor.id,
                                telegram=student.telegram,
                                topic_name=topic,
                                student_id=student.id
                            )
                        except Exception as e:
                            print(f"Warn: failed to create manual commission for {username}: {e}")

                    # Дублирование для фуллстека
                    if student.training_type and student.training_type.strip().lower() == "фуллстек":
                        try:
                            session.execute(
                                text(
                                    """
                                    INSERT INTO fullstack_topic_assignments (student_id, mentor_id, topic_manual, topic_auto, assigned_at)
                                    VALUES (:student_id, :mentor_id, :topic_manual, NULL, NOW())
                                    """
                                ),
                                {
                                    "student_id": student.id,
                                    "mentor_id": mentor.id,
                                    "topic_manual": topic,
                                },
                            )
                        except Exception:
                            print(f"Warn: failed to insert manual assignment for {username}")

                    found.append(username)
                else:
                    not_found.append(username + " (нет поля)")
            else:
                not_found.append(username + " (не найден)")

        session.commit()

        msg_parts = []
        if found: msg_parts.append(f"✅ Дата сдачи темы '{topic}' проставлена: {', '.join(found)}")
        if already_submitted: msg_parts.append(f"ℹ️ Уже сдали тему '{topic}': {', '.join(already_submitted)}")
        if not_found: msg_parts.append(f"⚠️ Проблемы: {', '.join(not_found)}")
        await update.message.reply_text("\n".join(msg_parts) if msg_parts else "ℹ️ Нет студентов")
        return await back_to_main_menu(update, context)