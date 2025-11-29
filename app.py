from flask import Flask, request, jsonify, render_template_string
from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
import logging
import os
from config import Config
from database import Database

# === Инициализация приложения ===
app = Flask(__name__)
app.config.from_object(Config)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
db = Database()

# === Глобальные переменные для бота ===
updater = None
dispatcher = None

def init_bot():
    """Инициализация бота"""
    global updater, dispatcher
    try:
        updater = Updater(token=app.config['TELEGRAM_TOKEN'], use_context=True)
        dispatcher = updater.dispatcher
        
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
        
        # Админ-команды
        dispatcher.add_handler(CommandHandler('admin_stats', admin_stats))
        dispatcher.add_handler(CommandHandler('admin_add', admin_add))
        dispatcher.add_handler(CommandHandler('admin_list', admin_list))
        dispatcher.add_handler(CommandHandler('broadcast', admin_broadcast))
        dispatcher.add_handler(CommandHandler('admin_help', admin_help))
        
        # Обработчик неизвестных команд
        dispatcher.add_handler(MessageHandler(Filters.command, unknown_command))
        
        logger.info("Бот инициализирован успешно")
        return True
    except Exception as e:
        logger.error(f"Ошибка инициализации бота: {e}")
        return False

# === Состояния разговора ===
NAME, WEAPON, CATEGORY, AGE, PHONE, EXPERIENCE, CONFIRM = range(7)

# === Декораторы доступа ===
def admin_required(func):
    """Декоратор для проверки прав администратора"""
    def wrapper(update, context):
        user_id = update.message.from_user.id
        if not db.admin_manager.is_admin(user_id):
            update.message.reply_text("❌ У вас нет прав администратора.")
            return
        return func(update, context)
    return wrapper

def super_admin_required(func):
    """Декоратор для проверки прав супер-администратора"""
    def wrapper(update, context):
        user_id = update.message.from_user.id
        if not db.admin_manager.is_super_admin(user_id):
            update.message.reply_text("❌ У вас нет прав супер-администратора.")
            return
        return func(update, context)
    return wrapper

# === Обработчики команд администратора ===
@admin_required
def admin_stats(update, context):
    """Статистика для администратора"""
    try:
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
        logger.info(f"Админ {update.message.from_user.id} запросил статистику")
        
    except Exception as e:
        logger.error(f"Ошибка в admin_stats: {e}")
        update.message.reply_text("❌ Ошибка при получении статистики")

@super_admin_required
def admin_add(update, context):
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
            logger.info(f"Админ {user.id} добавил администратора {telegram_id} с ролью {role}")
        else:
            update.message.reply_text("❌ Не удалось добавить администратора (возможно, уже существует)")

    except ValueError:
        update.message.reply_text("❌ Неверный формат ID")
    except Exception as e:
        logger.error(f"Ошибка при добавлении админа: {e}")
        update.message.reply_text("⚠️ Ошибка при добавлении администратора")

@super_admin_required
def admin_list(update, context):
    """Список администраторов"""
    try:
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
        logger.info(f"Админ {update.message.from_user.id} запросил список администраторов")
        
    except Exception as e:
        logger.error(f"Ошибка в admin_list: {e}")
        update.message.reply_text("❌ Ошибка при получении списка администраторов")

@admin_required
def admin_broadcast(update, context):
    """Рассылка сообщения всем участникам"""
    if not context.args:
        update.message.reply_text("Использование: /broadcast <сообщение>")
        return

    try:
        message = ' '.join(context.args)
        registrations = db.get_all_registrations()
        user_ids = set(reg.telegram_id for reg in registrations)

        success = 0
        failed = 0

        update.message.reply_text("🔄 Начинаю рассылку...")

        for user_id in user_ids:
            try:
                context.bot.send_message(
                    user_id,
                    f"📢 *Объявление от организаторов:*\n\n{message}",
                    parse_mode='Markdown'
                )
                success += 1
            except Exception as e:
                logger.warning(f"Не удалось отправить сообщение {user_id}: {e}")
                failed += 1

        update.message.reply_text(
            f"✅ Рассылка завершена:\n• Успешно: {success}\n• Не удалось: {failed}"
        )
        logger.info(f"Админ {update.message.from_user.id} сделал рассылку: успешно {success}, неудачно {failed}")
        
    except Exception as e:
        logger.error(f"Ошибка в рассылке: {e}")
        update.message.reply_text("❌ Ошибка при рассылке сообщений")

