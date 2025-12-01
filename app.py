from flask import Flask, request, jsonify, render_template, g
from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
import logging
import time
import secrets
from datetime import datetime, timedelta
from contextlib import contextmanager

# Импорт конфигурации
from config import config
from database import init_db, db_session, Registration, Admin

# === Настройка логирования ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, config.LOG_LEVEL)
)
logger = logging.getLogger(__name__)

# === Валидация конфигурации ===
try:
    config.validate_config()
    logger.info("✅ Конфигурация проверена успешно")
except ValueError as e:
    logger.error(f"❌ Ошибка конфигурации: {e}")
    if not config.DEBUG:
        raise

# === Инициализация приложения ===
app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# === Инициализация базы данных ===
init_db()

# === Состояния для диалога ===
NAME, WEAPON, CATEGORY, AGE, PHONE, EXPERIENCE, CONFIRM = range(7)

# === Инициализация бота ===
bot = None
dispatcher = None

try:
    if config.TELEGRAM_TOKEN:
        bot = Bot(token=config.TELEGRAM_TOKEN)
        dispatcher = Dispatcher(bot, None, workers=0)
        logger.info("✅ Telegram bot инициализирован")
    else:
        logger.warning("⚠️ TELEGRAM_TOKEN не установлен")
except Exception as e:
    logger.error(f"❌ Ошибка инициализации бота: {e}")

# === Хранилище временных токенов ===
# В production рекомендуется использовать Redis вместо словаря
admin_tokens = {}

def generate_admin_token(telegram_id):
    """Генерирует токен для доступа к админ-панели"""
    token = secrets.token_urlsafe(32)
    admin_tokens[telegram_id] = {
        'token': token,
        'expires': time.time() + config.ADMIN_TOKEN_EXPIRE
    }
    logger.info(f"Сгенерирован токен для admin_id={telegram_id}")
    return token

def validate_admin_token(token):
    """Проверяет валидность токена и возвращает telegram_id"""
    for telegram_id, data in admin_tokens.items():
        if data['token'] == token and data['expires'] > time.time():
            # Обновляем время жизни токена
            data['expires'] = time.time() + config.ADMIN_TOKEN_EXPIRE
            return telegram_id
    return None

def cleanup_expired_tokens():
    """Очищает просроченные токены"""
    current_time = time.time()
    expired = [uid for uid, data in admin_tokens.items() if data['expires'] <= current_time]
    for uid in expired:
        del admin_tokens[uid]
    if expired:
        logger.info(f"Очищено {len(expired)} просроченных токенов")

@contextmanager
def get_db():
    """Контекстный менеджер для работы с базой данных"""
    session = db_session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Ошибка базы данных: {e}")
        raise
    finally:
        session.close()

def is_admin(telegram_id):
    """Проверяет, является ли пользователь администратором"""
    with get_db() as session:
        admin = session.query(Admin).filter_by(
            telegram_id=telegram_id,
            is_active=True
        ).first()
        return admin is not None

def is_super_admin(telegram_id):
    """Проверяет, является ли пользователь супер-админом"""
    with get_db() as session:
        admin = session.query(Admin).filter_by(
            telegram_id=telegram_id,
            role='admin',
            is_active=True
        ).first()
        return admin is not None

