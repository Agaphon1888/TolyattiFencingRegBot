#!/usr/bin/env python
"""
Скрипт для добавления колонки created_at в таблицу registrations
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import config
import psycopg2

def fix_created_at_column():
    """Добавляет отсутствующий столбец created_at в базу данных"""
    
    db_url = config.DATABASE_URL
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    
    print("🔧 Добавление колонки created_at в таблицу registrations...")
    
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Проверяем существование колонки created_at
        print("1. Проверяем столбец 'created_at' в таблице 'registrations'...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'registrations' AND column_name = 'created_at'
        """)
        
        if not cursor.fetchone():
            print("   ⚠️ Столбец 'created_at' не найден, добавляем...")
            cursor.execute("ALTER TABLE registrations ADD COLUMN created_at TIMESTAMP DEFAULT NOW()")
            print("   ✅ Столбец 'created_at' добавлен")
        else:
            print("   ✅ Столбец 'created_at' уже существует")
        
        print("\n✅ Схема базы данных исправлена!")
        
        # Проверяем текущие колонки
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'registrations' 
            ORDER BY ordinal_position
        """)
        print("\n📊 Текущая структура таблицы registrations:")
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
    fix_created_at_column()
