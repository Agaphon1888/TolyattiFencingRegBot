from flask import Flask, request, jsonify, render_template
from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
from telegram.error import RetryAfter, Unauthorized
import logging
import time
import os
from datetime import datetime

# === Настройка логирования ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Инициализация приложения ===
app = Flask(__name__)

# === Конфигурация ===
class Config:
    TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '')
    WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '') + '/webhook'
    ADMIN_TELEGRAM_IDS = os.environ.get('ADMIN_TELEGRAM_IDS', '')
    
    WEAPON_TYPES = ['Сабля', 'Шпага', 'Рапира']
    CATEGORIES = ['Юниоры', 'Взрослые', 'Ветераны']
    AGE_GROUPS = ['до 12 лет', '13-15 лет', '16-18 лет', '19+ лет']

# === Простая база данных в памяти ===
class SimpleDB:
    def __init__(self):
        self.registrations = []
        self.next_id = 1
        self.admins = []
        
        # Инициализация админов из переменной окружения
        admin_ids = Config.ADMIN_TELEGRAM_IDS
        if admin_ids:
            for admin_id in admin_ids.split(','):
                try:
                    self.admins.append(int(admin_id.strip()))
                except ValueError:
                    continue
    
    def add_registration(self, data):
        registration = {
            'id': self.next_id,
            'telegram_id': data.get('telegram_id'),
            'username': data.get('username'),
            'full_name': data.get('full_name'),
            'weapon_type': data.get('weapon_type'),
            'category': data.get('category'),
            'age_group': data.get('age_group'),
            'phone': data.get('phone'),
            'experience': data.get('experience'),
            'status': 'pending',
            'created_at': time.time()
        }
        self.registrations.append(registration)
        self.next_id += 1
        return registration
    
    def get_all_registrations(self):
        return self.registrations
    
    def get_user_registrations(self, telegram_id):
        return [r for r in self.registrations if r['telegram_id'] == telegram_id]
    
    def is_admin(self, telegram_id):
        return telegram_id in self.admins
    
    def get_stats(self):
        total = len(self.registrations)
        pending = len([r for r in self.registrations if r['status'] == 'pending'])
        confirmed = len([r for r in self.registrations if r['status'] == 'confirmed'])
        rejected = len([r for r in self.registrations if r['status'] == 'rejected'])
        
        weapon_stats = {}
        for reg in self.registrations:
            weapon = reg['weapon_type']
            if weapon not in weapon_stats:
                weapon_stats[weapon] = {'total': 0, 'pending': 0, 'confirmed': 0, 'rejected': 0}
            weapon_stats[weapon]['total'] += 1
            weapon_stats[weapon][reg['status']] += 1
        
        return {
            'total': total,
            'pending': pending,
            'confirmed': confirmed,
            'rejected': rejected,
            'weapons': weapon_stats
        }

# === Инициализация базы данных ===
db = SimpleDB()

# === Состояния для диалога ===
NAME, WEAPON, CATEGORY, AGE, PHONE, EXPERIENCE, CONFIRM = range(7)

