"""
Обработчики сценариев работы с привычками.

Включает в себя FSM для создания новой привычки:
Ввод названия -> Ввод описания -> Ввод времени напоминания -> Сохранение в API.
"""

import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove

from src.bot.keyboards.reply import BTN_CREATE_HABIT, get_main_menu_keyboard
from src.bot.services.api_client import APIClientError, HabitTrackerClient
from src.bot.states.habit_states import HabitCreation
from src.core_shared.logging_setup import setup_logger

# Настраиваем логгер
log = setup_logger("BotHabitHandlers")

# Создаем роутер
router = Router(name="habit_handlers")


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
        reply_markup=ReplyKeyboardRemove()
    )

    # Переводим бота в состояние ожидания названия
    await state.set_state(HabitCreation.waiting_for_name)


# --- Получение названия ---

@router.message(HabitCreation.waiting_for_name)
async def process_habit_name(message: Message, state: FSMContext) -> None:
    """
    Принимает название привычки.

    Валидирует ввод (должен быть текст) и переходит бота в состояние ожидания описания привычки.

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

    # Переход к следующему состоянию ожидания описания
    await state.set_state(HabitCreation.waiting_for_description)


# --- Получение описания ---

@router.message(HabitCreation.waiting_for_description)
async def process_habit_description(message: Message, state: FSMContext) -> None:
    """
    Принимает описание привычки.

    Поддерживает команду /skip для пропуска шага (description будет None).
    Переходит бота в состояние ожидания времени напоминания.

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
        "⏰ <b>Время напоминания</b>\n\n"
        "В какое время вам напоминать о привычке?\n"
        "Введите время в формате <b>ЧЧ:ММ</b> (24-часовой формат).\n"
        "Примеры: <code>08:00</code>, <code>14:30</code>, <code>22:00</code>."
    )

    # Переход к следующему состоянию ожидания времени напоминания
    await state.set_state(HabitCreation.waiting_for_time)


# --- Получение времени и сохранение ---

@router.message(HabitCreation.waiting_for_time)
async def process_habit_time(
        message: Message,
        state: FSMContext,
        api_client: HabitTrackerClient
) -> None:
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

    # Валидация формата времени через регулярное выражение
    # ^([0-1]?[0-9]|2[0-3]) - часы от 00 до 23
    # :[0-5][0-9]$ - минуты от 00 до 59
    time_pattern = r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"

    if not re.match(time_pattern, time_to_remind_str):
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

    # Сообщаем пользователю, что процесс идет
    processing_msg = await message.answer("⏳ Сохраняю привычку...")

    try:
        # Отправляем запрос к Backend API
        new_habit = await api_client.create_habit(
            tg_user=message.from_user,  # type: ignore
            name=habit_name,
            description=habit_description,
            time_to_remind=time_to_remind_str
        )

        # Удаляем сообщение "Сохраняю..."
        await processing_msg.delete()

        # Формируем красивый ответ
        desc_text = f"\n<i>{new_habit['description']}</i>" if new_habit.get('description') else ""

        await message.answer(
            f"🎉 <b>Привычка успешно создана!</b>\n\n"
            f"📌 <b>{new_habit['name']}</b>{desc_text}\n"
            f"⏰ Напоминание в: <b>{new_habit['time_to_remind']}</b>\n"
            f"📅 Цель: <b>{new_habit['target_days']} дней</b>\n\n"
            f"Удачи в достижении цели! 💪",
            reply_markup=get_main_menu_keyboard()  # Возвращаем главное меню
        )
        log.info(f"Привычка '{habit_name}' создана для пользователя {message.from_user.id}.")

    except APIClientError as exc:
        await processing_msg.delete()
        log.error(f"Ошибка при сохранении привычки для {message.from_user.id}: {exc}")

        await message.answer(
            "😔 <b>Произошла ошибка при сохранении.</b>\n"
            "Пожалуйста, попробуйте еще раз позже.",
            reply_markup=get_main_menu_keyboard()
        )
    finally:
        # В любом случае (успех или ошибка) сбрасываем состояние FSM
        # Чтобы пользователь не "застрял" в диалоге
        await state.clear()