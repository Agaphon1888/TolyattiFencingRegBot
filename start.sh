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

# Показываем информацию для доступа
echo ""
echo "🔑 Информация для доступа к админ-панели:"
echo "Ссылка с токеном: https://tolyattifencingregbot.onrender.com/admin?token=b1e807aeb2b1425995b17e1694296448"
echo "Простая версия: https://tolyattifencingregbot.onrender.com/admin?simple=1"
echo ""

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
