"""
Система хранения промокодов в JSON файлах
"""
import json
import os
from datetime import datetime
from typing import List, Dict, Set
from pathlib import Path
from loguru import logger


class PromoJSONStorage:
    """Класс для работы с JSON хранилищем промокодов"""

    def __init__(self, storage_dir: str = "data/promo_history"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.current_file = self.storage_dir / "current_promos.json"
        self.history_dir = self.storage_dir / "history"
        self.history_dir.mkdir(exist_ok=True)

    def save_current_promos(self, promocodes: List[Dict]) -> None:
        """
        Сохранить текущие промокоды
        """
        data = {
            "timestamp": datetime.now().isoformat(),
            "total_count": len(promocodes),
            "promocodes": promocodes
        }

        with open(self.current_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"Сохранено {len(promocodes)} промокодов в {self.current_file}")

    def load_current_promos(self) -> List[Dict]:
        """
        Загрузить текущие промокоды
        """
        if not self.current_file.exists():
            return []

        try:
            with open(self.current_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('promocodes', [])
        except Exception as e:
            logger.error(f"Ошибка загрузки текущих промокодов: {e}")
            return []

    def save_to_history(self, promocodes: List[Dict], label: str = None) -> str:
        """
        Сохранить промокоды в историю
        Returns: путь к сохраненному файлу
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if label:
            filename = f"{timestamp}_{label}.json"
        else:
            filename = f"{timestamp}.json"

        filepath = self.history_dir / filename

        data = {
            "timestamp": datetime.now().isoformat(),
            "label": label,
            "total_count": len(promocodes),
            "promocodes": promocodes
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"Сохранено {len(promocodes)} промокодов в историю: {filepath}")
        return str(filepath)

    def find_new_promos(self, new_promos: List[Dict]) -> tuple[List[Dict], List[Dict], List[Dict]]:
        """
        Найти новые, обновленные и удаленные промокоды

        Returns:
            (new_promocodes, updated_promocodes, removed_promocodes)
        """
        old_promos = self.load_current_promos()

        # Создаем словари для быстрого поиска
        old_dict = {
            (p['shop_name'], p['code']): p
            for p in old_promos
        }

        new_dict = {
            (p['shop_name'], p['code']): p
            for p in new_promos
        }

        # Новые промокоды (есть в new, но нет в old)
        new_promocodes = [
            p for p in new_promos
            if (p['shop_name'], p['code']) not in old_dict
        ]

        # Обновленные промокоды (есть в обоих, но изменились)
        updated_promocodes = []
        for key, new_promo in new_dict.items():
            if key in old_dict:
                old_promo = old_dict[key]
                # Проверяем изменения в описании или скидке
                if (old_promo.get('description') != new_promo.get('description') or
                    old_promo.get('discount_value') != new_promo.get('discount_value')):
                    updated_promocodes.append(new_promo)

        # Удаленные промокоды (есть в old, но нет в new)
        removed_promocodes = [
            p for p in old_promos
            if (p['shop_name'], p['code']) not in new_dict
        ]

        logger.info(f"Анализ изменений:")
        logger.info(f"  - Новых: {len(new_promocodes)}")
        logger.info(f"  - Обновленных: {len(updated_promocodes)}")
        logger.info(f"  - Удаленных: {len(removed_promocodes)}")

        return new_promocodes, updated_promocodes, removed_promocodes

    def save_diff_report(self, new_promos: List[Dict], updated_promos: List[Dict],
                        removed_promos: List[Dict]) -> str:
        """
        Сохранить отчет об изменениях
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"diff_{timestamp}.json"
        filepath = self.history_dir / filename

        data = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "new_count": len(new_promos),
                "updated_count": len(updated_promos),
                "removed_count": len(removed_promos)
            },
            "new_promocodes": new_promos,
            "updated_promocodes": updated_promos,
            "removed_promocodes": removed_promos
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"Отчет об изменениях сохранен: {filepath}")
        return str(filepath)

    def cleanup_old_history(self, keep_days: int = 30):
        """
        Очистить старую историю (старше keep_days дней)
        """
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=keep_days)
        deleted_count = 0

        for file in self.history_dir.glob("*.json"):
            try:
                # Извлекаем дату из имени файла
                date_str = file.stem.split('_')[0]  # YYYYMMDD
                file_date = datetime.strptime(date_str, "%Y%m%d")

                if file_date < cutoff_date:
                    file.unlink()
                    deleted_count += 1
            except Exception as e:
                logger.warning(f"Не удалось обработать файл {file}: {e}")
                continue

        if deleted_count > 0:
            logger.info(f"Удалено {deleted_count} старых файлов истории")

    def get_statistics(self) -> Dict:
        """
        Получить статистику по промокодам
        """
        current_promos = self.load_current_promos()

        if not current_promos:
            return {
                "total_count": 0,
                "shops_count": 0,
                "categories": {},
                "hot_deals_count": 0
            }

        # Подсчет по категориям
        categories = {}
        shops = set()
        hot_count = 0

        for promo in current_promos:
            # Категории
            cat = promo.get('category', 'Разное')
            categories[cat] = categories.get(cat, 0) + 1

            # Магазины
            shops.add(promo.get('shop_name'))

            # Горячие предложения
            if promo.get('is_hot'):
                hot_count += 1

        return {
            "total_count": len(current_promos),
            "shops_count": len(shops),
            "categories": categories,
            "hot_deals_count": hot_count,
            "last_update": datetime.now().isoformat()
        }
