"""
Inline клавиатуры бота
"""
from typing import List, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🏪 Магазины", callback_data="shops_menu")
    )
    builder.row(
        InlineKeyboardButton(text="📂 Категории", callback_data="categories_menu")
    )
    builder.row(
        InlineKeyboardButton(text="🔥 Горячие предложения", callback_data="hot_offers")
    )
    builder.row(
        InlineKeyboardButton(text="⭐ Избранное", callback_data="favorites")
    )
    builder.row(
        InlineKeyboardButton(text="🔍 Поиск", callback_data="search_prompt"),
        InlineKeyboardButton(text="🔔 Подписка", callback_data="subscription_menu")
    )

    return builder.as_markup()


def shops_list_keyboard(shops: List[str], page: int = 0) -> InlineKeyboardMarkup:
    """Список магазинов с пагинацией"""
    builder = InlineKeyboardBuilder()

    # Магазины по 8 штук на странице
    items_per_page = 8
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page

    page_shops = shops[start_idx:end_idx]

    # Добавляем кнопки магазинов по 2 в ряд
    for i in range(0, len(page_shops), 2):
        row_buttons = []
        for shop in page_shops[i:i+2]:
            row_buttons.append(
                InlineKeyboardButton(
                    text=shop,
                    callback_data=f"shop:{shop}"
                )
            )
        builder.row(*row_buttons)

    # Пагинация
    total_pages = (len(shops) + items_per_page - 1) // items_per_page
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton(text="⬅️", callback_data=f"shops_page:{page-1}")
            )
        nav_buttons.append(
            InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="current_page")
        )
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton(text="➡️", callback_data=f"shops_page:{page+1}")
            )
        builder.row(*nav_buttons)

    # Кнопка назад
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
    )

    return builder.as_markup()


def categories_keyboard(categories: List[str]) -> InlineKeyboardMarkup:
    """Клавиатура категорий"""
    builder = InlineKeyboardBuilder()

    # Эмодзи для категорий
    category_emojis = {
        'Электроника': '💻',
        'Мода и одежда': '👔',
        'Красота и здоровье': '💄',
        'Дом и сад': '🏡',
        'Продукты': '🛒',
        'Спорт и отдых': '⚽',
        'Детские товары': '🧸',
        'Книги и медиа': '📚',
        'Путешествия': '✈️',
        'Рестораны и кафе': '🍕',
        'Услуги': '🔧',
        'Авто': '🚗',
        'Разное': '🎁'
    }

    # Добавляем кнопки категорий
    for category in sorted(categories):
        emoji = category_emojis.get(category, '📌')
        builder.row(
            InlineKeyboardButton(
                text=f"{emoji} {category}",
                callback_data=f"category:{category}"
            )
        )

    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
    )

    return builder.as_markup()


def promocodes_list_keyboard(
    promocodes: List,
    page: int = 0,
    callback_prefix: str = "promo",
    back_callback: str = "main_menu"
) -> InlineKeyboardMarkup:
    """Список промокодов с пагинацией"""
    builder = InlineKeyboardBuilder()

    items_per_page = 5
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page

    page_promos = promocodes[start_idx:end_idx]

    # Добавляем кнопки промокодов
    for promo in page_promos:
        # Формируем текст кнопки
        button_text = f"{'🔥' if promo.is_hot else '📌'} {promo.shop_name}"
        if promo.discount_value:
            button_text += f" - {promo.discount_value}"

        builder.row(
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"{callback_prefix}:{promo.id}"
            )
        )

    # Пагинация
    total_pages = (len(promocodes) + items_per_page - 1) // items_per_page
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton(text="⬅️", callback_data=f"{callback_prefix}_page:{page-1}")
            )
        nav_buttons.append(
            InlineKeyboardButton(text=f"📄 {page+1}/{total_pages}", callback_data="current_page")
        )
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton(text="➡️", callback_data=f"{callback_prefix}_page:{page+1}")
            )
        builder.row(*nav_buttons)

    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback)
    )

    return builder.as_markup()


def promocode_card_keyboard(
    promo_id: int,
    promo_code: str,
    shop_url: str,
    is_favorite: bool = False,
    back_callback: str = "main_menu"
) -> InlineKeyboardMarkup:
    """Клавиатура для карточки промокода"""
    builder = InlineKeyboardBuilder()

    # Кнопка копирования промокода
    builder.row(
        InlineKeyboardButton(
            text=f"📋 {promo_code}",
            callback_data=f"copy:{promo_id}"
        )
    )

    # Переход в магазин
    builder.row(
        InlineKeyboardButton(
            text="🔗 Перейти в магазин",
            url=shop_url
        )
    )

    # Избранное
    fav_text = "💔 Удалить из избранного" if is_favorite else "⭐ В избранное"
    builder.row(
        InlineKeyboardButton(
            text=fav_text,
            callback_data=f"toggle_fav:{promo_id}"
        )
    )

    # Поделиться
    builder.row(
        InlineKeyboardButton(
            text="📤 Поделиться",
            callback_data=f"share:{promo_id}"
        )
    )

    # Назад
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback)
    )

    return builder.as_markup()


