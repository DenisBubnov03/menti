import os
from dotenv import load_dotenv # Добавь этот импорт
from google import genai

# Загружаем переменные из .env
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Проверка, чтобы не падать с непонятной ошибкой
if not GEMINI_API_KEY:
    raise ValueError("Ошибка: GEMINI_API_KEY не найден! Проверь файл .env")

client = genai.Client(api_key=GEMINI_API_KEY)