FROM python:3.12-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY . .

# Создаем директории
RUN mkdir -p templates

# Открываем порт
EXPOSE 10000

# Запускаем приложение с СИНХРОННЫМ воркером
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--workers", "1", "--worker-class", "sync", "--timeout", "120", "app:app"]
