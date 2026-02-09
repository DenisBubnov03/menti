from telegram import ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ConversationHandler, MessageHandler, filters

from commands.base_function import back_to_main_menu
from data_base.operations import get_student_by_fio_or_telegram
from data_base.models import Student, Homework, ManualProgress, AutoProgress
from data_base.db import session
from commands.states import STUDENT_PROGRESS_WAITING
from datetime import datetime, date

# --- ПОЛНАЯ КОНФИГУРАЦИЯ ТЕМ (СТРОГО ПО ТВОЕМУ MODELS.PY) ---
MODULES_TOPICS = {
    "Ручное тестирование": {
        "Модуль 1": ["Тема 1.4"],
        "Модуль 2": ["Тема 2.1", "Тема 2.3", "Тема 2.4"],
        "Модуль 3": ["Тема 3.1", "Тема 3.2", "Тема 3.3"],
        "Модуль 4": ["Тема 4.1", "Тема 4.2", "Тема 4.3", "Тема 4.5", "Мок-интервью"],
        "Модуль 5": ["Резюме/Легенда"],
    },
    "Автотестирование": {
        "Модуль 1": ["Тема 1.1", "Тема 1.2", "Тема 1.3"],
        "Модуль 2": ["Экзамен 2"],
        "Модуль 3": ["Экзамен 3"],
        "Модуль 4": ["Экзамен 4"],
        "Модуль 5": ["Экзамен 5"],
    }
}

# Маппинг полей ManualProgress (Boolean и Date)
# 4.2 и 4.3 ссылаются на одно общее поле m4_2_4_3_submission_date согласно модели
MANUAL_FIELD_MAPPING = {
    "Тема 1.4": "m1_homework",
    "Тема 2.1": "m2_1_homework",
    "Тема 2.3": "m2_3_homework",
    "Тема 3.1": "m3_1_homework",
    "Тема 3.2": "m3_2_homework",
    "Тема 3.3": "m3_3_homework",
    "Тема 4.1": "m4_1_submission_date",
    "Тема 4.2": "m4_2_4_3_submission_date",
    "Тема 4.3": "m4_2_4_3_submission_date",
    "Тема 4.5": "m4_5_homework",
    "Мок-интервью": "m4_mock_exam_passed_date"
}

AUTO_START_MAPPING = {
    "Модуль 1": "m1_start_date", "Модуль 2": "m2_start_date",
    "Модуль 3": "m3_start_date", "Модуль 4": "m4_start_date", "Модуль 5": "m5_start_date",
}

AUTO_DONE_MAPPING = {
    "Экзамен 2": "m2_exam_passed_date", "Экзамен 3": "m3_exam_passed_date",
    "Экзамен 4": "m4_topic_passed_date", "Экзамен 5": "m5_topic_passed_date",
}


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def safe_date_format(date_value, default="None"):
    if not date_value: return default
    if hasattr(date_value, 'strftime'): return date_value.strftime('%Y-%m-%d')
    return str(date_value)


