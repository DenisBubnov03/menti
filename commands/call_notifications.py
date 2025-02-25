import asyncio
from googleapiclient.discovery import build
from google.oauth2 import service_account
import datetime
import re

from telegram import Bot, ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes

from commands.base_function import back_to_main_menu
from commands.google_calendar import get_calendar_service
import os
from dotenv import load_dotenv

from data_base.db import session
from data_base.models import Mentor

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_IDS = {"mentor1@example.com": 123456789, "student1@example.com": 987654321}  # Связка email → chat_id

def get_calls_for_mentor_from_calendar(calendar_id: str, mentor_telegram: str, max_results=10) -> list:
    """
    Получает предстоящие события из Google Calendar, фильтруя их по Telegram-нику ментора в описании.
    :param calendar_id: ID календаря.
    :param mentor_telegram: Telegram-ник ментора для фильтрации.
    :param max_results: Максимальное количество событий для отображения.
    :return: Список словарей с датой, временем и студентом.
    """
    # Авторизация сервисного аккаунта
    SERVICE_ACCOUNT_FILE = "credentials.json"
    SCOPES = ["https://www.googleapis.com/auth/calendar"]

    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )

    service = build("calendar", "v3", credentials=credentials)

    # Текущее время в UTC
    now = datetime.datetime.utcnow().isoformat() + "Z"

    # Запрос событий
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=now,
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    events = events_result.get("items", [])

    # Формируем список событий для данного ментора
    calls = []
    for event in events:
        description = event.get("description", "")
        if f"@{mentor_telegram}" in description:  # Фильтрация по Telegram-нику ментора
            start_time = event["start"].get("dateTime", event["start"].get("date"))
            start_time = datetime.datetime.fromisoformat(start_time).strftime("%d.%m.%Y %H:%M")

            # Извлекаем Telegram студента из описания с помощью регулярного выражения
            student_telegram_match = re.search(r"@(\w+)", description)
            student_telegram = f"@{student_telegram_match.group(1)}" if student_telegram_match else "Не указан"

            calls.append({
                "date_time": start_time,
                "student_telegram": student_telegram
            })

    return calls

async def show_mentor_calls(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отправляет ментору список всех его предстоящих звонков из Google Calendar.
    """
    user_id = update.message.from_user.id
    mentor = session.query(Mentor).filter(Mentor.chat_id == str(user_id)).first()


    if not mentor:
        await update.message.reply_text("❌ Ошибка: ваш профиль не найден.")
        return

    calendar_id = "12027ce1762cbd0cb206050a7e14f741d2845ea5b73984acb5ac71fca6166495@group.calendar.google.com"
    mentor_telegram = mentor.telegram.lstrip("@")  # Убираем @ для поиска

    calls = get_calls_for_mentor_from_calendar(calendar_id, mentor_telegram)

    if not calls:
        await update.message.reply_text("📭 У вас нет предстоящих звонков.")
        return

    # Формируем сообщение
    message = "Ваши предстоящие звонки:\n\n"
    for call in calls:
        message += (
            f"📅 {call['date_time']}\n"
            f"👨‍🎓 {call['student_telegram']}\n\n"
        )

    await update.message.reply_text(message)
    return await back_to_main_menu(update, context)


async def check_upcoming_calls():
    """Проверяет события на ближайшие 15 минут и отправляет уведомления"""
    bot = Bot(token=TELEGRAM_TOKEN)
    service = get_calendar_service()
    now = datetime.datetime.utcnow()
    time_min = (now + datetime.timedelta(minutes=14)).isoformat() + "Z"
    time_max = (now + datetime.timedelta(minutes=16)).isoformat() + "Z"

    events_result = service.events().list(
        calendarId="your_calendar_id@group.calendar.google.com",
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    events = events_result.get("items", [])

    for event in events:
        summary = event.get("summary", "Созвон")
        description = event.get("description", "")
        attendees = event.get("attendees", [])

        message = f"⏳ Напоминание! Через 15 минут {summary}\n\n{description}"

        # Отправляем уведомления студенту и ментору
        for attendee in attendees:
            email = attendee.get("email")
            chat_id = CHAT_IDS.get(email)
            if chat_id:
                await bot.send_message(chat_id=chat_id, text=message)

async def run_scheduler():
    """Запускает проверку каждые 5 минут"""
    while True:
        await check_upcoming_calls()
        await asyncio.sleep(300)  # 5 минут