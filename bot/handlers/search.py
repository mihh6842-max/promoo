"""
Обработчик поиска
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, FSInputFile, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger

from database import async_session_maker
from database.crud import search_promocodes
from bot.keyboards.inline import promocodes_list_keyboard, main_menu_keyboard
from utils.state_storage import bot_storage

router = Router(name='search')


class SearchStates(StatesGroup):
    """Состояния для поиска"""
    waiting_for_query = State()


@router.message(F.text == "🔍 Поиск")
async def search_button(message: Message, state: FSMContext):
    """Кнопка поиска"""
    from bot.keyboards.inline import back_button
    await message.answer(
        "🔍 <b>Поиск промокодов</b>\n\n"
        "Введите название магазина, категории\n"
        "или ключевое слово:\n\n"
        "<i>Например: ozon, электроника, скидка 50%</i>",
        reply_markup=back_button("main_menu"),
        parse_mode="HTML"
    )

    await state.set_state(SearchStates.waiting_for_query)


@router.callback_query(F.data == "search_prompt")
async def search_prompt(callback: CallbackQuery, state: FSMContext):
    """Запрос строки поиска"""
    banner_path = "baners/search.jpg"
    await callback.message.edit_media(
        media=InputMediaPhoto(
            media=FSInputFile(banner_path),
            caption="🔍 <b>Поиск промокодов</b>\n\n"
                    "Введите название магазина, категории\n"
                    "или ключевое слово:\n\n"
                    "<i>Например: ozon, электроника, скидка 50%</i>",
            parse_mode="HTML"
        )
    )

    await state.set_state(SearchStates.waiting_for_query)
    await callback.answer()


@router.message(SearchStates.waiting_for_query)
async def process_search(message: Message, state: FSMContext):
    """Обработка поискового запроса"""
    try:
        query = message.text.strip()

        # Отмена поиска
        if query == "❌ Отмена":
            await state.clear()
            await message.answer(
                "❌ Поиск отменён",
                reply_markup=main_menu_keyboard()
            )
            return

        if len(query) < 2:
            await message.answer(
                "❌ Запрос слишком короткий.\n"
                "Введите минимум 2 символа."
            )
            return

        async with async_session_maker() as session:
            promos = await search_promocodes(session, query, limit=50)

        if not promos:
            text = (f"😔 По запросу '<b>{query}</b>'\n"
                   f"ничего не найдено.\n\n"
                   f"Попробуйте другой запрос.")
            markup = main_menu_keyboard()
            await state.clear()  # Очищаем state если ничего не найдено
        else:
            text = (f"🔍 <b>Результаты поиска</b>\n\n"
                   f"Запрос: <i>{query}</i>\n"
                   f"Найдено: {len(promos)}\n\n"
                   f"Выберите промокод:")
            markup = promocodes_list_keyboard(
                promos,
                page=0,
                callback_prefix="search_promo",
                back_callback="main_menu"
            )
            # Сохраняем запрос для пагинации
            await state.update_data(last_search_query=query)
            # НЕ очищаем state, чтобы пагинация работала

        await bot_storage.edit_or_send(
            message.from_user.id,
            message,
            text,
            reply_markup=markup,
            parse_mode="HTML"
        )

        logger.info(f"Пользователь {message.from_user.id} искал: {query}, найдено: {len(promos)}")

    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        await message.answer(
            "❌ Ошибка при поиске. Попробуйте позже.",
            reply_markup=main_menu_keyboard()
        )
        await state.clear()


@router.callback_query(F.data.startswith("search_promo:"))
async def show_search_promocode(callback: CallbackQuery):
    """Показать промокод из результатов поиска"""
    # Используем общую функцию из categories.py
    from bot.handlers.categories import _show_promo_card
    await _show_promo_card(callback, "search_promo", "main_menu")


@router.callback_query(F.data.startswith("search_promo_page:"))
async def search_pagination(callback: CallbackQuery, state: FSMContext):
    """Пагинация результатов поиска"""
    try:
        page = int(callback.data.split(":")[1])
        
        # Получаем последний поисковый запрос из state
        data = await state.get_data()
        query = data.get("last_search_query", "")
        
        if not query:
            # Пытаемся извлечь из текущего сообщения
            current_text = callback.message.caption or callback.message.text
            if "Запрос: <i>" in current_text:
                query = current_text.split("Запрос: <i>")[1].split("</i>")[0]
        
        if not query:
            await callback.answer("❌ Запрос не найден", show_alert=True)
            return
            
        async with async_session_maker() as session:
            promos = await search_promocodes(session, query, limit=50)
        
        text = (f"🔍 <b>Результаты поиска</b>\n\n"
               f"Запрос: <i>{query}</i>\n"
               f"Найдено: {len(promos)}\n\n"
               f"Выберите промокод:")
        
        markup = promocodes_list_keyboard(
            promos,
            page=page,
            callback_prefix="search_promo",
            back_callback="main_menu"
        )
        
        # Сохраняем запрос для следующей пагинации
        await state.update_data(last_search_query=query)
        
        if callback.message.photo:
            await callback.message.edit_caption(
                caption=text,
                reply_markup=markup,
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                text=text,
                reply_markup=markup,
                parse_mode="HTML"
            )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка пагинации поиска: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)