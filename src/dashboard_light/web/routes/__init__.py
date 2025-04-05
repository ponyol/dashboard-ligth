"""Модуль с маршрутами API."""

from typing import Any, Dict

from fastapi import APIRouter

from dashboard_light.web.routes.auth import create_auth_router
from dashboard_light.web.routes.health import create_health_router
from dashboard_light.web.routes.k8s import create_k8s_router


def create_router(app_config: Dict[str, Any], k8s_client: Dict[str, Any]) -> APIRouter:
    """Создание основного роутера с подключением всех дочерних роутеров.

    Args:
        app_config: Конфигурация приложения
        k8s_client: Словарь с Kubernetes клиентом и API

    Returns:
        APIRouter: Основной роутер с подключенными дочерними роутерами
    """
    main_router = APIRouter(prefix="/api")

    # Добавление дочерних роутеров
    main_router.include_router(create_health_router(app_config))
    main_router.include_router(create_auth_router(app_config))
    main_router.include_router(create_k8s_router(app_config, k8s_client))

    return main_router
