"""
Обработчики сценариев работы с привычками.

Включает в себя:
- Просмотр списка привычек (Pagination).
- Просмотр деталей привычки.
- Отметку выполнения/отмены выполнения привычки.
- Удаление привычки.
- FSM для создания новой привычки: название -> описание -> цель -> время напоминания -> Сохранение в API.
- FSM для редактирования существующей привычки.
"""

from contextlib import suppress
from datetime import date
from re import match
from typing import Any, TypedDict, Unpack

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.types import User as TelegramUser

from src.bot.core.enums import HabitAction
from src.bot.keyboards.callbacks import (
    HabitActionCallback,
    HabitDetailCallback,
    HabitsNavigationCallback,
)
from src.bot.keyboards.inline import (
    get_habit_delete_confirmation_keyboard,
    get_habit_detail_keyboard,
    get_habit_edit_menu_keyboard,
    get_habits_list_keyboard,
)
from src.bot.keyboards.reply import BTN_CREATE_HABIT, BTN_MY_HABITS, get_main_menu_keyboard
from src.bot.services.api_client import APIClientError, HabitTrackerClient
from src.bot.states.habit_states import HabitCreation, HabitEditing
from src.core_shared.logging_setup import setup_logger

# Настраиваем логгер
log = setup_logger("BotHabitHandlers")

# Создаем роутер
router = Router(name="habit_handlers")

# Константа размера страницы для списка привычек
PAGE_SIZE = 5


# ==============================================================================
# Вспомогательные функции (Utils)
# ==============================================================================


def _is_done_today(habit_details: dict[str, Any]) -> bool:
    """
    Проверяет, есть ли в истории выполнений запись за сегодня со статусом 'done'.

    Args:
        habit_details (dict[str, Any]): Словарь с данными привычки, включая ключ 'executions'.

    Returns:
        bool: True - если привычка выполнена сегодня, иначе False.
    """
    today_str = date.today().isoformat()  # 'YYYY-MM-DD'

    executions = habit_details.get("executions", [])

    for execution in executions:
        # Сравниваем строки дат
        if execution.get("execution_date") == today_str and execution.get("status") == "done":
            return True

    return False


def _format_habit_text(
        habit: dict[str, Any],
        is_done_today: bool,
        is_new_habit: bool = False,
) -> str:
    """
    Формирует красивый текст сообщения с информацией о привычке.

    Args:
        habit (dict[str, Any]): Словарь с данными привычки.
        is_done_today (bool): Флаг, определяющий статус выполнения привычки на сегодня.
        is_new_habit (bool): Флаг, определяющий была ли только что создана новая привычка (по умолчанию - False).

    Returns:
        str: Отформатированный текст сообщения (HTML).
    """
    # Формируем статус выполнения на сегодняшний день для существующей привычки
    status_text = "✅ <b>Выполнено сегодня</b>" if is_done_today else "⏳ <b>Ждет выполнения</b>"

    # Форматируем описание, если оно есть
    habit_description_text = f"📝 <i>{habit['description']}</i>\n\n" if habit.get("description") else ""

    # API возвращает время в формате "ЧЧ:ММ:СС", берем первые 5 символов "ЧЧ:ММ"
    formatted_time = str(habit["time_to_remind"])[:5]

    # Нижняя строчка зависит от контекста (новая привычка или просмотр существующей)
    last_line = "Удачи в достижении цели! 💪" if is_new_habit else status_text

    text = (
        f"📌 <b>{habit['name']}</b>\n\n"
        f"{habit_description_text}"
        f"🔥 Стрик: <b>{habit['current_streak']} дн.</b> (Рекорд: {habit['max_streak']})\n"
        f"⏰ Напоминание: {formatted_time}\n"
        f"📅 Цель: {habit['target_days']} дн.\n"
        f"──────────────────\n"
        f"{last_line}"
    )

    # Если создается новая привычка, добавляем строку успеха в начало текста
    if is_new_habit:
        text = "🎉 <b>Привычка успешно создана!</b>\n\n" + text

    return text


# ==============================================================================
# Просмотр списка привычек (List View)
# ==============================================================================


