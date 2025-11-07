from telegram import ReplyKeyboardMarkup, KeyboardButton, Update
from telegram.ext import ConversationHandler, ContextTypes
from datetime import datetime

from commands.base_function import back_to_main_menu
from commands.rules_checker import check_rules_accepted
from data_base.db import session
from data_base.models import Student, ManualProgress, AutoProgress
from data_base.operations import get_student_by_fio_or_telegram
from utils.request_logger import log_request, log_conversation_handler

GET_TOPIC_DIRECTION = 1001

@log_request("get_new_topic_entry")
@check_rules_accepted
async def get_new_topic_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    student_telegram = f"@{update.message.from_user.username}"
    student = get_student_by_fio_or_telegram(student_telegram)
    if not student:
        await update.message.reply_text("❌ Вы не зарегистрированы как студент!")
        return await back_to_main_menu(update, context)

    if student.training_type.strip().lower() == "фуллстек":
        # Проверяем прогресс по обоим направлениям
        manual_progress = session.query(ManualProgress).filter_by(student_id=student.id).first()
        auto_progress = session.query(AutoProgress).filter_by(student_id=student.id).first()
        
        # Проверяем завершение ручного тестирования
        manual_completed = False
        if manual_progress:
            next_manual = get_next_manual_module(manual_progress)
            manual_completed = next_manual > 5
        
        # Проверяем завершение автотестирования
        auto_completed = False
        if auto_progress:
            auto_completed = auto_progress.m8_start_date
        
        # Если оба направления завершены
        if manual_completed and auto_completed:
            await update.message.reply_text("🎉 Поздравляем! Вы получили все доступные темы по обоим направлениям обучения!")
            return await back_to_main_menu(update, context)
        
        # Предлагаем выбор направления
        keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("Ручное тестирование")], [KeyboardButton("Автотестирование")]],
            resize_keyboard=True, one_time_keyboard=True
        )
        await update.message.reply_text(
            "Выберите направление, по которому хотите получить новую тему:",
            reply_markup=keyboard
        )
        return GET_TOPIC_DIRECTION
    else:
        return await handle_get_new_topic(update, context, direction=student.training_type)

@log_conversation_handler("get_new_topic_direction")
async def get_new_topic_direction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    direction = update.message.text.strip()
    if direction not in ["Ручное тестирование", "Автотестирование"]:
        await update.message.reply_text("❌ Выберите направление из предложенных.")
        return GET_TOPIC_DIRECTION
    return await handle_get_new_topic(update, context, direction=direction)

async def handle_get_new_topic(update: Update, context: ContextTypes.DEFAULT_TYPE, direction: str):
    student_telegram = f"@{update.message.from_user.username}"
    student = get_student_by_fio_or_telegram(student_telegram)
    if not student:
        await update.message.reply_text("❌ Вы не зарегистрированы как студент!")
        return await back_to_main_menu(update, context)

    if direction == "Ручное тестирование":
        return await handle_manual_direction(update, context, student)
    elif direction == "Автотестирование":
        return await handle_auto_direction(update, context, student)
    else:
        await update.message.reply_text("❌ Неизвестное направление.")
        return await back_to_main_menu(update, context)

def all_manual_module_submitted(progress: ManualProgress, module: int) -> bool:
    if module == 2:
        return bool(progress.m2_1_2_2_submission_date and progress.m2_3_3_1_submission_date)
    elif module == 3:
        return bool(progress.m3_2_submission_date and progress.m3_3_submission_date)
    elif module == 4:
        return bool(
            progress.m4_1_start_date and
            progress.m4_2_start_date and
            progress.m4_3_start_date and
            progress.m4_5_homework
        )
    return False

def get_next_manual_module(progress: ManualProgress) -> int:
    # Возвращает номер следующего модуля, который можно открыть
    if not progress.m1_start_date:
        return 1
    elif not (progress.m2_1_2_2_submission_date and progress.m2_3_3_1_submission_date):
        return 2
    elif not (progress.m3_2_submission_date and progress.m3_3_submission_date):
        return 3
    elif not (progress.m4_1_start_date and progress.m4_2_start_date and progress.m4_3_start_date):
        return 4
    elif not progress.m4_5_homework:
        return 4  # 4 модуль не завершен, пока не сдана домашняя работа по 4.5
    else:
        return 5  # 5 модуль доступен, если все темы 4 модуля начаты и домашняя работа по 4.5 сдана

MANUAL_MODULE_1_LINK = "https://thankful-candy-c57.notion.site/1-20594f774aab81db8392f01309905510?source=copy_link"

