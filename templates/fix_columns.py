#!/usr/bin/env python
"""
Скрипт для исправления схемы базы данных
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
        
        # 1. Проверяем и добавляем столбец admin_comment в registrations
        print("1. Проверяем столбец 'admin_comment' в таблице 'registrations'...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'registrations' AND column_name = 'admin_comment'
        """)
        
        if not cursor.fetchone():
            print("   ⚠️ Столбец 'admin_comment' не найден, добавляем...")
            cursor.execute("ALTER TABLE registrations ADD COLUMN admin_comment TEXT")
            print("   ✅ Столбец 'admin_comment' добавлен")
        else:
            print("   ✅ Столбец 'admin_comment' уже существует")
        
        print("\n✅ Схема базы данных проверена!")
        
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
