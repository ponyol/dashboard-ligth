"""Маршруты для аутентификации и авторизации."""

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from dashboard_light.web.models import UserInfo

logger = logging.getLogger(__name__)


def create_auth_router(app_config: Dict[str, Any]) -> APIRouter:
    """Создание роутера для аутентификации.

    Args:
        app_config: Конфигурация приложения

    Returns:
        APIRouter: Роутер с маршрутами для аутентификации
    """
    router = APIRouter(prefix="/auth", tags=["Authentication"])

    # Получение настроек аутентификации из конфигурации
    auth_config = app_config.get("auth", {})

    # Функция для проверки, отключена ли аутентификация
    def is_auth_disabled() -> bool:
        """Проверка, отключена ли аутентификация в режиме разработки."""
        return os.environ.get("DISABLE_AUTH", "false").lower() == "true"

    # Тестовый пользователь для режима разработки
    DEV_USER = {
        "id": 1,
        "username": "dev-user",
        "name": "Developer",
        "email": "dev@example.com",
        "roles": ["admin"]
    }

    @router.get("/login")
    async def login(request: Request):
        """Начало процесса аутентификации с перенаправлением на GitLab."""
        # Проверка, отключена ли аутентификация
        if is_auth_disabled():
            # В режиме разработки сразу авторизуем как тестового пользователя
            request.session["user"] = DEV_USER
            return RedirectResponse(url="/")

        # В противном случае перенаправляем на GitLab OAuth
        # TODO: Реализовать перенаправление на GitLab OAuth
        return {"message": "Redirect to GitLab OAuth - Not implemented yet"}

    @router.get("/callback")
    async def callback(request: Request, code: Optional[str] = None):
        """Обработка callback от GitLab OAuth."""
        # Проверка, отключена ли аутентификация
        if is_auth_disabled():
            request.session["user"] = DEV_USER
            return RedirectResponse(url="/")

        # Проверка наличия кода аутентификации
        if not code:
            raise HTTPException(status_code=400, detail="Invalid code")

        # TODO: Реализовать обмен кода на токен и получение информации о пользователе
        return {"message": "GitLab OAuth callback - Not implemented yet"}

    @router.get("/logout")
    async def logout(request: Request, response: Response):
        """Выход из системы."""
        # Очистка сессии
        request.session.clear()
        return RedirectResponse(url="/")

    @router.get("/user", response_model=UserInfo)
    async def current_user(request: Request):
        """Получение информации о текущем пользователе."""
        # Получение пользователя из сессии
        user = request.session.get("user")

        # Если пользователь не аутентифицирован
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")

        return user

    return router
