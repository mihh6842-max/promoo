#!/bin/bash
# Скрипт для запуска бота на хостинге в фоновом режиме

cd "$(dirname "$0")"

# Проверяем, запущен ли уже бот
if pgrep -f "python.*main.py" > /dev/null; then
    echo "Бот уже запущен!"
    exit 1
fi

echo "Запуск PromoBot в фоновом режиме..."

# Запуск в screen (если установлен)
if command -v screen &> /dev/null; then
    screen -dmS promobot python3 main.py
    echo "✓ Бот запущен в screen сессии 'promobot'"
    echo "Для просмотра логов: screen -r promobot"
    echo "Для выхода из screen: Ctrl+A, затем D"
# Альтернатива: nohup (если screen не установлен)
else
    nohup python3 main.py > bot_output.log 2>&1 &
    echo "✓ Бот запущен через nohup"
    echo "Для просмотра логов: tail -f bot_output.log"
fi

echo ""
echo "Для остановки бота: ./stop_bot.sh"
