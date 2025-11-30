# app.py
import os
import logging
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from database import init_db, db
import asyncio

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Flask приложение ===
app = Flask(__name__)

# === Инициализация базы данных ===
init_db()

# === Глобальные переменные ===
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_TELEGRAM_IDS", "123456789").split(",")))

if not TOKEN:
    raise RuntimeError("❌ Переменная окружения TELEGRAM_TOKEN не установлена!")

# === Состояния для сбора данных ===
USER_DATA = {}

# === Команда /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Зарегистрироваться", callback_data="register")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Привет! Добро пожаловать в турнир по фехтованию!\n"
        "Нажмите кнопку ниже, чтобы зарегистрироваться.",
        reply_markup=reply_markup
    )

# === Обработка нажатий ===
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user_data = USER_DATA.setdefault(user_id, {})

    if query.data == "register":
        user_data.clear()
        user_data['step'] = 'full_name'
        await query.edit_message_text("Введите ваше ФИО:")

    elif query.data.startswith("confirm_") or query.data.startswith("reject_"):
        reg_id = int(query.data.split("_")[1])
        registration = db.session.query(db.Registration).filter_by(id=reg_id).first()
        if not registration:
            await query.edit_message_text("❌ Заявка не найдена.")
            return

        if user_id not in ADMIN_IDS:
            await query.answer("❌ У вас нет прав!", show_alert=True)
            return

        if query.data.startswith("confirm_"):
            registration.status = "confirmed"
            db.session.commit()
            await context.bot.send_message(
                registration.telegram_id,
                "✅ Ваша заявка одобрена! До встречи на турнире!"
            )
            await query.edit_message_text("✅ Заявка одобрена.")
        else:
            comment = "Отклонено"
            registration.status = "rejected"
            registration.admin_comment = comment
            db.session.commit()
            await context.bot.send_message(
                registration.telegram_id,
                f"❌ Ваша заявка отклонена.\nКомментарий: {comment}"
            )
            await query.edit_message_text("❌ Заявка отклонена.")

# === Обработка сообщений от пользователя ===
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_data = USER_DATA.get(user_id, {})
    step = user_data.get('step')

    if not step:
        return

    text = update.message.text.strip()

    if step == 'full_name':
        user_data['full_name'] = text
        user_data['step'] = 'weapon_type'
        keyboard = [
            [InlineKeyboardButton("Рапира", callback_data="weapon_рапира")],
            [InlineKeyboardButton("Шпага", callback_data="weapon_шпага")],
            [InlineKeyboardButton("Сабля", callback_data="weapon_сабля")]
        ]
        await update.message.reply_text(
            "Выберите тип оружия:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif step == 'phone':
        user_data['phone'] = text
        user_data['step'] = 'experience'
        await update.message.reply_text("Расскажите о вашем опыте фехтования (например: «3 года, юниор»):")

    elif step == 'experience':
        user_data['experience'] = text
        user_data['step'] = None

        # Сохраняем в базу
        registration = db.Registration(
            telegram_id=user_id,
            full_name=user_data['full_name'],
            weapon_type=user_data['weapon_type'],
            category=user_data['category'],
            age_group=user_data['age_group'],
            phone=user_data['phone'],
            experience=user_data['experience'],
            status='pending'
        )
        db.session.add(registration)
        db.session.commit()

        await update.message.reply_text(
            "✅ Спасибо! Ваша заявка отправлена на рассмотрение.\n"
            "Администратор свяжется с вами в ближайшее время."
        )

        # Уведомление админам
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"🆕 Новая заявка от {user_data['full_name']}\n"
                    f"Оружие: {user_data['weapon_type']}\n"
                    f"Возраст: {user_data['age_group']}\n"
                    f"Телефон: {user_data['phone']}\n"
                    f"Опыт: {user_data['experience']}\n\n"
                    "Подтвердить?",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{registration.id}")],
                        [InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{registration.id}")]
                    ])
                )
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение админу {admin_id}: {e}")

        USER_DATA.pop(user_id, None)