async def _render_habits_page(
    message_or_callback: Message | CallbackQuery,
    tg_user: TelegramUser,
    api_client: HabitTrackerClient,
    page: int,
    is_edit: bool = False,
) -> None:
    """
    Отображает страницу списка привычек (List View).

    Реализует "умную пагинацию": рекурсивно загружает предыдущую страницу,
    если текущая оказалась пустой (например, после удаления элементов).

    Args:
        message_or_callback (Message | CallbackQuery): Объект входящего события.
        tg_user (TelegramUser): Пользователь Telegram.
        api_client (HabitTrackerClient): Клиент API.
        page (int): Номер страницы.
        is_edit (bool): Если True, редактирует текущее сообщение. Иначе отправляет новое.
    """
    # Запрашиваем на 1 элемент больше, чтобы узнать, есть ли следующая страница
    limit = PAGE_SIZE + 1
    skip = page * PAGE_SIZE

    try:
        # Отправляем запрос к API
        habits = await api_client.get_my_habits(
            tg_user=tg_user,
            skip=skip,
            limit=limit,
        )
    except APIClientError:
        text = "❌ Не удалось загрузить список привычек."

        if is_edit and isinstance(message_or_callback, CallbackQuery):
            with suppress(Exception):
                await message_or_callback.answer(text, show_alert=True)
        else:
            if isinstance(message_or_callback, Message):
                await message_or_callback.answer(text)

        return

    # Рекурсивный переход на предыдущую страницу, если текущая пуста (но это не первая)
    if not habits and page > 0:
        log.debug(f"Страница {page} пуста, переходим на страницу {page - 1}")

        await _render_habits_page(
            message_or_callback=message_or_callback,
            tg_user=tg_user,
            api_client=api_client,
            page=page - 1,
            is_edit=is_edit,
        )

        return

    # Определяем, есть ли следующая страница
    has_next = len(habits) > PAGE_SIZE

    # Отрезаем лишний элемент, чтобы список был равен размеру страницы (PAGE_SIZE)
    habits_to_show = habits[:PAGE_SIZE]

    # Формируем текст и клавиатуру
    if not habits_to_show and page == 0:
        text = "📋 <b>У вас пока нет привычек.</b>\nСамое время создать первую! 👇"
        keyboard = None
    else:
        text = f"📋 <b>Ваши привычки (стр. {page + 1}):</b>"
        keyboard = get_habits_list_keyboard(habits=habits_to_show, page=page, has_next=has_next)

    # Отправляем или редактируем сообщение
    if is_edit and isinstance(message_or_callback, CallbackQuery):
        # Если список пуст (например, удалили последнюю привычку), удаляем сообщение или пишем текст
        if not habits_to_show and page == 0:
            await message_or_callback.message.edit_text(text="Список пуст.")  # type: ignore
        else:
            await message_or_callback.message.edit_text(text=text, reply_markup=keyboard)  # type: ignore
    elif isinstance(message_or_callback, Message):
        await message_or_callback.answer(text, reply_markup=keyboard)


@router.message(F.text == BTN_MY_HABITS)
async def show_my_habits(message: Message, api_client: HabitTrackerClient) -> None:
    """
    Обработчик кнопки главного меню "📋 Мои привычки".

    Отправляет первую страницу списка привычек.

    Args:
        message (Message): Объект сообщения Telegram.
        api_client (HabitTrackerClient): Клиент API.
    """
    if not message.from_user:
        return

    await _render_habits_page(
        message_or_callback=message,
        tg_user=message.from_user,
        api_client=api_client,
        page=0,
        is_edit=False,
    )


@router.callback_query(HabitsNavigationCallback.filter())
async def navigate_habits_list(
    callback: CallbackQuery, callback_data: HabitsNavigationCallback, api_client: HabitTrackerClient
) -> None:
    """
    Обработчик кнопок пагинации (Назад/Вперед) и кнопки "Назад к списку".

    Args:
        callback (CallbackQuery): Объект колбэка от нажатия кнопки навигации.
        callback_data (HabitsNavigationCallback): Данные кнопки, содержащие номер целевой страницы.
        api_client (HabitTrackerClient): Клиент API.
    """
    # Всегда отвечаем на callback, чтобы убрать часики загрузки у кнопки
    await callback.answer()

    if not callback.message or not isinstance(callback.message, Message):
        return

    # Редактируем текущее сообщение, показывая нужную страницу
    await _render_habits_page(
        message_or_callback=callback.message,
        tg_user=callback.from_user,
        api_client=api_client,
        page=callback_data.page,
        is_edit=True,
    )


