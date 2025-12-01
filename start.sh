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
python migrations.py

# Устанавливаем вебхук (если сервер уже запускается)
echo "🌐 Настройка вебхука..."
sleep 5  # Даем время серверу запуститься
curl -s "https://tolyattifencingregbot.onrender.com/set_webhook" || echo "Webhook setup skipped"

# Запуск основного приложения
echo "🚀 Запуск приложения..."
exec gunicorn --bind 0.0.0.0:10000 --workers 1 --timeout 120 app:app
