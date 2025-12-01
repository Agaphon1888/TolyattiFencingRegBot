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
COPY runtime.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY . .

# Создание необходимых директорий
RUN mkdir -p templates

# Установка прав на исполнение скриптов
RUN chmod +x migrations.py

# Проверка миграций при старте
RUN python migrations.py

EXPOSE 10000

# Команда запуска
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--workers", "2", "--threads", "4", "--timeout", "120", "app:app"]
