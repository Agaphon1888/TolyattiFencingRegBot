import os
import logging
from sqlalchemy import create_engine, Column, BigInteger, String, Boolean, DateTime, Text, inspect, text, Integer, Date, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session, relationship
from datetime import datetime
from contextlib import contextmanager

from config import config

logging.basicConfig(level=getattr(logging, config.LOG_LEVEL))
logger = logging.getLogger(__name__)

Base = declarative_base()


class Event(Base):
    __tablename__ = 'events'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    event_date = Column(Date, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'event_date': self.event_date.isoformat() if self.event_date else None,
            'description': self.description,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Registration(Base):
    __tablename__ = 'registrations'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    username = Column(String(100))
    full_name = Column(String(200), nullable=False)
    weapon_type = Column(String(50), nullable=False)
    category = Column(String(50), nullable=False)
    age_group = Column(String(50), nullable=False)
    phone = Column(String(20), nullable=False)
    experience = Column(Text, nullable=False)
    status = Column(String(20), default='pending', index=True)
    admin_comment = Column(Text)
    event_id = Column(Integer, ForeignKey('events.id'))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связь
    event = relationship("Event")
    
    def to_dict(self):
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
            'admin_comment': self.admin_comment,
            'event_id': self.event_id,
            'event_name': self.event.name if self.event else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Admin(Base):
    __tablename__ = 'admins'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(100))
    full_name = Column(String(200))
    role = Column(String(50), default='moderator')
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(BigInteger)
    
    def to_dict(self):
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


engine = None
SessionLocal = None


