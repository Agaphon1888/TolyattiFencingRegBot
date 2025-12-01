#!/bin/bash
set -e

echo "🤺 Запуск Tolyatti Fencing Registration Bot..."

# Запуск миграций базы данных
echo "🔄 Выполнение миграций базы данных..."
python migrations.py

# Запуск основного приложения
echo "🚀 Запуск приложения..."
exec gunicorn --bind 0.0.0.0:10000 --workers 2 --threads 4 --timeout 120 app:app