@admin_required
def admin_help(update, context):
    """Справка по командам администратора"""
    help_text = """
🛠️ *Команды администратора:*

*/admin_stats* - статистика системы
*/admin_list* - список администраторов
*/broadcast <сообщение>* - рассылка участникам
*/admin_help* - эта справка

*Только для супер-админов:*
*/admin_add <telegram_id> <role>* - добавить админа
*/admin_list* - список всех админов
"""
    update.message.reply_text(help_text, parse_mode='Markdown')

# === Диалог регистрации ===
def start(update, context):
    """Начало диалога регистрации"""
    try:
        user = update.message.from_user
        context.user_data['telegram_id'] = user.id
        context.user_data['username'] = user.username
        
        # Проверяем есть ли активные заявки
        existing_registrations = db.get_user_registrations(user.id)
        if existing_registrations:
            pending = [r for r in existing_registrations if r.status == 'pending']
            if pending:
                update.message.reply_text(
                    '⚠️ У вас есть незавершенные заявки. '
                    'Вы можете просмотреть их с помощью /myregistrations\n\n'
                    'Хотите создать новую заявку? Введите ваше ФИО:'
                )
                return NAME

        update.message.reply_text(
            '🤺 *Добро пожаловать в систему регистрации на соревнования по фехтованию!*\n\n'
            'Для начала регистрации введите ваше *ФИО*:',
            parse_mode='Markdown'
        )
        logger.info(f"Пользователь {user.id} начал регистрацию")
        return NAME
        
    except Exception as e:
        logger.error(f"Ошибка в start: {e}")
        update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")
        return ConversationHandler.END

