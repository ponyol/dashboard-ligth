"""Промежуточное ПО (middleware) для обработки HTTP запросов."""

import logging
import time
from typing import Callable

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware для логирования запросов и ответов."""

    async def dispatch(self, request: Request, call_next: Callable):
        """Обработка запроса с логированием.

        Args:
            request: HTTP запрос
            call_next: Следующий обработчик в цепочке

        Returns:
            Ответ от следующего обработчика
        """
        start_time = time.time()

        # Логирование запроса
        logger.debug(f"Request: {request.method} {request.url.path}")

        # Вызов следующего обработчика
        try:
            response = await call_next(request)
            process_time = time.time() - start_time

            # Логирование ответа
            logger.debug(
                f"Response: {request.method} {request.url.path} - Status: {response.status_code} "
                f"- Time: {process_time:.3f}s"
            )

            # Добавление заголовка с временем обработки
            response.headers["X-Process-Time"] = str(process_time)

            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"Error processing request: {request.method} {request.url.path} - "
                f"Error: {str(e)} - Time: {process_time:.3f}s"
            )
            raise


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware для проверки аутентификации."""

    async def dispatch(self, request: Request, call_next: Callable):
        """Обработка запроса с проверкой аутентификации.

        Args:
            request: HTTP запрос
            call_next: Следующий обработчик в цепочке

        Returns:
            Ответ от следующего обработчика
        """
        # Проверка, отключена ли аутентификация в режиме разработки
        auth_disabled = request.app.state.config.get("auth", {}).get("disable_auth", False)

        # Пути, которые не требуют аутентификации
        public_paths = [
            "/api/health",
            "/api/auth/login",
            "/api/auth/callback",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]

        # Проверка, нужна ли аутентификация для этого пути
        is_public_path = any(
            request.url.path.startswith(path) for path in public_paths
        )

        # Если аутентификация отключена или путь публичный, пропускаем проверку
        if auth_disabled or is_public_path:
            return await call_next(request)

        # Проверка аутентификации пользователя
        session = request.session
        user = session.get("user")

        if not user:
            # Проверка анонимного доступа
            allow_anonymous = request.app.state.config.get("auth", {}).get("allow_anonymous_access", False)

            if not allow_anonymous:
                # Если анонимный доступ отключен и пользователь не аутентифицирован,
                # перенаправляем на страницу входа или возвращаем ошибку 401
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Not authenticated"}
                )

        # Если проверка пройдена, вызываем следующий обработчик
        return await call_next(request)


def add_middlewares(app: FastAPI) -> None:
    """Добавление всех необходимых middleware к приложению.

    Args:
        app: FastAPI приложение
    """
    # Добавление middleware для логирования
    app.add_middleware(LoggingMiddleware)

    # Добавление middleware для аутентификации
    # app.add_middleware(AuthenticationMiddleware)
    # Пока отключим, т.к. нужно сначала реализовать сессии
