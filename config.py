import os
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
    def validate_config(cls):
        errors = []
        if not cls.TELEGRAM_TOKEN:
            errors.append("TELEGRAM_TOKEN не установлен")
        if not cls.WEBHOOK_URL:
            errors.append("WEBHOOK_URL не установлен")
        if not cls.DATABASE_URL:
            errors.append("DATABASE_URL не установлен")
        if not cls.ADMIN_TELEGRAM_IDS:
            errors.append("ADMIN_TELEGRAM_IDS не установлен")
        if errors:
            raise ValueError("Ошибки конфигурации:\n" + "\n".join(errors))
        return True

    @classmethod
    def get_admin_ids(cls):
        if not cls.ADMIN_TELEGRAM_IDS:
            return []
        return [int(id.strip()) for id in cls.ADMIN_TELEGRAM_IDS.split(',') if id.strip().isdigit()]

    @classmethod
    def get_webhook_url(cls):
        return f"{cls.WEBHOOK_URL.rstrip('/')}/webhook"

    @classmethod
    def get_base_url(cls):
        return cls.WEBHOOK_URL.rstrip('/')

    @classmethod
    def to_dict(cls):
        return {k: v for k, v in cls.__dict__.items() if not k.startswith('_') and not callable(v)}

config = Config()  # ⚠️ Важно: экспортируем как объект `config`
