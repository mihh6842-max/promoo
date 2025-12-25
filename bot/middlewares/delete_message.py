"""
Middleware для удаления сообщений пользователя
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from loguru import logger


class DeleteUserMessageMiddleware(BaseMiddleware):
    """Удаление сообщений пользователя с кнопками"""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        # Вызываем обработчик
        result = await handler(event, data)

        # Удаляем сообщение пользователя после обработки
        # Если это текстовое сообщение (не команда /start, /help и т.д.)
        if event.text and not event.text.startswith('/'):
            try:
                await event.delete()
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение: {e}")

        return result
