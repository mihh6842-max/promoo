"""
CRUD операции для работы с базой данных
"""
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy import select, func, or_, and_, desc, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from database.models import PromoCode, User, Favorite, Subscription, ParseLog
from loguru import logger


async def create_promocode(session: AsyncSession, **kwargs) -> PromoCode:
    """Создать промокод"""
    promo = PromoCode(**kwargs)
    session.add(promo)
    await session.commit()
    await session.refresh(promo)
    return promo


async def get_promocode_by_id(session: AsyncSession, promo_id: int) -> Optional[PromoCode]:
    """Получить промокод по ID"""
    result = await session.execute(
        select(PromoCode).where(PromoCode.id == promo_id)
    )
    return result.scalar_one_or_none()


async def get_promocode_by_code(
    session: AsyncSession,
    code: str,
    shop_name: str
) -> Optional[PromoCode]:
    """Получить промокод по коду и магазину"""
    result = await session.execute(
        select(PromoCode).where(
            and_(
                PromoCode.code == code,
                PromoCode.shop_name == shop_name
            )
        )
    )
    return result.scalar_one_or_none()


async def get_all_promocodes(
    session: AsyncSession,
    active_only: bool = True,
    limit: int = 100,
    offset: int = 0
) -> List[PromoCode]:
    """Получить все промокоды"""
    query = select(PromoCode)

    if active_only:
        query = query.where(PromoCode.is_active == True)

    query = query.order_by(desc(PromoCode.created_at)).limit(limit).offset(offset)

    result = await session.execute(query)
    return list(result.scalars().all())


