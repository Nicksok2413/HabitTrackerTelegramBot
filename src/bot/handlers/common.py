"""
Обработчики общих команд бота (/start, /help, /cancel).

Эти обработчики доступны из любого состояния и служат точками входа или выхода из сценариев.
"""

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot.keyboards.reply import get_main_menu_keyboard
from src.bot.services.api_client import APIClientError, HabitTrackerClient
from src.core_shared.logging_setup import setup_logger

# Настраиваем логгер
log = setup_logger("BotCommonHandlers")

# Создаем роутер
router = Router(name="common_commands")


@router.message(CommandStart())
async def cmd_start(message: Message, api_client: HabitTrackerClient, state: FSMContext) -> None:
    """
    Обработчик команды /start.

    1. Сбрасывает любое активное состояние FSM.
    2. Регистрирует пользователя в Backend API (неявно, через запрос списка привычек).
    3. Отправляет приветствие и Главное меню.

    Args:
        message (Message): Объект сообщения Telegram.
        api_client (HabitTrackerClient): Инъекция клиента API.
        state (FSMContext): Контекст машины состояний.
    """
    # Гарантированно сбрасываем состояние диалога при рестарте
    await state.clear()

    if not message.from_user:
        return

    # Отправляем действие "печатает...", чтобы показать реакцию бота (так как запрос к API может занять время)
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")  # type: ignore

    try:
        # Делаем пробный запрос к API, чтобы зарегистрировать пользователя
        # Не важен результат, важен факт успешной авторизации
        await api_client.get_my_habits(message.from_user, limit=1)

        await message.answer(
            f"Привет, <b>{message.from_user.first_name}</b>! 👋\n\n"
            f"Я твой бот-трекер привычек. Я помогу тебе внедрить полезные ритуалы в твою жизнь.\n\n"
            f"👇 <b>Выберите действие в меню ниже:</b>",
            reply_markup=get_main_menu_keyboard(),
        )
        log.info(f"Пользователь {message.from_user.id} запустил бота (/start).")

    except APIClientError:
        log.error(f"Ошибка инициализации пользователя {message.from_user.id} в API.")
        await message.answer(
            "😔 <b>Проблема с соединением.</b>\n\n"
            "К сожалению, сервер сейчас недоступен. Попробуйте нажать /start через пару минут."
        )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """
    Команда отмены текущего действия (/cancel).

    Сбрасывает текущее состояние FSM и возвращает пользователя в главное меню.

    Args:
        message (Message): Объект сообщения Telegram.
        state (FSMContext): Контекст машины состояний.
    """

    # Получаем текущее состояние
    current_state = await state.get_state()

    # Если состояния нет, выводим информативное сообщение и клавиатуру главного меню
    if current_state is None:
        await message.answer("Нет активных действий для отмены.", reply_markup=get_main_menu_keyboard())
        return

    # Сбрасываем состояние и очищаем данные формы
    await state.clear()

    log.info(f"Пользователь {message.from_user.id} отменил действие (было состояние: {current_state}).")

    await message.answer("❌ Действие отменено.\nВозвращаюсь в главное меню.", reply_markup=get_main_menu_keyboard())
