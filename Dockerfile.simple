FROM python:3.11-slim

WORKDIR /app

# Установи зависимости системы (без Chrome)
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Копируй requirements.txt
COPY requirements.txt .

# Установи Python зависимости (без playwright)
RUN grep -v "playwright" requirements.txt > requirements_simple.txt && \
    pip install --no-cache-dir -r requirements_simple.txt

# Копируй всё остальное
COPY . .

# Запусти бот
CMD ["python", "main.py"]
