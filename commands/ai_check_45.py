import os
import asyncio
import logging
import tempfile
import docx2txt
import openpyxl
import re
from io import BytesIO
from google import genai  # Новый SDK
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential

# Настройка логов
logger = logging.getLogger(__name__)

# --- КОНФИГУРАЦИЯ ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_ID = "gemini-2.0-flash"
# Инициализация клиента (вместо устаревшего configure)
client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_45 = """Проверь правильно ли все. На терминологию и оформление не обращай внимание.
Формат ответа:
✅ Проверка 4.5 готова
Оценка: <балл>/100
Статус: ✅ Задание принято! (Если меньше 50 баллов, то писать <❌ Задание не принято!>)
Итог: <одно предложение о результате>
<Похвали за работу>"""


# --- РЕПОЗИТОРИИ (ЛОГИКА БД) ---

class AICheckRepository:
    """Управление записями о проверках ИИ"""

    def __init__(self, session):
        self.session = session
        from data_base.models import AIHomeworkCheck
        self.AIHomeworkCheck = AIHomeworkCheck

    def has_active_or_done(self, submission_id: int) -> bool:
        check = self.session.query(self.AIHomeworkCheck).filter(
            self.AIHomeworkCheck.submission_id == submission_id,
            self.AIHomeworkCheck.status.in_(['running', 'done'])
        ).first()
        return check is not None

    def create_check(self, submission_id: int, topic: str, model: str, status: str = "running") -> int:
        check = self.AIHomeworkCheck(
            submission_id=submission_id,
            topic=topic,
            model=model,
            status=status
        )
        self.session.add(check)
        self.session.commit()
        return check.id

    def update_check(self, check_id: int, status: str, raw_text: str = None):
        check = self.session.query(self.AIHomeworkCheck).filter_by(id=check_id).first()
        if check:
            check.status = status
            check.raw_text = raw_text
            self.session.commit()


class TopicAttemptsRepository:
    """Логика подсчета попыток студента"""

    def __init__(self, session):
        self.session = session
        from data_base.models import Homework
        self.Homework = Homework

    def get_attempts(self, student_id: int, topic: str) -> dict:
        submissions = self.session.query(self.Homework).filter_by(
            student_id=student_id, topic=topic
        ).all()

        is_completed = any(hw.status == "проверено" for hw in submissions)
        best_score = 0

        for hw in submissions:
            for check in hw.ai_checks:
                if check.status == "done" and check.raw_text:
                    score_match = re.search(r'Оценка:\s*(\d+)/100', check.raw_text)
                    if score_match:
                        score = int(score_match.group(1))
                        best_score = max(best_score, score)
                        if score >= 50: is_completed = True

        return {
            "attempts_count": len(submissions),
            "best_score": best_score,
            "is_completed": is_completed,
            "can_attempt": len(submissions) < 2 and not is_completed
        }


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def extract_score_from_text(text: str) -> int:
    match = re.search(r'Оценка:\s*(\d+)/100', text)
    if match:
        score = int(match.group(1))
        return score if 0 <= score <= 100 else None
    return None


def extract_text_non_pdf(filename: str, content: bytes) -> str:
    ext = filename.lower()
    try:
        if ext.endswith('.docx'):
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            text = docx2txt.process(tmp_path)
            os.remove(tmp_path)
            return text
        elif ext.endswith(('.xlsx', '.xls')):
            wb = openpyxl.load_workbook(BytesIO(content), data_only=True)
            text = ""
            for s in wb.worksheets:
                for r in s.iter_rows(values_only=True):
                    text += " | ".join([str(c) for c in r if c is not None]) + "\n"
            return text
        elif ext.endswith('.txt'):
            return content.decode('utf-8', errors='ignore')
        return ""
    except Exception as e:
        logger.error(f"Ошибка парсинга {filename}: {e}")
        return ""


# --- API CALLS ---

@retry(
    stop=stop_after_attempt(5), # Дадим 5 попыток вместо 3
    wait=wait_exponential(min=5, max=30), # Начнем с 5 секунд и дойдем до 30
    reraise=True)
def call_gemini_api(filename: str, file_content: bytes) -> str:
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_45,
        temperature=0.2,
    )

    if filename.lower().endswith('.pdf'):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        try:
            uploaded_file = client.files.upload(path=tmp_path)
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=[uploaded_file, "Проверь домашнюю работу."],
                config=config
            )
            return response.text
        finally:
            if os.path.exists(tmp_path): os.remove(tmp_path)
    else:
        text = extract_text_non_pdf(filename, file_content)
        if not text: raise ValueError("Файл не содержит текста")
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=f"Проверь домашнюю работу:\n\n{text[:30000]}",
            config=config
        )
        return response.text


# --- ГЛАВНЫЙ АСИНХРОННЫЙ ОБРАБОТЧИК ---

async def review_45_async(submission_id: int, get_submission_payload, repo=None, notify_student=None,
                          notify_mentor=None):
    """Автономная проверка. Сама управляет сессиями БД."""
    from data_base.db import get_session

    # 1. Проверяем статус и создаем запись 'running'
    with get_session() as db_session:
        active_repo = AICheckRepository(db_session)
        if active_repo.has_active_or_done(submission_id):
            logger.info(f"Проверка {submission_id} уже выполнена.")
            return
        check_id = active_repo.create_check(submission_id, "4.5", MODEL_ID)

    try:
        # 2. Получаем данные файла
        payload = await get_submission_payload(submission_id)

        # 3. Вызываем Gemini в отдельном потоке (API синхронное в SDK)
        loop = asyncio.get_running_loop()
        llm_response = await loop.run_in_executor(
            None, lambda: call_gemini_api(payload["filename"], payload["file_bytes"])
        )

        # 4. Обрабатываем результат и сохраняем
        score = extract_score_from_text(llm_response)
        is_passed = score is not None and score >= 50

        with get_session() as db_session:
            final_repo = AICheckRepository(db_session)
            final_repo.update_check(check_id, status="done", raw_text=llm_response)

            from data_base.models import Homework
            hw = db_session.query(Homework).filter_by(id=submission_id).first()
            if hw:
                hw.status = "проверено" if is_passed else "не принято"
                db_session.commit()

        # 5. Уведомления
        if notify_student:
            await notify_student(payload["student_id"], llm_response)
        if notify_mentor:
            await notify_mentor(payload["mentor_id"],
                                f"✅ Работа {submission_id} проверена ИИ. Оценка: {score if score else '??'}/100")

    except Exception as e:
        logger.error(f"Ошибка Gemini-проверки {submission_id}: {e}")
        logger.error(f"ДЕТАЛИ ОШИБКИ: {getattr(e, 'message', str(e))}")
        with get_session() as db_session:
            error_repo = AICheckRepository(db_session)
            error_repo.update_check(check_id, status="error", raw_text=str(e))
        if notify_student:
            await notify_student(payload["student_id"], "⚠️ Ошибка автопроверки. Работа передана ментору.")