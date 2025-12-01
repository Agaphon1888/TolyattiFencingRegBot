import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import config
from database import init_db, get_session, Registration, Admin, get_db_stats

def create_test_data():
    session = get_session()
    try:
        if session.query(Registration).filter_by(phone='+79991234567').first():
            print("⚠️  Тестовые данные уже есть")
            return

        test_data = [
            Registration(telegram_id=999999999, username='test1', full_name='Иван Иванов', weapon_type='Сабля', category='Взрослые', age_group='19+ лет', phone='+79991234567', experience='5 лет, 1 разряд', status='pending'),
            Registration(telegram_id=888888888, username='test2', full_name='Анна Петрова', weapon_type='Рапира', category='Юниоры', age_group='16-18 лет', phone='+79997654321', experience='3 года, КМС', status='confirmed'),
            Registration(telegram_id=777777777, username='test3', full_name='Алексей Сидоров', weapon_type='Шпага', category='Ветераны', age_group='19+ лет', phone='+79995555555', experience='10 лет, МС', status='rejected'),
        ]
        for r in test_data:
            session.add(r)
        session.commit()
        print(f"✅ {len(test_data)} тестовых записей добавлено")
    finally:
        session.close()

if __name__ == "__main__":
    init_db()
    create_test_data()
    stats = get_db_stats()
    print("📊 Статистика:", stats)