# ==============================================================================
# Детали привычки и действия (Detail View & Actions)
# ==============================================================================


async def _render_habit_details(
    callback: CallbackQuery,
    habit_id: int,
    page: int,
    api_client: HabitTrackerClient,
) -> None:
    """
    Отображает детальную карточку привычки.

    Загружает детали привычки и обновляет сообщение с информацией.

    Args:
        callback (CallbackQuery): Объект колбэка.
        habit_id (int): ID привычки.
        page (int): Номер страницы.
        api_client (HabitTrackerClient): Клиент API.

    """
    # Пытаемся ответить на колбэк, чтобы убрать часики загрузки у кнопки
    # Используем suppress, так как если callback устарел или был вызван вручную,
    # метод answer может упасть, но это не должно прерывать логику отображения
    with suppress(Exception):
        await callback.answer()

    if not callback.message or not isinstance(callback.message, Message):
        return

    try:
        # Получаем полные детали привычки (с выполнениями)
        habit = await api_client.get_habit_details(tg_user=callback.from_user, habit_id=habit_id)

        # Определяем статус на сегодня
        is_done = _is_done_today(habit)

        # Формируем красивый текст
        text = _format_habit_text(habit=habit, is_done_today=is_done, is_new_habit=False)

        # Клавиатура с кнопками действий (выполнить, отменить выполнение, редактировать, удалить и назад)
        keyboard = get_habit_detail_keyboard(
            habit_id=habit["id"],
            page=page,
            is_done_today=is_done,  # Передаем статус для выбора кнопок
        )

        # Обновляем сообщение
        try:
            await callback.message.edit_text(text, reply_markup=keyboard)
        except TelegramBadRequest as exc:
            # Игнорируем ошибку "Message is not modified", если текст не изменился
            # Все остальные ошибки (например, невалидный HTML) - пробрасываем
            if "message is not modified" not in str(exc).lower():
                raise exc

    except APIClientError:
        # В случае ошибки API показываем всплывающее уведомление
        # Используем suppress на случай, если callback.answer уже был вызван выше
        with suppress(Exception):
            await callback.answer("❌ Не удалось загрузить данные о привычке.", show_alert=True)


@router.callback_query(HabitDetailCallback.filter())
async def show_habit_details(
    callback: CallbackQuery, callback_data: HabitDetailCallback, api_client: HabitTrackerClient
) -> None:
    """
    Показывает детали выбранной привычки из списка.

    Args:
        callback (CallbackQuery): Объект колбэка от нажатия на привычку.
        callback_data (HabitDetailCallback): Данные с ID привычки и номером страницы списка.
        api_client (HabitTrackerClient): Клиент API.
    """
    await _render_habit_details(
        callback=callback,
        habit_id=callback_data.habit_id,
        page=callback_data.page,
        api_client=api_client,
    )


@router.callback_query(HabitActionCallback.filter(F.action == HabitAction.VIEW))
async def return_to_habit_details(
    callback: CallbackQuery, callback_data: HabitActionCallback, api_client: HabitTrackerClient
) -> None:
    """
    Обработчик для возврата к просмотру деталей привычки (например, при отмене удаления).

    Args:
        callback (CallbackQuery): Объект колбэка.
        callback_data (HabitActionCallback): Данные с действием 'view'.
        api_client (HabitTrackerClient): Клиент API.
    """
    await _render_habit_details(
        callback=callback,
        habit_id=callback_data.habit_id,
        page=callback_data.page,
        api_client=api_client,
    )


# --- Логика выполнения / отмены выполнения привычки ---


