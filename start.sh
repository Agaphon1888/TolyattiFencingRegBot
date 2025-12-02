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

# Исправление схемы базы данных - добавляем created_at если его нет
echo "🔧 Исправление схемы базы данных (добавляем created_at)..."
if [ -f "fix_created_at.py" ]; then
    python fix_created_at.py
else
    echo "⚠️ Файл fix_created_at.py не найден"
fi

# Дополнительное исправление схемы
echo "🔧 Дополнительное исправление схемы базы данных..."
if [ -f "templates/fix_columns.py" ]; then
    # Добавляем текущую директорию в PYTHONPATH для импорта config
    export PYTHONPATH="/app:$PYTHONPATH"
    python templates/fix_columns.py
elif [ -f "fix_columns.py" ]; then
    python fix_columns.py
else
    echo "⚠️ Файл fix_columns.py не найден, пропускаем исправление схемы"
fi

# Проверяем структуру базы данных
echo "🔍 Проверка структуры базы данных..."
if [ -f "check_db.py" ]; then
    python check_db.py
fi

# Показываем информацию для доступа
echo ""
echo "🔑 Информация для доступа к админ-панели:"
echo "Ссылка с токеном: https://$(echo $RENDER_SERVICE_NAME || echo 'tolyattifencingregbot').onrender.com/admin?token=b1e807aeb2b1425995b17e1694296448"
echo "Простая версия: https://$(echo $RENDER_SERVICE_NAME || echo 'tolyattifencingregbot').onrender.com/admin?simple=1"
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
