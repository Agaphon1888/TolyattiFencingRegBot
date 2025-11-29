from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

Base = declarative_base()

class Registration(Base):
    __tablename__ = 'registrations'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, nullable=False)
    username = Column(String(100))
    full_name = Column(String(200), nullable=False)
    weapon_type = Column(String(50), nullable=False)
    category = Column(String(50), nullable=False)
    age_group = Column(String(50), nullable=False)
    phone = Column(String(20), nullable=False)
    experience = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default='pending')
    notes = Column(Text)

class Admin(Base):
    __tablename__ = 'admins'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))
    full_name = Column(String(200))
    role = Column(String(50), default='moderator')
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer)

class Database:
    def __init__(self):
        db_path = os.environ.get('DATABASE_URL', 'sqlite:///registrations.db')
        if db_path.startswith('postgres://'):
            db_path = db_path.replace('postgres://', 'postgresql://', 1)
        self.engine = create_engine(db_path)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Инициализация менеджера администраторов
        self.admin_manager = AdminManager(self.session)
        self.admin_manager.initialize_super_admins()
    
    def add_registration(self, data):
        registration = Registration(**data)
        self.session.add(registration)
        self.session.commit()
        return registration
    
    def get_user_registrations(self, telegram_id):
        return self.session.query(Registration).filter_by(
            telegram_id=telegram_id
        ).order_by(Registration.created_at.desc()).all()
    
    def get_all_registrations(self):
        return self.session.query(Registration).order_by(
            Registration.created_at.desc()
        ).all()
    
    def get_pending_registrations(self):
        return self.session.query(Registration).filter_by(
            status='pending'
        ).order_by(Registration.created_at.desc()).all()
    
    def update_registration_status(self, registration_id, status, notes=None):
        registration = self.session.query(Registration).get(registration_id)
        if registration:
            registration.status = status
            if notes:
                registration.notes = notes
            self.session.commit()
            return True
        return False
    
    def get_stats(self):
        total = self.session.query(Registration).count()
        pending = self.session.query(Registration).filter_by(status='pending').count()
        confirmed = self.session.query(Registration).filter_by(status='confirmed').count()
        rejected = self.session.query(Registration).filter_by(status='rejected').count()
        
        # Статистика по оружию
        weapons = self.session.query(
            Registration.weapon_type,
            Registration.status
        ).all()
        
        weapon_stats = {}
        for weapon, status in weapons:
            if weapon not in weapon_stats:
                weapon_stats[weapon] = {'total': 0, 'pending': 0, 'confirmed': 0, 'rejected': 0}
            weapon_stats[weapon]['total'] += 1
            weapon_stats[weapon][status] += 1
        
        return {
            'total': total,
            'pending': pending,
            'confirmed': confirmed,
            'rejected': rejected,
            'weapons': weapon_stats
        }

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
        if admin and admin.telegram_id != removed_by:
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
                    created_by=0
                )
            except ValueError:
                continue
