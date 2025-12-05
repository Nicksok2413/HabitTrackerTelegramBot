"""
Обработчики сценариев работы с привычками.

Включает в себя:
- FSM для создания новой привычки: название -> описание -> цель -> время напоминания -> Сохранение в API.
- Просмотр списка привычек (Pagination).
- Просмотр деталей привычки.
- Отметку выполнения/отмены выполнения привычки.
- Удаление привычки.
"""

from contextlib import suppress
from datetime import date
from re import match

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove, User as TelegramUser

from src.core_shared.logging_setup import setup_logger
from src.bot.keyboards.callbacks import HabitActionCallback, HabitDetailCallback, HabitsNavigationCallback
from src.bot.keyboards.inline import (
    get_habit_delete_confirmation_keyboard,
    get_habit_detail_keyboard,
    get_habits_list_keyboard,
)
from src.bot.keyboards.reply import BTN_CREATE_HABIT, BTN_MY_HABITS, get_main_menu_keyboard
from src.bot.services.api_client import APIClientError, HabitTrackerClient
from src.bot.states.habit_states import HabitCreation

# Настраиваем логгер
log = setup_logger("BotHabitHandlers")

# Создаем роутер
router = Router(name="habit_handlers")

# Константа размера страницы для списка привычек
PAGE_SIZE = 5


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
    Вспомогательная функция для отображения страницы списка привычек.

    Используется как при первом вызове (отправка сообщения), так и при пагинации (редактирование).

    Args:
        message_or_callback (Message | CallbackQuery): Объект входящего события (Message или CallbackQuery).
        tg_user (TelegramUser): Пользователь Telegram.
        api_client (HabitTrackerClient): Клиент API.
        page (int): Номер страницы.
        is_edit (bool): Флаг режима редактирования.
                        Если True - редактируем существующее сообщение (для пагинации).
                        Если False - отправляем новое сообщение.
    """
    # Запрашиваем на 1 элемент больше, чтобы узнать, есть ли следующая страница
    limit = PAGE_SIZE + 1
    skip = page * PAGE_SIZE

    # # Определяем объект User (зависит от типа входящего события)
    # tg_user = message_or_callback.from_user

    try:
        habits = await api_client.get_my_habits(
            tg_user=tg_user,  # type: ignore
            skip=skip,
            limit=limit,
        )
    except APIClientError:
        text = "Не удалось загрузить список привычек."

        if is_edit and isinstance(message_or_callback, CallbackQuery):
            with suppress(Exception):
                await message_or_callback.answer(text, show_alert=True)
        else:
            if isinstance(message_or_callback, Message):
                await message_or_callback.answer(text)

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
        keyboard = get_habits_list_keyboard(habits_to_show, page, has_next)

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
    await _render_habits_page(
        message_or_callback=message, tg_user=message.from_user, api_client=api_client, page=0, is_edit=False
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

    if not callback.message:
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


def _is_done_today(habit_details: dict) -> bool:
    """
    Проверяет, есть ли в истории выполнений запись за сегодня со статусом 'done'.

    Args:
        habit_details: Словарь с данными привычки, включая ключ 'executions'.

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


