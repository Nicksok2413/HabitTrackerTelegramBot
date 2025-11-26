"""Базовый репозиторий с общими CRUD-операциями."""

from typing import Any, Generic, Sequence, TypeVar

from pydantic import BaseModel
from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.core.logging import api_log as log
from src.api.models import Base as SQLAlchemyBaseModel

# Определяем обобщенные (Generic) типы для моделей SQLAlchemy и схем Pydantic
ModelType = TypeVar("ModelType", bound=SQLAlchemyBaseModel)  # SQLAlchemy модель
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)  # Pydantic схема для создания
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)  # Pydantic схема для обновления


class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    Базовый класс репозитория для асинхронных CRUD-операций.

    Предоставляет общие методы для создания, чтения, обновления и удаления
    сущностей в базе данных.

    Attributes:
        model: Класс модели SQLAlchemy, с которым работает репозиторий.
    """

    def __init__(self, model: type[ModelType]):
        """
        Инициализирует базовый репозиторий.

        Args:
            model (ModelType): Класс модели SQLAlchemy.
        """
        self.model = model

    async def get_by_id(self, db_session: AsyncSession, *, obj_id: int) -> ModelType | None:
        """
        Получает одну запись по ее ID.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            obj_id (int): Идентификатор записи.

        Returns:
            ModelType | None: Экземпляр модели или None, если запись не найдена.
        """
        log.debug(f"Получение записи {self.model.__name__} по ID: {obj_id}")
        statement = select(self.model).where(self.model.id == obj_id)
        result = await db_session.execute(statement)
        instance = result.scalar_one_or_none()

        if instance:
            log.debug(f"Запись {self.model.__name__} с ID {obj_id} найдена.")
        else:
            log.debug(f"Запись {self.model.__name__} с ID {obj_id} не найдена.")

        # is_found = "найдена" if instance else "не найдена"
        # log.debug(f"Запись {self.model.__name__} с ID {obj_id} {is_found}.")

        return instance

    async def get_by_filter_first_or_none(
        self, db_session: AsyncSession, *filters: ColumnElement[bool]
    ) -> ModelType | None:
        """
        Получает первую запись, соответствующую заданным критериям фильтрации, или None.

        Критерии должны быть выражениями SQLAlchemy (например, self.model.name == "John").

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            *filters (ColumnElement[bool]): Один или несколько критериев фильтрации SQLAlchemy.
                                            Они будут объединены через AND.

        Returns:
            ModelType | None: Экземпляр модели или None, если запись не найдена.
        """
        log.debug(f"Получение записи {self.model.__name__} с фильтрами {filters}")
        statement = select(self.model)

        if filters:
            statement = statement.where(*filters)

        result = await db_session.execute(statement)
        instance =  result.scalar_one_or_none()

        if instance:
            log.debug(f"Запись {self.model.__name__} найдена.")
        else:
            log.debug(f"Запись {self.model.__name__} не найдена.")

        # is_found = "найдена" if instance else "не найдена"
        # log.debug(f"Запись {self.model.__name__} {is_found}.")

        return instance

    async def get_multi(
            self,
            db_session: AsyncSession,
            *,
            skip: int = 0,
            limit: int = 100,
            order_by: list[ColumnElement[Any]] | None = None,
    ) -> Sequence[ModelType]:
        """
        Получает список записей с пагинацией и опциональной сортировкой.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            skip (int): Количество записей, которое нужно пропустить.
            limit (int): Максимальное количество записей для возврата.
            order_by (list[ColumnElement[Any]] | None): Список полей для сортировки
                                                       (например, [self.model.created_at.desc()]).

        Returns:
            Sequence[ModelType]: Список экземпляров модели.
        """
        log.debug(f"Получение списка записей {self.model.__name__}: (skip={skip}, limit={limit}, order_by={order_by})")
        statement = select(self.model)

        if order_by:
            statement = statement.order_by(*order_by)

        statement = statement.offset(skip).limit(limit)
        result = await db_session.execute(statement)
        instances = result.scalars().all()
        log.debug(f"Найдено {len(instances)} записей {self.model.__name__}.")
        return instances

    async def get_multi_by_filter(
        self,
        db_session: AsyncSession,
        *filters: ColumnElement[bool],
        skip: int = 0,
        limit: int = 100,
        order_by: list[ColumnElement[Any]] | None = None,
    ) -> Sequence[ModelType]:
        """
        Получает список записей, соответствующих заданным критериям фильтрации,
        с пагинацией и опциональной сортировкой.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            *filters (ColumnElement[bool]): Критерии фильтрации SQLAlchemy.
            skip (int): Количество записей, которое нужно пропустить.
            limit (int): Максимальное количество записей для возврата.
            order_by (list[ColumnElement[Any]] | None): Список полей для сортировки
                                                       (например, [self.model.created_at.desc()]).

        Returns:
            Sequence[ModelType]: Список экземпляров модели.
        """
        log.debug(
            f"Получение списка записей {self.model.__name__} по фильтрам: {filters} "
            f"(skip={skip}, limit={limit}, order_by={order_by})"
        )
        statement = select(self.model)

        if filters:
            statement = statement.where(*filters)

        if order_by:
            statement = statement.order_by(*order_by)

        statement = statement.offset(skip).limit(limit)

        result = await db_session.execute(statement)
        instances = result.scalars().all()
        log.debug(f"Найдено {len(instances)} записей {self.model.__name__}.")
        return instances

    async def add(self, db_session: AsyncSession, *, db_obj: ModelType) -> ModelType:
        """
        Добавляет объект модели в сессию.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            db_obj (ModelType): Экземпляр модели для добавления.

        Returns:
            ModelType: Добавленный объект модели.
        """
        log.debug(f"Добавление {self.model.__name__} в сессию (ID: {getattr(db_obj, 'id', 'new')})")
        db_session.add(db_obj)
        return db_obj

    async def create(self, db_session: AsyncSession, *, obj_in: CreateSchemaType) -> ModelType:
        """
        Создает и добавляет новый объект в сессию на основе Pydantic схемы.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            obj_in (CreateSchemaType): Pydantic схема с данными для создания модели.

        Returns:
            ModelType: Созданный экземпляр модели.
        """
        # Конвертируем в словарь
        obj_in_data = obj_in.model_dump()

        log.debug(f"Подготовка к созданию записи {self.model.__name__} с данными: {obj_in_data}")
        db_obj = self.model(**obj_in_data)
        await self.add(db_session, db_obj=db_obj)
        await db_session.flush()
        await db_session.refresh(db_obj)
        log.info(f"{self.model.__name__} успешно создан.")
        return db_obj

    async def update(
        self,
        db_session: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: UpdateSchemaType | dict[str, Any],
    ) -> ModelType:
        """
        Обновляет существующую запись в базе данных.

        Args:
            db_session  (AsyncSession): Асинхронная сессия базы данных.
            db_obj (ModelType): Экземпляр модели SQLAlchemy для обновления.
            obj_in (UpdateSchemaType | dict[str, Any]): Схема Pydantic с данными для обновления или словарь.

        Returns:
            ModelType: Обновленный экземпляр модели.
        """
        log.debug(f"Обновление записи {self.model.__name__} с ID: {db_obj.id}")

        # Конвертируем в словарь, исключая None значения (чтобы не затереть данные пустыми полями)
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)  # exclude_unset=True для частичного обновления

        # Обновляем поля модели
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
            else:
                log.warning(f"Попытка обновить несуществующее поле '{field}' для {self.model.__name__} ID: {db_obj.id}")

        await self.add(db_session, db_obj=db_obj)
        await db_session.flush()
        await db_session.refresh(db_obj)
        log.info(f"{self.model.__name__} с ID: {db_obj.id} успешно обновлен.")
        return db_obj

    async def remove(self, db_session: AsyncSession, *, db_obj: ModelType) -> None:
        """
         Помечает объект для удаления в сессии.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            db_obj (ModelType): Объект для удаления.
        """

        log.debug(f"Пометка на удаление записи {self.model.__name__} (ID: {getattr(db_obj, 'id', 'N/A')})")
        await db_session.delete(db_obj)
        await db_session.flush()
