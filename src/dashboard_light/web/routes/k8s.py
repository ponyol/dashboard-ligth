"""Маршруты для работы с Kubernetes API."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from dashboard_light.k8s import deployments, namespaces, pods, metrics
from dashboard_light.k8s.cache import invalidate_all as invalidate_k8s_cache
from dashboard_light.web.models import (
    DeploymentInfo,
    DeploymentList,
    NamespaceInfo,
    NamespaceList,
    PodInfo,
    PodList
)

logger = logging.getLogger(__name__)


def create_k8s_router(app_config: Dict[str, Any], k8s_client: Dict[str, Any]) -> APIRouter:
    """Создание роутера для работы с Kubernetes API.

    Args:
        app_config: Конфигурация приложения
        k8s_client: Словарь с Kubernetes клиентом и API

    Returns:
        APIRouter: Роутер с маршрутами для работы с Kubernetes API
    """
    router = APIRouter(prefix="/k8s", tags=["Kubernetes"])

    # Функция для фильтрации неймспейсов по правам доступа пользователя
    async def filter_namespaces_by_access(request: Request, namespaces_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Фильтрация неймспейсов по правам доступа пользователя.

        Args:
            request: HTTP запрос
            namespaces_data: Список данных о неймспейсах

        Returns:
            List[Dict[str, Any]]: Отфильтрованный список данных о неймспейсах
        """
        # Получение пользователя из сессии
        user = request.session.get("user")

        # Если пользователь не аутентифицирован, предоставляем доступ только к неймспейсам для анонимных
        if not user:
            # Проверка настройки анонимного доступа
            auth_config = app_config.get("auth", {})
            allow_anonymous = auth_config.get("allow_anonymous_access", False)

            if not allow_anonymous:
                return []

            # Использование роли по умолчанию для анонимных пользователей
            anonymous_role = auth_config.get("anonymous_role")
            if not anonymous_role:
                return []

            # Получение разрешенных неймспейсов для роли анонимного пользователя
            permissions = auth_config.get("permissions", {}).get(anonymous_role, {})
            allowed_patterns = permissions.get("allowed_namespace_patterns", [])

            # Фильтрация неймспейсов по разрешенным шаблонам
            return namespaces.filter_namespaces_by_pattern(namespaces_data, allowed_patterns)

        # Для аутентифицированных пользователей фильтруем по их правам
        # TODO: Реализовать RBAC для фильтрации неймспейсов

        # Пока возвращаем все неймспейсы (для отладки)
        return namespaces_data

    @router.get("/namespaces", response_model=NamespaceList)
    async def list_namespaces(request: Request):
        """Получение списка доступных неймспейсов с учётом RBAC."""
        try:
            # Получение списка неймспейсов
            all_namespaces = namespaces.list_namespaces(k8s_client)

            # Фильтрация неймспейсов по правам доступа
            allowed_namespaces = await filter_namespaces_by_access(request, all_namespaces)

            return {"items": allowed_namespaces}
        except Exception as e:
            logger.error(f"Ошибка при получении списка неймспейсов: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ошибка при получении списка неймспейсов: {str(e)}")

    @router.get("/deployments", response_model=DeploymentList)
    async def list_deployments(
        request: Request,
        namespace: Optional[str] = None,
        cluster: Optional[str] = None
    ):
        """Получение списка Deployments с учетом фильтров."""
        try:
            if namespace:
                # Если указан конкретный неймспейс
                all_deployments = deployments.list_deployments_for_namespace(k8s_client, namespace)
                # Добавляем статус каждому деплойменту
                for deployment in all_deployments:
                    deployment["status"] = deployments.get_deployment_status(deployment)

                return {"items": all_deployments}
            else:
                # Если неймспейс не указан, получаем список всех неймспейсов
                all_namespaces = namespaces.list_namespaces(k8s_client)

                # Фильтрация неймспейсов по правам доступа
                allowed_namespaces = await filter_namespaces_by_access(request, all_namespaces)

                # Получение списка деплойментов для всех доступных неймспейсов
                ns_names = [ns.get("name") for ns in allowed_namespaces]
                all_deployments = deployments.list_deployments_multi_ns(k8s_client, ns_names)

                # Добавляем статус каждому деплойменту
                for deployment in all_deployments:
                    deployment["status"] = deployments.get_deployment_status(deployment)

                return {"items": all_deployments}
        except Exception as e:
            logger.error(f"Ошибка при получении списка деплойментов: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ошибка при получении списка деплойментов: {str(e)}")

    @router.get("/deployments/{namespace}/{name}", response_model=DeploymentInfo)
    async def get_deployment(
        request: Request,
        namespace: str,
        name: str
    ):
        """Получение детальной информации о конкретном Deployment."""
        try:
            # Получение списка деплойментов в указанном неймспейсе
            all_deployments = deployments.list_deployments_for_namespace(k8s_client, namespace)

            # Поиск нужного деплоймента
            deployment = next((d for d in all_deployments if d.get("name") == name), None)

            if not deployment:
                raise HTTPException(status_code=404, detail=f"Deployment {name} не найден в неймспейсе {namespace}")

            # Добавляем статус деплойменту
            deployment["status"] = deployments.get_deployment_status(deployment)

            # Получение подов, связанных с деплойментом
            deployment_pods = pods.list_deployment_pods(k8s_client, namespace, name)

            # Получение метрик для каждого пода
            pod_metrics = []
            for pod in deployment_pods:
                pod_name = pod.get("name")
                pod_metrics_data = metrics.get_pod_metrics_by_name(k8s_client, namespace, pod_name)
                pod["metrics"] = pod_metrics_data
                pod_metrics.append(pod)

            # Добавляем поды к деплойменту
            deployment["pods"] = pod_metrics

            return deployment
        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Ошибка при получении деплоймента: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ошибка при получении деплоймента: {str(e)}")

    @router.get("/pods", response_model=PodList)
    async def list_pods(
        request: Request,
        namespace: Optional[str] = None,
        label_selector: Optional[str] = None
    ):
        """Получение списка Pods с учетом фильтров."""
        try:
            if namespace:
                # Если указан конкретный неймспейс
                all_pods = pods.list_pods_for_namespace(k8s_client, namespace, label_selector)
                return {"items": all_pods}
            else:
                # Если неймспейс не указан, получаем список всех неймспейсов
                all_namespaces = namespaces.list_namespaces(k8s_client)

                # Фильтрация неймспейсов по правам доступа
                allowed_namespaces = await filter_namespaces_by_access(request, all_namespaces)

                # Получение списка подов для всех доступных неймспейсов
                ns_names = [ns.get("name") for ns in allowed_namespaces]
                all_pods = []
                for ns in ns_names:
                    ns_pods = pods.list_pods_for_namespace(k8s_client, ns, label_selector)
                    all_pods.extend(ns_pods)

                return {"items": all_pods}
        except Exception as e:
            logger.error(f"Ошибка при получении списка подов: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ошибка при получении списка подов: {str(e)}")

    @router.get("/pods/{namespace}/{name}", response_model=PodInfo)
    async def get_pod(
        request: Request,
        namespace: str,
        name: str
    ):
        """Получение детальной информации о конкретном Pod."""
        try:
            # Получение списка подов в указанном неймспейсе
            all_pods = pods.list_pods_for_namespace(k8s_client, namespace)

            # Поиск нужного пода
            pod = next((p for p in all_pods if p.get("name") == name), None)

            if not pod:
                raise HTTPException(status_code=404, detail=f"Pod {name} не найден в неймспейсе {namespace}")

            # Получение метрик для пода
            pod_metrics = metrics.get_pod_metrics_by_name(k8s_client, namespace, name)
            pod["metrics"] = pod_metrics

            return pod
        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Ошибка при получении пода: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ошибка при получении пода: {str(e)}")

    @router.post("/cache/clear")
    async def clear_cache():
        """Очистка кэша Kubernetes API."""
        try:
            invalidate_k8s_cache()
            return {"status": "ok", "message": "Кэш успешно очищен"}
        except Exception as e:
            logger.error(f"Ошибка при очистке кэша: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ошибка при очистке кэша: {str(e)}")

    return router
