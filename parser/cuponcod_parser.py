"""
Оптимизированный парсер для сайта cuponcod.ru
Обновлен с правильными селекторами
Включает fallback-парсер без Playwright для работы на ограниченных хостингах
"""
import re
import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential
import httpx

# Условный импорт Playwright (может отсутствовать на хостинге)
try:
    from playwright.async_api import async_playwright, Page, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    logger.warning("Playwright не установлен. Будет использоваться только Simple парсер.")
    PLAYWRIGHT_AVAILABLE = False
    Page = None
    Browser = None

# Добавляем корневую директорию в путь для импорта config
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from config import config


class CuponcodParser:
    """Парсер промокодов с cuponcod.ru"""

    def __init__(self):
        self.base_url = config.TARGET_URL
        self.browser: Optional[Browser] = None
        self.context = None
        self.max_shops = 200  # Полный парсинг всех магазинов

    async def __aenter__(self):
        """Инициализация браузера"""
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright не установлен")
        try:
            # Добавляем таймаут на инициализацию (30 секунд)
            async with asyncio.timeout(30):
                self.playwright = await async_playwright().start()
                self.browser = await self.playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--no-sandbox',
                        '--disable-setuid-sandbox'
                    ]
                )
                self.context = await self.browser.new_context(
                    user_agent=config.PARSER_USER_AGENT,
                    viewport={'width': 1920, 'height': 1080},
                    java_script_enabled=True
                )
        except asyncio.TimeoutError:
            logger.error("Таймаут при инициализации Playwright (30 сек)")
            raise Exception("Playwright не смог запуститься за 30 секунд")
        except Exception as e:
            logger.error(f"Ошибка инициализации Playwright: {e}")
            raise
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрытие браузера"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _wait_for_page_load(self, page: Page):
        """Ожидание загрузки страницы с retry"""
        try:
            await page.wait_for_load_state('networkidle', timeout=30000)
            await asyncio.sleep(2)
        except Exception as e:
            logger.warning(f"Timeout waiting for page load: {e}")

    def _parse_discount(self, text: str) -> tuple[Optional[str], Optional[float]]:
        """Извлечь информацию о скидке"""
        if not text:
            return None, None

        # Ищем процент
        percent_match = re.search(r'(\d+)\s*%', text)
        if percent_match:
            return f"{percent_match.group(1)}%", float(percent_match.group(1))

        # Ищем сумму со скидкой
        amount_match = re.search(r'(\d+)\s*(?:руб|₽|рублей)', text, re.IGNORECASE)
        if amount_match:
            return f"{amount_match.group(1)}₽", None

        return text.strip()[:50], None

    def _parse_expiry_date(self, text: str) -> Optional[datetime]:
        """Извлечь дату истечения"""
        if not text:
            return None

        patterns = [
            r'(\d{1,2})\.(\d{1,2})\.(\d{4})',
            r'(\d{1,2})/(\d{1,2})/(\d{4})',
            r'(\d{4})-(\d{1,2})-(\d{1,2})',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    if pattern == patterns[2]:
                        year, month, day = match.groups()
                    else:
                        day, month, year = match.groups()
                    return datetime(int(year), int(month), int(day))
                except ValueError:
                    continue

        # Относительные даты
        if 'сегодня' in text.lower():
            return datetime.now()
        elif 'завтра' in text.lower():
            return datetime.now() + timedelta(days=1)

        days_match = re.search(r'(\d+)\s*(?:день|дня|дней)', text, re.IGNORECASE)
        if days_match:
            return datetime.now() + timedelta(days=int(days_match.group(1)))

        return None

    def _categorize_shop(self, shop_name: str, description: str) -> str:
        """Определить категорию магазина"""
        shop_lower = shop_name.lower()
        desc_lower = description.lower() if description else ""
        text = shop_lower + " " + desc_lower

        categories = {
            'Электроника': ['электроник', 'техник', 'гаджет', 'смартфон', 'ноутбук', 'компьютер', 'озон', 'ozon', 'яндекс маркет', 'mvideo', 'мвидео', 'эльдорадо', 'eldorado', 'dns', 'онлайн трейд', 'megamarket', 'мегамаркет'],
            'Мода и одежда': ['одежд', 'обувь', 'мод', 'стиль', 'бренд', 'fashion', 'zara', 'h&m', 'lamoda', 'ламода', 'wildberries', 'вайлдберриз', 'befree', 'бифри', 'спортмастер', 'sportmaster', 'nike', 'adidas', 'аксессуар', 'коллекци', 'сумк', 'платье', 'брюки', 'джинс', 'куртк', 'пальто', 'аутлет', 'кросс', 'acoola', 'акула', 'kari', 'кари', 'henderson', 'хендерсон', 'ostin', 'остин', 'reserved', 'твоё', 'твое', 'incity', 'инсити', 'colin', 'колинз', 'savage', 'саваж', 'sela', 'сэла', 'gloria jeans', 'глория джинс', 'reebok', 'рибок', 'puma', 'пума', 'skechers', 'скечерс'],
            'Красота и здоровье': ['красот', 'косметик', 'парфюм', 'здоровь', 'аптек', 'витамин', 'уход', 'макияж', 'крем', 'шампунь', 'рив гош', 'rivegauche', 'лэтуаль', 'летуаль', 'улыбка радуги'],
            'Дом и сад': ['дом', 'мебель', 'интерьер', 'сад', 'ремонт', 'декор', 'посуд', 'текстиль', 'hoff', 'хофф', 'askona', 'аскона', 'ikea', 'икея', 'леруа', 'leroy'],
            'Продукты': ['продукт', 'еда', 'доставка еды', 'супермаркет', 'лента', 'перекресток', 'перекрёсток', 'groceries', 'пятерочка', 'pyaterochka', 'магнит', 'magnit', 'ашан', 'auchan', 'сбермаркет', 'sbermarket', 'foodband', 'фудбенд', 'samokat', 'самокат', 'vprok', 'впрок', 'perekrestok'],
            'Спорт и отдых': ['спорт', 'фитнес', 'туризм', 'активн', 'отдых', 'декатлон', 'decathlon', 'тренировк', 'велоспорт', 'велосипед'],
            'Детские товары': ['детск', 'игрушк', 'малыш', 'ребенок', 'baby', 'дет', 'ребёнок', 'мам', 'дочки-сыночки', 'дочки сыночки', 'mothercare', 'мазекеа', 'детский мир'],
            'Книги и медиа': ['книг', 'аудио', 'кино', 'музык', 'медиа', 'читай', 'литератур', 'bookmate', 'литрес', 'litres', 'лабиринт', 'labirint', 'буквоед'],
            'Путешествия': ['путешеств', 'отель', 'авиа', 'билет', 'туры', 'hotel', 'level travel', 'островок', 'тур', 'поездк', 'отдых', 'travel', 'hostel', 'жд', 'авиабилет', 'onlinetours', 'онлайнтурс', 'травелата', 'travelata'],
            'Рестораны и кафе': ['ресторан', 'кафе', 'пицц', 'суши', 'доставка', 'питан', 'бургер', 'кухн', 'едим дома', 'яндекс еда', 'yandex eda', 'delivery club', 'деливери клаб'],
            'Услуги': ['услуг', 'сервис', 'обучен', 'курс', 'подписк', 'mail space', 'облак', 'cloud', 'учеб', 'образован', 'страхован', 'банк', 'карт', 'вклад', 'yandex disk', 'яндекс диск', 'майл', 'mail'],
            'Авто': ['авто', 'машин', 'запчаст', 'шины', 'масло', 'каршеринг', 'car', 'delimobil', 'делимобиль', 'яндекс драйв', 'yandex drive', 'ситидрайв', 'citydrive'],
        }

        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword in text:
                    return category

        return 'Разное'

    async def _extract_shop_name_from_page(self, page: Page) -> str:
        """Извлечь настоящее название магазина со страницы"""
        try:
            content = await page.content()
            soup = BeautifulSoup(content, 'lxml')
            
            # Пробуем несколько вариантов селекторов для названия магазина
            selectors = [
                'h1.page-title',
                'h1.entry-title', 
                'h1',
                '.dealstore-title',
                'header h1',
                '.store-name',
                '.shop-title',
                '.rh-container h1',
                'article h1',
                '.post-title'
            ]
            
            for selector in selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    shop_name = title_elem.get_text(strip=True)
                    
                    # Очищаем от лишнего текста
                    shop_name = re.sub(r'промокод[ыа]?\s*(и\s*купоны?)?', '', shop_name, flags=re.IGNORECASE)
                    shop_name = re.sub(r'купон[ыа]?(\s*и\s*скидки)?', '', shop_name, flags=re.IGNORECASE)
                    shop_name = re.sub(r'скидк[аи](\s*и\s*акции)?', '', shop_name, flags=re.IGNORECASE)
                    shop_name = re.sub(r'акци[ия]', '', shop_name, flags=re.IGNORECASE)
                    shop_name = re.sub(r'\s*-\s*', ' ', shop_name)
                    shop_name = re.sub(r'\s+', ' ', shop_name)
                    shop_name = shop_name.strip()
                    
                    if shop_name and len(shop_name) > 2:
                        logger.debug(f"Извлечено название магазина: {shop_name}")
                        return shop_name
            
            # Пытаемся найти название в meta-тегах
            meta_title = soup.select_one('meta[property="og:title"]')
            if meta_title and meta_title.get('content'):
                shop_name = meta_title['content']
                shop_name = re.sub(r'промокод[ыа]?.*', '', shop_name, flags=re.IGNORECASE)
                shop_name = re.sub(r'купон[ыа]?.*', '', shop_name, flags=re.IGNORECASE)
                shop_name = shop_name.strip()
                if shop_name and len(shop_name) > 2:
                    logger.debug(f"Извлечено название из meta: {shop_name}")
                    return shop_name
            
            # Пытаемся найти в title
            title_tag = soup.select_one('title')
            if title_tag:
                title_text = title_tag.get_text(strip=True)
                # Берем первую часть до " - " или " | "
                shop_name = re.split(r'\s*[-|]\s*', title_text)[0]
                shop_name = re.sub(r'промокод[ыа]?.*', '', shop_name, flags=re.IGNORECASE)
                shop_name = re.sub(r'купон[ыа]?.*', '', shop_name, flags=re.IGNORECASE)
                shop_name = shop_name.strip()
                if shop_name and len(shop_name) > 2:
                    logger.debug(f"Извлечено название из title: {shop_name}")
                    return shop_name
            
            # Последний fallback: ищем текст перед словом "промокод" в любом h-теге
            for h_tag in soup.select('h1, h2, h3'):
                text = h_tag.get_text(strip=True)
                match = re.match(r'^(.+?)\s*промокод', text, re.IGNORECASE)
                if match:
                    shop_name = match.group(1).strip()
                    if len(shop_name) > 2:
                        logger.debug(f"Извлечено название из заголовка: {shop_name}")
                        return shop_name
            
            # Если ничего не нашли - используем словарь известных магазинов из URL
            url = page.url
            if '/dealstore/' in url:
                slug = url.rstrip('/').split('/')[-1]
                
                # Словарь известных магазинов (slug -> правильное название)
                known_shops = {
                    'perekrestok': 'Перекрёсток',
                    'pyaterochka': 'Пятёрочка',
                    '5ka': 'Пятёрочка',
                    'magnit': 'Магнит',
                    'ozon': 'Ozon',
                    'wildberries': 'Wildberries',
                    'wb': 'Wildberries',
                    'lamoda': 'Lamoda',
                    'mvideo': 'М.Видео',
                    'eldorado': 'Эльдорадо',
                    'yandex': 'Яндекс',
                    'ya': 'Яндекс',
                    'sbermarket': 'СберМаркет',
                    'sber': 'Сбер',
                    'lenta': 'Лента',
                    'auchan': 'Ашан',
                    'ashan': 'Ашан',
                    'metro': 'METRO',
                    'vprok': 'ВкусВилл',
                    'vkusvill': 'ВкусВилл',
                    'samokat': 'Самокат',
                    'sportmaster': 'Спортмастер',
                    'sportm': 'Спортмастер',
                    'letoile': 'Л\'Этуаль',
                    'letuali': 'Л\'Этуаль',
                    'rivegauche': 'Рив Гош',
                    'riv-gosh': 'Рив Гош',
                    'hoff': 'Hoff',
                    'ikea': 'IKEA',
                    'leroymerlin': 'Leroy Merlin',
                    'leroy': 'Leroy Merlin',
                    'detmir': 'Детский мир',
                    'deti': 'Детский мир',
                    'chitai-gorod': 'Читай-город',
                    'labirint': 'Лабиринт',
                    'litres': 'Литрес',
                    'kfc': 'KFC',
                    'mcdonalds': 'McDonald\'s',
                    'burgerking': 'Burger King',
                    'bk': 'Burger King',
                    'delivery-club': 'Delivery Club',
                    'yandex-eda': 'Яндекс Еда',
                    'yaeda': 'Яндекс Еда'
                }
                
                slug_lower = slug.lower()
                if slug_lower in known_shops:
                    logger.debug(f"Найдено в словаре: {known_shops[slug_lower]}")
                    return known_shops[slug_lower]
                
                # Если не в словаре, делаем красивый Title Case
                shop_name = slug.replace('-', ' ').replace('_', ' ')
                
                # Пытаемся определить если это английское или русское название
                if re.match(r'^[a-z0-9\-_\s]+$', slug, re.IGNORECASE):
                    # Английское - делаем Title Case
                    return shop_name.title()
                else:
                    # Русское или смешанное - возвращаем как есть с заглавной
                    return shop_name.capitalize()
            
            logger.warning(f"Не удалось извлечь название магазина для {page.url}")
            return "Неизвестный магазин"
            
        except Exception as e:
            logger.warning(f"Ошибка извлечения названия магазина: {e}")
            return "Неизвестный магазин"

    async def parse_promo_cards(self, page: Page, shop_name_override: Optional[str] = None) -> List[Dict]:
        """Парсинг карточек промокодов со страницы с правильными селекторами

        Args:
            page: Playwright страница
            shop_name_override: Название магазина из URL (для страниц магазинов)
        """
        promocodes = []

        try:
            await self._wait_for_page_load(page)
            content = await page.content()
            soup = BeautifulSoup(content, 'lxml')

            # ПРАВИЛЬНЫЕ СЕЛЕКТОРЫ на основе реального HTML
            cards = soup.select('.wpsm_recent_posts_list .col_item')

            if not cards:
                logger.warning("Карточки .col_item не найдены, пробуем альтернативные")
                # Альтернативные селекторы
                alternative_selectors = [
                    'div.rh_offer_list',  # Страницы магазинов!
                    'div.rh_grid_image_3_col',
                    'div.deal_daywoo',
                    'div.woo_offer_list > div',
                    'article.post',
                ]
                for selector in alternative_selectors:
                    cards = soup.select(selector)
                    if cards:
                        logger.info(f"Найдено {len(cards)} карточек с селектором: {selector}")
                        break

            if not cards:
                logger.warning("Не найдено карточек промокодов")
                return []

            logger.info(f"Найдено {len(cards)} карточек для парсинга")

            for i, card in enumerate(cards, 1):
                try:
                    promo_data = await self._parse_single_card(card, shop_name_override)
                    if promo_data:
                        promocodes.append(promo_data)
                        logger.debug(f"[{i}/{len(cards)}] Спарсено: {promo_data['shop_name']} - {promo_data['code']}")
                except Exception as e:
                    logger.error(f"Ошибка парсинга карточки {i}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Ошибка парсинга страницы: {e}", exc_info=True)

        logger.info(f"Успешно спарсено {len(promocodes)} промокодов")
        return promocodes

    async def _parse_single_card(self, card, shop_name_override: Optional[str] = None) -> Optional[Dict]:
        """Парсинг одной карточки с реальными селекторами cuponcod.ru

        Args:
            card: BeautifulSoup элемент карточки
            shop_name_override: Название магазина (если известно из URL)
        """
        try:
            # Заголовок - в h3 > a
            h3_elem = card.select_one('h3 > a')
            if h3_elem:
                description = h3_elem.get_text(strip=True)
            else:
                # Fallback: любая ссылка с текстом
                links = card.select('a[href]')
                description = None
                for link in links:
                    text = link.get_text(strip=True)
                    if text and len(text) > 10:  # Берем длинный текст, это скорее всего заголовок
                        description = text
                        break

            if not description:
                logger.debug(f"Карточка пропущена: нет описания. HTML: {str(card)[:200]}")
                return None

            # Название магазина - используем shop_name_override если он передан
            if shop_name_override:
                shop_name = shop_name_override
            else:
                # Ищем в ссылке на dealstore (главная страница)
                shop_link = card.select_one('a[href*="/dealstore/"]')
                if shop_link:
                    shop_name = shop_link.get_text(strip=True)
                else:
                    # Fallback: в .dealstore
                    shop_elem = card.select_one('.dealstore, span.dealstore')
                    if shop_elem:
                        shop_name = shop_elem.get_text(strip=True)
                    else:
                        shop_name = "Неизвестный магазин"

            # Промокод - ПРИОРИТЕТ: .rehub_offer_coupon (страницы магазинов)
            code_elem = card.select_one('.rehub_offer_coupon, span.rehub_offer_coupon')
            if code_elem:
                code = code_elem.get_text(strip=True)
            else:
                # Fallback: .code или span.code
                code_elem = card.select_one('.code, span.code')
                if code_elem:
                    code = code_elem.get_text(strip=True)
                else:
                    # Ищем последний span (обычно там промокод)
                    all_spans = card.select('span')
                    code = None
                    if all_spans:
                        # Берем последний span с текстом
                        for span in reversed(all_spans):
                            text = span.get_text(strip=True)
                            if text and len(text) >= 4 and len(text) <= 20:
                                # Проверяем что это похоже на промокод (буквы/цифры/дефисы)
                                if re.match(r'^[A-Z0-9-]+$', text, re.IGNORECASE):
                                    code = text
                                    break

            # Еще один fallback: ищем паттерн промокода в тексте
            if not code:
                card_text = card.get_text()
                code_matches = re.findall(r'\b([A-Z0-9]{4,20})\b', card_text)
                for potential_code in code_matches:
                    if not re.match(r'^\d+$', potential_code) and not re.match(r'^\d{2}\.?\d{2}\.?\d{4}$', potential_code):
                        code = potential_code
                        break

            # Если все еще не нашли, используем SALE
            if not code:
                code = "SALE"

            # Очистка кода
            code = re.sub(r'[^A-Z0-9-]', '', code.upper())

            logger.debug(f"Спарсено: {shop_name} - {code} - {description[:50]}")

            # Дата - в .date или span.date
            date_elem = card.select_one('.date, span.date')
            date_text = date_elem.get_text(strip=True) if date_elem else ""
            expiry_date = self._parse_expiry_date(date_text)

            # Ссылка - из h3 > a или первой ссылки
            link_elem = card.select_one('h3 > a, a[href]')
            shop_url = link_elem['href'] if link_elem and link_elem.get('href') else self.base_url

            # Полная ссылка
            if not shop_url.startswith('http'):
                shop_url = self.base_url + shop_url if shop_url.startswith('/') else self.base_url + '/' + shop_url

            # Изображение
            image_url = None
            img = card.select_one('img')
            if img:
                src = img.get('src') or img.get('data-src')
                if src and src.startswith('http'):
                    image_url = src

            # Скидка - из заголовка
            discount_value, discount_percent = self._parse_discount(description)

            # Категория
            category = self._categorize_shop(shop_name, description)

            # Горячее предложение
            is_hot = bool(discount_percent and discount_percent >= 30)

            # Условия
            conditions = description[:200]

            return {
                'shop_name': shop_name,
                'code': code,
                'description': description[:200],
                'discount_value': discount_value,
                'discount_percent': discount_percent,
                'conditions': conditions,
                'expiry_date': expiry_date,
                'category': category,
                'shop_url': shop_url,
                'image_url': image_url,
                'is_hot': is_hot,
            }

        except Exception as e:
            logger.error(f"Ошибка парсинга карточки: {e}", exc_info=True)
            return None

    async def parse_all_pages(self) -> List[Dict]:
        """Парсинг всех промокодов с cuponcod.ru (главная + все магазины)"""
        all_promocodes = []

        try:
            page = await self.context.new_page()

            logger.info(f"Парсинг главной страницы: {self.base_url}")
            await page.goto(self.base_url, wait_until='domcontentloaded', timeout=60000)
            await self._wait_for_page_load(page)

            # Парсим промокоды с главной страницы
            main_promos = await self.parse_promo_cards(page)
            all_promocodes.extend(main_promos)
            logger.info(f"С главной страницы: {len(main_promos)} промокодов")

            # Ищем ссылки на магазины
            shop_urls = await self._find_shop_urls(page)
            logger.info(f"Найдено магазинов: {len(shop_urls)}")

            # Парсим магазины
            for i, shop_url in enumerate(shop_urls[:self.max_shops], 1):
                try:
                    logger.info(f"[{i}/{min(self.max_shops, len(shop_urls))}] Парсинг: {shop_url}")
                    await page.goto(shop_url, wait_until='domcontentloaded', timeout=60000)
                    await self._wait_for_page_load(page)

                    # ИСПРАВЛЕНИЕ: Парсим название магазина со страницы
                    shop_name = await self._extract_shop_name_from_page(page)

                    shop_promos = await self.parse_promo_cards(page, shop_name_override=shop_name)
                    all_promocodes.extend(shop_promos)
                    logger.info(f"  -> Найдено: {len(shop_promos)} промокодов")

                    # Задержка между запросами
                    await asyncio.sleep(1)

                except Exception as e:
                    logger.error(f"Ошибка парсинга магазина {shop_url}: {e}")
                    continue

            await page.close()

        except Exception as e:
            logger.error(f"Критическая ошибка парсинга: {e}", exc_info=True)

        # Удаляем дубликаты
        unique_promos = self._remove_duplicates(all_promocodes)
        logger.info(f"="*50)
        logger.info(f"ИТОГО: {len(unique_promos)} уникальных промокодов с cuponcod.ru")
        logger.info(f"="*50)

        return unique_promos

    async def _find_shop_urls(self, page) -> List[str]:
        """Поиск ссылок на магазины"""
        shop_urls = []
        try:
            content = await page.content()
            soup = BeautifulSoup(content, 'lxml')

            # Ищем ссылки на магазины (dealstore)
            links = soup.select('a[href*="/dealstore/"]')
            logger.info(f"Найдено ссылок на магазины: {len(links)}")

            for link in links:
                href = link.get('href')
                if href:
                    if href.startswith('http'):
                        shop_url = href
                    elif href.startswith('/'):
                        shop_url = self.base_url + href
                    else:
                        shop_url = self.base_url + '/' + href

                    if shop_url not in shop_urls:
                        shop_urls.append(shop_url)

        except Exception as e:
            logger.error(f"Ошибка поиска магазинов: {e}")

        return shop_urls

    def _remove_duplicates(self, promocodes: List[Dict]) -> List[Dict]:
        """Удалить дубликаты промокодов"""
        seen = set()
        unique = []

        for promo in promocodes:
            # Ключ уникальности: магазин + код
            key = (promo['shop_name'], promo['code'])
            if key not in seen:
                seen.add(key)
                unique.append(promo)

        return unique


class SimpleCuponcodParser:
    """Упрощенный парсер без Playwright (fallback для хостингов без системных зависимостей)"""

    def __init__(self):
        self.base_url = config.TARGET_URL
        self.max_shops = 200
        self.client = None

    async def __aenter__(self):
        """Инициализация HTTP клиента"""
        self.client = httpx.AsyncClient(
            headers={
                'User-Agent': config.PARSER_USER_AGENT,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            },
            timeout=30.0,
            follow_redirects=True
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрытие HTTP клиента"""
        if self.client:
            await self.client.aclose()

    def _parse_discount(self, text: str) -> tuple[Optional[str], Optional[float]]:
        """Извлечь информацию о скидке (копия из CuponcodParser)"""
        if not text:
            return None, None

        percent_match = re.search(r'(\d+)\s*%', text)
        if percent_match:
            return f"{percent_match.group(1)}%", float(percent_match.group(1))

        amount_match = re.search(r'(\d+)\s*(?:руб|₽|рублей)', text, re.IGNORECASE)
        if amount_match:
            return f"{amount_match.group(1)}₽", None

        return text.strip()[:50], None

    def _parse_expiry_date(self, text: str) -> Optional[datetime]:
        """Извлечь дату истечения (копия из CuponcodParser)"""
        if not text:
            return None

        patterns = [
            r'(\d{1,2})\.(\d{1,2})\.(\d{4})',
            r'(\d{1,2})/(\d{1,2})/(\d{4})',
            r'(\d{4})-(\d{1,2})-(\d{1,2})',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    if pattern == patterns[2]:
                        year, month, day = match.groups()
                    else:
                        day, month, year = match.groups()
                    return datetime(int(year), int(month), int(day))
                except ValueError:
                    continue

        if 'сегодня' in text.lower():
            return datetime.now()
        elif 'завтра' in text.lower():
            return datetime.now() + timedelta(days=1)

        days_match = re.search(r'(\d+)\s*(?:день|дня|дней)', text, re.IGNORECASE)
        if days_match:
            return datetime.now() + timedelta(days=int(days_match.group(1)))

        return None

    def _categorize_shop(self, shop_name: str, description: str) -> str:
        """Определить категорию магазина (копия из CuponcodParser)"""
        shop_lower = shop_name.lower()
        desc_lower = description.lower() if description else ""
        text = shop_lower + " " + desc_lower

        categories = {
            'Электроника': ['электроник', 'техник', 'гаджет', 'смартфон', 'ноутбук', 'компьютер', 'озон', 'ozon', 'яндекс маркет', 'mvideo', 'мвидео', 'эльдорадо', 'eldorado', 'dns', 'онлайн трейд', 'megamarket', 'мегамаркет'],
            'Мода и одежда': ['одежд', 'обувь', 'мод', 'стиль', 'бренд', 'fashion', 'zara', 'h&m', 'lamoda', 'ламода', 'wildberries', 'вайлдберриз', 'befree', 'бифри', 'спортмастер', 'sportmaster', 'nike', 'adidas'],
            'Красота и здоровье': ['красот', 'косметик', 'парфюм', 'здоровь', 'аптек', 'витамин', 'уход', 'макияж', 'крем', 'шампунь', 'рив гош', 'rivegauche', 'лэтуаль', 'летуаль'],
            'Дом и сад': ['дом', 'мебель', 'интерьер', 'сад', 'ремонт', 'декор', 'посуд', 'текстиль', 'hoff', 'хофф', 'askona', 'аскона', 'ikea', 'икея', 'леруа', 'leroy'],
            'Продукты': ['продукт', 'еда', 'доставка еды', 'супермаркет', 'лента', 'перекресток', 'перекрёсток', 'groceries', 'пятерочка', 'pyaterochka', 'магнит', 'magnit', 'ашан', 'auchan', 'сбермаркет', 'sbermarket'],
            'Спорт и отдых': ['спорт', 'фитнес', 'туризм', 'активн', 'отдых', 'декатлон', 'decathlon'],
            'Детские товары': ['детск', 'игрушк', 'малыш', 'ребенок', 'baby', 'дет', 'ребёнок', 'мам', 'детский мир'],
            'Книги и медиа': ['книг', 'аудио', 'кино', 'музык', 'медиа', 'читай', 'литератур', 'bookmate', 'литрес', 'litres', 'лабиринт'],
            'Путешествия': ['путешеств', 'отель', 'авиа', 'билет', 'туры', 'hotel', 'level travel', 'островок', 'тур', 'поездк', 'отдых', 'travel', 'hostel'],
            'Рестораны и кафе': ['ресторан', 'кафе', 'пицц', 'суши', 'доставка', 'питан', 'бургер', 'кухн', 'едим дома', 'яндекс еда'],
            'Услуги': ['услуг', 'сервис', 'обучен', 'курс', 'подписк', 'mail space', 'облак', 'cloud', 'учеб', 'образован', 'страхован', 'банк'],
            'Авто': ['авто', 'машин', 'запчаст', 'шины', 'масло', 'каршеринг', 'car', 'delimobil'],
        }

        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword in text:
                    return category

        return 'Разное'

    def _extract_shop_name_from_html(self, soup: BeautifulSoup, url: str) -> str:
        """Извлечь название магазина из HTML"""
        try:
            # Пробуем те же селекторы что и в оригинальном парсере
            selectors = [
                'h1.page-title', 'h1.entry-title', 'h1',
                '.dealstore-title', 'header h1', '.store-name',
                '.shop-title', '.rh-container h1', 'article h1', '.post-title'
            ]

            for selector in selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    shop_name = title_elem.get_text(strip=True)
                    shop_name = re.sub(r'промокод[ыа]?\s*(и\s*купоны?)?', '', shop_name, flags=re.IGNORECASE)
                    shop_name = re.sub(r'купон[ыа]?(\s*и\s*скидки)?', '', shop_name, flags=re.IGNORECASE)
                    shop_name = re.sub(r'\s+', ' ', shop_name).strip()

                    if shop_name and len(shop_name) > 2:
                        return shop_name

            # Fallback к словарю известных магазинов
            if '/dealstore/' in url:
                slug = url.rstrip('/').split('/')[-1].lower()
                known_shops = {
                    'perekrestok': 'Перекрёсток', 'pyaterochka': 'Пятёрочка',
                    '5ka': 'Пятёрочка', 'magnit': 'Магнит',
                    'ozon': 'Ozon', 'wildberries': 'Wildberries',
                    'wb': 'Wildberries', 'lamoda': 'Lamoda',
                    'mvideo': 'М.Видео', 'eldorado': 'Эльдорадо',
                }

                if slug in known_shops:
                    return known_shops[slug]

                return slug.replace('-', ' ').title()

            return "Неизвестный магазин"

        except Exception as e:
            logger.warning(f"Ошибка извлечения названия: {e}")
            return "Неизвестный магазин"

    async def _parse_single_card_simple(self, card, shop_name_override: Optional[str] = None) -> Optional[Dict]:
        """Парсинг одной карточки (аналог _parse_single_card)"""
        try:
            h3_elem = card.select_one('h3 > a')
            if h3_elem:
                description = h3_elem.get_text(strip=True)
            else:
                links = card.select('a[href]')
                description = None
                for link in links:
                    text = link.get_text(strip=True)
                    if text and len(text) > 10:
                        description = text
                        break

            if not description:
                return None

            if shop_name_override:
                shop_name = shop_name_override
            else:
                shop_link = card.select_one('a[href*="/dealstore/"]')
                if shop_link:
                    shop_name = shop_link.get_text(strip=True)
                else:
                    shop_elem = card.select_one('.dealstore, span.dealstore')
                    shop_name = shop_elem.get_text(strip=True) if shop_elem else "Неизвестный магазин"

            code_elem = card.select_one('.rehub_offer_coupon, span.rehub_offer_coupon, .code, span.code')
            if code_elem:
                code = code_elem.get_text(strip=True)
            else:
                all_spans = card.select('span')
                code = None
                if all_spans:
                    for span in reversed(all_spans):
                        text = span.get_text(strip=True)
                        if text and 4 <= len(text) <= 20:
                            if re.match(r'^[A-Z0-9-]+$', text, re.IGNORECASE):
                                code = text
                                break

            if not code:
                card_text = card.get_text()
                code_matches = re.findall(r'\b([A-Z0-9]{4,20})\b', card_text)
                for potential_code in code_matches:
                    if not re.match(r'^\d+$', potential_code):
                        code = potential_code
                        break

            if not code:
                code = "SALE"

            code = re.sub(r'[^A-Z0-9-]', '', code.upper())

            date_elem = card.select_one('.date, span.date')
            date_text = date_elem.get_text(strip=True) if date_elem else ""
            expiry_date = self._parse_expiry_date(date_text)

            link_elem = card.select_one('h3 > a, a[href]')
            shop_url = link_elem['href'] if link_elem and link_elem.get('href') else self.base_url

            if not shop_url.startswith('http'):
                shop_url = self.base_url + shop_url if shop_url.startswith('/') else self.base_url + '/' + shop_url

            image_url = None
            img = card.select_one('img')
            if img:
                src = img.get('src') or img.get('data-src')
                if src and src.startswith('http'):
                    image_url = src

            discount_value, discount_percent = self._parse_discount(description)
            category = self._categorize_shop(shop_name, description)
            is_hot = bool(discount_percent and discount_percent >= 30)
            conditions = description[:200]

            return {
                'shop_name': shop_name,
                'code': code,
                'description': description[:200],
                'discount_value': discount_value,
                'discount_percent': discount_percent,
                'conditions': conditions,
                'expiry_date': expiry_date,
                'category': category,
                'shop_url': shop_url,
                'image_url': image_url,
                'is_hot': is_hot,
            }

        except Exception as e:
            logger.error(f"Ошибка парсинга карточки: {e}")
            return None

    async def parse_page_simple(self, url: str, shop_name_override: Optional[str] = None) -> List[Dict]:
        """Парсинг страницы через HTTP запрос"""
        promocodes = []

        try:
            response = await self.client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'lxml')

            cards = soup.select('.wpsm_recent_posts_list .col_item')

            if not cards:
                alternative_selectors = [
                    'div.rh_offer_list', 'div.rh_grid_image_3_col',
                    'div.deal_daywoo', 'div.woo_offer_list > div', 'article.post',
                ]
                for selector in alternative_selectors:
                    cards = soup.select(selector)
                    if cards:
                        break

            if not cards:
                logger.warning(f"Не найдено карточек на {url}")
                return []

            logger.info(f"Найдено {len(cards)} карточек на {url}")

            for card in cards:
                promo_data = await self._parse_single_card_simple(card, shop_name_override)
                if promo_data:
                    promocodes.append(promo_data)

        except Exception as e:
            logger.error(f"Ошибка парсинга {url}: {e}")

        return promocodes

    async def parse_all_pages(self) -> List[Dict]:
        """Парсинг всех промокодов (упрощенная версия)"""
        all_promocodes = []

        try:
            logger.info(f"Парсинг главной страницы (Simple): {self.base_url}")
            main_promos = await self.parse_page_simple(self.base_url)
            all_promocodes.extend(main_promos)
            logger.info(f"С главной страницы: {len(main_promos)} промокодов")

            # Ищем ссылки на магазины
            response = await self.client.get(self.base_url)
            soup = BeautifulSoup(response.text, 'lxml')

            shop_urls = []
            links = soup.select('a[href*="/dealstore/"]')
            for link in links:
                href = link.get('href')
                if href:
                    if href.startswith('http'):
                        shop_url = href
                    elif href.startswith('/'):
                        shop_url = self.base_url + href
                    else:
                        shop_url = self.base_url + '/' + href

                    if shop_url not in shop_urls:
                        shop_urls.append(shop_url)

            logger.info(f"Найдено магазинов: {len(shop_urls)}")

            # Парсим магазины
            for i, shop_url in enumerate(shop_urls[:self.max_shops], 1):
                try:
                    logger.info(f"[{i}/{min(self.max_shops, len(shop_urls))}] Парсинг: {shop_url}")

                    response = await self.client.get(shop_url)
                    soup = BeautifulSoup(response.text, 'lxml')
                    shop_name = self._extract_shop_name_from_html(soup, shop_url)

                    shop_promos = await self.parse_page_simple(shop_url, shop_name_override=shop_name)
                    all_promocodes.extend(shop_promos)
                    logger.info(f"  -> Найдено: {len(shop_promos)} промокодов")

                    await asyncio.sleep(1)

                except Exception as e:
                    logger.error(f"Ошибка парсинга магазина {shop_url}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Критическая ошибка парсинга: {e}")

        # Удаляем дубликаты
        seen = set()
        unique = []
        for promo in all_promocodes:
            key = (promo['shop_name'], promo['code'])
            if key not in seen:
                seen.add(key)
                unique.append(promo)

        logger.info(f"="*50)
        logger.info(f"ИТОГО (Simple): {len(unique)} уникальных промокодов")
        logger.info(f"="*50)

        return unique


async def test_parser():
    """Тестирование парсера"""
    import json
    from datetime import datetime

    logger.info("="*50)
    logger.info("ЗАПУСК ПОЛНОГО ПАРСИНГА ВСЕХ ПРОМОКОДОВ")
    logger.info("="*50)

    async with CuponcodParser() as parser:
        promocodes = await parser.parse_all_pages()

        logger.info(f"\n{'='*50}")
        logger.info(f"РЕЗУЛЬТАТЫ ПАРСИНГА:")
        logger.info(f"Всего найдено промокодов: {len(promocodes)}")
        logger.info(f"{'='*50}\n")

        # Группировка по категориям
        categories = {}
        for promo in promocodes:
            cat = promo['category']
            categories[cat] = categories.get(cat, 0) + 1

        logger.info("Промокоды по категориям:")
        for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {cat}: {count}")

        logger.info(f"\n{'='*50}")
        logger.info("Примеры промокодов:")
        logger.info(f"{'='*50}\n")

        for i, promo in enumerate(promocodes[:10], 1):
            logger.info(f"{i}. {promo['shop_name']} - {promo['code']}")
            logger.info(f"   📝 {promo['description'][:60]}...")
            logger.info(f"   🏷️ {promo['category']}")
            logger.info(f"   💰 Скидка: {promo['discount_value']}")
            logger.info(f"   🔥 Горячее: {'Да' if promo['is_hot'] else 'Нет'}")
            logger.info("")

        # Сохраняем в JSON
        json_filename = f"data/promocodes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        # Конвертируем datetime в строку для JSON
        json_data = []
        for promo in promocodes:
            promo_copy = promo.copy()
            if promo_copy['expiry_date']:
                promo_copy['expiry_date'] = promo_copy['expiry_date'].isoformat()
            json_data.append(promo_copy)

        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        logger.info(f"\n{'='*50}")
        logger.info(f"Результаты сохранены в: {json_filename}")
        logger.info(f"{'='*50}\n")

    return promocodes


if __name__ == "__main__":
    asyncio.run(test_parser())