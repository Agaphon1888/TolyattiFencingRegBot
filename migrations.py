#!/usr/bin/env python
"""
Миграции базы данных и тестовые данные
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import config
from database import get_session, Registration, Admin, init_db, session_scope
from datetime import datetime, timedelta
import random


def create_test_data():
    """Создание тестовых данных"""
    print("🔄 Создание тестовых данных...")
    
    with session_scope() as session:
        # Проверяем, нет ли уже тестовых данных
        if session.query(Registration).filter_by(phone='+79991234567').first():
            print("ℹ️ Тестовые данные уже существуют")
            return False
        
        # Тестовые заявки
        test_registrations = [
            Registration(
                telegram_id=999999999,
                username='test1',
                full_name='Иван Иванов',
                weapon_type='Сабля',
                category='Взрослые',
                age_group='19+ лет',
                phone='+79991234567',
                experience='5 лет, КМС, участник региональных соревнований',
                status='pending',
                created_at=datetime.utcnow() - timedelta(days=2)
            ),
            Registration(
                telegram_id=888888888,
                username='test2',
                full_name='Анна Петрова',
                weapon_type='Рапира',
                category='Юниоры',
                age_group='16-18 лет',
                phone='+79997654321',
                experience='3 года, I разряд, победитель городских соревнований',
                status='confirmed',
                created_at=datetime.utcnow() - timedelta(days=1)
            ),
            Registration(
                telegram_id=777777777,
                username='test3',
                full_name='Петр Сидоров',
                weapon_type='Шпага',
                category='Взрослые',
                age_group='19+ лет',
                phone='+79995554433',
                experience='7 лет, МС, участник всероссийских соревнований',
                status='rejected',
                created_at=datetime.utcnow() - timedelta(hours=12)
            ),
        ]
        
        # Добавляем заявки
        for reg in test_registrations:
            session.add(reg)
        
        print(f"✅ Добавлено {len(test_registrations)} тестовых заявок")
        return True


def show_stats():
    """Показать статистику базы данных"""
    print("\n📊 Статистика базы данных:")
    print("=" * 40)
    
    with session_scope() as session:
        total = session.query(Registration).count()
        pending = session.query(Registration).filter_by(status='pending').count()
        confirmed = session.query(Registration).filter_by(status='confirmed').count()
        rejected = session.query(Registration).filter_by(status='rejected').count()
        admins_count = session.query(Admin).count()
        
        print(f"Всего заявок: {total}")
        print(f"  • Ожидают: {pending}")
        print(f"  • Подтверждены: {confirmed}")
        print(f"  • Отклонены: {rejected}")
        print(f"Администраторов: {admins_count}")
        
        last_reg = session.query(Registration).order_by(Registration.created_at.desc()).first()
        if last_reg:
            print(f"Последняя заявка: {last_reg.created_at.strftime('%d.%m.%Y %H:%M')}")
    
    print("=" * 40)


def main():
    """Основная функция миграций"""
    print("🤺 Tolyatti Fencing - Миграции базы данных")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'init':
            print("🔄 Инициализация базы данных...")
            init_db()
            print("✅ База данных инициализирована")
            
        elif command == 'test_data':
            init_db()
            create_test_data()
            show_stats()
            
        elif command == 'stats':
            init_db()
            show_stats()
            
        elif command == 'help':
            print("Доступные команды:")
            print("  init       - Инициализация базы данных")
            print("  test_data  - Создание тестовых данных")
            print("  stats      - Показать статистику")
            print("  help       - Показать эту справку")
            
        else:
            print(f"❌ Неизвестная команда: {command}")
            print("Используйте: python migrations.py [init|test_data|stats|help]")
    
    else:
        # По умолчанию: инициализация
        print("🔄 Инициализация базы данных...")
        init_db()
        show_stats()


if __name__ == "__main__":
    main()
