"""
Планировщик задач для автоматического парсинга
"""
import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from config import config
from parser.cuponcod_parser import CuponcodParser, SimpleCuponcodParser
from parser.json_storage import PromoJSONStorage
from database import async_session_maker
from database.crud import (
    create_promocode, get_promocode_by_code, update_promocode,
    create_parse_log, update_parse_log, mark_old_promos_as_not_new,
    deactivate_expired_promos, get_new_promocodes, get_subscribed_users
)
from utils.notifications import send_new_promos_notification


class ParserScheduler:
    """Планировщик парсинга"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone='Europe/Moscow')
        self.is_parsing = False
        self.json_storage = PromoJSONStorage()

        # Прогресс парсинга для мониторинга
        self.parsing_status = "idle"  # idle, running, completed, error
        self.current_page = 0
        self.total_pages = 0
        self.promos_found = 0
        self.new_added = 0
        self.updated = 0
        self.errors = []
        self.start_time = None

    async def parse_and_update_db(self):
        """Парсинг и обновление базы данных"""
        if self.is_parsing:
            logger.warning("Парсинг уже выполняется, пропускаем...")
            return

        self.is_parsing = True
        parse_log = None

        try:
            # Добавляем общий таймаут на весь процесс парсинга (15 минут)
            await asyncio.wait_for(self._do_parse_and_update(), timeout=900)
        except asyncio.TimeoutError:
            logger.error("❌ Парсинг превысил таймаут 15 минут и был остановлен")
            if parse_log:
                async with async_session_maker() as session:
                    await update_parse_log(
                        session,
                        parse_log.id,
                        finished_at=datetime.utcnow(),
                        status="error",
                        error_message="Timeout: парсинг превысил 15 минут"
                    )
        except Exception as e:
            logger.error(f"Критическая ошибка парсинга: {e}", exc_info=True)
        finally:
            self.is_parsing = False

    async def _do_parse_and_update(self):
        """Внутренний метод для парсинга и обновления"""
        parse_log = None

        try:
            # Обнуляем прогресс
            self.parsing_status = "running"
            self.current_page = 0
            self.total_pages = 0
            self.promos_found = 0
            self.new_added = 0
            self.updated = 0
            self.errors = []
            self.start_time = datetime.utcnow()

            logger.info("Начало автоматического парсинга")

            async with async_session_maker() as session:
                # Создаем лог
                parse_log = await create_parse_log(session)
                log_id = parse_log.id

            # Парсим сайт - пробуем Playwright, при ошибке fallback на Simple
            promocodes = []
            try:
                logger.info("Пробуем парсинг с Playwright...")
                async with CuponcodParser() as parser:
                    promocodes = await parser.parse_all_pages()
                logger.info(f"Парсинг с Playwright завершен. Найдено: {len(promocodes)}")
            except Exception as playwright_error:
                logger.warning(f"Playwright парсер не работает: {playwright_error}")
                logger.info("Переключаемся на Simple парсер (без Playwright)...")
                try:
                    async with SimpleCuponcodParser() as parser:
                        promocodes = await parser.parse_all_pages()
                    logger.info(f"Парсинг с Simple парсером завершен. Найдено: {len(promocodes)}")
                except Exception as simple_error:
                    logger.error(f"Simple парсер тоже не работает: {simple_error}")
                    raise Exception(f"Оба парсера не смогли выполнить работу. Playwright: {playwright_error}, Simple: {simple_error}")

            if not promocodes:
                raise Exception("Парсеры не нашли ни одного промокода")

            # Обновляем прогресс
            self.promos_found = len(promocodes)
            logger.info(f"Парсинг завершен. Найдено промокодов: {len(promocodes)}")

            # Анализируем изменения через JSON хранилище
            new_promos, updated_promos, removed_promos = self.json_storage.find_new_promos(promocodes)

            # Сохраняем текущее состояние в JSON
            self.json_storage.save_current_promos(promocodes)

            # Сохраняем в историю
            if new_promos or updated_promos:
                self.json_storage.save_to_history(promocodes, "auto_parse")
                self.json_storage.save_diff_report(new_promos, updated_promos, removed_promos)

            # Очищаем старую историю (старше 30 дней)
            self.json_storage.cleanup_old_history(keep_days=30)

            # Обновляем базу
            stats = await self._update_database(promocodes)

            # Обновляем прогресс
            self.new_added = stats['new_added']
            self.updated = stats['updated']

            # Обновляем лог
            async with async_session_maker() as session:
                await update_parse_log(
                    session,
                    log_id,
                    finished_at=datetime.utcnow(),
                    status="success",
                    total_found=len(promocodes),
                    **stats
                )

            logger.info(f"Статистика обновления:")
            logger.info(f"  - Новых: {stats['new_added']}")
            logger.info(f"  - Обновлено: {stats['updated']}")
            logger.info(f"  - Деактивировано: {stats['deactivated']}")

            # Отправляем уведомления о новых промокодах
            if stats['new_added'] > 0:
                await self._notify_users_about_new_promos()

            # Очищаем старые метки NEW
            async with async_session_maker() as session:
                await mark_old_promos_as_not_new(session, hours=24)

            # Деактивируем истекшие
            async with async_session_maker() as session:
                expired = await deactivate_expired_promos(session)
                if expired:
                    logger.info(f"Деактивировано истекших промокодов: {expired}")

            # Успешное завершение
            self.parsing_status = "completed"
            logger.info("Автоматический парсинг завершен успешно")

        except Exception as e:
            logger.error(f"Ошибка при парсинге: {e}", exc_info=True)

            # Сохраняем ошибку
            self.parsing_status = "error"
            self.errors.append(str(e))

            if parse_log:
                async with async_session_maker() as session:
                    await update_parse_log(
                        session,
                        parse_log.id,
                        finished_at=datetime.utcnow(),
                        status="error",
                        error_message=str(e)
                    )

    async def _update_database(self, promocodes: list) -> dict:
        """Обновление базы данных промокодами"""
        new_added = 0
        updated = 0
        deactivated = 0

        async with async_session_maker() as session:
            for promo_data in promocodes:
                try:
                    # Проверяем существование
                    existing = await get_promocode_by_code(
                        session,
                        promo_data['code'],
                        promo_data['shop_name']
                    )

                    if existing:
                        # Обновляем существующий
                        await update_promocode(
                            session,
                            existing.id,
                            description=promo_data['description'],
                            discount_value=promo_data.get('discount_value'),
                            discount_percent=promo_data.get('discount_percent'),
                            conditions=promo_data.get('conditions'),
                            expiry_date=promo_data.get('expiry_date'),
                            category=promo_data['category'],
                            shop_url=promo_data['shop_url'],
                            image_url=promo_data.get('image_url'),
                            is_hot=promo_data['is_hot'],
                            is_active=True
                        )
                        updated += 1
                    else:
                        # Создаем новый
                        await create_promocode(
                            session,
                            shop_name=promo_data['shop_name'],
                            code=promo_data['code'],
                            description=promo_data['description'],
                            discount_value=promo_data.get('discount_value'),
                            discount_percent=promo_data.get('discount_percent'),
                            conditions=promo_data.get('conditions'),
                            expiry_date=promo_data.get('expiry_date'),
                            category=promo_data['category'],
                            shop_url=promo_data['shop_url'],
                            image_url=promo_data.get('image_url'),
                            is_hot=promo_data['is_hot'],
                            is_new=True,
                            is_active=True
                        )
                        new_added += 1

                except Exception as e:
                    logger.error(f"Ошибка обновления промокода {promo_data.get('code')}: {e}")
                    continue

        return {
            'new_added': new_added,
            'updated': updated,
            'deactivated': deactivated
        }

    async def _notify_users_about_new_promos(self):
        """Уведомление пользователей о новых промокодах"""
        try:
            async with async_session_maker() as session:
                # Получаем новые промокоды
                new_promos = await get_new_promocodes(session, limit=10)

                if not new_promos:
                    return

                # Получаем подписанных пользователей
                users = await get_subscribed_users(session)

                if not users:
                    return

                logger.info(f"Отправка уведомлений {len(users)} пользователям о {len(new_promos)} новых промокодах")

                # Отправляем уведомления порциями
                await send_new_promos_notification(users, new_promos)

        except Exception as e:
            logger.error(f"Ошибка отправки уведомлений: {e}")

    def start(self):
        """Запуск планировщика"""
        # Добавляем задачи по расписанию
        for time in config.PARSE_TIMES:
            hour, minute = map(int, time.split(':'))

            self.scheduler.add_job(
                self.parse_and_update_db,
                CronTrigger(hour=hour, minute=minute),
                id=f'parse_{time}',
                name=f'Парсинг в {time}',
                replace_existing=True
            )

            logger.info(f"Запланирован парсинг на {time}")

        # Запускаем планировщик
        self.scheduler.start()
        logger.info("Планировщик запущен")

    def stop(self):
        """Остановка планировщика"""
        self.scheduler.shutdown()
        logger.info("Планировщик остановлен")

    async def run_now(self):
        """Запустить парсинг прямо сейчас"""
        await self.parse_and_update_db()

    def get_progress(self) -> dict:
        """Получить текущий прогресс парсинга"""
        elapsed = 0
        if self.start_time:
            try:
                elapsed = (datetime.utcnow() - self.start_time).total_seconds()
            except Exception:
                elapsed = 0

        return {
            "status": self.parsing_status,
            "is_parsing": self.is_parsing,
            "promos_found": self.promos_found,
            "new_added": self.new_added,
            "updated": self.updated,
            "errors": self.errors if self.errors else [],
            "elapsed_seconds": elapsed
        }