async def _render_habit_details(
    callback: CallbackQuery,
    habit_id: int,
    page: int,
    api_client: HabitTrackerClient,
) -> None:
    """
    Вспомогательная функция для отрисовки карточки детализации привычки.

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

    if not callback.message:
        return

    try:
        # Получаем полные детали привычки (с выполнениями)
        habit = await api_client.get_habit_details(tg_user=callback.from_user, habit_id=habit_id)

        # Определяем статус на сегодня
        is_done = _is_done_today(habit)
        status_text = "✅ <b>Выполнено сегодня</b>" if is_done else "⏳ <b>Ждет выполнения</b>"

        # Формируем красивый текст
        habit_description_text = f"\n<i>{habit['description']}</i>" if habit.get("description") else ""
        formatted_time = habit["time_to_remind"][:5]  # API возвращает "ЧЧ:ММ:СС", берем первые 5 символов "ЧЧ:ММ"

        text = (
            f"📝 <b>{habit['name']}</b>\n"
            f"{habit_description_text}\n\n"
            f"🔥 Стрик: <b>{habit['current_streak']} дн.</b> (Рекорд: {habit['max_streak']})\n"
            f"⏰ Напоминание: {formatted_time}\n"
            f"📅 Цель: {habit['target_days']} дн.\n"
            f"──────────────────\n"
            f"{status_text}"
        )

        # Клавиатура с кнопками действий (выполнить, отменить выполнение, удалить и назад)
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
            await callback.answer("Не удалось загрузить данные о привычке.", show_alert=True)


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
        callback=callback, habit_id=callback_data.habit_id, page=callback_data.page, api_client=api_client
    )


@router.callback_query(HabitActionCallback.filter(F.action == "view"))  # type: ignore
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
        callback=callback, habit_id=callback_data.habit_id, page=callback_data.page, api_client=api_client
    )


# --- Логика выполнения / отмены выполнения привычки ---


@router.callback_query(HabitActionCallback.filter(F.action.in_({"done", "set_pending"})))
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
    target_status = "done" if callback_data.action == "done" else "pending"

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
            await callback.answer("Ошибка при обновлении статуса привычки.", show_alert=True)


# --- Логика удаления привычки ---


@router.callback_query(HabitActionCallback.filter(F.action == "request_delete"))  # type: ignore
async def request_habit_delete(callback: CallbackQuery, callback_data: HabitActionCallback) -> None:
    """
    Запрашивает подтверждение удаления привычки.

    Args:
        callback (CallbackQuery): Объект колбэка от кнопки 'Удалить'.
        callback_data (HabitActionCallback): Данные с ID привычки.
    """
    # Всегда отвечаем на callback, чтобы убрать часики загрузки у кнопки
    await callback.answer()

    if not callback.message:
        return

    keyboard = get_habit_delete_confirmation_keyboard(habit_id=callback_data.habit_id, page=callback_data.page)

    await callback.message.edit_text(
        "⚠️ <b>Вы действительно хотите удалить эту привычку?</b>\n\n"
        "Это действие нельзя будет отменить. Вся история выполнений будет потеряна.",
        reply_markup=keyboard,
    )


@router.callback_query(HabitActionCallback.filter(F.action == "confirm_delete"))  # type: ignore
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
            await callback.answer("Не удалось удалить привычку. Попробуйте позже.", show_alert=True)
        # Если ошибка, возвращаем пользователя к просмотру привычки
        await _render_habit_details(
            callback=callback, habit_id=callback_data.habit_id, page=callback_data.page, api_client=api_client
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

    habit_description = message.text.strip()

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
        if not text.isdigit():
            await message.answer(answer_text)
            return

        habit_target_days = int(text)

        if habit_target_days < 1:
            await message.answer(answer_text)
            return

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
        api_client (HabitTrackerClient): Инъекция клиента API.
    """
    if not message.text:
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

    # Сообщаем пользователю, что процесс идет
    processing_msg = await message.answer("⏳ Сохраняю привычку...")

    try:
        # Отправляем запрос к Backend API
        new_habit = await api_client.create_habit(
            tg_user=message.from_user,  # type: ignore
            name=habit_name,
            description=habit_description,
            time_to_remind=time_to_remind_str,
            target_days=habit_target_days,
        )

        # Удаляем сообщение "Сохраняю..."
        await processing_msg.delete()

        # Формируем красивый ответ
        habit_description_text = f"\n<i>{new_habit['description']}</i>" if new_habit.get("description") else ""
        formatted_time = new_habit["time_to_remind"][:5]  # API возвращает "ЧЧ:ММ:СС", берем первые 5 символов "ЧЧ:ММ"

        await message.answer(
            f"🎉 <b>Привычка успешно создана!</b>\n\n"
            f"📌 <b>{new_habit['name']}</b>{habit_description_text}\n"
            f"⏰ Напоминание в: <b>{formatted_time}</b>\n"
            f"📅 Цель: <b>{new_habit['target_days']} дн.</b>\n\n"
            f"Удачи в достижении цели! 💪",
            reply_markup=get_main_menu_keyboard(),  # Возвращаем главное меню
        )
        log.info(f"Привычка '{habit_name}' создана для пользователя {message.from_user.id}.")

    except APIClientError as exc:
        await processing_msg.delete()
        log.error(f"Ошибка при сохранении привычки для {message.from_user.id}: {exc}")

        await message.answer(
            "😔 <b>Произошла ошибка при сохранении.</b>\nПожалуйста, попробуйте еще раз позже.",
            reply_markup=get_main_menu_keyboard(),
        )
    finally:
        # В любом случае (успех или ошибка) сбрасываем состояние FSM
        # Чтобы пользователь не "застрял" в диалоге
        await state.clear()