# === Декораторы для проверки прав ===
def admin_required(func):
    def wrapper(update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        if not is_admin(user_id):
            update.message.reply_text("❌ У вас нет прав администратора.")
            return
        return func(update, context)
    return wrapper

def super_admin_required(func):
    def wrapper(update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        if not is_super_admin(user_id):
            update.message.reply_text("❌ Требуются права супер-администратора.")
            return
        return func(update, context)
    return wrapper

# === Команды бота ===
def start(update: Update, context: CallbackContext) -> int:
    user = update.effective_user
    context.user_data.clear()
    context.user_data['telegram_id'] = user.id
    context.user_data['username'] = user.username
    
    # Если пользователь админ, показываем админ-меню
    if is_admin(user.id):
        keyboard = [
            ["📊 Статистика", "📋 Список заявок"],
            ["⏳ Ожидающие", "✅ Подтвержденные"],
            ["📝 Новая регистрация", "🌐 Админ-панель"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        update.message.reply_text(
            "👑 Панель администратора\nВыберите действие:",
            reply_markup=reply_markup
        )
        return ConversationHandler.END
    else:
        # Обычный пользователь - начинаем регистрацию
        update.message.reply_text(
            "🤺 Добро пожаловать в систему регистрации на соревнования по фехтованию!\n\n"
            "Введите ваше ФИО (полностью):"
        )
        return NAME

def get_name(update: Update, context: CallbackContext) -> int:
    context.user_data['full_name'] = update.message.text
    
    keyboard = [[weapon] for weapon in config.WEAPON_TYPES]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    
    update.message.reply_text(
        "Выберите вид оружия:",
        reply_markup=reply_markup
    )
    return WEAPON

def get_weapon(update: Update, context: CallbackContext) -> int:
    weapon = update.message.text
    if weapon not in config.WEAPON_TYPES:
        update.message.reply_text("Пожалуйста, выберите вид оружия из предложенных вариантов.")
        return WEAPON
    
    context.user_data['weapon_type'] = weapon
    
    keyboard = [[category] for category in config.CATEGORIES]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    
    update.message.reply_text(
        "Выберите категорию:",
        reply_markup=reply_markup
    )
    return CATEGORY

def get_category(update: Update, context: CallbackContext) -> int:
    category = update.message.text
    if category not in config.CATEGORIES:
        update.message.reply_text("Пожалуйста, выберите категорию из предложенных вариантов.")
        return CATEGORY
    
    context.user_data['category'] = category
    
    keyboard = [[age] for age in config.AGE_GROUPS]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    
    update.message.reply_text(
        "Выберите возрастную группу:",
        reply_markup=reply_markup
    )
    return AGE

def get_age(update: Update, context: CallbackContext) -> int:
    age_group = update.message.text
    if age_group not in config.AGE_GROUPS:
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
        # Сохраняем заявку в базу данных
        with get_db() as session:
            registration = Registration(
                telegram_id=context.user_data['telegram_id'],
                username=context.user_data.get('username', ''),
                full_name=context.user_data['full_name'],
                weapon_type=context.user_data['weapon_type'],
                category=context.user_data['category'],
                age_group=context.user_data['age_group'],
                phone=context.user_data['phone'],
                experience=context.user_data['experience'],
                status='pending',
                created_at=datetime.utcnow()
            )
            session.add(registration)
            session.flush()  # Получаем ID без коммита
            registration_id = registration.id
        
        # Уведомляем админов
        with get_db() as session:
            admins = session.query(Admin).filter_by(is_active=True).all()
        
        admin_message = (
            f"📝 *Новая заявка!*\n\n"
            f"ID: {registration_id}\n"
            f"ФИО: {context.user_data['full_name']}\n"
            f"Оружие: {context.user_data['weapon_type']}\n"
            f"Категория: {context.user_data['category']}\n"
            f"Телефон: {context.user_data['phone']}\n\n"
            f"Подтвердить: /confirm_{registration_id}\n"
            f"Отклонить: /reject_{registration_id}"
        )
        
        for admin in admins:
            try:
                bot.send_message(
                    admin.telegram_id,
                    admin_message,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить админа {admin.telegram_id}: {e}")
        
        # Коммитим после отправки уведомлений
        with get_db() as session:
            session.commit()
        
        update.message.reply_text(
            "✅ *Ваша заявка отправлена!*\n\n"
            "Администратор свяжется с вами в ближайшее время для подтверждения участия. "
            "Вы можете проверить статус своей заявки с помощью команды /my_registrations",
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

# === Админские команды ===
@admin_required
def admin_stats(update: Update, context: CallbackContext):
    with get_db() as session:
        total = session.query(Registration).count()
        pending = session.query(Registration).filter_by(status='pending').count()
        confirmed = session.query(Registration).filter_by(status='confirmed').count()
        rejected = session.query(Registration).filter_by(status='rejected').count()
        
        # Статистика по оружию
        weapon_stats = {}
        for weapon in config.WEAPON_TYPES:
            weapon_total = session.query(Registration).filter_by(weapon_type=weapon).count()
            weapon_confirmed = session.query(Registration).filter_by(
                weapon_type=weapon, status='confirmed').count()
            weapon_stats[weapon] = {'total': weapon_total, 'confirmed': weapon_confirmed}
    
    message = (
        f"📊 *Статистика заявок:*\n\n"
        f"*Всего:* {total}\n"
        f"⏳ *Ожидают:* {pending}\n"
        f"✅ *Подтверждены:* {confirmed}\n"
        f"❌ *Отклонены:* {rejected}\n\n"
        f"*По оружию:*\n"
    )
    
    for weapon, stats in weapon_stats.items():
        message += f"• {weapon}: {stats['total']} (✓{stats['confirmed']})\n"
    
    update.message.reply_text(message, parse_mode='Markdown')

@admin_required
def admin_list(update: Update, context: CallbackContext):
    with get_db() as session:
        registrations = session.query(Registration).order_by(
            Registration.created_at.desc()).limit(10).all()
    
    if not registrations:
        update.message.reply_text("📝 Нет заявок.")
        return
    
    message = "📋 *Последние 10 заявок:*\n\n"
    for reg in registrations:
        status_icon = "⏳" if reg.status == 'pending' else "✅" if reg.status == 'confirmed' else "❌"
        message += f"{status_icon} *ID {reg.id}:* {reg.full_name} - {reg.weapon_type} - {reg.status}\n"
    
    update.message.reply_text(message, parse_mode='Markdown')

@admin_required
def admin_pending(update: Update, context: CallbackContext):
    with get_db() as session:
        pending = session.query(Registration).filter_by(
            status='pending').order_by(Registration.created_at.desc()).limit(10).all()
    
    if not pending:
        update.message.reply_text("⏳ Нет ожидающих заявок.")
        return
    
    message = "⏳ *Ожидающие заявки:*\n\n"
    for reg in pending:
        message += f"*ID {reg.id}:* {reg.full_name}\n"
        message += f"Оружие: {reg.weapon_type}\n"
        message += f"Телефон: {reg.phone}\n"
        message += f"Подтвердить: /confirm_{reg.id}\n"
        message += f"Отклонить: /reject_{reg.id}\n\n"
    
    update.message.reply_text(message, parse_mode='Markdown')

@admin_required
def admin_confirmed(update: Update, context: CallbackContext):
    with get_db() as session:
        confirmed = session.query(Registration).filter_by(
            status='confirmed').order_by(Registration.created_at.desc()).limit(10).all()
    
    if not confirmed:
        update.message.reply_text("✅ Нет подтвержденных заявок.")
        return
    
    message = "✅ *Подтвержденные заявки:*\n\n"
    for reg in confirmed:
        message += f"*ID {reg.id}:* {reg.full_name} - {reg.weapon_type}\n"
    
    update.message.reply_text(message, parse_mode='Markdown')

@admin_required
def confirm_registration_cmd(update: Update, context: CallbackContext):
    try:
        reg_id = int(context.args[0]) if context.args else None
        if not reg_id:
            update.message.reply_text("Используйте: /confirm <ID заявки>")
            return
        
        with get_db() as session:
            registration = session.query(Registration).filter_by(id=reg_id).first()
            if not registration:
                update.message.reply_text(f"❌ Заявка с ID {reg_id} не найдена.")
                return
            
            registration.status = 'confirmed'
            session.commit()
            
            # Уведомляем пользователя
            try:
                bot.send_message(
                    registration.telegram_id,
                    f"✅ *Ваша заявка подтверждена!*\n\n"
                    f"ФИО: {registration.full_name}\n"
                    f"Оружие: {registration.weapon_type}\n"
                    f"Категория: {registration.category}\n\n"
                    f"Ждем вас на соревнованиях!",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить пользователя: {e}")
            
            update.message.reply_text(f"✅ Заявка ID {reg_id} подтверждена.")
            
    except (ValueError, IndexError):
        update.message.reply_text("Используйте: /confirm <ID заявки>")

@admin_required
def reject_registration_cmd(update: Update, context: CallbackContext):
    try:
        reg_id = int(context.args[0]) if context.args else None
        if not reg_id:
            update.message.reply_text("Используйте: /reject <ID заявки>")
            return
        
        with get_db() as session:
            registration = session.query(Registration).filter_by(id=reg_id).first()
            if not registration:
                update.message.reply_text(f"❌ Заявка с ID {reg_id} не найдена.")
                return
            
            registration.status = 'rejected'
            session.commit()
            
            # Уведомляем пользователя
            try:
                bot.send_message(
                    registration.telegram_id,
                    f"❌ *Ваша заявка отклонена.*\n\n"
                    f"ФИО: {registration.full_name}\n"
                    f"Оружие: {registration.weapon_type}\n\n"
                    f"По вопросам обращайтесь к администраторам.",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить пользователя: {e}")
            
            update.message.reply_text(f"❌ Заявка ID {reg_id} отклонена.")
            
    except (ValueError, IndexError):
        update.message.reply_text("Используйте: /reject <ID заявки>")

# Обработчики быстрых команд (confirm_1, reject_1 и т.д.)
def create_quick_command_handler(command_type):
    def handler(update: Update, context: CallbackContext):
        if not is_admin(update.effective_user.id):
            update.message.reply_text("❌ У вас нет прав администратора.")
            return
        
        try:
            reg_id = int(update.message.text.split('_')[1])
            
            with get_db() as session:
                registration = session.query(Registration).filter_by(id=reg_id).first()
                if not registration:
                    update.message.reply_text(f"❌ Заявка с ID {reg_id} не найдена.")
                    return
                
                new_status = 'confirmed' if command_type == 'confirm' else 'rejected'
                registration.status = new_status
                session.commit()
                
                # Уведомляем пользователя
                status_text = "подтверждена" if command_type == 'confirm' else "отклонена"
                emoji = "✅" if command_type == 'confirm' else "❌"
                
                try:
                    bot.send_message(
                        registration.telegram_id,
                        f"{emoji} *Ваша заявка {status_text}!*\n\n"
                        f"ФИО: {registration.full_name}\n"
                        f"Оружие: {registration.weapon_type}\n"
                        f"Категория: {registration.category}",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Не удалось уведомить пользователя: {e}")
                
                update.message.reply_text(f"{emoji} Заявка ID {reg_id} {status_text}.")
                
        except (ValueError, IndexError):
            update.message.reply_text("❌ Неверный формат команды.")
    
    return handler

# Команда для просмотра своих заявок
def my_registrations(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    with get_db() as session:
        registrations = session.query(Registration).filter_by(
            telegram_id=user_id).order_by(Registration.created_at.desc()).all()
    
    if not registrations:
        update.message.reply_text("📭 У вас нет заявок. Начните регистрацию с команды /start")
        return
    
    message = "📋 *Ваши заявки:*\n\n"
    for reg in registrations:
        status_icon = "⏳" if reg.status == 'pending' else "✅" if reg.status == 'confirmed' else "❌"
        status_text = "ожидает" if reg.status == 'pending' else "подтверждена" if reg.status == 'confirmed' else "отклонена"
        message += f"{status_icon} *Заявка #{reg.id}*\n"
        message += f"Оружие: {reg.weapon_type}\n"
        message += f"Категория: {reg.category}\n"
        message += f"Статус: {status_text}\n"
        message += f"Дата: {reg.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
    
    update.message.reply_text(message, parse_mode='Markdown')

# Команда для перехода в админ-панель через браузер
@admin_required
def admin_panel_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    # Генерируем токен доступа
    token = generate_admin_token(user_id)
    
    # Получаем базовый URL
    base_url = config.get_base_url()
    
    if not base_url:
        update.message.reply_text("❌ WEBHOOK_URL не настроен. Обратитесь к разработчику.")
        return
    
    admin_url = f"{base_url}/admin_panel?token={token}"
    
    # Отправляем сообщение с кнопкой
    keyboard = [[InlineKeyboardButton("🌐 Открыть админ-панель", url=admin_url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        "👑 *Доступ к админ-панели*\n\n"
        "Для управления заявками перейдите по ссылке ниже:\n"
        f"Ссылка действительна {config.ADMIN_TOKEN_EXPIRE//3600} час.\n\n"
        "📱 *Возможности админ-панели:*\n"
        "• 📊 Просмотр статистики\n"
        "• 📋 Управление заявками\n"
        "• ✅ Подтверждение/отклонение\n"
        "• 🔍 Поиск и фильтрация\n"
        "• 📤 Экспорт данных",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Экспорт данных в CSV
@admin_required
def export_data(update: Update, context: CallbackContext):
    import csv
    import io
    
    with get_db() as session:
        registrations = session.query(Registration).all()
    
    if not registrations:
        update.message.reply_text("📭 Нет данных для экспорта.")
        return
    
    # Создаем CSV файл
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    
    # Заголовки
    writer.writerow(['ID', 'ФИО', 'Оружие', 'Категория', 'Возраст', 'Телефон', 'Статус', 'Дата регистрации'])
    
    # Данные
    for reg in registrations:
        writer.writerow([
            reg.id,
            reg.full_name,
            reg.weapon_type,
            reg.category,
            reg.age_group,
            reg.phone,
            reg.status,
            reg.created_at.strftime('%d.%m.%Y %H:%M') if reg.created_at else ''
        ])
    
    # Отправляем файл
    output.seek(0)
    context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=io.BytesIO(output.getvalue().encode('utf-8-sig')),
        filename=f'регистрации_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
        caption='📊 Экспорт данных регистраций'
    )

# Управление администраторами (только для супер-админов)
@super_admin_required
def add_admin(update: Update, context: CallbackContext):
    """Добавление нового администратора"""
    try:
        if not context.args or len(context.args) < 1:
            update.message.reply_text("Используйте: /add_admin <telegram_id> [role]")
            return
        
        new_admin_id = int(context.args[0])
        role = context.args[1] if len(context.args) > 1 else 'moderator'
        
        if role not in config.ADMIN_ROLES:
            update.message.reply_text(f"Роль должна быть одна из: {', '.join(config.ADMIN_ROLES)}")
            return
        
        with get_db() as session:
            # Проверяем, нет ли уже такого администратора
            existing = session.query(Admin).filter_by(telegram_id=new_admin_id).first()
            if existing:
                if existing.is_active:
                    update.message.reply_text(f"❌ Администратор с ID {new_admin_id} уже существует.")
                else:
                    existing.is_active = True
                    existing.role = role
                    session.commit()
                    update.message.reply_text(f"✅ Администратор с ID {new_admin_id} активирован с ролью '{role}'.")
                return
            
            # Добавляем нового администратора
            admin = Admin(
                telegram_id=new_admin_id,
                username='',
                full_name=f'Администратор {new_admin_id}',
                role=role,
                is_active=True,
                created_by=update.effective_user.id,
                created_at=datetime.utcnow()
            )
            session.add(admin)
            session.commit()
        
        update.message.reply_text(f"✅ Администратор с ID {new_admin_id} добавлен с ролью '{role}'.")
        
    except ValueError:
        update.message.reply_text("❌ Неверный формат ID. ID должен быть числом.")

@super_admin_required
def list_admins(update: Update, context: CallbackContext):
    """Список всех администраторов"""
    with get_db() as session:
        admins = session.query(Admin).filter_by(is_active=True).all()
    
    if not admins:
        update.message.reply_text("👥 Нет активных администраторов.")
        return
    
    message = "👥 *Список администраторов:*\n\n"
    for admin in admins:
        role_icon = "👑" if admin.role == 'admin' else "🛡️"
        message += f"{role_icon} *ID {admin.telegram_id}*\n"
        message += f"Роль: {admin.role}\n"
        if admin.full_name:
            message += f"Имя: {admin.full_name}\n"
        message += f"Добавлен: {admin.created_at.strftime('%d.%m.%Y')}\n\n"
    
    update.message.reply_text(message, parse_mode='Markdown')

# Обработчик текстовых команд админ-панели
def admin_text_handler(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        return
    
    text = update.message.text
    if text == "📊 Статистика":
        admin_stats(update, context)
    elif text == "📋 Список заявок":
        admin_list(update, context)
    elif text == "⏳ Ожидающие":
        admin_pending(update, context)
    elif text == "✅ Подтвержденные":
        admin_confirmed(update, context)
    elif text == "📝 Новая регистрация":
        update.message.reply_text(
            "Для начала регистрации отправьте /start",
            reply_markup=None
        )
    elif text == "🌐 Админ-панель":
        admin_panel_command(update, context)

# === Настройка обработчиков ===
if bot and dispatcher:
    # Основной диалог регистрации
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
    
    # Основные команды
    dispatcher.add_handler(CommandHandler('my_registrations', my_registrations))
    
    # Админские команды
    dispatcher.add_handler(CommandHandler('stats', admin_stats))
    dispatcher.add_handler(CommandHandler('list', admin_list))
    dispatcher.add_handler(CommandHandler('pending', admin_pending))
    dispatcher.add_handler(CommandHandler('confirmed', admin_confirmed))
    dispatcher.add_handler(CommandHandler('confirm', confirm_registration_cmd))
    dispatcher.add_handler(CommandHandler('reject', reject_registration_cmd))
    dispatcher.add_handler(CommandHandler('admin', admin_panel_command))
    dispatcher.add_handler(CommandHandler('export', export_data))
    dispatcher.add_handler(CommandHandler('add_admin', add_admin))
    dispatcher.add_handler(CommandHandler('list_admins', list_admins))
    
    # Быстрые команды (confirm_1, reject_1 и т.д.)
    dispatcher.add_handler(MessageHandler(Filters.regex(r'^/confirm_\d+$'), create_quick_command_handler('confirm')))
    dispatcher.add_handler(MessageHandler(Filters.regex(r'^/reject_\d+$'), create_quick_command_handler('reject')))
    
    # Обработчик текстовых команд админ-панели
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, admin_text_handler))

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
    clean_phone = ''.join(filter(str.isdigit, str(phone)))
    if len(clean_phone) == 11 and clean_phone.startswith('7'):
        return f"+7 ({clean_phone[1:4]}) {clean_phone[4:7]}-{clean_phone[7:9]}-{clean_phone[9:11]}"
    elif len(clean_phone) == 10:
        return f"+7 ({clean_phone[0:3]}) {clean_phone[3:6]}-{clean_phone[6:8]}-{clean_phone[8:10]}"
    return phone

@app.template_filter('status_icon')
def status_icon_filter(status):
    """Возвращает иконку для статуса"""
    icons = {
        'pending': '⏳',
        'confirmed': '✅',
        'rejected': '❌'
    }
    return icons.get(status, '')

# === Flask маршруты ===
@app.route('/')
def home():
    with get_db() as session:
        total_reg = session.query(Registration).count()
        total_admins = session.query(Admin).filter_by(is_active=True).count()
    
    return jsonify({
        "status": "running",
        "service": "TolyattiFencingRegBot",
        "version": "5.0",
        "config": config.to_dict(),
        "database": {
            "registrations": total_reg,
            "active_admins": total_admins
        }
    })

@app.route('/admin')
def admin_page():
    """Страница администратора (старая версия без авторизации)"""
    with get_db() as session:
        registrations = session.query(Registration).order_by(
            Registration.created_at.desc()).all()
    
    # Очищаем просроченные токены
    cleanup_expired_tokens()
    
    return render_template('admin.html', 
                         registrations=registrations,
                         config=config)

@app.route('/admin_panel')
def admin_panel_auth():
    """Защищенная админ-панель с токеном"""
    # Очищаем просроченные токены
    cleanup_expired_tokens()
    
    token = request.args.get('token')
    if not token:
        return render_template('error.html', 
                             error="Токен доступа отсутствует",
                             code=403), 403
    
    # Проверяем токен
    telegram_id = validate_admin_token(token)
    if not telegram_id:
        return render_template('error.html',
                             error="Токен недействителен или истек",
                             code=403), 403
    
    if not is_admin(telegram_id):
        return render_template('error.html',
                             error="Доступ запрещен",
                             code=403), 403
    
    with get_db() as session:
        registrations = session.query(Registration).order_by(
            Registration.created_at.desc()).all()
    
    return render_template('admin.html', 
                         registrations=registrations,
                         config=config,
                         current_admin_id=telegram_id,
                         token=token)

@app.route('/api/registrations')
def api_registrations():
    """API для получения заявок"""
    token = request.args.get('token')
    if not token:
        return jsonify({"error": "Токен отсутствует"}), 401
    
    telegram_id = validate_admin_token(token)
    if not telegram_id or not is_admin(telegram_id):
        return jsonify({"error": "Неавторизованный доступ"}), 403
    
    with get_db() as session:
        status = request.args.get('status')
        query = session.query(Registration)
        
        if status in ['pending', 'confirmed', 'rejected']:
            query = query.filter_by(status=status)
        
        page = int(request.args.get('page', 1))
        per_page = config.ITEMS_PER_PAGE
        offset = (page - 1) * per_page
        
        total = query.count()
        registrations = query.order_by(
            Registration.created_at.desc()).offset(offset).limit(per_page).all()
    
    return jsonify({
        'registrations': [{
            'id': r.id,
            'full_name': r.full_name,
            'weapon_type': r.weapon_type,
            'category': r.category,
            'age_group': r.age_group,
            'phone': r.phone,
            'experience': r.experience,
            'status': r.status,
            'created_at': r.created_at.isoformat() if r.created_at else None
        } for r in registrations],
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page
    })

@app.route('/api/registrations/<int:reg_id>/<action>', methods=['POST'])
def api_update_registration(reg_id, action):
    """API для обновления статуса заявки"""
    token = request.args.get('token')
    if not token:
        return jsonify({"error": "Токен отсутствует"}), 401
    
    telegram_id = validate_admin_token(token)
    if not telegram_id or not is_admin(telegram_id):
        return jsonify({"error": "Неавторизованный доступ"}), 403
    
    if action not in ['confirm', 'reject']:
        return jsonify({"error": "Неверное действие"}), 400
    
    with get_db() as session:
        registration = session.query(Registration).filter_by(id=reg_id).first()
        if not registration:
            return jsonify({"error": "Заявка не найдена"}), 404
        
        new_status = 'confirmed' if action == 'confirm' else 'rejected'
        registration.status = new_status
        session.commit()
        
        # Уведомляем пользователя
        try:
            bot.send_message(
                registration.telegram_id,
                f"{'✅' if action == 'confirm' else '❌'} *Ваша заявка {'подтверждена' if action == 'confirm' else 'отклонена'}!*\n\n"
                f"ФИО: {registration.full_name}\n"
                f"Оружие: {registration.weapon_type}\n"
                f"Категория: {registration.category}",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя: {e}")
    
    return jsonify({"success": True, "new_status": new_status})

@app.route('/webhook', methods=['POST'])
def webhook():
    if not bot or not dispatcher:
        return jsonify({"error": "Telegram bot not available"}), 500
        
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok'

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    if not bot:
        return jsonify({"error": "Telegram bot not available"}), 500
        
    webhook_url = config.get_webhook_url()
    if not webhook_url:
        return jsonify({"error": "WEBHOOK_URL не задан"}), 400
    
    try:
        result = bot.set_webhook(webhook_url)
        return jsonify({
            "status": "success" if result else "failed",
            "url": webhook_url,
            "bot_info": {
                "username": bot.get_me().username,
                "name": bot.get_me().first_name
            }
        })
    except Exception as e:
        logger.error(f"Ошибка установки вебхука: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health')
def health():
    with get_db() as session:
        total_reg = session.query(Registration).count()
        try:
            session.execute('SELECT 1')
            db_ok = True
        except:
            db_ok = False
    
    bot_status = bot is not None
    if bot:
        try:
            bot.get_me()
            bot_connected = True
        except:
            bot_connected = False
    else:
        bot_connected = False
    
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "database": {
                "ok": db_ok,
                "records": total_reg
            },
            "telegram_bot": {
                "initialized": bot_status,
                "connected": bot_connected
            },
            "webhook": {
                "url": config.WEBHOOK_URL,
                "set": bot_status
            }
        }
    })

@app.route('/test_data')
def test_data():
    """Добавляет тестовые данные для демонстрации"""
    with get_db() as session:
        # Проверяем, есть ли уже тестовые данные
        existing = session.query(Registration).filter_by(telegram_id=999999999).first()
        if existing:
            return jsonify({
                "status": "already_exists",
                "message": "Тестовые данные уже существуют"
            })
        
        test_registrations = [
            Registration(
                telegram_id=999999999,
                username='test_user',
                full_name='Иванов Иван Иванович',
                weapon_type='Сабля',
                category='Взрослые',
                age_group='19+ лет',
                phone='+79991234567',
                experience='Занимаюсь 5 лет, имею 1 разряд',
                status='pending',
                created_at=datetime.utcnow()
            ),
            Registration(
                telegram_id=888888888,
                username='test_user2',
                full_name='Петрова Анна Сергеевна',
                weapon_type='Рапира',
                category='Юниоры',
                age_group='16-18 лет',
                phone='+79997654321',
                experience='Занимаюсь 3 года, КМС',
                status='confirmed',
                created_at=datetime.utcnow()
            ),
            Registration(
                telegram_id=777777777,
                username='test_user3',
                full_name='Сидоров Алексей Владимирович',
                weapon_type='Шпага',
                category='Ветераны',
                age_group='19+ лет',
                phone='+79995555555',
                experience='Занимаюсь 10 лет, МС',
                status='rejected',
                created_at=datetime.utcnow()
            )
        ]
        
        for reg in test_registrations:
            session.add(reg)
        
        session.commit()
    
    return jsonify({
        "status": "added",
        "added": len(test_registrations),
        "total": total_reg + len(test_registrations)
    })

@app.route('/config')
def show_config():
    """Показать конфигурацию (без секретов)"""
    return jsonify(config.to_dict())

# === Инициализация при запуске ===
def initialize_bot():
    if bot:
        try:
            # Устанавливаем вебхук
            webhook_url = config.get_webhook_url()
            if webhook_url:
                # Удаляем старый вебхук
                bot.delete_webhook()
                time.sleep(0.1)
                
                # Устанавливаем новый
                bot.set_webhook(webhook_url)
                logger.info(f"✅ Вебхук установлен: {webhook_url}")
                
                # Проверяем бота
                bot_info = bot.get_me()
                logger.info(f"🤖 Бот: @{bot_info.username} ({bot_info.first_name})")
            else:
                logger.warning("⚠️ WEBHOOK_URL не установлен")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации бота: {e}")

# Инициализируем при импорте
initialize_bot()

if __name__ == '__main__':
    port = config.PORT
    logger.info(f"🚀 Запуск приложения на порту {port}")
    logger.info(f"🔧 Режим отладки: {'ВКЛ' if config.DEBUG else 'ВЫКЛ'}")
    
    # Показываем конфигурацию
    logger.info("📋 Конфигурация:")
    for key, value in config.to_dict().items():
        if isinstance(value, list):
            value = ', '.join(value)
        logger.info(f"  {key}: {value}")
    
    app.run(host='0.0.0.0', port=port, debug=config.DEBUG)
