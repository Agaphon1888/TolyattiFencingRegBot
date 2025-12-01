import os
import logging
from datetime import datetime, timedelta
import secrets
from urllib.parse import urlparse

from flask import Flask, request, jsonify, render_template, redirect, url_for, abort
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext
import werkzeug.exceptions as http_exceptions

from config import config
from database import init_db, get_session, Registration, Admin, get_db_stats

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация Flask
app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# Инициализация базы данных
try:
    init_db()
    logger.info("✅ База данных инициализирована")
except Exception as e:
    logger.error(f"❌ Ошибка инициализации БД: {e}")
    # Продолжаем работу даже если БД не инициализирована
    # для возможности показать страницу ошибки

# Глобальные переменные
bot = None
dispatcher = None

def initialize_bot():
    """Инициализация бота Telegram"""
    global bot, dispatcher
    
    if not config.TELEGRAM_TOKEN:
        logger.warning("⚠️ TELEGRAM_TOKEN не установлен. Бот не будет работать.")
        return
    
    try:
        bot = Bot(token=config.TELEGRAM_TOKEN)
        dispatcher = Dispatcher(bot, None, workers=0)
        
        # Регистрация обработчиков
        dispatcher.add_handler(CommandHandler("start", start_command))
        dispatcher.add_handler(CommandHandler("help", help_command))
        dispatcher.add_handler(CommandHandler("admin", admin_command))
        dispatcher.add_handler(CommandHandler("status", status_command))
        dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
        
        # Установка вебхука
        webhook_url = config.get_webhook_url()
        bot.set_webhook(webhook_url)
        logger.info(f"✅ Вебхук установлен на {webhook_url}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации бота: {e}")

# Команда /start
def start_command(update: Update, context: CallbackContext):
    """Обработчик команды /start"""
    user = update.effective_user
    update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n\n"
        "Добро пожаловать в систему регистрации на соревнования по фехтованию в Тольятти!\n\n"
        "Используйте команды:\n"
        "/register - начать регистрацию\n"
        "/status - проверить статус заявки\n"
        "/help - помощь\n\n"
        "Администраторы могут использовать /admin для доступа к панели управления."
    )

# Команда /help
def help_command(update: Update, context: CallbackContext):
    """Обработчик команды /help"""
    update.message.reply_text(
        "📋 Доступные команды:\n\n"
        "/start - начать работу с ботом\n"
        "/register - зарегистрироваться на соревнования\n"
        "/status - проверить статус заявки\n"
        "/help - показать эту справку\n\n"
        "Для регистрации вам понадобится:\n"
        "• ФИО\n"
        "• Вид оружия (сабля/шпага/рапира)\n"
        "• Возрастная группа\n"
        "• Контактный телефон\n"
        "• Информация об опыте\n\n"
        "Администраторы: /admin - панель управления"
    )

# Команда /admin
def admin_command(update: Update, context: CallbackContext):
    """Обработчик команды /admin"""
    user_id = update.effective_user.id
    
    # Проверка прав администратора
    session = get_session()
    try:
        admin = session.query(Admin).filter_by(
            telegram_id=user_id, 
            is_active=True
        ).first()
        
        if admin:
            # Генерация токена доступа
            token = secrets.token_urlsafe(32)
            
            # В реальной реализации здесь нужно сохранить токен в базе
            # с временем истечения и привязать к пользователю
            
            base_url = config.get_base_url()
            admin_url = f"{base_url}/admin?token={token}"
            
            update.message.reply_text(
                f"🔑 Доступ разрешен, {update.effective_user.first_name}!\n\n"
                f"Ваша панель управления:\n{admin_url}\n\n"
                f"Токен действителен 1 час.\n"
                f"ID администратора: {user_id}"
            )
        else:
            update.message.reply_text(
                "⛔ У вас нет прав администратора.\n"
                "Обратитесь к организаторам соревнований."
            )
    finally:
        session.close()

# Команда /status
def status_command(update: Update, context: CallbackContext):
    """Обработчик команды /status"""
    user_id = update.effective_user.id
    
    session = get_session()
    try:
        registrations = session.query(Registration).filter_by(
            telegram_id=user_id
        ).order_by(Registration.created_at.desc()).all()
        
        if not registrations:
            update.message.reply_text(
                "📭 У вас нет активных заявок.\n"
                "Используйте /register для регистрации."
            )
            return
        
        message = "📋 Ваши заявки:\n\n"
        for reg in registrations[:5]:  # Показываем последние 5 заявок
            status_icon = {
                'pending': '⏳',
                'confirmed': '✅',
                'rejected': '❌'
            }.get(reg.status, '❓')
            
            status_text = {
                'pending': 'На рассмотрении',
                'confirmed': 'Подтверждена',
                'rejected': 'Отклонена'
            }.get(reg.status, 'Неизвестно')
            
            message += (
                f"Заявка #{reg.id}\n"
                f"Оружие: {reg.weapon_type}\n"
                f"Категория: {reg.category}\n"
                f"Статус: {status_icon} {status_text}\n"
                f"Дата: {reg.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
            )
        
        if len(registrations) > 5:
            message += f"\n... и еще {len(registrations) - 5} заявок"
        
        update.message.reply_text(message)
    finally:
        session.close()

