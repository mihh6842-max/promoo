"""Middleware для обработки ошибок"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, ErrorEvent
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from loguru import logger


class ErrorHandlerMiddleware(BaseMiddleware):
    """Middleware для перехвата и обработки ошибок"""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        try:
            return await handler(event, data)
        except TelegramBadRequest as e:
            logger.error(f"TelegramBadRequest: {e}")
            # Игнорируем ошибки типа "message is not modified"
            if "message is not modified" in str(e).lower():
                return None
            raise
        except TelegramForbiddenError as e:
            logger.warning(f"TelegramForbiddenError (user blocked bot): {e}")
            return None
        except Exception as e:
            logger.exception(f"Необработанная ошибка в middleware: {e}")
            raise


async def error_handler(event: ErrorEvent):
    """
    Глобальный обработчик ошибок для aiogram

    Args:
        event: Событие ошибки
    """
    update: Update = event.update
    exception = event.exception

    # Логируем ошибку
    logger.error(
        f"Ошибка при обработке update {update.update_id}: "
        f"{type(exception).__name__}: {exception}"
    )

    # Специфичная обработка различных типов ошибок
    if isinstance(exception, TelegramBadRequest):
        if "message is not modified" in str(exception).lower():
            # Игнорируем ошибки, когда сообщение не изменилось
            logger.debug("Игнорируем 'message is not modified'")
            return True
        elif "message to delete not found" in str(exception).lower():
            # Сообщение уже удалено
            logger.debug("Сообщение уже удалено")
            return True

    elif isinstance(exception, TelegramForbiddenError):
        # Пользователь заблокировал бота
        logger.warning("Пользователь заблокировал бота")
        return True

    # Для остальных ошибок - выводим полный traceback
    logger.exception("Необработанное исключение:")
    return True
