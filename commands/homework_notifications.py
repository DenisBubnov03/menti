from datetime import datetime, timedelta
from telegram import Bot
from data_base.db import session
from data_base.models import Homework, Student, Mentor
import asyncio
import logging
from dotenv import load_dotenv
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

load_dotenv()
# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_unreviewed_homework(bot: Bot):
    """
    Проверяет домашние задания, которые не проверены больше недели
    и отправляет уведомления менторам и директору
    """
    try:
        # Получаем дату неделю назад
        week_ago = datetime.now() - timedelta(days=7)
        
        # Находим домашние задания, которые не проверены больше недели
        unreviewed_homework = session.query(Homework).filter(
            Homework.status == "ожидает проверки",
            Homework.created_at < week_ago
        ).all()
        
        if not unreviewed_homework:
            logger.info("Нет непроверенных домашних заданий старше недели")
            return
        
        # Группируем по менторам для отправки уведомлений
        mentor_notifications = {}
        director_notifications = []
        
        for hw in unreviewed_homework:
            # Получаем информацию о студенте
            student = session.query(Student).filter_by(id=hw.student_id).first()
            if not student:
                continue
                
            # Получаем ментора
            mentor = None
            if hw.mentor_id:
                mentor = session.query(Mentor).filter_by(id=hw.mentor_id).first()
            
            # Формируем сообщение
            hw_info = f"📚 ДЗ #{hw.id}: {student.fio} - {hw.module}, {hw.topic}, ментор {mentor.telegram}\n"
            hw_info += f"📅 Отправлено: {hw.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            hw_info += f"⏰ Не проверено: {(datetime.now() - hw.created_at).days} дней\n"
            
            # Добавляем в уведомления для ментора
            if mentor and mentor.chat_id:
                if mentor.id not in mentor_notifications:
                    mentor_notifications[mentor.id] = {
                        'mentor': mentor,
                        'homeworks': []
                    }
                mentor_notifications[mentor.id]['homeworks'].append(hw_info)
            
            # Добавляем в уведомления для директора
            director_notifications.append(hw_info)
        
        # Отправляем уведомления менторам
        for mentor_id, data in mentor_notifications.items():
            mentor = data['mentor']
            homeworks = data['homeworks']
            
            message = f"⚠️ ВНИМАНИЕ! У вас есть непроверенные домашние задания старше недели:\n\n"
            message += "".join(homeworks)
            message += "\nПожалуйста, проверьте их как можно скорее!"
            
            try:
                await bot.send_message(
                    chat_id=mentor.chat_id,
                    text=message
                )
                logger.info(f"Уведомление отправлено ментору {mentor.full_name}")
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления ментору {mentor.full_name}: {e}")
        
        # Отправляем уведомление директору (ID=1)
        if director_notifications:
            director = session.query(Mentor).filter_by(id=1).first()
            if director and director.chat_id:
                message = f"🚨 ВНИМАНИЕ ДИРЕКТОРУ! Есть непроверенные домашние задания старше недели:\n\n"
                message += "".join(director_notifications)
                message += f"\nВсего непроверенных ДЗ: {len(director_notifications)}"
                
                try:
                    await bot.send_message(
                        chat_id=director.chat_id,
                        text=message
                    )
                    logger.info("Уведомление отправлено директору")
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления директору: {e}")
        
        logger.info(f"Проверка завершена. Найдено {len(unreviewed_homework)} непроверенных ДЗ")
        
    except Exception as e:
        logger.error(f"Ошибка при проверке непроверенных домашних заданий: {e}")




async def manual_check_notifications(bot: Bot):
    """
    Ручная проверка уведомлений (для тестирования)
    """
    await check_unreviewed_homework(bot)
    return "Проверка завершена"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if __name__ == "__main__":
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TELEGRAM_TOKEN:
        logger.error("❌ Не задан TELEGRAM_BOT_TOKEN")
    else:
        asyncio.run(check_unreviewed_homework(Bot(token=TELEGRAM_TOKEN)))
