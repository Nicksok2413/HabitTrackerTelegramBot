"""Основной API роутер, объединяющий все остальные роутеры."""

from fastapi import APIRouter

# from . import auth, users, habits, habit_executions

# Основной роутер API, объединяющий все остальные
api_router = APIRouter(prefix="/v1")  # Префикс /v1 для всех API эндпоинтов

# api_router.include_router(auth.router)
# api_router.include_router(users.router)
# api_router.include_router(habits.router)
# api_router.include_router(habit_executions.router)

__all__ = ["api_router"]
