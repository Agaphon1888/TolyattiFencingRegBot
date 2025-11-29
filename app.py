from flask import Flask, request, jsonify, render_template_string
from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
from telegram.error import RetryAfter, Unauthorized, TelegramError
import logging
import time
from datetime import datetime
from config import Config
from database import Database

# === 1. Инициализация приложения и базы данных ===
app = Flask(__name__)
app.config.from_object(Config)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация базы данных ДО использования в декораторах
db = Database()

# === 2. Декораторы доступа ===
def admin_required(func):
    """Декоратор для проверки прав администратора"""
    def wrapper(update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        if not db.admin_manager.is_admin(user_id):
            update.message.reply_text("❌ У вас нет прав администратора.")
            return
        return func(update, context)
    return wrapper

def super_admin_required(func):
    """Декоратор для проверки прав супер-администратора"""
    def wrapper(update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        if not db.admin_manager.is_super_admin(user_id):
            update.message.reply_text("❌ У вас нет прав супер-администратора.")
            return
        return func(update, context)
    return wrapper

# === 3. Обработчики команд администратора ===
@admin_required
def admin_stats(update: Update, context: CallbackContext):
    """Статистика для администратора"""
    try:
        stats = db.get_stats()
        admin_stats = db.admin_manager.get_admin_stats()

        message = f"""
📊 *Статистика системы:*

*Заявки:*
• Всего: {stats['total']}
• Ожидают: {stats['pending']}
• Подтверждены: {stats['confirmed']}
• Отклонены: {stats['rejected']}

*Администраторы:*
• Всего: {admin_stats['total']}
• Админы: {admin_stats['admins']}
• Модераторы: {admin_stats['moderators']}

*По оружию:*
"""

        for weapon, weapon_stats in stats['weapons'].items():
            message += f"• {weapon}: {weapon_stats['total']} (✓{weapon_stats['confirmed']} ⏳{weapon_stats['pending']})\n"

        update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка в admin_stats: {e}")
        update.message.reply_text("❌ Ошибка при получении статистики")

# ... остальные обработчики команд без изменений ...

# === 7. Flask маршруты ===
@app.route('/')
def home():
    return jsonify({
        "status": "Fencing Registration Bot is running!",
        "version": "1.0", 
        "admin_panel": "/admin",
        "health_check": "/health"
    })

@app.route('/admin')
def admin():
    """Админка для просмотра всех заявок"""
    try:
        registrations = db.get_all_registrations()
        
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Регистрации на соревнования</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                table { width: 100%; border-collapse: collapse; margin-top: 20px; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                .status-pending { color: orange; }
                .status-confirmed { color: green; }
                .status-rejected { color: red; }
            </style>
        </head>
        <body>
            <h1>🤺 Заявки на соревнования по фехтованию</h1>
            <p>Всего заявок: {{ registrations|length }}</p>
            
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Имя</th>
                        <th>Оружие</th>
                        <th>Категория</th>
                        <th>Возраст</th>
                        <th>Телефон</th>
                        <th>Опыт</th>
                        <th>Статус</th>
                        <th>Дата</th>
                    </tr>
                </thead>
                <tbody>
                    {% for reg in registrations %}
                    <tr>
                        <td>{{ reg.id }}</td>
                        <td>{{ reg.full_name }}</td>
                        <td>{{ reg.weapon_type }}</td>
                        <td>{{ reg.category }}</td>
                        <td>{{ reg.age_group }}</td>
                        <td>{{ reg.phone }}</td>
                        <td>{{ reg.experience or 'Не указан' }}</td>
                        <td class="status-{{ reg.status }}">{{ reg.status }}</td>
                        <td>{{ reg.created_at.strftime('%d.%m.%Y %H:%M') }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </body>
        </html>
        """
        return render_template_string(html_template, registrations=registrations)
        
    except Exception as e:
        logger.error(f"Ошибка в админке: {e}")
        return f"Ошибка при загрузке админки: {str(e)}", 500

@app.route('/webhook', methods=['POST'])
def webhook():
    """Вебхук для Telegram"""
    try:
        update = Update.de_json(request.get_json(), bot)
        dispatcher.process_update(update)
        return 'ok'
    except Exception as e:
        logger.error(f"Ошибка в обработке вебхука: {e}")
        return 'error', 500

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Установка вебхука"""
    webhook_url = app.config['WEBHOOK_URL']
    if not webhook_url:
        return "WEBHOOK_URL not configured", 400

    try:
        current = bot.get_webhook_info().url
        if current == webhook_url:
            return f"✅ Webhook уже установлен: {webhook_url}"

        result = bot.set_webhook(webhook_url)
        if result:
            logger.info(f"Webhook установлен: {webhook_url}")
            return f"✅ Webhook успешно установлен на {webhook_url}"
        else:
            return "❌ Ошибка при установке вебхука", 500
    except Exception as e:
        logger.exception("Ошибка при установке вебхука")
        return f"❌ Ошибка: {str(e)}", 500

@app.route('/health')
def health_check():
    """Проверка здоровья приложения"""
    try:
        # Простая проверка базы данных
        db.session.execute('SELECT 1')
        return jsonify({
            "status": "healthy",
            "database": "connected", 
            "bot_initialized": True,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500

# === 8. Запуск ===
if __name__ == '__main__':
    logger.info("Запуск приложения Fencing Registration Bot")
    app.run(host='0.0.0.0', port=5000, debug=False)
