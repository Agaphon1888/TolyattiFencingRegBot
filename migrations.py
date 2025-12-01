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
            Registration(
                telegram_id=666666666,
                username='test4',
                full_name='Мария Кузнецова',
                weapon_type='Сабля',
                category='Юниоры',
                age_group='13-15 лет',
                phone='+79992223344',
                experience='2 года, II разряд',
                status='pending',
                created_at=datetime.utcnow() - timedelta(hours=6)
            ),
            Registration(
                telegram_id=555555555,
                username='test5',
                full_name='Алексей Смирнов',
                weapon_type='Рапира',
                category='Ветераны',
                age_group='19+ лет',
                phone='+79991112233',
                experience='15 лет, ЗМС, чемпион России',
                status='confirmed',
                created_at=datetime.utcnow() - timedelta(hours=3)
            )
        ]
        
        # Добавляем случайные заявки для наполнения
        first_names = ['Александр', 'Дмитрий', 'Михаил', 'Андрей', 'Сергей', 'Владимир', 
                      'Екатерина', 'Ольга', 'Наталья', 'Елена', 'Татьяна', 'Ирина']
        last_names = ['Соколов', 'Попов', 'Лебедев', 'Козлов', 'Новиков', 'Морозов',
                     'Волков', 'Соловьев', 'Васильев', 'Зайцев', 'Павлов', 'Семенов']
        weapons = config.WEAPON_TYPES
        categories = config.CATEGORIES
        age_groups = config.AGE_GROUPS
        statuses = ['pending', 'confirmed', 'rejected']
        experiences = [
            '1 год, начинающий',
            '2 года, III разряд',
            '3 года, II разряд',
            '4 года, I разряд',
            '5 лет, КМС',
            '6 лет, МС',
            '8 лет, ЗМС',
            '10 лет, опытный спортсмен'
        ]
        
        for i in range(10):  # 10 случайных заявок
            reg = Registration(
                telegram_id=1000000000 + i,
                username=f'user_{i}',
                full_name=f'{random.choice(last_names)} {random.choice(first_names)}',
                weapon_type=random.choice(weapons),
                category=random.choice(categories),
                age_group=random.choice(age_groups),
                phone=f'+7999{random.randint(1000000, 9999999)}',
                experience=random.choice(experiences),
                status=random.choice(statuses),
                created_at=datetime.utcnow() - timedelta(days=random.randint(0, 30))
            )
            test_registrations.append(reg)
        
        # Добавляем все заявки
        for reg in test_registrations:
            session.add(reg)
        
        print(f"✅ Добавлено {len(test_registrations)} тестовых заявок")
        return True


def add_test_admins():
    """Добавление тестовых администраторов"""
    print("🔄 Добавление тестовых администраторов...")
    
    with session_scope() as session:
        test_admins = [
            Admin(
                telegram_id=111111111,
                username='admin_test1',
                full_name='Тестовый Админ 1',
                role='admin',
                is_active=True,
                created_by=0
            ),
            Admin(
                telegram_id=222222222,
                username='admin_test2',
                full_name='Тестовый Админ 2',
                role='moderator',
                is_active=True,
                created_by=111111111
            )
        ]
        
        added_count = 0
        for admin in test_admins:
            if not session.query(Admin).filter_by(telegram_id=admin.telegram_id).first():
                session.add(admin)
                added_count += 1
        
        if added_count > 0:
            print(f"✅ Добавлено {added_count} тестовых администраторов")
        else:
            print("ℹ️ Тестовые администраторы уже существуют")
        
        return added_count > 0


def clear_test_data():
    """Очистка тестовых данных"""
    confirmation = input("⚠️ Вы уверены, что хотите удалить все тестовые данные? (yes/no): ")
    if confirmation.lower() != 'yes':
        print("❌ Операция отменена")
        return
    
    with session_scope() as session:
        # Удаляем тестовые заявки
        test_phones = ['+79991234567', '+79997654321', '+79995554433', '+79992223344', '+79991112233']
        deleted_count = 0
        
        for phone in test_phones:
            regs = session.query(Registration).filter_by(phone=phone).all()
            for reg in regs:
                session.delete(reg)
                deleted_count += 1
        
        # Удаляем тестовых админов
        test_admin_ids = [111111111, 222222222]
        for admin_id in test_admin_ids:
            admin = session.query(Admin).filter_by(telegram_id=admin_id).first()
            if admin:
                session.delete(admin)
                deleted_count += 1
        
        print(f"✅ Удалено {deleted_count} тестовых записей")


def show_stats():
    """Показать статистику базы данных"""
    from database import get_database_stats
    
    stats = get_database_stats()
    
    print("\n📊 Статистика базы данных:")
    print("=" * 40)
    print(f"Всего заявок: {stats.get('registrations_count', 0)}")
    print(f"  • Ожидают: {stats.get('pending_count', 0)}")
    print(f"  • Подтверждены: {stats.get('confirmed_count', 0)}")
    print(f"  • Отклонены: {stats.get('rejected_count', 0)}")
    print(f"Администраторов: {stats.get('admins_count', 0)}")
    
    if 'last_registration' in stats:
        last_date = datetime.fromisoformat(stats['last_registration'].replace('Z', '+00:00'))
        print(f"Последняя заявка: {last_date.strftime('%d.%m.%Y %H:%M')}")
    
    print("=" * 40)


def fix_database_issues():
    """Исправление проблем с базой данных"""
    print("🔧 Исправление проблем с БД...")
    
    from database import fix_database_schema, initialize_super_admins
    
    try:
        # Инициализируем БД (повторно)
        init_db()
        
        # Исправляем схему
        fix_database_schema()
        
        # Инициализируем админов
        initialize_super_admins()
        
        print("✅ Проблемы с БД исправлены")
        return True
    except Exception as e:
        print(f"❌ Ошибка при исправлении БД: {e}")
        return False


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
            add_test_admins()
            show_stats()
            
        elif command == 'clear_test':
            init_db()
            clear_test_data()
            
        elif command == 'stats':
            init_db()
            show_stats()
            
        elif command == 'fix':
            fix_database_issues()
            show_stats()
            
        elif command == 'help':
            print("Доступные команды:")
            print("  init       - Инициализация базы данных")
            print("  test_data  - Создание тестовых данных")
            print("  clear_test - Удаление тестовых данных")
            print("  stats      - Показать статистику")
            print("  fix        - Исправить проблемы с БД")
            print("  help       - Показать эту справку")
            
        else:
            print(f"❌ Неизвестная команда: {command}")
            print("Используйте: python migrations.py [init|test_data|clear_test|stats|fix|help]")
    
    else:
        # По умолчанию: инициализация и тестовые данные
        print("🔄 Полная инициализация...")
        init_db()
        create_test_data()
        add_test_admins()
        show_stats()


if __name__ == "__main__":
    main()
