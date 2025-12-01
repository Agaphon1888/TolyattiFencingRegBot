from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Dispatcher, CallbackContext, CommandHandler, MessageHandler, Filters, ConversationHandler
import logging
from config import config
from database import init_db, get_session, Registration
import secrets
from datetime import datetime, timedelta

# ===== Инициализация приложения =====
app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# Инициализация базы данных
init_db()

# Настройка логирования
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=config.TELEGRAM_TOKEN)

# ===== Состояния диалога =====
NAME, WEAPON, CATEGORY, AGE, PHONE, EXPERIENCE, CONFIRM = range(7)

# ===== Telegram Handlers =====
def start(update: Update, context: CallbackContext) -> int:
    user = update.effective_user
    context.user_data['telegram_id'] = user.id
    context.user_data['username'] = user.username

    update.message.reply_text(
        '🤺 Добро пожаловать в систему регистрации на соревнования по фехтованию!\n\n'
        'Введите ваше ФИО:'
    )
    return NAME


def get_name(update: Update, context: CallbackContext) -> int:
    context.user_data['full_name'] = update.message.text

    keyboard = [[weapon] for weapon in config.WEAPON_TYPES]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    update.message.reply_text('Выберите вид оружия:', reply_markup=reply_markup)
    return WEAPON


def get_weapon(update: Update, context: CallbackContext) -> int:
    weapon = update.message.text
    if weapon not in config.WEAPON_TYPES:
        update.message.reply_text('Пожалуйста, выберите из списка.')
        return WEAPON
    context.user_data['weapon_type'] = weapon

    keyboard = [[cat] for cat in config.CATEGORIES]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    update.message.reply_text('Выберите категорию:', reply_markup=reply_markup)
    return CATEGORY


def get_category(update: Update, context: CallbackContext) -> int:
    category = update.message.text
    if category not in config.CATEGORIES:
        return CATEGORY
    context.user_data['category'] = category

    keyboard = [[age] for age in config.AGE_GROUPS]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    update.message.reply_text('Выберите возрастную группу:', reply_markup=reply_markup)
    return AGE


def get_age(update: Update, context: CallbackContext) -> int:
    age_group = update.message.text
    if age_group not in config.AGE_GROUPS:
        return AGE
    context.user_data['age_group'] = age_group

    keyboard = [[KeyboardButton("📞 Поделиться контактом", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    update.message.reply_text('Отправьте номер телефона:', reply_markup=reply_markup)
    return PHONE


def get_phone(update: Update, context: CallbackContext) -> int:
    phone = update.message.contact.phone_number if update.message.contact else update.message.text
    context.user_data['phone'] = phone
    update.message.reply_text('Расскажите о вашем опыте (разряд, стаж, соревнования):')
    return EXPERIENCE


def get_experience(update: Update, context: CallbackContext) -> int:
    context.user_data['experience'] = update.message.text

    data = context.user_data
    summary = f"""
📋 *Данные регистрации:*

ФИО: {data['full_name']}
Оружие: {data['weapon_type']}
Категория: {data['category']}
Возраст: {data['age_group']}
Телефон: {data['phone']}
Опыт: {data['experience']}

Подтвердить?
"""
    keyboard = [['✅ Да', '❌ Нет']]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    update.message.reply_text(summary, parse_mode='Markdown', reply_markup=reply_markup)
    return CONFIRM


def confirm_registration(update: Update, context: CallbackContext) -> int:
    if update.message.text == '❌ Нет':
        return start(update, context)

    data = context.user_data
    session_db = get_session()
    try:
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
        session_db.add(reg)
        session_db.commit()
        update.message.reply_text('✅ Заявка отправлена!', reply_markup=None)
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")
        update.message.reply_text('❌ Ошибка отправки заявки.', reply_markup=None)
    finally:
        session_db.close()

    return ConversationHandler.END


def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Отменено.', reply_markup=None)
    return ConversationHandler.END


def view_registrations(update: Update, context: CallbackContext):
    session_db = get_session()
    try:
        regs = session_db.query(Registration).filter_by(telegram_id=update.effective_user.id).all()
        if not regs:
            update.message.reply_text('У вас нет заявок.')
            return
        msg = "Ваши заявки:\n\n"
        for r in regs:
            msg += f"#{r.id} {r.weapon_type}, {r.category} — {r.status}\n"
        update.message.reply_text(msg)
    finally:
        session_db.close()


# ===== Админ-команды (пример) =====
def admin_required(func):
    def wrapper(update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        if user_id not in config.get_admin_ids():
            update.message.reply_text("❌ У вас нет прав администратора.")
            return
        return func(update, context)
    return wrapper


@admin_required
def admin_stats(update: Update, context: CallbackContext):
    session_db = get_session()
    try:
        regs = session_db.query(Registration).all()
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
    finally:
        session_db.close()


# ===== Настройка диспетчера =====
def setup_dispatcher():
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
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    dp = Dispatcher(bot, None, workers=0)
    dp.add_handler(conv_handler)
    dp.add_handler(CommandHandler('myregistrations', view_registrations))
    dp.add_handler(CommandHandler('admin_stats', admin_stats))  # Добавьте другие команды
    return dp


dp = setup_dispatcher()

# ===== Веб-интерфейс =====
ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Админ-панель</title>
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
    <h1>Заявки на участие</h1>
    <p><strong>Всего заявок:</strong> {{ registrations|length }}</p>
    <a href="{{ url_for('test_data') }}">➕ Добавить тестовые данные</a> | 
    <a href="{{ url_for('admin_panel') }}?token={{ token }}">🔄 Обновить</a>

    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>ФИО</th>
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
                <td>{{ reg.experience }}</td>
                <td class="status-{{ reg.status }}">{{ reg.status }}</td>
                <td>{{ reg.created_at.strftime('%d.%m %H:%M') }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
"""


@app.route('/')
def index():
    return redirect(url_for('admin_panel'))


@app.route('/admin_panel')
def admin_panel():
    token = request.args.get('token') or session.get('admin_token')
    if not token or token != session.get('admin_token'):
        return redirect(f"https://t.me/TolyattiFencingRegBot?start=admin_auth")
    session['last_activity'] = datetime.utcnow()
    session['admin_token'] = token

    if datetime.utcnow() > session.get('last_activity', datetime.min) + timedelta(seconds=config.ADMIN_TOKEN_EXPIRE):
        session.clear()
        return redirect(url_for('admin_panel'))

    session_db = get_session()
    try:
        regs = session_db.query(Registration).all()
        return render_template_string(ADMIN_TEMPLATE, registrations=regs, token=token)
    finally:
        session_db.close()


@app.route('/test_data')
def test_data():
    from migrations import create_test_data
    create_test_data()
    return redirect(url_for('admin_panel'))


@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(), bot)
    dp.process_update(update)
    return 'ok'


@app.route('/set_webhook')
def set_webhook_route():
    try:
        bot.set_webhook(config.get_webhook_url())
        return 'Webhook установлен'
    except Exception as e:
        return f'Ошибка: {e}'


@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})


# ===== Запуск =====
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=config.PORT)
