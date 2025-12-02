FROM python:3.12-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Копирование файлов зависимостей
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY . .

# Создание необходимых директорий
RUN mkdir -p templates

# Проверка и исправление базы данных перед запуском
RUN python fix_created_at.py || echo "Предварительная проверка базы данных"

# Сделаем start.sh исполняемым
RUN chmod +x start.sh

EXPOSE 10000

# Команда запуска
CMD ["./start.sh"]
