from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from data_base.db import session
from data_base.models import Student

# Состояния для ConversationHandler
RULES_ACCEPTANCE = "RULES_ACCEPTANCE"

# Ссылка на правила
RULES_URL = "https://thankful-candy-c57.notion.site/21794f774aab80d299cdc4d2255ad0a6"

async def check_rules_acceptance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверяет, принял ли пользователь правила"""
    student_telegram = f"@{update.message.from_user.username}"
    student = session.query(Student).filter_by(telegram=student_telegram).first()
    
    if not student:
        return False  # Студент не найден, показываем правила
    
    return student.rules_accepted

async def show_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает правила пользования и обучения"""
    keyboard = [
        [InlineKeyboardButton("📖 Читать правила", url=RULES_URL)],
        [InlineKeyboardButton("📋 Показать кнопку принятия", callback_data="show_accept")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = (
        "📋 **Правила пользования и обучения**\n\n"
        "Для продолжения работы с ботом необходимо ознакомиться и принять правила пользования и обучения.\n\n"
        "⚠️ **Важно:** Пожалуйста, внимательно прочитайте все правила перед принятием.\n\n"
        "1. Нажмите «Читать правила» чтобы открыть правила\n"
        "2. После ознакомления нажмите «Показать кнопку принятия»"
    )
    
    await update.message.reply_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def accept_rules_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия кнопки принятия правил"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "show_accept":
        # Показываем кнопку принятия правил
        keyboard = [
            [InlineKeyboardButton("✅ Принял правила", callback_data="accept_rules")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = (
            "✅ **Готовы принять правила?**\n\n"
            "Если вы ознакомились с правилами и согласны с ними, нажмите кнопку «Принял правила».\n\n"
            "⚠️ **Важно:** Принятие правил обязательно для использования бота.\n\n"
            "Если у вас есть вопросы по правилам, обратитесь к администратору."
        )
        
        await query.edit_message_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    if query.data == "accept_rules":
        student_telegram = f"@{query.from_user.username}"
        student = session.query(Student).filter_by(telegram=student_telegram).first()
        
        if student:
            student.rules_accepted = True
            session.commit()
            
            await query.edit_message_text(
                "✅ **Правила приняты!**\n\n"
                "Теперь вы можете пользоваться всеми функциями бота.\n"
                "Добро пожаловать в систему обучения! 🎓",
                parse_mode='Markdown'
            )
            
            # Показываем главное меню после принятия правил
            from telegram import ReplyKeyboardMarkup, KeyboardButton
            keyboard_buttons = [
                [KeyboardButton("🆕 Получить новую тему")],
                [KeyboardButton("🐛 Бесконечные баги")],
                [KeyboardButton("📚 Отправить домашку")],
                [KeyboardButton("📜 Мои темы и ссылки")],
                [KeyboardButton("📅 Записаться на звонок")],
                [KeyboardButton("💳 Оплата за обучение")],
                [KeyboardButton("💸 Выплата комиссии")],
                [KeyboardButton("📋 Правила")],
            ]
            keyboard = ReplyKeyboardMarkup(
                keyboard=keyboard_buttons,
                resize_keyboard=True
            )
            
            # Отправляем новое сообщение с главным меню
            await context.bot.send_message(
                chat_id=query.from_user.id,
                text="🔙 Вы вернулись в главное меню.",
                reply_markup=keyboard
            )
        else:
            await query.edit_message_text(
                "❌ **Ошибка!**\n\n"
                "Студент не найден в системе. Обратитесь к администратору.",
                parse_mode='Markdown'
            )

async def force_rules_acceptance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принудительно показывает правила, если пользователь не принял их"""
    return await show_rules(update, context)

 