@router.callback_query(HabitActionCallback.filter(F.action.in_({HabitAction.DONE, HabitAction.SET_PENDING})))
async def toggle_habit_status(
    callback: CallbackQuery, callback_data: HabitActionCallback, api_client: HabitTrackerClient
) -> None:
    """
    Переключает статус привычки:
    - done: Выполнить
    - set_pending: Отменить выполнение (вернуть в pending)

    После успеха обновляет интерфейс (карточку привычки), чтобы показать новый статус и стрик.

    Args:
        callback (CallbackQuery): Объект колбэка от нажатия кнопки действия.
        callback_data (HabitActionCallback): Данные с ID привычки и типом действия.
        api_client (HabitTrackerClient): Клиент API.
    """
    # Определяем целевой статус для API
    target_status = "done" if callback_data.action == HabitAction.DONE else "pending"

    try:
        # Отправляем запрос в API
        await api_client.change_habit_status(callback.from_user, callback_data.habit_id, status=target_status)

        # Показываем уведомление
        text = "🎉 Супер! Привычка выполнена!" if target_status == "done" else "↩️ Выполнение отменено."
        await callback.answer(text)

        # Перерисовываем карточку привычки, чтобы показать актуальный статус и стрик
        await _render_habit_details(
            callback=callback,
            habit_id=callback_data.habit_id,
            page=callback_data.page,
            api_client=api_client,
        )

    except APIClientError:
        with suppress(Exception):
            await callback.answer("❌ Ошибка при обновлении статуса привычки.", show_alert=True)


# --- Логика удаления привычки ---


@router.callback_query(HabitActionCallback.filter(F.action == HabitAction.REQUEST_DELETE))
async def request_habit_delete(callback: CallbackQuery, callback_data: HabitActionCallback) -> None:
    """
    Запрашивает подтверждение удаления привычки.

    Args:
        callback (CallbackQuery): Объект колбэка от кнопки 'Удалить'.
        callback_data (HabitActionCallback): Данные с ID привычки.
    """
    # Всегда отвечаем на callback, чтобы убрать часики загрузки у кнопки
    await callback.answer()

    if not callback.message or not isinstance(callback.message, Message):
        return

    # Клавиатура с кнопками действий
    keyboard = get_habit_delete_confirmation_keyboard(habit_id=callback_data.habit_id, page=callback_data.page)

    await callback.message.edit_text(
        "⚠️ <b>Вы действительно хотите удалить эту привычку?</b>\n\n"
        "Это действие нельзя будет отменить. Вся история выполнений будет потеряна.",
        reply_markup=keyboard,
    )


@router.callback_query(HabitActionCallback.filter(F.action == HabitAction.CONFIRM_DELETE))
async def confirm_habit_delete(
    callback: CallbackQuery, callback_data: HabitActionCallback, api_client: HabitTrackerClient
) -> None:
    """
    Выполняет удаление привычки после подтверждения.

    Args:
        callback (CallbackQuery): Объект колбэка от кнопки 'Да, удалить навсегда'.
        callback_data (HabitActionCallback): Данные с ID привычки.
        api_client (HabitTrackerClient): Клиент API.
    """

    try:
        # Удаляем через API
        await api_client.delete_habit(callback.from_user, callback_data.habit_id)

        await callback.answer("✅ Привычка удалена.")

        # Возвращаемся к списку (на страницу, с которой перешли)
        await _render_habits_page(
            message_or_callback=callback,
            tg_user=callback.from_user,
            api_client=api_client,
            page=callback_data.page,
            is_edit=True,
        )

    except APIClientError:
        with suppress(Exception):
            await callback.answer("❌ Не удалось удалить привычку. Попробуйте позже.", show_alert=True)
        # Если ошибка, возвращаем пользователя к просмотру привычки
        await _render_habit_details(
            callback=callback,
            habit_id=callback_data.habit_id,
            page=callback_data.page,
            api_client=api_client,
        )


# ==============================================================================
# Создание привычки (FSM)
# ==============================================================================

# --- Начало (по нажатию кнопки) ---


