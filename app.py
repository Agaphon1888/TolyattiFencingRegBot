# app.py
from flask import Flask, request, jsonify, render_template
import logging
import os
import asyncio

from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

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

# === Глобальная переменная для хранения Application ===
telegram_app = None

# === Декораторы доступа ===
def admin_required(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not db.admin_manager.is_admin(user_id):
            await update.message.reply_text("❌ У вас нет прав администратора.")
            return
        return await func(update, context)
    return wrapper

def super_admin_required(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not db.admin_manager.is_super_admin(user_id):
            await update.message.reply_text("❌ У вас нет прав супер-администратора.")
            return
        return await func(update, context)
    return wrapper

# === Команды для админов ===
@admin_required
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    await update.message.reply_text(message, parse_mode='Markdown')

@super_admin_required
async def admin_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Используйте: /admin_add <id> <role=admin|moderator>")
        return
    try:
        tid = int(context.args[0])
        role = context.args[1] if len(context.args) > 1 else 'moderator'
        if role not in ['admin', 'moderator']:
            await update.message.reply_text("Роль: admin или moderator")
            return
        db.admin_manager.add_admin(tid, f"user_{tid}", "Неизвестно", role, update.effective_user.id)
        await update.message.reply_text(f"✅ Админ {tid} добавлен как {role}")
    except Exception as e:
        logger.exception("Ошибка добавления админа")
        await update.message.reply_text("❌ Ошибка")

@super_admin_required
async def admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admins = db.admin_manager.get_all_admins()
    msg = "👥 *Администраторы:*\n"
    for a in admins:
        status = "🟢" if a.is_active else "🔴"
        role_icon = "👑" if a.role == 'admin' else "🛠️"
        msg += f"{status} {role_icon} `{a.telegram_id}` — {a.role}\n"
    await update.message.reply_text(msg, parse_mode='Markdown')

@admin_required
async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Используйте: /broadcast <текст>")
        return
    text = ' '.join(context.args)
    users = {r.telegram_id for r in db.get_all_registrations()}
    bot = context.bot
    ok, fail = 0, 0
    for uid in users:
        try:
            await bot.send_message(uid, f"📢 {text}", parse_mode='Markdown')
            ok += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            if "blocked" in str(e) or "not found" in str(e):
                continue
            logger.warning(f"Не отправлено {uid}: {e}")
            fail += 1
    await update.message.reply_text(f"✅ Готово: {ok}, ❌ ошибок: {fail}")

# === Диалог регистрации ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    context.user_data['telegram_id'] = update.effective_user.id
    context.user_data['username'] = update.effective_user.username
    await update.message.reply_text("Введите ФИО:")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['full_name'] = update.message.text
    kb = [[w] for w in Config.WEAPON_TYPES]
    await update.message.reply_text(
        "Оружие:",
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True)
    )
    return WEAPON

async def get_weapon(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    w = update.message.text
    if w not in Config.WEAPON_TYPES:
        await update.message.reply_text("Выберите из списка.")
        return WEAPON
    context.user_data['weapon_type'] = w
    kb = [[c] for c in Config.CATEGORIES]
    await update.message.reply_text(
        "Категория:",
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True)
    )
    return CATEGORY

async def get_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    c = update.message.text
    if c not in Config.CATEGORIES:
        await update.message.reply_text("Выберите из списка.")
        return CATEGORY
    context.user_data['category'] = c
    kb = [[a] for a in Config.AGE_GROUPS]
    await update.message.reply_text(
        "Возраст:",
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True)
    )
    return AGE

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    a = update.message.text
    if a not in Config.AGE_GROUPS:
        await update.message.reply_text("Выберите из списка.")
        return AGE
    context.user_data['age_group'] = a
    kb = [[KeyboardButton("📞", request_contact=True)]]
    await update.message.reply_text(
        "Телефон:",
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True)
    )
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone = update.message.contact.phone_number if update.message.contact else update.message.text
    context.user_data['phone'] = phone
    await update.message.reply_text("Расскажите об опыте фехтования:")
    return EXPERIENCE

async def get_experience(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
    await update.message.reply_text(
        msg,
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True)
    )
    return CONFIRM

async def confirm_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == '✅ Отправить':
        db.add_registration(context.user_data)
        await update.message.reply_text(
            "✅ Заявка отправлена! Администратор свяжется с вами.",
            reply_markup=None
        )
    else:
        return await start(update, context)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Отменено.", reply_markup=None)
    return ConversationHandler.END

# === Инициализация Telegram Application ===
def create_telegram_app():
    global telegram_app
    telegram_app = Application.builder().token(Config.TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            WEAPON: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_weapon)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_category)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            PHONE: [MessageHandler(filters.TEXT | filters.CONTACT, get_phone)],
            EXPERIENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_experience)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_registration)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    telegram_app.add_handler(conv_handler)
    telegram_app.add_handler(CommandHandler('admin_stats', admin_stats))
    telegram_app.add_handler(CommandHandler('admin_add', admin_add))
    telegram_app.add_handler(CommandHandler('admin_list', admin_list))
    telegram_app.add_handler(CommandHandler('broadcast', admin_broadcast))

    return telegram_app

# === Flask маршруты ===
@app.route('/')
def home():
    return jsonify({"status": "running", "service": "TolyattiFencingRegBot"})

@app.route('/admin')
def admin():
    regs = db.get_all_registrations()
    return render_template('admin.html', registrations=regs)

@app.route('/webhook', methods=['POST'])
async def webhook():
    if telegram_app is None:
        create_telegram_app()
    request_json = await request.get_json()
    update = Update.de_json(request_json, telegram_app.bot)
    await telegram_app.process_update(update)
    return 'ok'

@app.route('/set_webhook', methods=['GET'])
async def set_webhook_route():
    url = Config.WEBHOOK_URL
    if not url:
        return jsonify({"error": "WEBHOOK_URL не задан"}), 400
    try:
        bot = Bot(token=Config.TELEGRAM_TOKEN)
        await bot.set_webhook(url)
        return jsonify({"status": "success", "url": url})
    except Exception as e:
        logger.error(f"Ошибка вебхука: {e}")
        return jsonify({"error": str(e)}), 500

# === Точка входа ===
if __name__ == '__main__':
    create_telegram_app()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
