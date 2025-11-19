"""Базовый класс для сервисов."""

from typing import Any, Generic, TypeVar, cast

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.core.exceptions import NotFoundException
from src.api.core.logging import api_log as log
from src.api.models import Base as SQLAlchemyBaseModel
from src.api.repositories import BaseRepository

# Обобщенные (Generic) типы
ModelType = TypeVar("ModelType", bound=SQLAlchemyBaseModel)
RepositoryType = TypeVar("RepositoryType", bound=BaseRepository)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class BaseService(Generic[ModelType, RepositoryType, CreateSchemaType, UpdateSchemaType]):
    """
    Базовый сервис с общими операциями.

    Этот класс предназначен для наследования конкретными сервисами.
    Он предоставляет общую логику для CRUD операций, используя репозиторий.
    Управление транзакциями (commit, rollback) предполагается на уровне
    конкретных методов сервиса, которые представляют собой "единицу работы".

    Attributes:
        repository (RepositoryType): Экземпляр репозитория для работы с данными.
    """

    def __init__(self, repository: RepositoryType):
        """
        Инициализирует базовый сервис.

        Args:
            repository (RepositoryType): Репозиторий для работы с данными.
        """
        self.repository = repository

    async def get_by_id(self, db_session: AsyncSession, *, obj_id: int) -> ModelType:
        """
        Получает объект по ID.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            obj_id (int): ID объекта.

        Returns:
            ModelType: Найденный объект.

        Raises:
            NotFoundException: Если объект с указанным ID не найден.
        """
        db_obj = await self.repository.get_by_id(db_session, obj_id=obj_id)

        if not db_obj:
            raise NotFoundException(
                message=f"{self.repository.model.__name__} с ID {obj_id} не найден.",
                error_type=f"{self.repository.model.__name__.lower()}_not_found",
            )

        # Явное приведение типа для Mypy
        return cast(ModelType, db_obj)

    async def create(self, db_session: AsyncSession, *, obj_in: CreateSchemaType) -> ModelType:
        """
        Создает новый объект.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            obj_in (CreateSchemaType): Схема с данными для создания.

        Returns:
            ModelType: Созданный объект.
        """
        db_obj = await self.repository.create(db_session, obj_in=obj_in)

        try:
            await db_session.flush()  # Получаем ID и другие сгенерированные БД значения
            await db_session.refresh(db_obj)  # Обновляем объект из БД
            await db_session.commit()  # Фиксируем транзакцию
        except Exception as exc:
            log.error(
                f"Ошибка при создании {self.repository.model.__name__}: {exc}",
                exc_info=True,
            )
            await db_session.rollback()
            raise

        # Явное приведение типа для Mypy
        return cast(ModelType, db_obj)

    async def update(
        self,
        db_session: AsyncSession,
        *,
        obj_id: int,
        obj_in: UpdateSchemaType,
        **kwargs: Any,
    ) -> ModelType:
        """
        Обновляет существующий объект по ID.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            obj_id (int): ID объекта для обновления.
            obj_in (UpdateSchemaType): Схема с данными для обновления.
            **kwargs: Дополнительные аргументы, которые могут быть использованы для
                      проверки прав или других условий перед обновлением.

        Returns:
            ModelType: Обновленный объект.

        Raises:
            NotFoundException: Если объект для обновления не найден.
        """
        # Проверка существования и получение объекта
        db_obj = await self.get_by_id(db_session, obj_id=obj_id)

        # Здесь могут быть дополнительные проверки прав доступа, используя **kwargs,
        # например, проверка, что user_id из JWT совпадает с user_id объекта

        updated_obj = await self.repository.update(db_session, db_obj=db_obj, obj_in=obj_in)

        try:
            await db_session.flush()
            await db_session.refresh(updated_obj)
            await db_session.commit()
        except Exception as exc:
            log.error(
                f"Ошибка при обновлении {self.repository.model.__name__} (ID: {obj_id}): {exc}",
                exc_info=True,
            )
            await db_session.rollback()
            raise

        # Явное приведение типа для Mypy
        return cast(ModelType, updated_obj)

    async def remove(self, db_session: AsyncSession, *, obj_id: int, **kwargs: Any) -> ModelType | None:
        """
        Находит объект по ID и удаляет его.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            obj_id (int): ID объекта для удаления.
            **kwargs: Дополнительные аргументы для проверок.

        Returns:
            ModelType | None: Удаленный объект или None, если не найден.

        Raises:
            NotFoundException: Если объект для удаления не найден.
        """
        log.debug(f"Подготовка к удалению {self.repository.model.__name__} по ID: {obj_id}")
        db_obj = await self.get_by_id(db_session, obj_id=obj_id)

        # Здесь могут быть дополнительные проверки прав доступа

        # Помечаем объект на удаление
        await self.repository.remove(db_session, db_obj=db_obj)

        try:
            # Фиксируем удаление
            await db_session.commit()
            log.info(f"{self.repository.model.__name__} (ID: {obj_id}) успешно удален.")
        except Exception as exc:
            log.error(
                f"Ошибка при удалении {self.repository.model.__name__} (ID: {obj_id}): {exc}",
                exc_info=True,
            )
            await db_session.rollback()
            raise

        return db_obj

    async def get_list(self, db_session: AsyncSession, *, skip: int = 0, limit: int = 100) -> list[ModelType]:
        """
        Получает список объектов с пагинацией.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            skip (int): Количество записей для пропуска.
            limit (int): Максимальное количество записей.

        Returns:
            list[ModelType]: Список объектов.
        """
        items = await self.repository.get_multi(db_session, skip=skip, limit=limit)
        return list(items)