async def get_promocodes_by_shop(
    session: AsyncSession,
    shop_name: str,
    limit: int = 50,
    offset: int = 0
) -> List[PromoCode]:
    """Получить промокоды по магазину"""
    result = await session.execute(
        select(PromoCode)
        .where(
            and_(
                PromoCode.shop_name == shop_name,
                PromoCode.is_active == True
            )
        )
        .order_by(desc(PromoCode.created_at))
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_promocodes_by_category(
    session: AsyncSession,
    category: str,
    limit: int = 50,
    offset: int = 0
) -> List[PromoCode]:
    """Получить промокоды по категории (точное совпадение)"""
    result = await session.execute(
        select(PromoCode)
        .where(
            and_(
                PromoCode.category == category,
                PromoCode.is_active == True
            )
        )
        .order_by(desc(PromoCode.created_at))
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_hot_promocodes(
    session: AsyncSession,
    limit: int = 20
) -> List[PromoCode]:
    """Получить горячие промокоды"""
    result = await session.execute(
        select(PromoCode)
        .where(
            and_(
                PromoCode.is_hot == True,
                PromoCode.is_active == True
            )
        )
        .order_by(desc(PromoCode.created_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_new_promocodes(
    session: AsyncSession,
    limit: int = 20
) -> List[PromoCode]:
    """Получить новые промокоды"""
    result = await session.execute(
        select(PromoCode)
        .where(
            and_(
                PromoCode.is_new == True,
                PromoCode.is_active == True
            )
        )
        .order_by(desc(PromoCode.created_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def search_promocodes(
    session: AsyncSession,
    query: str,
    limit: int = 50
) -> List[PromoCode]:
    """Поиск промокодов с поддержкой русского и английского"""
    # Словарь для поиска магазинов (теперь все названия в базе на русском)
    # Ключ: что ищет пользователь -> Значения: варианты в базе данных
    translit_map = {
        # Пятёрочка
        'пятерочка': ['Пятерочка Доставка'],
        'пятёрочка': ['Пятерочка Доставка'],
        'pyaterochka': ['Пятерочка Доставка'],
        '5ka': ['Пятерочка Доставка'],

        # Магнит
        'магнит': ['магнит'],
        'magnit': ['магнит'],

        # Перекрёсток
        'перекресток': ['перекрёсток'],
        'перекрёсток': ['перекрёсток'],
        'perekrestok': ['перекрёсток'],

        # Лента
        'лента': ['лента'],
        'lenta': ['лента'],

        # Монетка
        'монетка': ['монетка'],
        'monetka': ['монетка'],

        # Ozon (бренд, остается)
        'озон': ['ozon'],
        'ozon': ['ozon'],

        # Wildberries (бренд)
        'вайлдберриз': ['wildberries'],
        'вб': ['wildberries'],
        'wildberries': ['wildberries'],
        'wb': ['wildberries'],

        # СберМаркет
        'сбермаркет': ['сбермаркет'],
        'sbermarket': ['сбермаркет'],
        'сбер': ['сбермаркет', 'сберздоровье'],

        # Самокат
        'самокат': ['самокат'],
        'samokat': ['самокат'],

        # Яндекс
        'яндекс': ['яндекс'],
        'yandex': ['яндекс'],

        # ВкусВилл
        'вкусвилл': ['вкусвилл'],
        'впрок': ['вкусвилл'],
        'vkusvill': ['вкусвилл'],
        'vprok': ['вкусвилл'],

        # МегаМаркет
        'мегамаркет': ['мегамаркет'],
        'megamarket': ['мегамаркет'],
        'мега': ['мегамаркет'],

        # Спортмастер
        'спортмастер': ['спортмастер'],
        'sportmaster': ['спортмастер'],

        # Авито
        'авито': ['авито'],
        'avito': ['авито'],

        # AliExpress (бренд)
        'алиэкспресс': ['aliexpress'],
        'aliexpress': ['aliexpress'],
        'ali': ['aliexpress'],
        'али': ['aliexpress'],

        # ЛитРес
        'литрес': ['литрес'],
        'litres': ['литрес'],

        # Kari (бренд)
        'кари': ['kari'],
        'kari': ['kari'],

        # Леруа Мерлен
        'леруа': ['леруа мерлен'],
        'lerua': ['леруа мерлен'],
        'leroy merlin': ['леруа мерлен'],
        'leroymerlin': ['леруа мерлен'],

        # Золотое Яблоко
        'золотое яблоко': ['золотое яблоко'],
        'goldapple': ['золотое яблоко'],
        'gold apple': ['золотое яблоко'],

        # Рив Гош
        'рив гош': ['рив гош'],
        'ривгош': ['рив гош'],
        'rivegauche': ['рив гош'],

        # Л'Этуаль
        'летуаль': ['л\'этуаль'],
        'letu': ['л\'этуаль'],

        # Тинькофф
        'тинькофф': ['тинькофф'],
        'tinkoff': ['тинькофф'],

        # Альфа-Банк
        'альфа': ['альфа-банк'],
        'alfabank': ['альфа-банк'],

        # Додо Пицца
        'додо': ['додо пицца'],
        'dodopizza': ['додо пицца'],

        # KFC (бренд)
        'кфс': ['kfc'],
        'kfc': ['kfc'],

        # Fix Price (бренд)
        'фикс прайс': ['fix price'],
        'fix price': ['fix price'],
        'fixprice': ['fix price'],
    }

    query_lower = query.lower().strip()

    # Создаем список паттернов для поиска
    patterns = [f"%{query_lower}%"]

    # Добавляем транслитные версии если есть в словаре
    if query_lower in translit_map:
        for variant in translit_map[query_lower]:
            patterns.append(f"%{variant}%")

    # Также проверяем частичные совпадения для составных слов
    # Например, "пятер" найдет "пятерочка"
    for key, values in translit_map.items():
        if query_lower in key or key in query_lower:
            patterns.append(f"%{key}%")
            for variant in values:
                patterns.append(f"%{variant}%")

    # Убираем дубликаты паттернов
    patterns = list(set(patterns))

    # Для каждого паттерна создаем варианты с разным регистром
    # (т.к. func.lower() в SQLite не работает с русскими буквами)
    all_patterns = []
    for pattern in patterns:
        all_patterns.append(pattern)  # нижний регистр
        # Добавляем вариант с заглавной первой буквой
        if len(pattern) > 2:  # убираем %
            inner = pattern[1:-1]  # убираем % с обеих сторон
            if inner:
                capitalized = inner[0].upper() + inner[1:]
                all_patterns.append(f"%{capitalized}%")

    # Убираем дубликаты
    all_patterns = list(set(all_patterns))

    # Создаем условия поиска для всех паттернов
    # БЕЗ func.lower() т.к. в SQLite он не работает с кириллицей
    search_conditions = []
    for pattern in all_patterns:
        search_conditions.extend([
            PromoCode.shop_name.like(pattern),
            PromoCode.description.like(pattern),
            PromoCode.category.like(pattern),
            PromoCode.code.like(pattern)
        ])

    result = await session.execute(
        select(PromoCode)
        .where(
            and_(
                PromoCode.is_active == True,
                or_(*search_conditions)
            )
        )
        .order_by(desc(PromoCode.created_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_all_shops(session: AsyncSession) -> List[str]:
    """Получить список всех магазинов"""
    result = await session.execute(
        select(PromoCode.shop_name)
        .where(PromoCode.is_active == True)
        .distinct()
        .order_by(PromoCode.shop_name)
    )
    return list(result.scalars().all())


async def get_all_categories(session: AsyncSession) -> List[str]:
    """Получить список всех категорий"""
    result = await session.execute(
        select(PromoCode.category)
        .where(PromoCode.is_active == True)
        .distinct()
        .order_by(PromoCode.category)
    )
    return list(result.scalars().all())


async def update_promocode(
    session: AsyncSession,
    promo_id: int,
    **kwargs
) -> Optional[PromoCode]:
    """Обновить промокод"""
    await session.execute(
        update(PromoCode)
        .where(PromoCode.id == promo_id)
        .values(**kwargs)
    )
    await session.commit()
    return await get_promocode_by_id(session, promo_id)


async def increment_views(session: AsyncSession, promo_id: int):
    """Увеличить счетчик просмотров"""
    await session.execute(
        update(PromoCode)
        .where(PromoCode.id == promo_id)
        .values(views_count=PromoCode.views_count + 1)
    )
    await session.commit()


async def increment_copies(session: AsyncSession, promo_id: int):
    """Увеличить счетчик копирований"""
    await session.execute(
        update(PromoCode)
        .where(PromoCode.id == promo_id)
        .values(copy_count=PromoCode.copy_count + 1)
    )
    await session.commit()


async def mark_old_promos_as_not_new(session: AsyncSession, hours: int = 24):
    """Убрать метку NEW у старых промокодов"""
    threshold = datetime.utcnow() - timedelta(hours=hours)
    await session.execute(
        update(PromoCode)
        .where(
            and_(
                PromoCode.is_new == True,
                PromoCode.created_at < threshold
            )
        )
        .values(is_new=False)
    )
    await session.commit()


async def deactivate_expired_promos(session: AsyncSession):
    """Деактивировать истекшие промокоды"""
    now = datetime.utcnow()
    result = await session.execute(
        update(PromoCode)
        .where(
            and_(
                PromoCode.is_active == True,
                PromoCode.expiry_date.isnot(None),
                PromoCode.expiry_date < now
            )
        )
        .values(is_active=False)
    )
    await session.commit()
    return result.rowcount



async def create_or_update_user(
    session: AsyncSession,
    telegram_id: int,
    **kwargs
) -> User:
    """Создать или обновить пользователя"""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if user:
        # Обновляем
        for key, value in kwargs.items():
            setattr(user, key, value)
        user.last_activity = datetime.utcnow()
    else:
        # Создаем
        user = User(telegram_id=telegram_id, **kwargs)
        session.add(user)

    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_telegram_id(
    session: AsyncSession,
    telegram_id: int
) -> Optional[User]:
    """Получить пользователя по Telegram ID"""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def get_subscribed_users(session: AsyncSession) -> List[User]:
    """Получить всех подписанных пользователей"""
    result = await session.execute(
        select(User).where(User.is_subscribed == True)
    )
    return list(result.scalars().all())


async def update_user_stats(
    session: AsyncSession,
    telegram_id: int,
    views: int = 0,
    copies: int = 0
):
    """Обновить статистику пользователя"""
    await session.execute(
        update(User)
        .where(User.telegram_id == telegram_id)
        .values(
            promo_views=User.promo_views + views,
            promo_copies=User.promo_copies + copies
        )
    )
    await session.commit()



async def add_to_favorites(
    session: AsyncSession,
    telegram_id: int,
    promo_id: int
) -> Optional[Favorite]:
    """Добавить в избранное"""
    # Получаем user_id
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        return None

    # Проверяем, нет ли уже в избранном
    result = await session.execute(
        select(Favorite).where(
            and_(
                Favorite.user_id == user.id,
                Favorite.promocode_id == promo_id
            )
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        return existing

    favorite = Favorite(user_id=user.id, promocode_id=promo_id)
    session.add(favorite)
    await session.commit()
    await session.refresh(favorite)
    return favorite


async def remove_from_favorites(
    session: AsyncSession,
    telegram_id: int,
    promo_id: int
) -> bool:
    """Удалить из избранного"""
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        return False

    result = await session.execute(
        delete(Favorite).where(
            and_(
                Favorite.user_id == user.id,
                Favorite.promocode_id == promo_id
            )
        )
    )
    await session.commit()
    return result.rowcount > 0


async def get_user_favorites(
    session: AsyncSession,
    telegram_id: int
) -> List[PromoCode]:
    """Получить избранные промокоды пользователя"""
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        return []

    result = await session.execute(
        select(PromoCode)
        .join(Favorite)
        .where(Favorite.user_id == user.id)
        .order_by(desc(Favorite.created_at))
    )
    return list(result.scalars().all())


async def is_in_favorites(
    session: AsyncSession,
    telegram_id: int,
    promo_id: int
) -> bool:
    """Проверить, в избранном ли промокод"""
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        return False

    result = await session.execute(
        select(Favorite).where(
            and_(
                Favorite.user_id == user.id,
                Favorite.promocode_id == promo_id
            )
        )
    )
    return result.scalar_one_or_none() is not None



async def add_subscription(
    session: AsyncSession,
    telegram_id: int,
    sub_type: str,
    sub_value: str
) -> Optional[Subscription]:
    """Добавить подписку"""
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        return None

    # Проверяем существующую подписку
    result = await session.execute(
        select(Subscription).where(
            and_(
                Subscription.user_id == user.id,
                Subscription.subscription_type == sub_type,
                Subscription.subscription_value == sub_value
            )
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        return existing

    subscription = Subscription(
        user_id=user.id,
        subscription_type=sub_type,
        subscription_value=sub_value
    )
    session.add(subscription)
    await session.commit()
    await session.refresh(subscription)
    return subscription


async def remove_subscription(
    session: AsyncSession,
    telegram_id: int,
    sub_type: str,
    sub_value: str
) -> bool:
    """Удалить подписку"""
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        return False

    result = await session.execute(
        delete(Subscription).where(
            and_(
                Subscription.user_id == user.id,
                Subscription.subscription_type == sub_type,
                Subscription.subscription_value == sub_value
            )
        )
    )
    await session.commit()
    return result.rowcount > 0



async def create_parse_log(session: AsyncSession) -> ParseLog:
    """Создать лог парсинга"""
    log = ParseLog(status="running")
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


async def update_parse_log(
    session: AsyncSession,
    log_id: int,
    **kwargs
) -> Optional[ParseLog]:
    """Обновить лог парсинга"""
    await session.execute(
        update(ParseLog)
        .where(ParseLog.id == log_id)
        .values(**kwargs)
    )
    await session.commit()

    result = await session.execute(
        select(ParseLog).where(ParseLog.id == log_id)
    )
    return result.scalar_one_or_none()


async def get_last_parse_log(session: AsyncSession) -> Optional[ParseLog]:
    """Получить последний лог парсинга"""
    result = await session.execute(
        select(ParseLog)
        .order_by(desc(ParseLog.started_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_stats(session: AsyncSession) -> dict:
    """Получить общую статистику"""
    # Общее количество промокодов
    total_promos = await session.execute(
        select(func.count(PromoCode.id))
        .where(PromoCode.is_active == True)
    )
    total_promos = total_promos.scalar()

    # Новые промокоды
    new_promos = await session.execute(
        select(func.count(PromoCode.id))
        .where(
            and_(
                PromoCode.is_active == True,
                PromoCode.is_new == True
            )
        )
    )
    new_promos = new_promos.scalar()

    # Количество магазинов
    total_shops = await session.execute(
        select(func.count(func.distinct(PromoCode.shop_name)))
        .where(PromoCode.is_active == True)
    )
    total_shops = total_shops.scalar()

    # Количество пользователей
    total_users = await session.execute(
        select(func.count(User.id))
    )
    total_users = total_users.scalar()

    # Подписанные пользователи
    subscribed_users = await session.execute(
        select(func.count(User.id))
        .where(User.is_subscribed == True)
    )
    subscribed_users = subscribed_users.scalar()

    # Топ магазинов
    top_shops = await session.execute(
        select(
            PromoCode.shop_name,
            func.count(PromoCode.id).label('count')
        )
        .where(PromoCode.is_active == True)
        .group_by(PromoCode.shop_name)
        .order_by(desc('count'))
        .limit(10)
    )
    top_shops = [(row[0], row[1]) for row in top_shops.all()]

    return {
        'total_promos': total_promos,
        'new_promos': new_promos,
        'total_shops': total_shops,
        'total_users': total_users,
        'subscribed_users': subscribed_users,
        'top_shops': top_shops
    }


async def delete_promocode(session: AsyncSession, promo_id: int) -> bool:
    """Удалить промокод"""
    result = await session.execute(
        delete(PromoCode).where(PromoCode.id == promo_id)
    )
    await session.commit()
    return result.rowcount > 0


async def toggle_promocode_status(session: AsyncSession, promo_id: int) -> Optional[PromoCode]:
    """Переключить статус активности промокода"""
    promo = await get_promocode_by_id(session, promo_id)
    if not promo:
        return None
    
    new_status = not promo.is_active
    await session.execute(
        update(PromoCode)
        .where(PromoCode.id == promo_id)
        .values(is_active=new_status)
    )
    await session.commit()
    return await get_promocode_by_id(session, promo_id)
