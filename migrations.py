#!/usr/bin/env python3
"""
Миграции базы данных для TolyattiFencingRegBot
"""

import os
import sys
from datetime import datetime
from sqlalchemy import text, inspect

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import config
from database import init_db, get_session, Registration, Admin, engine

def run_migrations():
    """Запуск миграций"""
    print("🔄 Запуск миграций базы данных...")
    
    try:
        # Инициализируем базу данных
        from database import migrate_database, initialize_super_admins
        migrate_database()
        
        session = get_session()
        try:
            count = session.query(Registration).count()
            print(f"✅ Таблицы созданы. Записей в базе: {count}")
            
            # Инициализируем супер-админов
            initialize_super_admins()
            
            # Проверяем наличие админов
            admin_count = session.query(Admin).count()
            print(f"✅ Администраторов в базе: {admin_count}")
            
            # Создаем индексы для быстрого поиска
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_status ON registrations(status)",
                "CREATE INDEX IF NOT EXISTS idx_telegram_id ON registrations(telegram_id)",
                "CREATE INDEX IF NOT EXISTS idx_created_at ON registrations(created_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_weapon_type ON registrations(weapon_type)",
                "CREATE INDEX IF NOT EXISTS idx_category ON registrations(category)",
                "CREATE INDEX IF NOT EXISTS idx_admin_telegram_id ON admins(telegram_id)",
                "CREATE INDEX IF NOT EXISTS idx_admin_active ON admins(is_active)"
            ]
            
            for idx_sql in indexes:
                try:
                    session.execute(text(idx_sql))
                    print(f"  ✅ Индекс создан: {idx_sql.split('IF NOT EXISTS ')[1].split(' ON')[0]}")
                except Exception as e:
                    print(f"  ⚠️  Не удалось создать индекс: {e}")
            
            session.commit()
            print("✅ Индексы созданы")
            
        finally:
            session.close()
            
    except Exception as e:
        print(f"❌ Ошибка при миграциях: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def create_test_data():
    """Создание тестовых данных"""
    print("🧪 Создание тестовых данных...")
    
    session = get_session()
    try:
        # Проверяем, есть ли уже тестовые данные
        existing = session.query(Registration).filter_by(telegram_id=999999999).first()
        if existing:
            print("⚠️  Тестовые данные уже существуют")
            return
        
        test_registrations = [
            Registration(
                telegram_id=999999999,
                username='test_user',
                full_name='Иванов Иван Иванович',
                weapon_type='Сабля',
                category='Взрослые',
                age_group='19+ лет',
                phone='+79991234567',
                experience='Занимаюсь 5 лет, имею 1 разряд',
                status='pending',
                created_at=datetime.utcnow()
            ),
            Registration(
                telegram_id=888888888,
                username='test_user2',
                full_name='Петрова Анна Сергеевна',
                weapon_type='Рапира',
                category='Юниоры',
                age_group='16-18 лет',
                phone='+79997654321',
                experience='Занимаюсь 3 года, КМС',
                status='confirmed',
                created_at=datetime.utcnow()
            ),
            Registration(
                telegram_id=777777777,
                username='test_user3',
                full_name='Сидоров Алексей Владимирович',
                weapon_type='Шпага',
                category='Ветераны',
                age_group='19+ лет',
                phone='+79995555555',
                experience='Занимаюсь 10 лет, МС',
                status='rejected',
                created_at=datetime.utcnow()
            )
        ]
        
        for reg in test_registrations:
            session.add(reg)
        
        session.commit()
        print(f"✅ Добавлено {len(test_registrations)} тестовых записей")
        
    finally:
        session.close()

def show_stats():
    """Показать статистику базы данных"""
    print("📊 Статистика базы данных:")
    
    session = get_session()
    try:
        total_reg = session.query(Registration).count()
        pending = session.query(Registration).filter_by(status='pending').count()
        confirmed = session.query(Registration).filter_by(status='confirmed').count()
        rejected = session.query(Registration).filter_by(status='rejected').count()
        
        admins = session.query(Admin).filter_by(is_active=True).all()
        
        print(f"  📝 Заявок всего: {total_reg}")
        print(f"    ⏳ Ожидают: {pending}")
        print(f"    ✅ Подтверждены: {confirmed}")
        print(f"    ❌ Отклонены: {rejected}")
        print(f"  👥 Администраторов: {len(admins)}")
        
        for admin in admins:
            role_icon = "👑" if admin.role == 'admin' else "🛡️"
            print(f"    {role_icon} ID {admin.telegram_id} ({admin.role})")
            
    finally:
        session.close()

if __name__ == "__main__":
    print("🤺 Tolyatti Fencing Registration Bot - Миграции")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--test-data':
            create_test_data()
        elif sys.argv[1] == '--stats':
            show_stats()
        elif sys.argv[1] == '--help':
            print("Использование:")
            print("  python migrations.py           # Основные миграции")
            print("  python migrations.py --test-data  # Создать тестовые данные")
            print("  python migrations.py --stats      # Показать статистику")
            print("  python migrations.py --help       # Эта справка")
    else:
        run_migrations()
    
    print("=" * 50)
    print("✅ Миграции завершены!")
