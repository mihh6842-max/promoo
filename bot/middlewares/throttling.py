"""Middleware для защиты от спама (throttling)"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from loguru import logger
import time


class ThrottlingMiddleware(BaseMiddleware):
    """Middleware для ограничения частоты запросов"""

    def __init__(self, rate_limit: float = 0.5):
        """
        Args:
            rate_limit: Минимальный интервал между сообщениями в секундах
        """
        self.rate_limit = rate_limit
        self.user_timings: Dict[int, float] = {}
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        current_time = time.time()

        # Проверяем время последнего сообщения пользователя
        last_time = self.user_timings.get(user_id, 0)
        time_passed = current_time - last_time

        if time_passed < self.rate_limit:
            # Слишком частые запросы
            logger.warning(
                f"Throttling: пользователь {user_id} отправляет сообщения слишком часто "
                f"(интервал {time_passed:.2f}s)"
            )
            return None

        # Обновляем время последнего сообщения
        self.user_timings[user_id] = current_time

        # Очищаем старые записи (старше 1 часа)
        if len(self.user_timings) > 1000:
            cutoff_time = current_time - 3600
            self.user_timings = {
                uid: t for uid, t in self.user_timings.items()
                if t > cutoff_time
            }

        return await handler(event, data)
