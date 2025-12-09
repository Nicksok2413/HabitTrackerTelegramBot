"""
Обработчики раздела "Профиль".
"""

from contextlib import suppress
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.core.enums import ProfileAction
from src.bot.keyboards.callbacks import ProfileActionCallback
from src.bot.keyboards.inline import get_profile_keyboard
from src.bot.keyboards.reply import BTN_PROFILE, get_main_menu_keyboard
from src.bot.services.api_client import APIClientError, HabitTrackerClient
from src.bot.states.profile_states import ProfileEdit
from src.core_shared.logging_setup import setup_logger

# Настраиваем логгер
log = setup_logger("BotProfileHandlers")

# Создаем роутер
router = Router(name="profile_handlers")


@router.message(F.text == BTN_PROFILE)
async def show_profile(message: Message, api_client: HabitTrackerClient) -> None:
    """
    Отображает профиль пользователя: ID, дату регистрации и текущий часовой пояс.

    Args:
        message (Message): Объект сообщения Telegram.
        api_client (HabitTrackerClient): Клиент API.
    """
    if not message.from_user:
        return

    # Индикатор загрузки
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")  # type: ignore

    try:
        # Получаем данные пользователя из API
        user_data = await api_client.get_me(message.from_user)

        # Формируем красивый ответ
        first_name = f"<i>{user_data['first_name']}</i>" if user_data.get("first_name") else "🤷🏻‍♂️"
        last_name = f"<i>{user_data['last_name']}</i>" if user_data.get("last_name") else "🤷🏻‍♂️"
        timezone = user_data.get("timezone", "UTC")

        text = (
            f"👤 <b>Ваш профиль</b>\n\n"
            f"🆔 Telegram ID: <code>{user_data['telegram_id']}</code>\n"
            f"🪪 Имя: <b>{first_name}</b>\n"
            f"🪪 Фамилия: <b>{last_name}</b>\n"
            f"🌍 Часовой пояс: <b>{timezone}</b>\n\n"
            f"<i>Напоминания приходят в соответствии с вашим часовым поясом.</i>"
        )

        await message.answer(text, reply_markup=get_profile_keyboard())

    except APIClientError:
        await message.answer("❌ Не удалось загрузить профиль. Попробуйте позже.")


@router.callback_query(ProfileActionCallback.filter(F.action == ProfileAction.CHANGE_TIMEZONE))
async def start_timezone_change(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Начало процесса смены часового пояса (нажатие на кнопку).

    Args:
        callback (CallbackQuery): Объект колбэка от кнопки 'Изменить часовой пояс'.
        state (FSMContext): Контекст машины состояний.
    """
    # Всегда отвечаем на callback, чтобы убрать часики загрузки у кнопки
    await callback.answer()

    if not callback.message:
        return

    await callback.message.answer(
        "🌍 <b>Настройка часового пояса</b>\n\n"
        "Введите название вашего часового пояса в формате IANA.\n"
        "Примеры:\n"
        "• <code>Europe/Moscow</code>\n"
        "• <code>Asia/Yekaterinburg</code>\n"
        "• <code>Europe/Minsk</code>\n"
        "• <code>UTC</code>\n\n"
        "<i>Вы можете найти свой пояс в настройках даты и времени телефона или в Google.</i>"
    )

    # Устанавливаем состояние ожидания ввода таймзоны
    await state.set_state(ProfileEdit.waiting_for_timezone)


@router.message(ProfileEdit.waiting_for_timezone)
async def process_timezone_input(message: Message, state: FSMContext, api_client: HabitTrackerClient) -> None:
    """
    Обработка введенного текста часового пояса.

    Args:
        message (Message): Объект сообщения Telegram.
        state (FSMContext): Контекст машины состояний.
        api_client (HabitTrackerClient): Клиент API.
    """
    if not message.text:
        await message.answer("⚠️ Пожалуйста, отправьте название часового пояса текстом.")
        return

    new_timezone = message.text.strip()

    # Валидация: проверяем, существует ли такая таймзона
    try:
        ZoneInfo(new_timezone)

    except ZoneInfoNotFoundError:
        await message.answer(
            "⚠️ <b>Некорректный часовой пояс.</b>\n\n"
            "Проверьте правильность написания (регистр важен для некоторых систем, но обычно нет).\n"
            "Попробуйте <code>Europe/Moscow</code> или <code>UTC</code>.\n"
            "Попробуйте еще раз или нажмите /cancel."
        )
        return

    if not message.from_user:
        return

    # Если валидация прошла, начинаем процесс сохранения
    processing_msg = await message.answer("⏳ Сохраняю настройки...")

    try:
        # Отправляем запрос к API
        await api_client.update_users_timezone(message.from_user, timezone=new_timezone)

        await message.answer(
            f"✅ Часовой пояс успешно изменен на <b>{new_timezone}</b>.\nНапоминания будут приходить вовремя!",
            reply_markup=get_main_menu_keyboard(),  # Возвращаем главное меню
        )
        log.info(f"Часовой пояс успешно изменен на {new_timezone} для пользователя {message.from_user.id}.")

    except APIClientError as exc:
        log.error(f"Ошибка при обновлении профиля для {message.from_user.id}: {exc}")
        await message.answer(
            "❌ Ошибка при обновлении профиля на сервере. Попробуйте позже.", reply_markup=get_profile_keyboard()
        )

    finally:
        # Удаляем сообщение "Сохраняю...", если оно еще есть
        with suppress(Exception):
            await processing_msg.delete()

        # В любом случае (успех или ошибка) сбрасываем состояние FSM
        # Чтобы пользователь не "застрял" в диалоге
        await state.clear()
