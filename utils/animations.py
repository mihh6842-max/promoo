"""Анимации и сообщения для бота"""
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from database.models import PromoCode


def welcome_message() -> str:
    """Приветственное сообщение"""
    return (
        "👋 <b>Добро пожаловать в PromoBot!</b>\n\n"
        "🎁 Здесь вы найдете актуальные промокоды и скидки "
        "от популярных интернет-магазинов.\n\n"
        "📱 Используйте меню ниже для навигации:"
    )


def help_message() -> str:
    """Сообщение помощи"""
    return (
        "ℹ️ <b>Помощь по использованию бота</b>\n\n"
        "🔍 <b>Поиск</b> - найти промокоды по названию магазина или категории\n"
        "🏪 <b>Магазины</b> - список всех доступных магазинов\n"
        "📂 <b>Категории</b> - промокоды по категориям\n"
        "⭐ <b>Избранное</b> - сохраненные промокоды\n"
        "🔔 <b>Подписки</b> - уведомления о новых промокодах\n\n"
        "💡 Бот автоматически обновляет базу промокодов каждый день!"
    )


def format_promocode_card(promo: "PromoCode", is_favorite: bool = False) -> str:
    """Форматирование карточки промокода"""

    # Эмодзи статусов
    badges = []
    if promo.is_hot:
        badges.append("🔥 HOT")
    if promo.is_new:
        badges.append("🆕 NEW")

    status_line = " ".join(badges) if badges else ""

    # Заголовок
    fav_emoji = "⭐" if is_favorite else ""
    title = f"{fav_emoji} <b>{promo.shop_name}</b> {status_line}".strip()

    # Скидка
    discount = ""
    if promo.discount_percent:
        discount = f"💰 <b>Скидка:</b> {promo.discount_percent}%"
    elif promo.discount_value:
        discount = f"💰 <b>Скидка:</b> {promo.discount_value}"

    # Промокод
    code_line = f"🎟 <b>Промокод:</b> <code>{promo.code}</code>"

    # Описание
    description = f"📝 {promo.description}"

    # Условия
    conditions = ""
    if promo.conditions:
        conditions = f"⚠️ <i>{promo.conditions}</i>"

    # Срок действия
    expiry = ""
    if promo.expiry_date:
        expiry_str = promo.expiry_date.strftime("%d.%m.%Y")
        days_left = (promo.expiry_date - datetime.utcnow()).days

        if days_left < 0:
            expiry = f"⏰ Истек {expiry_str}"
        elif days_left == 0:
            expiry = f"⏰ Истекает сегодня!"
        elif days_left <= 3:
            expiry = f"⏰ Истекает {expiry_str} (осталось {days_left} дн.)"
        else:
            expiry = f"⏰ Действует до {expiry_str}"

    # Статистика
    stats = f"👁 Просмотров: {promo.views_count} | 📋 Копирований: {promo.copy_count}"

    # Собираем карточку
    parts = [title, discount, code_line, "", description]

    if conditions:
        parts.append("")
        parts.append(conditions)

    if expiry:
        parts.append("")
        parts.append(expiry)

    parts.append("")
    parts.append(stats)

    return "\n".join(part for part in parts if part is not None)
