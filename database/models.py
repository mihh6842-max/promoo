"""
Модели базы данных
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String, Integer, DateTime, Boolean, Text, ForeignKey, Float, Index
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Базовый класс для всех моделей"""
    pass


class PromoCode(Base):
    """Модель промокода"""
    __tablename__ = "promocodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Основная информация
    shop_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    discount_value: Mapped[Optional[str]] = mapped_column(String(50))
    discount_percent: Mapped[Optional[float]] = mapped_column(Float)

    # Условия и сроки
    conditions: Mapped[Optional[str]] = mapped_column(Text)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Категория и ссылки
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    shop_url: Mapped[str] = mapped_column(String(500), nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Мета информация
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_new: Mapped[bool] = mapped_column(Boolean, default=True)
    is_hot: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Статистика
    views_count: Mapped[int] = mapped_column(Integer, default=0)
    copy_count: Mapped[int] = mapped_column(Integer, default=0)

    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Связи
    favorites: Mapped[list["Favorite"]] = relationship(
        back_populates="promocode", cascade="all, delete-orphan"
    )

    # Индексы
    __table_args__ = (
        Index('idx_shop_category', 'shop_name', 'category'),
        Index('idx_active_new', 'is_active', 'is_new'),
    )

    def __repr__(self) -> str:
        return f"<PromoCode(id={self.id}, shop={self.shop_name}, code={self.code})>"


class User(Base):
    """Модель пользователя"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255))
    first_name: Mapped[Optional[str]] = mapped_column(String(255))
    last_name: Mapped[Optional[str]] = mapped_column(String(255))

    # Настройки
    is_subscribed: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_new_promos: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_hot_promos: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_expiring: Mapped[bool] = mapped_column(Boolean, default=False)

    # Статистика
    promo_views: Mapped[int] = mapped_column(Integer, default=0)
    promo_copies: Mapped[int] = mapped_column(Integer, default=0)

    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_activity: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Связи
    favorites: Mapped[list["Favorite"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"


class Favorite(Base):
    """Модель избранных промокодов"""
    __tablename__ = "favorites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    promocode_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("promocodes.id"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Связи
    user: Mapped["User"] = relationship(back_populates="favorites")
    promocode: Mapped["PromoCode"] = relationship(back_populates="favorites")

    # Индексы
    __table_args__ = (
        Index('idx_user_promo', 'user_id', 'promocode_id', unique=True),
    )

    def __repr__(self) -> str:
        return f"<Favorite(user_id={self.user_id}, promocode_id={self.promocode_id})>"


class Subscription(Base):
    """Модель подписок на магазины/категории"""
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Тип подписки
    subscription_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'shop' или 'category'
    subscription_value: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Связи
    user: Mapped["User"] = relationship(back_populates="subscriptions")

    # Индексы
    __table_args__ = (
        Index('idx_user_subscription', 'user_id', 'subscription_type', 'subscription_value'),
    )

    def __repr__(self) -> str:
        return (
            f"<Subscription(user_id={self.user_id}, "
            f"type={self.subscription_type}, value={self.subscription_value})>"
        )


class ParseLog(Base):
    """Модель логов парсинга"""
    __tablename__ = "parse_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success, error, running

    # Статистика
    total_found: Mapped[int] = mapped_column(Integer, default=0)
    new_added: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    deactivated: Mapped[int] = mapped_column(Integer, default=0)

    error_message: Mapped[Optional[str]] = mapped_column(Text)

    def __repr__(self) -> str:
        return f"<ParseLog(id={self.id}, status={self.status}, new_added={self.new_added})>"
