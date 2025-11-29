# app.py
from flask import Flask, request, jsonify, render_template
from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
from telegram.error import RetryAfter, Unauthorized
import logging
import time
import os

from config import Config
from database import Database

# === Настройка логирования ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Инициализация приложения ===
app = Flask(__name__)
app.config.from_object(Config)

# === Инициализация базы данных ===
db = Database()

# === Состояния для диалога ===
NAME, WEAPON, CATEGORY, AGE, PHONE, EXPERIENCE, CONFIRM = range(7)

# === Декораторы доступа ===
def admin_required(func):
    def wrapper(update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        if not db.admin_manager.is_admin(user_id):
            update.message.reply_text("❌ У вас нет прав администратора.")
            return
        return func(update, context)
    return wrapper

def super_admin_required(func):
    def wrapper(update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        if not db.admin_manager.is_super_admin(user_id):
            update.message.reply_text("❌ У вас нет прав супер-администратора.")
            return
        return func(update, context)
    return wrapper

# === Команды для админов ===
@admin_required
def admin_stats(update: Update, context: CallbackContext):
    stats = db.get_stats()
    admin_stats = db.admin_manager.get_admin_stats()
    message = f"""
📊 *Статистика системы:*

*Заявки:* {stats['total']} (⏳{stats['pending']}, ✓{stats['confirmed']}, ✖️{stats['rejected']})
*Админы:* {admin_stats['admins']}, *Модеры:* {admin_stats['moderators']}

*По оружию:*
"""
    for w, s in stats['weapons'].items():
        message += f"• {w}: {s['total']} (✓{s['confirmed']})\n"
    update.message.reply_text(message, parse_mode='Markdown')

@super_admin_required
def admin_add(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Используйте: /admin_add <id> <role=admin|moderator>")
        return
    try:
        tid = int(context.args[0])
        role = context.args[1] if len(context.args) > 1 else 'moderator'
        if role not in ['admin', 'moderator']:
            update.message.reply_text("Роль: admin или moderator")
            return
        db.admin_manager.add_admin(tid, f"user_{tid}", "Неизвестно", role, update.effective_user.id)
        update.message.reply_text(f"✅ Админ {tid} добавлен как {role}")
    except Exception as e:
        logger.exception("Ошибка добавления админа")
        update.message.reply_text("❌ Ошибка")

@super_admin_required
def admin_list(update: Update, context: CallbackContext):
    admins = db.admin_manager.get_all_admins()
    msg = "👥 *Администраторы:*\n"
    for a in admins:
        status = "🟢" if a.is_active else "🔴"
        role_icon = "👑" if a.role == 'admin' else "🛠️"
        msg += f"{status} {role_icon} `{a.telegram_id}` — {a.role}\n"
    update.message.reply_text(msg, parse_mode='Markdown')

@admin_required
def admin_broadcast(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Используйте: /broadcast <текст>")
        return
    text = ' '.join(context.args)
    users = {r.telegram_id for r in db.get_all_registrations()}
    bot = context.bot
    ok, fail = 0, 0
    for uid in users:
        try:
            bot.send_message(uid, f"📢 {text}", parse_mode='Markdown')
            ok += 1
            time.sleep(0.05)
        except Unauthorized:
            continue
        except RetryAfter as e:
            time.sleep(e.retry_after)
            bot.send_message(uid, f"📢 {text}", parse_mode='Markdown')
            ok += 1
        except Exception as e:
            logger.warning(f"Не отправлено {uid}: {e}")
            fail += 1
    update.message.reply_text(f"✅ Готово: {ok}, ❌ ошибок: {fail}")

# === Диалог регистрации ===
def start(update: Update, context: CallbackContext) -> int:
    context.user_data.clear()
    context.user_data['telegram_id'] = update.effective_user.id
    context.user_data['username'] = update.effective_user.username
    update.message.reply_text("Введите ФИО:")
    return NAME

def get_name(update: Update, context: CallbackContext) -> int:
    context.user_data['full_name'] = update.message.text
    kb = [[w] for w in Config.WEAPON_TYPES]
    update.message.reply_text("Оружие:", reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True))
    return WEAPON

def get_weapon(update: Update, context: CallbackContext) -> int:
    w = update.message.text
    if w not in Config.WEAPON_TYPES:
        update.message.reply_text("Выберите из списка.")
        return WEAPON
    context.user_data['weapon_type'] = w
    kb = [[c] for c in Config.CATEGORIES]
    update.message.reply_text("Категория:", reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True))
    return CATEGORY

def get_category(update: Update, context: CallbackContext) -> int:
    c = update.message.text
    if c not in Config.CATEGORIES:
        update.message.reply_text("Выберите из списка.")
        return CATEGORY
    context.user_data['category'] = c
    kb = [[a] for a in Config.AGE_GROUPS]
    update.message.reply_text("Возраст:", reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True))
    return AGE

def get_age(update: Update, context: CallbackContext) -> int:
    a = update.message.text
    if a not in Config.AGE_GROUPS:
        update.message.reply_text("Выберите из списка.")
        return AGE
    context.user_data['age_group'] = a
    kb = [[KeyboardButton("📞", request_contact=True)]]
    update.message.reply_text("Телефон:", reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True))
    return PHONE

