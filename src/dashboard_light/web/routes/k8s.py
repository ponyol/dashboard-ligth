"""Маршруты для работы с Kubernetes API."""

import logging
from typing import Any, Dict, List, Optional
import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from dashboard_light.k8s import deployments, namespaces, pods, metrics, controllers, statefulsets
from dashboard_light.k8s.cache import invalidate_all as invalidate_k8s_cache
from dashboard_light.web.models import (
    DeploymentInfo,
    DeploymentList,
    NamespaceInfo,
    NamespaceList,
    PodInfo,
    PodList,
    ControllerInfo,
    ControllerList
)

from fastapi import WebSocket, WebSocketDisconnect, BackgroundTasks, Query
from dashboard_light.web.websockets import handle_connection
from dashboard_light.k8s.watch import start_watching, stop_watching, get_active_watches
import asyncio
import websockets.exceptions

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
        """Фильтрация неймспейсов по правам доступа пользователя."""
        # Проверяем, отключена ли аутентификация в режиме разработки
        auth_disabled = os.environ.get("DISABLE_AUTH", "false").lower() in ["true", "1", "yes", "y"]

        # Получаем паттерны фильтрации из конфигурации
        namespace_patterns = app_config.get("default", {}).get("namespace_patterns", [])

        # Если есть паттерны фильтрации в конфиге, применяем их независимо от статуса аутентификации
        if namespace_patterns:
            logger.debug(f"Применяем фильтрацию по паттернам из конфига: {namespace_patterns}")
            return namespaces.filter_namespaces_by_pattern(namespaces_data, namespace_patterns)

        # Если аутентификация отключена, возвращаем все неймспейсы
        if auth_disabled:
            logger.debug("Аутентификация отключена, возвращаем все неймспейсы")
            return namespaces_data

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
        """Получение списка доступных неймспейсов с учётом RBAC.

        Примечание: Этот API эндпоинт считается устаревшим.
        Рекомендуется использовать WebSocket для получения данных в реальном времени.
        """
        logger.warning("Использование устаревшего HTTP API вместо WebSocket для получения неймспейсов")
        try:
            # Получение списка неймспейсов
            all_namespaces = namespaces.list_namespaces(k8s_client)
            logger.debug(f"Получено неймспейсов: {len(all_namespaces)}")

            # Фильтрация неймспейсов по правам доступа
            allowed_namespaces = await filter_namespaces_by_access(request, all_namespaces)
            logger.debug(f"После фильтрации осталось неймспейсов: {len(allowed_namespaces)}")

            response = {"items": allowed_namespaces}
            logger.debug(f"Отправка неймспейсов на фронт: {response}")
            return response
        except Exception as e:
            logger.error(f"Ошибка при получении списка неймспейсов: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ошибка при получении списка неймспейсов: {str(e)}")

    @router.get("/deployments", response_model=DeploymentList)
    async def list_deployments(
        request: Request,
        namespace: Optional[str] = None,
        cluster: Optional[str] = None
    ):
        """Получение списка Deployments с учетом фильтров.

        Примечание: Этот API эндпоинт считается устаревшим.
        Рекомендуется использовать WebSocket для получения данных в реальном времени.
        """
        logger.warning("Использование устаревшего HTTP API вместо WebSocket для получения деплойментов")
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
            valid_pods = []
            for pod in deployment_pods:
                pod_name = pod.get("name")
                try:
                    # Получаем метрики для пода
                    pod_metrics_data = metrics.get_pod_metrics_by_name(k8s_client, namespace, pod_name)

                    # Убедимся, что все поля соответствуют ожидаемой модели
                    if "containers" not in pod:
                        pod["containers"] = []

                    # Если метрики получены успешно, добавляем их к поду
                    if pod_metrics_data:
                        pod["metrics"] = pod_metrics_data
                    else:
                        # Создаем пустые метрики с правильной структурой
                        pod["metrics"] = {
                            "name": pod_name,
                            "namespace": namespace,
                            "containers": [],
                            "timestamp": None,
                            "age_seconds": 0
                        }

                    # Убедимся, что поле phase есть в каждом поде
                    if "phase" not in pod:
                        pod["phase"] = "Unknown"

                    valid_pods.append(pod)
                except Exception as e:
                    logger.error(f"Ошибка при обработке пода {pod_name}: {str(e)}")
                    # Пропускаем поды с ошибками для сохранения валидации

            # Добавляем поды к деплойменту
            deployment["pods"] = valid_pods

            return deployment
        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Ошибка при получении деплоймента: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ошибка при получении деплоймента: {str(e)}")

    @router.get("/controllers", response_model=ControllerList)
    async def list_controllers(
        request: Request,
        namespace: Optional[str] = None,
        cluster: Optional[str] = None
    ):
        """Получение списка контроллеров (Deployments и StatefulSets) с учетом фильтров.

        Примечание: Этот API эндпоинт считается устаревшим.
        Рекомендуется использовать WebSocket для получения данных в реальном времени.
        """
        logger.warning("Использование устаревшего HTTP API вместо WebSocket для получения контроллеров")
        try:
            if namespace:
                # Если указан конкретный неймспейс
                all_controllers = controllers.list_controllers_for_namespace(k8s_client, namespace)

                # Получение паттернов для фильтрации контроллеров
                controller_patterns = app_config.get("default", {}).get("controller_patterns", [".*"])

                # Фильтрация контроллеров по паттернам
                filtered_controllers = controllers.filter_controllers_by_patterns(
                    all_controllers, controller_patterns
                )

                return {"items": filtered_controllers}
            else:
                # Если неймспейс не указан, получаем список всех неймспейсов
                all_namespaces = namespaces.list_namespaces(k8s_client)

                # Фильтрация неймспейсов по правам доступа
                allowed_namespaces = await filter_namespaces_by_access(request, all_namespaces)

                # Получение списка контроллеров для всех доступных неймспейсов
                ns_names = [ns.get("name") for ns in allowed_namespaces]
                all_controllers = controllers.list_controllers_multi_ns(k8s_client, ns_names)

                # Получение паттернов для фильтрации контроллеров
                controller_patterns = app_config.get("default", {}).get("controller_patterns", [".*"])

                # Фильтрация контроллеров по паттернам
                filtered_controllers = controllers.filter_controllers_by_patterns(
                    all_controllers, controller_patterns
                )

                return {"items": filtered_controllers}
        except Exception as e:
            logger.error(f"Ошибка при получении списка контроллеров: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ошибка при получении списка контроллеров: {str(e)}")

    @router.get("/controllers/{namespace}/{name}", response_model=ControllerInfo)
    async def get_controller(
        request: Request,
        namespace: str,
        name: str
    ):
        """Получение детальной информации о конкретном контроллере (Deployment или StatefulSet)."""
        try:
            # Получение контроллера по имени и неймспейсу
            controller, controller_type = controllers.get_controller_by_name_and_namespace(
                k8s_client, namespace, name
            )

            if not controller:
                raise HTTPException(status_code=404, detail=f"Контроллер {name} не найден в неймспейсе {namespace}")

            # Получение подов, связанных с контроллером
            controller_pods = controllers.get_controller_pods(
                k8s_client, namespace, name, controller_type
            )

            # Получение метрик для каждого пода
            valid_pods = []
            for pod in controller_pods:
                pod_name = pod.get("name")
                try:
                    # Получаем метрики для пода
                    pod_metrics_data = metrics.get_pod_metrics_by_name(k8s_client, namespace, pod_name)

                    # Убедимся, что все поля соответствуют ожидаемой модели
                    if "containers" not in pod:
                        pod["containers"] = []

                    # Если метрики получены успешно, добавляем их к поду
                    if pod_metrics_data:
                        pod["metrics"] = pod_metrics_data
                    else:
                        # Создаем пустые метрики с правильной структурой
                        pod["metrics"] = {
                            "name": pod_name,
                            "namespace": namespace,
                            "containers": [],
                            "timestamp": None,
                            "age_seconds": 0
                        }

                    # Убедимся, что поле phase есть в каждом поде
                    if "phase" not in pod:
                        pod["phase"] = "Unknown"

                    valid_pods.append(pod)
                except Exception as e:
                    logger.error(f"Ошибка при обработке пода {pod_name}: {str(e)}")
                    # Пропускаем поды с ошибками для сохранения валидации

            # Добавляем поды к контроллеру
            controller["pods"] = valid_pods

            return controller
        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Ошибка при получении контроллера: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ошибка при получении контроллера: {str(e)}")

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

    @router.get("/debug/data")
    async def debug_data():
        """Эндпоинт для отладки данных."""
        return {
            "namespaces": namespaces.list_namespaces(k8s_client),
            "deployments": [
                {
                    "namespace": ns["name"],
                    "deployments": deployments.list_deployments_for_namespace(k8s_client, ns["name"])
                }
                for ns in namespaces.list_namespaces(k8s_client)
            ],
            "statefulsets": [
                {
                    "namespace": ns["name"],
                    "statefulsets": statefulsets.list_statefulsets_for_namespace(k8s_client, ns["name"])
                }
                for ns in namespaces.list_namespaces(k8s_client)
            ]
        }

    @router.get("/debug/namespaces")
    async def debug_namespaces(request: Request):
        """Эндпоинт для отладки данных неймспейсов."""
        all_namespaces = namespaces.list_namespaces(k8s_client)
        allowed_namespaces = await filter_namespaces_by_access(request, all_namespaces)

        return {
            "all_namespaces": all_namespaces,
            "allowed_namespaces": allowed_namespaces,
            "disable_auth": os.environ.get("DISABLE_AUTH", "false").lower() in ["true", "1", "yes", "y"],
            "user_in_session": request.session.get("user") is not None
        }

    @router.post("/watch/start")
    async def start_resource_watching(
        resource_types: List[str] = Query(["deployments", "pods", "namespaces"])
    ):
        """Запуск наблюдения за ресурсами."""
        try:
            watch_tasks = await start_watching(k8s_client, resource_types)
            return {
                "status": "ok",
                "message": "Наблюдение за ресурсами запущено",
                "watching": list(watch_tasks.keys())
            }
        except Exception as e:
            logger.error(f"Ошибка при запуске наблюдения: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ошибка при запуске наблюдения: {str(e)}")

    @router.post("/watch/stop")
    async def stop_resource_watching():
        """Остановка наблюдения за ресурсами."""
        try:
            await stop_watching()
            return {
                "status": "ok",
                "message": "Наблюдение за ресурсами остановлено"
            }
        except Exception as e:
            logger.error(f"Ошибка при остановке наблюдения: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ошибка при остановке наблюдения: {str(e)}")

    @router.get("/watch/status")
    async def get_watch_status():
        """Получение статуса наблюдения за ресурсами."""
        active_watches = get_active_watches()
        return {
            "status": "ok",
            "watching": list(active_watches)
        }

    return router
