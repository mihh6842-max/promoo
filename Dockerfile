FROM python:3.11-slim

WORKDIR /app

# Копируй requirements.txt
COPY requirements.txt .

# Установи Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируй всё остальное
COPY . .

# Запусти бот
CMD ["python", "main.py"]