# === Обработка callback weapon выбора ===
async def weapon_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user_data = USER_DATA[user_id]
    user_data['weapon_type'] = query.data.split("_", 1)[1]
    user_data['step'] = 'category'

    keyboard = [
        [InlineKeyboardButton("Начинающий", callback_data="cat_beginner")],
        [InlineKeyboardButton("Продвинутый", callback_data="cat_advanced")]
    ]
    await query.edit_message_text("Выберите категорию:", reply_markup=InlineKeyboardMarkup(keyboard))

# === Обработка callback категории ===
async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user_data = USER_DATA[user_id]
    user_data['category'] = "начинающий" if "beginner" in query.data else "продвинутый"
    user_data['step'] = 'age_group'

    keyboard = [
        [InlineKeyboardButton("Детская (6–12)", callback_data="age_kid")],
        [InlineKeyboardButton("Юношеская (13–17)", callback_data="age_teen")],
        [InlineKeyboardButton("Взрослая (18+)", callback_data="age_adult")]
    ]
    await query.edit_message_text("Выберите возрастную группу:", reply_markup=InlineKeyboardMarkup(keyboard))

# === Обработка callback возрастной группы ===
async def age_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user_data = USER_DATA[user_id]
    age_map = {"kid": "6–12", "teen": "13–17", "adult": "18+"}
    user_data['age_group'] = age_map[query.data.split("_")[1]]
    user_data['step'] = 'phone'

    await query.edit_message_text("Введите ваш номер телефона:")

# === Flask маршруты ===

@app.route("/")
def home():
    return "<h1>Бот для регистрации на турнир по фехтованию</h1>"

@app.route("/set_webhook", methods=["GET", "POST"])
def set_webhook():
    try:
        application = app.bot_app
        result = asyncio.run(application.bot.set_webhook(f"{WEBHOOK_URL}/webhook"))
        return jsonify({"status": "success", "result": str(result)})
    except Exception as e:
        logger.error(f"Ошибка установки вебхука: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/webhook", methods=["POST"])
def webhook():
    asyncio.run(app.bot_app.update_queue.put(Update.de_json(request.get_json(), app.bot_app.bot)))
    return "OK", 200

# === Админка (опционально) ===
@app.route("/admin")
def admin_panel():
    try:
        registrations = db.session.query(db.Registration).all()
        admins = db.session.query(db.Admin).all()

        regs_html = "<h2>Заявки</h2><ul>"
        for r in registrations:
            regs_html += f"<li>{r.full_name} — {r.weapon_type}, {r.status}</li>"
        regs_html += "</ul>"

        admins_html = "<h2>Администраторы</h2><ul>"
        for a in admins:
            admins_html += f"<li>{a.full_name or a.telegram_id} — {a.role}, активен: {a.is_active}</li>"
        admins_html += "</ul>"

        return f"<html><body>{regs_html}{admins_html}</body></html>"
    except Exception as e:
        logger.error(f"Ошибка админки: {e}")
        return f"<h1>Ошибка: {e}</h1>"

# === Инициализация бота ===
async def setup_bot():
    application = Application.builder().token(TOKEN).build()

    # Хендлеры
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(weapon_callback, pattern="^weapon_"))
    application.add_handler(CallbackQueryHandler(category_callback, pattern="^cat_"))
    application.add_handler(CallbackQueryHandler(age_callback, pattern="^age_"))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    return application

# === Запуск приложения ===
async def run_app():
    # Создаём бота
    app.bot_app = await setup_bot()
    logger.info("🤖 Бот инициализирован")

    # Запускаем бота в фоне
    await app.bot_app.initialize()
    await app.bot_app.start()
    logger.info("🟢 Бот запущен")

    # Только если нужно — установить вебхук
    if WEBHOOK_URL:
        await app.bot_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
        logger.info(f"🔗 Вебхук установлен на {WEBHOOK_URL}/webhook")

# === Запуск Flask + бота ===
if __name__ == "__main__":
    import threading

    def run_flask():
        port = int(os.getenv("PORT", 10000))
        app.run(host="0.0.0.0", port=port)

    # Запуск Flask в отдельном потоке
    threading.Thread(target=run_flask, daemon=True).start()

    # Запуск бота
    try:
        asyncio.run(run_app())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Бот остановлен")
    except Exception as e:
        logger.critical(f"💥 Критическая ошибка: {e}")
        raise
