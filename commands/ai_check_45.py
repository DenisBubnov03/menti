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

# Проверяем переменные окружения
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# Логируем информацию о переменных окружения
if OPENAI_API_KEY:
    logger.info(f"OPENAI_API_KEY найден: {OPENAI_API_KEY[:10]}...")
    if not OPENAI_API_KEY.startswith("sk-"):
        logger.warning(f"OPENAI_API_KEY имеет неправильный формат: {OPENAI_API_KEY[:20]}...")
else:
    logger.error("OPENAI_API_KEY не установлен!")

logger.info(f"LLM_MODEL: {LLM_MODEL}")

# Проверяем переменные прокси, которые могут вызывать проблемы
proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'no_proxy']
proxy_found = False
for var in proxy_vars:
    if os.getenv(var):
        proxy_found = True
        logger.warning(f"Обнаружена переменная прокси {var}: {os.getenv(var)[:20]}...")
        logger.warning("Это может вызывать проблемы с OpenAI API")

if proxy_found:
    logger.warning("ВНИМАНИЕ: Обнаружены переменные прокси! Система будет временно их отключать при создании OpenAI клиента.")
else:
    logger.info("Переменные прокси не обнаружены")

# SYSTEM_45 = """
# Ты — проверяющий домашнюю работу по теме 4.5.
# Проверяй строго по вопросам. Если есть «Вопрос 1/2/…» — используй номера; иначе бери ключевые слова.
# Если ошибок нет, то не придумывай их. Орфографию и структурирование  во внимание не бери.
# Сильную проверку на обязательные поля в баг репортах, жизненых циклах и прочее не делай, но внимательно проверяй на то, чтоб не указать имеющий пункт в ошибке
#
# Формат ответа (обязательно соблюдать, если ошибок нет, то не упоминать и не придумывать):
# ✅ Проверка 4.5 готова
# Оценка: <балл>/100
# Статус: ✅ Задание принято!
# Итог: <одно предложение о результате>
#
# Плюсы:
# • 2–4 пункта (только реально сильные стороны, без противоречий с ошибками)
#
# Ошибки:
# ❌ Вопрос N. <Название вопроса или ключ>
# - Проблема: <в чём ошибка или что не раскрыто>
# - Как исправить: <чёткий исправленный текст или список пунктов>
#
# Для вопросов с перечислением ответов:
# В 'Как исправить' сначала добавляется, что необходимо добавить, а затем писать с новой строки: 'У вас перечислено: <Перечисление ответов>'.
#
# Советы:
# • 3–5 конкретных рекомендаций
# """
SYSTEM_45 = """Проверь правильно ли все. На терминологию и оформление не обращай внимание
Формат ответа :
✅ Проверка 4.5 готова
Оценка: <балл>/100
Статус: ✅ Задание принято! (Если меньше 50 баллов, то писать <❌ Задание не принято!>
Итог: <одно предложение о результате>

Похвали за работу"""