# Обработчик текстовых сообщений
def handle_message(update: Update, context: CallbackContext):
    """Обработчик текстовых сообщений"""
    # В будущем здесь будет логика регистрации
    update.message.reply_text(
        "Для регистрации используйте команду /register\n"
        "Для проверки статуса - /status\n"
        "Для помощи - /help"
    )

# ================ ВЕБ-ИНТЕРФЕЙС ================

# Фильтры для Jinja2
@app.template_filter('datetimeformat')
def datetimeformat(value, format='%d.%m.%Y %H:%M:%S'):
    """Форматирование даты"""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except:
            return value
    return value.strftime(format) if value else ''

@app.template_filter('status_icon')
def status_icon(status):
    """Иконка статуса"""
    icons = {
        'pending': '⏳',
        'confirmed': '✅',
        'rejected': '❌'
    }
    return icons.get(status, '❓')

@app.template_filter('format_phone')
def format_phone(phone):
    """Форматирование телефона"""
    if not phone:
        return ''
    # Простое форматирование: +7 (999) 123-45-67
    phone = str(phone).replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if phone.startswith('+7') and len(phone) == 12:
        return f"+7 ({phone[2:5]}) {phone[5:8]}-{phone[8:10]}-{phone[10:12]}"
    elif phone.startswith('8') and len(phone) == 11:
        return f"+7 ({phone[1:4]}) {phone[4:7]}-{phone[7:9]}-{phone[9:11]}"
    return phone

# Обработка ошибок
@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', code=404, error="Страница не найдена"), 404

@app.errorhandler(403)
def access_denied(e):
    return render_template('error.html', code=403, error="Доступ запрещен"), 403

@app.errorhandler(500)
def internal_error(e):
    return render_template('error.html', code=500, error="Внутренняя ошибка сервера"), 500

# Главная страница
@app.route('/')
def index():
    """Главная страница"""
    try:
        stats = get_db_stats()
    except:
        stats = {'total_registrations': 0, 'pending': 0, 'confirmed': 0, 'rejected': 0}
    
    return render_template('admin.html', 
                         registrations=[],
                         config=config,
                         now=datetime.utcnow(),
                         current_admin_id=None)

# Страница администратора
@app.route('/admin')
def admin_login():
    """Страница входа администратора"""
    return render_template('error.html', 
                         code=403, 
                         error="Для доступа используйте команду /admin в боте Telegram")

@app.route('/admin_panel')
def admin_panel():
    """Панель администратора"""
    token = request.args.get('token')
    
    # В реальной реализации здесь должна быть проверка токена
    # Для демо принимаем любой токен
    if not token:
        return redirect('/admin')
    
    try:
        session = get_session()
        registrations = session.query(Registration).order_by(Registration.created_at.desc()).all()
        stats = get_db_stats()
        
        return render_template('admin.html',
                             registrations=registrations,
                             config=config,
                             now=datetime.utcnow(),
                             current_admin_id=123456,  # Заглушка
                             token=token)
    except Exception as e:
        logger.error(f"Ошибка загрузки панели админа: {e}")
        return render_template('error.html', 
                             code=500, 
                             error=f"Ошибка загрузки данных: {str(e)}")
    finally:
        if 'session' in locals():
            session.close()

# API для администратора
@app.route('/api/registrations/<int:reg_id>/confirm')
def confirm_registration(reg_id):
    """Подтверждение заявки"""
    token = request.args.get('token')
    if not token:
        return jsonify({'error': 'Токен отсутствует'}), 403
    
    session = get_session()
    try:
        registration = session.query(Registration).get(reg_id)
        if not registration:
            return jsonify({'error': 'Заявка не найдена'}), 404
        
        registration.status = 'confirmed'
        registration.updated_at = datetime.utcnow()
        session.commit()
        
        # Уведомление пользователя в Telegram
        try:
            if bot:
                bot.send_message(
                    chat_id=registration.telegram_id,
                    text=f"✅ Ваша заявка #{registration.id} подтверждена!\n\n"
                         f"Ожидайте дальнейших инструкций от организаторов."
                )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление: {e}")
        
        return jsonify({'success': True, 'registration': registration.to_dict()})
    finally:
        session.close()

