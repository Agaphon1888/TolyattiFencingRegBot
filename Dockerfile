# Используем официальный стабильный образ Python 3.12
FROM python:3.12-slim

# Устанавливаем системные зависимости
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Настройка локали
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем requirements.txt и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код проекта
COPY . .

# Создаем директорию для шаблонов
RUN mkdir -p templates

# Экспорт порта
EXPOSE 10000

# Запуск приложения через gunicorn
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:$PORT --workers 2 app:app"]
