# Инструкция по запуску бота на хостинге

## Исправлена проблема с зависанием Playwright

**Что было исправлено:**
- Добавлен таймаут 30 секунд на инициализацию Playwright
- Если Playwright не запустится, автоматически используется Simple парсер (BeautifulSoup)
- Бот больше не будет зависать при запуске

---

## Вариант 1: Запуск через screen (рекомендуется)

### 1. Сделайте скрипты исполняемыми:
```bash
chmod +x start_bot.sh stop_bot.sh status_bot.sh
```

### 2. Запустите бота:
```bash
./start_bot.sh
```

### 3. Проверьте статус:
```bash
./status_bot.sh
```

### 4. Просмотр логов в реальном времени:
```bash
# Если запущен через screen:
screen -r promobot

# Выйти из screen (не останавливая бота):
# Нажмите: Ctrl+A, затем D

# Или смотрите файлы логов:
tail -f logs/bot_$(date +%Y-%m-%d).log
```

### 5. Остановка бота:
```bash
./stop_bot.sh
```

---

## Вариант 2: Запуск через systemd (автозапуск)

### 1. Отредактируйте promobot.service:
```bash
nano promobot.service
```

Замените:
- `YOUR_USERNAME` на ваше имя пользователя
- `/path/to/promo-bot/host` на полный путь к папке с ботом

### 2. Скопируйте сервис в systemd:
```bash
sudo cp promobot.service /etc/systemd/system/
```

### 3. Перезагрузите systemd:
```bash
sudo systemctl daemon-reload
```

### 4. Включите автозапуск:
```bash
sudo systemctl enable promobot
```

### 5. Запустите бот:
```bash
sudo systemctl start promobot
```

### 6. Проверьте статус:
```bash
sudo systemctl status promobot
```

### 7. Просмотр логов:
```bash
# Логи systemd:
sudo journalctl -u promobot -f

# Логи бота:
tail -f logs/bot_$(date +%Y-%m-%d).log
```

### 8. Остановка:
```bash
sudo systemctl stop promobot
```

### 9. Отключение автозапуска:
```bash
sudo systemctl disable promobot
```

---

## Вариант 3: Простой запуск через nohup

```bash
nohup python3 main.py > bot_output.log 2>&1 &
```

Просмотр логов:
```bash
tail -f bot_output.log
```

Остановка:
```bash
pkill -f "python.*main.py"
```

---

## Проверка работы бота

### 1. Проверка процесса:
```bash
ps aux | grep main.py
```

### 2. Проверка логов:
```bash
# Последние 50 строк:
tail -50 logs/bot_$(date +%Y-%m-%d).log

# В реальном времени:
tail -f logs/bot_$(date +%Y-%m-%d).log
```

### 3. Проверка памяти:
```bash
ps aux --sort=-%mem | grep python
```

---

## Решение проблем

### Бот не запускается:
1. Проверьте зависимости:
   ```bash
   pip3 install -r requirements.txt
   ```

2. Проверьте .env файл:
   ```bash
   cat .env
   ```

3. Проверьте права на файлы:
   ```bash
   ls -la
   ```

### Бот падает при парсинге:
- **Исправлено!** Теперь есть таймаут на Playwright
- Simple парсер (BeautifulSoup) работает всегда
- Бот автоматически переключается на Simple парсер если Playwright не работает

### Нет уведомлений:
1. Проверьте настройки уведомлений в боте: `/settings`
2. Проверьте логи на ошибки Telegram API

---

## Мониторинг

### Автоматическая проверка и перезапуск (cron):

Создайте скрипт `check_bot.sh`:
```bash
#!/bin/bash
if ! pgrep -f "python.*main.py" > /dev/null; then
    cd /path/to/promo-bot/host
    ./start_bot.sh
    echo "$(date): Бот был перезапущен" >> logs/restarts.log
fi
```

Сделайте исполняемым:
```bash
chmod +x check_bot.sh
```

Добавьте в crontab (каждые 5 минут):
```bash
crontab -e
```

Добавьте строку:
```
*/5 * * * * /path/to/promo-bot/host/check_bot.sh
```

---

## Полезные команды

```bash
# Статус бота
./status_bot.sh

# Перезапуск бота
./stop_bot.sh && sleep 5 && ./start_bot.sh

# Просмотр всех screen сессий
screen -list

# Отключение от screen (не останавливая)
Ctrl+A, затем D

# Подключение к screen
screen -r promobot

# Мониторинг ресурсов
htop

# Очистка старых логов (старше 30 дней)
find logs/ -name "*.log" -mtime +30 -delete
```