def get_name(update, context):
    """Получение ФИО"""
    try:
        context.user_data['full_name'] = update.message.text

        keyboard = [[weapon] for weapon in Config.WEAPON_TYPES]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

        update.message.reply_text(
            'Отлично! Теперь выберите *вид оружия*:',
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return WEAPON
        
    except Exception as e:
        logger.error(f"Ошибка в get_name: {e}")
        update.message.reply_text("❌ Ошибка. Попробуйте снова.")
        return NAME

def get_weapon(update, context):
    """Получение типа оружия"""
    try:
        weapon = update.message.text
        if weapon not in Config.WEAPON_TYPES:
            update.message.reply_text('Пожалуйста, выберите тип оружия из предложенных вариантов.')
            return WEAPON

        context.user_data['weapon_type'] = weapon

        keyboard = [[category] for category in Config.CATEGORIES]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

        update.message.reply_text(
            'Выберите *категорию*:',
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return CATEGORY
        
    except Exception as e:
        logger.error(f"Ошибка в get_weapon: {e}")
        update.message.reply_text("❌ Ошибка. Попробуйте снова.")
        return WEAPON

def get_category(update, context):
    """Получение категории"""
    try:
        category = update.message.text
        if category not in Config.CATEGORIES:
            update.message.reply_text('Пожалуйста, выберите категорию из предложенных вариантов.')
            return CATEGORY

        context.user_data['category'] = category

        keyboard = [[age_group] for age_group in Config.AGE_GROUPS]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

        update.message.reply_text(
            'Выберите *возрастную группу*:',
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return AGE
        
    except Exception as e:
        logger.error(f"Ошибка в get_category: {e}")
        update.message.reply_text("❌ Ошибка. Попробуйте снова.")
        return CATEGORY

def get_age(update, context):
    """Получение возрастной группы"""
    try:
        age_group = update.message.text
        if age_group not in Config.AGE_GROUPS:
            update.message.reply_text('Пожалуйста, выберите возрастную группу из предложенных вариантов.')
            return AGE

        context.user_data['age_group'] = age_group

        contact_keyboard = [[KeyboardButton("📞 Поделиться контактом", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(contact_keyboard, one_time_keyboard=True)

        update.message.reply_text(
            'Теперь нам нужен ваш *номер телефона*.\n\n'
            'Вы можете отправить его вручную или использовать кнопку ниже:',
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return PHONE
        
    except Exception as e:
        logger.error(f"Ошибка в get_age: {e}")
        update.message.reply_text("❌ Ошибка. Попробуйте снова.")
        return AGE

def get_phone(update, context):
    """Получение телефона"""
    try:
        if update.message.contact:
            phone = update.message.contact.phone_number
        else:
            phone = update.message.text

        context.user_data['phone'] = phone

        update.message.reply_text(
            'Расскажите кратко о вашем *опыте в фехтовании*:\n\n'
            '(сколько лет занимаетесь, разряд, участия в соревнованиях)',
            parse_mode='Markdown'
        )
        return EXPERIENCE
        
    except Exception as e:
        logger.error(f"Ошибка в get_phone: {e}")
        update.message.reply_text("❌ Ошибка. Попробуйте снова.")
        return PHONE

def get_experience(update, context):
    """Получение информации об опыте"""
    try:
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
        
    except Exception as e:
        logger.error(f"Ошибка в get_experience: {e}")
        update.message.reply_text("❌ Ошибка. Попробуйте снова.")
        return EXPERIENCE

def confirm_registration(update, context):
    """Подтверждение и сохранение регистрации"""
    try:
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

            registration = db.add_registration(registration_data)

            update.message.reply_text(
                '🎉 *Ваша заявка успешно отправлена!*\n\n'
                'Мы свяжемся с вами для подтверждения участия. '
                'Следите за обновлениями в этом чате.\n\n'
                'Для просмотра ваших заявок используйте /myregistrations',
                parse_mode='Markdown',
                reply_markup=None
            )
            logger.info(f"Новая заявка #{registration.id} от пользователя {context.user_data['telegram_id']}")
        else:
            update.message.reply_text(
                'Давайте начнем регистрацию заново. Введите ваше ФИО:',
                reply_markup=None
            )
            return NAME

        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Ошибка в confirm_registration: {e}")
        update.message.reply_text("❌ Ошибка при сохранении заявки. Попробуйте позже.")
        return ConversationHandler.END

def cancel(update, context):
    """Отмена регистрации"""
    user_id = update.message.from_user.id
    context.user_data.clear()
    
    update.message.reply_text(
        '❌ Регистрация отменена.\n\n'
        'Если захотите зарегистрироваться, отправьте /start\n'
        'Для просмотра ваших заявок - /myregistrations',
        reply_markup=None
    )
    logger.info(f"Пользователь {user_id} отменил регистрацию")
    return ConversationHandler.END

def view_registrations(update, context):
    """Просмотр своих заявок"""
    try:
        telegram_id = update.message.from_user.id
        registrations = db.get_user_registrations(telegram_id)

        if not registrations:
            update.message.reply_text('📭 У вас нет активных заявок.')
            return

        message = "📝 *Ваши заявки:*\n\n"
        for reg in registrations:
            status_emoji = {
                'pending': '⏳',
                'confirmed': '✅', 
                'rejected': '❌'
            }.get(reg.status, '📄')
            
            message += f"""
{status_emoji} *Заявка #{reg.id}*
*ФИО:* {reg.full_name}
*Оружие:* {reg.weapon_type}
*Категория:* {reg.category}
*Возрастная группа:* {reg.age_group}
*Статус:* {reg.status}
*Дата:* {reg.created_at.strftime('%d.%m.%Y')}
---
"""

        update.message.reply_text(message, parse_mode='Markdown')
        logger.info(f"Пользователь {telegram_id} запросил список заявок")
        
    except Exception as e:
        logger.error(f"Ошибка в view_registrations: {e}")
        update.message.reply_text("❌ Ошибка при получении заявок.")

def unknown_command(update, context):
    """Обработка неизвестных команд"""
    update.message.reply_text(
        "❌ Неизвестная команда.\n\n"
        "*Доступные команды:*\n"
        "/start - начать регистрацию\n"
        "/myregistrations - мои заявки\n" 
        "/cancel - отмена регистрации\n"
        "/admin_help - справка для админов",
        parse_mode='Markdown'
    )

# === HTML шаблон для админки ===
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
        .status-pending { color: orange; font-weight: bold; }
        .status-confirmed { color: green; font-weight: bold; }
        .status-rejected { color: red; font-weight: bold; }
        .filters { margin: 20px 0; padding: 10px; background: #f5f5f5; }
        .stats { margin: 10px 0; padding: 10px; background: #e8f4fd; border-radius: 5px; }
        .filter-active { font-weight: bold; color: #0066cc; }
    </style>
</head>
<body>
    <h1>🤺 Заявки на соревнования по фехтованию</h1>
    
    <div class="stats">
        <strong>Статистика:</strong><br>
        Всего заявок: {{ total_count }} | 
        Ожидают: {{ pending_count }} | 
        Подтверждены: {{ confirmed_count }} | 
        Отклонены: {{ rejected_count }}
    </div>
    
    <div class="filters">
        <strong>Фильтры по статусу:</strong>
        <a href="?status=all" {% if current_filter == 'all' %}class="filter-active"{% endif %}>Все</a> |
        <a href="?status=pending" {% if current_filter == 'pending' %}class="filter-active"{% endif %}>Ожидают ({{ pending_count }})</a> |
        <a href="?status=confirmed" {% if current_filter == 'confirmed' %}class="filter-active"{% endif %}>Подтверждены ({{ confirmed_count }})</a> |
        <a href="?status=rejected" {% if current_filter == 'rejected' %}class="filter-active"{% endif %}>Отклонены ({{ rejected_count }})</a>
    </div>
    
    {% if registrations %}
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
                <th>Дата регистрации</th>
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
    {% else %}
    <p>Нет заявок, соответствующих выбранному фильтру.</p>
    {% endif %}
</body>
</html>
"""

# === Flask маршруты ===
@app.route('/')
def home():
    return jsonify({
        "status": "Fencing Registration Bot is running!",
        "version": "1.0",
        "admin_panel": "/admin"
    })

@app.route('/admin')
def admin():
    """Админка для просмотра всех заявок"""
    try:
        status_filter = request.args.get('status', 'all')
        all_registrations = db.get_all_registrations()
        
        if status_filter != 'all':
            registrations = [r for r in all_registrations if r.status == status_filter]
        else:
            registrations = all_registrations
        
        # Статистика
        total_count = len(all_registrations)
        pending_count = len([r for r in all_registrations if r.status == 'pending'])
        confirmed_count = len([r for r in all_registrations if r.status == 'confirmed'])
        rejected_count = len([r for r in all_registrations if r.status == 'rejected'])
        
        return render_template_string(
            ADMIN_TEMPLATE, 
            registrations=registrations,
            total_count=total_count,
            pending_count=pending_count,
            confirmed_count=confirmed_count,
            rejected_count=rejected_count,
            current_filter=status_filter
        )
        
    except Exception as e:
        logger.error(f"Ошибка в админке: {e}")
        return f"Ошибка при загрузке админки: {str(e)}", 500

@app.route('/webhook', methods=['POST'])
def webhook():
    """Вебхук для Telegram"""
    if updater is None:
        return 'Bot not initialized', 500
        
    try:
        update = Update.de_json(request.get_json(force=True), updater.bot)
        dispatcher.process_update(update)
        return 'ok'
    except Exception as e:
        logger.error(f"Ошибка в обработке вебхука: {e}")
        return 'error', 500

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Установка вебхука"""
    try:
        webhook_url = app.config['WEBHOOK_URL']
        if not webhook_url:
            return "WEBHOOK_URL not configured", 400

        if updater is None:
            return "Bot not initialized", 500

        result = updater.bot.set_webhook(webhook_url)
        if result:
            logger.info(f"Webhook установлен: {webhook_url}")
            return f"✅ Webhook успешно установлен на {webhook_url}"
        else:
            logger.error("Ошибка при установке вебхука")
            return "❌ Ошибка при установке вебхука", 500
            
    except Exception as e:
        logger.exception("Ошибка при установке вебхука")
        return f"❌ Ошибка: {str(e)}", 500

@app.route('/health')
def health_check():
    """Проверка здоровья приложения"""
    try:
        # Проверяем подключение к базе данных
        db.session.execute('SELECT 1')
        return jsonify({
            "status": "healthy",
            "database": "connected",
            "bot_initialized": updater is not None
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500

# === Инициализация при запуске ===
def initialize():
    """Инициализация приложения"""
    if init_bot():
        logger.info("Бот успешно инициализирован")
        
        # Устанавливаем вебхук при старте
        webhook_url = app.config['WEBHOOK_URL']
        if webhook_url:
            try:
                updater.bot.set_webhook(webhook_url)
                logger.info(f"Webhook установлен на: {webhook_url}")
            except Exception as e:
                logger.error(f"Ошибка установки вебхука: {e}")
    else:
        logger.error("Не удалось инициализировать бота")

# Инициализируем при запуске
initialize()

# === Запуск приложения ===
if __name__ == '__main__':
    logger.info("Запуск приложения Fencing Registration Bot")
    app.run(host='0.0.0.0', port=5000, debug=False)
