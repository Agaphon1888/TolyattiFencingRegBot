#!/usr/bin/env python
"""
Скрипт для проверки структуры базы данных
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import config
import psycopg2

def check_database_structure():
    """Проверяет структуру базы данных"""
    
    db_url = config.DATABASE_URL
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    
    print("🔍 Проверка структуры базы данных...")
    
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Проверяем таблицу registrations
        print("\n📊 Таблица 'registrations':")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'registrations' 
            ORDER BY ordinal_position
        """)
        
        columns = cursor.fetchall()
        if not columns:
            print("   ❌ Таблица 'registrations' не существует или пуста")
        else:
            for col_name, data_type, is_nullable, column_default in columns:
                print(f"   - {col_name}: {data_type} (nullable: {is_nullable})")
        
        # Проверяем таблицу admins
        print("\n👥 Таблица 'admins':")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'admins' 
            ORDER BY ordinal_position
        """)
        
        columns = cursor.fetchall()
        if not columns:
            print("   ❌ Таблица 'admins' не существует или пуста")
        else:
            for col_name, data_type, is_nullable, column_default in columns:
                print(f"   - {col_name}: {data_type} (nullable: {is_nullable})")
        
        # Проверяем данные
        print("\n📈 Статистика данных:")
        
        cursor.execute("SELECT COUNT(*) FROM registrations")
        reg_count = cursor.fetchone()[0]
        print(f"   Заявок: {reg_count}")
        
        cursor.execute("SELECT COUNT(*) FROM admins")
        admin_count = cursor.fetchone()[0]
        print(f"   Админов: {admin_count}")
        
        if reg_count > 0:
            cursor.execute("SELECT created_at FROM registrations LIMIT 1")
            sample_date = cursor.fetchone()[0]
            print(f"   Пример даты в created_at: {sample_date}")
        
        print("\n✅ Проверка структуры завершена!")
        
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
    check_database_structure()