@contextmanager
def session_scope():
    """Контекстный менеджер для работы с сессиями"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        logger.error(f"Session error: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    global engine, SessionLocal

    logger.info("🔄 Инициализация базы данных...")
    
    db_url = config.DATABASE_URL
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        logger.info("✅ Преобразовали postgres:// в postgresql://")

    logger.info(f"📊 Подключаемся к БД")
    
    try:
        engine = create_engine(
            db_url, 
            pool_pre_ping=True, 
            echo=config.DEBUG,
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600
        )
        
        # Проверяем соединение
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ Соединение с БД установлено")
        
    except Exception as e:
        logger.error(f"❌ Не удалось подключиться к БД: {e}")
        raise
    
    # Создаем таблицы
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Таблицы созданы/проверены")
    except Exception as e:
        logger.error(f"❌ Ошибка при создании таблиц: {e}")
        raise
    
    SessionLocal = scoped_session(sessionmaker(bind=engine, expire_on_commit=False))
    
    # Исправляем схему и инициализируем админов
    fix_database_schema()
    initialize_super_admins()
    
    logger.info("✅ База данных инициализирована")
    return True


def fix_database_schema():
    """Исправление схемы базы данных"""
    logger.info("🔧 Проверка и исправление схемы БД...")
    
    session = SessionLocal()
    try:
        inspector = inspect(engine)
        
        # ===== Таблица admins =====
        if 'admins' in inspector.get_table_names():
            logger.info("✅ Таблица 'admins' существует")
            
            # Получаем информацию о колонках
            columns = {col['name']: col for col in inspector.get_columns('admins')}
            
            # 1. Проверяем telegram_id
            if 'telegram_id' in columns:
                col_type = str(columns['telegram_id']['type'])
                logger.info(f"   telegram_id тип: {col_type}")
                
                # Если тип integer, меняем на bigint
                if 'INTEGER' in col_type.upper() or 'INT' in col_type.upper():
                    logger.warning("   ⚠️ telegram_id имеет тип INTEGER, меняем на BIGINT")
                    try:
                        session.execute(text("ALTER TABLE admins ALTER COLUMN telegram_id TYPE BIGINT"))
                        session.commit()
                        logger.info("   ✅ telegram_id изменен на BIGINT")
                    except Exception as e:
                        logger.error(f"   ❌ Ошибка изменения типа telegram_id: {e}")
                        session.rollback()
                else:
                    logger.info("   ✅ telegram_id уже имеет правильный тип")
            
            # 2. Проверяем created_at
            if 'created_at' not in columns:
                logger.warning("   ⚠️ Колонка created_at не найдена, добавляем...")
                try:
                    session.execute(text("ALTER TABLE admins ADD COLUMN created_at TIMESTAMP DEFAULT NOW()"))
                    session.commit()
                    logger.info("   ✅ Колонка created_at добавлена")
                except Exception as e:
                    logger.error(f"   ❌ Ошибка добавления created_at: {e}")
                    session.rollback()
            
            # 3. Проверяем created_by
            if 'created_by' not in columns:
                logger.warning("   ⚠️ Колонка created_by не найдена, добавляем...")
                try:
                    session.execute(text("ALTER TABLE admins ADD COLUMN created_by BIGINT"))
                    session.commit()
                    logger.info("   ✅ Колонка created_by добавлена")
                except Exception as e:
                    logger.error(f"   ❌ Ошибка добавления created_by: {e}")
                    session.rollback()
        
        # ===== Таблица registrations =====
        if 'registrations' in inspector.get_table_names():
            logger.info("✅ Таблица 'registrations' существует")
            
            # Получаем информацию о колонках
            columns = inspector.get_columns('registrations')
            column_names = [col['name'] for col in columns]
            logger.info(f"   Найдены колонки: {column_names}")
            
            # Проверяем и добавляем отсутствующие колонки
            expected_columns = {
                'username': 'VARCHAR(100)',
                'updated_at': 'TIMESTAMP'
            }
            
            for column_name, column_type in expected_columns.items():
                if column_name not in column_names:
                    logger.warning(f"   ⚠️ Колонка '{column_name}' не найден, добавляем...")
                    try:
                        if column_name == 'updated_at':
                            session.execute(text(f"ALTER TABLE registrations ADD COLUMN {column_name} {column_type} DEFAULT NOW()"))
                        else:
                            session.execute(text(f"ALTER TABLE registrations ADD COLUMN {column_name} {column_type}"))
                        session.commit()
                        logger.info(f"   ✅ Колонка '{column_name}' добавлен")
                    except Exception as e:
                        logger.error(f"   ❌ Ошибка добавления колонки '{column_name}': {e}")
                        session.rollback()
            
            # Создаем индексы если их нет
            indexes = inspector.get_indexes('registrations')
            
            # Индекс для telegram_id
            if not any('telegram_id' in idx.get('column_names', []) for idx in indexes):
                logger.warning("   ⚠️ Индекс для telegram_id не найден, создаем...")
                try:
                    session.execute(text("CREATE INDEX IF NOT EXISTS idx_registrations_telegram_id ON registrations(telegram_id)"))
                    session.commit()
                    logger.info("   ✅ Индекс для telegram_id создан")
                except Exception as e:
                    logger.error(f"   ❌ Ошибка создания индекса: {e}")
            
            # Индекс для status
            if not any('status' in idx.get('column_names', []) for idx in indexes):
                logger.warning("   ⚠️ Индекс для status не найден, создаем...")
                try:
                    session.execute(text("CREATE INDEX IF NOT EXISTS idx_registrations_status ON registrations(status)"))
                    session.commit()
                    logger.info("   ✅ Индекс для status создан")
                except Exception as e:
                    logger.error(f"   ❌ Ошибка создания индекса: {e}")
        
        # ===== Таблица events =====
        if 'events' not in inspector.get_table_names():
            logger.warning("⚠️ Таблица 'events' не найдена, создаем...")
            try:
                session.execute(text("""
                    CREATE TABLE events (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(200) NOT NULL,
                        event_date DATE NOT NULL,
                        description TEXT,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                logger.info("   ✅ Таблица 'events' создана")
            except Exception as e:
                logger.error(f"   ❌ Ошибка создания таблицы 'events': {e}")
        
        logger.info("✅ Проверка схемы завершена")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке схемы: {e}")
        session.rollback()
    finally:
        session.close()


def initialize_super_admins():
    """Инициализация супер-администраторов из конфига"""
    admin_ids = config.get_admin_ids()
    if not admin_ids:
        logger.warning("⚠️ ADMIN_TELEGRAM_IDS не заданы в конфигурации")
        return
    
    logger.info(f"👥 Инициализация супер-админов: {admin_ids}")
    
    session = SessionLocal()
    try:
        for tid in admin_ids:
            existing = session.query(Admin).filter_by(telegram_id=tid).first()
            if not existing:
                admin = Admin(
                    telegram_id=tid,
                    username=f'admin_{tid}',
                    full_name=f'Супер-админ {tid}',
                    role='admin',
                    is_active=True,
                    created_by=0
                )
                session.add(admin)
                logger.info(f"   ✅ Добавлен супер-админ: {tid}")
            else:
                logger.info(f"   ℹ️ Супер-админ {tid} уже существует")
        
        session.commit()
        logger.info(f"✅ Инициализация админов завершена")
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации админов: {e}")
        session.rollback()
    finally:
        session.close()


def get_session():
    """Получение новой сессии"""
    return SessionLocal()


def check_database_connection():
    """Проверка соединения с базой данных"""
    try:
        session = SessionLocal()
        result = session.execute(text("SELECT 1")).fetchone()
        session.close()
        return result[0] == 1
    except Exception as e:
        logger.error(f"❌ Ошибка проверки соединения с БД: {e}")
        return False
