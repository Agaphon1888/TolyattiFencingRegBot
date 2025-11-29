from flask import Flask, request, jsonify, render_template
from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
from telegram.error import RetryAfter, Unauthorized, TelegramError
import logging
import time
from config import Config
from database import Database

# === 1. Инициализация приложения и базы данных (должно быть в начале) ===
app = Flask(__name__)
app.config.from_object(Config)

# Инициализация базы данных ДО использования в декораторах
db = Database()

# === 2. Декораторы доступа ===
def admin_required(func):
    """Декоратор для проверки прав администратора"""
    def wrapper(update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        if not db.admin_manager.is_admin(user_id):
            update.message.reply_text("❌ У вас нет прав администратора.")
            return
        return func(update, context)
    return wrapper

def super_admin_required(func):
    """Декоратор для проверки прав супер-администратора"""
    def wrapper(update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        if not db.admin_manager.is_super_admin(user_id):
            update.message.reply_text("❌ У вас нет прав супер-администратора.")
            return
        return func(update, context)
    return wrapper

# === 3. Обработчики команд ===
@admin_required
def admin_stats(update: Update, context: CallbackContext):
    """Статистика для администратора"""
    stats = db.get_stats()
    admin_stats = db.admin_manager.get_admin_stats()

    message = f"""
📊 *Статистика системы:*

*Заявки:*
• Всего: {stats['total']}
• Ожидают: {stats['pending']}
• Подтверждены: {stats['confirmed']}
• Отклонены: {stats['rejected']}

*Администраторы:*
• Всего: {admin_stats['total']}
• Админы: {admin_stats['admins']}
• Модераторы: {admin_stats['moderators']}

*По оружию:*
"""

    for weapon, weapon_stats in stats['weapons'].items():
        message += f"• {weapon}: {weapon_stats['total']} (✓{weapon_stats['confirmed']} ⏳{weapon_stats['pending']})\n"

    update.message.reply_text(message, parse_mode='Markdown')

@super_admin_required
def admin_add(update: Update, context: CallbackContext):
    """Добавление администратора"""
    if not context.args:
        update.message.reply_text("Использование: /admin_add <telegram_id> <role=moderator>")
        return

    try:
        telegram_id = int(context.args[0])
        role = context.args[1] if len(context.args) > 1 else 'moderator'

        if role not in ['admin', 'moderator']:
            update.message.reply_text("Роль должна быть 'admin' или 'moderator'")
            return

        user = update.message.from_user
        result = db.admin_manager.add_admin(
            telegram_id=telegram_id,
            username=f"user_{telegram_id}",
            full_name="Неизвестно",
            role=role,
            created_by=user.id
        )

        if result:
            update.message.reply_text(f"✅ Администратор {telegram_id} добавлен с ролью '{role}'")
        else:
            update.message.reply_text("❌ Не удалось добавить администратора")

    except ValueError:
        update.message.reply_text("❌ Неверный формат ID")
    except Exception as e:
        logging.getLogger(__name__).exception("Ошибка при добавлении админа")
        update.message.reply_text("⚠️ Ошибка при добавлении администратора")

@super_admin_required
def admin_list(update: Update, context: CallbackContext):
    """Список администраторов"""
    admins = db.admin_manager.get_all_admins()

    if not admins:
        update.message.reply_text("Нет активных администраторов")
        return

    message = "👥 *Список администраторов:*\n\n"
    for admin in admins:
        status = "🟢" if admin.is_active else "🔴"
        message += f"{status} ID: {admin.telegram_id}\n"
        message += f"   Роль: {admin.role}\n"
        message += f"   Имя: {admin.full_name or 'Не указано'}\n"
        message += f"   С: {admin.created_at.strftime('%d.%m.%Y')}\n\n"

    update.message.reply_text(message, parse_mode='Markdown')

@admin_required
def admin_broadcast(update: Update, context: CallbackContext):
    """Рассылка сообщения всем участникам"""
    if not context.args:
        update.message.reply_text("Использование: /broadcast <сообщение>")
        return

    message = ' '.join(context.args)
    registrations = db.get_all_registrations()
    user_ids = set(reg.telegram_id for reg in registrations)

    bot = context.bot
    success = 0
    failed = 0

    for user_id in user_ids:
        try:
            bot.send_message(
                user_id,
                f"📢 *Объявление от организаторов:*\n\n{message}",
                parse_mode='Markdown'
            )
            success += 1
            time.sleep(0.05)  # Анти-Flood
        except Unauthorized:
            # Пользователь заблокировал бота
            logging.info(f"Пользователь {user_id} заблокировал бота")
            continue
        except RetryAfter as e:
            # Telegram требует подождать
            logging.warning(f"Flood limit. Sleep for {e.retry_after} seconds")
            time.sleep(e.retry_after)
            try:
                bot.send_message(user_id, message, parse_mode='Markdown')
                success += 1
            except Exception:
                failed += 1
        except Exception as e:
            logging.warning(f"Не удалось отправить {user_id}: {e}")
            failed += 1

    update.message.reply_text(f"✅ Рассылка завершена:\n• Успешно: {success}\n• Не удалось: {failed}")

# === 4. Диалог регистрации ===
NAME, WEAPON, CATEGORY, AGE, PHONE, EXPERIENCE, CONFIRM = range(7)

def start(update: Update, context: CallbackContext) -> int:
    """Начало диалога регистрации"""
    user = update.message.from_user
    context.user_data = context.user_data or {}  # Защита от None
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

# === 5. Настройка диспетчера (один раз) ===
def setup_dispatcher():
    """Настройка диспетчера"""
    bot = Bot(token=app.config['TELEGRAM_TOKEN'])
    dispatcher = Dispatcher(bot, None, workers=0)

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

    # Админ-команды
    dispatcher.add_handler(CommandHandler('admin_stats', admin_stats))
    dispatcher.add_handler(CommandHandler('admin_add', admin_add))
    dispatcher.add_handler(CommandHandler('admin_list', admin_list))
    dispatcher.add_handler(CommandHandler('broadcast', admin_broadcast))

    return dispatcher

# === 6. Глобальные bot и dispatcher (создаются один раз) ===
bot = Bot(token=app.config['TELEGRAM_TOKEN'])
dispatcher = setup_dispatcher()

# === 7. Flask маршруты ===
@app.route('/')
def home():
    return jsonify({"status": "Fencing Registration Bot is running!"})

@app.route('/admin')
def admin():
    """Админка для просмотра всех заявок"""
    registrations = db.get_all_registrations()
    return render_template('admin.html', registrations=registrations)

@app.route('/webhook', methods=['POST'])
def webhook():
    """Вебхук для Telegram"""
    update = Update.de_json(request.get_json(), bot)
    dispatcher.process_update(update)
    return 'ok'

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Установка вебхука"""
    webhook_url = app.config['WEBHOOK_URL']
    if not webhook_url:
        return "WEBHOOK_URL not configured", 400

    try:
        current = bot.get_webhook_info().url
        if current == webhook_url:
            return f"✅ Webhook уже установлен: {webhook_url}"

        result = bot.set_webhook(webhook_url)
        if result:
            return f"✅ Webhook успешно установлен на {webhook_url}"
        else:
            return "❌ Ошибка при установке вебхука", 500
    except Exception as e:
        logging.getLogger(__name__).exception("Ошибка при установке вебхука")
        return f"❌ Ошибка: {str(e)}", 500

# === 8. Запуск ===
if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    app.run(host='0.0.0.0', port=5000, debug=False)
