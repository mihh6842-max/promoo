#!/bin/bash
# Скрипт для остановки бота

cd "$(dirname "$0")"

echo "Остановка PromoBot..."

# Находим процесс бота
PID=$(pgrep -f "python.*main.py")

if [ -z "$PID" ]; then
    echo "Бот не запущен"
    exit 0
fi

# Отправляем сигнал остановки
kill -SIGINT $PID

echo "Отправлен сигнал остановки (PID: $PID)"
echo "Ожидание завершения..."

# Ждем 10 секунд
sleep 10

# Проверяем, завершился ли процесс
if pgrep -f "python.*main.py" > /dev/null; then
    echo "Процесс не завершился, принудительная остановка..."
    kill -9 $PID
    echo "✓ Бот остановлен принудительно"
else
    echo "✓ Бот остановлен корректно"
fi

# Закрываем screen сессию если была
if command -v screen &> /dev/null; then
    screen -S promobot -X quit 2>/dev/null
fi
