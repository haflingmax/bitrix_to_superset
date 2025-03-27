FROM python:3.9-slim

WORKDIR /app

# Установка зависимостей системы
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Установка Python-зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY . .

# Порт
EXPOSE 5000

# Проверка здоровья
HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl -f http://localhost:5000/status || exit 1

# Запуск через Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]