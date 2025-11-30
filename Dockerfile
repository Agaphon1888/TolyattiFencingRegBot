# Используем Python 3.11 для стабильности
FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libssl-dev \
        libffi-dev \
        zlib1g-dev \
        libjpeg-dev \
        libpng-dev \
        libpython3-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Настройка локали
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Рабочая директория
WORKDIR /app

# Копируем зависимости и устанавливаем
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код
COPY . .

# Убедимся, что все файлы читаемы
RUN chmod +r . -R

# Экспорт порта
EXPOSE 10000

# Запуск через gunicorn с поддержкой async
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:$PORT --workers 1 --worker-class aiohttp.GunicornWebWorker app:app"]