@router.message(F.text == BTN_CREATE_HABIT)
async def start_habit_creation(message: Message, state: FSMContext) -> None:
    """
    Начинает процесс создания новой привычки.

    Срабатывает при нажатии кнопки "➕ Создать привычку".
    Переводит бота в состояние ожидания названия привычки.

    Args:
        message (Message): Объект сообщения Telegram.
        state (FSMContext): Контекст машины состояний.
    """
    if not message.from_user:
        return

    log.info(f"Пользователь {message.from_user.id} начал создание привычки.")

    await message.answer(
        "✨ <b>Создание новой привычки</b>\n\n"
        "Введите название привычки (например: <i>'Читать 30 минут'</i>, <i>'Выпить стакан воды'</i>).\n"
        "Или нажмите /cancel для отмены.",
        # Убираем клавиатуру меню, чтобы не мешала
        reply_markup=ReplyKeyboardRemove(),
    )

    # Переводим бота в состояние ожидания названия
    await state.set_state(HabitCreation.waiting_for_name)


# --- Получение названия ---


@router.message(HabitCreation.waiting_for_name)
async def process_habit_name(message: Message, state: FSMContext) -> None:
    """
    Принимает название привычки.

    Валидирует ввод (должен быть текст) и переводит бота в состояние ожидания описания привычки.

    Args:
        message (Message): Объект сообщения Telegram.
        state (FSMContext): Контекст машины состояний.
    """
    if not message.text:
        await message.answer("⚠️ Пожалуйста, отправьте текстовое сообщение с названием привычки.")
        return

    habit_name = message.text.strip()

    # Простая валидация длины
    if len(habit_name) > 100:
        await message.answer("⚠️ Название привычки слишком длинное. Пожалуйста, сократите до 100 символов.")
        return

    # Сохраняем данные в контекст FSM
    await state.update_data(name=habit_name)

    await message.answer(
        f"👍 Отлично, название: <b>{habit_name}</b>.\n\n"
        "Теперь добавьте краткое описание или мотивацию (зачем вам это?).\n"
        "Отправьте /skip, если хотите пропустить этот шаг."
    )

    # Переводим бота в состояние ожидания описания
    await state.set_state(HabitCreation.waiting_for_description)


# --- Получение описания ---


@router.message(HabitCreation.waiting_for_description)
async def process_habit_description(message: Message, state: FSMContext) -> None:
    """
    Принимает описание привычки.

    Поддерживает команду /skip для пропуска шага (description будет None).
    Переводит бота в состояние ожидания цели (количества дней).

    Args:
        message (Message): Объект сообщения Telegram.
        state (FSMContext): Контекст машины состояний.
    """
    if not message.text:
        await message.answer("⚠️ Пожалуйста, отправьте текст или нажмите /skip.")
        return

    habit_description: str | None = message.text.strip()

    # Логика пропуска шага (если команда /skip)
    if habit_description == "/skip":
        habit_description = None

    # Сохраняем данные в контекст FSM
    await state.update_data(description=habit_description)

    await message.answer(
        "📅 <b>Цель привычки</b>\n\n"
        "Сколько дней вы хотите придерживаться этой привычки?\n"
        "Обычно привычка формируется за <b>21 день</b>.\n\n"
        "Введите число (например, 30) или нажмите /skip для использования 21 дня."
    )

    # Переводим бота в состояние ожидания цели (количества дней)
    await state.set_state(HabitCreation.waiting_for_target_days)


# --- Получение цели (количества дней) ---
@router.message(HabitCreation.waiting_for_target_days)
async def process_habit_target_days(message: Message, state: FSMContext) -> None:
    """
    Принимает цель (количество дней) для формирования привычки.

    Поддерживает команду /skip для пропуска шага (description будет None).
    Валидирует ввод (должен быть натуральное число) и переводит бота в состояние ожидания времени напоминания.

    Args:
        message (Message): Объект сообщения Telegram.
        state (FSMContext): Контекст машины состояний.
    """
    answer_text = "⚠️ Пожалуйста, введите натуральное число (от 1 и более) или нажмите /skip."

    if not message.text:
        await message.answer(answer_text)
        return

    text = message.text.strip()
    habit_target_days = None

    # Если не /skip, пытаемся распарсить число
    if text != "/skip":
        if not text.isdigit() or int(text) < 1:
            await message.answer(answer_text)
            return

        habit_target_days = int(text)

    # Сохраняем данные в контекст FSM
    await state.update_data(target_days=habit_target_days)

    await message.answer(
        "⏰ <b>Время напоминания</b>\n\n"
        "В какое время вам напоминать о привычке?\n"
        "Введите время в формате <b>ЧЧ:ММ</b> (24-часовой формат).\n"
        "Примеры: <code>08:00</code>, <code>14:30</code>, <code>22:00</code>."
    )

    # Переводим бота в состояние ожидания времени напоминания
    await state.set_state(HabitCreation.waiting_for_time)


