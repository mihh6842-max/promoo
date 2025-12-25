"""
Обработчик админ панели
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger
from datetime import datetime
import os

from config import config
from database import async_session_maker
from database.crud import (
    get_stats, 
    get_last_parse_log,
    get_all_shops,
    get_all_categories,
    get_promocode_by_id,
    delete_promocode,
    toggle_promocode_status
)
from bot.keyboards.inline import main_menu_keyboard
from utils.animations import format_stats_message
from utils.notifications import broadcast_message
from utils.state_storage import bot_storage

router = Router(name='admin')


class BroadcastStates(StatesGroup):
    """Состояния для рассылки"""
    waiting_for_message = State()


class PromoStates(StatesGroup):
    """Состояния для добавления промокода"""
    waiting_shop = State()
    waiting_code = State()
    waiting_category = State()
    waiting_discount = State()
    waiting_description = State()
    waiting_url = State()
    waiting_expires = State()


class BannerStates(StatesGroup):
    """Состояния для смены баннера"""
    waiting_banner_type = State()
    waiting_banner_photo = State()


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь админом"""
    return user_id in config.ADMIN_IDS


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Команда /admin"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к админ панели")
        return

    from bot.keyboards.inline import admin_panel_keyboard
    await message.answer(
        "👑 <b>АДМИН ПАНЕЛЬ</b>\n\n"
        "Управление ботом:",
        reply_markup=admin_panel_keyboard(),
        parse_mode="HTML"
    )


# ==================== СТАТИСТИКА ====================

@router.callback_query(F.data == "admin_stats")
async def show_admin_stats(callback: CallbackQuery):
    """Показать статистику"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    try:
        async with async_session_maker() as session:
            stats = await get_stats(session)
            last_parse = await get_last_parse_log(session)

        stats_text = format_stats_message(stats)

        if last_parse:
            stats_text += f"\n\n📊 <b>Последний парсинг:</b>\n"
            stats_text += f"Время: {last_parse.started_at.strftime('%d.%m.%Y %H:%M')}\n"
            stats_text += f"Статус: {last_parse.status}\n"
            stats_text += f"Найдено: {last_parse.total_found}\n"
            stats_text += f"Новых: {last_parse.new_added}\n"
            stats_text += f"Обновлено: {last_parse.updated}\n"

        from bot.keyboards.inline import admin_panel_keyboard
        await callback.message.edit_text(
            stats_text,
            reply_markup=admin_panel_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка показа статистики: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


# ==================== РАССЫЛКА ====================

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_prompt(callback: CallbackQuery, state: FSMContext):
    """Запрос сообщения для рассылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    await callback.message.edit_text(
        "📨 <b>Рассылка сообщения</b>\n\n"
        "Введите текст сообщения для рассылки\n"
        "всем пользователям бота:\n\n"
        "<i>Можно использовать HTML разметку</i>",
        parse_mode="HTML"
    )

    await state.set_state(BroadcastStates.waiting_for_message)
    await callback.answer()


@router.message(BroadcastStates.waiting_for_message)
async def process_broadcast(message: Message, state: FSMContext):
    """Обработка рассылки"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа")
        await state.clear()
        return

    try:
        broadcast_text = message.text

        # Показываем превью
        await message.answer(
            "📨 <b>Превью рассылки:</b>\n\n" + broadcast_text,
            parse_mode="HTML"
        )

        from bot.keyboards.inline import confirm_keyboard
        await message.answer(
            "Отправить это сообщение всем пользователям?",
            reply_markup=confirm_keyboard("broadcast")
        )

        # Сохраняем текст в state
        await state.update_data(broadcast_text=broadcast_text)

    except Exception as e:
        logger.error(f"Ошибка preview рассылки: {e}")
        await message.answer(
            "❌ Ошибка. Проверьте HTML разметку.",
            reply_markup=main_menu_keyboard()
        )
        await state.clear()


@router.callback_query(F.data == "confirm:broadcast")
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext):
    """Подтверждение рассылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    try:
        data = await state.get_data()
        broadcast_text = data.get('broadcast_text')

        if not broadcast_text:
            await callback.answer("❌ Текст не найден", show_alert=True)
            return

        await callback.message.edit_text(
            "📨 Рассылка началась...\n\n"
            "Это может занять некоторое время."
        )

        from database.models import User
        from sqlalchemy import select
        async with async_session_maker() as session:
            result = await session.execute(select(User))
            users = list(result.scalars().all())

        from main import bot
        success, fail = await broadcast_message(bot, users, broadcast_text)

        from bot.keyboards.inline import admin_panel_keyboard
        await callback.message.edit_text(
            f"✅ <b>Рассылка завершена!</b>\n\n"
            f"Успешно: {success}\n"
            f"Ошибок: {fail}",
            reply_markup=admin_panel_keyboard(),
            parse_mode="HTML"
        )

        await state.clear()
        logger.info(f"Админ {callback.from_user.id} выполнил рассылку: успешно {success}, ошибок {fail}")

    except Exception as e:
        logger.error(f"Ошибка рассылки: {e}")
        from bot.keyboards.inline import admin_panel_keyboard
        await callback.message.edit_text(
            f"❌ Ошибка рассылки:\n{str(e)}",
            reply_markup=admin_panel_keyboard()
        )
        await state.clear()