MANUAL_MODULE_2_LINKS = {
    "Тема 2.1": "https://thankful-candy-c57.notion.site/2-1-1df94f774aab8113b8d5ecb89cc6db75?source=copy_link",
    "Тема 2.2": "https://thankful-candy-c57.notion.site/2-2-1df94f774aab8184865ef8f5ae3fdc2e?source=copy_link",
    "Тема 2.3": "https://thankful-candy-c57.notion.site/2-3-1df94f774aab81a8a129e1bbd9cb11cd?source=copy_link",
}

MANUAL_MODULE_3_LINKS = {
    "Тема 3.1": "https://thankful-candy-c57.notion.site/3-1-API-1df94f774aab816a9530d320beea7bb9?source=copy_link",
    "Тема 3.2": "https://thankful-candy-c57.notion.site/3-2-1df94f774aab818ea9c3cc95d6e23445?source=copy_link",
    "Тема 3.3": "https://thankful-candy-c57.notion.site/3-3-SQL-20594f774aab816ca61fec3a416ecdc3?source=copy_link",
}

MANUAL_MODULE_4_LINKS = {
    "Тема 4.1": "https://thankful-candy-c57.notion.site/4-1-Devops-CI-CD-Docker-Kuber-20594f774aab81bfaf19cc22a4b7b577?source=copy_link",
    "Тема 4.2": "https://thankful-candy-c57.notion.site/4-2-Kafka-Rabbit-MQ-20594f774aab81f39be6f33280263a7a?source=copy_link",
    "Тема 4.3": "https://thankful-candy-c57.notion.site/4-3-Kibana-20594f774aab81428667e65f1ad8a20b?source=copy_link",
    "Тема 4.4": "https://thankful-candy-c57.notion.site/4-4-Git-20594f774aab81dbb3ecce447f1ca634?source=copy_link",
    "Тема 4.5": "https://thankful-candy-c57.notion.site/4-5-20c94f774aab80c48be5f0f09eb71152?source=copy_link",
    "Мок экзамен": "https://thankful-candy-c57.notion.site/4-5-20c94f774aab80c48be5f0f09eb71152?source=copy_link",
}