# --- Получение времени и сохранение ---


@router.message(HabitCreation.waiting_for_time)
async def process_habit_time(message: Message, state: FSMContext, api_client: HabitTrackerClient) -> None:
    """
    Принимает время, валидирует его и отправляет запрос на создание привычки в API.

    Это финальный шаг сценария.

    Args:
        message (Message): Объект сообщения Telegram.
        state (FSMContext): Контекст машины состояний.
        api_client (HabitTrackerClient): Клиент API.
    """

    if not message.text or not message.from_user:
        await message.answer("⚠️ Введите время текстом в формате ЧЧ:ММ.")
        return

    time_to_remind_str = message.text.strip()

    # Если пользователь ввел Ч:ММ, дополним до ЧЧ:ММ
    if len(time_to_remind_str) == 4 and time_to_remind_str[1] == ":":
        time_to_remind_str = "0" + time_to_remind_str

    # Валидация формата времени через регулярное выражение
    # ^([0-1]?[0-9]|2[0-3]) - часы от 00 до 23
    # :[0-5][0-9]$ - минуты от 00 до 59
    time_pattern = r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"

    if not match(time_pattern, time_to_remind_str):
        await message.answer(
            "⚠️ <b>Неверный формат времени.</b>\n\n"
            "Пожалуйста, введи время в формате ЧЧ:ММ (24-часовой формат).\n"
            "Пример: <code>07:30</code>"
        )
        return

    # Получаем все накопленные данные из машины состояний
    data = await state.get_data()
    habit_name = data["name"]
    habit_description = data.get("description")
    habit_target_days = data.get("target_days")

    # Если валидация прошла, начинаем процесс сохранения
    processing_msg = await message.answer("⏳ Сохраняю привычку...")

    try:
        # Отправляем запрос к API
        new_habit = await api_client.create_habit(
            tg_user=message.from_user,
            name=habit_name,
            description=habit_description,
            time_to_remind=time_to_remind_str,
            target_days=habit_target_days,
        )

        # Формируем красивый ответ
        text = _format_habit_text(habit=new_habit, is_done_today=False, is_new_habit=True)

        await message.answer(
            text=text,
            reply_markup=get_main_menu_keyboard(),  # Возвращаем главное меню
        )
        log.info(f"Привычка '{habit_name}' создана для пользователя {message.from_user.id}.")

    except APIClientError as exc:
        log.error(f"Ошибка при сохранении привычки для {message.from_user.id}: {exc}")
        await message.answer(
            "❌ <b>Произошла ошибка при сохранении.</b>\nПожалуйста, попробуйте еще раз позже.",
            reply_markup=get_main_menu_keyboard(),
        )

    finally:
        # Удаляем сообщение "Сохраняю...", если оно еще есть
        with suppress(Exception):
            await processing_msg.delete()

        # В любом случае (успех или ошибка) сбрасываем состояние FSM
        # Чтобы пользователь не "застрял" в диалоге
        await state.clear()


# ==============================================================================
# Редактирование привычки (FSM: HabitEditing)
# ==============================================================================


# Определяем структуру ожидаемых аргументов (изменяемых полей привычки)
class HabitUpdateParams(TypedDict, total=False):
    name: str
    description: str | None
    time_to_remind: str
    target_days: int