# === Инициализация бота ===
bot = Bot(token=Config.TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# === Фильтры для шаблонов ===
@app.template_filter('timestamp_to_datetime')
def timestamp_to_datetime_filter(timestamp):
    """Конвертирует timestamp в datetime объект"""
    return datetime.fromtimestamp(timestamp)

@app.template_filter('datetimeformat')
def datetimeformat_filter(value, format='%d.%m.%Y %H:%M'):
    """Форматирует datetime объект в строку"""
    if isinstance(value, (int, float)):
        value = datetime.fromtimestamp(value)
    return value.strftime(format)

@app.template_filter('format_phone')
def format_phone_filter(phone):
    """Форматирует номер телефона"""
    if not phone:
        return ""
    # Убираем все нецифровые символы
    clean_phone = ''.join(filter(str.isdigit, str(phone)))
    if len(clean_phone) == 11 and clean_phone.startswith('7'):
        return f"+7 ({clean_phone[1:4]}) {clean_phone[4:7]}-{clean_phone[7:9]}-{clean_phone[9:11]}"
    elif len(clean_phone) == 10:
        return f"+7 ({clean_phone[0:3]}) {clean_phone[3:6]}-{clean_phone[6:8]}-{clean_phone[8:10]}"
    return phone

# === Команды бота ===
def start(update: Update, context: CallbackContext) -> int:
    user = update.effective_user
    context.user_data.clear()
    context.user_data['telegram_id'] = user.id
    context.user_data['username'] = user.username
    
    update.message.reply_text(
        "🤺 Добро пожаловать в систему регистрации на соревнования по фехтованию!\n\n"
        "Введите ваше ФИО (полностью):"
    )
    return NAME

def get_name(update: Update, context: CallbackContext) -> int:
    context.user_data['full_name'] = update.message.text
    
    keyboard = [[weapon] for weapon in Config.WEAPON_TYPES]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    
    update.message.reply_text(
        "Выберите вид оружия:",
        reply_markup=reply_markup
    )
    return WEAPON

def get_weapon(update: Update, context: CallbackContext) -> int:
    weapon = update.message.text
    if weapon not in Config.WEAPON_TYPES:
        update.message.reply_text("Пожалуйста, выберите вид оружия из предложенных вариантов.")
        return WEAPON
    
    context.user_data['weapon_type'] = weapon
    
    keyboard = [[category] for category in Config.CATEGORIES]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    
    update.message.reply_text(
        "Выберите категорию:",
        reply_markup=reply_markup
    )
    return CATEGORY

def get_category(update: Update, context: CallbackContext) -> int:
    category = update.message.text
    if category not in Config.CATEGORIES:
        update.message.reply_text("Пожалуйста, выберите категорию из предложенных вариантов.")
        return CATEGORY
    
    context.user_data['category'] = category
    
    keyboard = [[age] for age in Config.AGE_GROUPS]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    
    update.message.reply_text(
        "Выберите возрастную группу:",
        reply_markup=reply_markup
    )
    return AGE

def get_age(update: Update, context: CallbackContext) -> int:
    age_group = update.message.text
    if age_group not in Config.AGE_GROUPS:
        update.message.reply_text("Пожалуйста, выберите возрастную группу из предложенных вариантов.")
        return AGE
    
    context.user_data['age_group'] = age_group
    
    keyboard = [[KeyboardButton("📞 Отправить номер телефона", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    
    update.message.reply_text(
        "Поделитесь вашим номером телефона с помощью кнопки ниже:",
        reply_markup=reply_markup
    )
    return PHONE

def get_phone(update: Update, context: CallbackContext) -> int:
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text
    
    context.user_data['phone'] = phone
    
    update.message.reply_text(
        "Расскажите о вашем опыте в фехтовании (сколько лет занимаетесь, разряд, достижения и т.д.):"
    )
    return EXPERIENCE

def get_experience(update: Update, context: CallbackContext) -> int:
    context.user_data['experience'] = update.message.text
    
    # Формируем summary
    data = context.user_data
    summary = f"""
📋 *Проверьте ваши данные:*

*ФИО:* {data['full_name']}
*Оружие:* {data['weapon_type']}
*Категория:* {data['category']}
*Возрастная группа:* {data['age_group']}
*Телефон:* {data['phone']}
*Опыт:* {data['experience'][:100]}...

Всё верно?
"""
    
    keyboard = [["✅ Да, отправить заявку"], ["❌ Нет, заполнить заново"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    
    update.message.reply_text(summary, reply_markup=reply_markup, parse_mode='Markdown')
    return CONFIRM

def confirm_registration(update: Update, context: CallbackContext) -> int:
    if "да" in update.message.text.lower() or "отправить" in update.message.text:
        # Сохраняем заявку
        registration = db.add_registration(context.user_data)
        
        # Уведомляем админов
        for admin_id in db.admins:
            try:
                bot.send_message(
                    admin_id,
                    f"📝 *Новая заявка!*\n\n"
                    f"ФИО: {registration['full_name']}\n"
                    f"Оружие: {registration['weapon_type']}\n"
                    f"Категория: {registration['category']}\n"
                    f"Телефон: {registration['phone']}",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить админа {admin_id}: {e}")
        
        update.message.reply_text(
            "✅ *Ваша заявка отправлена!*\n\n"
            "Администратор свяжется с вами в ближайшее время для подтверждения участия.",
            reply_markup=None,
            parse_mode='Markdown'
        )
    else:
        update.message.reply_text("Давайте заполним заявку заново.")
        return start(update, context)
    
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Регистрация отменена.", reply_markup=None)
    return ConversationHandler.END

def stats_command(update: Update, context: CallbackContext):
    if not db.is_admin(update.effective_user.id):
        update.message.reply_text("❌ У вас нет прав для просмотра статистики.")
        return
    
    stats = db.get_stats()
    message = f"""
📊 *Статистика заявок:*

Всего: {stats['total']}
⏳ Ожидают: {stats['pending']}
✅ Подтверждены: {stats['confirmed']}
❌ Отклонены: {stats['rejected']}

*По оружию:*
"""
    for weapon, weapon_stats in stats['weapons'].items():
        message += f"• {weapon}: {weapon_stats['total']} (✓{weapon_stats['confirmed']})\n"
    
    update.message.reply_text(message, parse_mode='Markdown')

# === Настройка обработчиков ===
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

dispatcher.add_handler(conv_handler)
dispatcher.add_handler(CommandHandler('stats', stats_command))

# === Flask маршруты ===
@app.route('/')
def home():
    return jsonify({
        "status": "running", 
        "service": "TolyattiFencingRegBot",
        "registrations_count": len(db.registrations),
        "active_admins": len(db.admins),
        "version": "1.0"
    })

@app.route('/admin')
def admin_page():
    registrations = db.get_all_registrations()
    return render_template('admin.html', registrations=registrations)

@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok'

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    webhook_url = Config.WEBHOOK_URL
    if not webhook_url:
        return jsonify({"error": "WEBHOOK_URL не задан"}), 400
    
    try:
        result = bot.set_webhook(webhook_url)
        return jsonify({
            "status": "success" if result else "failed",
            "url": webhook_url
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "database_records": len(db.registrations),
        "telegram_bot": Config.TELEGRAM_TOKEN is not None,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/test_data')
def test_data():
    """Добавляет тестовые данные для демонстрации"""
    test_registrations = [
        {
            'telegram_id': 123456789,
            'username': 'test_user',
            'full_name': 'Иванов Иван Иванович',
            'weapon_type': 'Сабля',
            'category': 'Взрослые',
            'age_group': '19+ лет',
            'phone': '+79991234567',
            'experience': 'Занимаюсь 5 лет, имею 1 разряд',
            'status': 'pending'
        },
        {
            'telegram_id': 987654321,
            'username': 'test_user2',
            'full_name': 'Петрова Анна Сергеевна',
            'weapon_type': 'Рапира',
            'category': 'Юниоры',
            'age_group': '16-18 лет',
            'phone': '+79997654321',
            'experience': 'Занимаюсь 3 года, КМС',
            'status': 'confirmed'
        }
    ]
    
    for reg_data in test_registrations:
        db.add_registration(reg_data)
    
    return jsonify({
        "status": "test data added",
        "added_records": len(test_registrations),
        "total_records": len(db.registrations)
    })

# === Инициализация при запуске ===
def initialize():
    logger.info("🤖 Инициализация бота...")
    
    # Установка вебхука при запуске
    webhook_url = Config.WEBHOOK_URL
    if webhook_url and Config.TELEGRAM_TOKEN:
        try:
            bot.set_webhook(webhook_url)
            logger.info(f"✅ Вебхук установлен: {webhook_url}")
        except Exception as e:
            logger.error(f"❌ Ошибка установки вебхука: {e}")
    else:
        logger.warning("⚠️  Вебхук не установлен: проверьте TELEGRAM_TOKEN и WEBHOOK_URL")

# Инициализируем при импорте
initialize()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🚀 Запуск приложения на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
