from flask import Flask, request, jsonify, render_template, render_template_string
from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
import logging
import os
import json
from datetime import datetime, timedelta
from functools import wraps
import threading
import time

from config import config
from database import init_db, get_session, Registration, Admin, session_scope

# ===== Инициализация приложения =====
app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# Автоматически определяем папку с шаблонами
app.template_folder = 'templates'  # Явно указываем папку templates
print(f"✅ Шаблоны из папки: {app.template_folder}")

# Инициализация БД
try:
    init_db()
    print("✅ База данных инициализирована")
except Exception as e:
    print(f"❌ Ошибка инициализации БД: {e}")

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, config.LOG_LEVEL)
)
logger = logging.getLogger(__name__)

# ===== Глобальные переменные для бота =====
bot_instance = None
dp_instance = None

def get_bot():
    global bot_instance
    if bot_instance is None:
        try:
            bot_instance = Bot(token=config.TELEGRAM_TOKEN)
            logger.info(f"✅ Бот инициализирован: {bot_instance.get_me().first_name}")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации бота: {e}")
    return bot_instance

# ===== Вспомогательные функции для шаблонов =====
@app.template_filter('datetimeformat')
def datetimeformat(value, format='%d.%m.%Y %H:%M'):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except:
            return value
    return value.strftime(format) if value else ''

@app.template_filter('format_phone')
def format_phone(value):
    if not value:
        return ''
    # Форматирование телефона: +7 (999) 123-45-67
    phone = ''.join(filter(str.isdigit, value))
    if len(phone) == 11 and phone.startswith('7'):
        phone = phone[1:]
    if len(phone) == 10:
        return f"+7 ({phone[:3]}) {phone[3:6]}-{phone[6:8]}-{phone[8:]}"
    return value

@app.template_filter('status_icon')
def status_icon(value):
    icons = {
        'pending': '⏳',
        'confirmed': '✅',
        'rejected': '❌'
    }
    return icons.get(value, '❓')

@app.template_filter('tojson')
def tojson(value):
    return json.dumps(value, ensure_ascii=False, default=str)

# ===== Состояния регистрации =====
NAME, WEAPON, CATEGORY, AGE, PHONE, EXPERIENCE, CONFIRM = range(7)

