"""
Обработчик избранного
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, FSInputFile, InputMediaPhoto
from loguru import logger

from database import async_session_maker
from database.crud import (
    get_user_favorites,
    add_to_favorites,
    remove_from_favorites,
    get_promocode_by_id,
    is_in_favorites
)
from bot.keyboards.inline import promocodes_list_keyboard, main_menu_keyboard, promocode_card_keyboard
from utils.animations import format_promocode_card
from utils.state_storage import bot_storage

router = Router(name='favorites')


@router.message(F.text == "⭐ Избранное")
async def favorites_button(message: Message):
    """Кнопка избранного"""
    try:
        async with async_session_maker() as session:
            promos = await get_user_favorites(session, message.from_user.id)

        if not promos:
            text = ("💔 <b>Избранное пусто</b>\n\n"
                   "Добавьте промокоды в избранное,\n"
                   "чтобы быстро находить их!\n\n"
                   "Для добавления нажмите ⭐ на\n"
                   "карточке промокода.")
            markup = main_menu_keyboard()
        else:
            text = (f"⭐ <b>Избранные промокоды</b>\n\n"
                   f"Сохранено: {len(promos)}\n\n"
                   f"Выберите промокод:")
            markup = promocodes_list_keyboard(
                promos,
                page=0,
                callback_prefix="fav_promo",
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
        logger.error(f"Ошибка показа избранного: {e}")
        try:
            await loading.delete()
        except:
            pass


@router.callback_query(F.data == "favorites")
async def show_favorites(callback: CallbackQuery):
    """Показать избранные промокоды"""
    try:
        async with async_session_maker() as session:
            promos = await get_user_favorites(session, callback.from_user.id)

        if not promos:
            banner_path = "baners/izbrannoe.jpg"
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=FSInputFile(banner_path),
                    caption="💔 <b>Избранное пусто</b>\n\n"
                            "Добавьте промокоды в избранное,\n"
                            "чтобы быстро находить их!",
                    parse_mode="HTML"
                ),
                reply_markup=main_menu_keyboard()
            )
            await callback.answer()
            return

        banner_path = "baners/izbrannoe.jpg"
        await callback.message.edit_media(
            media=InputMediaPhoto(
                media=FSInputFile(banner_path),
                caption=f"⭐ <b>Избранные промокоды</b>\n\n"
                        f"Сохранено: {len(promos)}\n\n"
                        f"Выберите промокод:",
                parse_mode="HTML"
            ),
            reply_markup=promocodes_list_keyboard(
                promos,
                page=0,
                callback_prefix="fav_promo",
                back_callback="main_menu"
            )
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка показа избранного: {e}")
        await callback.answer("❌ Ошибка загрузки", show_alert=True)


@router.callback_query(F.data.startswith("fav_promo_page:"))
async def favorites_pagination(callback: CallbackQuery):
    """Пагинация избранного"""
    try:
        page = int(callback.data.split(":")[1])

        async with async_session_maker() as session:
            promos = await get_user_favorites(session, callback.from_user.id)

        if not promos:
            await callback.answer("Избранное пусто", show_alert=True)
            return

        banner_path = "baners/izbrannoe.jpg"
        await callback.message.edit_media(
            media=InputMediaPhoto(
                media=FSInputFile(banner_path),
                caption=f"⭐ <b>Избранные промокоды</b>\n\n"
                        f"Сохранено: {len(promos)}\n\n"
                        f"Выберите промокод:",
                parse_mode="HTML"
            ),
            reply_markup=promocodes_list_keyboard(
                promos,
                page=page,
                callback_prefix="fav_promo",
                back_callback="main_menu"
            )
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка пагинации избранного: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("fav_promo:"))
async def show_favorite_promocode(callback: CallbackQuery):
    """Показать промокод из избранного"""
    from bot.handlers.categories import _show_promo_card
    await _show_promo_card(callback, "fav_promo", "favorites")


@router.callback_query(F.data.startswith("toggle_fav:"))
async def toggle_favorite(callback: CallbackQuery):
    """Добавить/удалить из избранного"""
    try:
        promo_id = int(callback.data.split(":")[1])

        async with async_session_maker() as session:
            # Проверяем, в избранном ли
            is_fav = await is_in_favorites(session, callback.from_user.id, promo_id)

            if is_fav:
                # Удаляем
                await remove_from_favorites(session, callback.from_user.id, promo_id)
                message = "💔 Удалено из избранного"
            else:
                # Добавляем
                await add_to_favorites(session, callback.from_user.id, promo_id)
                message = "⭐ Добавлено в избранное!"

            # Обновляем карточку промокода
            promo = await get_promocode_by_id(session, promo_id)
            is_fav = not is_fav  # Инвертируем состояние

        # Обновляем сообщение
        card_text = format_promocode_card(promo, is_fav)

        await callback.message.edit_text(
            card_text,
            reply_markup=promocode_card_keyboard(
                promo_id,
                promo.code,
                promo.shop_url,
                is_fav,
                "main_menu"  # TODO: сохранять back_callback
            ),
            parse_mode="HTML"
        )

        await callback.answer(message, show_alert=False)

        logger.info(f"Пользователь {callback.from_user.id} {'добавил' if is_fav else 'удалил'} промокод {promo_id} в избранное")

    except Exception as e:
        logger.error(f"Ошибка toggle_favorite: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)