def subscription_menu_keyboard(is_subscribed: bool) -> InlineKeyboardMarkup:
    """Меню подписок"""
    builder = InlineKeyboardBuilder()

    # Главная подписка
    if is_subscribed:
        builder.row(
            InlineKeyboardButton(
                text="🔕 Отключить уведомления",
                callback_data="toggle_subscription"
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text="🔔 Включить уведомления",
                callback_data="toggle_subscription"
            )
        )

    # Настройки уведомлений
    builder.row(
        InlineKeyboardButton(
            text="⚙️ Настройки уведомлений",
            callback_data="notification_settings"
        )
    )

    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
    )

    return builder.as_markup()


def notification_settings_keyboard(
    notify_new: bool,
    notify_hot: bool,
    notify_expiring: bool
) -> InlineKeyboardMarkup:
    """Настройки уведомлений"""
    builder = InlineKeyboardBuilder()

    # Новые промокоды
    new_icon = "✅" if notify_new else "❌"
    builder.row(
        InlineKeyboardButton(
            text=f"{new_icon} Новые промокоды",
            callback_data="toggle_notify_new"
        )
    )

    # Горячие предложения
    hot_icon = "✅" if notify_hot else "❌"
    builder.row(
        InlineKeyboardButton(
            text=f"{hot_icon} Горячие предложения (>30%)",
            callback_data="toggle_notify_hot"
        )
    )

    # Истекающие
    exp_icon = "✅" if notify_expiring else "❌"
    builder.row(
        InlineKeyboardButton(
            text=f"{exp_icon} Истекающие промокоды",
            callback_data="toggle_notify_expiring"
        )
    )

    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="subscription_menu")
    )

    return builder.as_markup()


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Админ панель - ОБНОВЛЕННАЯ"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Запустить парсинг", callback_data="admin_run_parser")
    )
    builder.row(
        InlineKeyboardButton(text="➕ Добавить промокод", callback_data="admin_add_promo")
    )
    builder.row(
        InlineKeyboardButton(text="🗂️ Управление промокодами", callback_data="admin_manage_promos")
    )
    builder.row(
        InlineKeyboardButton(text="🖼️ Сменить баннеры", callback_data="admin_change_banners")
    )
    builder.row(
        InlineKeyboardButton(text="📨 Рассылка", callback_data="admin_broadcast")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
    )

    return builder.as_markup()


def confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=f"confirm:{action}"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"cancel:{action}")
    )

    return builder.as_markup()


