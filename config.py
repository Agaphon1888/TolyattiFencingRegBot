import os
import sys
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '')
    WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '')
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    ADMIN_TOKEN_EXPIRE = int(os.environ.get('ADMIN_TOKEN_EXPIRE', 3600))

    ADMIN_TELEGRAM_IDS = os.environ.get('ADMIN_TELEGRAM_IDS', '')
    DATABASE_URL = os.environ.get('DATABASE_URL', '')

    PORT = int(os.environ.get('PORT', 10000))
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

    MAX_FILE_SIZE = int(os.environ.get('MAX_FILE_SIZE', 16 * 1024 * 1024))
    ITEMS_PER_PAGE = int(os.environ.get('ITEMS_PER_PAGE', 20))

    WEAPON_TYPES = ['Сабля', 'Шпага', 'Рапира']
    CATEGORIES = ['Юниоры', 'Взрослые', 'Ветераны']
    AGE_GROUPS = ['до 12 лет', '13-15 лет', '16-18 лет', '19+ лет']
    ADMIN_ROLES = ['admin', 'moderator']

    @classmethod
    def get_admin_ids(cls):
        if not cls.ADMIN_TELEGRAM_IDS:
            return []
        try:
            return [int(id.strip()) for id in cls.ADMIN_TELEGRAM_IDS.split(',') if id.strip().isdigit()]
        except:
            return []

    @classmethod
    def get_webhook_url(cls):
        if not cls.WEBHOOK_URL:
            return ''
        return f"{cls.WEBHOOK_URL.rstrip('/')}/webhook"

    @classmethod
    def to_dict(cls):
        return {k: v for k, v in cls.__dict__.items() if not k.startswith('_') and not callable(v)}

    @classmethod
    def validate(cls):
        """Проверка конфигурации"""
        errors = []
        
        if not cls.TELEGRAM_TOKEN:
            errors.append("TELEGRAM_TOKEN не установлен")
        
        if not cls.WEBHOOK_URL:
            errors.append("WEBHOOK_URL не установлен")
        
        if not cls.DATABASE_URL:
            errors.append("DATABASE_URL не установлен")
        
        if not cls.SECRET_KEY or cls.SECRET_KEY == 'dev-secret-key':
            print("⚠️  Внимание: используется стандартный SECRET_KEY")
        
        if errors:
            print("❌ Ошибки конфигурации:")
            for error in errors:
                print(f"   - {error}")
            if not os.environ.get('RENDER'):
                print("🚨 Приложение остановлено из-за ошибок конфигурации")
                sys.exit(1)
            else:
                print("⚠️  Работаем с ошибками конфигурации...")
        
        return len(errors) == 0

config = Config()
config.validate()
