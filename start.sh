#!/bin/bash
set -e

echo "🤺 Запуск Tolyatti Fencing Registration Bot..."

# Создаем папку templates если её нет
mkdir -p templates

# Перемещаем HTML файлы в templates, если они есть в корне
if [ -f "admin.html" ]; then
    mv admin.html templates/
fi
if [ -f "error.html" ]; then
    mv error.html templates/
fi

# Запуск миграций базы данных
echo "🔄 Выполнение миграций базы данных..."
python migrations.py init

# Запуск основного приложения
echo "🚀 Запуск приложения..."
exec gunicorn --bind 0.0.0.0:10000 \
    --workers 1 \
    --threads 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    app:app
