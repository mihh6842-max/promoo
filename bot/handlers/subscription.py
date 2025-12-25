"""
Обработчик подписок
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, FSInputFile, InputMediaPhoto
from loguru import logger

from database import async_session_maker
from database.crud import get_user_by_telegram_id, update_user_stats
from bot.keyboards.inline import subscription_menu_keyboard, notification_settings_keyboard, main_menu_keyboard
from sqlalchemy import update
from database.models import User
from utils.state_storage import bot_storage

router = Router(name='subscription')


@router.message(F.text == "🔔 Подписка")
async def subscription_button(message: Message):
    """Кнопка подписки"""
    try:
        await message.delete()
    except:
        pass

    try:
        async with async_session_maker() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)

            if not user:
                await message.answer("❌ Ошибка")
                return

            is_subscribed = user.is_subscribed

        status = "✅ Включены" if is_subscribed else "❌ Выключены"

        text = (f"🔔 <b>Управление подписками</b>\n\n"
               f"Статус уведомлений: {status}\n\n"
               f"С подпиской вы будете получать:\n"
               f"• Новые промокоды\n"
               f"• Горячие предложения\n"
               f"• Истекающие промокоды\n\n"
               f"Выберите действие:")
        markup = subscription_menu_keyboard(is_subscribed)

        await bot_storage.edit_or_send(
            message.from_user.id,
            message,
            text,
            reply_markup=markup,
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Ошибка показа меню подписок: {e}")


@router.callback_query(F.data == "subscription_menu")
async def show_subscription_menu(callback: CallbackQuery):
    """Показать меню подписок"""
    try:
        async with async_session_maker() as session:
            user = await get_user_by_telegram_id(session, callback.from_user.id)

            if not user:
                await callback.answer("❌ Ошибка", show_alert=True)
                return

            is_subscribed = user.is_subscribed

        status = "✅ Включены" if is_subscribed else "❌ Выключены"

        banner_path = "baners/podpiska.jpg"
        await callback.message.edit_media(
            media=InputMediaPhoto(
                media=FSInputFile(banner_path),
                caption=f"🔔 <b>Управление подписками</b>\n\n"
                        f"Статус уведомлений: {status}\n\n"
                        f"С подпиской вы будете получать:\n"
                        f"• Новые промокоды\n"
                        f"• Горячие предложения\n"
                        f"• Истекающие промокоды\n\n"
                        f"Выберите действие:",
                parse_mode="HTML"
            ),
            reply_markup=subscription_menu_keyboard(is_subscribed)
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка показа меню подписок: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data == "toggle_subscription")
async def toggle_subscription(callback: CallbackQuery):
    """Включить/выключить подписку"""
    try:
        async with async_session_maker() as session:
            user = await get_user_by_telegram_id(session, callback.from_user.id)

            if not user:
                await callback.answer("❌ Ошибка", show_alert=True)
                return

            # Переключаем
            new_status = not user.is_subscribed

            await session.execute(
                update(User)
                .where(User.telegram_id == callback.from_user.id)
                .values(is_subscribed=new_status)
            )
            await session.commit()

        status = "✅ Включены" if new_status else "❌ Выключены"
        message = "✅ Уведомления включены!" if new_status else "🔕 Уведомления выключены"

        await callback.message.edit_text(
            f"🔔 <b>Управление подписками</b>\n\n"
            f"Статус уведомлений: {status}\n\n"
            f"С подпиской вы будете получать:\n"
            f"• Новые промокоды\n"
            f"• Горячие предложения\n"
            f"• Истекающие промокоды\n\n"
            f"Выберите действие:",
            reply_markup=subscription_menu_keyboard(new_status),
            parse_mode="HTML"
        )

        await callback.answer(message, show_alert=True)

        logger.info(f"Пользователь {callback.from_user.id} {'включил' if new_status else 'выключил'} подписку")

    except Exception as e:
        logger.error(f"Ошибка toggle_subscription: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data == "notification_settings")
async def show_notification_settings(callback: CallbackQuery):
    """Показать настройки уведомлений"""
    try:
        async with async_session_maker() as session:
            user = await get_user_by_telegram_id(session, callback.from_user.id)

            if not user:
                await callback.answer("❌ Ошибка", show_alert=True)
                return

        await callback.message.edit_text(
            "⚙️ <b>Настройки уведомлений</b>\n\n"
            "Выберите типы уведомлений,\n"
            "которые хотите получать:",
            reply_markup=notification_settings_keyboard(
                user.notify_new_promos,
                user.notify_hot_promos,
                user.notify_expiring
            ),
            parse_mode="HTML"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка показа настроек уведомлений: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data == "toggle_notify_new")
async def toggle_notify_new(callback: CallbackQuery):
    """Переключить уведомления о новых промокодах"""
    await _toggle_notification(callback, "notify_new_promos", "новые промокоды")


@router.callback_query(F.data == "toggle_notify_hot")
async def toggle_notify_hot(callback: CallbackQuery):
    """Переключить уведомления о горячих предложениях"""
    await _toggle_notification(callback, "notify_hot_promos", "горячие предложения")


@router.callback_query(F.data == "toggle_notify_expiring")
async def toggle_notify_expiring(callback: CallbackQuery):
    """Переключить уведомления об истекающих промокодах"""
    await _toggle_notification(callback, "notify_expiring", "истекающие промокоды")


async def _toggle_notification(callback: CallbackQuery, field: str, name: str):
    """Вспомогательная функция переключения уведомлений"""
    try:
        async with async_session_maker() as session:
            user = await get_user_by_telegram_id(session, callback.from_user.id)

            if not user:
                await callback.answer("❌ Ошибка", show_alert=True)
                return

            # Переключаем
            current_value = getattr(user, field)
            new_value = not current_value

            await session.execute(
                update(User)
                .where(User.telegram_id == callback.from_user.id)
                .values(**{field: new_value})
            )
            await session.commit()

            # Обновляем данные пользователя
            await session.refresh(user)

        # Обновляем клавиатуру
        await callback.message.edit_reply_markup(
            reply_markup=notification_settings_keyboard(
                user.notify_new_promos,
                user.notify_hot_promos,
                user.notify_expiring
            )
        )

        status = "✅ Включены" if new_value else "❌ Выключены"
        await callback.answer(f"{name.capitalize()}: {status}", show_alert=False)

    except Exception as e:
        logger.error(f"Ошибка переключения уведомлений: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)