async def _save_habit_change(
        message: Message,
        state: FSMContext,
        api_client: HabitTrackerClient,
        **changes: Unpack[HabitUpdateParams]
) -> None:
    """
    Отправляет изменения привычки в API и возвращает пользователя к карточке привычки.

    Args:
        message (Message): Объект сообщения Telegram.
        state (FSMContext): Контекст машины состояний.
        api_client (HabitTrackerClient): Клиент API.
        **changes (Unpack[HabitUpdateParams]): Словарь изменяемых полей привычки.
    """
    if not message.from_user:
        return

    data = await state.get_data()
    habit_id = data["habit_id"]
    page = data.get("page", 0)

    try:
        # Отправляем запрос к API
        await api_client.update_habit(message.from_user, habit_id, **changes)
        await message.answer("✅ Изменения сохранены.")

        # Показываем обновленную карточку привычки (новым сообщением)
        habit = await api_client.get_habit_details(message.from_user, habit_id)

        # Определяем статус на сегодня
        is_done = _is_done_today(habit)

        # Формируем красивый текст
        text = _format_habit_text(habit=habit, is_done_today=is_done)

        # Клавиатура с кнопками действий
        keyboard = get_habit_detail_keyboard(habit_id=habit_id, page=page, is_done_today=is_done)

        await message.answer(text, reply_markup=keyboard)

    except APIClientError:
        await message.answer("❌ Ошибка при сохранении.")
    finally:
        # В любом случае (успех или ошибка) сбрасываем состояние FSM
        # Чтобы пользователь не "застрял" в диалоге
        await state.clear()

# --- Открытие меню редактирования ---
@router.callback_query(HabitActionCallback.filter(F.action == HabitAction.OPEN_EDIT_MENU))
async def open_edit_menu(
        callback: CallbackQuery, callback_data: HabitActionCallback
) -> None:
    """
    Показывает меню выбора поля для редактирования.

    Args:
        callback (CallbackQuery): Объект колбэка от кнопки 'Редактировать'.
        callback_data (HabitActionCallback): Данные с ID привычки.
    """
    await callback.message.edit_text(
        "✏️ <b>Редактирование привычки</b>\n\nЧто вы хотите изменить?",
        reply_markup=get_habit_edit_menu_keyboard(habit_id=callback_data.habit_id, page=callback_data.page)
    )


# --- Начало редактирования конкретного поля (Роутинг по кнопкам) ---
@router.callback_query(HabitActionCallback.filter(F.action.in_({
    HabitAction.EDIT_NAME, HabitAction.EDIT_DESC, HabitAction.EDIT_TIME, HabitAction.EDIT_DAYS
})))
async def start_editing_field(
        callback: CallbackQuery,
        callback_data: HabitActionCallback,
        state: FSMContext
) -> None:
    """
    Запускает процесс редактирования конкретного поля привычки.

    Args:
        callback (CallbackQuery): Объект колбэка.
        callback_data (HabitActionCallback): Данные с ID привычки.
        state (FSMContext): Контекст машины состояний.
    """

    # Сохраняем контекст (ID привычки и страницу списка), чтобы потом вернуться
    await state.update_data(habit_id=callback_data.habit_id, page=callback_data.page)

    # Получаем действие из данных колбэка
    action = callback_data.action

    # Словарь для переключений состояний - dict[Action, tuple[text, new_state]]
    prompts = {
        HabitAction.EDIT_NAME: (
            "Введите новое <b>название</b> привычки:",
            HabitEditing.waiting_for_new_name
        ),
        HabitAction.EDIT_DESC: (
            "Введите новое <b>описание</b> (или /empty для удаления существующего):",
            HabitEditing.waiting_for_new_description
        ),
        HabitAction.EDIT_DAYS: (
            "Введите новую <b>цель</b> (количество дней):",
            HabitEditing.waiting_for_new_target_days
        ),
        HabitAction.EDIT_TIME: (
            "Введите новое <b>время</b> напоминания (ЧЧ:ММ):",
            HabitEditing.waiting_for_new_time
        ),
    }

    # Ищем действие в словаре
    if action in prompts:
        # Распаковываем кортеж
        text, new_state = prompts[action]
    else:
        return

    # Переводим бота в новое состояние
    await state.set_state(new_state)

    # Приглашаем пользователя ко вводу
    await callback.message.edit_text(text)

    await callback.answer()


