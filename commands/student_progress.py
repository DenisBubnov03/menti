from telegram import ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ConversationHandler

from commands.base_function import back_to_main_menu
from data_base.operations import get_student_by_fio_or_telegram
from data_base.models import Student, Homework, ManualProgress
from data_base.db import session
from commands.states import STUDENT_PROGRESS_WAITING
from datetime import datetime, date

# --- КОНФИГУРАЦИЯ ---
MODULES_TOPICS = {
    "Ручное тестирование": {
        "Модуль 1": ["Тема 1.4"],
        "Модуль 2": ["Тема 2.1", "Тема 2.3", "Тема 2.4"],
        "Модуль 3": ["Тема 3.1", "Тема 3.2", "Тема 3.3"],
        "Модуль 4": ["Тема 4.5"],
        "Модуль 5": ["Резюме/Легенда"],
    },
    "Автотестирование": {
        "Модуль 1": ["Тема 1.1", "Тема 1.2", "Тема 1.3"],
        "Модуль 2": ["Тема 2.1", "Тема 2.2", "Тема 2.3", "Тема 2.4", "Тема 2.5", "Тема 2.6", "Тема 2.7", "Экзамен 2"],
        "Модуль 3": ["Тема 3.1", "Тема 3.2", "Тема 3.3", "Тема 3.4", "Тема 3.5", "Тема 3.6", "Экзамен 3"],
        "Модуль 4": ["Тема 4.1", "Тема 4.2", "Тема 4.3", "Тема 4.4", "Тема 4.5", "Экзамен 4"],
        "Модуль 5": ["Тема 5.1", "Тема 5.2", "Тема 5.3", "Тема 5.4", "Тема 5.5", "Тема 5.6", "Экзамен 5"],
    }
}

PROGRESS_FIELD_MAPPING = {
    "Тема 1.4": "m1_homework",
    "Тема 2.1": "m2_1_homework",
    "Тема 2.3": "m2_3_homework",
    "Тема 2.4": "m2_4_homework",
    "Тема 3.1": "m3_1_homework",
    "Тема 3.2": "m3_2_homework",
    "Тема 3.3": "m3_3_homework",
    "Тема 4.5": "m4_5_homework",
}


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def safe_date_format(date_value, default="—"):
    if not date_value: return default
    if hasattr(date_value, 'strftime'): return date_value.strftime('%d.%m.%Y')
    return str(date_value)


def generate_progress_bar(percent):
    length = 10
    filled = int(length * percent // 100)
    bar = "🟢" * filled + "⚪" * (length - filled)
    return f"{bar} {percent}%"


def get_module_status_icon(student_hws, module_name):
    """Определяет статус всего модуля (для Авто-части)"""
    relevant_hws = [hw for hw in student_hws if hw.module and module_name.lower() in hw.module.lower()]
    if not relevant_hws:
        return "⭕"

    statuses = [hw.status.lower() for hw in relevant_hws if hw.status]
    if any(s in ["принято", "завершено", "проверено"] for s in statuses):
        return "✅"
    if any(s in ["ожидает проверки", "на проверке"] for s in statuses):
        return "⏳"
    if any(s in ["отклонено", "в доработке", "доработка"] for s in statuses):
        return "🟡"
    return "❓"


def get_topic_status(student_hws, manual_progress, topic_name):
    """Определяет статус темы и наличие ДЗ (для Ручной части)"""
    hw_exists = False
    status_icon = "⭕"

    # Проверка через Homework
    relevant_hws = [hw for hw in student_hws if hw.topic and topic_name.lower() in hw.topic.lower()]
    if relevant_hws:
        hw_exists = True
        statuses = [hw.status.lower() for hw in relevant_hws if hw.status]
        if any(s in ["принято", "завершено", "проверено"] for s in statuses):
            status_icon = "✅"
        elif any(s in ["ожидает проверки", "на проверке"] for s in statuses):
            status_icon = "⏳"
        elif any(s in ["отклонено", "в доработке", "доработка"] for s in statuses):
            status_icon = "🟡"

    # Доп. проверка через ManualProgress
    if status_icon != "✅" and topic_name in PROGRESS_FIELD_MAPPING and manual_progress:
        field_name = PROGRESS_FIELD_MAPPING[topic_name]
        if getattr(manual_progress, field_name, False):
            hw_exists = True
            status_icon = "✅"

    hw_label = "📦 ДЗ: Есть" if hw_exists else "✖️ ДЗ: Нет"
    return f"{status_icon} {topic_name} ({hw_label})"


# --- ОСНОВНЫЕ ХЕНДЛЕРЫ ---
async def request_student_progress(update, context):
    keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton("🔙 В главное меню")]], resize_keyboard=True)
    await update.message.reply_text("📊 *Проверка успеваемости*\n\nВведите @username или ФИО студента:",
                                    reply_markup=keyboard, parse_mode="Markdown")
    return STUDENT_PROGRESS_WAITING


