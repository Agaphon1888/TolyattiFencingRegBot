```python
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from database import Base
from datetime import datetime
import os

class Admin(Base):
    __tablename__ = 'admins'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))
    full_name = Column(String(200))
    role = Column(String(50), default='moderator')  # 'admin', 'moderator'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer)  # ID администратора, который добавил

class AdminManager:
    def __init__(self, db_session):
        self.db = db_session
        
    def is_admin(self, telegram_id):
        """Проверяет, является ли пользователь администратором"""
        admin = self.db.query(Admin).filter_by(
            telegram_id=telegram_id, 
            is_active=True
        ).first()
        return admin is not None
    
    def is_super_admin(self, telegram_id):
        """Проверяет, является ли пользователь супер-админом"""
        admin = self.db.query(Admin).filter_by(
            telegram_id=telegram_id, 
            role='admin',
            is_active=True
        ).first()
        return admin is not None
    
    def add_admin(self, telegram_id, username, full_name, role='moderator', created_by=None):
        """Добавляет нового администратора"""
        # Проверяем, нет ли уже такого администратора
        existing = self.db.query(Admin).filter_by(telegram_id=telegram_id).first()
        if existing:
            if not existing.is_active:
                existing.is_active = True
                existing.role = role
                self.db.commit()
                return existing
            return None
        
        admin = Admin(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            role=role,
            created_by=created_by
        )
        self.db.add(admin)
        self.db.commit()
        return admin
    
    def remove_admin(self, telegram_id, removed_by):
        """Деактивирует администратора"""
        admin = self.db.query(Admin).filter_by(telegram_id=telegram_id).first()
        if admin and admin.telegram_id != removed_by:  # Нельзя удалить себя
            admin.is_active = False
            self.db.commit()
            return True
        return False
    
    def get_all_admins(self):
        """Возвращает список всех активных администраторов"""
        return self.db.query(Admin).filter_by(is_active=True).all()
    
    def get_admin_stats(self):
        """Статистика по администраторам"""
        total = self.db.query(Admin).filter_by(is_active=True).count()
        admins = self.db.query(Admin).filter_by(role='admin', is_active=True).count()
        moderators = self.db.query(Admin).filter_by(role='moderator', is_active=True).count()
        
        return {
            'total': total,
            'admins': admins,
            'moderators': moderators
        }
    
    def initialize_super_admins(self):
        """Инициализирует супер-админов из переменной окружения"""
        admin_ids = os.environ.get('ADMIN_TELEGRAM_IDS', '')
        if not admin_ids:
            return
        
        for telegram_id in admin_ids.split(','):
            try:
                telegram_id = int(telegram_id.strip())
                self.add_admin(
                    telegram_id=telegram_id,
                    username='super_admin',
                    full_name='Super Administrator',
                    role='admin',
                    created_by=0  # System
                )
            except ValueError:
                continue
