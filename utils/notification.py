import os
import json
import asyncio
import psycopg2
from datetime import datetime, date
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from data_base.db import DATABASE_URL

# --- ИНИЦИАЛИЗАЦИЯ ---
BASE_DIR = Path(__file__).resolve().parent.parent
dotenv_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=dotenv_path)

TOKEN = os.getenv("TELEGRAM_TOKEN")
DATABASE_URL = DATABASE_URL
MY_PERSONAL_ID = 1257163820

bot = Bot(token=TOKEN)
JSON_FILE = Path(__file__).resolve().parent / "notification_state.json"

# --- ШАБЛОНЫ (без изменений) ---
first_masage = "{student_name}, привет! Мы не созванивались уже {days_passed} дн. Решил уточнить: всё ли в порядке? 🙌"
second_massage_student = "{student_name}, добрый день! Заметил паузу в {days_passed} д. Есть вопросы по программе? 😊"
third_massage_student = "{student_name}, привет! Мы не общались уже {days_passed} д. Напиши куратору, чтобы обсудить прогресс! 🔥"

def get_director_chat_id_from_db(director_id: int) -> Optional[int]:
    """
    Получает chat_id ментора/директора из базы данных по его первичному ключу (ID).
    """
    try:
        # Используем DATABASE_URL из .env
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        cur.execute("SELECT chat_id FROM mentors WHERE id = %s", (director_id,))
        row = cur.fetchone()

        cur.close()
        conn.close()

        if row and row[0]:
            return int(row[0])
        return None
    except Exception as e:
        print(f"❌ Ошибка при получении chat_id директора {director_id}: {e}")
        return None
# --- ФУНКЦИИ ---

def load_state():
    if JSON_FILE.exists():
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=4)


def _render_template(template: str, context: dict) -> str:
    try:
        return template.format(**context)
    except Exception:
        return template


def _director_ids_for_training_type(training_type: Optional[str]) -> list[int]:
    if training_type == "Ручное тестирование": return [1]
    if training_type == "Автотестирование": return [3]
    if training_type == "Фуллстек": return [1, 3]
    return []


async def send_smart_message(chat_id, text, kb=None, tg_name=None):
    try:
        target = str(chat_id).strip()
        if not target or target.lower() == 'none':
            raise ValueError("ID пустой")
        if not target.startswith('@'):
            target = int(float(target))

        await bot.send_message(chat_id=target, text=text, reply_markup=kb, parse_mode="HTML")
        return True
    except Exception as e:
        recipient = tg_name if tg_name else chat_id
        admin_info = (
            f"<b>‼️ ОШИБКА ДОСТАВКИ</b>\n"
            f"Кому: <b>{recipient}</b>\n"
            f"ID: <code>{chat_id}</code>\n"
            f"Ошибка: <i>{e}</i>\n\n"
            f"<b>Текст:</b>\n{text}"
        )
        try:
            await bot.send_message(chat_id=MY_PERSONAL_ID, text=admin_info, parse_mode="HTML")
        except:
            pass
        return False


# --- ОСНОВНОЙ СКРИПТ ---

async def run_check():
    if not DATABASE_URL: return

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
    except Exception as e:
        print(f"❌ Ошибка БД: {e}")
        return

    cur.execute("""
        SELECT s.id, s.fio, m.chat_id, s.chat_id, s.telegram, s.last_call_date, s.training_type
        FROM students s
        JOIN mentors m ON s.mentor_id = m.id
        WHERE s.training_status = 'Учится'
        AND s.start_date >= '2025-10-01';
    """)
    rows = cur.fetchall()

    cur.execute("SELECT id, chat_id FROM mentors WHERE id IN (1, 3);")
    director_chat_ids = {int(row_id): row_chat_id for row_id, row_chat_id in cur.fetchall() if row_chat_id}

    state = load_state()
    today = date.today()
    curator_digests = {}
    director_digests = {}

    for s_id, s_name, m_chat_id, s_chat_id, s_telegram, raw_date, training_type in rows:
        s_id_str = str(s_id)

        try:
            if not raw_date: continue
            last_call = raw_date if isinstance(raw_date, date) else datetime.strptime(str(raw_date).strip(),
                                                                                      "%Y-%m-%d").date()
        except:
            continue

        days_passed = (today - last_call).days
        if days_passed <= 14:
            if s_id_str in state: del state[s_id_str]
            continue

        if state.get(s_id_str, {}).get("active_hold"):
            last_notified = datetime.strptime(state[s_id_str]["last_notified"], "%Y-%m-%d").date()
            if (today - last_notified).days < 14: continue

        if days_passed >= 35:
            required_stage = 4
        elif days_passed >= 28:
            required_stage = 3
        elif days_passed >= 21:
            required_stage = 2
        else:
            required_stage = 1

        last_stage = int(state.get(s_id_str, {}).get("stage", 0))
        if required_stage <= last_stage: continue

        student_target = s_chat_id if s_chat_id else s_telegram
        context = {
            "student_name": s_name, "student_telegram": s_telegram,
            "days_passed": days_passed, "last_call_date": str(last_call),
            "training_type": training_type or "",
        }

        if required_stage == 1:
            msg = _render_template(first_masage, context)
            await send_smart_message(student_target, msg, tg_name=s_telegram)

            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Активен (2 нед.)", callback_data=f"keep_active:{s_id}")],
                [InlineKeyboardButton(text="❌ Не учится", callback_data=f"set_inactive:{s_id}")]
            ])
            await send_smart_message(m_chat_id, f"🔔 <b>{s_name}</b> молчит {days_passed} дн. Подтвердите статус:", kb)

        elif required_stage == 2:
            msg = _render_template(second_massage_student, context)
            await send_smart_message(student_target, msg, tg_name=s_telegram)
            alert = f"⚠️ 3 нед: <b>{s_name}</b> {s_telegram} ({training_type})"
            curator_digests.setdefault(m_chat_id, []).append(alert)
            for d_id in _director_ids_for_training_type(training_type):
                d_chat = director_chat_ids.get(d_id)
                if d_chat: director_digests.setdefault(d_chat, []).append(alert)

        elif required_stage == 3:
            msg = _render_template(third_massage_student, context)
            await send_smart_message(student_target, msg, tg_name=s_telegram)
            alert = f"🚨 <b>АЛАРМ 4 нед</b>: {s_name} {s_telegram}"
            curator_digests.setdefault(m_chat_id, []).append(alert)
            for d_id in _director_ids_for_training_type(training_type):
                d_chat = director_chat_ids.get(d_id)
                if d_chat: director_digests.setdefault(d_chat, []).append(alert)

        elif required_stage == 4:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Да, отчислить", callback_data=f"drop_student:{s_id}")],
                [InlineKeyboardButton(text="❌ Нет, оставить", callback_data=f"keep_active:{s_id}")]
            ])
            text = f"💀 <b>ФИНАЛЬНЫЙ ЭТАП: {s_name} {s_telegram}</b>\nМолчит {days_passed} дн. Перевести в 'Не учится'?"
            await send_smart_message(m_chat_id, text, kb)

        state[s_id_str] = {"stage": required_stage, "last_notified": str(today), "active_hold": False}

    for chat_id, alerts in curator_digests.items():
        await send_smart_message(chat_id, "<b>📋 Сводка по пропускам (2-3 недели):</b>\n\n" + "\n".join(alerts))

    for chat_id, alerts in director_digests.items():
        await send_smart_message(chat_id, "<b>📊 Отчет для руководства:</b>\n\n" + "\n".join(alerts))

    save_state(state)
    cur.close();
    conn.close()
    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run_check())