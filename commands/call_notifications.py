import datetime
import asyncio

from telegram import Bot

from commands.google_calendar import get_calendar_service
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_IDS = {"mentor1@example.com": 123456789, "student1@example.com": 987654321}  # Связка email → chat_id

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