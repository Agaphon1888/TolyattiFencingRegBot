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
# from sqlalchemy import ForeignKey
# from sqlalchemy.orm import relationship

from config import config
from database import init_db, get_session, Registration, Admin, Event, session_scope

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
NAME, WEAPON, CATEGORY, AGE, PHONE, EVENT, EXPERIENCE, CONFIRM = range(8)

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
def send_example(update: Update, context: CallbackContext):
    """Отправляет пример заполнения заявки"""
    example_text = """
📋 *Пример заполнения заявки:*

*ФИО:* Иванов Иван Иванович
*Оружие:* Сабля
*Категория:* Взрослые
*Возрастная группа:* 19+ лет
*Телефон:* +79991234567
*Опыт и достижения:*
- КМС по фехтованию
- 5 лет стажа
- Участник чемпионата области 2023
- Победитель городского турнира 2022

*Важно:*
• Указывайте полное ФИО
• Телефон должен быть действительным
• Подробно опишите опыт и достижения
• Выберите актуальное соревнование
"""
    update.message.reply_text(example_text, parse_mode='Markdown')

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
5. Информация об опыте и достижениях
6. Выбор соревнования

📋 *Пример заполнения:*
ФИО: Иванов Иван Иванович
Телефон: +79991234567
Опыт: КМС, 5 лет стажа, участник чемпионата области

*Для просмотра подробного примера используйте команду /example*

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
    
    # Переходим к выбору события
    return get_event(update, context)

def get_event(update: Update, context: CallbackContext) -> int:
    """Выбор события/соревнования"""
    with session_scope() as session:
        # Получаем активные события (будущие)
        events = session.query(Event).filter(
            Event.is_active == True,
            Event.event_date >= datetime.now().date()
        ).order_by(Event.event_date).all()
        
        if not events:
            update.message.reply_text(
                "❌ В данный момент нет доступных соревнований для регистрации.\n"
                "Попробуйте позже или обратитесь к организаторам."
            )
            return ConversationHandler.END
        
        # Создаем клавиатуру с событиями
        kb = [[f"{e.name} ({e.event_date.strftime('%d.%m.%Y')})"] for e in events]
        rm = ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
        
        event_list = "\n".join([f"{i+1}. {e.name} - {e.event_date.strftime('%d.%m.%Y')}" 
                               for i, e in enumerate(events)])
        
        update.message.reply_text(
            f"📅 *Выберите соревнование:*\n\n{event_list}\n\n"
            "Нажмите на нужное соревнование в клавиатуре ниже:",
            parse_mode='Markdown',
            reply_markup=rm
        )
        return EVENT

def select_event(update: Update, context: CallbackContext) -> int:
    """Обработка выбора события"""
    event_choice = update.message.text
    
    with session_scope() as session:
        # Пытаемся найти событие по названию и дате
        events = session.query(Event).filter(
            Event.is_active == True,
            Event.event_date >= datetime.now().date()
        ).all()
        
        selected_event = None
        for event in events:
            event_str = f"{event.name} ({event.event_date.strftime('%d.%m.%Y')})"
            if event_choice == event_str:
                selected_event = event
                break
        
        if not selected_event:
            update.message.reply_text(
                "❌ Пожалуйста, выберите соревнование из списка ниже.",
                reply_markup=None
            )
            return get_event(update, context)
        
        context.user_data['event_id'] = selected_event.id
        context.user_data['event_name'] = selected_event.name
    
    update.message.reply_text(
        "Опишите ваш опыт, достижения, разряды и стаж занятий:\n\n"
        "• Разряд/звание (если есть)\n"
        "• Стаж занятий (сколько лет)\n"
        "• Участие в соревнованиях\n"
        "• Достижения и награды\n"
        "• Дополнительная информация\n\n"
        "*Пример:* КМС по фехтованию, 5 лет стажа, участник чемпионата области 2023, победитель городского турнира 2022",
        parse_mode='Markdown'
    )
    return EXPERIENCE

def get_experience(update: Update, context: CallbackContext) -> int:
    """Получение информации об опыте"""
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
*Соревнование:* {data.get('event_name', 'Не указано')}
*Опыт:* {data['experience'][:100]}{'...' if len(data['experience']) > 100 else ''}

Всё правильно?
    """
    
    kb = [['✅ Да, всё верно', '❌ Нет, исправить']]
    rm = ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
    update.message.reply_text(msg, parse_mode='Markdown', reply_markup=rm)
    return CONFIRM

def confirm_registration(update: Update, context: CallbackContext) -> int:
    """Подтверждение регистрации"""
    if update.message.text == '❌ Нет, исправить':
        update.message.reply_text("Начнем заново. Введите ваше ФИО:", reply_markup=None)
        return NAME

    data = context.user_data
    
    with session_scope() as session:
        reg = Registration(
            telegram_id=data['telegram_id'],
            username=data.get('username'),
            full_name=data['full_name'],
            weapon_type=data['weapon_type'],
            category=data['category'],
            age_group=data['age_group'],
            phone=data['phone'],
            experience=data['experience'],
            status='pending',
            event_id=data.get('event_id')
        )
        session.add(reg)
        session.commit()  # Явный коммит для получения ID
    
    # Уведомляем администраторов - ПРОСТОЙ ТЕКСТ БЕЗ РАЗМЕТКИ
    admin_ids = config.get_admin_ids()
    bot = get_bot()
    if admin_ids and bot:
        # Простой текст без Markdown
        notification = f"""📥 Новая заявка на регистрацию

