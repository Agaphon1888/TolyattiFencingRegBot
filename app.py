from flask import Flask, request, jsonify, render_template_string, session
from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
import logging
from config import config
from database import init_db, get_session, Registration

# Инициализация приложения
app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# Инициализация БД
init_db()

# Настройка логирования
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Бот
bot = Bot(token=config.TELEGRAM_TOKEN)

# Состояния
NAME, WEAPON, CATEGORY, AGE, PHONE, EXPERIENCE, CONFIRM = range(7)

# Декораторы
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

• Всего: {total}
• Ожидают: {pending}
• Подтверждены: {confirmed}
• Отклонены: {rejected}
        """
        update.message.reply_text(stats, parse_mode='Markdown')
    finally:
        session_db.close()


# Обработчики регистрации
def start(update: Update, context: CallbackContext) -> int:
    user = update.effective_user
    context.user_data['telegram_id'] = user.id
    context.user_data['username'] = user.username
    update.message.reply_text("Введите ваше ФИО:")
    return NAME


def get_name(update: Update, context: CallbackContext) -> int:
    context.user_data['full_name'] = update.message.text
    keyboard = [[w] for w in config.WEAPON_TYPES]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    update.message.reply_text("Выберите оружие:", reply_markup=reply_markup)
    return WEAPON


def get_weapon(update: Update, context: CallbackContext) -> int:
    weapon = update.message.text
    if weapon not in config.WEAPON_TYPES:
        update.message.reply_text("Выберите из списка.")
        return WEAPON
    context.user_data['weapon_type'] = weapon
    keyboard = [[c] for c in config.CATEGORIES]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    update.message.reply_text("Категория:", reply_markup=reply_markup)
    return CATEGORY


def get_category(update: Update, context: CallbackContext) -> int:
    category = update.message.text
    if category not in config.CATEGORIES:
        return CATEGORY
    context.user_data['category'] = category
    keyboard = [[a] for a in config.AGE_GROUPS]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    update.message.reply_text("Возраст:", reply_markup=reply_markup)
    return AGE


def get_age(update: Update, context: CallbackContext) -> int:
    age_group = update.message.text
    if age_group not in config.AGE_GROUPS:
        return AGE
    context.user_data['age_group'] = age_group
    keyboard = [[KeyboardButton("📞 Поделиться", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    update.message.reply_text("Телефон:", reply_markup=reply_markup)
    return PHONE


def get_phone(update: Update, context: CallbackContext) -> int:
    phone = update.message.contact.phone_number if update.message.contact else update.message.text
    context.user_data['phone'] = phone
    update.message.reply_text("Опыт:")
    return EXPERIENCE


def get_experience(update: Update, context: CallbackContext) -> int:
    context.user_data['experience'] = update.message.text
    data = context.user_data
    summary = f"""
📋 {data['full_name']}
Оружие: {data['weapon_type']}
Категория: {data['category']}
Возраст: {data['age_group']}
Телефон: {data['phone']}
Опыт: {data['experience']}
Подтвердить?
"""
    keyboard = [['✅ Да', '❌ Нет']]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    update.message.reply_text(summary, reply_markup=reply_markup)
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
        update.message.reply_text('✅ Заявка отправлена!')
    except Exception as e:
        logger.error(e)
        update.message.reply_text('❌ Ошибка.')
    finally:
        session_db.close()
    return ConversationHandler.END


def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Отменено.')
    return ConversationHandler.END


def view_registrations(update: Update, context: CallbackContext):
    session_db = get_session()
    try:
        regs = session_db.query(Registration).filter_by(telegram_id=update.effective_user.id).all()
        if not regs:
            update.message.reply_text('Нет заявок.')
            return
        msg = "Ваши заявки:\n"
        for r in regs:
            msg += f"#{r.id} {r.weapon_type} — {r.status}\n"
        update.message.reply_text(msg)
    finally:
        session_db.close()


# Диспетчер
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
    dp.add_handler(CommandHandler('admin_stats', admin_stats))
    return dp


dp = setup_dispatcher()

# Веб-интерфейс
ADMIN_TEMPLATE = """
<h1>Заявки ({{ registrations|length }})</h1>
<table border="1">
  <tr><th>ID</th><th>ФИО</th><th>Оружие</th><th>Статус</th></tr>
  {% for r in registrations %}
  <tr>
    <td>{{ r.id }}</td>
    <td>{{ r.full_name }}</td>
    <td>{{ r.weapon_type }}</td>
    <td>{{ r.status }}</td>
  </tr>
  {% endfor %}
</table>
"""

@app.route('/')
def index():
    return jsonify(status="Fencing Bot is running!")

@app.route('/admin')
def admin():
    session_db = get_session()
    try:
        regs = session_db.query(Registration).all()
        return render_template_string(ADMIN_TEMPLATE, registrations=regs)
    finally:
        session_db.close()

@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(), bot)
    dp.process_update(update)
    return 'ok'

@app.route('/set_webhook')
def set_webhook():
    try:
        bot.set_webhook(config.get_webhook_url())
        return f"✅ Webhook установлен: {config.get_webhook_url()}"
    except Exception as e:
        return f"❌ Ошибка: {e}"

@app.route('/health')
def health():
    return jsonify(status="healthy")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=config.PORT)
