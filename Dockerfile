# Используем стабильный образ Python 3.11 (slim — легковесный)
FROM python:3.11-slim

# Устанавливаем системные зависимости
# Необходимы для компиляции пакетов вроде cryptography, Pillow (если будете добавлять)
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

# Настройка локали (важно для корректной работы Python)
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Рабочая директория внутри контейнера
WORKDIR /app

# Копируем requirements.txt и устанавливаем зависимости
COPY requirements.txt .

# Обновляем pip и устанавливаем зависимости без кеша
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код проекта в контейнер
COPY . .

# Делаем все файлы читаемыми (на случай проблем с правами)
RUN chmod +r . -R

# Экспорт порта (Render прочитает $PORT)
EXPOSE 10000

# Запуск приложения через gunicorn с асинхронным воркером
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:$PORT --workers 1 --worker-class aiohttp.GunicornWebWorker app:app"]
