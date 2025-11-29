# Используем официальный образ Python
FROM python:3.10-slim

# Устанавливаем нужные системные зависимости
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libjpeg-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Копируем зависимости и устанавливаем
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY . .

# Экспорт порта
EXPOSE 10000

# Запуск
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "app:app"]