# ===== Декораторы для проверки прав =====
def admin_required(func):
    @wraps(func)
    def wrapper(update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        with session_scope() as session:
            admin = session.query(Admin).filter_by(telegram_id=user_id, is_active=True).first()
            if not admin:
                update.message.reply_text("❌ У вас нет прав администратора.")
                return
        return func(update, context)
    return wrapper

def super_admin_required(func):
    @wraps(func)
    def wrapper(update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        if user_id not in config.get_admin_ids():
            update.message.reply_text("❌ Только супер-админы могут использовать эту команду.")
            return
        return func(update, context)
    return wrapper

# ===== Команды Telegram бота =====
def start(update: Update, context: CallbackContext) -> int:
    user = update.message.from_user
    context.user_data.clear()
    context.user_data.update({
        'telegram_id': user.id,
        'username': user.username or f"user_{user.id}"
    })
    
    welcome_text = """
🤺 *Добро пожаловать в систему регистрации на соревнования по фехтованию в Тольятти!*

Для регистрации вам потребуется:
1. Ваше ФИО
2. Выбор оружия
3. Категория и возрастная группа
4. Контактный телефон
5. Информация об опыте

*Давайте начнем!*

Введите ваше ФИО (полностью):
    """
    update.message.reply_text(welcome_text, parse_mode='Markdown')
    return NAME

def get_name(update: Update, context: CallbackContext) -> int:
    full_name = update.message.text.strip()
    if len(full_name) < 5:
        update.message.reply_text("❌ Пожалуйста, введите полное ФИО (например: Иванов Иван Иванович)")
        return NAME
    
    context.user_data['full_name'] = full_name
    kb = [[w] for w in config.WEAPON_TYPES]
    rm = ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
    update.message.reply_text("Выберите вид оружия:", reply_markup=rm)
    return WEAPON

def get_weapon(update: Update, context: CallbackContext) -> int:
    w = update.message.text
    if w not in config.WEAPON_TYPES:
        update.message.reply_text("❌ Пожалуйста, выберите один из предложенных вариантов.")
        return WEAPON
    context.user_data['weapon_type'] = w
    kb = [[c] for c in config.CATEGORIES]
    rm = ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
    update.message.reply_text("Выберите категорию:", reply_markup=rm)
    return CATEGORY

def get_category(update: Update, context: CallbackContext) -> int:
    c = update.message.text
    if c not in config.CATEGORIES:
        update.message.reply_text("❌ Пожалуйста, выберите один из предложенных вариантов.")
        return CATEGORY
    context.user_data['category'] = c
    kb = [[a] for a in config.AGE_GROUPS]
    rm = ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
    update.message.reply_text("Выберите возрастную группу:", reply_markup=rm)
    return AGE

def get_age(update: Update, context: CallbackContext) -> int:
    a = update.message.text
    if a not in config.AGE_GROUPS:
        update.message.reply_text("❌ Пожалуйста, выберите один из предложенных вариантов.")
        return AGE
    context.user_data['age_group'] = a
    
    kb = [[KeyboardButton("📞 Отправить мой номер", request_contact=True)]]
    rm = ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
    update.message.reply_text(
        "Телефон для связи:\n\n"
        "Нажмите кнопку ниже, чтобы отправить ваш номер, или введите номер вручную в формате:\n"
        "+79991234567 или 89991234567",
        reply_markup=rm
    )
    return PHONE

def get_phone(update: Update, context: CallbackContext) -> int:
    phone = None
    
    if update.message.contact:
        phone = update.message.contact.phone_number
    elif update.message.text:
        phone = update.message.text.strip()
    else:
        update.message.reply_text("❌ Пожалуйста, отправьте контакт или введите номер вручную.")
        return PHONE
    
    # Нормализуем номер
    if phone:
        phone_digits = ''.join(filter(str.isdigit, phone))
        
        if phone_digits.startswith('8') and len(phone_digits) == 11:
            phone_digits = '7' + phone_digits[1:]
        elif len(phone_digits) == 10:
            phone_digits = '7' + phone_digits
        
        if not phone_digits.startswith('7') or len(phone_digits) != 11:
            update.message.reply_text("❌ Неверный формат номера. Пожалуйста, введите номер в формате +79991234567")
            return PHONE
        
        context.user_data['phone'] = f'+{phone_digits}'
    
    update.message.reply_text(
        "Опишите ваш опыт:\n\n"
        "• Разряд/звание (если есть)\n"
        "• Стаж занятий\n"
        "• Участие в соревнованиях\n"
        "• Дополнительная информация"
    )
    return EXPERIENCE

def get_experience(update: Update, context: CallbackContext) -> int:
    experience = update.message.text.strip()
    if len(experience) < 10:
        update.message.reply_text("❌ Пожалуйста, опишите ваш опыт более подробно (минимум 10 символов)")
        return EXPERIENCE
    
    context.user_data['experience'] = experience
    data = context.user_data
    
    msg = f"""
📋 *Проверьте ваши данные:*

*ФИО:* {data['full_name']}
*Оружие:* {data['weapon_type']}
*Категория:* {data['category']}
*Возрастная группа:* {data['age_group']}
*Телефон:* {data['phone']}
*Опыт:* {data['experience'][:100]}{'...' if len(data['experience']) > 100 else ''}

Всё правильно?
    """
    
    kb = [['✅ Да, всё верно', '❌ Нет, исправить']]
    rm = ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
    update.message.reply_text(msg, parse_mode='Markdown', reply_markup=rm)
    return CONFIRM

def confirm_registration(update: Update, context: CallbackContext) -> int:
    if update.message.text == '❌ Нет, исправить':
        update.message.reply_text("Начнем заново. Введите ваше ФИО:", reply_markup=None)
        return NAME

    data = context.user_data
    with session_scope() as session:
        # ВРЕМЕННО ЗАКОММЕНТИРОВАНО - из-за проблем с created_at
        # existing = session.query(Registration).filter_by(
        #     telegram_id=data['telegram_id'],
        #     status='pending'
        # ).first()
        
        # if existing:
        #     update.message.reply_text(
        #         "⚠️ У вас уже есть активная заявка на рассмотрении.\n"
        #         "Используйте /myregistrations для просмотра статуса.",
        #         reply_markup=None
        #     )
        #     return ConversationHandler.END
            
        reg = Registration(
            telegram_id=data['telegram_id'],
            username=data.get('username'),
            full_name=data['full_name'],
            weapon_type=data['weapon_type'],
            category=data['category'],
            age_group=data['age_group'],
            phone=data['phone'],
            experience=data['experience'],
            status='pending'
        )
        session.add(reg)
        session.commit()  # Явный коммит для получения ID
    
    # Уведомляем администраторов
    admin_ids = config.get_admin_ids()
    bot = get_bot()
    if admin_ids and bot:
        notification = f"""
📥 *Новая заявка на регистрацию*

*ФИО:* {data['full_name']}
*Оружие:* {data['weapon_type']}
*Телефон:* {data['phone']}

Для просмотра: /admin_stats
        """
        for admin_id in admin_ids:
            try:
                bot.send_message(admin_id, notification, parse_mode='Markdown')
            except Exception as e:
                logger.error(f"Не удалось уведомить админа {admin_id}: {e}")
    
    update.message.reply_text(
        "✅ *Заявка успешно отправлена!*\n\n"
        "Ваша заявка принята и ожидает подтверждения администратором.\n"
        "Мы свяжемся с вами в ближайшее время.\n\n"
        "Для просмотра статуса заявки используйте команду /myregistrations",
        parse_mode='Markdown',
        reply_markup=None
    )
    
    context.user_data.clear()
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(
        "Регистрация отменена.\n"
        "Если хотите начать заново, используйте /start",
        reply_markup=None
    )
    context.user_data.clear()
    return ConversationHandler.END

def view_registrations(update: Update, context: CallbackContext):
    with session_scope() as session:
        regs = session.query(Registration).filter_by(
            telegram_id=update.message.from_user.id
        ).order_by(Registration.created_at.desc()).all()
        
        if not regs:
            update.message.reply_text("📭 У вас пока нет заявок.\nИспользуйте /start для регистрации.")
            return
        
        msg = "📋 *Ваши заявки:*\n\n"
        for r in regs:
            status_ru = {
                'pending': '⏳ Ожидает рассмотрения',
                'confirmed': '✅ Подтверждена',
                'rejected': '❌ Отклонена'
            }.get(r.status, '❓ Неизвестно')
            
            msg += f"*Заявка #{r.id}*\n"
            msg += f"ФИО: {r.full_name}\n"
            msg += f"Оружие: {r.weapon_type}\n"
            msg += f"Категория: {r.category}\n"
            msg += f"Статус: {status_ru}\n"
            msg += f"Дата: {r.created_at.strftime('%d.%m.%Y %H:%M') if r.created_at else 'Не указана'}\n"
            msg += "─" * 20 + "\n\n"
        
        update.message.reply_text(msg, parse_mode='Markdown')

def help_command(update: Update, context: CallbackContext):
    help_text = """
🤖 *Доступные команды:*

/start - Начать регистрацию на соревнования
/myregistrations - Просмотреть мои заявки
/cancel - Отменить текущую регистрацию
/help - Показать справку

*Для администраторов:*
/admin_stats - Статистика заявок
/admin_list - Список администраторов
/admin_add <id> [роль] - Добавить администратора

📞 *По вопросам:*
Обратитесь к организаторам соревнований.
    """
    update.message.reply_text(help_text, parse_mode='Markdown')

@admin_required
def admin_stats(update: Update, context: CallbackContext):
    with session_scope() as session:
        regs = session.query(Registration).all()
        total = len(regs)
        pending = len([r for r in regs if r.status == 'pending'])
        confirmed = len([r for r in regs if r.status == 'confirmed'])
        rejected = len([r for r in regs if r.status == 'rejected'])

        stats = f"""
📊 *Статистика:*

• Всего заявок: {total}
• Ожидают: {pending}
• Подтверждены: {confirmed}
• Отклонены: {rejected}
        """
        update.message.reply_text(stats, parse_mode='Markdown')

@super_admin_required
def admin_add(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Использование: /admin_add <telegram_id> [роль]")
        return
    try:
        tid = int(context.args[0])
        role = context.args[1] if len(context.args) > 1 else 'moderator'
        if role not in ['admin', 'moderator']:
            update.message.reply_text("Роль: 'admin' или 'moderator'")
            return

        with session_scope() as session:
            if session.query(Admin).filter_by(telegram_id=tid).first():
                update.message.reply_text("⚠️ Уже является админом.")
                return

            new_admin = Admin(
                telegram_id=tid, 
                role=role, 
                created_by=update.message.from_user.id
            )
            session.add(new_admin)
        update.message.reply_text(f"✅ Админ {tid} добавлен как {role}")
    except ValueError:
        update.message.reply_text("❌ Неверный ID")

@admin_required
def admin_list(update: Update, context: CallbackContext):
    with session_scope() as session:
        admins = session.query(Admin).all()
        msg = "👥 *Администраторы:*\n"
        for a in admins:
            status = "🟢" if a.is_active else "🔴"
            msg += f"{status} {a.telegram_id} ({a.role})\n"
        update.message.reply_text(msg, parse_mode='Markdown')

# ===== Настройка диспетчера Telegram =====
def setup_dispatcher():
    """Настройка диспетчера Telegram"""
    bot = get_bot()
    if not bot:
        logger.error("❌ Не удалось инициализировать бота для диспетчера")
        return None
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(Filters.text & ~Filters.command, get_name)],
            WEAPON: [MessageHandler(Filters.text & ~Filters.command, get_weapon)],
            CATEGORY: [MessageHandler(Filters.text & ~Filters.command, get_category)],
            AGE: [MessageHandler(Filters.text & ~Filters.command, get_age)],
            PHONE: [MessageHandler(Filters.text | Filters.contact, get_phone)],
            EXPERIENCE: [MessageHandler(Filters.text & ~Filters.command, get_experience)],
            CONFIRM: [MessageHandler(Filters.text & ~Filters.command, confirm_registration)],
        },
        fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
        allow_reentry=True
    )

    dp = Dispatcher(bot, None, workers=1, use_context=True)
    dp.add_handler(conv_handler)
    dp.add_handler(CommandHandler('help', help_command))
    dp.add_handler(CommandHandler('myregistrations', view_registrations))
    dp.add_handler(CommandHandler('admin_stats', admin_stats))
    dp.add_handler(CommandHandler('admin_add', admin_add))
    dp.add_handler(CommandHandler('admin_list', admin_list))
    
    return dp

