"""
Reply клавиатуры (внизу экрана)
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню (постоянная клавиатура)"""
    builder = ReplyKeyboardBuilder()

    # Первый ряд
    builder.row(
        KeyboardButton(text="🏪 Магазины"),
        KeyboardButton(text="📂 Категории")
    )

    # Второй ряд
    builder.row(
        KeyboardButton(text="🔥 Горячие"),
        KeyboardButton(text="⭐ Избранное")
    )

    # Третий ряд
    builder.row(
        KeyboardButton(text="🔍 Поиск"),
        KeyboardButton(text="🔔 Подписка")
    )

    # Четвертый ряд
    builder.row(
        KeyboardButton(text="ℹ️ Помощь"),
        KeyboardButton(text="👑 Админ")
    )

    return builder.as_markup(resize_keyboard=True, persistent=True)


def cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура отмены"""
    builder = ReplyKeyboardBuilder()

    builder.row(KeyboardButton(text="❌ Отмена"))

    return builder.as_markup(resize_keyboard=True)


def admin_keyboard() -> ReplyKeyboardMarkup:
    """Админ клавиатура"""
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="▶️ Запустить парсинг")
    )
    builder.row(
        KeyboardButton(text="📊 Статистика"),
        KeyboardButton(text="📨 Рассылка")
    )
    builder.row(
        KeyboardButton(text="🔙 Главное меню")
    )

    return builder.as_markup(resize_keyboard=True, persistent=True)


def back_to_menu_keyboard() -> ReplyKeyboardMarkup:
    """Просто кнопка назад в меню"""
    builder = ReplyKeyboardBuilder()

    builder.row(KeyboardButton(text="🔙 Главное меню"))

    return builder.as_markup(resize_keyboard=True)


def confirm_keyboard() -> ReplyKeyboardMarkup:
    """Подтверждение действия"""
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="✅ Да"),
        KeyboardButton(text="❌ Нет")
    )

    return builder.as_markup(resize_keyboard=True)
