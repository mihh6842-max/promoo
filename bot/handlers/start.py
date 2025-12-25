"""
Обработчик команды /start и главного меню
"""
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from loguru import logger

from database import async_session_maker
from database.crud import create_or_update_user
from bot.keyboards.inline import main_menu_keyboard
from utils.animations import welcome_message, help_message
from utils.state_storage import bot_storage

router = Router(name='start')


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Команда /start"""
    try:
        # Регистрируем пользователя
        async with async_session_maker() as session:
            await create_or_update_user(
                session,
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )

        # Отправляем приветствие с баннером
        banner_path = "baners/hello.jpg"
        bot_msg = await message.answer_photo(
            photo=FSInputFile(banner_path),
            caption=welcome_message(),
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML"
        )

        # Сохраняем сообщение бота
        bot_storage.save_message(message.from_user.id, bot_msg)

        logger.info(f"Пользователь {message.from_user.id} запустил бота")

    except Exception as e:
        logger.error(f"Ошибка в /start: {e}")
        await message.answer(
            "❌ Произошла ошибка. Попробуйте позже.",
            reply_markup=main_menu_keyboard()
        )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Команда /help"""
    await message.answer(
        help_message(),
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML"
    )


@router.message(F.text == "ℹ️ Помощь")
async def help_button(message: Message):
    """Кнопка помощи"""
    await bot_storage.edit_or_send(
        message.from_user.id,
        message,
        help_message(),
        parse_mode="HTML"
    )


@router.message(F.text == "🔙 Главное меню")
async def back_to_main_menu(message: Message):
    """Возврат в главное меню"""
    await bot_storage.edit_or_send(
        message.from_user.id,
        message,
        "📱 Главное меню:",
        reply_markup=main_menu_keyboard()
    )


@router.callback_query(F.data == "current_page")
async def current_page_handler(callback: CallbackQuery):
    """Обработчик текущей страницы (просто показываем номер)"""
    await callback.answer("📄 Текущая страница", show_alert=False)


@router.callback_query(F.data == "main_menu")
async def back_to_main_menu_callback(callback: CallbackQuery):
    """Обработчик кнопки возврата в главное меню"""
    try:
        from aiogram.types import InputMediaPhoto

        banner_path = "baners/hello.jpg"
        await callback.message.edit_media(
            media=InputMediaPhoto(
                media=FSInputFile(banner_path),
                caption="🏠 Главное меню\n\nВыберите действие:"
            ),
            reply_markup=main_menu_keyboard()
        )
        await callback.answer()
        logger.debug(f"Пользователь {callback.from_user.id} вернулся в главное меню")
    except Exception as e:
        logger.error(f"Ошибка возврата в главное меню: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


