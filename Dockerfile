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

# Запускаем приложение через Waitress (синхронный WSGI сервер)
CMD ["waitress-serve", "--host=0.0.0.0", "--port=10000", "app:app"]
