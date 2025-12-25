"""Модуль для рассылки уведомлений пользователям"""
import asyncio
from typing import List, Tuple
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from loguru import logger

from database.models import User


async def broadcast_message(
    bot: Bot,
    users: List[User],
    text: str,
    parse_mode: str = "HTML",
    disable_notification: bool = False
) -> Tuple[int, int]:
    """
    Отправить сообщение списку пользователей

    Args:
        bot: Экземпляр бота
        users: Список пользователей
        text: Текст сообщения
        parse_mode: Режим парсинга (HTML, Markdown)
        disable_notification: Отключить звук уведомления

    Returns:
        Кортеж (успешно отправлено, ошибок)
    """
    success = 0
    fail = 0

    for user in users:
        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=text,
                parse_mode=parse_mode,
                disable_notification=disable_notification
            )
            success += 1
            logger.debug(f"Сообщение отправлено пользователю {user.telegram_id}")

            # Небольшая задержка, чтобы не превысить лимиты Telegram
            await asyncio.sleep(0.05)

        except TelegramForbiddenError:
            # Пользователь заблокировал бота
            fail += 1
            logger.warning(f"Пользователь {user.telegram_id} заблокировал бота")

        except TelegramBadRequest as e:
            # Неверный запрос (например, chat не найден)
            fail += 1
            logger.warning(f"Ошибка отправки пользователю {user.telegram_id}: {e}")

        except Exception as e:
            # Прочие ошибки
            fail += 1
            logger.error(f"Неожиданная ошибка при отправке {user.telegram_id}: {e}")

    logger.info(f"Рассылка завершена: успешно={success}, ошибок={fail}")
    return success, fail
