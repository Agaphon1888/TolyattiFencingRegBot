import os
import logging
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from contextlib import contextmanager

from config import config

logging.basicConfig(level=getattr(logging, config.LOG_LEVEL))
logger = logging.getLogger(__name__)

Base = declarative_base()


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


class Admin(Base):
    __tablename__ = 'admins'
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))
    full_name = Column(String(200))
    role = Column(String(50), default='moderator')
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)  # 🟢 Добавляем колонку
    created_by = Column(Integer)


engine = None
SessionLocal = None


def init_db():
    global engine, SessionLocal

    db_url = config.DATABASE_URL
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    engine = create_engine(db_url, pool_pre_ping=True, echo=config.DEBUG)
    Base.metadata.create_all(bind=engine)

    SessionLocal = scoped_session(sessionmaker(bind=engine))
    fix_admin_table_schema()
    initialize_super_admins()


def fix_admin_table_schema():
    session = SessionLocal()
    try:
        # Проверяем существование колонки created_at
        result = session.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'admins' AND column_name = 'created_at'
        """)
        if not result.fetchone():
            session.execute("ALTER TABLE admins ADD COLUMN created_at TIMESTAMP DEFAULT NOW()")
            session.commit()
            logger.info("✅ Добавлена колонка 'created_at' в 'admins'")
    except Exception as e:
        logger.error(f"Ошибка при добавлении колонки created_at: {e}")
        session.rollback()
    finally:
        session.close()


def initialize_super_admins():
    admin_ids = config.get_admin_ids()
    session = SessionLocal()
    try:
        for tid in admin_ids:
            existing = session.query(Admin).filter_by(telegram_id=tid).first()
            if not existing:
                admin = Admin(
                    telegram_id=tid,
                    username='admin',
                    full_name='Super Admin',
                    role='admin',
                    created_by=0
                )
                session.add(admin)
                logger.info(f"✅ Добавлен супер-админ: {tid}")
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Ошибка инициализации админов: {e}")
    finally:
        session.close()


@contextmanager
def db_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()


def get_session():
    return SessionLocal()
