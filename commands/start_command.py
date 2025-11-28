from datetime import datetime

from commands.homework_mentor import *
from data_base.models import Mentor, ManualProgress
from data_base.operations import is_mentor, get_student_by_fio_or_telegram, is_admin
from telegram import  ReplyKeyboardMarkup, KeyboardButton, Update
from telegram.ext import ContextTypes
from data_base.db import session
from data_base.models import Student, ManualProgress, AutoProgress
from commands.get_new_topic import MANUAL_MODULE_2_LINKS, MANUAL_MODULE_3_LINKS, MANUAL_MODULE_4_LINKS, \
    AUTO_MODULE_LINKS, MANUAL_MODULE_1_LINK
from utils.request_logger import log_request


@log_request("start_command")
async def start_command(update, context):
    message = update.message
    username = str(message.from_user.username)

    # Добавляем подробное логирование
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"=== START COMMAND ===")
    logger.info(f"Chat ID: {message.chat_id}")
    logger.info(f"Original username: {message.from_user.username}")
    logger.info(f"User ID: {message.from_user.id}")
    logger.info(f"Full name: {message.from_user.full_name}")

    # Добавляем @, если его нет
    if not username.startswith("@"):
        username = "@" + username  # ← Переопределяем username
    
    logger.info(f"Final username: {username}")
    chat_id = message.chat_id  # Получаем chat_id

    logger.info(f"Checking if user is admin...")
    if is_admin(username):  # Проверяем, админ ли это
        logger.info(f"User is ADMIN")
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton("📹 Создание встречи")],
                [KeyboardButton("💰 Платежи")],
                [KeyboardButton("📚 Домашние задания")],
                [KeyboardButton("📌 Подтверждение сдачи темы")],
                [KeyboardButton("📊 Проверить успеваемость")],
                [KeyboardButton("➕ Добавить ментора")],
                [KeyboardButton("📢 Сделать рассылку")],
                [KeyboardButton("🗑 Удалить ментора")]
                # [KeyboardButton("📅 Записи на звонки")],
            ],
            resize_keyboard=True
        )
        await update.message.reply_text("🔹 Вы вошли как админ-ментор. Выберите действие:", reply_markup=keyboard)
        return

    # Проверяем, ментор ли это
    logger.info(f"Checking if user is mentor...")
    if is_mentor(username):
        logger.info(f"User is MENTOR")
        mentor = session.query(Mentor).filter(Mentor.telegram == username).first()
        if mentor:
            if not mentor.chat_id:
                # Обновляем chat_id в отдельной сессии
                from data_base.db import get_session, close_session
                update_session = get_session()
                try:
                    mentor_update = update_session.query(Mentor).filter(Mentor.id == mentor.id).first()
                    if mentor_update:
                        mentor_update.chat_id = chat_id
                        update_session.commit()
                        logger.info(f"Updated chat_id for mentor {mentor.id}")
                except Exception as e:
                    logger.error(f"Error updating mentor chat_id: {e}")
                    update_session.rollback()
                finally:
                    close_session()
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton("📚 Домашние задания")],
                [KeyboardButton("📌 Подтверждение сдачи темы")],
                [KeyboardButton("📹 Создание встречи")],
                    # [KeyboardButton("📅 Записи на звонки")],
                [KeyboardButton("📊 Проверить успеваемость")],
            ],
            resize_keyboard=True
        )
        await update.message.reply_text("🔹 Вы вошли как ментор. Выберите действие:", reply_markup=keyboard)
        return

    # Проверяем, студент ли это
    logger.info(f"Checking if user is student...")
    logger.info(f"Searching for student with username: {username}")
    student = get_student_by_fio_or_telegram(username)
    logger.info(f"Student found: {student is not None}")
    if student:
        # Обновляем chat_id студента, если он отсутствует
        if not student.chat_id:
            # Обновляем chat_id в отдельной сессии
            from data_base.db import get_session, close_session
            update_session = get_session()
            try:
                student_update = update_session.query(Student).filter(Student.id == student.id).first()
                if student_update:
                    student_update.chat_id = chat_id
                    update_session.commit()
                    logger.info(f"Updated chat_id for student {student.id} ({student.telegram})")
            except Exception as e:
                logger.error(f"Error updating student chat_id: {e}")
                update_session.rollback()
            finally:
                close_session()
        
        # Проверяем, принял ли студент правила
        if not student.rules_accepted:
            logger.info(f"Student {student.id} has not accepted rules, showing rules")
            from commands.rules_acceptance import show_rules
            return await show_rules(update, context)
        logger.info(f"Student details: ID={student.id}, FIO={student.fio}, Telegram={student.telegram}")
        if not student.chat_id:
            # Обновляем chat_id в отдельной сессии
            from data_base.db import get_session, close_session
            update_session = get_session()
            try:
                student_update = update_session.query(Student).filter(Student.id == student.id).first()
                if student_update:
                    student_update.chat_id = chat_id
                    update_session.commit()
                    logger.info(f"Updated chat_id for student {student.id}")
            except Exception as e:
                logger.error(f"Error updating chat_id: {e}")
                update_session.rollback()
            finally:
                close_session()
            # Получаем актуальных менторов студента
        mentor = session.query(Mentor).get(student.mentor_id) if student.mentor_id else None
        auto_mentor = session.query(Mentor).get(getattr(student, 'auto_mentor_id', None)) if getattr(student, 'auto_mentor_id', None) else None

        training_type = student.training_type.strip().lower() if student.training_type else ""
        mentor_info = ""

        if training_type == "фуллстек":
            mentor_info = "\n👨‍🏫 Менторы для ваших направлений:\n"
            
            # Проверяем telegram менторов
            manual_telegram = ""
            if mentor and hasattr(mentor, 'telegram'):
                if isinstance(mentor.telegram, tuple):
                    manual_telegram = mentor.telegram[0]
                else:
                    manual_telegram = mentor.telegram
            
            auto_telegram = ""
            if auto_mentor and hasattr(auto_mentor, 'telegram'):
                if isinstance(auto_mentor.telegram, tuple):
                    auto_telegram = auto_mentor.telegram[0]
                else:
                    auto_telegram = auto_mentor.telegram
            
            mentor_info += f"💼 Ручное тестирование: {mentor.full_name if mentor else 'Не назначен'} {manual_telegram}\n"
            mentor_info += f"💻 Автотестирование: {auto_mentor.full_name if auto_mentor else 'Не назначен'} {auto_telegram}"
        elif training_type == "ручное тестирование":
            # Исправление: проверяем telegram ментора
            mentor_telegram = ""
            if mentor and hasattr(mentor, 'telegram'):
                if isinstance(mentor.telegram, tuple):
                    mentor_telegram = mentor.telegram[0]
                else:
                    mentor_telegram = mentor.telegram
            
            mentor_info = f"\n👨‍🏫 Ваш ментор по ручному тестированию: {mentor.full_name if mentor else 'Не назначен'} {mentor_telegram}"
        elif training_type == "автотестирование":
            # Исправление: проверяем telegram ментора
            auto_telegram = ""
            if auto_mentor and hasattr(auto_mentor, 'telegram'):
                if isinstance(auto_mentor.telegram, tuple):
                    auto_telegram = auto_mentor.telegram[0]
                else:
                    auto_telegram = auto_mentor.telegram
            
            mentor_info = f"\n👨‍🏫 Ваш ментор по автотестированию: {auto_mentor.full_name if auto_mentor else 'Не назначен'} {auto_telegram}"
        else:
            mentor_info = "\n⚠ Обратите внимание: У вас не указан тип обучения."

        keyboard_buttons = [
            [KeyboardButton("🆕 Получить новую тему")],
            [KeyboardButton("🐛 Бесконечные баги")],
        ]

        # Добавляем кнопку "Отправить домашку" только для ручного тестирования и фуллстеков
        if student.training_type in ["Ручное тестирование", "Фуллстек"]:
            keyboard_buttons.append([KeyboardButton("📚 Отправить домашку")])

        # Добавляем кнопку "Запросить назначение куратора" для фуллстеков, если не назначен какой-либо куратор
        if training_type == "фуллстек" and (not mentor or not auto_mentor):
            keyboard_buttons.append([KeyboardButton("👨‍🏫 Запросить назначение куратора")])

        keyboard_buttons.extend([
            [KeyboardButton("📜 Мои темы и ссылки")],
            #[KeyboardButton("📅 Записаться на звонок")],
            [KeyboardButton("💳 Оплата за обучение")],
            [KeyboardButton("💸 Выплата комиссии")],
            [KeyboardButton("📋 Правила")],
        ])

        keyboard = ReplyKeyboardMarkup(keyboard_buttons, resize_keyboard=True)
        
        # Добавляем retry логику для отправки сообщения
        max_retries = 3
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                # Логируем для отладки
                logger.info(f"DEBUG: student={student}, type={type(student)}")
                logger.info(f"DEBUG: student.fio={getattr(student, 'fio', None)}, type={type(getattr(student, 'fio', None))}")

                # Исправление: если student — кортеж, берём первый элемент
                if isinstance(student, tuple):
                    fio_value = student[0]
                elif hasattr(student, 'fio'):
                    fio_value = student.fio
                else:
                    fio_value = str(student)

                # Проверяем, что ФИО не пустое и не точка
                if not fio_value or fio_value.strip() in [".", ""]:
                    fio_value = "Студент"  # Используем дефолтное значение
                else:
                    fio_value = fio_value.strip()  # Убираем лишние пробелы

                await update.message.reply_text(f"🔹 Привет, {fio_value}! Вы вошли как ученик. Для сдачи тем необходим куратор, если он у вас не назначен, отправьте команду 'Запросить назначение куратора' из меню бота, и выберете необходимого куратора.{mentor_info}",
                                                reply_markup=keyboard)
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    import asyncio
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Попытка {attempt + 1} отправки сообщения не удалась: {e}. Повтор через {retry_delay}с")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Экспоненциальная задержка
                else:
                    # Последняя попытка не удалась
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Не удалось отправить сообщение после {max_retries} попыток: {e}")
                    # Пытаемся отправить простое сообщение без клавиатуры
                    try:
                        await update.message.reply_text("🔹 Привет! Произошла ошибка при загрузке меню. Попробуйте еще раз.")
                    except Exception as final_error:
                        logger.error(f"Не удалось отправить даже простое сообщение: {final_error}")
                        # Не поднимаем исключение, чтобы бот не падал
                    return


