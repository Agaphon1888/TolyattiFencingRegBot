#!/usr/bin/env python
"""
Скрипт для исправления схемы базы данных
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import config
import psycopg2

def fix_database_columns():
    """Добавляет отсутствующие столбцы в базу данных"""
    
    db_url = config.DATABASE_URL
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    
    print("🔧 Исправление схемы базы данных...")
    
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # 1. Проверяем и добавляем столбец username в registrations
        print("1. Проверяем столбец 'username' в таблице 'registrations'...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'registrations' AND column_name = 'username'
        """)
        
        if not cursor.fetchone():
            print("   ⚠️ Столбец 'username' не найден, добавляем...")
            cursor.execute("ALTER TABLE registrations ADD COLUMN username VARCHAR(100)")
            print("   ✅ Столбец 'username' добавлен")
        else:
            print("   ✅ Столбец 'username' уже существует")
        
        # 2. Проверяем и добавляем столбец updated_at в registrations
        print("\n2. Проверяем столбец 'updated_at' в таблице 'registrations'...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'registrations' AND column_name = 'updated_at'
        """)
        
        if not cursor.fetchone():
            print("   ⚠️ Столбец 'updated_at' не найден, добавляем...")
            cursor.execute("ALTER TABLE registrations ADD COLUMN updated_at TIMESTAMP DEFAULT NOW()")
            print("   ✅ Столбец 'updated_at' добавлен")
        else:
            print("   ✅ Столбец 'updated_at' уже существует")
        
        # 3. Проверяем и добавляем столбец created_by в admins
        print("\n3. Проверяем столбец 'created_by' в таблице 'admins'...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'admins' AND column_name = 'created_by'
        """)
        
        if not cursor.fetchone():
            print("   ⚠️ Столбец 'created_by' не найден, добавляем...")
            cursor.execute("ALTER TABLE admins ADD COLUMN created_by BIGINT")
            print("   ✅ Столбец 'created_by' добавлен")
        else:
            print("   ✅ Столбец 'created_by' уже существует")
        
        print("\n✅ Схема базы данных исправлена!")
        
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
    fix_database_columns()
