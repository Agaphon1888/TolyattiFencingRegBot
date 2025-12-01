from config import config
from database import get_session, Registration, init_db

def create_test_data():
    session = get_session()
    try:
        if session.query(Registration).filter_by(phone='+79991234567').first():
            print("Тестовые данные уже есть")
            return

        regs = [
            Registration(telegram_id=999999999, username='test1', full_name='Иван Иванов', weapon_type='Сабля', category='Взрослые', age_group='19+ лет', phone='+79991234567', experience='5 лет', status='pending'),
            Registration(telegram_id=888888888, username='test2', full_name='Анна Петрова', weapon_type='Рапира', category='Юниоры', age_group='16-18 лет', phone='+79997654321', experience='КМС', status='confirmed'),
        ]
        for r in regs:
            session.add(r)
        session.commit()
        print("✅ Тестовые данные добавлены")
    finally:
        session.close()


if __name__ == "__main__":
    init_db()
    create_test_data()
