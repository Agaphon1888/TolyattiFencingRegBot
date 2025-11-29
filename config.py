import os

class Config:
    TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', 'YOUR_BOT_TOKEN')
    WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '') + '/webhook'
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-here')
    ADMIN_TELEGRAM_IDS = os.environ.get('ADMIN_TELEGRAM_IDS', '')
    
    # Настройки формы регистрации
    WEAPON_TYPES = ['Сабля', 'Шпага', 'Рапира']
    CATEGORIES = ['Юниоры', 'Взрослые', 'Ветераны']
    AGE_GROUPS = ['до 12 лет', '13-15 лет', '16-18 лет', '19+ лет']
    
    # Настройки администрирования
    ADMIN_ROLES = ['admin', 'moderator']