# Инициализируем диспетчер
dp_instance = setup_dispatcher()

# ===== Веб-маршруты Flask =====
@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "service": "Tolyatti Fencing Registration Bot",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "admin": "/admin",
            "admin_panel": "/admin_panel?token=b1e807aeb2b1425995b17e1694296448",
            "health": "/health",
            "webhook": "/webhook (POST)",
            "api": "/api/registrations?token=b1e807aeb2b1425995b17e1694296448"
        }
    })

@app.route('/admin')
def admin_page():
    """Простая админ-страница с возможностью ввода токена"""
    simple_mode = request.args.get('simple')
    token = request.args.get('token')
    
    try:
        with session_scope() as session:
            total = session.query(Registration).count()
            pending = session.query(Registration).filter_by(status='pending').count()
            
            # Если запрошена простая версия, показываем только данные без API
            if simple_mode:
                regs = session.query(Registration).order_by(Registration.created_at.desc()).limit(50).all()
                return render_template_string("""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>Админ-панель (простая версия)</title>
                    <style>
                        body { font-family: Arial, sans-serif; margin: 40px; }
                        h1 { color: #333; }
                        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
                        th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
                        th { background-color: #4CAF50; color: white; }
                        tr:nth-child(even) { background-color: #f2f2f2; }
                        .badge { padding: 4px 8px; border-radius: 4px; font-size: 12px; }
                        .pending { background: #ffc107; color: #000; }
                        .confirmed { background: #28a745; color: white; }
                        .rejected { background: #dc3545; color: white; }
                        a { color: #007bff; text-decoration: none; }
                        a:hover { text-decoration: underline; }
                    </style>
                </head>
                <body>
                    <h1>🤺 Админ-панель Tolyatti Fencing (простая версия)</h1>
                    
                    <div style="background: #f5f5f5; padding: 20px; border-radius: 10px; margin: 20px 0;">
                        <h3>📊 Статистика</h3>
                        <p><strong>Всего заявок:</strong> {{ total }}</p>
                        <p><strong>Ожидают рассмотрения:</strong> {{ pending }}</p>
                        <p><a href="/admin">Вернуться к полной версии</a> | <a href="/">На главную</a></p>
                    </div>
                    
                    <h3>Последние 50 заявок</h3>
                    {% if regs %}
                    <table>
                        <tr>
                            <th>ID</th><th>ФИО</th><th>Оружие</th><th>Телефон</th><th>Статус</th><th>Дата</th>
                        </tr>
                        {% for r in regs %}
                        <tr>
                            <td>{{ r.id }}</td>
                            <td>{{ r.full_name }}</td>
                            <td>{{ r.weapon_type }}</td>
                            <td>{{ r.phone }}</td>
                            <td>
                                <span class="badge {{ r.status }}">
                                    {% if r.status == 'pending' %}⏳ Ожидает
                                    {% elif r.status == 'confirmed' %}✅ Подтверждена
                                    {% else %}❌ Отклонена{% endif %}
                                </span>
                            </td>
                            <td>{{ r.created_at.strftime('%d.%m.%Y %H:%M') if r.created_at else 'Не указана' }}</td>
                        </tr>
                        {% endfor %}
                    </table>
                    {% else %}
                    <p>Нет заявок</p>
                    {% endif %}
                </body>
                </html>
                """, regs=regs, total=total, pending=pending)
            
            # Полная версия с возможностью ввода токена
            return render_template(
                'admin.html',
                total=total,
                pending=pending,
                token=token  # передаем токен из URL если есть
            )
    except Exception as e:
        logger.error(f"Ошибка в админке: {e}")
        return render_template('error.html', 
                             code=500, 
                             error=f"Внутренняя ошибка сервера: {str(e)}"), 500

