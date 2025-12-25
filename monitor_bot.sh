#!/bin/bash
# Скрипт мониторинга и автоматического перезапуска бота

cd "$(dirname "$0")"

LOG_FILE="logs/monitor.log"
BOT_PROCESS="python.*main.py"

# Функция логирования
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Проверяем, запущен ли бот
if pgrep -f "$BOT_PROCESS" > /dev/null; then
    # Бот работает

    # Проверяем использование памяти (предупреждение если больше 500MB)
    MEM_USAGE=$(ps aux | grep -E "$BOT_PROCESS" | grep -v grep | awk '{print $6}')
    if [ ! -z "$MEM_USAGE" ]; then
        MEM_MB=$((MEM_USAGE / 1024))
        if [ $MEM_MB -gt 500 ]; then
            log "⚠️ WARNING: Высокое использование памяти: ${MEM_MB}MB"
        fi
    fi

    # Проверяем свежесть логов (бот должен писать логи)
    TODAY_LOG="logs/bot_$(date +%Y-%m-%d).log"
    if [ -f "$TODAY_LOG" ]; then
        # Проверяем, есть ли записи за последние 10 минут
        RECENT_LOGS=$(find "$TODAY_LOG" -mmin -10)
        if [ -z "$RECENT_LOGS" ]; then
            log "⚠️ WARNING: Нет логов за последние 10 минут - возможно бот завис"
            log "🔄 Перезапускаем бота..."

            # Останавливаем
            pkill -SIGTERM -f "$BOT_PROCESS"
            sleep 5
            pkill -9 -f "$BOT_PROCESS" 2>/dev/null

            # Запускаем
            ./start_bot.sh
            log "✅ Бот перезапущен"
        fi
    fi
else
    # Бот не запущен - запускаем
    log "❌ Бот не запущен! Запускаем..."
    ./start_bot.sh

    # Даем время на запуск
    sleep 10

    # Проверяем успешность запуска
    if pgrep -f "$BOT_PROCESS" > /dev/null; then
        log "✅ Бот успешно запущен"
    else
        log "❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось запустить бота!"
        log "Проверьте логи: tail -f logs/bot_$(date +%Y-%m-%d).log"
    fi
fi
