"""
Базовый класс для сервисов.

Реализует основную бизнес-логику CRUD операций, управление транзакциями
и валидацию данных перед передачей в репозиторий.
"""

from typing import Any, Generic, Sequence, TypeVar, cast

from pydantic import BaseModel
from sqlalchemy import ColumnElement, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.core.exceptions import BadRequestException, NotFoundException
from src.api.core.logging import api_log as log
from src.api.models import Base as SQLAlchemyBaseModel
from src.api.repositories import BaseRepository

# Определяем обобщенные (Generic) типы для моделей SQLAlchemy, репозиториев и схем Pydantic
ModelType = TypeVar("ModelType", bound=SQLAlchemyBaseModel)  # SQLAlchemy модель
RepositoryType = TypeVar("RepositoryType", bound=BaseRepository)  # Репозиторий
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)  # Pydantic схема для создания
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)  # Pydantic схема для обновления


class BaseService(Generic[ModelType, RepositoryType, CreateSchemaType, UpdateSchemaType]):
    """
    Базовый сервис с общими операциями и управлением транзакциями.

    Этот класс предназначен для наследования конкретными сервисами.
    Он предоставляет общую логику для CRUD операций, используя репозиторий.
    Управление транзакциями (commit, rollback) предполагается на уровне
    конкретных методов сервиса, которые представляют собой "единицу работы (Unit of Work)".

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

    def _get_order_by_clause(self, sort_by: str | None, descending: bool = False) -> list[ColumnElement[Any]] | None:
        """
        Формирует список выражений для сортировки SQLAlchemy на основе строкового имени поля.

        Проверяет, существует ли указанное поле в модели, чтобы предотвратить
        ошибки выполнения или попытки сортировки по недопустимым полям.

        Args:
            sort_by (str | None): Строковое имя поля модели для сортировки.
            descending (bool): Флаг направления сортировки (True для DESC, False для ASC).

        Returns:
            list[ColumnElement[Any]] | None: Список выражений для order_by или None.
                                                       (например, [self.repository.model.created_at.desc()]).

        Raises:
            BadRequestException: Если указанного поля не существует в модели.
        """
        model_name = self.repository.model.__name__

        if not sort_by:
            return None

        # Проверяем наличие поля в модели
        if not hasattr(self.repository.model.__table__.columns, sort_by):
            log.warning(f"Попытка сортировки по несуществующему полю '{sort_by}' в модели {model_name}")

            # Получаем список доступных колонок для подсказки в ошибке
            available_columns = list(self.repository.model.__table__.columns.keys())

            # Выбрасываем ошибку с информацией о доступных колонках модели
            raise BadRequestException(
                message=f"Некорректное поле для сортировки: '{sort_by}'. Доступные поля: {available_columns}",
                error_type="invalid_sort_field",
                loc=["query", "sort_by"],
            )

        field = getattr(self.repository.model.__table__.columns, sort_by)

        # Формируем выражение сортировки
        order_expression = desc(field) if descending else asc(field)

        return [order_expression]

    async def get_by_id(self, db_session: AsyncSession, *, obj_id: int) -> ModelType:
        """
        Получает объект по ID или выбрасывает исключение, если объект не найден.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            obj_id (int): ID объекта.

        Returns:
            ModelType: Найденный объект.

        Raises:
            NotFoundException: Если объект с указанным ID не найден.
        """
        model_name = self.repository.model.__name__

        # Проверка существования объекта
        db_obj = await self.repository.get_by_id(db_session, obj_id=obj_id)

        # Если объект не найден, выбрасываем исключение
        if not db_obj:
            raise NotFoundException(
                message=f"{model_name} с ID {obj_id} не найден.",
                error_type=f"{model_name.lower()}_not_found",
            )

        # Возвращаем найденный объект
        return cast(ModelType, db_obj)  # Явное приведение типа для mypy

    async def get_list(
        self,
        db_session: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        sort_by: str | None = None,
        descending: bool = False,
    ) -> Sequence[ModelType]:
        """
        Получает список объектов с поддержкой пагинации и динамической сортировки.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            skip (int): Количество записей для пропуска.
            limit (int): Максимальное количество записей.
            sort_by (str | None): Поле для сортировки.
            descending (bool): Сортировать по убыванию.

        Returns:
            Sequence[ModelType]: Список объектов.
        """
        # Преобразуем строковые параметры сортировки в выражения SQLAlchemy
        order_by_clause = self._get_order_by_clause(sort_by, descending)

        return await self.repository.get_multi(db_session, skip=skip, limit=limit, order_by=order_by_clause)

    async def create(self, db_session: AsyncSession, *, obj_in: CreateSchemaType) -> ModelType:
        """
        Создает новый объект.

        Управляет транзакцией: выполняет commit в случае успеха или rollback при ошибке.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            obj_in (CreateSchemaType): Схема с данными для создания.

        Returns:
            ModelType: Созданный объект.
        """
        model_name = self.repository.model.__name__

        try:
            # Репозиторий добавляет объект в сессию
            db_obj = await self.repository.create(db_session, obj_in=obj_in)

            # Сервис фиксирует транзакцию (бизнес-операция завершена успешно)
            await db_session.commit()

            # Возвращаем созданный объект
            return cast(ModelType, db_obj)  # Явное приведение типа для mypy

        except Exception as exc:
            # При любой ошибке откатываем транзакцию, чтобы сохранить целостность данных
            await db_session.rollback()

            # Логируем ошибку и выбрасываем исключение
            log.error(f"Ошибка при создании {model_name}: {exc}", exc_info=True)
            raise exc

    async def update(
        self,
        db_session: AsyncSession,
        *,
        db_obj: ModelType | None = None,
        obj_id: int,
        obj_in: UpdateSchemaType,
    ) -> ModelType:
        """
        Обновляет объект базы данных.

        Ищет объект по ID и обновляет его или выбрасывает исключение, если объект не найден.
        Если передан аргумент `db_obj` - уже найденный объект для обновления,
        то не выполняет поиск (избегаем лишнего SELECT).

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            db_obj (ModelType | None): Сам объект для обновления.
            obj_id (int): ID объекта для обновления.
            obj_in (UpdateSchemaType): Схема с данными для обновления.

        Returns:
            ModelType: Обновленный объект.

        Raises:
            NotFoundException: Если объект для обновления не найден.
        """
        model_name = self.repository.model.__name__

        # Если сам объект для обновления (db_obj) не был передан, то выполняем его поиск по ID
        if db_obj is None:
            db_obj = await self.get_by_id(db_session, obj_id=obj_id)

        # Здесь можно добавить дополнительные проверки прав доступа, используя **kwargs,
        # например, проверка, что user_id из JWT совпадает с user_id объекта

        try:
            # Репозиторий добавляет объект в сессию
            updated_obj = await self.repository.update(db_session, db_obj=db_obj, obj_in=obj_in)

            # Сервис фиксирует обновление объекта
            await db_session.commit()

            # Возвращаем обновленный объект
            return cast(ModelType, updated_obj)  # Явное приведение типа для mypy

        except Exception as exc:
            # При любой ошибке откатываем транзакцию, чтобы сохранить целостность данных
            await db_session.rollback()

            # Логируем ошибку и выбрасываем исключение
            log.error(f"Ошибка при обновлении {model_name} (ID: {obj_id}): {exc}", exc_info=True)
            raise exc

    async def delete(
        self,
        db_session: AsyncSession,
        *,
        db_obj: ModelType | None = None,
        obj_id: int,
    ) -> None:
        """
        Удаляет объект базы данных.

        Ищет объект по ID и удаляет его или выбрасывает исключение, если объект не найден.
        Если передан аргумент `db_obj` - уже найденный объект для удаления,
        то не выполняет поиск (избегаем лишнего SELECT).

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            db_obj (ModelType | None): Сам объект для удаления.
            obj_id (int): ID объекта для удаления.

        Raises:
            NotFoundException: Если объект для удаления не найден.
        """
        model_name = self.repository.model.__name__

        # Если сам объект для удаления (db_obj) не был передан, то выполняем его поиск по ID
        if db_obj is None:
            db_obj = await self.get_by_id(db_session, obj_id=obj_id)

        try:
            # Репозиторий помечает объект на удаление
            await self.repository.remove(db_session, db_obj=db_obj)

            # Сервис фиксирует удаление объекта
            await db_session.commit()

            # Логируем успешное удаление объекта
            log.info(f"{model_name} (ID: {obj_id}) успешно удален.")

        except Exception as exc:
            # При любой ошибке откатываем транзакцию, чтобы сохранить целостность данных
            await db_session.rollback()

            # Логируем ошибку и выбрасываем исключение
            log.error(f"Ошибка при удалении {model_name} (ID: {obj_id}): {exc}", exc_info=True)
            raise exc