@app.route('/admin_panel')
def admin_panel():
    """Полная админ-панель с токеном"""
    token = request.args.get('token')
    
    if not token or token != config.SECRET_KEY:
        return render_template('error.html', 
                             code=403, 
                             error="Неверный токен доступа. Используйте: /admin_panel?token=ваш_секретный_ключ"), 403
    
    try:
        with session_scope() as session:
            regs = session.query(Registration).order_by(Registration.created_at.desc()).all()
            
            regs_data = []
            for r in regs:
                regs_data.append({
                    'id': r.id,
                    'telegram_id': r.telegram_id,
                    'username': r.username,
                    'full_name': r.full_name,
                    'weapon_type': r.weapon_type,
                    'category': r.category,
                    'age_group': r.age_group,
                    'phone': r.phone,
                    'experience': r.experience,
                    'status': r.status,
                    'created_at': r.created_at.isoformat() if r.created_at else None,
                    'updated_at': r.updated_at.isoformat() if r.updated_at else None
                })
            
            admin_ids = config.get_admin_ids()
            current_admin_id = admin_ids[0] if admin_ids else 0
            
            return render_template(
                'admin.html',
                registrations=regs,
                registrations_json=regs_data,
                config=config,
                token=token,
                current_admin_id=current_admin_id,
                now=datetime.utcnow()
            )
    except Exception as e:
        logger.error(f"Ошибка в админ-панели: {e}")
        return render_template('error.html', 
                             code=500, 
                             error=f"Внутренняя ошибка сервера: {str(e)}"), 500