@log_request("my_topics_and_links")
async def my_topics_and_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    student_telegram = f"@{update.message.from_user.username}"
    student = session.query(Student).filter_by(telegram=student_telegram).first()
    if not student:
        await update.message.reply_text("❌ Вы не зарегистрированы как студент!")
        return
    msg = []
    # Ручное тестирование
    if student.training_type.lower().startswith("ручн") or student.training_type.lower().startswith("фулл"):
        progress = session.query(ManualProgress).filter_by(student_id=student.id).first()
        if progress:
            msg.append("<b>Ручное тестирование:</b>")
            # 1 модуль
            if progress.m1_start_date:
                msg.append(f" Доп модуль:\n"
                           f"AI: https://cyber-liver-416.notion.site/AI-2b53f89d012f80da9620e622079962cd\n"
                           f"- Тема 1: {MANUAL_MODULE_1_LINK}")
            # 2 модуль
            if progress.m2_1_start_date:
                msg.append(f"- Тема 2.1: {MANUAL_MODULE_2_LINKS.get('Тема 2.1', '-')}")
            if progress.m2_2_start_date:
                msg.append(f"- Тема 2.2: {MANUAL_MODULE_2_LINKS.get('Тема 2.2', '-')}")
            if progress.m2_3_start_date:
                msg.append(
                    f"- Тема 2.3: {MANUAL_MODULE_2_LINKS.get('Тема 2.3', '-')}\n"
                    f"- Тема 2.4: https://thankful-candy-c57.notion.site/2-4-20594f774aab8197a077ef3921eaf641?source=copy_link"
                )
            # 3 модуль
            if progress.m3_1_start_date:
                msg.append(f"- Тема 3.1: {MANUAL_MODULE_3_LINKS.get('Тема 3.1', '-')}")
            if progress.m3_2_start_date:
                msg.append(f"- Тема 3.2: {MANUAL_MODULE_3_LINKS.get('Тема 3.2', '-')}")
            if progress.m3_3_start_date:
                msg.append(f"- Тема 3.3: {MANUAL_MODULE_3_LINKS.get('Тема 3.3', '-')}")
            # 4 модуль
            if progress.m4_1_start_date:
                msg.append(f"- Тема 4.1: {MANUAL_MODULE_4_LINKS.get('Тема 4.1', '-')}")
            if progress.m4_2_start_date:
                msg.append(f"- Тема 4.2: {MANUAL_MODULE_4_LINKS.get('Тема 4.2', '-')}")
            if progress.m4_3_start_date:
                msg.append(f"- Тема 4.3: {MANUAL_MODULE_4_LINKS.get('Тема 4.3', '-')}")
            # Доп. темы 4 модуля
            if getattr(progress, 'm4_4_start_date', None):
                msg.append(f"- Тема 4.4: {MANUAL_MODULE_4_LINKS.get('Тема 4.4', '-')}")
            if getattr(progress, 'm4_5_start_date', None):
                msg.append(f"- Тема 4.5: {MANUAL_MODULE_4_LINKS.get('Тема 4.5', '-')}")
            if getattr(progress, 'm4_mock_exam_start_date', None):
                msg.append(f"- Мок экзамен: {MANUAL_MODULE_4_LINKS.get('Мок экзамен','-')}")
    # Автотестирование
    if student.training_type.lower().startswith("авто") or student.training_type.lower().startswith("фулл"):
        progress = session.query(AutoProgress).filter_by(student_id=student.id).first()
        if progress:
            msg.append("\n<b>Автотестирование:</b>")
            for i in range(1, 9):
                if getattr(progress, f"m{i}_start_date", None):
                    msg.append(f"- Модуль {i}: {AUTO_MODULE_LINKS.get(i,'-')}")
    if not msg:
        await update.message.reply_text("У вас пока нет открытых тем.")
    else:
        await update.message.reply_text("\n".join(msg), parse_mode="HTML")
