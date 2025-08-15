import json
import asyncio
import logging
import os
from tenacity import retry, stop_after_attempt, wait_exponential
from openai import OpenAI
from datetime import datetime
import docx2txt
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

SYSTEM_45 = (
    "Ты проверяешь домашнюю работу студента по теме 4.5 где он ответил на 100 вопросов. Не учитывай необходимость наличия ссылок на статья, сервисы, инструменты и тд. Так же не акцентируй сильно внимание на наличие примеров технологий, сервисов, инструментов \n"
    "Оцени качество ответов на вопросы по следующим критериям:\n\n"
    "1. Точность информации - ответы должны быть корректными с технической точки зрения\n"
    "2. Полнота ответов - должны быть раскрыты все аспекты вопроса\n"
    "3. Структурированность - логичное изложение материала\n"
    "4. Практическая применимость - ответы должны быть полезными для работы\n"
    "5. Актуальность - использование современных подходов и инструментов\n\n"
    "ВАЖНО: Если текст пустой, неразборчивый или содержит только символы/цифры без смысла, поставь 0 баллов.\n\n"
    "Критерии оценки:\n"
    "- 90-100: Отличные ответы с глубоким пониманием темы\n"
    "- 70-89: Хорошие ответы с небольшими неточностями\n"
    "- 50-69: Удовлетворительные ответы, есть пробелы в знаниях\n"
    "- 30-49: Слабые ответы, много неточностей\n"
    "- 0-29: Неудовлетворительные ответы, пустой текст или неразборчивое содержимое\n\n"
                    "Верни ТОЛЬКО JSON c ключами:\n"
                "- score: целое 0..100\n"
                "- pluses: массив 2–4 сильных сторон работы\n"
                "- mistakes: массив 2–5 конкретных ошибок или недостатков в ответах\n"
                "- tips: массив 2–5 конкретных советов по улучшению знаний\n"
                "- verdict: одно краткое итоговое предложение с оценкой\n"
                "Никаких пояснений вне JSON."
)


def safe_parse_json(s: str):
    """Безопасный парсинг JSON с обработкой markdown блоков"""
    t = s.strip()
    if t.startswith("```"):
        t = t.strip("`")
        # убрать возможный префикс типа json\n
        t = t.split("\n", 1)[1] if "\n" in t else t
    try:
        return json.loads(t)
    except Exception:
        return None


