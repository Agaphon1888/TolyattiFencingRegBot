from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
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
    experience = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default='pending')

class Database:
    def __init__(self):
        db_path = os.environ.get('DATABASE_URL', 'sqlite:///registrations.db')
        if db_path.startswith('postgres://'):
            db_path = db_path.replace('postgres://', 'postgresql://', 1)
        self.engine = create_engine(db_path)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
    
    def add_registration(self, data):
        registration = Registration(**data)
        self.session.add(registration)
        self.session.commit()
        return registration
    
    def get_user_registrations(self, telegram_id):
        return self.session.query(Registration).filter_by(
            telegram_id=telegram_id
        ).all()
    
    def get_all_registrations(self):
        return self.session.query(Registration).all()
