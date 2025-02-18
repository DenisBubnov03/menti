import os
import datetime
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

from data_base.operations import get_mentor_by_student

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CALENDAR_ID = "12027ce1762cbd0cb206050a7e14f741d2845ea5b73984acb5ac71fca6166495@group.calendar.google.com"  # ID календаря

# Загружаем учетные данные
CREDENTIALS_FILE = "credentials.json"

def get_calendar_service():
    """Создает сервисный объект для работы с Google Calendar"""
    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_FILE, scopes=SCOPES
    )
    return build("calendar", "v3", credentials=credentials)


def list_available_slots():
    """Возвращает список свободных слотов в календаре"""
    service = get_calendar_service()
    now = datetime.datetime.utcnow().isoformat() + "Z"

    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=now,
        maxResults=10,
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    events = events_result.get("items", [])
    free_slots = []

    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))
        free_slots.append(f"{start} - {end}")

    return free_slots


def create_event(student_name, student_telegram, date_time):
    """
    Создает событие в Google Calendar без Google Meet и с указанием ментора.
    """
    service = get_calendar_service()

    start_time = datetime.datetime.strptime(date_time, "%d.%m.%Y %H:%M")
    end_time = start_time + datetime.timedelta(minutes=45)  # Длительность 30 минут

    # Получаем информацию о менторе студента
    mentor = get_mentor_by_student(student_telegram)
    mentor_name = mentor.full_name if mentor else "Неизвестный ментор"
    mentor_tg = mentor.telegram if mentor else "Нет данных"

    event = {
        "summary": f"📅 Созвон у {mentor_name}",
        "description": (
            f"👤 Студент: {student_name} ({student_telegram})\n"
            f"📅 Время: {date_time}\n"
            f"🧑‍ Ментор: {mentor_name} ({mentor_tg})"
        ),
        "start": {"dateTime": start_time.isoformat(), "timeZone": "Europe/Moscow"},
        "end": {"dateTime": end_time.isoformat(), "timeZone": "Europe/Moscow"},
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": 15}]
        }
    }

    created_event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    return created_event.get("id"), date_time