def extract_text(filename: str, content: bytes) -> str:
    """Извлечение текста из файлов разных форматов"""
    try:
        logger.info(f"Извлечение текста из файла: {filename}, размер: {len(content)} байт")
        
        # Проверяем входные данные
        if not content or len(content) == 0:
            logger.error(f"Пустое содержимое файла: {filename}")
            return ""
        
        if not filename:
            logger.error("Не указано имя файла")
            return ""
        
        if filename.lower().endswith('.pdf'):
            # PDF через PyMuPDF
            doc = fitz.open(stream=content, filetype="pdf")
            text = ""
            for page_num, page in enumerate(doc):
                page_text = page.get_text()
                text += page_text
                logger.info(f"PDF страница {page_num + 1}: {len(page_text)} символов")
            doc.close()
            logger.info(f"PDF извлечено всего: {len(text)} символов")
            return text
        
        elif filename.lower().endswith('.docx'):
            # DOCX через docx2txt
            import tempfile
            import shutil
            
            try:
                # Создаем временный файл с уникальным именем
                temp_dir = tempfile.gettempdir()
                temp_file = os.path.join(temp_dir, f"docx_{hash(content) % 1000000}.docx")
                
                # Записываем содержимое
                with open(temp_file, 'wb') as f:
                    f.write(content)
                
                # Извлекаем текст
                text = docx2txt.process(temp_file)
                
                # Удаляем временный файл
                try:
                    os.remove(temp_file)
                except OSError:
                    pass  # Игнорируем ошибки удаления
                
                logger.info(f"DOCX извлечено: {len(text)} символов")
                return text
                
            except Exception as docx_error:
                logger.error(f"Ошибка извлечения из DOCX {filename} через docx2txt: {docx_error}")
                
                # Пробуем альтернативный способ через python-docx
                try:
                    from docx import Document
                    from io import BytesIO
                    
                    doc = Document(BytesIO(content))
                    text = ""
                    for paragraph in doc.paragraphs:
                        if paragraph.text.strip():
                            text += paragraph.text.strip() + "\n"
                    
                    logger.info(f"DOCX извлечено через python-docx: {len(text)} символов")
                    return text
                    
                except Exception as docx2_error:
                    logger.error(f"Ошибка извлечения из DOCX {filename} через python-docx: {docx2_error}")
                    return ""
        
        elif filename.lower().endswith(('.xlsx', '.xls')):
            # Excel файлы через openpyxl
            import tempfile
            import openpyxl
            from io import BytesIO
            
            try:
                # Создаем временный файл
                with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
                    tmp.write(content)
                    tmp.flush()
                    
                    # Открываем Excel файл
                    workbook = openpyxl.load_workbook(tmp.name, data_only=True)
                    text = ""
                    
                    # Проходим по всем листам
                    for sheet_name in workbook.sheetnames:
                        sheet = workbook[sheet_name]
                        text += f"\n=== Лист: {sheet_name} ===\n"
                        
                        # Находим диапазон с данными
                        data_range = sheet.calculate_dimension()
                        if data_range == 'A1:A1' and sheet['A1'].value is None:
                            # Пустой лист
                            continue
                            
                        # Проходим по всем ячейкам с данными
                        for row in sheet.iter_rows(values_only=True):
                            row_text = ""
                            has_data = False
                            for cell_value in row:
                                if cell_value is not None and str(cell_value).strip():
                                    row_text += str(cell_value).strip() + " | "
                                    has_data = True
                            if has_data:
                                text += row_text.rstrip(" | ") + "\n"
                    
                    workbook.close()
                    os.unlink(tmp.name)
                    logger.info(f"Excel извлечено: {len(text)} символов")
                    return text
                    
            except Exception as excel_error:
                logger.error(f"Ошибка извлечения из Excel {filename}: {excel_error}")
                return ""
        
        elif filename.lower().endswith('.csv'):
            # CSV файлы
            try:
                import pandas as pd
                from io import BytesIO
                
                # Читаем CSV
                df = pd.read_csv(BytesIO(content), encoding='utf-8', on_bad_lines='skip')
                text = df.to_string(index=False)
                logger.info(f"CSV извлечено: {len(text)} символов")
                return text
                
            except Exception as csv_error:
                logger.error(f"Ошибка извлечения из CSV {filename}: {csv_error}")
                # Пробуем как обычный текст
                text = content.decode('utf-8', errors='ignore')
                logger.info(f"CSV извлечено как текст: {len(text)} символов")
                return text
        
        elif filename.lower().endswith('.txt'):
            # TXT файл
            text = content.decode('utf-8', errors='ignore')
            logger.info(f"TXT извлечено: {len(text)} символов")
            return text
        
        elif filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
            # Изображения - возвращаем пустую строку с предупреждением
            logger.warning(f"Изображение {filename} не содержит извлекаемого текста")
            return ""
        
        elif filename.lower().endswith(('.ogg', '.mp3', '.wav')):
            # Аудио файлы - возвращаем пустую строку с предупреждением
            logger.warning(f"Аудио файл {filename} не содержит извлекаемого текста")
            return ""
        
        else:
            # Для остальных форматов пробуем как текст
            text = content.decode('utf-8', errors='ignore')
            logger.info(f"Неизвестный формат {filename}, извлечено как текст: {len(text)} символов")
            return text
    
    except Exception as e:
        logger.error(f"Ошибка извлечения текста из {filename}: {e}")
        return ""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=0.5, max=4))
def call_llm(text: str) -> dict:
    """Вызов LLM с ретраями"""
    try:
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY не установлен")
        
        logger.info(f"Вызов LLM с текстом длиной {len(text)} символов")
        
        # Создаем клиент с учетом разных версий библиотеки
        try:
            # Временно очищаем переменные прокси, которые могут конфликтовать с OpenAI
            import os
            original_proxy_vars = {}
            proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']
            
            # Сохраняем оригинальные значения
            for var in proxy_vars:
                if var in os.environ:
                    original_proxy_vars[var] = os.environ[var]
                    del os.environ[var]
                    logger.info(f"Временно удалена переменная прокси: {var}")
            
            try:
                client = OpenAI(api_key=OPENAI_API_KEY)
            finally:
                # Восстанавливаем оригинальные значения
                for var, value in original_proxy_vars.items():
                    os.environ[var] = value
                    logger.info(f"Восстановлена переменная прокси: {var}")
                    
        except TypeError as e:
            if "proxies" in str(e):
                logger.warning("Ошибка с параметром proxies, создаем клиент без дополнительных параметров")
                # Пробуем создать клиент с минимальными параметрами
                client = OpenAI(api_key=OPENAI_API_KEY)
            else:
                raise
        
        # Ограничиваем текст до 12000 символов
        limited_text = text[:12000]
        logger.info(f"Ограниченный текст: {len(limited_text)} символов")
        
        # Проверяем кодировку текста
        try:
            limited_text.encode('utf-8')
            logger.info("Кодировка текста корректна")
        except UnicodeEncodeError as e:
            logger.error(f"Ошибка кодировки текста: {e}")
            limited_text = limited_text.encode('utf-8', errors='ignore').decode('utf-8')
            logger.info("Текст перекодирован с игнорированием ошибок")
        
        resp = client.chat.completions.create(
                model=LLM_MODEL,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": SYSTEM_45},
                    {"role": "user", "content": f"Проверь домашнюю работу по теме 4.5. Проанализируй ответы студента на вопросы по классификаци техник тестирования, терминологию, работу с багами, жизненным циклам.\n\nТекст работы:\n{limited_text}"},
                ],
                timeout=30
            )
        
        raw = resp.choices[0].message.content or ""
        logger.info(f"Получен ответ от LLM длиной {len(raw)} символов")
        
        data = safe_parse_json(raw) or {}
        logger.info(f"JSON парсинг: {len(data)} ключей")
        
        return {"raw": raw, "data": data}
        
    except Exception as e:
        logger.error(f"Ошибка в call_llm: {type(e).__name__}: {str(e)}")
        logger.error(f"Тип текста: {type(text)}, длина: {len(text) if text else 0}")
        raise


