"""
Обработчики общих команд бота (/start, /help, /cancel).
"""

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from src.bot.services.api_client import HabitTrackerClient, APIClientError
from src.core_shared.logging_setup import setup_logger

# Настраиваем логгер
log = setup_logger("BotHandlers")

# Создаем роутер для регистрации хендлеров
router = Router(name="common_commands")


@router.message(CommandStart())
async def cmd_start(message: Message, api_client: HabitTrackerClient, state: FSMContext):
    """
    Обработчик команды /start.

    1. Сбрасывает текущее состояние FSM (если было).
    2. Пытается зарегистрировать пользователя в API (получить список привычек как тест соединения).
    3. Отправляет приветственное сообщение.

    Args:
        message (Message): Объект сообщения от Telegram.
        api_client (HabitTrackerClient): Инъекция зависимости API клиента.
        state (FSMContext): Контекст машины состояний.
    """
    # Сбрасываем состояние диалога, если пользователь был в процессе создания чего-то
    await state.clear()

    if not message.from_user:
        return

    user_name = message.from_user.first_name

    # Отправляем сообщение "печатает...", так как запрос к API может занять время
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")  # type: ignore

    try:
        # Делаем пробный запрос к API, чтобы зарегистрировать пользователя
        # Не важен результат, важен факт успешной авторизации
        await api_client.get_my_habits(message.from_user, limit=1)

        await message.answer(
            f"Привет, <b>{user_name}</b>! 👋\n\n"
            f"Я твой бот-трекер привычек. Я помогу тебе внедрить полезные ритуалы в твою жизнь.\n\n"
            f"Что мы будем делать?",
            # TODO: Здесь позже добавим клавиатуру с главным меню
            # reply_markup=get_main_menu_keyboard()
        )
        log.info(f"Пользователь {message.from_user.id} запустил бота.")

    except APIClientError:
        await message.answer(
            "😔 Извини, сейчас у меня проблемы с подключением к серверу.\n"
            "Попробуй нажать /start через пару минут."
        )
        log.error(f"Не удалось инициализировать пользователя {message.from_user.id} через API.")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """
    Команда отмены текущего действия.
    Сбрасывает состояние FSM.

    Args:
        message (Message): Объект сообщения от Telegram.
        state (FSMContext): Контекст машины состояний.
    """
    current_state = await state.get_state()

    if current_state is None:
        await message.answer("Нет активных действий для отмены.")
        return

    await state.clear()
    await message.answer("Действие отменено. Возвращаюсь в главное меню.")