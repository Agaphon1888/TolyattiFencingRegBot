import os
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

class Config:
    # Основные настройки
    TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '')
    WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '')  # Без /webhook в конце
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    ADMIN_TOKEN_EXPIRE = int(os.environ.get('ADMIN_TOKEN_EXPIRE', 3600))  # 1 час в секундах
    
    # Настройки администраторов (через запятую)
    ADMIN_TELEGRAM_IDS = os.environ.get('ADMIN_TELEGRAM_IDS', '')
    
    # Настройки базы данных
    DATABASE_URL = os.environ.get('DATABASE_URL', '')
    
    # Настройки сервера
    PORT = int(os.environ.get('PORT', 10000))
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    # Настройки формы регистрации
    WEAPON_TYPES = ['Сабля', 'Шпага', 'Рапира']
    CATEGORIES = ['Юниоры', 'Взрослые', 'Ветераны']
    AGE_GROUPS = ['до 12 лет', '13-15 лет', '16-18 лет', '19+ лет']
    
    # Настройки администрирования
    ADMIN_ROLES = ['admin', 'moderator']
    
    # Настройки логгирования
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    
    # Настройки безопасности
    MAX_FILE_SIZE = int(os.environ.get('MAX_FILE_SIZE', 16 * 1024 * 1024))  # 16MB
    
    # Настройки веб-интерфейса
    ITEMS_PER_PAGE = int(os.environ.get('ITEMS_PER_PAGE', 20))
    
    @classmethod
    def validate_config(cls):
        """Проверка конфигурации"""
        errors = []
        
        if not cls.TELEGRAM_TOKEN:
            errors.append("TELEGRAM_TOKEN не установлен")
        
        if not cls.WEBHOOK_URL:
            errors.append("WEBHOOK_URL не установлен")
        
        if not cls.ADMIN_TELEGRAM_IDS:
            errors.append("ADMIN_TELEGRAM_IDS не установлен (укажите хотя бы один ID)")
        
        if not cls.DATABASE_URL:
            errors.append("DATABASE_URL не установлен")
        
        if errors:
            raise ValueError("Ошибки конфигурации:\n" + "\n".join(f"  • {error}" for error in errors))
        
        return True
    
    @classmethod
    def get_admin_ids(cls):
        """Получение списка ID администраторов"""
        if not cls.ADMIN_TELEGRAM_IDS:
            return []
        
        admin_ids = []
        for admin_id in cls.ADMIN_TELEGRAM_IDS.split(','):
            try:
                admin_ids.append(int(admin_id.strip()))
            except ValueError:
                continue
        
        return admin_ids
    
    @classmethod
    def get_webhook_url(cls):
        """Получение полного URL для вебхука"""
        if cls.WEBHOOK_URL.endswith('/'):
            return f"{cls.WEBHOOK_URL}webhook"
        return f"{cls.WEBHOOK_URL}/webhook"
    
    @classmethod
    def get_base_url(cls):
        """Получение базового URL (без /webhook)"""
        if cls.WEBHOOK_URL.endswith('/webhook'):
            return cls.WEBHOOK_URL.replace('/webhook', '')
        elif cls.WEBHOOK_URL.endswith('/'):
            return cls.WEBHOOK_URL[:-1]
        return cls.WEBHOOK_URL
    
    @classmethod
    def to_dict(cls):
        """Конвертация конфигурации в словарь (без секретов)"""
        return {
            'WEBHOOK_URL': cls.WEBHOOK_URL,
            'PORT': cls.PORT,
            'DEBUG': cls.DEBUG,
            'LOG_LEVEL': cls.LOG_LEVEL,
            'ITEMS_PER_PAGE': cls.ITEMS_PER_PAGE,
            'WEAPON_TYPES': cls.WEAPON_TYPES,
            'CATEGORIES': cls.CATEGORIES,
            'AGE_GROUPS': cls.AGE_GROUPS,
            'ADMIN_ROLES': cls.ADMIN_ROLES,
            'TELEGRAM_TOKEN_SET': bool(cls.TELEGRAM_TOKEN),
            'ADMIN_IDS_COUNT': len(cls.get_admin_ids()),
            'DATABASE_URL_SET': bool(cls.DATABASE_URL),
        }

# Создаем экземпляр конфигурации
config = Config()
