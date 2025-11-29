from flask import Flask, request, jsonify, render_template_string
from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
import logging
import os
from database import Database
from config import Config

# Состояния разговора
NAME, WEAPON, CATEGORY, AGE, PHONE, EXPERIENCE, CONFIRM = range(7)

app = Flask(__name__)
app.config.from_object(Config)

# Инициализация базы данных
db = Database()

# HTML шаблон для админки
ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Регистрации на соревнования</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .status-pending { color: orange; }
        .status-confirmed { color: green; }
    </style>
</head>
<body>
    <h1>Заявки на соревнования по фехтованию</h1>
    <p>Всего заявок: {{ registrations|length }}</p>
    
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>Имя</th>
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
                <td>{{ reg.experience or 'Не указан' }}</td>
                <td class="status-{{ reg.status }}">{{ reg.status }}</td>
                <td>{{ reg.created_at.strftime('%d.%m.%Y %H:%M') }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
"""

def start(update: Update, context: CallbackContext) -> int:
    """Начало диалога регистрации"""
    user = update.message.from_user
    context.user_data['telegram_id'] = user.id
    context.user_data['username'] = user.username
    
    update.message.reply_text(
        'Добро пожаловать в систему регистрации на соревнования по фехтованию!\n\n'
        'Для начала регистрации введите ваше ФИО:'
    )
    return NAME

def get_name(update: Update, context: CallbackContext) -> int:
    """Получение ФИО"""
    context.user_data['full_name'] = update.message.text
    
    # Создаем клавиатуру с типами оружия
    keyboard = [[weapon] for weapon in Config.WEAPON_TYPES]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    
    update.message.reply_text(
        'Отлично! Теперь выберите вид оружия:',
        reply_markup=reply_markup
    )
    return WEAPON

def get_weapon(update: Update, context: CallbackContext) -> int:
    """Получение типа оружия"""
    weapon = update.message.text
    if weapon not in Config.WEAPON_TYPES:
        update.message.reply_text('Пожалуйста, выберите тип оружия из предложенных вариантов.')
        return WEAPON
    
    context.user_data['weapon_type'] = weapon
    
    # Клавиатура для категорий
    keyboard = [[category] for category in Config.CATEGORIES]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    
    update.message.reply_text(
        'Выберите категорию:',
        reply_markup=reply_markup
    )
    return CATEGORY

def get_category(update: Update, context: CallbackContext) -> int:
    """Получение категории"""
    category = update.message.text
    if category not in Config.CATEGORIES:
        update.message.reply_text('Пожалуйста, выберите категорию из предложенных вариантов.')
        return CATEGORY
    
    context.user_data['category'] = category
    
    # Клавиатура для возрастных групп
    keyboard = [[age_group] for age_group in Config.AGE_GROUPS]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    
    update.message.reply_text(
        'Выберите возрастную группу:',
        reply_markup=reply_markup
    )
    return AGE

def get_age(update: Update, context: CallbackContext) -> int:
    """Получение возрастной группы"""
    age_group = update.message.text
    if age_group not in Config.AGE_GROUPS:
        update.message.reply_text('Пожалуйста, выберите возрастную группу из предложенных вариантов.')
        return AGE
    
    context.user_data['age_group'] = age_group
    
    # Предлагаем поделиться контактом
    contact_keyboard = [[KeyboardButton("📞 Поделиться контактом", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(contact_keyboard, one_time_keyboard=True)
    
    update.message.reply_text(
        'Теперь нам нужен ваш номер телефона. '
        'Вы можете отправить его вручную или использовать кнопку ниже:',
        reply_markup=reply_markup
    )
    return PHONE

def get_phone(update: Update, context: CallbackContext) -> int:
    """Получение телефона"""
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text
    
    context.user_data['phone'] = phone
    
    update.message.reply_text(
        'Расскажите кратко о вашем опыте в фехтовании '
        '(сколько лет занимаетесь, разряд, участия в соревнованиях):'
    )
    return EXPERIENCE

def get_experience(update: Update, context: CallbackContext) -> int:
    """Получение информации об опыте"""
    context.user_data['experience'] = update.message.text
    
    # Показываем сводку для подтверждения
    data = context.user_data
    summary = f"""
📋 *Проверьте ваши данные:*

*ФИО:* {data['full_name']}
*Оружие:* {data['weapon_type']}
*Категория:* {data['category']}
*Возрастная группа:* {data['age_group']}
*Телефон:* {data['phone']}
*Опыт:* {data['experience']}

Всё верно?
"""
    
    keyboard = [['✅ Да, отправить заявку', '❌ Нет, исправить']]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    
    update.message.reply_text(summary, parse_mode='Markdown', reply_markup=reply_markup)
    return CONFIRM

def confirm_registration(update: Update, context: CallbackContext) -> int:
    """Подтверждение и сохранение регистрации"""
    if update.message.text == '✅ Да, отправить заявку':
        # Сохраняем в базу данных
        registration_data = {
            'telegram_id': context.user_data['telegram_id'],
            'username': context.user_data.get('username'),
            'full_name': context.user_data['full_name'],
            'weapon_type': context.user_data['weapon_type'],
            'category': context.user_data['category'],
            'age_group': context.user_data['age_group'],
            'phone': context.user_data['phone'],
            'experience': context.user_data['experience']
        }
        
        db.add_registration(registration_data)
        
        update.message.reply_text(
            '🎉 *Ваша заявка успешно отправлена!*\n\n'
            'Мы свяжемся с вами для подтверждения участия. '
            'Следите за обновлениями в этом чате.',
            parse_mode='Markdown',
            reply_markup=None
        )
    else:
        update.message.reply_text(
            'Давайте начнем регистрацию заново. Введите ваше ФИО:',
            reply_markup=None
        )
        return NAME
    
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    """Отмена регистрации"""
    update.message.reply_text(
        'Регистрация отменена. Если захотите зарегистрироваться, '
        'просто отправьте /start',
        reply_markup=None
    )
    return ConversationHandler.END

def view_registrations(update: Update, context: CallbackContext):
    """Просмотр своих заявок"""
    telegram_id = update.message.from_user.id
    registrations = db.get_user_registrations(telegram_id)
    
    if not registrations:
        update.message.reply_text('У вас нет активных заявок.')
        return
    
    message = "📝 *Ваши заявки:*\n\n"
    for reg in registrations:
        message += f"""
*Заявка #{reg.id}*
ФИО: {reg.full_name}
Оружие: {reg.weapon_type}
Категория: {reg.category}
Статус: {reg.status}
Дата: {reg.created_at.strftime('%d.%m.%Y')}
---
"""
    
    update.message.reply_text(message, parse_mode='Markdown')

def setup_dispatcher():
    """Настройка диспетчера"""
    bot = Bot(token=app.config['TELEGRAM_TOKEN'])
    dispatcher = Dispatcher(bot, None, workers=0)
    
    # Обработчик диалога регистрации
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
    dispatcher.add_handler(CommandHandler('myregistrations', view_registrations))
    
    return dispatcher

@app.route('/')
def home():
    return jsonify({"status": "Fencing Registration Bot is running!"})

@app.route('/admin')
def admin():
    """Админка для просмотра всех заявок"""
    registrations = db.get_all_registrations()
    return render_template_string(ADMIN_TEMPLATE, registrations=registrations)

@app.route('/webhook', methods=['POST'])
def webhook():
    """Вебхук для Telegram"""
    dispatcher = setup_dispatcher()
    update = Update.de_json(request.get_json(), dispatcher.bot)
    dispatcher.process_update(update)
    return 'ok'

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Установка вебхука"""
    bot = Bot(token=app.config['TELEGRAM_TOKEN'])
    webhook_url = app.config['WEBHOOK_URL']
    
    if not webhook_url:
        return "WEBHOOK_URL not configured", 400
    
    try:
        bot.set_webhook(webhook_url)
        return f"Webhook set to {webhook_url}"
    except Exception as e:
        return f"Error setting webhook: {str(e)}", 500

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app.run(host='0.0.0.0', port=5000)
