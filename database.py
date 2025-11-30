# database.py
import os
import logging
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Базовый класс для моделей
Base = declarative_base()

# === Модель регистрации участников ===
class Registration(Base):
    __tablename__ = 'registrations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, nullable=False)
    full_name = Column(String, nullable=False)
    weapon_type = Column(String, nullable=False)  # фехтование на рапирах, шпагах и т.д.
    category = Column(String, nullable=False)     # начинающий, продвинутый
    age_group = Column(String, nullable=False)    # детская, юношеская, взрослая
    phone = Column(String, nullable=False)
    experience = Column(String, nullable=False)   # опыт фехтования
    status = Column(String, default='pending')    # pending, confirmed, rejected
    admin_comment = Column(String, nullable=True)

    def __repr__(self):
        return f"<Registration(id={self.id}, name='{self.full_name}', status='{self.status}')>"

# === Модель администраторов ===
class Admin(Base):
    __tablename__ = 'admins'

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    full_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    role = Column(String, default='moderator')  # moderator, admin
    is_active = Column(Boolean, default=True)
    added_by = Column(Integer, nullable=True)  # кто добавил этого админа

    def __repr__(self):
        return f"<Admin(id={self.telegram_id}, role='{self.role}', active={self.is_active})>"

# === Класс управления базой данных ===
class Database:
    def __init__(self):
        # Получаем URL базы из переменной окружения
        self.db_url = os.getenv("DATABASE_URL")
        
        # Проверка, установлена ли переменная
        if not self.db_url:
            logger.critical("❌ Переменная окружения DATABASE_URL не установлена!")
            raise RuntimeError("DATABASE_URL is not set. Check your environment variables in Render.")

        # SQLAlchemy поддерживает только 'postgresql://', а не 'postgres://'
        if self.db_url.startswith("postgres://"):
            self.db_url = self.db_url.replace("postgres://", "postgresql://", 1)
            logger.info("🔄 Обновлён URL с 'postgres://' на 'postgresql://'")

        logger.info(f"🔗 Подключение к базе данных: {self.db_url.split('@')[-1].split('/')[0]}")  # логируем хост

        try:
            # Создаём движок
            self.engine = create_engine(
                self.db_url,
                pool_pre_ping=True,        # Проверяет соединение перед использованием
                pool_recycle=300,          # Пересоздаёт соединения каждые 5 минут
                echo=False                 # Отключаем SQL-логи (включите для отладки)
            )

            # Создаём таблицы, если их нет
            Base.metadata.create_all(self.engine)
            logger.info("✅ Таблицы проверены/созданы")

            # Создаём сессию
            Session = sessionmaker(bind=self.engine)
            self.session = Session()
            logger.info("🟢 Подключение к базе данных успешно установлено")

        except SQLAlchemyError as e:
            logger.critical(f"🔴 Ошибка подключения к базе данных: {e}")
            raise
        except Exception as e:
            logger.critical(f"🔴 Неизвестная ошибка при инициализации БД: {e}")
            raise

    def close(self):
        """Закрытие сессии (вызывается при остановке бота)"""
        if hasattr(self, 'session'):
            self.session.close()
            logger.info("🔒 Сессия базы данных закрыта")

# === Глобальный экземпляр базы данных ===
# Будет использоваться в app.py
db = None

def init_db():
    """Инициализация базы данных (вызывается в app.py)"""
    global db
    try:
        db = Database()
        logger.info("📦 База данных инициализирована")
    except Exception as e:
        logger.critical(f"💥 Не удалось инициализировать базу данных: {e}")
        raise
