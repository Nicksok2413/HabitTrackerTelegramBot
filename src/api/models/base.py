"""Базовое определение модели для SQLAlchemy."""

from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

# Соглашение об именовании для внешних ключей и индексов (для Alembic и SQLAlchemy)
# https://alembic.sqlalchemy.org/en/latest/naming.html
# https://docs.sqlalchemy.org/en/20/core/constraints.html#constraint-naming-conventions
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata_obj = MetaData(naming_convention=convention)


class TimestampMixin:
    """
    Миксин для добавления полей created_at и updated_at к моделям.

    Attributes:
        created_at: Время создания записи (автоматически устанавливается БД).
        updated_at: Время последнего обновления записи (автоматически обновляется БД при изменении).
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Время создания записи",
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="Время последнего обновления записи",
        nullable=False,
    )


class Base(DeclarativeBase, TimestampMixin):
    """
    Базовый класс для декларативных моделей SQLAlchemy.

    Предоставляет:
    - Настроенный metadata (naming convention).
    - Автоматическое именование таблиц (User -> users).
    - Общий первичный ключ 'id'.
    - Поля created_at и updated_at (через TimestampMixin).
    - Стандартный __repr__.
    """

    # Явно указываем, что это абстрактный класс
    # Это предотвращает создание таблицы 'bases' и гарантирует, что этот класс используется только как шаблон
    __abstract__ = True

    # Применение соглашения об именовании
    metadata = metadata_obj

    @declared_attr.directive
    def __tablename__(cls) -> str:
        """
        Автоматически генерирует имя таблицы на основе имени класса.

        Для сложных случаев (Child -> Children) можно переопределять атрибут __tablename__ в самой модели.
        Пример: User -> users.
        """
        # Простая плюрализация: добавляем 's'
        return f"{cls.__name__.lower()}s"

    # Общий первичный ключ для большинства моделей
    # Если у какой-то модели будет другой ПК, его нужно будет объявить там явно
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    def __repr__(self) -> str:
        """
        Возвращает строковое представление объекта модели.

        Включает имя класса и значение первичного ключа 'id'.
        Если модель имеет другой первичный ключ, этот метод нужно переопределить.
        Пример: <User(id=1)>.
        """
        return f"<{self.__class__.__name__}(id={self.id!r})>"
