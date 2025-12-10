"""Репозиторий для работы с моделью Habit."""

from typing import Any, Sequence

from sqlalchemy import ColumnElement, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.core.config import settings  # Для значения target_days по умолчанию
from src.api.core.logging import api_log as log
from src.api.models import Habit, User
from src.api.repositories import BaseRepository
from src.api.schemas import HabitSchemaCreate, HabitSchemaUpdate


class HabitRepository(BaseRepository[Habit, HabitSchemaCreate, HabitSchemaUpdate]):
    """
    Репозиторий для выполнения CRUD-операций с моделью Habit.

    Наследует общие методы от BaseRepository и содержит специфичные для Habit методы.
    """

    async def create_habit(
        self,
        db_session: AsyncSession,
        *,
        habit_in: HabitSchemaCreate,
        user_id: int,
    ) -> Habit:
        """
        Создает новую привычку для указанного пользователя.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            habit_in (HabitSchemaCreate): Данные для создания привычки.
            user_id (int): ID аутентифицированного пользователя, создающего привычку.

        Returns:
            Habit: Созданная привычка.
        """

        # Конвертируем в словарь
        habit_in_data = habit_in.model_dump()

        # Устанавливаем target_days из настроек, если в переданных данных - None
        if not habit_in_data.get("target_days"):
            habit_in_data["target_days"] = settings.DAYS_TO_FORM_HABIT

        # Подготавливаем объект привычки
        habit_obj = self.model(**habit_in_data, user_id=user_id)

        # Добавляем объект привычки в сессию
        db_session.add(habit_obj)

        # Получаем ID и другие сгенерированные базой данных значения
        await db_session.flush()

        # Обновляем объект привычки из базы данных
        await db_session.refresh(habit_obj)

        # Возвращаем созданную привычку
        return habit_obj

    async def get_habit_by_id_with_executions(self, db_session: AsyncSession, *, habit_id: int) -> Habit | None:
        """
        Получает привычку по ID с жадной загрузкой ее выполнений.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            habit_id (int): ID привычки.

        Returns:
            Habit | None: Экземпляр привычки с подгруженными выполнениями или None.
        """
        log.info(f"Получение привычки ID: {habit_id} с жадной загрузкой ее выполнений.")
        statement = (
            select(self.model)
            .where(self.model.id == habit_id)
            .options(selectinload(self.model.executions))  # Жадная загрузка выполнений
        )
        result = await db_session.execute(statement)
        habit = result.scalar_one_or_none()

        status = "найдена" if habit else "не найдена"
        log.debug(f"Привычка (ID {habit_id}) с подгруженными выполнениями {status}.")

        return habit

    async def get_habit_by_id_for_update(self, db_session: AsyncSession, *, habit_id: int) -> Habit | None:
        """
        Получает привычку по ID для ее последующего обновления.

        Получает привычку по ID и блокирует строку от изменения другими транзакциями
        до конца текущей транзакции (SELECT ... FOR UPDATE).

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            habit_id (int): ID привычки.

        Returns:
            Habit | None: Экземпляр привычки или None.
        """
        statement = select(self.model).where(self.model.id == habit_id).with_for_update()
        result = await db_session.execute(statement)
        habit = result.scalar_one_or_none()

        status = "найдена" if habit else "не найдена"
        log.debug(f"Привычка (ID {habit_id}) для обновления {status}.")

        return habit

    async def get_habits_by_user_id(
        self,
        db_session: AsyncSession,
        *,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = False,
    ) -> Sequence[Habit]:
        """
        Получает список привычек для указанного пользователя с пагинацией.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            user_id (int): ID пользователя, чьи привычки нужно получить.
            skip (int): Количество записей для пропуска.
            limit (int): Максимальное количество записей.
            active_only (bool): Если True, возвращает только активные привычки.

        Returns:
            Sequence[Habit]: Список привычек пользователя.
        """

        # Явно указываем тип списка: list[ColumnElement[bool]]
        # Это говорит mypy, что внутри лежат SQL-выражения, возвращающие булево значение (WHERE ...)
        filters: list[ColumnElement[bool]] = (
            [self.model.user_id == user_id, self.model.is_active.is_(True)]
            if active_only
            else [self.model.user_id == user_id]
        )
        # Сортировка по времени и имени если active_only == True, иначе сортировка по дате создания (сначала новые)
        # Явно указываем тип списка: list[ColumnElement[Any]]
        # .asc() и .desc() возвращают UnaryExpression, который совместим с ColumnElement
        order: list[ColumnElement[Any]] = (
            [self.model.time_to_remind.asc(), self.model.name.asc()] if active_only else [self.model.created_at.desc()]
        )

        habits = await self.get_multi_by_filter(
            db_session,
            *filters,
            skip=skip,
            limit=limit,
            order_by=order,
        )

        log.debug(f"Найдено {len(habits)} привычек для пользователя ID: {user_id}.")
        return habits

    async def get_habits_needing_notification(self, db_session: AsyncSession) -> Sequence[Habit]:
        """
        Находит активные привычки, время напоминания которых совпадает
        с текущим временем в часовом поясе пользователя.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.

        Returns:
            Sequence[Habit]: Список привычек пользователя, о выполнении которых нужно напомнить.
        """
        # Конвертируем UTC время сервера в локальное время пользователя, используя его timezone

        # Функция `date_trunc('minute', ...)` специфична для PostgreSQL
        # Она округляет время до заданной точности (отбрасываем секунды, чтобы сравнивать только ЧЧ:ММ)

        # Функция `timezone(zone_name, timestamp)` специфична для PostgreSQL
        # Она конвертирует время из одной зоны в другую внутри SQL-запроса

        # Синтаксис `::time` специфичен для PostgreSQL
        # В стандарте SQL это CAST(... AS TIME)

        # Этот запрос
        statement = select(self.model).join(self.model.user).where(
            self.model.is_active.is_(True),
            self.model.user.has(User.is_active.is_(True)),  # Только активным юзерам
            self.model.user.has(User.is_bot_blocked.is_(False)),  # Которые не заблочили бота
            # Сравниваем время:
            text(
                "date_trunc('minute', habits.time_to_remind) = date_trunc('minute', timezone(users.timezone, now())::time)")
        )

        # Подгружаем пользователя, чтобы знать telegram_id для отправки
        statement = statement.options(selectinload(self.model.user))

        result = await db_session.execute(statement)

        return result.scalars().all()

# Можно добавить методы для поиска привычек, у которых time_to_remind совпадает с текущим,
# для использования планировщиком, если планировщик будет обращаться к API,
# либо если логика планировщика будет в API сервисе.
# Если планировщик работает напрямую с БД, такие методы в API репозитории не понадобятся.
