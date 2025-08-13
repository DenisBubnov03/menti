import functools
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from data_base.db import session
from data_base.models import Student

# Ссылка на правила
RULES_URL = "https://thankful-candy-c57.notion.site/21794f774aab80d299cdc4d2255ad0a6"

def check_rules_accepted(func):
    """Декоратор для проверки принятия правил"""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        # Проверяем, является ли пользователь студентом
        student_telegram = f"@{update.message.from_user.username}"
        student = session.query(Student).filter_by(telegram=student_telegram).first()
        
        # Если это студент и он не принял правила
        if student and not student.rules_accepted:
            keyboard = [
                [InlineKeyboardButton("📖 Читать правила", url=RULES_URL)],
                [InlineKeyboardButton("📋 Показать кнопку принятия", callback_data="show_accept")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message_text = (
                "🚫 **Доступ заблокирован!**\n\n"
                "Для использования функций бота необходимо принять правила пользования и обучения.\n\n"
                "⚠️ **Важно:** Пожалуйста, внимательно прочитайте все правила перед принятием.\n\n"
                "1. Нажмите «Читать правила» чтобы открыть правила\n"
                "2. После ознакомления нажмите «Показать кнопку принятия»"
            )
            
            await update.message.reply_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return
        
        # Если правила приняты или это не студент, выполняем оригинальную функцию
        return await func(update, context, *args, **kwargs)
    
    return wrapper

def check_rules_accepted_callback(func):
    """Декоратор для проверки принятия правил в callback-функциях"""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        # Проверяем, является ли пользователь студентом
        student_telegram = f"@{update.callback_query.from_user.username}"
        student = session.query(Student).filter_by(telegram=student_telegram).first()
        
        # Если это студент и он не принял правила
        if student and not student.rules_accepted:
            keyboard = [
                [InlineKeyboardButton("📖 Читать правила", url=RULES_URL)],
                [InlineKeyboardButton("📋 Показать кнопку принятия", callback_data="show_accept")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message_text = (
                "🚫 **Доступ заблокирован!**\n\n"
                "Для использования функций бота необходимо принять правила пользования и обучения.\n\n"
                "⚠️ **Важно:** Пожалуйста, внимательно прочитайте все правила перед принятием.\n\n"
                "1. Нажмите «Читать правила» чтобы открыть правила\n"
                "2. После ознакомления нажмите «Показать кнопку принятия»"
            )
            
            await update.callback_query.answer("Необходимо принять правила!")
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return
        
        # Если правила приняты или это не студент, выполняем оригинальную функцию
        return await func(update, context, *args, **kwargs)
    
    return wrapper 