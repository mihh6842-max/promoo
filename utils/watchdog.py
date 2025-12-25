"""Watchdog для мониторинга работы бота"""
import asyncio
from datetime import datetime
from loguru import logger


class BotWatchdog:
    """Класс для мониторинга работы бота"""

    def __init__(self, check_interval: int = 300):
        """
        Args:
            check_interval: Интервал проверки в секундах (по умолчанию 5 минут)
        """
        self.check_interval = check_interval
        self.last_activity = datetime.now()
        self.is_running = False
        self._task = None

    def update_activity(self):
        """Обновить время последней активности"""
        self.last_activity = datetime.now()

    async def _watch(self):
        """Цикл мониторинга"""
        while self.is_running:
            try:
                await asyncio.sleep(self.check_interval)

                # Проверяем время последней активности
                inactive_time = (datetime.now() - self.last_activity).total_seconds()

                if inactive_time > self.check_interval * 2:
                    logger.warning(
                        f"Бот неактивен уже {inactive_time:.0f} секунд! "
                        f"Последняя активность: {self.last_activity}"
                    )
                else:
                    logger.debug(
                        f"Watchdog check OK. Последняя активность: "
                        f"{inactive_time:.0f}s назад"
                    )

            except asyncio.CancelledError:
                logger.info("Watchdog остановлен")
                break
            except Exception as e:
                logger.error(f"Ошибка в watchdog: {e}")

    async def start(self):
        """Запустить watchdog"""
        if not self.is_running:
            self.is_running = True
            self.update_activity()
            self._task = asyncio.create_task(self._watch())
            logger.info(f"Watchdog запущен (интервал проверки: {self.check_interval}s)")

    async def stop(self):
        """Остановить watchdog"""
        if self.is_running:
            self.is_running = False
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            logger.info("Watchdog остановлен")
