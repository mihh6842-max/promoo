#!/bin/bash
# Скрипт для проверки статуса бота

cd "$(dirname "$0")"

echo "=== Статус PromoBot ==="
echo ""

# Проверяем процесс
PID=$(pgrep -f "python.*main.py")

if [ -z "$PID" ]; then
    echo "❌ Бот не запущен"
    echo ""
    echo "Для запуска: ./start_bot.sh"
else
    echo "✓ Бот запущен (PID: $PID)"

    # Показываем информацию о процессе
    echo ""
    echo "=== Информация о процессе ==="
    ps -p $PID -o pid,ppid,cmd,%mem,%cpu,etime

    # Проверяем screen сессию
    if command -v screen &> /dev/null; then
        if screen -list | grep -q promobot; then
            echo ""
            echo "✓ Screen сессия активна"
            echo "Для просмотра: screen -r promobot"
        fi
    fi
fi

echo ""
echo "=== Последние логи ==="
if [ -f "logs/bot_$(date +%Y-%m-%d).log" ]; then
    tail -20 "logs/bot_$(date +%Y-%m-%d).log"
else
    echo "Лог-файл не найден"
fi
