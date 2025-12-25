"""
Обработчик магазинов
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, FSInputFile, InputMediaPhoto
from loguru import logger

from database import async_session_maker
from database.crud import get_all_shops, get_promocodes_by_shop
from bot.keyboards.inline import shops_list_keyboard, promocodes_list_keyboard, main_menu_keyboard
from utils.state_storage import bot_storage

router = Router(name='shops')


@router.message(F.text == "🏪 Магазины")
async def shops_button(message: Message):
    """Кнопка магазинов"""
    try:
        async with async_session_maker() as session:
            shops = await get_all_shops(session)

        if not shops:
            text = "😔 Пока нет доступных магазинов.\n\nПромокоды появятся после автоматического обновления."
            markup = main_menu_keyboard()
        else:
            text = (f"🏪 <b>Магазины ({len(shops)})</b>\n\n"
                   f"Выберите магазин:")
            markup = shops_list_keyboard(shops, page=0)

        bot_msg = await bot_storage.edit_or_send(
            message.from_user.id,
            message,
            text,
            reply_markup=markup,
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка показа магазинов: {e}")


@router.callback_query(F.data == "shops_menu")
async def show_shops_menu(callback: CallbackQuery):
    """Показать список магазинов"""
    try:
        async with async_session_maker() as session:
            shops = await get_all_shops(session)

        banner_path = "baners/shops.jpg"

        if not shops:
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=FSInputFile(banner_path),
                    caption="😔 Пока нет доступных магазинов.\nПопробуйте позже!",
                    parse_mode="HTML"
                ),
                reply_markup=main_menu_keyboard()
            )
            await callback.answer()
            return

        await callback.message.edit_media(
            media=InputMediaPhoto(
                media=FSInputFile(banner_path),
                caption=f"🏪 <b>Магазины ({len(shops)})</b>\n\n"
                        f"Выберите магазин для просмотра промокодов:",
                parse_mode="HTML"
            ),
            reply_markup=shops_list_keyboard(shops, page=0)
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка показа магазинов: {e}")
        await callback.answer("❌ Ошибка загрузки", show_alert=True)


@router.callback_query(F.data.startswith("shops_page:"))
async def shops_pagination(callback: CallbackQuery):
    """Пагинация магазинов"""
    try:
        page = int(callback.data.split(":")[1])

        async with async_session_maker() as session:
            shops = await get_all_shops(session)

        await callback.message.edit_caption(
            caption=f"🏪 <b>Магазины ({len(shops)})</b>\n\n"
                    f"Выберите магазин для просмотра промокодов:",
            reply_markup=shops_list_keyboard(shops, page=page),
            parse_mode="HTML"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка пагинации магазинов: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("shop:"))
async def show_shop_promos(callback: CallbackQuery):
    """Показать промокоды магазина"""
    try:
        # Извлекаем название магазина из callback_data
        shop_name = callback.data.split(":", 1)[1]

        async with async_session_maker() as session:
            promos = await get_promocodes_by_shop(session, shop_name)

        if not promos:
            await callback.answer(
                f"😔 В магазине {shop_name} пока нет промокодов",
                show_alert=True
            )
            return

        await callback.message.edit_caption(
            caption=f"🏪 <b>{shop_name}</b>\n\n"
                    f"Найдено промокодов: {len(promos)}\n\n"
                    f"Выберите промокод:",
            reply_markup=promocodes_list_keyboard(
                promos,
                page=0,
                callback_prefix="shop_promo",
                back_callback="shops_menu"
            ),
            parse_mode="HTML"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка показа промокодов магазина: {e}")
        await callback.answer("❌ Ошибка загрузки", show_alert=True)


@router.callback_query(F.data.startswith("shop_promo_page:"))
async def shop_promos_pagination(callback: CallbackQuery):
    """Пагинация промокодов магазина"""
    try:
        # TODO: Нужно сохранять shop_name в state или в callback_data
        # Пока просто обновляем текущую страницу
        page = int(callback.data.split(":")[1])
        await callback.answer(f"Страница {page + 1}")

    except Exception as e:
        logger.error(f"Ошибка пагинации промокодов: {e}")
        await callback.answer("❌ Ошибка")