# --- Обработка ввода нового названия ---
@router.message(HabitEditing.waiting_for_new_name)
async def process_habit_new_name(message: Message, state: FSMContext, api_client: HabitTrackerClient) -> None:
    """
    Принимает новое название привычки.

    Args:
        message (Message): Объект сообщения Telegram.
        state (FSMContext): Контекст машины состояний.
        api_client (HabitTrackerClient): Клиент API.
    """

    if not message.text:
        await message.answer("⚠️ Пожалуйста, отправьте текстовое сообщение с названием привычки.")
        return

    habit_new_name = message.text.strip()

    # Простая валидация длины
    if len(habit_new_name) > 100:
        await message.answer("⚠️ Название привычки слишком длинное. Пожалуйста, сократите до 100 символов.")
        return

    await _save_habit_change(
        message=message,
        state=state,
        api_client=api_client,
        name=habit_new_name,
    )


# --- Обработка ввода нового описания ---
@router.message(HabitEditing.waiting_for_new_description)
async def process_habit_new_description(message: Message, state: FSMContext, api_client: HabitTrackerClient) -> None:
    """
    Принимает новое описание привычки.

    Поддерживает команду /empty для удаления существующего описания привычки (description будет None).

    Args:
        message (Message): Объект сообщения Telegram.
        state (FSMContext): Контекст машины состояний.
        api_client (HabitTrackerClient): Клиент API.
    """

    if not message.text:
        await message.answer("⚠️ Пожалуйста, отправьте текст или введите /empty.")
        return

    habit_new_description = message.text.strip()

    # Логика удаления существующего описания (если команда /empty)
    if habit_new_description == "/empty":
        habit_new_description = None

    await _save_habit_change(
        message=message,
        state=state,
        api_client=api_client,
        description=habit_new_description,
    )


# --- Обработка ввода новой цели (количества дней) ---
@router.message(HabitEditing.waiting_for_new_target_days)
async def process_habit_new_target_days(message: Message, state: FSMContext, api_client: HabitTrackerClient) -> None:
    """
    Принимает новую цель (количество дней) для формирования привычки.

    Валидирует ввод (должен быть натуральным числом).

    Args:
        message (Message): Объект сообщения Telegram.
        state (FSMContext): Контекст машины состояний.
        api_client (HabitTrackerClient): Клиент API.
    """
    answer_text = "⚠️ Пожалуйста, введите натуральное число (от 1 и более)."

    if not message.text:
        await message.answer(answer_text)
        return

    text = message.text.strip()

    # Простая валидация на натуральное число
    if not text.isdigit() or int(text) < 1:
        await message.answer(answer_text)
        return

    habit_new_target_days = int(text)

    await _save_habit_change(
        message=message,
        state=state,
        api_client=api_client,
        target_days=habit_new_target_days,
    )


# --- Обработка ввода нового времени оповещения ---
@router.message(HabitEditing.waiting_for_new_time)
async def process_habit_new_time(message: Message, state: FSMContext, api_client: HabitTrackerClient) -> None:
    """
    Принимает новое время оповещения.

    Валидирует ввод через регулярное выражение.

    Args:
        message (Message): Объект сообщения Telegram.
        state (FSMContext): Контекст машины состояний.
        api_client (HabitTrackerClient): Клиент API.
    """
    if not message.text:
        await message.answer("⚠️ Введите время текстом в формате ЧЧ:ММ.")
        return

    new_time_to_remind_str = message.text.strip()

    # Если пользователь ввел Ч:ММ, дополним до ЧЧ:ММ
    if len(new_time_to_remind_str) == 4 and new_time_to_remind_str[1] == ":":
        new_time_to_remind_str = "0" + new_time_to_remind_str

    # Валидация формата времени через регулярное выражение
    # ^([0-1]?[0-9]|2[0-3]) - часы от 00 до 23
    # :[0-5][0-9]$ - минуты от 00 до 59
    time_pattern = r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"

    if not match(time_pattern, new_time_to_remind_str):
        await message.answer(
            "⚠️ <b>Неверный формат времени.</b>\n\n"
            "Пожалуйста, введи время в формате ЧЧ:ММ (24-часовой формат).\n"
            "Пример: <code>07:30</code>"
        )
        return

    await _save_habit_change(
        message=message,
        state=state,
        api_client=api_client,
        time_to_remind=new_time_to_remind_str,
    )

