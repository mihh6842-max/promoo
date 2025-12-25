"""
Обработчик категорий
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, FSInputFile, InputMediaPhoto
from loguru import logger

from database import async_session_maker
from database.crud import (
    get_all_categories,
    get_promocodes_by_category,
    get_hot_promocodes,
    get_promocode_by_id,
    increment_views,
    increment_copies,
    is_in_favorites,
    get_promocodes_by_shop
)
from bot.keyboards.inline import (
    categories_keyboard,
    promocodes_list_keyboard,
    promocode_card_keyboard,
    main_menu_keyboard
)
from utils.animations import format_promocode_card
from utils.state_storage import bot_storage

router = Router(name='categories')


@router.message(F.text == "📂 Категории")
async def categories_button(message: Message):
    """Кнопка категорий"""
    try:
        async with async_session_maker() as session:
            categories = await get_all_categories(session)

        if not categories:
            text = "😔 Пока нет доступных категорий.\n\nСоздайте тестовые данные: /testdata"
            markup = main_menu_keyboard()
        else:
            text = f"📂 <b>Категории ({len(categories)})</b>\n\nВыберите категорию:"
            markup = categories_keyboard(categories)

        await bot_storage.edit_or_send(
            message.from_user.id,
            message,
            text,
            reply_markup=markup,
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка показа категорий: {e}")


@router.message(F.text == "🔥 Горячие")
async def hot_button(message: Message):
    """Кнопка горячих предложений"""
    try:
        async with async_session_maker() as session:
            promos = await get_hot_promocodes(session, limit=50)

        if not promos:
            text = "😔 Сейчас нет горячих предложений.\n\nГорячими считаются промокоды со скидкой >30%\n\nСоздайте тестовые данные: /testdata"
            markup = main_menu_keyboard()
        else:
            text = (f"🔥 <b>ГОРЯЧИЕ ПРЕДЛОЖЕНИЯ</b> 🔥\n\n"
                   f"Скидки более 30%!\n"
                   f"Найдено: {len(promos)}\n\n"
                   f"Выберите промокод:")
            markup = promocodes_list_keyboard(
                promos,
                page=0,
                callback_prefix="hot_promo",
                back_callback="main_menu"
            )

        await bot_storage.edit_or_send(
            message.from_user.id,
            message,
            text,
            reply_markup=markup,
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка показа горячих предложений: {e}")


@router.callback_query(F.data == "categories_menu")
async def show_categories_menu(callback: CallbackQuery):
    """Показать список категорий"""
    try:
        async with async_session_maker() as session:
            categories = await get_all_categories(session)

        banner_path = "baners/katigories.jpg"

        if not categories:
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=FSInputFile(banner_path),
                    caption="😔 Пока нет доступных категорий.\nПопробуйте позже!",
                    parse_mode="HTML"
                ),
                reply_markup=main_menu_keyboard()
            )
            await callback.answer()
            return

        await callback.message.edit_media(
            media=InputMediaPhoto(
                media=FSInputFile(banner_path),
                caption=f"📂 <b>Категории ({len(categories)})</b>\n\n"
                        f"Выберите категорию:",
                parse_mode="HTML"
            ),
            reply_markup=categories_keyboard(categories)
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка показа категорий: {e}")
        await callback.answer("❌ Ошибка загрузки", show_alert=True)


@router.callback_query(F.data.startswith("category:"))
async def show_category_promos(callback: CallbackQuery):
    """Показать промокоды категории"""
    try:
        category = callback.data.split(":", 1)[1]

        async with async_session_maker() as session:
            promos = await get_promocodes_by_category(session, category)

        if not promos:
            await callback.answer(
                f"😔 В категории {category} пока нет промокодов",
                show_alert=True
            )
            return

        await callback.message.edit_caption(
            caption=f"📂 <b>{category}</b>\n\n"
                    f"Найдено промокодов: {len(promos)}\n\n"
                    f"Выберите промокод:",
            reply_markup=promocodes_list_keyboard(
                promos,
                page=0,
                callback_prefix="cat_promo",
                back_callback="categories_menu"
            ),
            parse_mode="HTML"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка показа промокодов категории: {e}")
        await callback.answer("❌ Ошибка загрузки", show_alert=True)


@router.callback_query(F.data == "hot_offers")
async def show_hot_offers(callback: CallbackQuery):
    """Показать горячие предложения"""
    try:
        async with async_session_maker() as session:
            promos = await get_hot_promocodes(session, limit=50)

        banner_path = "baners/goriachie_predlojenia.jpg"

        if not promos:
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=FSInputFile(banner_path),
                    caption="😔 Сейчас нет горячих предложений.\nЗаходите позже!",
                    parse_mode="HTML"
                ),
                reply_markup=main_menu_keyboard()
            )
            await callback.answer()
            return

        await callback.message.edit_media(
            media=InputMediaPhoto(
                media=FSInputFile(banner_path),
                caption=f"🔥 <b>ГОРЯЧИЕ ПРЕДЛОЖЕНИЯ</b> 🔥\n\n"
                        f"Скидки более 30%!\n"
                        f"Найдено: {len(promos)}\n\n"
                        f"Выберите промокод:",
                parse_mode="HTML"
            ),
            reply_markup=promocodes_list_keyboard(
                promos,
                page=0,
                callback_prefix="hot_promo",
                back_callback="main_menu"
            )
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка показа горячих предложений: {e}")
        await callback.answer("❌ Ошибка загрузки", show_alert=True)


@router.callback_query(F.data.startswith("promo:"))
async def show_promocode(callback: CallbackQuery):
    """Показать карточку промокода"""
    await _show_promo_card(callback, "promo", "main_menu")


@router.callback_query(F.data.startswith("shop_promo:"))
async def show_shop_promocode(callback: CallbackQuery):
    """Показать промокод из магазина"""
    await _show_promo_card(callback, "shop_promo", "shops_menu")


@router.callback_query(F.data.startswith("cat_promo:"))
async def show_category_promocode(callback: CallbackQuery):
    """Показать промокод из категории"""
    await _show_promo_card(callback, "cat_promo", "categories_menu")


@router.callback_query(F.data.startswith("hot_promo:"))
async def show_hot_promocode(callback: CallbackQuery):
    """Показать горячий промокод"""
    await _show_promo_card(callback, "hot_promo", "hot_offers")


@router.callback_query(F.data.startswith("hot_promo_page:"))
async def hot_offers_pagination(callback: CallbackQuery):
    """Пагинация горячих предложений"""
    try:
        page = int(callback.data.split(":")[1])

        async with async_session_maker() as session:
            promos = await get_hot_promocodes(session, limit=50)

        banner_path = "baners/goriachie_predlojenia.jpg"
        await callback.message.edit_media(
            media=InputMediaPhoto(
                media=FSInputFile(banner_path),
                caption=f"🔥 <b>ГОРЯЧИЕ ПРЕДЛОЖЕНИЯ</b> 🔥\n\n"
                        f"Скидки более 30%!\n"
                        f"Найдено: {len(promos)}\n\n"
                        f"Выберите промокод:",
                parse_mode="HTML"
            ),
            reply_markup=promocodes_list_keyboard(
                promos,
                page=page,
                callback_prefix="hot_promo",
                back_callback="main_menu"
            )
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка пагинации горячих предложений: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("cat_promo_page:"))
async def category_promos_pagination(callback: CallbackQuery):
    """Пагинация промокодов категории"""
    try:
        page = int(callback.data.split(":")[1])
        
        # Извлекаем категорию из текущего сообщения
        current_text = callback.message.caption or callback.message.text
        if "📂 <b>" in current_text:
            category = current_text.split("📂 <b>")[1].split("</b>")[0]
            
            async with async_session_maker() as session:
                promos = await get_promocodes_by_category(session, category)
            
            await callback.message.edit_caption(
                caption=f"📂 <b>{category}</b>\n\n"
                        f"Найдено промокодов: {len(promos)}\n\n"
                        f"Выберите промокод:",
                reply_markup=promocodes_list_keyboard(
                    promos,
                    page=page,
                    callback_prefix="cat_promo",
                    back_callback="categories_menu"
                ),
                parse_mode="HTML"
            )
            await callback.answer()
        else:
            await callback.answer("❌ Не удалось определить категорию", show_alert=True)
        
    except Exception as e:
        logger.error(f"Ошибка пагинации категории: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("shop_promo_page:"))
async def shop_promos_pagination(callback: CallbackQuery):
    """Пагинация промокодов магазина"""
    try:
        page = int(callback.data.split(":")[1])
        
        # Парсим название магазина из текущего сообщения
        current_text = callback.message.caption or callback.message.text
        if "🏪 <b>" in current_text:
            shop_name = current_text.split("🏪 <b>")[1].split("</b>")[0]
            
            async with async_session_maker() as session:
                promos = await get_promocodes_by_shop(session, shop_name)
            
            await callback.message.edit_caption(
                caption=f"🏪 <b>{shop_name}</b>\n\n"
                        f"Найдено промокодов: {len(promos)}\n\n"
                        f"Выберите промокод:",
                reply_markup=promocodes_list_keyboard(
                    promos,
                    page=page,
                    callback_prefix="shop_promo",
                    back_callback="shops_menu"
                ),
                parse_mode="HTML"
            )
            await callback.answer()
        else:
            await callback.answer("❌ Не удалось определить магазин", show_alert=True)
        
    except Exception as e:
        logger.error(f"Ошибка пагинации магазина: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data == "current_page")
async def ignore_current_page(callback: CallbackQuery):
    """Игнорировать нажатие на индикатор страницы"""
    await callback.answer()


async def _show_promo_card(callback: CallbackQuery, prefix: str, back_callback: str):
    """Вспомогательная функция показа карточки промокода"""
    try:
        promo_id = int(callback.data.split(":")[1])

        async with async_session_maker() as session:
            promo = await get_promocode_by_id(session, promo_id)

            if not promo:
                await callback.answer("❌ Промокод не найден", show_alert=True)
                return

            # Увеличиваем счетчик просмотров
            await increment_views(session, promo_id)

            # Проверяем, в избранном ли
            is_fav = await is_in_favorites(session, callback.from_user.id, promo_id)

        # Форматируем карточку
        card_text = format_promocode_card(promo, is_fav)
        markup = promocode_card_keyboard(
            promo_id,
            promo.code,
            promo.shop_url,
            is_fav,
            back_callback
        )

        # Проверяем, есть ли у сообщения медиа (фото)
        if callback.message.photo:
            # Если есть фото - редактируем caption
            await callback.message.edit_caption(
                caption=card_text,
                reply_markup=markup,
                parse_mode="HTML"
            )
        else:
            # Если текстовое сообщение - редактируем текст
            await callback.message.edit_text(
                text=card_text,
                reply_markup=markup,
                parse_mode="HTML"
            )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка показа промокода: {e}")
        await callback.answer("❌ Ошибка загрузки", show_alert=True)


@router.callback_query(F.data.startswith("copy:"))
async def copy_promocode(callback: CallbackQuery):
    """Копирование промокода"""
    try:
        promo_id = int(callback.data.split(":")[1])

        async with async_session_maker() as session:
            promo = await get_promocode_by_id(session, promo_id)

            if not promo:
                await callback.answer("❌ Промокод не найден", show_alert=True)
                return

            # Увеличиваем счетчик копирований
            await increment_copies(session, promo_id)

        # Показываем промокод для копирования
        await callback.answer(
            f"📋 Промокод: {promo.code}\n\n"
            f"✅ Нажмите на код выше, чтобы скопировать!",
            show_alert=True
        )

        logger.info(f"Пользователь {callback.from_user.id} скопировал промокод {promo.code}")

    except Exception as e:
        logger.error(f"Ошибка копирования промокода: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("share:"))
async def share_promocode(callback: CallbackQuery):
    """Поделиться промокодом"""
    try:
        promo_id = int(callback.data.split(":")[1])

        async with async_session_maker() as session:
            promo = await get_promocode_by_id(session, promo_id)

            if not promo:
                await callback.answer("❌ Промокод не найден", show_alert=True)
                return

        # Формируем сообщение для шаринга
        share_text = (
            f"🎁 {promo.shop_name}\n"
            f"💰 {promo.discount_value or 'Скидка'}\n\n"
            f"📋 Промокод: <code>{promo.code}</code>\n\n"
            f"Используй PromoBot для поиска скидок: @YourBotUsername"
        )

        await callback.message.answer(
            "📤 <b>Поделитесь этим промокодом:</b>\n\n" + share_text,
            parse_mode="HTML"
        )

        await callback.answer("✅ Отправлено!")

    except Exception as e:
        logger.error(f"Ошибка шаринга промокода: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)