def extract_score_from_text(text: str) -> int:
    """Извлекает оценку из текстового ответа LLM"""
    try:
        # Ищем строку с оценкой
        lines = text.split('\n')
        for line in lines:
            if 'Оценка:' in line:
                # Извлекаем число из строки типа "Оценка: 85/100"
                import re
                match = re.search(r'(\d+)/100', line)
                if match:
                    score = int(match.group(1))
                    if 0 <= score <= 100:
                        return score
        return None
    except Exception as e:
        logger.error(f"Ошибка извлечения оценки из текста: {e}")
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
                # Используем более детальное извлечение текста
                page_text = page.get_text("text")  # Явно указываем формат
                text += page_text + "\n"  # Добавляем перенос строки между страницами
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
                        if paragraph.text:  # Убираем .strip() чтобы сохранить пробелы
                            text += paragraph.text + "\n"
                    
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
                                if cell_value is not None and str(cell_value):
                                    row_text += str(cell_value) + " | "  # Убираем .strip()
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
            # TXT файл - пробуем разные кодировки
            encodings = ['utf-8', 'utf-8-sig', 'cp1251', 'windows-1251', 'latin-1']
            for encoding in encodings:
                try:
                    text = content.decode(encoding, errors='ignore')
                    logger.info(f"TXT извлечено с кодировкой {encoding}: {len(text)} символов")
                    return text
                except UnicodeDecodeError:
                    continue
            
            # Если ни одна кодировка не подошла, используем utf-8 с игнорированием ошибок
            text = content.decode('utf-8', errors='ignore')
            logger.info(f"TXT извлечено с fallback кодировкой: {len(text)} символов")
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
def call_llm_with_file(filename: str, file_content: bytes) -> str:
    """Вызов LLM с прямым файлом"""
    try:
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY не установлен")
        
        logger.info(f"Вызов LLM с файлом: {filename}, размер: {len(file_content)} байт")
        
        # Создаем клиент OpenAI
        try:
            # Временно очищаем переменные прокси из окружения
            original_proxy_vars = {}
            proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'no_proxy']
            
            for var in proxy_vars:
                if var in os.environ:
                    original_proxy_vars[var] = os.environ[var]
                    del os.environ[var]
                    logger.info(f"Временно удалена переменная прокси: {var}")
            
            try:
                # Создаем клиент без прокси
                client = OpenAI(api_key=OPENAI_API_KEY)
                logger.info("OpenAI клиент для файлов успешно создан")
            finally:
                # Восстанавливаем переменные прокси
                for var, value in original_proxy_vars.items():
                    os.environ[var] = value
                    logger.info(f"Восстановлена переменная прокси: {var}")
                    
        except Exception as client_error:
            logger.error(f"Ошибка создания OpenAI клиента для файлов: {type(client_error).__name__}: {client_error}")
            
            # Если не можем создать клиент, используем fallback
            logger.warning("OpenAI API недоступен для файлов, используем fallback")
            raise ValueError("OpenAI клиент недоступен")
        
        # Проверяем, поддерживается ли формат для прямой отправки
        # gpt-4o-mini поддерживает только PDF файлы
        if not filename.lower().endswith('.pdf'):
            raise ValueError(f"Формат {filename} не поддерживается для прямой отправки в {LLM_MODEL}. Поддерживается только PDF.")
        
        mime_type = "application/pdf"
        
        logger.info(f"Используем MIME тип: {mime_type}")
        
        # Проверяем размер файла (OpenAI ограничение ~20MB)
        if len(file_content) > 20 * 1024 * 1024:  # 20MB
            raise ValueError(f"Файл слишком большой: {len(file_content)} байт (максимум 20MB)")
        
        # Проверяем, поддерживает ли модель работу с файлами
        if "gpt-4o" in LLM_MODEL.lower():
            # Для GPT-4o сначала загружаем файл, затем используем file_id
            import tempfile
            import os
            
            # Создаем временный файл
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as temp_file:
                temp_file.write(file_content)
                temp_file.flush()
                
                try:
                    # Загружаем файл в OpenAI
                    with open(temp_file.name, 'rb') as f:
                        uploaded_file = client.files.create(
                            file=f,
                            purpose="assistants"
                        )
                    
                    logger.info(f"Файл загружен в OpenAI с ID: {uploaded_file.id}")
                    
                    # Используем file_id в запросе
                    resp = client.chat.completions.create(
                        model=LLM_MODEL,
                        temperature=0.2,
                        messages=[
                            {"role": "system", "content": SYSTEM_45},
                            {
                                "role": "user", 
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Проверь домашнюю работу по теме 4.5. "
                                                "Проанализируй ответы студента на вопросы по классификации техник тестирования, терминологию, работу с багами, жизненным циклам."
                                                "Не обращай внимание на сокращение/упрощения слов, к примеру Kuber = Kubernetes. Техники тест дизайна допускаются не стандартные, это подсвечивать не надо. "
                                                "Так же наличие примеров не обязательно."
                                    },
                                    {
                                        "type": "file",
                                        "file": {
                                            "file_id": uploaded_file.id
                                        }
                                    }
                                ]
                            }
                        ],
                        timeout=60  # Увеличиваем timeout для файлов
                    )
                    
                    # Удаляем временный файл
                    os.unlink(temp_file.name)
                    
                except Exception as upload_error:
                    # Удаляем временный файл в случае ошибки
                    try:
                        os.unlink(temp_file.name)
                    except:
                        pass
                    raise upload_error
                    
        else:
            # Для других моделей используем старый формат
            raise ValueError(f"Модель {LLM_MODEL} не поддерживает работу с файлами")
        
        result = resp.choices[0].message.content or ""
        logger.info(f"Получен ответ от LLM длиной {len(result)} символов")
        
        return result
        
    except Exception as e:
        logger.error(f"Ошибка в call_llm_with_file: {type(e).__name__}: {str(e)}")
        logger.error(f"Файл: {filename}, размер: {len(file_content) if file_content else 0}")
        logger.error(f"Модель: {LLM_MODEL}, MIME тип: {mime_type}")
        logger.error(f"Полная ошибка: {e}")
        raise


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=0.5, max=4))
def call_llm(text: str) -> str:
    """Вызов LLM с текстом (fallback)"""
    try:
        # Проверяем API ключ
        if not OPENAI_API_KEY:
            logger.error("OPENAI_API_KEY не установлен")
            raise ValueError("OPENAI_API_KEY не установлен")
        
        # Проверяем формат API ключа
        if not OPENAI_API_KEY.startswith("sk-"):
            logger.error(f"Неправильный формат OPENAI_API_KEY: {OPENAI_API_KEY[:10]}...")
            raise ValueError("Неправильный формат OPENAI_API_KEY")
        
        logger.info(f"Вызов LLM с текстом длиной {len(text)} символов")
        logger.info(f"Используем модель: {LLM_MODEL}")
        logger.info(f"API ключ: {OPENAI_API_KEY[:10]}...")
        
        # Создаем клиент OpenAI
        try:
            # Временно очищаем переменные прокси из окружения
            original_proxy_vars = {}
            proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'no_proxy']
            
            for var in proxy_vars:
                if var in os.environ:
                    original_proxy_vars[var] = os.environ[var]
                    del os.environ[var]
                    logger.info(f"Временно удалена переменная прокси: {var}")
            
            try:
                # Создаем клиент без прокси
                client = OpenAI(api_key=OPENAI_API_KEY)
                logger.info("OpenAI клиент успешно создан")
            finally:
                # Восстанавливаем переменные прокси
                for var, value in original_proxy_vars.items():
                    os.environ[var] = value
                    logger.info(f"Восстановлена переменная прокси: {var}")
                    
        except Exception as client_error:
            logger.error(f"Ошибка создания OpenAI клиента: {type(client_error).__name__}: {client_error}")
            
            # Если все еще не работает, используем fallback
            logger.warning("OpenAI API недоступен, используем базовую оценку")
            return generate_basic_assessment(text)
        
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
        
        result = resp.choices[0].message.content or ""
        logger.info(f"Получен ответ от LLM длиной {len(result)} символов")
        
        return result
        
    except Exception as e:
        logger.error(f"Ошибка в call_llm: {type(e).__name__}: {str(e)}")
        logger.error(f"Тип текста: {type(text)}, длина: {len(text) if text else 0}")
        
        # Если OpenAI недоступен, возвращаем базовую оценку
        if "OPENAI_API_KEY" in str(e) or "Client.init" in str(e):
            logger.warning("OpenAI API недоступен, используем базовую оценку")
            return generate_basic_assessment(text)
        
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
                    if check.status == "done" and check.raw_text:
                        try:
                            score = extract_score_from_text(check.raw_text)
                            if score is not None:
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
        """Записывает попытку и возвращает True если тема завершена (порог 50 баллов)"""
        # Просто возвращаем результат на основе оценки
        # Статус домашнего задания уже обновляется в HomeworkRepository
        return score is not None and score >= 50


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
        
        # Проверяем размер файла
        if len(payload["file_bytes"]) < 100:
            logger.error(f"Файл слишком маленький ({len(payload['file_bytes'])} байт) для сдачи {submission_id}")
            from data_base.db import get_session
            with get_session() as db_session:
                temp_repo = AICheckRepository(db_session)
                temp_repo.update_check(check_id, status="error", result_json=None, raw_text="file_too_small")
            await notify_student(payload["student_id"], "Автопроверка 4.5: файл слишком маленький. Убедитесь, что файл содержит данные.")
            await notify_mentor(payload["mentor_id"], f"Автопроверка 4.5 по сдаче {submission_id}: файл слишком маленький ({len(payload['file_bytes'])} байт)")
            return
        
        logger.info(f"Отправляем файл {payload['filename']} размером {len(payload['file_bytes'])} байт напрямую в LLM")
        
        try:
            # Пробуем отправить файл напрямую в LLM
            llm_response = await asyncio.get_running_loop().run_in_executor(
                None, 
                call_llm_with_file, 
                payload["filename"], 
                payload["file_bytes"]
            )
            
            # Извлекаем оценку из текстового ответа
            score = extract_score_from_text(llm_response)
            
            # Проверяем корректность score
            if score is not None:
                if score < 0 or score > 100:
                    logger.warning(f"Некорректный score {score} для сдачи {submission_id}, устанавливаем None")
                    score = None

            from data_base.db import get_session
            with get_session() as db_session:
                temp_repo = AICheckRepository(db_session)
                temp_repo.update_check(check_id, status="done", result_json=None, raw_text=llm_response)
                
        except Exception as llm_error:
            logger.error(f"Ошибка при прямой отправке файла в LLM для сдачи {submission_id}: {type(llm_error).__name__}: {str(llm_error)}")
            
            # Логируем ошибку для диагностики
            logger.error(f"Ошибка при отправке файла: {llm_error}")
            
            # Проверяем, является ли это ошибкой неподдерживаемого формата
            if "не поддерживается" in str(llm_error) or "Expected a file with an application/pdf" in str(llm_error):
                logger.info(f"Формат файла не поддерживается для прямой отправки, переключаемся на fallback")
            else:
                logger.error(f"Неожиданная ошибка при отправке файла: {llm_error}")
            
            logger.info(f"Переключаемся на fallback метод")
            
            # Пробуем fallback - извлекаем текст и отправляем как раньше
            logger.info(f"Пробуем fallback метод для сдачи {submission_id}")
            try:
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
                
                logger.info(f"Fallback: извлечен текст длиной {len(text)} символов для сдачи {submission_id}")
                logger.info(f"Fallback: первые 300 символов: {text[:300]}...")
                
                # Проверяем наличие ключевых слов в fallback
                text_lower = text.lower()
                keywords = ['безопасность', 'нагрузочное', 'юзабилити', 'совместимость', 'установка', 'регресс', 'смоук', 'ретест']
                found_keywords = [kw for kw in keywords if kw in text_lower]
                logger.info(f"Fallback: найденные ключевые слова: {found_keywords}")
                
                # Проверяем минимальную длину текста
                if len(text.strip()) < 50:
                    logger.warning(f"Fallback: текст слишком короткий ({len(text)} символов) для сдачи {submission_id}")
                    from data_base.db import get_session
                    with get_session() as db_session:
                        temp_repo = AICheckRepository(db_session)
                        temp_repo.update_check(check_id, status="done", result_json=None, raw_text="Текст слишком короткий для оценки")
                    
                    await notify_student(payload["student_id"], 
                        "Автопроверка 4.5: текст слишком короткий для оценки. Убедитесь, что файл содержит полные ответы на вопросы.")
                    await notify_mentor(payload["mentor_id"], 
                        f"Автопроверка 4.5 по сдаче {submission_id}: текст слишком короткий ({len(text)} символов)")
                    return
                
                # Отправляем извлеченный текст
                llm_response = await asyncio.get_running_loop().run_in_executor(None, call_llm, text)
                
                # Извлекаем оценку из текстового ответа (fallback)
                score = extract_score_from_text(llm_response)
                
                # Проверяем корректность score
                if score is not None:
                    if score < 0 or score > 100:
                        logger.warning(f"Fallback: некорректный score {score} для сдачи {submission_id}, устанавливаем None")
                        score = None
                
                # Обновляем статус в fallback
                from data_base.db import get_session
                with get_session() as db_session:
                    temp_repo = AICheckRepository(db_session)
                    temp_repo.update_check(check_id, status="done", result_json=None, raw_text=llm_response)
                
            except Exception as fallback_error:
                logger.error(f"Ошибка в fallback методе для сдачи {submission_id}: {type(fallback_error).__name__}: {str(fallback_error)}")
                
                # Обновляем статус на ошибку
                from data_base.db import get_session
                with get_session() as db_session:
                    temp_repo = AICheckRepository(db_session)
                    temp_repo.update_check(check_id, status="error", result_json=None, raw_text=f"LLM error: {str(llm_error)} + fallback error: {str(fallback_error)}")
                
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
            
            # Определяем завершение темы (порог 50 баллов)
            is_completed = score is not None and score >= 50
            
            # Обновляем статус домашнего задания
            if score is not None and score >= 50:
                homework_repo.update_homework_status(submission_id, "проверено")
                status_msg = "✅ Задание принято!"
            elif score is None:
                homework_repo.update_homework_status(submission_id, "не принято")
                status_msg = "❌ Задание не принято (ошибка оценки)"
            else:
                homework_repo.update_homework_status(submission_id, "не принято")
                status_msg = "❌ Задание не принято!"
            
            # Получаем информацию о попытках
            attempts_info = attempts_repo.get_attempts(payload["student_id"], "Тема 4.5")

        # Студенту - используем готовый ответ LLM
        msg_student = llm_response
        
        # Добавляем информацию о попытках
        current_attempt = attempts_info["attempts_count"]
        
        # Добавляем информацию о попытках в конец сообщения
        attempts_info_text = ""
        if attempts_info["is_completed"]:
            attempts_info_text = "\n\n🎉 Тема 4.5 завершена!"
        elif current_attempt >= 2 and (score is None or score < 50):
            # Вторая или последующая неудачная попытка - показываем сообщение о лимите
            attempts_info_text = "\n\n⚠️ Вы исчерпали две попытки на самопроверку. Работа отправлена ментору для личной проверки."
        elif current_attempt < 2:
            remaining = 2 - current_attempt
            attempts_info_text = f"\n\n🔄 Осталось попыток: {remaining}"
        
        # Добавляем информацию о попытках в конец сообщения
        if attempts_info_text:
            msg_student += attempts_info_text
        
        await notify_student(payload["student_id"], msg_student)

        # Ментору - извлекаем информацию из ответа LLM
        score_display = score if score is not None else "Ошибка оценки"
        # Ищем статус в ответе LLM
        status_from_llm = "Статус не определен"
        for line in llm_response.split('\n'):
            if 'Статус:' in line:
                status_from_llm = line.split('Статус:')[1].strip()
                break
        
        msg_mentor = (
            f"Ученик {payload.get('student_username') or payload['student_id']} сдал 4.5\n"
            f"Оценка: {score_display}/100\n"
            f"Статус: {status_from_llm}\n"
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


def generate_basic_assessment(text: str) -> str:
    """Генерирует базовую оценку, когда OpenAI API недоступен"""
    try:
        # Простая логика оценки на основе длины текста и ключевых слов
        text_lower = text.lower()
        
        # Ищем ключевые слова
        keywords = ['безопасность', 'нагрузочное', 'юзабилити', 'совместимость', 'установка', 'регресс', 'смоук', 'ретест']
        found_keywords = [kw for kw in keywords if kw in text_lower]
        
        # Базовая оценка на основе длины и ключевых слов
        base_score = min(100, max(0, len(text) // 100 + len(found_keywords) * 10))
        
        # Определяем статус
        if base_score >= 50:
            status = "✅ Задание принято!"
        else:
            status = "❌ Задание не принято!"
        
        assessment = f"""✅ Проверка 4.5 готова
Оценка: {base_score}/100
Статус: {status}
Итог: Базовая оценка (OpenAI API недоступен)

Плюсы:
• Текст содержит {len(found_keywords)} ключевых терминов
• Длина ответа: {len(text)} символов

Ошибки:
❌ Вопрос 1. Автоматическая проверка
- Проблема: OpenAI API недоступен, используется базовая оценка
- Как исправить: Обратитесь к ментору для детальной проверки

Советы:
• Дождитесь восстановления автоматической проверки
• Или обратитесь к ментору для ручной проверки

🎉 Тема 4.5 проверена (базовая оценка)"""
        
        return assessment
        
    except Exception as e:
        logger.error(f"Ошибка в generate_basic_assessment: {e}")
        return "❌ Ошибка автоматической проверки. Обратитесь к ментору." 