def generate_progress_bar(percent):
    length = 10
    filled = int(length * percent // 100)
    bar = "🟢" * filled + "⚪" * (length - filled)
    return f"{bar} {percent}%"


# --- ХЕНДЛЕРЫ ---
async def request_student_progress(update, context):
    keyboard = ReplyKeyboardMarkup([[KeyboardButton("🔙 В главное меню")]], resize_keyboard=True)
    await update.message.reply_text("📊 *Проверка успеваемости*\n\nВведите @username или ФИО студента:",
                                    reply_markup=keyboard, parse_mode="Markdown")
    return STUDENT_PROGRESS_WAITING


async def show_student_progress(update, context):
    text = update.message.text.strip()
    if text == "🔙 В главное меню":
        return await back_to_main_menu(update, context)

    student = get_student_by_fio_or_telegram(text)
    if not student:
        await update.message.reply_text(f"❌ Студент *{text}* не найден.", parse_mode="Markdown")
        return STUDENT_PROGRESS_WAITING

    progress_info = await get_student_progress_info(student)

    if len(progress_info) > 4000:
        for i in range(0, len(progress_info), 4000):
            await update.message.reply_text(progress_info[i:i + 4000])
    else:
        await update.message.reply_text(progress_info)
    return await back_to_main_menu(update, context)


async def get_student_progress_info(student):
    all_hws = session.query(Homework).filter(Homework.student_id == student.id).all()
    manual_p = session.query(ManualProgress).filter(ManualProgress.student_id == student.id).first()
    auto_p = session.query(AutoProgress).filter(AutoProgress.student_id == student.id).first()
    t_type = (student.training_type or "").lower()

    report = [
        f"👤 Студент: {student.fio}",
        f"🎯 Курс: {student.training_type or 'Не определен'}",
        f"📈 Статус: {student.training_status or 'Активен'}",
        "\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
    ]

    # --- MANUAL QA ---
    if any(x in t_type for x in ["ручн", "фулл", "manual", "full"]):
        report.append("\n🧠 Manual QA")
        m_total, m_done = 0, 0
        manual_lines = []

        for module_name, topics in MODULES_TOPICS["Ручное тестирование"].items():
            manual_lines.append(f"\n  ▪️ {module_name}")
            for topic in topics:
                m_total += 1
                status_icon = "⭕"

                # 1. Проверяем наличие ДЗ (строгое соответствие)
                relevant_hws = [h for h in all_hws if h.topic and h.topic.strip() == topic]
                hw_exists = len(relevant_hws) > 0

                # 2. Определяем статус-иконку ТОЛЬКО на основе ManualProgress
                is_passed = False
                if manual_p and topic in MANUAL_FIELD_MAPPING:
                    if getattr(manual_p, MANUAL_FIELD_MAPPING[topic], None):
                        is_passed = True

                if is_passed:
                    status_icon = "✅"
                    m_done += 1
                elif hw_exists:
                    # Если ДЗ есть, но тема не закрыта — смотрим статус ДЗ для промежуточных иконок
                    st = [h.status.lower() for h in relevant_hws if h.status]
                    if any(s in ["ожидает проверки", "на проверке"] for s in st):
                        status_icon = "⏳"
                    elif any(s in ["отклонено", "в доработке", "доработка"] for s in st):
                        status_icon = "🟡"
                    else:
                        status_icon = "⭕"  # Принято, но не проставлено в прогресс — оставляем круг

                hw_label = "📦 ДЗ: Есть" if hw_exists else "✖️ ДЗ: Нет"
                manual_lines.append(f"  {status_icon} {topic} ({hw_label})")

        percent = int((m_done / m_total) * 100) if m_total > 0 else 0
        report.append(generate_progress_bar(percent))
        report.extend(manual_lines)

    # --- AUTOMATION ---
    if any(x in t_type for x in ["автом", "фулл", "auto", "full", "python"]):
        report.append("\n🚀 Automation")
        a_total, a_done = 0, 0
        auto_lines = []

        for module_name, topics in MODULES_TOPICS["Автотестирование"].items():
            mod_total, mod_done = 0, 0
            is_started = False
            if auto_p and module_name in AUTO_START_MAPPING:
                if getattr(auto_p, AUTO_START_MAPPING[module_name], None): is_started = True

            for topic in topics:
                mod_total += 1
                a_total += 1
                topic_done = False

                # Здесь логика аналогична: приоритет за AutoProgress (даты экзаменов)
                if auto_p and topic in AUTO_DONE_MAPPING:
                    if getattr(auto_p, AUTO_DONE_MAPPING[topic], None):
                        topic_done = True

                # Если в AutoProgress пусто, проверяем статус в Homework
                if not topic_done:
                    relevant = [h for h in all_hws if h.topic and h.topic.strip() == topic]
                    if any(h.status.lower() in ["принято", "завершено", "проверено"] for h in relevant if h.status):
                        topic_done = True

                if topic_done:
                    mod_done += 1
                    a_done += 1

            icon = "✅" if mod_done == mod_total else ("⏳" if is_started or mod_done > 0 else "⭕")
            auto_lines.append(f"  {icon} {module_name}")

        a_percent = int((a_done / a_total) * 100) if a_total > 0 else 0
        report.append(generate_progress_bar(a_percent))
        report.extend(auto_lines)

    # --- ФИНАНСЫ ---
    report.append("\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")
    accepted = len([h for h in all_hws if h.status and h.status.lower() in ["принято", "завершено", "проверено"]])
    report.append(f"📊 Принято всего: {accepted} ДЗ")
    report.append(
        f"💳 Оплата: {student.payment_amount or 0} / {student.total_cost or 0} ₽ {'✅' if student.fully_paid == 'Да' else '⏳'}")
    report.append(f"📅 Дата трудоустройства: {safe_date_format(student.employment_date)}")
    report.append(f"💵 Зарплата: {student.salary or 0}")
    report.append(f"💸 Выплачено комиссии: {getattr(student, 'commission_paid', 0)}")

    if student.last_call_date:
        report.append(f"📞 Последний звонок: {safe_date_format(student.last_call_date)}")

    return "\n".join(report)