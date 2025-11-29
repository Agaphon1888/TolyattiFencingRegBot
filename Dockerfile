# Используем официальный стабильный образ Python 3.10
FROM python:3.10-slim

# Устанавливаем системные зависимости (включая поддержку imghdr, SSL и др.)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libssl-dev \
        libffi-dev \
        zlib1g-dev \
        libjpeg-dev \
        libpng-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Настройка локали (чтобы избежать предупреждений)
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем requirements.txt и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код проекта
COPY . .

# Убедимся, что файлы исполняемы
RUN chmod +r . -R

# Экспорт порта (Render передаёт настоящий PORT через переменную окружения)
EXPOSE 10000

# Запуск приложения через gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "--workers", "2", "app:app"]
