#!/usr/bin/env python
"""
Миграции базы данных
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import config
from database import init_db

def main():
    """Основная функция миграций"""
    print("🤺 Tolyatti Fencing - Миграции базы данных")
    print("=" * 50)
    
    print("🔄 Инициализация базы данных...")
    try:
        init_db()
        print("✅ База данных инициализирована")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())