def get_phone(update: Update, context: CallbackContext) -> int:
    phone = update.message.contact.phone_number if update.message.contact else update.message.text
    context.user_data['phone'] = phone
    update.message.reply_text("Расскажите об опыте фехтования:")
    return EXPERIENCE

def get_experience(update: Update, context: CallbackContext) -> int:
    context.user_data['experience'] = update.message.text
    data = context.user_data
    msg = f"""
📋 Проверьте данные:
ФИО: {data['full_name']}
Оружие: {data['weapon_type']}
Телефон: {data['phone']}

Всё верно?
"""
    kb = [['✅ Отправить', '❌ Переписать']]
    update.message.reply_text(msg, reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True))
    return CONFIRM

def confirm_registration(update: Update, context: CallbackContext) -> int:
    if update.message.text == '✅ Отправить':
        db.add_registration(context.user_data)
        update.message.reply_text("✅ Заявка отправлена! Администратор свяжется с вами.", reply_markup=None)
    else:
        return start(update, context)
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Отменено.", reply_markup=None)
    return ConversationHandler.END

# === Инициализация Dispatcher ===
def setup_dispatcher():
    bot = Bot(token=Config.TELEGRAM_TOKEN)
    dp = Dispatcher(bot, None, workers=0, use_context=True)
    
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
    
    dp.add_handler(conv_handler)
    dp.add_handler(CommandHandler('admin_stats', admin_stats))
    dp.add_handler(CommandHandler('admin_add', admin_add))
    dp.add_handler(CommandHandler('admin_list', admin_list))
    dp.add_handler(CommandHandler('broadcast', admin_broadcast))
    
    return dp

# === Создание dispatcher после db ===
dispatcher = setup_dispatcher()

# === Flask маршруты ===
@app.route('/')
def home():
    return jsonify({"status": "running", "service": "TolyattiFencingRegBot"})

@app.route('/admin')
def admin():
    regs = db.get_all_registrations()
    return render_template('admin.html', registrations=regs)

@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(), dispatcher.bot)
    dispatcher.process_update(update)
    return 'ok'

@app.route('/set_webhook', methods=['GET'])
def set_webhook_route():
    url = Config.WEBHOOK_URL
    if not url:
        return jsonify({"error": "WEBHOOK_URL не задан"}), 400
    try:
        result = dispatcher.bot.set_webhook(url)
        if result:
            return jsonify({"status": "success", "url": url})
        else:
            return jsonify({"error": "Не удалось установить вебхук"}), 500
    except Exception as e:
        logger.error(f"Ошибка вебхука: {e}")
        return jsonify({"error": str(e)}), 500

# === Точка входа ===
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