class AICheckRepository:
    """Репозиторий для работы с AI проверками"""
    
    def __init__(self, session):
        self.session = session
        from data_base.models import AIHomeworkCheck
        self.AIHomeworkCheck = AIHomeworkCheck
    
    def has_active_or_done(self, submission_id: int) -> bool:
        """Проверяет, есть ли уже активная или завершенная проверка"""
        check = self.session.query(self.AIHomeworkCheck).filter(
            self.AIHomeworkCheck.submission_id == submission_id,
            self.AIHomeworkCheck.status.in_(['running', 'done'])
        ).first()
        return check is not None
    
    def create_check(self, submission_id: int, topic: str, model: str, status: str = "running") -> int:
        """Создает новую запись проверки"""
        check = self.AIHomeworkCheck(
            submission_id=submission_id,
            topic=topic,
            model=model,
            status=status
        )
        self.session.add(check)
        self.session.commit()
        return check.id
    
    def update_check(self, check_id: int, status: str, result_json: str = None, raw_text: str = None):
        """Обновляет статус и результат проверки"""
        check = self.session.query(self.AIHomeworkCheck).filter_by(id=check_id).first()
        if check:
            check.status = status
            check.result_json = result_json
            check.raw_text = raw_text
            check.updated_at = datetime.utcnow()
            self.session.commit()


class TopicAttemptsRepository:
    """Репозиторий для работы с попытками сдачи тем через таблицу homework"""
    
    def __init__(self, session):
        self.session = session
        from data_base.models import Homework
        self.Homework = Homework
    
    def get_attempts(self, student_id: int, topic: str) -> dict:
        """Получает информацию о попытках студента по теме"""
        # Подсчитываем все сдачи по теме
        all_attempts = self.session.query(self.Homework).filter_by(
            student_id=student_id, 
            topic=topic
        ).order_by(self.Homework.created_at.desc()).all()
        
        attempts_count = len(all_attempts)
        
        # Проверяем, есть ли успешная сдача (статус "проверено")
        is_completed = any(hw.status == "проверено" for hw in all_attempts)
        
        # Определяем лучший результат (если есть AI проверки)
        best_score = 0
        for hw in all_attempts:
            if hw.ai_checks:
                for check in hw.ai_checks:
                    if check.status == "done" and check.result_json:
                        try:
                            import json
                            result = json.loads(check.result_json)
                            score = result.get("score", 0)
                            best_score = max(best_score, score)
                        except:
                            pass
        
        return {
            "attempts_count": attempts_count,
            "best_score": best_score,
            "is_completed": is_completed,
            "can_attempt": attempts_count < 2 and not is_completed
        }
    
    def record_attempt(self, student_id: int, topic: str, score: int) -> bool:
        """Записывает попытку и возвращает True если тема завершена"""
        # Просто возвращаем результат на основе оценки
        # Статус домашнего задания уже обновляется в HomeworkRepository
        return score >= 50


class HomeworkRepository:
    """Репозиторий для работы с домашними заданиями"""
    
    def __init__(self, session):
        self.session = session
        from data_base.models import Homework
        self.Homework = Homework
    
    def update_homework_status(self, homework_id: int, status: str):
        """Обновляет статус домашнего задания"""
        homework = self.session.query(self.Homework).filter_by(id=homework_id).first()
        if homework:
            homework.status = status
            self.session.commit()
    
    def count_topic_attempts(self, student_id: int, topic: str) -> int:
        """Подсчитывает количество сдач по теме"""
        count = self.session.query(self.Homework).filter_by(
            student_id=student_id,
            topic=topic
        ).count()
        return count


