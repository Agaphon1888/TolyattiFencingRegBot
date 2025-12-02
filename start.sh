#!/bin/bash
set -e

echo "🤺 Запуск Tolyatti Fencing Registration Bot..."

# Установка порта для Render
export PORT=${PORT:-10000}

# Создаем папку templates если её нет
mkdir -p templates

# Запуск миграций базы данных
echo "🔄 Выполнение миграций базы данных..."
python migrations.py init

# Запуск основного приложения
echo "🚀 Запуск приложения на порту $PORT..."
exec gunicorn --bind 0.0.0.0:$PORT \
    --workers 1 \
    --threads 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --worker-class sync \
    app:app