async def handle_manual_direction(update: Update, context, student: Student):
    progress = session.query(ManualProgress).filter_by(student_id=student.id).first()
    if not progress:
        progress = ManualProgress(student_id=student.id)
        session.add(progress)
        session.commit()

    next_module = get_next_manual_module(progress)

    # Проверка на завершение всех модулей
    if next_module > 5:
        await update.message.reply_text("🎉 Поздравляем! Вы получили все доступные темы по ручному тестированию!")
        return await back_to_main_menu(update, context)

    # --- Логика для 1 модуля ---
    if next_module == 1:
        if not progress.m1_start_date:
            progress.m1_start_date = datetime.now().date()
            session.commit()
            await update.message.reply_text("Вам открыт 1 модуль ручного тестирования! https://thankful-candy-c57.notion.site/1-20594f774aab81db8392f01309905510?source=copy_link")
            return await back_to_main_menu(update, context)
        # else: ничего не делаем, сразу идём дальше
    # --- Новая логика для 2 модуля ---
    if next_module == 2:
        theme_to_field = {
            "Тема 2.1": "m2_1_start_date",
            "Тема 2.2": "m2_2_start_date",
            "Тема 2.3": "m2_3_start_date",
        }
        for topic in list(theme_to_field.keys()):
            field = theme_to_field.get(topic)
            if field and not getattr(progress, field):
                setattr(progress, field, datetime.now().date())
                # Исключение: если это 2.3, также открываем 3.1
                if topic == "Тема 2.3" and not progress.m3_1_start_date:
                    progress.m3_1_start_date = datetime.now().date()
                    session.commit()
                    link_2_3 = MANUAL_MODULE_2_LINKS.get("Тема 2.3")
                    link_3_1 = MANUAL_MODULE_3_LINKS.get("Тема 3.1")
                    await update.message.reply_text(
                        f"Ваша новая тема: {topic}\nСсылка: {link_2_3}\n\n"
                        f"Также открыта тема 2.4!\nСсылка: https://thankful-candy-c57.notion.site/2-4-20594f774aab8197a077ef3921eaf641?source=copy_link\n\n"
                        f"Также открыта тема 3.1!\nСсылка: {link_3_1}"
                    )
                    return await back_to_main_menu(update, context)
                else:
                    session.commit()
                    link = MANUAL_MODULE_2_LINKS.get(topic)
                    await update.message.reply_text(f"Ваша новая тема: {topic}\nСсылка: {link}")
                    return await back_to_main_menu(update, context)
        else:
            # Если все темы 2 модуля уже начаты, проверяем готовность к 3 модулю
            if not progress.m1_homework:
                await update.message.reply_text("Чтобы получить темы 3 модуля, сдайте домашку по 1 модулю!")
                return await back_to_main_menu(update, context)
            elif not progress.m2_1_homework and not progress.m2_3_homework:
                await update.message.reply_text("Чтобы получить темы 3 модуля, сдайте домашки по 2 модулю!")
                return await back_to_main_menu(update, context)
            else:
                await update.message.reply_text("Все темы 2 модуля уже выданы. Сдайте темы ментору для получения тем 3 модуля.")
                return await back_to_main_menu(update, context)
        return await back_to_main_menu(update, context)
    # Для 3+ модулей проверяем сдачу предыдущего модуля
    if next_module > 2 and not all_manual_module_submitted(progress, next_module - 1):
        await update.message.reply_text(f"Чтобы получить новую тему, сдайте все темы и домашки по {next_module-1} модулю!")
        return await back_to_main_menu(update, context)

    # --- Новая логика для 3 модуля ---
    if next_module == 3:
        theme_to_field = {
            "Тема 3.1": "m3_1_start_date",
            "Тема 3.2": "m3_2_start_date",
            "Тема 3.3": "m3_3_start_date",
        }
        for topic in list(theme_to_field.keys()):
            field = theme_to_field.get(topic)
            if field and not getattr(progress, field):
                setattr(progress, field, datetime.now().date())
                session.commit()
                link = MANUAL_MODULE_3_LINKS.get(topic)
                await update.message.reply_text(f"Ваша новая тема: {topic}\nСсылка: {link}")
                return await back_to_main_menu(update, context)
        else:
            await update.message.reply_text("Чтобы получить новую тему, сдайте все темы и домашки по 3 модулю!")
            return await back_to_main_menu(update, context)
    # --- Конец новой логики ---
    # --- Новая логика для 4 модуля ---
    if next_module == 4:
        # Проверка оплаты и договора
        if student.training_type.strip().lower() == "фуллстек":
            # Для фуллстек-студентов проверяем 50% оплаты
            if student.total_cost and student.payment_amount:
                payment_percentage = (float(student.payment_amount) / float(student.total_cost)) * 100
                if payment_percentage < 50:
                    await update.message.reply_text(
                        f"Чтобы получить 4 модуль по ручному тестированию, оплатите минимум 50% от общей стоимости обучения!\n"
                        f"Ваша оплата: {student.payment_amount} руб. из {student.total_cost} руб. ({payment_percentage:.1f}%)"
                    )
                    return await back_to_main_menu(update, context)
            else:
                await update.message.reply_text("Чтобы получить 4 модуль по ручному тестированию, оплатите минимум 50% от общей стоимости обучения!")
                return await back_to_main_menu(update, context)
        else:
            # Для обычных студентов проверяем полную оплату
            if student.fully_paid != "Да":
                await update.message.reply_text("Чтобы получить 4 модуль, оплатите всю сумму за обучение!")
                return await back_to_main_menu(update, context)
        
        if not getattr(student, 'contract_signed', False):
            await update.message.reply_text("Чтобы получить 4 модуль, подпишите договор! Для получения договора обратитесь к @radosttvoyaa")
            return await back_to_main_menu(update, context)
        if not all_manual_module_submitted(progress, 3):
            await update.message.reply_text("Чтобы получить 4 модуль, сдайте все темы и домашки по 3 модулю!")
            return await back_to_main_menu(update, context)
        theme_to_field = {
            "Тема 4.1": "m4_1_start_date",
            "Тема 4.2": "m4_2_start_date",
            "Тема 4.3": "m4_3_start_date",
        }
        for topic in ["Тема 4.1", "Тема 4.2", "Тема 4.3"]:
            field = theme_to_field[topic]
            if field and not getattr(progress, field):
                setattr(progress, field, datetime.now().date())
                session.commit()
                link = MANUAL_MODULE_4_LINKS[topic]
                await update.message.reply_text(f"Ваша новая тема: {topic}\nСсылка: {link}")
                # Если это 4.3 — сразу выдаём только доп. темы
                if topic == "Тема 4.3":
                    # Автоматически устанавливаем даты старта для дополнительных тем
                    progress.m4_4_start_date = datetime.now().date()
                    progress.m4_5_start_date = datetime.now().date()
                    progress.m4_mock_exam_start_date = datetime.now().date()
                    session.commit()
                    await update.message.reply_text(
                        "Вы прошли основные темы 4 модуля! Вот дополнительные темы и экзамен:\n"
                        f"4.4: {MANUAL_MODULE_4_LINKS['Тема 4.4']}\n"
                        f"4.5: {MANUAL_MODULE_4_LINKS['Тема 4.5']}\n"
                    )
                return await back_to_main_menu(update, context)
        # Если дошли до сюда — значит 4.3 уже начата, выдаём все доп. темы сразу
        # Автоматически устанавливаем даты старта для дополнительных тем, если их нет
        # if not progress.m4_4_start_date:
        #     progress.m4_4_start_date = datetime.now().date()
        # if not progress.m4_5_start_date:
        #     progress.m4_5_start_date = datetime.now().date()
        # if not progress.m4_mock_exam_start_date:
        #     progress.m4_mock_exam_start_date = datetime.now().date()
        # session.commit()
        #
        # await update.message.reply_text(
        #     "Вы прошли основные темы 4 модуля! Вот дополнительные темы и экзамен:\n"
        #     f"4.4: {MANUAL_MODULE_4_LINKS['Тема 4.4']}\n"
        #     f"4.5: {MANUAL_MODULE_4_LINKS['Тема 4.5']}\n"
        #     f"Мок экзамен: {MANUAL_MODULE_4_LINKS['Мок экзамен']}"
        # )
        # Если у студента есть даты старта по всем темам 4 модуля, выдаём ссылку на 5 модуль
        # if all(getattr(progress, field, None) for field in ["m4_1_start_date", "m4_2_start_date", "m4_3_start_date"]):
        #     await update.message.reply_text(
        #         "Поздравляем! Вы завершили 4 модуль. Вот ссылка на 5 модуль:\n"
        #         "https://thankful-candy-c57.notion.site/5-20594f774aab81518d87db6edddd068e?source=copy_link"
        #     )
        # return await back_to_main_menu(update, context)
        
        # Если все темы 4 модуля уже выданы, но не сдана домашка 4.5
        if not progress.m4_5_homework:
            await update.message.reply_text("Чтобы получить 5 модуль, отправьте домашку по теме 4.5!")
            return await back_to_main_menu(update, context)
        else:
            await update.message.reply_text("Все темы 4 модуля уже выданы. Сдайте домашку по теме 4.5 для получения 5 модуля.")
            return await back_to_main_menu(update, context)
    # --- Конец новой логики ---
    # --- Новая логика для 5 модуля ---
    if next_module == 5:
        progress = session.query(ManualProgress).filter_by(student_id=student.id).first()
        from data_base.models import Homework
        homework_45 = session.query(Homework).filter_by(student_id=student.id, topic="Тема 4.5").first()
        
        # Сначала проверяем домашку 4.5
        if not homework_45:
            await update.message.reply_text("Чтобы получить 5 модуль, обязательно отправьте домашку по теме 4.5!")
            return await back_to_main_menu(update, context)
        
        # Потом проверяем остальные условия
        if not (
            progress.m4_1_submission_date and
            progress.m4_2_4_3_submission_date and
            progress.m4_5_homework and
            progress.m4_mock_exam_passed_date
        ):
            await update.message.reply_text(
                "Чтобы получить 5 модуль, нужно:\n"
                "- сдать тему 4.1\n"
                "- сдать темы 4.2 и 4.3\n"
                "- отправить домашку по теме 4.5\n"
                "- сдать мок экзамен по 4 модулю"
            )
            return await back_to_main_menu(update, context)
        
        # Проставляем дату получения 5 модуля
        progress.m5_start_date = datetime.now().date()
        session.commit()
        await update.message.reply_text(
            "Поздравляем! Вы завершили 4 модуль. Вот ссылка на 5 модуль:\n"
            "https://thankful-candy-c57.notion.site/5-20594f774aab81518d87db6edddd068e?source=copy_link\n"
            "А так же ознакомьтесь с правилами дискорда, где вы будете получать помощь на собесе\n"
            "https://elite-church-268.notion.site/256342f79ae780d09d9fd5d0185dd684?source=copy_link"
        )
        return await back_to_main_menu(update, context)