@router.callback_query(F.data == "cancel:broadcast")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    """Отмена рассылки"""
    from bot.keyboards.inline import admin_panel_keyboard
    await callback.message.edit_text(
        "❌ Рассылка отменена",
        reply_markup=admin_panel_keyboard()
    )
    await state.clear()
    await callback.answer()


# ==================== ДОБАВЛЕНИЕ ПРОМОКОДА ====================

@router.callback_query(F.data == "admin_add_promo")
async def admin_add_promo_start(callback: CallbackQuery, state: FSMContext):
    """Начало добавления промокода"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    async with async_session_maker() as session:
        shops = await get_all_shops(session)

    if not shops:
        await callback.answer("❌ Нет магазинов! Создайте тестовые данные: /testdata", show_alert=True)
        return

    # Сохраняем список магазинов в state для пагинации
    await state.update_data(available_shops=shops)

    from bot.keyboards.inline import shops_selection_keyboard
    await callback.message.edit_text(
        "➕ <b>Добавление промокода</b>\n\n"
        "Шаг 1/7: Выберите магазин или введите новое название:",
        reply_markup=shops_selection_keyboard(shops, page=0),
        parse_mode="HTML"
    )

    await state.set_state(PromoStates.waiting_shop)
    await callback.answer()


@router.message(PromoStates.waiting_shop)
async def promo_shop_entered(message: Message, state: FSMContext):
    """Получен магазин"""
    if not is_admin(message.from_user.id):
        return

    shop_name = message.text.strip()
    await state.update_data(shop_name=shop_name)

    await message.answer(
        f"✅ Магазин: <b>{shop_name}</b>\n\n"
        f"Шаг 2/7: Введите промокод:",
        parse_mode="HTML"
    )

    await state.set_state(PromoStates.waiting_code)


@router.callback_query(F.data.startswith("select_shop:"), PromoStates.waiting_shop)
async def promo_shop_selected(callback: CallbackQuery, state: FSMContext):
    """Выбран магазин из списка"""
    if not is_admin(callback.from_user.id):
        return

    # Получаем индекс магазина
    shop_idx = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    shops = data.get('available_shops', [])

    if shop_idx >= len(shops):
        await callback.answer("❌ Ошибка: магазин не найден", show_alert=True)
        return

    shop_name = shops[shop_idx]
    await state.update_data(shop_name=shop_name)

    await callback.message.edit_text(
        f"✅ Магазин: <b>{shop_name}</b>\n\n"
        f"Шаг 2/7: Введите промокод:",
        parse_mode="HTML"
    )

    await state.set_state(PromoStates.waiting_code)
    await callback.answer()


@router.callback_query(F.data.startswith("shops_select_page:"), PromoStates.waiting_shop)
async def shops_pagination_handler(callback: CallbackQuery, state: FSMContext):
    """Пагинация при выборе магазина"""
    if not is_admin(callback.from_user.id):
        return

    page = int(callback.data.split(":")[1])
    data = await state.get_data()
    shops = data.get('available_shops', [])

    from bot.keyboards.inline import shops_selection_keyboard
    await callback.message.edit_text(
        "➕ <b>Добавление промокода</b>\n\n"
        "Шаг 1/7: Выберите магазин или введите новое название:",
        reply_markup=shops_selection_keyboard(shops, page=page),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(PromoStates.waiting_code)
async def promo_code_entered(message: Message, state: FSMContext):
    """Получен код"""
    if not is_admin(message.from_user.id):
        return

    code = message.text.strip().upper()
    await state.update_data(code=code)

    async with async_session_maker() as session:
        categories = await get_all_categories(session)

    # Сохраняем отсортированный список категорий в state для пагинации
    sorted_categories = sorted(categories)
    await state.update_data(available_categories=sorted_categories)

    from bot.keyboards.inline import categories_selection_keyboard
    await message.answer(
        f"✅ Промокод: <code>{code}</code>\n\n"
        f"Шаг 3/7: Выберите категорию или введите новую:",
        reply_markup=categories_selection_keyboard(sorted_categories, page=0),
        parse_mode="HTML"
    )

    await state.set_state(PromoStates.waiting_category)


@router.message(PromoStates.waiting_category)
async def promo_category_entered(message: Message, state: FSMContext):
    """Получена категория"""
    if not is_admin(message.from_user.id):
        return

    category = message.text.strip()
    await state.update_data(category=category)

    await message.answer(
        f"✅ Категория: <b>{category}</b>\n\n"
        f"Шаг 4/7: Введите скидку (например: -20%, 500₽, 2+1):",
        parse_mode="HTML"
    )

    await state.set_state(PromoStates.waiting_discount)


@router.callback_query(F.data.startswith("select_category:"), PromoStates.waiting_category)
async def promo_category_selected(callback: CallbackQuery, state: FSMContext):
    """Выбрана категория из списка"""
    if not is_admin(callback.from_user.id):
        return

    # Получаем индекс категории
    category_idx = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    categories = data.get('available_categories', [])

    if category_idx >= len(categories):
        await callback.answer("❌ Ошибка: категория не найдена", show_alert=True)
        return

    category = categories[category_idx]
    await state.update_data(category=category)

    await callback.message.edit_text(
        f"✅ Категория: <b>{category}</b>\n\n"
        f"Шаг 4/7: Введите скидку (например: -20%, 500₽, 2+1):",
        parse_mode="HTML"
    )

    await state.set_state(PromoStates.waiting_discount)
    await callback.answer()


@router.callback_query(F.data.startswith("categories_select_page:"), PromoStates.waiting_category)
async def categories_pagination_handler(callback: CallbackQuery, state: FSMContext):
    """Пагинация при выборе категории"""
    if not is_admin(callback.from_user.id):
        return

    page = int(callback.data.split(":")[1])
    data = await state.get_data()
    categories = data.get('available_categories', [])

    from bot.keyboards.inline import categories_selection_keyboard
    code = data.get('code', '')
    await callback.message.edit_text(
        f"✅ Промокод: <code>{code}</code>\n\n"
        f"Шаг 3/7: Выберите категорию или введите новую:",
        reply_markup=categories_selection_keyboard(categories, page=page),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(PromoStates.waiting_discount)
async def promo_discount_entered(message: Message, state: FSMContext):
    """Получена скидка"""
    if not is_admin(message.from_user.id):
        return

    discount = message.text.strip()
    await state.update_data(discount_value=discount)

    await message.answer(
        f"✅ Скидка: <b>{discount}</b>\n\n"
        f"Шаг 5/7: Введите описание промокода:",
        parse_mode="HTML"
    )

    await state.set_state(PromoStates.waiting_description)


@router.message(PromoStates.waiting_description)
async def promo_description_entered(message: Message, state: FSMContext):
    """Получено описание"""
    if not is_admin(message.from_user.id):
        return

    description = message.text.strip()
    await state.update_data(description=description)

    await message.answer(
        f"✅ Описание сохранено\n\n"
        f"Шаг 6/7: Введите URL магазина:",
        parse_mode="HTML"
    )

    await state.set_state(PromoStates.waiting_url)


@router.message(PromoStates.waiting_url)
async def promo_url_entered(message: Message, state: FSMContext):
    """Получен URL"""
    if not is_admin(message.from_user.id):
        return

    url = message.text.strip()
    if not url.startswith('http'):
        url = 'https://' + url
    
    await state.update_data(shop_url=url)

    await message.answer(
        f"✅ URL сохранен\n\n"
        f"Шаг 7/7: Введите дату истечения (ДД.ММ.ГГГГ) или 'нет':",
        parse_mode="HTML"
    )

    await state.set_state(PromoStates.waiting_expires)


@router.message(PromoStates.waiting_expires)
async def promo_expires_entered(message: Message, state: FSMContext):
    """Получена дата истечения - финальный шаг"""
    if not is_admin(message.from_user.id):
        return

    expires_text = message.text.strip().lower()
    expires_at = None

    if expires_text != 'нет':
        try:
            expires_at = datetime.strptime(expires_text, '%d.%m.%Y')
        except ValueError:
            await message.answer("❌ Неверный формат даты! Используйте ДД.ММ.ГГГГ")
            return

    await state.update_data(expires_at=expires_at)

    # Получаем все данные
    data = await state.get_data()

    # Превью
    preview_text = (
        f"📋 <b>Предпросмотр промокода:</b>\n\n"
        f"🏪 Магазин: {data['shop_name']}\n"
        f"📋 Код: <code>{data['code']}</code>\n"
        f"📂 Категория: {data['category']}\n"
        f"💰 Скидка: {data['discount_value']}\n"
        f"📝 Описание: {data['description']}\n"
        f"🔗 URL: {data['shop_url']}\n"
        f"⏰ Истекает: {expires_at.strftime('%d.%m.%Y') if expires_at else 'Не указано'}\n"
    )

    from bot.keyboards.inline import confirm_keyboard
    await message.answer(
        preview_text,
        reply_markup=confirm_keyboard("add_promo"),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "confirm:add_promo")
async def confirm_add_promo(callback: CallbackQuery, state: FSMContext):
    """Подтверждение добавления промокода"""
    if not is_admin(callback.from_user.id):
        return

    try:
        data = await state.get_data()

        # Добавляем в БД
        from database.models import PromoCode
        async with async_session_maker() as session:
            new_promo = PromoCode(
                shop_name=data['shop_name'],
                code=data['code'],
                category=data['category'],
                discount_value=data['discount_value'],
                description=data['description'],
                shop_url=data['shop_url'],
                expires_at=data.get('expires_at'),
                is_active=True,
                is_hot=False  # Можно добавить логику определения "горячести"
            )
            session.add(new_promo)
            await session.commit()

        from bot.keyboards.inline import admin_panel_keyboard
        await callback.message.edit_text(
            f"✅ <b>Промокод успешно добавлен!</b>\n\n"
            f"Код: <code>{data['code']}</code>\n"
            f"Магазин: {data['shop_name']}",
            reply_markup=admin_panel_keyboard(),
            parse_mode="HTML"
        )

        await state.clear()
        logger.info(f"Админ {callback.from_user.id} добавил промокод {data['code']}")

    except Exception as e:
        logger.error(f"Ошибка добавления промокода: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
        await state.clear()


@router.callback_query(F.data == "cancel:add_promo")
async def cancel_add_promo(callback: CallbackQuery, state: FSMContext):
    """Отмена добавления"""
    from bot.keyboards.inline import admin_panel_keyboard
    await callback.message.edit_text(
        "❌ Добавление отменено",
        reply_markup=admin_panel_keyboard()
    )
    await state.clear()
    await callback.answer()


# ==================== УПРАВЛЕНИЕ ПРОМОКОДАМИ ====================

class AdminSearchStates(StatesGroup):
    """Состояния для поиска в админке"""
    waiting_search = State()
    waiting_delete_id = State()


@router.callback_query(F.data == "admin_manage_promos")
async def admin_manage_promos(callback: CallbackQuery):
    """Управление промокодами"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    from bot.keyboards.inline import manage_promos_keyboard
    await callback.message.edit_text(
        "🗂️ <b>Управление промокодами</b>\n\n"
        "Выберите действие:",
        reply_markup=manage_promos_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_list_promos")
async def admin_list_all_promos(callback: CallbackQuery):
    """Список всех промокодов с пагинацией"""
    if not is_admin(callback.from_user.id):
        return

    try:
        from database.models import PromoCode
        from sqlalchemy import select
        
        async with async_session_maker() as session:
            result = await session.execute(
                select(PromoCode).order_by(PromoCode.created_at.desc())
            )
            all_promos = list(result.scalars().all())

        if not all_promos:
            await callback.answer("📭 Промокодов нет", show_alert=True)
            return

        from bot.keyboards.inline import admin_promos_list_keyboard
        await callback.message.edit_text(
            f"📋 <b>Все промокоды</b>\n\n"
            f"Всего: {len(all_promos)}\n"
            f"Страница: 1/{(len(all_promos) + 9) // 10}",
            reply_markup=admin_promos_list_keyboard(all_promos, page=0),
            parse_mode="HTML"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка списка промокодов: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("admin_promos_page:"))
async def admin_promos_pagination(callback: CallbackQuery):
    """Пагинация списка промокодов в админке"""
    if not is_admin(callback.from_user.id):
        return

    try:
        page = int(callback.data.split(":")[1])
        
        from database.models import PromoCode
        from sqlalchemy import select
        
        async with async_session_maker() as session:
            result = await session.execute(
                select(PromoCode).order_by(PromoCode.created_at.desc())
            )
            all_promos = list(result.scalars().all())

        from bot.keyboards.inline import admin_promos_list_keyboard
        await callback.message.edit_text(
            f"📋 <b>Все промокоды</b>\n\n"
            f"Всего: {len(all_promos)}\n"
            f"Страница: {page + 1}/{(len(all_promos) + 9) // 10}",
            reply_markup=admin_promos_list_keyboard(all_promos, page=page),
            parse_mode="HTML"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка пагинации: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("admin_view_promo:"))
async def admin_view_promo(callback: CallbackQuery):
    """Просмотр промокода в админке"""
    if not is_admin(callback.from_user.id):
        return

    try:
        promo_id = int(callback.data.split(":")[1])
        
        async with async_session_maker() as session:
            promo = await get_promocode_by_id(session, promo_id)

        if not promo:
            await callback.answer("❌ Промокод не найден", show_alert=True)
            return

        promo_info = (
            f"📋 <b>Промокод #{promo.id}</b>\n\n"
            f"🏪 Магазин: {promo.shop_name}\n"
            f"📋 Код: <code>{promo.code}</code>\n"
            f"📂 Категория: {promo.category}\n"
            f"💰 Скидка: {promo.discount_value or 'Не указана'}\n"
            f"📝 Описание: {promo.description or 'Нет'}\n"
            f"🔗 URL: {promo.shop_url}\n"
            f"👁 Просмотров: {promo.views_count}\n"
            f"📋 Копирований: {promo.copies_count}\n"
            f"🔥 Горячий: {'Да' if promo.is_hot else 'Нет'}\n"
            f"✅ Активен: {'Да' if promo.is_active else 'Нет'}\n"
            f"⏰ Создан: {promo.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        )

        if promo.expires_at:
            promo_info += f"⏳ Истекает: {promo.expires_at.strftime('%d.%m.%Y')}\n"

        from bot.keyboards.inline import promo_actions_keyboard
        await callback.message.edit_text(
            promo_info,
            reply_markup=promo_actions_keyboard(promo_id),
            parse_mode="HTML"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка просмотра промокода: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data == "admin_search_promo")
async def admin_search_prompt(callback: CallbackQuery, state: FSMContext):
    """Запрос поиска промокода"""
    if not is_admin(callback.from_user.id):
        return

    await callback.message.edit_text(
        "🔍 <b>Поиск промокода</b>\n\n"
        "Введите для поиска:\n"
        "• ID промокода\n"
        "• Название магазина\n"
        "• Код промокода\n"
        "• Категорию",
        parse_mode="HTML"
    )

    await state.set_state(AdminSearchStates.waiting_search)
    await callback.answer()


@router.message(AdminSearchStates.waiting_search)
async def admin_search_process(message: Message, state: FSMContext):
    """Обработка поиска"""
    if not is_admin(message.from_user.id):
        return

    try:
        query = message.text.strip()
        
        from database.models import PromoCode
        from sqlalchemy import select, or_
        
        async with async_session_maker() as session:
            # Поиск по ID, магазину, коду или категории
            stmt = select(PromoCode).where(
                or_(
                    PromoCode.id == int(query) if query.isdigit() else False,
                    PromoCode.shop_name.ilike(f"%{query}%"),
                    PromoCode.code.ilike(f"%{query}%"),
                    PromoCode.category.ilike(f"%{query}%")
                )
            ).order_by(PromoCode.created_at.desc())
            
            result = await session.execute(stmt)
            found_promos = list(result.scalars().all())

        if not found_promos:
            from bot.keyboards.inline import manage_promos_keyboard
            await message.answer(
                f"😔 По запросу '<b>{query}</b>' ничего не найдено",
                reply_markup=manage_promos_keyboard(),
                parse_mode="HTML"
            )
        else:
            from bot.keyboards.inline import admin_promos_list_keyboard
            await message.answer(
                f"🔍 <b>Результаты поиска</b>\n\n"
                f"Запрос: <i>{query}</i>\n"
                f"Найдено: {len(found_promos)}",
                reply_markup=admin_promos_list_keyboard(found_promos, page=0),
                parse_mode="HTML"
            )

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка поиска в админке: {e}")
        await message.answer("❌ Ошибка поиска")
        await state.clear()


@router.callback_query(F.data == "admin_delete_promo")
async def admin_delete_promo_prompt(callback: CallbackQuery, state: FSMContext):
    """Запрос ID для удаления"""
    if not is_admin(callback.from_user.id):
        return

    await callback.message.edit_text(
        "🗑️ <b>Удаление промокода</b>\n\n"
        "Введите ID промокода для удаления:",
        parse_mode="HTML"
    )
    
    await state.set_state(AdminSearchStates.waiting_delete_id)
    await callback.answer()


@router.message(AdminSearchStates.waiting_delete_id)
async def admin_delete_promo_process(message: Message, state: FSMContext):
    """Обработка удаления"""
    if not is_admin(message.from_user.id):
        return

    try:
        promo_id = int(message.text.strip())
        
        from database.models import PromoCode
        from sqlalchemy import select, delete
        
        async with async_session_maker() as session:
            # Проверяем существование
            result = await session.execute(
                select(PromoCode).where(PromoCode.id == promo_id)
            )
            promo = result.scalar_one_or_none()
            
            if not promo:
                await message.answer("❌ Промокод не найден")
                await state.clear()
                return
            
            # Сохраняем инфо для логов
            promo_code = promo.code
            shop_name = promo.shop_name
            
            # Удаляем
            await session.execute(
                delete(PromoCode).where(PromoCode.id == promo_id)
            )
            await session.commit()

        from bot.keyboards.inline import manage_promos_keyboard
        await message.answer(
            f"✅ <b>Промокод удалён</b>\n\n"
            f"ID: {promo_id}\n"
            f"Код: <code>{promo_code}</code>\n"
            f"Магазин: {shop_name}",
            reply_markup=manage_promos_keyboard(),
            parse_mode="HTML"
        )

        logger.info(f"Админ {message.from_user.id} удалил промокод {promo_id} ({promo_code})")
        await state.clear()

    except ValueError:
        await message.answer("❌ ID должен быть числом")
    except Exception as e:
        logger.error(f"Ошибка удаления промокода: {e}")
        await message.answer("❌ Ошибка удаления")
        await state.clear()


@router.callback_query(F.data.startswith("admin_delete:"))
async def admin_delete_promo_confirm(callback: CallbackQuery):
    """Подтверждение удаления из просмотра"""
    if not is_admin(callback.from_user.id):
        return

    promo_id = int(callback.data.split(":")[1])
    
    from bot.keyboards.inline import confirm_keyboard
    await callback.message.edit_text(
        f"⚠️ <b>Подтверждение удаления</b>\n\n"
        f"Удалить промокод #{promo_id}?",
        reply_markup=confirm_keyboard(f"delete_promo:{promo_id}"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm:delete_promo:"))
async def confirm_delete_promo(callback: CallbackQuery):
    """Окончательное удаление"""
    if not is_admin(callback.from_user.id):
        return

    try:
        promo_id = int(callback.data.split(":")[2])
        
        from database.models import PromoCode
        from sqlalchemy import select, delete
        
        async with async_session_maker() as session:
            result = await session.execute(
                select(PromoCode).where(PromoCode.id == promo_id)
            )
            promo = result.scalar_one_or_none()
            
            if promo:
                promo_code = promo.code
                await session.execute(
                    delete(PromoCode).where(PromoCode.id == promo_id)
                )
                await session.commit()

                from bot.keyboards.inline import manage_promos_keyboard
                await callback.message.edit_text(
                    f"✅ Промокод <code>{promo_code}</code> удалён",
                    reply_markup=manage_promos_keyboard(),
                    parse_mode="HTML"
                )
                logger.info(f"Админ {callback.from_user.id} удалил промокод {promo_id}")
            else:
                await callback.answer("❌ Промокод не найден", show_alert=True)

    except Exception as e:
        logger.error(f"Ошибка удаления: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("cancel:delete_promo:"))
async def cancel_delete_promo(callback: CallbackQuery):
    """Отмена удаления"""
    promo_id = int(callback.data.split(":")[2])
    
    from bot.keyboards.inline import promo_actions_keyboard
    await callback.message.edit_text(
        "❌ Удаление отменено",
        reply_markup=promo_actions_keyboard(promo_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_toggle:"))
async def admin_toggle_promo_status(callback: CallbackQuery):
    """Переключить статус промокода"""
    if not is_admin(callback.from_user.id):
        return

    try:
        promo_id = int(callback.data.split(":")[1])
        
        async with async_session_maker() as session:
            promo = await toggle_promocode_status(session, promo_id)
            
            if not promo:
                await callback.answer("❌ Промокод не найден", show_alert=True)
                return
            
            status_text = "✅ Активен" if promo.is_active else "❌ Неактивен"
            
            await callback.answer(f"Статус изменён: {status_text}", show_alert=True)
            
            # Обновляем информацию
            promo_info = (
                f"📋 <b>Промокод #{promo.id}</b>\n\n"
                f"🏪 Магазин: {promo.shop_name}\n"
                f"📋 Код: <code>{promo.code}</code>\n"
                f"📂 Категория: {promo.category}\n"
                f"💰 Скидка: {promo.discount_value or 'Не указана'}\n"
                f"📝 Описание: {promo.description or 'Нет'}\n"
                f"🔗 URL: {promo.shop_url}\n"
                f"👁 Просмотров: {promo.views_count}\n"
                f"📋 Копирований: {promo.copies_count}\n"
                f"🔥 Горячий: {'Да' if promo.is_hot else 'Нет'}\n"
                f"✅ Активен: {'Да' if promo.is_active else 'Нет'}\n"
                f"⏰ Создан: {promo.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            )
            
            if promo.expires_at:
                promo_info += f"⏳ Истекает: {promo.expires_at.strftime('%d.%m.%Y')}\n"
            
            from bot.keyboards.inline import promo_actions_keyboard
            await callback.message.edit_text(
                promo_info,
                reply_markup=promo_actions_keyboard(promo_id),
                parse_mode="HTML"
            )

    except Exception as e:
        logger.error(f"Ошибка переключения статуса: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


# ==================== СМЕНА БАННЕРОВ ====================

@router.callback_query(F.data == "admin_change_banners")
async def admin_change_banners(callback: CallbackQuery, state: FSMContext):
    """Меню смены баннеров"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    from bot.keyboards.inline import banners_menu_keyboard
    await callback.message.edit_text(
        "🖼️ <b>Смена баннеров</b>\n\n"
        "Выберите баннер для замены:",
        reply_markup=banners_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("change_banner:"))
async def select_banner_to_change(callback: CallbackQuery, state: FSMContext):
    """Выбор баннера для замены"""
    if not is_admin(callback.from_user.id):
        return

    banner_type = callback.data.split(":")[1]
    await state.update_data(banner_type=banner_type)

    banner_names = {
        "main": "Главное меню (hello.jpg)",
        "categories": "Категории (katigories.jpg)",
        "hot": "Горячие предложения (goriachie_predlojenia.jpg)",
        "search": "Поиск (search.jpg)",
        "shops": "Магазины (shops.jpg)",
        "favorites": "Избранное (izbrannoe.jpg)",
        "subscription": "Подписка (podpiska.jpg)",
        "new_promos": "Новые промокоды (new_promokodes.jpg)"
    }

    await callback.message.edit_text(
        f"🖼️ Замена баннера: <b>{banner_names.get(banner_type, banner_type)}</b>\n\n"
        f"Отправьте новое изображение:",
        parse_mode="HTML"
    )

    await state.set_state(BannerStates.waiting_banner_photo)
    await callback.answer()


@router.message(BannerStates.waiting_banner_photo, F.photo)
async def save_new_banner(message: Message, state: FSMContext):
    """Сохранение нового баннера"""
    if not is_admin(message.from_user.id):
        return

    try:
        data = await state.get_data()
        banner_type = data.get('banner_type')

        # Имена файлов баннеров
        banner_files = {
            "main": "baners/hello.jpg",
            "categories": "baners/katigories.jpg",
            "hot": "baners/goriachie_predlojenia.jpg",
            "search": "baners/search.jpg",
            "shops": "baners/shops.jpg",
            "favorites": "baners/izbrannoe.jpg",
            "subscription": "baners/podpiska.jpg",
            "new_promos": "baners/new_promokodes.jpg"
        }

        file_path = banner_files.get(banner_type)
        if not file_path:
            await message.answer("❌ Неизвестный тип баннера")
            await state.clear()
            return

        # Скачиваем фото
        from main import bot
        photo = message.photo[-1]  # Берем фото наибольшего размера
        file = await bot.get_file(photo.file_id)
        
        # Сохраняем
        os.makedirs("baners", exist_ok=True)
        await bot.download_file(file.file_path, file_path)

        from bot.keyboards.inline import admin_panel_keyboard
        await message.answer(
            f"✅ Баннер успешно заменён!\n\n"
            f"Файл: {file_path}",
            reply_markup=admin_panel_keyboard()
        )

        await state.clear()
        logger.info(f"Админ {message.from_user.id} заменил баннер {banner_type}")

    except Exception as e:
        logger.error(f"Ошибка сохранения баннера: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")
        await state.clear()


# ==================== ПАРСИНГ ====================

@router.callback_query(F.data == "admin_run_parser")
async def admin_run_parser(callback: CallbackQuery):
    """Запуск парсинга вручную с отслеживанием прогресса"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    try:
        # Получаем scheduler из хранилища состояния
        scheduler = bot_storage.get("parser_scheduler")

        if not scheduler:
            await callback.answer("❌ Планировщик не найден", show_alert=True)
            return

        # Проверяем, не выполняется ли уже парсинг
        if scheduler.is_parsing:
            await callback.answer("⏳ Парсинг уже выполняется", show_alert=True)
            return

        # Отправляем начальное сообщение
        await callback.message.edit_text(
            "🔄 <b>Парсинг запущен!</b>\n\n"
            "⏳ Инициализация...",
            parse_mode="HTML"
        )

        # Запускаем парсинг асинхронно
        import asyncio
        asyncio.create_task(scheduler.run_now())

        # Запускаем мониторинг прогресса
        asyncio.create_task(monitor_parsing_progress(callback.message, scheduler))

        await callback.answer("✅ Парсинг запущен", show_alert=True)
        logger.info(f"Админ {callback.from_user.id} запустил ручной парсинг")

    except Exception as e:
        logger.error(f"Ошибка запуска парсинга: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


async def monitor_parsing_progress(message: Message, scheduler):
    """Мониторинг и обновление прогресса парсинга в реальном времени"""
    import asyncio
    from bot.keyboards.inline import admin_panel_keyboard

    last_text = ""
    update_count = 0

    try:
        while True:
            # Получаем прогресс
            progress = scheduler.get_progress()

            # Формируем текст сообщения
            status_emoji = {
                "idle": "⏸️",
                "running": "🔄",
                "completed": "✅",
                "error": "❌"
            }

            emoji = status_emoji.get(progress["status"], "❓")

            text = f"{emoji} <b>Парсинг промокодов</b>\n\n"

            if progress["is_parsing"]:
                elapsed = progress.get("elapsed_seconds") or 0
                minutes = int(elapsed // 60)
                seconds = int(elapsed % 60)

                text += f"⏱️ Время: {minutes:02d}:{seconds:02d}\n"
                text += f"📦 Найдено промокодов: {progress['promos_found']}\n"

                if progress['promos_found'] > 0:
                    text += f"🆕 Новых: {progress['new_added']}\n"
                    text += f"🔄 Обновлено: {progress['updated']}\n"

                # Анимация загрузки
                dots = "." * ((update_count % 3) + 1)
                text += f"\n💫 Обработка данных{dots}"

            elif progress["status"] == "completed":
                elapsed = progress.get("elapsed_seconds") or 0
                minutes = int(elapsed // 60)
                seconds = int(elapsed % 60)

                text += f"✅ <b>Парсинг завершен успешно!</b>\n\n"
                text += f"⏱️ Время выполнения: {minutes:02d}:{seconds:02d}\n"
                text += f"📦 Всего найдено: {progress['promos_found']}\n"
                text += f"🆕 Новых: {progress['new_added']}\n"
                text += f"🔄 Обновлено: {progress['updated']}\n"

                # Завершаем мониторинг
                await message.edit_text(text, reply_markup=admin_panel_keyboard(), parse_mode="HTML")
                break

            elif progress["status"] == "error":
                text += f"❌ <b>Ошибка при парсинге</b>\n\n"

                if progress["errors"]:
                    text += f"📋 Ошибки:\n"
                    for i, error in enumerate(progress["errors"][-3:], 1):  # Показываем последние 3 ошибки
                        error_short = error[:100] + "..." if len(error) > 100 else error
                        text += f"{i}. {error_short}\n"

                text += f"\n📦 Найдено до ошибки: {progress['promos_found']}\n"

                # Завершаем мониторинг
                await message.edit_text(text, reply_markup=admin_panel_keyboard(), parse_mode="HTML")
                break

            # Обновляем сообщение только если текст изменился
            if text != last_text:
                try:
                    await message.edit_text(text, parse_mode="HTML")
                    last_text = text
                except Exception as e:
                    # Игнорируем ошибки редактирования (например, если текст не изменился)
                    logger.debug(f"Ошибка обновления прогресса: {e}")

            update_count += 1
            await asyncio.sleep(2)  # Обновляем каждые 2 секунды

    except asyncio.CancelledError:
        logger.info("Мониторинг прогресса парсинга остановлен")
    except Exception as e:
        logger.error(f"Ошибка мониторинга прогресса: {e}")
        try:
            await message.edit_text(
                f"❌ Ошибка мониторинга: {str(e)}",
                reply_markup=admin_panel_keyboard(),
                parse_mode="HTML"
            )
        except:
            pass


# ==================== ПРОЧИЕ КОМАНДЫ ====================

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Команда /stats для админа"""
    if not is_admin(message.from_user.id):
        return

    try:
        async with async_session_maker() as session:
            stats = await get_stats(session)

        stats_text = format_stats_message(stats)

        await message.answer(
            stats_text,
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка /stats: {e}")
        await message.answer("❌ Ошибка получения статистики")


@router.message(Command("testdata"))
async def cmd_testdata(message: Message):
    """Команда создания тестовых данных"""
    if not is_admin(message.from_user.id):
        return

    try:
        await message.answer("⏳ Создаю тестовые промокоды...")

        from utils.test_data import create_test_promocodes

        async with async_session_maker() as session:
            count = await create_test_promocodes(session)

        await message.answer(
            f"✅ Создано {count} тестовых промокодов!\n\n"
            f"Теперь можете проверить:\n"
            f"🏪 Магазины\n"
            f"📂 Категории\n"
            f"🔥 Горячие предложения"
        )

    except Exception as e:
        logger.error(f"Ошибка создания тестовых данных: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")