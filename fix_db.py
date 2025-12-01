#!/usr/bin/env python
import psycopg2
import os
from config import config

def fix_database():
    """Исправляет проблемы с базой данных вручную"""
    db_url = config.DATABASE_URL
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    
    print(f"Подключаемся к БД: {db_url.split('@')[1] if '@' in db_url else db_url}")
    
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Исправляем тип telegram_id в таблице admins
        print("1. Проверяем тип telegram_id в таблице admins...")
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'admins' AND column_name = 'telegram_id'
        """)
        row = cursor.fetchone()
        if row:
            print(f"   Текущий тип: {row[1]}")
            if row[1] == 'integer':
                print("   ⚠️ Меняем integer на bigint...")
                try:
                    cursor.execute("ALTER TABLE admins ALTER COLUMN telegram_id TYPE BIGINT")
                    print("   ✅ Изменено на BIGINT")
                except Exception as e:
                    print(f"   ❌ Ошибка: {e}")
        else:
            print("   Колонка telegram_id не найдена")
        
        # Создаем таблицу admins если её нет
        print("\n2. Проверяем таблицу admins...")
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'admins'
            )
        """)
        if not cursor.fetchone()[0]:
            print("   ⚠️ Таблица admins не существует, создаем...")
            cursor.execute("""
                CREATE TABLE admins (
                    id BIGSERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username VARCHAR(100),
                    full_name VARCHAR(200),
                    role VARCHAR(50) DEFAULT 'moderator',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    created_by BIGINT
                )
            """)
            print("   ✅ Таблица admins создана")
        
        # Создаем таблицу registrations если её нет
        print("\n3. Проверяем таблицу registrations...")
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'registrations'
            )
        """)
        if not cursor.fetchone()[0]:
            print("   ⚠️ Таблица registrations не существует, создаем...")
            cursor.execute("""
                CREATE TABLE registrations (
                    id BIGSERIAL PRIMARY KEY,
                    telegram_id BIGINT NOT NULL,
                    username VARCHAR(100),
                    full_name VARCHAR(200) NOT NULL,
                    weapon_type VARCHAR(50) NOT NULL,
                    category VARCHAR(50) NOT NULL,
                    age_group VARCHAR(50) NOT NULL,
                    phone VARCHAR(20) NOT NULL,
                    experience TEXT NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            print("   ✅ Таблица registrations создана")
        
        print("\n✅ База данных проверена и исправлена!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    fix_database()