def back_button(callback_data: str = "main_menu") -> InlineKeyboardMarkup:
    """Просто кнопка Назад"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=callback_data)
    )

    return builder.as_markup()


# ==================== АДМИНСКИЕ КЛАВИАТУРЫ ====================

def shops_selection_keyboard(shops: List[str], page: int = 0) -> InlineKeyboardMarkup:
    """Выбор магазина для промокода с пагинацией"""
    builder = InlineKeyboardBuilder()

    items_per_page = 17
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page

    page_shops = shops[start_idx:end_idx]

    # Показываем магазины текущей страницы
    for idx, shop in enumerate(page_shops, start=start_idx):
        builder.row(
            InlineKeyboardButton(
                text=shop,
                callback_data=f"select_shop:{idx}"
            )
        )

    # Пагинация
    total_pages = (len(shops) + items_per_page - 1) // items_per_page
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton(text="⬅️", callback_data=f"shops_select_page:{page-1}")
            )
        nav_buttons.append(
            InlineKeyboardButton(text=f"📄 {page+1}/{total_pages}", callback_data="current_page")
        )
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton(text="➡️", callback_data=f"shops_select_page:{page+1}")
            )
        builder.row(*nav_buttons)

    builder.row(
        InlineKeyboardButton(text="✏️ Ввести вручную", callback_data="enter_shop_manual")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel:add_promo")
    )

    return builder.as_markup()


def categories_selection_keyboard(categories: List[str], page: int = 0) -> InlineKeyboardMarkup:
    """Выбор категории для промокода с пагинацией"""
    builder = InlineKeyboardBuilder()

    category_emojis = {
        'Электроника': '💻',
        'Мода и одежда': '👔',
        'Красота и здоровье': '💄',
        'Дом и сад': '🏡',
        'Продукты': '🛒',
        'Спорт и отдых': '⚽',
        'Детские товары': '🧸',
        'Книги и медиа': '📚',
        'Путешествия': '✈️',
        'Рестораны и кафе': '🍕',
        'Услуги': '🔧',
        'Авто': '🚗',
        'Разное': '🎁'
    }

    items_per_page = 17
    sorted_categories = sorted(categories)
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page

    page_categories = sorted_categories[start_idx:end_idx]

    # Показываем категории текущей страницы
    for idx, category in enumerate(page_categories, start=start_idx):
        emoji = category_emojis.get(category, '📌')
        builder.row(
            InlineKeyboardButton(
                text=f"{emoji} {category}",
                callback_data=f"select_category:{idx}"
            )
        )

    # Пагинация
    total_pages = (len(sorted_categories) + items_per_page - 1) // items_per_page
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton(text="⬅️", callback_data=f"categories_select_page:{page-1}")
            )
        nav_buttons.append(
            InlineKeyboardButton(text=f"📄 {page+1}/{total_pages}", callback_data="current_page")
        )
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton(text="➡️", callback_data=f"categories_select_page:{page+1}")
            )
        builder.row(*nav_buttons)

    builder.row(
        InlineKeyboardButton(text="✏️ Ввести вручную", callback_data="enter_category_manual")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel:add_promo")
    )

    return builder.as_markup()


def manage_promos_keyboard() -> InlineKeyboardMarkup:
    """Меню управления промокодами"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🔍 Поиск промокода", callback_data="admin_search_promo")
    )
    builder.row(
        InlineKeyboardButton(text="🗑️ Удалить промокод", callback_data="admin_delete_promo")
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Редактировать промокод", callback_data="admin_edit_promo")
    )
    builder.row(
        InlineKeyboardButton(text="📋 Список всех промокодов", callback_data="admin_list_promos")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_stats")
    )

    return builder.as_markup()


def banners_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню выбора баннера"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="👋 Главное меню (hello)", callback_data="change_banner:main")
    )
    builder.row(
        InlineKeyboardButton(text="📂 Категории", callback_data="change_banner:categories")
    )
    builder.row(
        InlineKeyboardButton(text="🔥 Горячие предложения", callback_data="change_banner:hot")
    )
    builder.row(
        InlineKeyboardButton(text="🔍 Поиск", callback_data="change_banner:search")
    )
    builder.row(
        InlineKeyboardButton(text="🏪 Магазины", callback_data="change_banner:shops")
    )
    builder.row(
        InlineKeyboardButton(text="⭐ Избранное", callback_data="change_banner:favorites")
    )
    builder.row(
        InlineKeyboardButton(text="🔔 Подписка", callback_data="change_banner:subscription")
    )
    builder.row(
        InlineKeyboardButton(text="🆕 Новые промокоды", callback_data="change_banner:new_promos")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_stats")
    )

    return builder.as_markup()


def promo_actions_keyboard(promo_id: int) -> InlineKeyboardMarkup:
    """Действия с промокодом в админке"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"admin_edit:{promo_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"admin_delete:{promo_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить статус", callback_data=f"admin_toggle:{promo_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_manage_promos")
    )

    return builder.as_markup()


def admin_promos_list_keyboard(promos: List, page: int = 0) -> InlineKeyboardMarkup:
    """Список промокодов в админке с пагинацией"""
    builder = InlineKeyboardBuilder()

    items_per_page = 17
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page

    page_promos = promos[start_idx:end_idx]

    # Добавляем кнопки промокодов
    for promo in page_promos:
        status = "✅" if promo.is_active else "❌"
        hot = "🔥" if promo.is_hot else ""
        
        button_text = f"{status}{hot} #{promo.id} | {promo.shop_name} - {promo.code}"
        
        builder.row(
            InlineKeyboardButton(
                text=button_text[:60],  # Обрезаем если длинное
                callback_data=f"admin_view_promo:{promo.id}"
            )
        )

    # Пагинация
    total_pages = (len(promos) + items_per_page - 1) // items_per_page
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton(text="⬅️", callback_data=f"admin_promos_page:{page-1}")
            )
        nav_buttons.append(
            InlineKeyboardButton(text=f"📄 {page+1}/{total_pages}", callback_data="current_page")
        )
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton(text="➡️", callback_data=f"admin_promos_page:{page+1}")
            )
        builder.row(*nav_buttons)

    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_manage_promos")
    )

    return builder.as_markup()