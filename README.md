# PromoBot - Минимальная сборка для хостинга

Оптимизированная версия бота для деплоя на хостинг.

## Размер
- **4.3 MB** (вместо 130+ MB с документацией)
- Баннеры сжаты: 34.5 MB → 4 MB (88% экономии)

## Установка

### 1. Загрузите файлы на сервер
```bash
# Распакуйте архив в папку проекта
```

### 2. Создайте виртуальное окружение
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows
```

### 3. Установите зависимости
```bash
pip install -r requirements.txt
python -m playwright install chromium
```

### 4. Настройте переменные окружения
Создайте файл `.env`:
```env
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=123456789,987654321
DATABASE_URL=sqlite+aiosqlite:///data/promo_bot.db
LOG_LEVEL=INFO
```

### 5. Запустите бота
```bash
python main.py
```

## Структура
```
host/
├── bot/          # Обработчики бота
├── database/     # Модели БД
├── parser/       # Парсер промокодов
├── utils/        # Утилиты
├── baners/       # Баннеры (JPEG, 4MB)
├── data/         # База данных
├── logs/         # Логи
├── config.py     # Конфигурация
├── main.py       # Точка входа
└── requirements.txt
```

## Отличия от полной версии
- Удалены тесты
- Удалена документация (вся в папке deploy/)
- Удалены Docker файлы
- Баннеры конвертированы из PNG в JPEG (качество 90%)
- Удалены __pycache__ и логи

## Поддержка
Полная документация в папке `deploy/`
