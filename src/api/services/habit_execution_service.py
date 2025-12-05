"""Сервис для работы с выполнениями привычек."""

from datetime import date, datetime, timezone
from typing import Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from src.api.core.logging import api_log as log
from src.api.models import Habit, HabitExecution, HabitExecutionStatus, User
from src.api.repositories import HabitExecutionRepository, HabitRepository
from src.api.schemas import HabitExecutionSchemaCreate, HabitExecutionSchemaUpdate

from .base_service import BaseService


class HabitExecutionService(
    BaseService[
        HabitExecution,
        HabitExecutionRepository,
        HabitExecutionSchemaCreate,
        HabitExecutionSchemaUpdate,
    ]
):
    """
    Сервис для управления выполнениями привычек (HabitExecution).

    Отвечает за создание, чтение, обновление записей о выполнении привычек,
    а также за связанную бизнес-логику, такую как обновление счетчиков серий (стриков) у родительской привычки.
    """

    def __init__(
        self,
        execution_repository: HabitExecutionRepository,
        habit_repository: HabitRepository,  # Добавляем зависимость от HabitRepository
    ):
        """
        Инициализирует сервис выполнения привычек.

        Args:
            execution_repository (HabitExecutionRepository): Репозиторий для работы с выполнениями.
            habit_repository (HabitRepository): Репозиторий для работы с привычками.
        """
        super().__init__(repository=execution_repository)
        self.habit_repository = habit_repository  # Сохраняем репозиторий привычек

    def _check_habit_ownership(self, habit: Habit, user_id: int) -> None:
        """
        Вспомогательный метод для проверки принадлежности привычки пользователю.

        Args:
            habit (Habit): Экземпляр привычки.
            user_id (int): ID пользователя.

        Raises:
            ForbiddenException: Если привычка не принадлежит текущему пользователю.
        """
        # Если пользователи не совпадают, логируем и выбрасываем исключение
        if habit.user_id != user_id:
            log.warning(f"Попытка доступа к чужой привычке ID: {habit.id}. User: {user_id}, Owner: {habit.user_id}")
            raise ForbiddenException(message="У вас нет прав на доступ к этой привычке.", error_type="habit_forbidden")

    def _check_habit_active(self, habit: Habit) -> None:
        """
        Вспомогательный метод для проверки активна ли привычка.

        Args:
            habit (Habit): Экземпляр привычки.

        Raises:
            BadRequestException: Если привычка не активна.
        """
        # Если привычка не активна, логируем и выбрасываем исключение
        if not habit.is_active:
            log.warning(f"Привычка '{habit.name}' не активна (в архиве).")
            raise BadRequestException(
                message=f"Привычка '{habit.name}' не активна (в архиве).",
                error_type="habit_not_active",
            )

    def _get_today_date_for_user(self, user: User) -> date:
        """
        Вычисляет текущую дату ("сегодня") с учетом часового пояса пользователя.

        Если часовой пояс пользователя некорректен, используется UTC.

        Args:
            user (User): habit (Habit): Экземпляр пользователя.

        Returns:
            date: Объект даты (YYYY-MM-DD), соответствующий "сегодня" для пользователя.
        """
        # Получаем текущее абсолютное время в UTC
        utc_now = datetime.now(timezone.utc)

        # Получаем строку часового пояса пользователя
        # Если поле пустое или None, используем UTC как дефолт
        user_timezone_str = user.timezone or "UTC"

        try:
            # Пытаемся создать объект информации о часовом поясе (IANA time zone)
            user_timezone = ZoneInfo(user_timezone_str)

        except ZoneInfoNotFoundError:
            # Если в записана несуществующая таймзона (например, опечатка),
            # не роняем запрос, а логируем проблему и откатываемся к UTC
            log.warning(
                f"Некорректный часовой пояс '{user_timezone_str}' у пользователя ID {user.id}. "
                "Используется UTC по умолчанию."
            )
            user_timezone = ZoneInfo("UTC")

        except Exception as exc:
            # Защита от любых других непредвиденных ошибок
            log.error(
                f"Непредвиденная ошибка при определении времени для пользователя ID {user.id}: {exc}", exc_info=True
            )
            user_timezone = ZoneInfo("UTC")

        # Конвертируем UTC время во время пользователя
        # Метод astimezone() создает новый объект datetime с тем же абсолютным моментом времени,
        # но с атрибутами year, month, day, hour, скорректированными под смещение таймзоны
        user_now = utc_now.astimezone(user_timezone)

        # Извлекаем и возвращаем дату "сегодня" для пользователя
        return user_now.date()

    async def _get_habit_by_id(
        self,
        db_session: AsyncSession,
        habit_id: int,
        for_update: bool = False,
    ) -> Habit:
        """
        Вспомогательный метод для получения привычки по ID.

        Получает привычку по ID или выбрасывает исключение.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            habit_id (int): ID привычки.
            for_update (bool): Флаг, указывающий, получаем ли мы привычку для ее же обновления.

        Returns:
            Habit: Экземпляр привычки.

        Raises:
            NotFoundException: Если привычка не найдена.
        """
        # Проверка существования привычки

        if for_update:
            # Если мы пытаемся получить привычку для ее последующего обновления используем специализированный метод,
            # который блокирует строку от изменения другими транзакциями до конца текущей транзакции
            habit = await self.habit_repository.get_habit_by_id_for_update(db_session, habit_id=habit_id)
        else:
            # Иначе используем стандартный метод, наследуемый от базового репозитория
            habit = await self.habit_repository.get_by_id(db_session, obj_id=habit_id)

        # Если объект привычки не найден, выбрасываем исключение
        if not habit:
            raise NotFoundException(message=f"Привычка с ID {habit_id} не найдена.", error_type="habit_not_found")

        # Возвращаем найденный объект привычки
        return habit

    async def _update_habit_streaks(
        self,
        *,
        habit: Habit,
        new_execution_status: HabitExecutionStatus,
        is_new_execution_for_today: bool = True,
        previous_execution_status: HabitExecutionStatus | None = None,
    ) -> bool:
        """
        Обновляет счетчики серий (стриков) для привычки на основе нового статуса выполнения.

        Предназначен для обработки выполнения *сегодняшнего дня*.

        Args:
            habit (Habit): Экземпляр привычки для обновления.
            new_execution_status (HabitExecutionStatus): Новый статус выполнения.
            is_new_execution_for_today (bool): Флаг, указывающий, относится ли это выполнение
                                               к сегодняшнему дню (влияет на логику стриков).
            previous_execution_status (HabitExecutionStatus | None): Предыдущий статус выполнения,
                                                                   если это обновление существующей записи.

        Returns:
            bool: True, если стрики были изменены, иначе False.
        """
        # Если выполнение не относится к сегодняшнему дню, логируем и возвращаем False
        if not is_new_execution_for_today:
            log.debug(f"Стрики для привычки ID: {habit.id} не обновляются, так как выполнение не за сегодня.")
            return False

        # Флаг изменения стриков
        streaks_changed = False

        log.debug(
            f"Обновление стриков для привычки ID: {habit.id}. "
            f"Статус: {previous_execution_status.value if previous_execution_status else 'N/A'}->{new_execution_status}"
        )

        # Сценарий A: Привычка выполнена (new_execution_status = "DONE")
        if new_execution_status == HabitExecutionStatus.DONE:
            # Увеличиваем стрик, только если привычка НЕ была выполнена ранее сегодня
            # Предыдущий статус = "PENDING" или "NOT_DONE"
            if previous_execution_status != HabitExecutionStatus.DONE:
                habit.current_streak += 1
                streaks_changed = True
                log.debug(f"Текущий стрик увеличен до {habit.current_streak} для привычки ID: {habit.id}.")

                # Если текущий стрик становится больше максимального, записываем его значение в максимальный
                if habit.current_streak > habit.max_streak:
                    habit.max_streak = habit.current_streak
                    log.debug(f"Новый рекорд стрика для привычки ID {habit.id}: {habit.max_streak}!.")

        # Сценарий B: Привычка не выполнена (new_execution_status = "NOT_DONE")
        elif new_execution_status == HabitExecutionStatus.NOT_DONE:
            # Сбрасываем стрик, если он был больше 0
            if habit.current_streak > 0:
                habit.current_streak = 0
                streaks_changed = True
                log.debug(f"Текущий стрик сброшен для привычки ID: {habit.id}.")

        # Сценарий C: Отмена выполнения (new_execution_status = "PENDING")
        elif new_execution_status == HabitExecutionStatus.PENDING:
            # Если статус меняется с DONE на PENDING (пользователь случайно нажал "Выполнил", а потом отменил),
            # уменьшаем стрик на 1, но не ниже 0
            if previous_execution_status == HabitExecutionStatus.DONE and habit.current_streak > 0:
                if habit.max_streak == habit.current_streak:
                    habit.max_streak -= 1

                habit.current_streak -= 1
                streaks_changed = True
                log.debug(f"Стрик для привычки ID {habit.id} уменьшен (отмена выполнения).")

        # Возвращаем флаг изменения стриков
        return streaks_changed

    async def get_execution_with_habit(
        self, db_session: AsyncSession, *, execution_id: int, current_user: User
    ) -> HabitExecution:
        """
        Получает детали конкретной записи о выполнении привычки с подгруженным объектом самой привычки.

        Проверяет, что запись о выполнении существует, что связанная с ней привычка активна
        и принадлежит текущему аутентифицированному пользователю.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            execution_id (int): ID записи о выполнении.
            current_user (User): Аутентифицированный пользователь.

        Returns:
            HabitExecution: Экземпляр записи о выполнении с подгруженной привычкой.

        Raises:
            NotFoundException: Если запись о выполнении или связанная привычка не найдены.
            ForbiddenException: Если у пользователя нет прав на доступ к связанной привычке.
            BadRequestException: Если привычка не активна.
        """

        # Получаем выполнения с подгруженной привычкой
        execution_with_habit = await self.repository.get_execution_by_id_with_habit(
            db_session, execution_id=execution_id
        )

        # Если записи о выполнении не существует, логируем и выбрасываем исключение
        if not execution_with_habit:
            log.warning(f"Выполнение ID {execution_id} не найдено.")
            raise NotFoundException(message=f"Выполнение ID {execution_id} не найдено.")

        # Объясняем переменную для объекта связанной привычки
        habit = execution_with_habit.habit

        # Проверяем права пользователя на привычку
        self._check_habit_ownership(habit, current_user.id)

        # Если ошибок не было, логируем успех
        log.debug(f"Детали выполнения ID: {execution_id} успешно получены.")

        # Возвращаем объект выполнения с подгруженной привычкой
        return execution_with_habit

    async def record_habit_execution(
        self,
        db_session: AsyncSession,
        *,
        habit_id: int,
        execution_in: HabitExecutionSchemaCreate,
        current_user: User,
        execution_date_override: date | None = None,
    ) -> HabitExecution:
        """
        Записывает или обновляет выполнение привычки на указанную дату (по умолчанию - сегодня).

        Если запись о выполнении на указанную дату уже существует, ее статус обновляется.
        В противном случае создается новая запись.
        Также обновляются счетчики текущей и максимальной серий (стриков) у привычки,
        если выполнение относится к сегодняшнему дню.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            habit_id (int): ID привычки, для которой фиксируется выполнение.
            execution_in (HabitExecutionSchemaCreate): Схема с новым статусом выполнения.
            current_user (User): Аутентифицированный пользователь, выполняющий действие.
            execution_date_override (date | None): Дата, на которую фиксируется выполнение.
                                                Если None, используется текущая дата (сегодня).
                                                Позволяет отмечать выполнение за прошлые дни.

        Returns:
            HabitExecution: Созданная или обновленная запись о выполнении привычки.

        Raises:
            NotFoundException: Если привычка с указанным ID не найдена.
            ForbiddenException: Если у пользователя нет прав на доступ к этой привычке.
            BadRequestException: Если привычка не активна.
        """
        # Определяем дату "сегодня" для пользователя
        today_user_date = self._get_today_date_for_user(current_user)

        # Вычисляем дату фиксирования выполнения
        # Если дата передана вручную (execution_date_override), используем её,
        # иначе используем "сегодня" по времени пользователя
        target_date = execution_date_override if execution_date_override else today_user_date

        log.info(
            f"Запись выполнения для привычки ID: {habit_id} на {target_date} "
            f"пользователем ID: {current_user.id} со статусом {execution_in.status.value}"
        )

        # Получаем привычку с блокировкой (for_update=True)
        # Это гарантирует, что другой поток не изменит её до конца транзакции
        habit = await self._get_habit_by_id(db_session, habit_id=habit_id, for_update=True)

        # Проверяем ее принадлежность текущему пользователю
        self._check_habit_ownership(habit, current_user.id)
        # Проверяем что она активна
        self._check_habit_active(habit)

        # Проверяем существование записи о выполнении на вычисленную дату
        existing_execution = await self.repository.get_execution_by_habit_id_and_date(
            db_session, habit_id=habit_id, execution_date=target_date
        )

        # Объявляем переменную для предыдущего статуса выполнения
        previous_status: HabitExecutionStatus | None = None
        # Объявляем переменную для создания/изменения объекта привычки
        db_execution: HabitExecution

        # Если запись о выполнении на вычисленную дату существует, меняем статусы и обновляем запись
        if existing_execution:
            log.debug(f"Обновление существующей записи (ID: {existing_execution.id}) о выполнении на {target_date}")
            previous_status = existing_execution.status

            # Если статус не изменился, ничего не делаем
            if previous_status == execution_in.status:
                return existing_execution

            existing_execution.status = execution_in.status
            db_session.add(existing_execution)  # Помечаем объект как измененный в сессии
            db_execution = existing_execution

        # Если записи на вычисленную дату нет, создаем новый объект выполнения привычки
        else:
            log.debug(f"Создание новой записи о выполнении для привычки ID: {habit_id} на {target_date}")
            db_execution = self.repository.model(
                habit_id=habit_id,
                execution_date=target_date,
                status=execution_in.status,
            )
            db_session.add(db_execution)  # Добавляем новый объект в сессию

        # Если вычисленная дата = сегодня, обновляем стрики
        is_today = target_date == today_user_date

        streaks_were_updated = await self._update_habit_streaks(
            habit=habit,
            new_execution_status=execution_in.status,
            is_new_execution_for_today=is_today,
            previous_execution_status=previous_status,
        )

        # Если стрики были обновлены, добавляем объект привычки в сессию, так как он изменился
        if streaks_were_updated:
            db_session.add(habit)

        try:
            # Фиксируем транзакцию (бизнес-операция завершена успешно)
            await db_session.commit()

            # Обновляем данные из базы данных
            await db_session.refresh(db_execution)

            if streaks_were_updated:
                await db_session.refresh(habit)

            # Логируем успех
            log.info(
                f"Выполнение привычки ID {habit_id} на {target_date} (ID: {db_execution.id}) "
                f"успешно записано со статусом {execution_in.status.value}."
            )

            # Возвращаем созданный/обновленный объект выполнения привычки
            return db_execution

        except Exception as exc:
            # При любой ошибке откатываем транзакцию, чтобы сохранить целостность данных
            await db_session.rollback()

            # Логируем ошибку и выбрасываем исключение
            log.error(f"Ошибка при записи выполнения привычки ID: {habit_id}: {exc}", exc_info=True)
            raise exc

    async def get_executions_for_habit_by_user(
        self,
        db_session: AsyncSession,
        *,
        habit_id: int,
        current_user: User,
        status: HabitExecutionStatus | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[HabitExecution]:
        """
        Получает список записей о выполнении для указанной привычки,
        принадлежащей текущему аутентифицированному пользователю.

        Позволяет фильтровать выполнения по статусу и временному диапазону,
        а также использовать пагинацию.

        Args:
            db_session (AsyncSession): Асинхронная сессия базы данных.
            habit_id (int): ID привычки, для которой запрашиваются выполнения.
            current_user (User): Аутентифицированный пользователь.
            status (HabitExecutionStatus | None): Опциональный фильтр по статусу выполнения.
            start_date (date | None): Опциональная начальная дата для фильтрации (включительно).
            end_date (date | None): Опциональная конечная дата для фильтрации (включительно).
            skip (int): Количество записей для пропуска.
            limit (int): Максимальное количество записей для возврата.

        Returns:
            Sequence[HabitExecution]: Список найденных записей о выполнении привычки.

        Raises:
            NotFoundException: Если привычка с указанным ID не найдена.
            ForbiddenException: Если у пользователя нет прав на доступ к этой привычке.
            BadRequestException: Если привычка не активна.
        """
        # Проверяем существование привычки
        habit = await self._get_habit_by_id(db_session, habit_id=habit_id)

        # Проверяем ее принадлежность текущему пользователю
        self._check_habit_ownership(habit, current_user.id)
        # Проверяем что она активна
        self._check_habit_active(habit)

        # Получает список выполнений для привычки
        return await self.repository.get_executions_for_habit(
            db_session,
            habit_id=habit_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit,
        )