@app.route('/api/registrations')
def get_registrations_api():
    """API для получения заявок"""
    token = request.args.get('token')
    if not token or token != config.SECRET_KEY:
        return jsonify({'error': 'Invalid token'}), 403
    
    try:
        status = request.args.get('status')
        with session_scope() as session:
            query = session.query(Registration)
            if status:
                query = query.filter_by(status=status)
            regs = query.order_by(Registration.created_at.desc()).all()
            
            result = []
            for r in regs:
                result.append({
                    'id': r.id,
                    'full_name': r.full_name,
                    'weapon_type': r.weapon_type,
                    'category': r.category,
                    'age_group': r.age_group,
                    'phone': r.phone,
                    'experience': r.experience,
                    'status': r.status,
                    'created_at': r.created_at.isoformat() if r.created_at else None
                })
            
            return jsonify({'registrations': result, 'count': len(result)})
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/registrations/<int:reg_id>/confirm')
def confirm_registration_api(reg_id):
    """API для подтверждения заявки"""
    token = request.args.get('token')
    if not token or token != config.SECRET_KEY:
        return jsonify({'error': 'Invalid token'}), 403
    
    try:
        with session_scope() as session:
            reg = session.query(Registration).get(reg_id)
            if not reg:
                return jsonify({'error': 'Registration not found'}), 404
            
            reg.status = 'confirmed'
            reg.updated_at = datetime.utcnow()
            session.add(reg)
            
            bot = get_bot()
            if bot:
                try:
                    bot.send_message(
                        reg.telegram_id,
                        f"✅ *Ваша заявка #{reg.id} подтверждена!*\n\n"
                        f"Рады сообщить, что ваша заявка на участие в соревнованиях по фехтованию подтверждена.\n"
                        f"Ждем вас на соревнованиях!\n\n"
                        f"*Детали заявки:*\n"
                        f"ФИО: {reg.full_name}\n"
                        f"Оружие: {reg.weapon_type}\n"
                        f"Категория: {reg.category}",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Не удалось отправить уведомление пользователю {reg.telegram_id}: {e}")
        
        return jsonify({'success': True, 'status': 'confirmed'})
    except Exception as e:
        logger.error(f"Confirm API error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/registrations/<int:reg_id>/reject')
def reject_registration_api(reg_id):
    """API для отклонения заявки"""
    token = request.args.get('token')
    if not token or token != config.SECRET_KEY:
        return jsonify({'error': 'Invalid token'}), 403
    
    try:
        with session_scope() as session:
            reg = session.query(Registration).get(reg_id)
            if not reg:
                return jsonify({'error': 'Registration not found'}), 404
            
            reg.status = 'rejected'
            reg.updated_at = datetime.utcnow()
            session.add(reg)
            
            bot = get_bot()
            if bot:
                try:
                    bot.send_message(
                        reg.telegram_id,
                        f"❌ *Ваша заявка #{reg.id} отклонена*\n\n"
                        f"К сожалению, ваша заявка на участие в соревнованиях была отклонена.\n"
                        f"По вопросам обращайтесь к организаторам.",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Не удалось отправить уведомление пользователю {reg.telegram_id}: {e}")
        
        return jsonify({'success': True, 'status': 'rejected'})
    except Exception as e:
        logger.error(f"Reject API error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    """Endpoint для вебхука Telegram"""
    if request.method == "POST":
        try:
            update = Update.de_json(request.get_json(force=True), get_bot())
            if dp_instance:
                dp_instance.process_update(update)
            else:
                logger.error("❌ Диспетчер не инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка обработки webhook: {e}")
    return 'ok'

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Установка вебхука"""
    try:
        webhook_url = config.get_webhook_url()
        bot = get_bot()
        
        if not bot:
            return "❌ Бот не инициализирован", 500
        
        success = bot.set_webhook(webhook_url)
        
        if success:
            bot_info = bot.get_me()
            return f"""
            <h1>✅ Webhook установлен успешно!</h1>
            <p><strong>URL:</strong> {webhook_url}</p>
            <p><strong>Бот:</strong> {bot_info.first_name if bot_info else 'Unknown'}</p>
            <p><a href="/">На главную</a> | <a href="/admin">В админку</a></p>
            <p><a href="/health">Проверить состояние</a></p>
            """
        else:
            return "❌ Не удалось установить webhook", 500
    except Exception as e:
        return f"❌ Ошибка установки webhook: {str(e)}", 500

@app.route('/health')
def health():
    """Проверка состояния сервиса"""
    try:
        with session_scope() as session:
            session.execute('SELECT 1')
            db_status = 'connected'
    except Exception as e:
        db_status = f'disconnected: {str(e)}'
    
    bot_status = 'initialized' if get_bot() else 'failed'
    
    return jsonify({
        'status': 'healthy',
        'service': 'Tolyatti Fencing Bot',
        'database': db_status,
        'bot': bot_status,
        'webhook_set': bool(get_bot() and get_bot().get_webhook_info().url if get_bot() else False),
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0',
        'endpoints': {
            'admin': '/admin',
            'health': '/health',
            'set_webhook': '/set_webhook'
        }
    })

@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', 
                         code=404, 
                         error="Страница не найдена. Проверьте URL и попробуйте снова."), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return render_template('error.html', 
                         code=500, 
                         error="Внутренняя ошибка сервера. Мы уже работаем над исправлением."), 500

@app.errorhandler(403)
def forbidden_error(error):
    return render_template('error.html', 
                         code=403, 
                         error="Доступ запрещен. У вас нет прав для просмотра этой страницы."), 403

# ===== Функция для установки webhook при старте =====
def setup_webhook_on_start():
    """Установка вебхука при запуске приложения"""
    def delayed_webhook_setup():
        time.sleep(10)  # Ждем 10 секунд чтобы сервер запустился
        try:
            bot = get_bot()
            if bot:
                webhook_url = config.get_webhook_url()
                bot.set_webhook(webhook_url)
                logger.info(f"✅ Webhook установлен: {webhook_url}")
        except Exception as e:
            logger.error(f"❌ Ошибка установки webhook при старте: {e}")
    
    thread = threading.Thread(target=delayed_webhook_setup, daemon=True)
    thread.start()

# Устанавливаем webhook при импорте модуля
setup_webhook_on_start()

# ===== Запуск приложения =====
if __name__ == '__main__':
    port = int(os.environ.get('PORT', config.PORT))
    app.run(host='0.0.0.0', port=port, debug=config.DEBUG)