async def review_45_async(submission_id: int, extract_text_fn, get_submission_payload, repo, notify_student, notify_mentor):
    """
    Фоновая задача для проверки темы 4.5
    
    Args:
        submission_id - ID существующей сдачи
        extract_text_fn - функция извлечения текста (filename, bytes) -> str
        get_submission_payload - коллбек: (submission_id) -> dict(filename, file_bytes, student_username, mentor_id, topic, etc)
        repo - слой доступа к БД: create_check(), update_check(), get_check_by_submission()
        notify_student - коллбек отправки сообщения студенту
        notify_mentor - коллбек отправки сообщения ментору
    """
    logger.info(f"Запуск авто-проверки 4.5 для сдачи {submission_id}")
    
    # Создаем репозиторий если не передан
    if repo is None:
        from data_base.db import get_session
        with get_session() as db_session:
            repo = AICheckRepository(db_session)
    
    # Идемпотентность
    if repo.has_active_or_done(submission_id):
        logger.info(f"Проверка 4.5 для сдачи {submission_id} уже существует, пропускаем")
        return

    # Создаем запись проверки
    from data_base.db import get_session
    with get_session() as db_session:
        temp_repo = AICheckRepository(db_session)
        check_id = temp_repo.create_check(submission_id, topic="4.5", model=LLM_MODEL, status="running")

    try:
        payload = await get_submission_payload(submission_id)
        text = extract_text_fn(payload["filename"], payload["file_bytes"]).strip()
        
        if not text:
            logger.error(f"Не удалось извлечь текст из файла {payload['filename']} для сдачи {submission_id}")
            from data_base.db import get_session
            with get_session() as db_session:
                temp_repo = AICheckRepository(db_session)
                temp_repo.update_check(check_id, status="error", result_json=None, raw_text="empty_extract")
            await notify_student(payload["student_id"], "Автопроверка 4.5: не удалось извлечь текст из файла. Убедитесь, что файл содержит текст.")
            await notify_mentor(payload["mentor_id"], f"Автопроверка 4.5 по сдаче {submission_id}: не удалось извлечь текст из {payload['filename']}")
            return

        logger.info(f"Извлечен текст длиной {len(text)} символов для сдачи {submission_id}")
        logger.info(f"Первые 200 символов текста: {text[:200]}...")
        
        # Проверяем минимальную длину текста
        if len(text.strip()) < 50:
            logger.warning(f"Текст слишком короткий ({len(text)} символов) для сдачи {submission_id}")
            from data_base.db import get_session
            with get_session() as db_session:
                temp_repo = AICheckRepository(db_session)
                temp_repo.update_check(check_id, status="done", result_json=json.dumps({
                    "score": 0,
                    "pluses": [],
                    "mistakes": ["Текст слишком короткий для оценки", "Недостаточно информации для анализа"],
                    "tips": ["Предоставьте полные ответы на вопросы", "Используйте текстовый формат файла"],
                    "verdict": "Недостаточно информации для оценки"
                }, ensure_ascii=False), raw_text=None)
            
            await notify_student(payload["student_id"], 
                "Автопроверка 4.5: текст слишком короткий для оценки. Убедитесь, что файл содержит полные ответы на вопросы.")
            await notify_mentor(payload["mentor_id"], 
                f"Автопроверка 4.5 по сдаче {submission_id}: текст слишком короткий ({len(text)} символов)")
            return
        
        try:
            result = await asyncio.get_running_loop().run_in_executor(None, call_llm, text)
            data = result.get("data") or {}
            score = data.get("score")
            pluses = data.get("pluses", [])
            mistakes = data.get("mistakes", [])
            tips = data.get("tips", [])
            verdict = data.get("verdict", "")

            from data_base.db import get_session
            with get_session() as db_session:
                temp_repo = AICheckRepository(db_session)
                temp_repo.update_check(check_id, status="done", result_json=json.dumps(data, ensure_ascii=False), raw_text=None)
                
        except Exception as llm_error:
            logger.error(f"Ошибка при вызове LLM для сдачи {submission_id}: {type(llm_error).__name__}: {str(llm_error)}")
            
            # Обновляем статус на ошибку
            from data_base.db import get_session
            with get_session() as db_session:
                temp_repo = AICheckRepository(db_session)
                temp_repo.update_check(check_id, status="error", result_json=None, raw_text=f"LLM error: {str(llm_error)}")
            
            # Уведомляем пользователей об ошибке
            await notify_student(payload["student_id"], 
                "Автопроверка 4.5: произошла ошибка при проверке. Работа отправлена ментору для ручной проверки.")
            await notify_mentor(payload["mentor_id"], 
                f"Автопроверка 4.5 по сдаче {submission_id}: ошибка LLM - {type(llm_error).__name__}: {str(llm_error)}")
            return

                # Обрабатываем результат и обновляем статусы
        from data_base.db import get_session
        
        # Получаем информацию о попытках и обновляем статусы
        with get_session() as db_session:
            attempts_repo = TopicAttemptsRepository(db_session)
            homework_repo = HomeworkRepository(db_session)
            
            # Определяем завершение темы
            is_completed = score >= 50
            
            # Обновляем статус домашнего задания
            if score >= 50:
                homework_repo.update_homework_status(submission_id, "проверено")
                status_msg = "✅ Задание принято!"
            else:
                homework_repo.update_homework_status(submission_id, "не принято")
                status_msg = "❌ Задание не принято (оценка меньше 50)"
            
            # Получаем информацию о попытках
            attempts_info = attempts_repo.get_attempts(payload["student_id"], "Тема 4.5")

        # Студенту
        msg_student = (
            f"✅ Проверка 4.5 готова\n"
            f"Оценка: {score}/100\n"
            f"Статус: {status_msg}\n"
            f"Итог: {verdict}\n"
        )
        if pluses:
            msg_student += "Плюсы:\n" + "\n".join(f"{p}" for p in pluses[:4]) + "\n\n"
        if mistakes:
            msg_student += "Ошибки:\n" + "\n".join(f"{m}" for m in mistakes[:5]) + "\n"
        if tips:
            msg_student += "Советы:\n" + "\n".join(f"{t}" for t in tips[:5])
        
        # Добавляем информацию о попытках
        current_attempt = attempts_info["attempts_count"]
        
        if attempts_info["is_completed"]:
            msg_student += "\n\n🎉 Тема 4.5 завершена!"
        elif current_attempt >= 2 and score < 50:
            # Вторая или последующая неудачная попытка - показываем сообщение о лимите
            msg_student += "\n\n⚠️ Вы исчерпали две попытки на самопроверку. Работа отправлена ментору для личной проверки."
        elif current_attempt < 2:
            remaining = 2 - current_attempt
            msg_student += f"\n\n🔄 Осталось попыток: {remaining}"
        
        await notify_student(payload["student_id"], msg_student)

        # Ментору
        msg_mentor = (
            f"Ученик {payload.get('student_username') or payload['student_id']} сдал 4.5\n"
            f"Оценка: {score}/100 — {verdict}\n"
            f"Статус: {status_msg}\n"
            f"Попытка: {attempts_info['attempts_count']}/2"
        )
        await notify_mentor(payload["mentor_id"], msg_mentor)
        
        logger.info(f"Авто-проверка 4.5 для сдачи {submission_id} завершена успешно")

    except Exception as e:
        logger.error(f"Ошибка авто-проверки 4.5 для сдачи {submission_id}: {e}")
        
        # Определяем тип ошибки для более точного сообщения
        error_message = str(e)
        if "PermissionDeniedError" in error_message or "Permission" in error_message:
            user_message = "Автопроверка 4.5: проблема с обработкой файла. Попробуйте сохранить документ в формате PDF или TXT."
            mentor_message = f"Автопроверка 4.5 по сдаче {submission_id}: ошибка прав доступа к файлу"
        elif "RetryError" in error_message:
            user_message = "Автопроверка 4.5: временная ошибка обработки. Работа передана на ручную проверку."
            mentor_message = f"Автреберка 4.5 по сдаче {submission_id}: ошибка ретраев - {e}"
        else:
            user_message = "Автопроверка 4.5 временно недоступна, работа передана на ручную проверку."
            mentor_message = f"Автопроверка 4.5 по сдаче {submission_id} не удалась: {e}"
        
        from data_base.db import get_session
        with get_session() as db_session:
            temp_repo = AICheckRepository(db_session)
            temp_repo.update_check(check_id, status="error", result_json=None, raw_text=error_message)
        
        # Уведомления об ошибке
        try:
            payload = await get_submission_payload(submission_id)
            await notify_student(payload["student_id"], user_message)
            await notify_mentor(payload["mentor_id"], mentor_message)
        except Exception as notify_error:
            logger.error(f"Ошибка отправки уведомлений об ошибке: {notify_error}") 