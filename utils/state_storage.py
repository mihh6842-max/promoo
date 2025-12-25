"""Хранилище состояния сообщений бота"""
from typing import Dict, Optional, Any
from aiogram.types import Message
from loguru import logger


class BotStorage:
    """Класс для хранения последних сообщений бота и глобального состояния"""

    def __init__(self):
        self._messages: Dict[int, Message] = {}
        self._data: Dict[str, Any] = {}

    def save_message(self, user_id: int, message: Message) -> None:
        """Сохранить сообщение бота для пользователя"""
        self._messages[user_id] = message
        logger.debug(f"Сохранено сообщение для пользователя {user_id}")

    def get_message(self, user_id: int) -> Optional[Message]:
        """Получить последнее сообщение бота для пользователя"""
        return self._messages.get(user_id)

    def remove_message(self, user_id: int) -> None:
        """Удалить сохраненное сообщение"""
        if user_id in self._messages:
            del self._messages[user_id]
            logger.debug(f"Удалено сообщение для пользователя {user_id}")

    def set(self, key: str, value: Any) -> None:
        """Сохранить произвольные данные по ключу"""
        self._data[key] = value
        logger.debug(f"Сохранено значение для ключа '{key}'")

    def get(self, key: str, default: Any = None) -> Any:
        """Получить данные по ключу"""
        return self._data.get(key, default)

    async def edit_or_send(
        self,
        user_id: int,
        message: Message,
        text: str,
        **kwargs
    ) -> Message:
        """Редактировать последнее сообщение или отправить новое"""
        last_message = self.get_message(user_id)

        try:
            if last_message:
                # Пытаемся отредактировать
                await last_message.edit_text(text, **kwargs)
                return last_message
        except Exception as e:
            logger.debug(f"Не удалось отредактировать сообщение: {e}")

        # Если не получилось отредактировать, отправляем новое
        new_message = await message.answer(text, **kwargs)
        self.save_message(user_id, new_message)
        return new_message


# Глобальный экземпляр хранилища
bot_storage = BotStorage()
# Force cache clear