# Ссылки на модули автотестирования
AUTO_MODULE_LINKS = {
    1: "https://thankful-candy-c57.notion.site/1-12794f774aab804fa485d54e333f7918?source=copy_link",
    2: "https://thankful-candy-c57.notion.site/2-Python-AQA-26f9629adcbb4cb49c74592a1ba2f66c?source=copy_link",
    3: "https://thankful-candy-c57.notion.site/3-Python-24f94f774aab808c9909d9d7fee3ead8?source=copy_link",
    4: "https://thankful-candy-c57.notion.site/4-12494f774aab80a180a5feda380ca76b?source=copy_link",
    5: "https://thankful-candy-c57.notion.site/5-16b94f774aab800f91acd78f1d488d0a?source=copy_link",
    6: "https://thankful-candy-c57.notion.site/6-13e94f774aab807bb68bc31f5f5bc482?source=copy_link",
    7: "https://thankful-candy-c57.notion.site/7-13e94f774aab8011b6bee07977107598?source=copy_link",
    8: "https://thankful-candy-c57.notion.site/8-aea202400ee44aedaa7f42a01bc484b4?source=copy_link",
}

async def handle_auto_direction(update, context, student):
    progress = session.query(AutoProgress).filter_by(student_id=student.id).first()
    if not progress:
        progress = AutoProgress(student_id=student.id)
        session.add(progress)
        session.commit()

    # Проверка на завершение всех модулей автотестирования
    if progress.m8_start_date:
        await update.message.reply_text("🎉 Поздравляем! Вы получили все доступные темы по автотестированию!")
        return await back_to_main_menu(update, context)

    # 1 модуль: просто открыть, если не открыт
    if not progress.m1_start_date:
        progress.m1_start_date = datetime.now().date()
        progress.m2_start_date = datetime.now().date()  # Сразу открыть 2 модуль
        session.commit()
        await update.message.reply_text(
            f"Вам открыт 1 модуль автотестирования!\nСсылка: {AUTO_MODULE_LINKS[1]}\n\n"
            f"Вам открыт 2 модуль автотестирования!\nСсылка: {AUTO_MODULE_LINKS[2]}"
        )
        return await back_to_main_menu(update, context)

    # 2 модуль: экзамен сдаётся отдельно
    if progress.m1_start_date and progress.m2_start_date and not progress.m2_exam_passed_date:
        await update.message.reply_text("Сдайте экзамен по 2 модулю, чтобы двигаться дальше!")
        return await back_to_main_menu(update, context)

    # 3 модуль: открыт, если 2 экзамен сдан
    if progress.m2_exam_passed_date and not progress.m3_start_date:
        progress.m3_start_date = datetime.now().date()
        session.commit()
        await update.message.reply_text(f"Вам открыт 3 модуль автотестирования!\nСсылка: {AUTO_MODULE_LINKS[3]}")
        return await back_to_main_menu(update, context)
    if progress.m3_start_date and not progress.m3_exam_passed_date:
        await update.message.reply_text("Сдайте экзамен по 3 модулю, чтобы двигаться дальше!")
        return await back_to_main_menu(update, context)

    # 4-7 модули: открывать по очереди, сдача темы
    for i in range(4, 8):
        start_date = getattr(progress, f"m{i}_start_date")
        passed_date = getattr(progress, f"m{i}_topic_passed_date")
        if not start_date:
            # Проверка: предыдущий модуль должен быть сдан
            prev_passed = getattr(progress, f"m{i-1}_topic_passed_date") if i > 4 else progress.m3_exam_passed_date
            if prev_passed:
                setattr(progress, f"m{i}_start_date", datetime.now().date())
                session.commit()
                await update.message.reply_text(f"Вам открыт {i} модуль автотестирования!\nСсылка: {AUTO_MODULE_LINKS[i]}")
                return await back_to_main_menu(update, context)
            else:
                await update.message.reply_text(f"Сдайте предыдущий модуль, чтобы открыть {i} модуль!")
                return await back_to_main_menu(update, context)
        if start_date and not passed_date:
            await update.message.reply_text(f"Сдайте тему {i} модуля, чтобы двигаться дальше!")
            return await back_to_main_menu(update, context)

    # 8 модуль: открыть, если 7 сдан
    if progress.m7_topic_passed_date and not progress.m8_start_date:
        progress.m8_start_date = datetime.now().date()
        session.commit()
        await update.message.reply_text(f"Вам открыт 8 модуль автотестирования!\nСсылка: {AUTO_MODULE_LINKS[8]}\n"
        "А так же ознакомьтесь с правилами дискорда, где вы будете получать помощь на собесе\n"
        "https://elite-church-268.notion.site/256342f79ae780d09d9fd5d0185dd684?source=copy_link")
        return await back_to_main_menu(update, context)
    if progress.m8_start_date:
        await update.message.reply_text("Вы прошли все модули автотестирования!")
        return await back_to_main_menu(update, context)