async def show_student_progress(update, context):
    message = update.message.text
    if message == "🔙 В главное меню":
        return await back_to_main_menu(update, context)

    student_telegram = message.strip()
    student = get_student_by_fio_or_telegram(student_telegram)

    if not student:
        await update.message.reply_text(f"❌ Студент *{student_telegram}* не найден.", parse_mode="Markdown")
        return STUDENT_PROGRESS_WAITING

    progress_info = await get_student_progress_info(student)

    if len(progress_info) > 4000:
        for i in range(0, len(progress_info), 4000):
            await update.message.reply_text(progress_info[i:i + 4000], parse_mode="Markdown")
    else:
        await update.message.reply_text(progress_info, parse_mode="Markdown")
    return await back_to_main_menu(update, context)


async def get_student_progress_info(student):
    all_hws = session.query(Homework).filter(Homework.student_id == student.id).all()
    manual_p = session.query(ManualProgress).filter(ManualProgress.student_id == student.id).first()
    t_type = (student.training_type or "").lower()

    report = [
        f"👤 *Студент:* {student.fio}",
        f"🎯 *Курс:* {student.training_type or 'Не определен'}",
        f"📈 *Статус:* {student.training_status or 'Активен'}\n",
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
    ]

    show_manual = any(x in t_type for x in ["ручн", "фулл", "manual", "full"])
    show_auto = any(x in t_type for x in ["автом", "фулл", "auto", "full", "python"])

    # --- БЛОК MANUAL (ПО ТЕМАМ) ---
    if show_manual:
        block = ["\n🧠 *Manual QA*"]
        total, done = 0, 0
        for module_name, topics in MODULES_TOPICS["Ручное тестирование"].items():
            block.append(f"\n  ▪️ _{module_name}_")
            for topic in topics:
                total += 1
                info = get_topic_status(all_hws, manual_p, topic)
                if "✅" in info: done += 1
                block.append(f"  {info}")

        percent = int((done / total) * 100) if total > 0 else 0
        block.insert(1, generate_progress_bar(percent))
        report.extend(block)

    # --- БЛОК AUTO (ПО МОДУЛЯМ) ---
    if show_auto:
        block = ["\n🚀 *Automation*"]
        total, done = 0, 0
        # Здесь итерируемся только по модулям, не заходя в темы
        for module_name in MODULES_TOPICS["Автотестирование"].keys():
            total += 1
            status = get_module_status_icon(all_hws, module_name)
            if status == "✅": done += 1
            block.append(f"  {status} {module_name}")

        percent = int((done / total) * 100) if total > 0 else 0
        block.insert(1, generate_progress_bar(percent))
        report.extend(block)

    accepted = len([h for h in all_hws if h.status and h.status.lower() in ["принято", "завершено"]])
    report.append("\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")
    report.append(f"📊 *Принято всего:* {accepted} ДЗ")
    is_paid = "✅" if student.fully_paid == "Да" else "⏳"
    report.append(f"💳 *Оплата:* {student.payment_amount or 0} / {student.total_cost or 0} ₽ {is_paid}")
    report.append(f"📅 *Дата трудоустройства:* {student.employment_date}")
    report.append(f"💵 *Зарплата:* {student.salary}")
    report.append(f"💸 *Выплачено комиссии:* {student.commission_paid}")


    if student.last_call_date:
        report.append(f"📞 *Последний звонок:* {safe_date_format(student.last_call_date)}")

    return "\n".join(report)


def get_current_module(student):
    last_hw = session.query(Homework).filter(Homework.student_id == student.id,
                                             Homework.status.in_(["принято", "завершено"])).order_by(
        Homework.created_at.desc()).first()
    return f"Завершил {last_hw.module}" if last_hw else "Модуль 1"