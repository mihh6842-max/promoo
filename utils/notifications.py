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


async def send_new_promos_notification(users: List[User], new_promos: list) -> None:
    """
    Отправить уведомления о новых промокодах

    Args:
        users: Список пользователей для уведомления
        new_promos: Список новых промокодов
    """
    from main import bot
    from utils.animations import format_promocode_card

    if not users or not new_promos:
        logger.debug("Нет пользователей или промокодов для уведомлений")
        return

    # Ограничиваем количество промокодов в уведомлении
    promos_to_notify = new_promos[:5]  # Максимум 5 промокодов

    # Формируем сообщение
    if len(new_promos) == 1:
        message = "🆕 <b>Новый промокод!</b>\n\n"
    else:
        message = f"🆕 <b>Новые промокоды ({len(new_promos)})!</b>\n\n"

    # Добавляем карточки промокодов
    for i, promo in enumerate(promos_to_notify, 1):
        message += f"<b>{i}.</b> "
        message += format_promocode_card(promo, is_favorite=False)
        if i < len(promos_to_notify):
            message += "\n\n" + "─" * 30 + "\n\n"

    # Если промокодов больше 5, добавляем сноску
    if len(new_promos) > 5:
        remaining = len(new_promos) - 5
        message += f"\n\n... и еще {remaining} промокод(ов)!"

    message += "\n\n📱 Откройте бота, чтобы увидеть все новые промокоды!"

    # Отправляем уведомления
    success, fail = await broadcast_message(
        bot=bot,
        users=users,
        text=message,
        parse_mode="HTML",
        disable_notification=False
    )

    logger.info(
        f"Уведомления о новых промокодах отправлены: "
        f"успешно={success}, ошибок={fail}"
    )