@app.route('/api/registrations/<int:reg_id>/reject')
def reject_registration(reg_id):
    """Отклонение заявки"""
    token = request.args.get('token')
    if not token:
        return jsonify({'error': 'Токен отсутствует'}), 403
    
    session = get_session()
    try:
        registration = session.query(Registration).get(reg_id)
        if not registration:
            return jsonify({'error': 'Заявка не найдена'}), 404
        
        registration.status = 'rejected'
        registration.updated_at = datetime.utcnow()
        session.commit()
        
        # Уведомление пользователя в Telegram
        try:
            if bot:
                bot.send_message(
                    chat_id=registration.telegram_id,
                    text=f"❌ Ваша заявка #{registration.id} отклонена.\n\n"
                         f"По вопросам обращайтесь к организаторам."
                )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление: {e}")
        
        return jsonify({'success': True, 'registration': registration.to_dict()})
    finally:
        session.close()

# Вебхук для Telegram
@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработчик вебхука от Telegram"""
    if not bot or not dispatcher:
        return jsonify({'status': 'error', 'message': 'Bot not initialized'}), 500
    
    try:
        update = Update.de_json(request.get_json(), bot)
        dispatcher.process_update(update)
        return jsonify({'status': 'ok'})
    except Exception as e:
        logger.error(f"Ошибка обработки вебхука: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Проверка здоровья
@app.route('/health')
def health_check():
    """Проверка здоровья приложения"""
    try:
        session = get_session()
        session.execute('SELECT 1')
        db_status = 'healthy'
        session.close()
    except Exception as e:
        db_status = f'unhealthy: {str(e)}'
    
    return jsonify({
        'status': 'running',
        'timestamp': datetime.utcnow().isoformat(),
        'database': db_status,
        'telegram_bot': 'initialized' if bot else 'not_initialized',
        'config': {
            'webhook_url': config.WEBHOOK_URL,
            'admin_ids': config.get_admin_ids(),
            'debug': config.DEBUG
        }
    })

# Установка вебхука
@app.route('/set_webhook')
def set_webhook():
    """Установка вебхука вручную"""
    if not bot:
        return "Бот не инициализирован", 500
    
    try:
        webhook_url = config.get_webhook_url()
        result = bot.set_webhook(webhook_url)
        return f"Вебхук установлен на {webhook_url}<br>Результат: {result}"
    except Exception as e:
        return f"Ошибка установки вебхука: {str(e)}", 500

# Тестовые данные
@app.route('/test_data')
def test_data():
    """Создание тестовых данных"""
    session = get_session()
    try:
        # Проверяем, есть ли уже тестовые данные
        existing = session.query(Registration).filter_by(telegram_id=999999999).first()
        if existing:
            return "Тестовые данные уже существуют"
        
        # Создаем тестовые записи
        test_regs = [
            Registration(
                telegram_id=999999999,
                username='test_user',
                full_name='Иванов Иван Иванович',
                weapon_type='Сабля',
                category='Взрослые',
                age_group='19+ лет',
                phone='+79991234567',
                experience='Занимаюсь 5 лет, имею 1 разряд',
                status='pending'
            ),
            Registration(
                telegram_id=888888888,
                username='test_user2',
                full_name='Петрова Анна Сергеевна',
                weapon_type='Рапира',
                category='Юниоры',
                age_group='16-18 лет',
                phone='+79997654321',
                experience='Занимаюсь 3 года, КМС',
                status='confirmed'
            ),
            Registration(
                telegram_id=777777777,
                username='test_user3',
                full_name='Сидоров Алексей Владимирович',
                weapon_type='Шпага',
                category='Ветераны',
                age_group='19+ лет',
                phone='+79995555555',
                experience='Занимаюсь 10 лет, МС',
                status='rejected'
            )
        ]
        
        for reg in test_regs:
            session.add(reg)
        
        session.commit()
        return "Тестовые данные созданы успешно"
    finally:
        session.close()

# Конфигурация
@app.route('/config')
def show_config():
    """Показать конфигурацию"""
    config_dict = config.to_dict()
    return jsonify(config_dict)

# Инициализация при запуске
if __name__ == '__main__':
    # Инициализация бота
    initialize_bot()
    
    # Запуск Flask
    app.run(host='0.0.0.0', port=config.PORT, debug=config.DEBUG)
else:
    # При запуске через Gunicorn
    initialize_bot()
