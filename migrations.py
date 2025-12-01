#!/usr/bin/env python3
"""
Миграции базы данных для TolyattiFencingRegBot
"""

import os
import sys
from datetime import datetime

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import config
from database import init_db, get_session, Registration, Admin

def run_migrations():
    """Запуск миграций"""
    print("🔄 Запуск миграций базы данных...")
    
    try:
        # Инициализируем базу данных
        init_db()
        print("✅ База данных инициализирована")
        
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
        
    except Exception as e:
        print(f"❌ Ошибка создания тестовых данных: {e}")
        session.rollback()
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
            
    except Exception as e:
        print(f"❌ Ошибка получения статистики: {e}")
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
