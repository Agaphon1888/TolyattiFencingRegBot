#!/usr/bin/env python
"""
Миграция для добавления таблицы событий
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import config
import psycopg2

def add_events_table():
    """Добавляет таблицу событий и связь с регистрациями"""
    
    db_url = config.DATABASE_URL
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    
    print("🎯 Создание таблицы событий...")
    
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # 1. Создаем таблицу событий
        print("1. Создаем таблицу 'events'...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id SERIAL PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                event_date DATE NOT NULL,
                description TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        print("   ✅ Таблица 'events' создана")
        
        # 2. Добавляем столбец event_id в registrations
        print("\n2. Добавляем столбец 'event_id' в 'registrations'...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'registrations' AND column_name = 'event_id'
        """)
        
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE registrations ADD COLUMN event_id INTEGER REFERENCES events(id)")
            print("   ✅ Столбец 'event_id' добавлен")
        else:
            print("   ✅ Столбец 'event_id' уже существует")
        
        # 3. Добавляем пример события
        print("\n3. Добавляем пример события...")
        cursor.execute("""
            INSERT INTO events (name, event_date, description, is_active) 
            VALUES ('Открытый турнир по фехтованию в Тольятти', CURRENT_DATE + INTERVAL '7 days', 'Ежегодный открытый турнир', TRUE)
            ON CONFLICT DO NOTHING
        """)
        
        print("\n✅ Миграция успешно выполнена!")
        
        # Показываем структуру
        print("\n📊 Структура таблицы events:")
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'events' 
            ORDER BY ordinal_position
        """)
        for col_name, col_type in cursor.fetchall():
            print(f"   - {col_name}: {col_type}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    add_events_table()
