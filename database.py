import os
import logging
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from datetime import datetime
from contextlib import contextmanager

# Импорт конфигурации
from config import config

# Настройка логирования
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Базовый класс для моделей
Base = declarative_base()

# === Модель регистрации участников ===
class Registration(Base):
    __tablename__ = 'registrations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, nullable=False)
    username = Column(String(100))
    full_name = Column(String(200), nullable=False)
    weapon_type = Column(String(50), nullable=False)
    category = Column(String(50), nullable=False)
    age_group = Column(String(50), nullable=False)
    phone = Column(String(20), nullable=False)
    experience = Column(Text, nullable=False)
    status = Column(String(20), default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Registration(id={self.id}, name='{self.full_name}', status='{self.status}')>"

    def to_dict(self):
        """Конвертация в словарь"""
        return {
            'id': self.id,
            'telegram_id': self.telegram_id,
            'username': self.username,
            'full_name': self.full_name,
            'weapon_type': self.weapon_type,
            'category': self.category,
            'age_group': self.age_group,
            'phone': self.phone,
            'experience': self.experience,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


# === Модель администраторов ===
class Admin(Base):
    __tablename__ = 'admins'

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))  # Может быть None
    full_name = Column(String(200))
    role = Column(String(50), default='moderator')
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer)

    def __repr__(self):
        return f"<Admin(telegram_id={self.telegram_id}, role='{self.role}', active={self.is_active})>"

    def to_dict(self):
        """Конвертация в словарь"""
        return {
            'id': self.id,
            'telegram_id': self.telegram_id,
            'username': self.username,
            'full_name': self.full_name,
            'role': self.role,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by': self.created_by
        }


# Глобальные объекты
engine = None
SessionLocal = None


def init_db():
    """Инициализация базы данных с автоматическим добавлением недостающих колонок"""
    global engine, SessionLocal

    db_url = config.DATABASE_URL
    if not db_url:
        logger.critical("❌ DATABASE_URL не установлен в конфигурации!")
        raise RuntimeError("DATABASE_URL is not set")

    # Исправление схемы URL для SQLAlchemy
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        logger.info("🔄 Обновлён URL с 'postgres://' на 'postgresql://'")

    try:
        # Создаём движок
        engine = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_recycle=300,
            pool_size=5,
            max_overflow=10,
            echo=config.DEBUG
        )

        # Создаём таблицы, если они не существуют
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Таблицы проверены/созданы")

        # Создаём фабрику сессий
        SessionLocal = scoped_session(sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine
        ))

        # Проверяем и обновляем схему при необходимости
        fix_admin_table_schema()

        # Инициализируем супер-админов
        initialize_super_admins()

        logger.info("🟢 База данных успешно инициализирована")

    except SQLAlchemyError as e:
        logger.critical(f"🔴 Ошибка подключения к базе данных: {e}")
        raise
    except Exception as e:
        logger.critical(f"🔴 Неизвестная ошибка при инициализации БД: {e}")
        raise


def fix_admin_table_schema():
    """Добавляет недостающие колонки в таблицу admins при необходимости"""
    session = SessionLocal()
    try:
        # Проверяем, есть ли колонка `username`
        result = session.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'admins' AND column_name = 'username'
        """))
        if not result.fetchone():
            session.execute(text("ALTER TABLE admins ADD COLUMN username VARCHAR(100)"))
            session.commit()
            logger.info("✅ Добавлена колонка 'username' в таблицу 'admins'")

        # Проверяем наличие `full_name`
        result = session.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'admins' AND column_name = 'full_name'
        """))
        if not result.fetchone():
            session.execute(text("ALTER TABLE admins ADD COLUMN full_name VARCHAR(200)"))
            session.commit()
            logger.info("✅ Добавлена колонка 'full_name' в таблицу 'admins'")

        # Проверяем наличие `created_by`
        result = session.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'admins' AND column_name = 'created_by'
        """))
        if not result.fetchone():
            session.execute(text("ALTER TABLE admins ADD COLUMN created_by INTEGER"))
            session.commit()
            logger.info("✅ Добавлена колонка 'created_by' в таблицу 'admins'")

    except Exception as e:
        logger.error(f"⚠️ Ошибка при обновлении схемы admins: {e}")
        session.rollback()
    finally:
        session.close()


@contextmanager
def db_session():
    """Контекстный менеджер для работы с сессиями (старый интерфейс)"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Ошибка в сессии БД: {e}")
        raise
    finally:
        session.close()


def get_session():
    """Получение новой сессии"""
    return SessionLocal()


def initialize_super_admins():
    """Инициализирует супер-админов из конфигурации"""
    admin_ids = config.get_admin_ids()
    if not admin_ids:
        logger.warning("⚠️ ADMIN_TELEGRAM_IDS не установлен")
        return

    session = SessionLocal()
    try:
        for telegram_id in admin_ids:
            # Проверяем, нет ли уже такого администратора
            existing = session.query(Admin).filter_by(telegram_id=telegram_id).first()
            if not existing:
                admin = Admin(
                    telegram_id=telegram_id,
                    username='super_admin',
                    full_name='Супер Администратор',
                    role='admin',
                    is_active=True,
                    created_by=0  # System
                )
                session.add(admin)
                logger.info(f"✅ Добавлен супер-админ: {telegram_id}")
            elif not existing.is_active:
                existing.is_active = True
                existing.role = 'admin'
                logger.info(f"✅ Активирован супер-админ: {telegram_id}")

        session.commit()

    except Exception as e:
        session.rollback()
        logger.error(f"❌ Ошибка при инициализации админов: {e}")
        raise
    finally:
        session.close()


def get_db_stats():
    """Получение статистики базы данных"""
    session = SessionLocal()
    try:
        total_reg = session.query(Registration).count()
        pending = session.query(Registration).filter_by(status='pending').count()
        confirmed = session.query(Registration).filter_by(status='confirmed').count()
        rejected = session.query(Registration).filter_by(status='rejected').count()
        total_admins = session.query(Admin).filter_by(is_active=True).count()

        return {
            'total_registrations': total_reg,
            'pending': pending,
            'confirmed': confirmed,
            'rejected': rejected,
            'total_admins': total_admins
        }
    finally:
        session.close()


def close_db():
    """Закрытие соединения с базой данных"""
    global engine
    if engine:
        engine.dispose()
        logger.info("🔒 Соединение с базой данных закрыто")
