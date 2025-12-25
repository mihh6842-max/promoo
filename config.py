"""
Конфигурация бота
"""
from os import getenv
from dotenv import load_dotenv
from typing import List

load_dotenv()


class Config:
    """Основная конфигурация"""

    # Telegram Bot
    BOT_TOKEN: str = getenv("BOT_TOKEN", "")
    ADMIN_IDS: List[int] = [int(id) for id in getenv("ADMIN_IDS", "").split(",") if id]

    # Database
    DATABASE_URL: str = getenv("DATABASE_URL", "sqlite:///promo.db")

    # Redis
    REDIS_URL: str = getenv("REDIS_URL", "redis://localhost:6379")

    # Parser
    PARSE_INTERVAL: int = int(getenv("PARSE_INTERVAL", "21600"))  # 6 часов
    PARSER_USER_AGENT: str = getenv(
        "PARSER_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    TARGET_URL: str = "https://cuponcod.ru"

    # Logging
    LOG_LEVEL: str = getenv("LOG_LEVEL", "INFO")

    # Планировщик - парсинг один раз в день в полночь по МСК
    # Время указано в формате 24-часов (МСК)
    PARSE_TIMES = [
        "00:00",  # Полночь - единственный парсинг в сутки
    ]

    # Кэширование
    CACHE_TTL: int = 3600  # 1 час

    # Пагинация
    ITEMS_PER_PAGE: int = 5

    # Уведомления
    NOTIFICATION_BATCH_SIZE: int = 30  # Отправка уведомлений порциями

    print(f"DEBUG: DATABASE_URL IS SET TO: {DATABASE_URL}")
config = Config()