ФИО: {data['full_name']}
Оружие: {data['weapon_type']}
Телефон: {data['phone']}
Соревнование: {data.get('event_name', 'Не указано')}

Для просмотра заявок используйте команду /admin_stats"""
        
        for admin_id in admin_ids:
            try:
                bot.send_message(admin_id, notification)  # Без parse_mode вообще
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
    """Отмена регистрации"""
    update.message.reply_text(
        "Регистрация отменена.\n"
        "Если хотите начать заново, используйте /start",
        reply_markup=None
    )
    context.user_data.clear()
    return ConversationHandler.END

def view_registrations(update: Update, context: CallbackContext):
    """Просмотр заявок пользователя"""
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
            
            event_name = r.event.name if r.event else "Не указано"
            
            msg += f"*Заявка #{r.id}*\n"
            msg += f"ФИО: {r.full_name}\n"
            msg += f"Оружие: {r.weapon_type}\n"
            msg += f"Категория: {r.category}\n"
            msg += f"Соревнование: {event_name}\n"
            msg += f"Статус: {status_ru}\n"
            msg += f"Дата: {r.created_at.strftime('%d.%m.%Y %H:%M') if r.created_at else 'Не указана'}\n"
            msg += "─" * 20 + "\n\n"
        
        update.message.reply_text(msg, parse_mode='Markdown')

def help_command(update: Update, context: CallbackContext):
    """Справка по командам"""
    help_text = """
🤖 *Доступные команды:*

