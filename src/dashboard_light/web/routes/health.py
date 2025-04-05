"""Маршруты для проверки состояния здоровья приложения."""

import logging
from typing import Any, Dict

from fastapi import APIRouter

from dashboard_light import __version__
from dashboard_light.web.models import HealthResponse

logger = logging.getLogger(__name__)


def create_health_router(app_config: Dict[str, Any]) -> APIRouter:
    """Создание роутера для проверки состояния здоровья.

    Args:
        app_config: Конфигурация приложения

    Returns:
        APIRouter: Роутер с маршрутами для проверки состояния здоровья
    """
    router = APIRouter(tags=["Health"])

    @router.get("/health", response_model=HealthResponse)
    async def health_check():
        """Проверка состояния здоровья приложения."""
        return {
            "status": "ok",
            "version": __version__,
            "kubernetes_connected": True,  # В реальном сценарии здесь будет проверка соединения
        }

    return router
