"""
Главный файл запуска бота
"""
import asyncio
import sys
from loguru import logger

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from database import init_db
from bot.handlers import routers
from bot.middlewares import ThrottlingMiddleware, ErrorHandlerMiddleware, error_handler
from parser.scheduler import ParserScheduler
from utils.watchdog import BotWatchdog


# Настройка логирования
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level=config.LOG_LEVEL
)
logger.add(
    "logs/bot_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="7 days",
    level=config.LOG_LEVEL,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}"
)


# Инициализация бота
bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

# Инициализация диспетчера
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Планировщик парсинга
parser_scheduler = ParserScheduler()

# Внутренний watchdog (самопроверка бота)
watchdog = BotWatchdog(check_interval=300)  # Проверка каждые 5 минут


async def on_startup():
    """Действия при запуске бота"""
    logger.info("Запуск PromoBot...")

    # Инициализация базы данных
    await init_db()
    logger.info("База данных инициализирована")

    # Установка Playwright (если не установлен)
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            timeout=300,
            text=True
        )
        if result.returncode == 0:
            logger.info("Playwright браузеры установлены успешно")
        else:
            logger.warning(f"Ошибка установки Playwright: {result.stderr}")
    except Exception as e:
        logger.warning(f"Ошибка установки Playwright: {e}")

    # Проверка наличия данных в базе
    from database import async_session_maker
    from database.crud import get_all_promocodes
    async with async_session_maker() as session:
        promos = await get_all_promocodes(session, limit=1)
        if promos:
            logger.info(f"✓ База данных содержит промокоды. Пример: {promos[0].code} ({promos[0].shop_name})")
        else:
            logger.warning("⚠ База данных пуста! Промокоды появятся после первого парсинга по расписанию")

    # Тестовая проверка работы парсера (без сохранения)
    from parser.cuponcod_parser import SimpleCuponcodParser
    try:
        logger.info("Проверка работы парсера...")
        async with SimpleCuponcodParser() as test_parser:
            test_promos = await test_parser.parse_page_simple(config.TARGET_URL)
            if test_promos:
                logger.info(f"✓ Парсер работает! Тест: найдено {len(test_promos)} промокодов на главной")
            else:
                logger.warning("⚠ Парсер не нашёл промокодов на главной странице")
    except Exception as e:
        logger.warning(f"⚠ Тест парсера не прошёл: {e}")

    # Запуск планировщика парсинга (парсинг по расписанию, без запуска при старте)
    parser_scheduler.start()
    logger.info("Планировщик парсинга запущен")

    # Сохраняем scheduler в глобальное хранилище для доступа из хэндлеров
    from utils.state_storage import bot_storage
    bot_storage.set("parser_scheduler", parser_scheduler)

    # Запуск watchdog в фоне
    asyncio.create_task(watchdog.start())
    logger.info("Watchdog запущен")

    # Регистрируем middleware
    # dp.message.middleware(ThrottlingMiddleware(rate_limit=20, time_period=60))
    # dp.callback_query.middleware(ThrottlingMiddleware(rate_limit=20, time_period=60))
    dp.message.middleware(ErrorHandlerMiddleware())
    dp.callback_query.middleware(ErrorHandlerMiddleware())
    dp.errors.register(error_handler)
    logger.info("Middleware зарегистрированы")

    # Регистрируем роутеры
    for router in routers:
        dp.include_router(router)
    logger.info(f"Зарегистрировано {len(routers)} роутеров")

    # Отправляем уведомление админу
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                "✅ <b>PromoBot запущен!</b>\n\n"
                "Бот готов к работе.\n"
                "Используйте /admin для управления.",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление админу {admin_id}: {e}")

    logger.info("PromoBot успешно запущен!")


async def on_shutdown():
    """Действия при остановке бота"""
    logger.info("Остановка бота...")

    # Останавливаем watchdog
    watchdog.stop()

    # Останавливаем планировщик
    parser_scheduler.stop()

    # Отправляем уведомление админу
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                "⚠️ <b>PromoBot остановлен</b>",
                parse_mode=ParseMode.HTML
            )
        except:
            pass

    await bot.session.close()
    logger.info("Бот остановлен")


async def main():
    """Главная функция с автоматическим перезапуском"""
    global bot, dp, storage, parser_scheduler
    restart_delay = 5  # Задержка перед перезапуском (секунды)

    while True:
        try:
            # Запуск
            await on_startup()

            # Polling
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                drop_pending_updates=True
            )

        except KeyboardInterrupt:
            logger.info("Получен сигнал остановки (Ctrl+C)")
            await on_shutdown()
            break  # Выходим только при явном Ctrl+C
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}", exc_info=True)
            logger.info(f"Перезапуск бота через {restart_delay} секунд...")

            # Пытаемся корректно завершить текущую сессию
            try:
                await bot.session.close()
            except:
                pass

            # Ждём перед перезапуском
            await asyncio.sleep(restart_delay)

            # Пересоздаём бота для нового подключения
            bot = Bot(
                token=config.BOT_TOKEN,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML)
            )
            storage = MemoryStorage()
            dp = Dispatcher(storage=storage)
            parser_scheduler = ParserScheduler()

            # Обновляем scheduler в хранилище
            from utils.state_storage import bot_storage
            bot_storage.set("parser_scheduler", parser_scheduler)

            logger.info("Перезапуск бота...")
            continue


if __name__ == "__main__":
    while True:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.info("Выход...")
            break
        except Exception as e:
            logger.error(f"Ошибка event loop: {e}", exc_info=True)
            logger.info("Перезапуск через 10 секунд...")
            import time
            time.sleep(10)