/start - Начать регистрацию на соревнования
/example - Пример заполнения заявки
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
    """Статистика для администраторов"""
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
    """Добавление администратора"""
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
    """Список администраторов"""
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
            EVENT: [MessageHandler(Filters.text & ~Filters.command, select_event)],
            EXPERIENCE: [MessageHandler(Filters.text & ~Filters.command, get_experience)],
            CONFIRM: [MessageHandler(Filters.text & ~Filters.command, confirm_registration)],
        },
        fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
        allow_reentry=True
    )

    dp = Dispatcher(bot, None, workers=1, use_context=True)
    dp.add_handler(conv_handler)
    dp.add_handler(CommandHandler('example', send_example))
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
    """Главная страница"""
    return jsonify({
        "status": "running",
        "service": "Tolyatti Fencing Registration Bot",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "admin": "/admin",
            "admin_panel": "/admin?token=b1e807aeb2b1425995b17e1694296448",
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
                            <th>ID</th><th>ФИО</th><th>Оружие</th><th>Телефон</th><th>Опыт</th><th>Событие</th><th>Статус</th><th>Дата</th>
                        </tr>
                        {% for r in regs %}
                        <tr>
                            <td>{{ r.id }}</td>
                            <td>{{ r.full_name }}</td>
                            <td>{{ r.weapon_type }}</td>
                            <td>{{ r.phone }}</td>
                            <td>{{ r.experience[:50] }}{% if r.experience|length > 50 %}...{% endif %}</td>
                            <td>{{ r.event.name if r.event else 'Не указано' }}</td>
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
                    'event_id': r.event_id,
                    'event_name': r.event.name if r.event else None,
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
                    # Простое уведомление без разметки
                    bot.send_message(
                        reg.telegram_id,
                        f"✅ Ваша заявка #{reg.id} подтверждена!\n\n"
                        f"Рады сообщить, что ваша заявка на участие в соревнованиях по фехтованию подтверждена.\n"
                        f"Ждем вас на соревнованиях!\n\n"
                        f"Детали заявки:\n"
                        f"ФИО: {reg.full_name}\n"
                        f"Оружие: {reg.weapon_type}\n"
                        f"Категория: {reg.category}\n"
                        f"Соревнование: {reg.event.name if reg.event else 'Не указано'}"
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
                    # Простое уведомление без разметки
                    bot.send_message(
                        reg.telegram_id,
                        f"❌ Ваша заявка #{reg.id} отклонена\n\n"
                        f"К сожалению, ваша заявка на участие в соревнованиях была отклонена.\n"
                        f"По вопросам обращайтесь к организаторам."
                    )
                except Exception as e:
                    logger.error(f"Не удалось отправить уведомление пользователю {reg.telegram_id}: {e}")
        
        return jsonify({'success': True, 'status': 'rejected'})
    except Exception as e:
        logger.error(f"Reject API error: {e}")
        return jsonify({'error': str(e)}), 500

# ===== API для управления событиями =====
@app.route('/api/events')
def get_events_api():
    """API для получения событий"""
    token = request.args.get('token')
    if not token or token != config.SECRET_KEY:
        return jsonify({'error': 'Invalid token'}), 403
    
    try:
        with session_scope() as session:
            events = session.query(Event).order_by(Event.event_date).all()
            result = [{
                'id': e.id,
                'name': e.name,
                'event_date': e.event_date.isoformat() if e.event_date else None,
                'description': e.description,
                'is_active': e.is_active,
                'created_at': e.created_at.isoformat() if e.created_at else None
            } for e in events]
            return jsonify({'events': result})
    except Exception as e:
        logger.error(f"Events API error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/events', methods=['POST'])
def create_event_api():
    """API для создания события"""
    token = request.args.get('token')
    if not token or token != config.SECRET_KEY:
        return jsonify({'error': 'Invalid token'}), 403
    
    try:
        data = request.get_json()
        if not data.get('name') or not data.get('event_date'):
            return jsonify({'error': 'Name and date are required'}), 400
        
        with session_scope() as session:
            event = Event(
                name=data['name'],
                event_date=datetime.strptime(data['event_date'], '%Y-%m-%d').date(),
                description=data.get('description', ''),
                is_active=True
            )
            session.add(event)
        
        return jsonify({'success': True, 'event': {
            'id': event.id,
            'name': event.name,
            'event_date': event.event_date.isoformat(),
            'description': event.description
        }})
    except Exception as e:
        logger.error(f"Create event API error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/events/<int:event_id>/toggle')
def toggle_event_api(event_id):
    """API для переключения активности события"""
    token = request.args.get('token')
    if not token or token != config.SECRET_KEY:
        return jsonify({'error': 'Invalid token'}), 403
    
    try:
        with session_scope() as session:
            event = session.query(Event).get(event_id)
            if not event:
                return jsonify({'error': 'Event not found'}), 404
            
            event.is_active = not event.is_active
            event.updated_at = datetime.utcnow()
        
        return jsonify({'success': True, 'is_active': event.is_active})
    except Exception as e:
        logger.error(f"Toggle event API error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/events/<int:event_id>', methods=['DELETE'])
def delete_event_api(event_id):
    """API для удаления события"""
    token = request.args.get('token')
    if not token or token != config.SECRET_KEY:
        return jsonify({'error': 'Invalid token'}), 403
    
    try:
        with session_scope() as session:
            event = session.query(Event).get(event_id)
            if not event:
                return jsonify({'error': 'Event not found'}), 404
            
            # Не удаляем, а деактивируем и отвязываем заявки
            event.is_active = False
            
            # Отвязываем заявки от этого события
            registrations = session.query(Registration).filter_by(event_id=event_id).all()
            for reg in registrations:
                reg.event_id = None
            
            session.delete(event)
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Delete event API error: {e}")
        return jsonify({'error': str(e)}), 500

# ===== API для очистки заявок =====
@app.route('/api/cleanup/preview')
def preview_cleanup_api():
    """API для предпросмотра очистки"""
    token = request.args.get('token')
    if not token or token != config.SECRET_KEY:
        return jsonify({'error': 'Invalid token'}), 403
    
    cleanup_type = request.args.get('type', 'past_events')
    
    try:
        with session_scope() as session:
            count = 0
            
            if cleanup_type == 'past_events':
                # Заявки на прошедшие события
                count = session.query(Registration).join(Event).filter(
                    Event.event_date < datetime.now().date()
                ).count()
            
            elif cleanup_type == 'all_rejected':
                # Все отклоненные заявки
                count = session.query(Registration).filter_by(status='rejected').count()
            
            elif cleanup_type == 'all_old':
                # Все заявки старше 30 дней
                cutoff_date = datetime.utcnow() - timedelta(days=30)
                count = session.query(Registration).filter(
                    Registration.created_at < cutoff_date
                ).count()
        
        return jsonify({'count': count})
    except Exception as e:
        logger.error(f"Cleanup preview API error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cleanup/execute', methods=['POST'])
def execute_cleanup_api():
    """API для выполнения очистки"""
    token = request.args.get('token')
    if not token or token != config.SECRET_KEY:
        return jsonify({'error': 'Invalid token'}), 403
    
    cleanup_type = request.args.get('type', 'past_events')
    
    try:
        with session_scope() as session:
            deleted_count = 0
            
            if cleanup_type == 'past_events':
                # Удаляем заявки на прошедшие события
                registrations = session.query(Registration).join(Event).filter(
                    Event.event_date < datetime.now().date()
                ).all()
                
                for reg in registrations:
                    session.delete(reg)
                    deleted_count += 1
            
            elif cleanup_type == 'all_rejected':
                # Удаляем все отклоненные заявки
                registrations = session.query(Registration).filter_by(status='rejected').all()
                
                for reg in registrations:
                    session.delete(reg)
                    deleted_count += 1
            
            elif cleanup_type == 'all_old':
                # Удаляем все заявки старше 30 дней
                cutoff_date = datetime.utcnow() - timedelta(days=30)
                registrations = session.query(Registration).filter(
                    Registration.created_at < cutoff_date
                ).all()
                
                for reg in registrations:
                    session.delete(reg)
                    deleted_count += 1
            
            session.commit()
        
        return jsonify({'success': True, 'deleted_count': deleted_count})
    except Exception as e:
        logger.error(f"Cleanup execute API error: {e}")
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
        'version': '2.0.0',
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
