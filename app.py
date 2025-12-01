from flask import Flask, request, jsonify, render_template_string
from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
import logging
from config import config
from database import init_db, get_session, Registration, Admin

# ===== Инициализация приложения =====
app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# Инициализация БД
init_db()

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Бот
bot = Bot(token=config.TELEGRAM_TOKEN)

# ===== Состояния =====
NAME, WEAPON, CATEGORY, AGE, PHONE, EXPERIENCE, CONFIRM = range(7)

# ===== Декораторы =====
def admin_required(func):
    def wrapper(update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        session_db = get_session()
        try:
            admin = session_db.query(Admin).filter_by(telegram_id=user_id, is_active=True).first()
            if not admin:
                update.message.reply_text("❌ У вас нет прав администратора.")
                return
        finally:
            session_db.close()
        return func(update, context)
    return wrapper


def super_admin_required(func):
    def wrapper(update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        if user_id not in config.get_admin_ids():
            update.message.reply_text("❌ Только супер-админы могут использовать эту команду.")
            return
        return func(update, context)
    return wrapper


# ===== Админ-команды =====
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

        session_db = get_session()
        try:
            if session_db.query(Admin).filter_by(telegram_id=tid).first():
                update.message.reply_text("⚠️ Уже является админом.")
                return

            new_admin = Admin(telegram_id=tid, role=role, created_by=update.message.from_user.id)
            session_db.add(new_admin)
            session_db.commit()
            update.message.reply_text(f"✅ Админ {tid} добавлен как {role}")
        finally:
            session_db.close()
    except ValueError:
        update.message.reply_text("❌ Неверный ID")


@admin_required
def admin_list(update: Update, context: CallbackContext):
    session_db = get_session()
    try:
        admins = session_db.query(Admin).all()
        msg = "👥 *Администраторы:*\n"
        for a in admins:
            status = "🟢" if a.is_active else "🔴"
            msg += f"{status} {a.telegram_id} ({a.role})\n"
        update.message.reply_text(msg, parse_mode='Markdown')
    finally:
        session_db.close()


# ===== Регистрация =====
def start(update: Update, context: CallbackContext) -> int:
    user = update.message.from_user
    context.user_data.update({
        'telegram_id': user.id,
        'username': user.username
    })
    update.message.reply_text("Введите ФИО:")
    return NAME


def get_name(update: Update, context: CallbackContext) -> int:
    context.user_data['full_name'] = update.message.text
    kb = [[w] for w in config.WEAPON_TYPES]
    rm = ReplyKeyboardMarkup(kb, one_time_keyboard=True)
    update.message.reply_text("Оружие:", reply_markup=rm)
    return WEAPON


def get_weapon(update: Update, context: CallbackContext) -> int:
    w = update.message.text
    if w not in config.WEAPON_TYPES:
        update.message.reply_text("Выберите из списка.")
        return WEAPON
    context.user_data['weapon_type'] = w
    kb = [[c] for c in config.CATEGORIES]
    rm = ReplyKeyboardMarkup(kb, one_time_keyboard=True)
    update.message.reply_text("Категория:", reply_markup=rm)
    return CATEGORY


def get_category(update: Update, context: CallbackContext) -> int:
    c = update.message.text
    if c not in config.CATEGORIES:
        return CATEGORY
    context.user_data['category'] = c
    kb = [[a] for a in config.AGE_GROUPS]
    rm = ReplyKeyboardMarkup(kb, one_time_keyboard=True)
    update.message.reply_text("Возраст:", reply_markup=rm)
    return AGE


def get_age(update: Update, context: CallbackContext) -> int:
    a = update.message.text
    if a not in config.AGE_GROUPS:
        return AGE
    context.user_data['age_group'] = a
    kb = [[KeyboardButton("📞 Поделиться", request_contact=True)]]
    rm = ReplyKeyboardMarkup(kb, one_time_keyboard=True)
    update.message.reply_text("Телефон:", reply_markup=rm)
    return PHONE


def get_phone(update: Update, context: CallbackContext) -> int:
    p = update.message.contact.phone_number if update.message.contact else update.message.text
    context.user_data['phone'] = p
    update.message.reply_text("Опыт:")
    return EXPERIENCE


def get_experience(update: Update, context: CallbackContext) -> int:
    context.user_data['experience'] = update.message.text
    data = context.user_data
    msg = f"""
📋 {data['full_name']} | {data['weapon_type']}
Телефон: {data['phone']}
Опыт: {data['experience']}
Подтвердить?
"""
    kb = [['✅ Да', '❌ Нет']]
    rm = ReplyKeyboardMarkup(kb, one_time_keyboard=True)
    update.message.reply_text(msg, reply_markup=rm)
    return CONFIRM


def confirm_registration(update: Update, context: CallbackContext) -> int:
    if update.message.text == '❌ Нет':
        return start(update, context)

    data = context.user_data
    session_db = get_session()
    try:
        reg = Registration(
            telegram_id=data['telegram_id'],
            username=data['username'],
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
        update.message.reply_text("✅ Заявка отправлена!", reply_markup=None)
    except Exception as e:
        logger.error(e)
        update.message.reply_text("❌ Ошибка.")
    finally:
        session_db.close()
    return ConversationHandler.END


def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Отменено.", reply_markup=None)
    return ConversationHandler.END


def view_registrations(update: Update, context: CallbackContext):
    session_db = get_session()
    try:
        regs = session_db.query(Registration).filter_by(telegram_id=update.message.from_user.id).all()
        msg = "Ваши заявки:\n" + "".join(f"\n#{r.id} {r.weapon_type} — {r.status}" for r in regs) or "Нет заявок."
        update.message.reply_text(msg)
    finally:
        session_db.close()


# ===== Диспетчер =====
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
    dp.add_handler(CommandHandler('admin_add', admin_add))
    dp.add_handler(CommandHandler('admin_list', admin_list))
    return dp


dp = setup_dispatcher()

# ===== Веб-интерфейс =====
ADMIN_TEMPLATE = """
<h1>Заявки ({{ regs|length }})</h1>
<table border="1"><tr><th>ФИО</th><th>Оружие</th><th>Статус</th></tr>
{% for r in regs %}
<tr><td>{{ r.full_name }}</td><td>{{ r.weapon_type }}</td><td>{{ r.status }}</td></tr>
{% endfor %}
</table>
"""


@app.route('/')
def home():
    return jsonify(status="Running")


@app.route('/admin')
def admin():
    session_db = get_session()
    try:
        regs = session_db.query(Registration).all()
        return render_template_string(ADMIN_TEMPLATE, regs=regs)
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
