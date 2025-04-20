"""Модуль для работы с Kubernetes Watch API."""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Callable, Awaitable, Tuple, Set

from kubernetes import client, watch
from kubernetes.client.exceptions import ApiException

from dashboard_light.state_manager import update_resource_state
import dashboard_light.k8s.deployments as deployments
import dashboard_light.k8s.pods as pods
import dashboard_light.k8s.namespaces as namespaces

logger = logging.getLogger(__name__)

# Типы для аннотаций
ResourceType = str  # 'deployments', 'pods', 'namespaces'
WatchTask = asyncio.Task  # Задача асинхронного наблюдения

# Словарь активных задач наблюдения по типам ресурсов
_watch_tasks: Dict[ResourceType, WatchTask] = {}

# Константы для ограничения повторных подключений
RETRY_INITIAL_DELAY = 1  # Начальная задержка в секундах
RETRY_MAX_DELAY = 60  # Максимальная задержка в секундах
RETRY_BACKOFF_FACTOR = 2  # Коэффициент увеличения задержки

# Словарь функций для получения ресурсов разных типов
_resource_functions = {
    'deployments': {
        'list_func': lambda api: api.list_deployment_for_all_namespaces,
        'api_type': 'apps_v1_api',
        'convert_func': deployments.get_deployment_status
    },
    'pods': {
        'list_func': lambda api: api.list_pod_for_all_namespaces,
        'api_type': 'core_v1_api',
        'convert_func': pods.get_pod_status
    },
    'namespaces': {
        'list_func': lambda api: api.list_namespace,
        'api_type': 'core_v1_api',
        'convert_func': None
    }
}

def _get_api_instance(k8s_client: Dict[str, Any], resource_type: ResourceType) -> Any:
    """Получение экземпляра API для указанного типа ресурса.

    Args:
        k8s_client: Словарь с Kubernetes клиентами
        resource_type: Тип ресурса ('deployments', 'pods', 'namespaces')

    Returns:
        Any: Экземпляр API или None, если не найден
    """
    api_type = _resource_functions.get(resource_type, {}).get('api_type')
    if not api_type:
        logger.error(f"Не найден тип API для ресурса {resource_type}")
        return None

    api_instance = k8s_client.get(api_type)
    if not api_instance:
        logger.warning(f"API клиент для {api_type} не инициализирован")
        return None

    return api_instance

def _convert_to_dict(resource_type: ResourceType, resource: Any) -> Dict[str, Any]:
    """Преобразование объекта Kubernetes в словарь.

    Args:
        resource_type: Тип ресурса ('deployments', 'pods', 'namespaces')
        resource: Объект ресурса Kubernetes

    Returns:
        Dict[str, Any]: Словарь с данными ресурса
    """
    metadata = resource.metadata
    result = {
        "name": metadata.name,
        "namespace": getattr(metadata, "namespace", ""),
    }

    # Дополнительные данные в зависимости от типа ресурса
    if resource_type == 'deployments':
        # Переиспользуем существующую логику из deployments.py
        spec = resource.spec
        status = resource.status

        # Получение информации о контейнерах
        containers = []
        if spec.template and spec.template.spec and spec.template.spec.containers:
            containers = spec.template.spec.containers

        main_container = containers[0] if containers else None

        # Формирование данных о деплойменте
        result.update({
            "replicas": {
                "desired": spec.replicas,
                "ready": status.ready_replicas if status.ready_replicas else 0,
                "available": status.available_replicas if status.available_replicas else 0,
                "updated": status.updated_replicas if status.updated_replicas else 0,
            }
        })

        # Добавление информации о главном контейнере, если он есть
        if main_container:
            image = main_container.image
            image_tag = image.split(":")[-1] if ":" in image else "latest"

            result["main_container"] = {
                "name": main_container.name,
                "image": image,
                "image_tag": image_tag,
            }

        # Добавление лейблов
        if metadata.labels:
            result["labels"] = metadata.labels

        # Добавление информации о владельце (owner references)
        if metadata.owner_references:
            owner_refs = []
            for ref in metadata.owner_references:
                owner_refs.append({
                    "name": ref.name,
                    "kind": ref.kind,
                    "uid": ref.uid,
                })
            result["owner_references"] = owner_refs

        # Добавление статуса
        result["status"] = deployments.get_deployment_status(result)

    elif resource_type == 'pods':
        # Переиспользуем существующую логику из pods.py
        spec = resource.spec
        status = resource.status

        # Получение информации о контейнерах
        container_specs = spec.containers if spec and spec.containers else []
        containers = []

        for container_spec in container_specs:
            image = container_spec.image
            image_tag = image.split(":")[-1] if ":" in image else "latest"

            containers.append({
                "name": container_spec.name,
                "image": image,
                "image_tag": image_tag,
            })

        # Дополнение данных о поде
        result.update({
            "phase": status.phase if status else "Unknown",
            "containers": containers,
            "pod_ip": status.pod_ip if status else None,
            "host_ip": status.host_ip if status else None,
            "started_at": status.start_time.isoformat() if status and status.start_time else None,
        })

        # Добавление лейблов
        if metadata.labels:
            result["labels"] = metadata.labels

        # Добавление статуса
        result["status"] = pods.get_pod_status(result)

    elif resource_type == 'namespaces':
        # Переиспользуем существующую логику из namespaces.py
        result.update({
            "phase": resource.status.phase,
            "created": metadata.creation_timestamp.isoformat() if metadata.creation_timestamp else None,
            "labels": metadata.labels if metadata.labels else {},
        })

    return result

async def _watch_resource(
    k8s_client: Dict[str, Any],
    resource_type: ResourceType,
    retry_delay: int = RETRY_INITIAL_DELAY
) -> None:
    """Асинхронное наблюдение за ресурсами указанного типа.

    Args:
        k8s_client: Словарь с Kubernetes клиентами
        resource_type: Тип ресурса ('deployments', 'pods', 'namespaces')
        retry_delay: Задержка перед повторной попыткой подключения
    """
    if resource_type not in _resource_functions:
        logger.error(f"Неизвестный тип ресурса: {resource_type}")
        return

    logger.info(f"Запуск наблюдения за ресурсами типа {resource_type}")

    # В бесконечном цикле пытаемся установить и поддерживать соединение
    while True:
        try:
            # Получение API в зависимости от типа ресурса
            api_instance = _get_api_instance(k8s_client, resource_type)
            if not api_instance:
                logger.error(f"Не удалось получить API для {resource_type}")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * RETRY_BACKOFF_FACTOR, RETRY_MAX_DELAY)
                continue

            # Создание объекта watch и функции для наблюдения
            w = watch.Watch()
            list_func = _resource_functions[resource_type]['list_func'](api_instance)

            # Запуск наблюдения
            logger.info(f"Установка соединения Watch API для {resource_type}")

            # Используем асинхронную обертку для синхронного API watch
            for event in w.stream(list_func):
                # Получение типа события и ресурса
                event_type = event['type']  # ADDED, MODIFIED, DELETED
                resource = event['object']

                # Преобразование ресурса в словарь
                resource_dict = _convert_to_dict(resource_type, resource)

                # Обновление состояния через менеджер состояния
                await update_resource_state(event_type, resource_type, resource_dict)

                # Даем шанс другим асинхронным задачам выполниться
                await asyncio.sleep(0)

            # Если мы здесь, значит соединение закрылось без исключения
            logger.warning(f"Соединение Watch API для {resource_type} закрылось, переподключение...")
            retry_delay = RETRY_INITIAL_DELAY

        except ApiException as e:
            logger.error(f"API ошибка при наблюдении за {resource_type}: {e}")
            if e.status == 410:  # Gone, требуется повторное подключение с новой версией
                logger.info(f"Ресурс версии больше нет, переподключение для {resource_type}")
                retry_delay = RETRY_INITIAL_DELAY
            else:
                retry_delay = min(retry_delay * RETRY_BACKOFF_FACTOR, RETRY_MAX_DELAY)
        except Exception as e:
            logger.error(f"Ошибка при наблюдении за {resource_type}: {e}")
            retry_delay = min(retry_delay * RETRY_BACKOFF_FACTOR, RETRY_MAX_DELAY)
        finally:
            if 'w' in locals():
                w.stop()
            logger.info(f"Повторное подключение через {retry_delay} сек для {resource_type}")
            await asyncio.sleep(retry_delay)

async def start_watching(
    k8s_client: Dict[str, Any],
    resource_types: List[ResourceType] = ['deployments', 'pods', 'namespaces']
) -> Dict[ResourceType, WatchTask]:
    """Запуск наблюдения за ресурсами указанных типов.

    Args:
        k8s_client: Словарь с Kubernetes клиентами
        resource_types: Список типов ресурсов для наблюдения

    Returns:
        Dict[ResourceType, WatchTask]: Словарь задач наблюдения
    """
    global _watch_tasks

    # Остановка существующих задач
    await stop_watching()

    # Запуск новых задач
    for resource_type in resource_types:
        if resource_type in _resource_functions:
            task = asyncio.create_task(
                _watch_resource(k8s_client, resource_type),
                name=f"watch_{resource_type}"
            )
            _watch_tasks[resource_type] = task
            logger.info(f"Создана задача наблюдения за {resource_type}")
        else:
            logger.warning(f"Неизвестный тип ресурса: {resource_type}")

    return _watch_tasks

async def stop_watching() -> None:
    """Остановка всех задач наблюдения."""
    global _watch_tasks

    for resource_type, task in _watch_tasks.items():
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info(f"Задача наблюдения за {resource_type} отменена")
            except Exception as e:
                logger.error(f"Ошибка при остановке наблюдения за {resource_type}: {e}")

    _watch_tasks.clear()
    logger.info("Все задачи наблюдения остановлены")

def is_watching(resource_type: ResourceType) -> bool:
    """Проверка, ведется ли наблюдение за указанным типом ресурса.

    Args:
        resource_type: Тип ресурса

    Returns:
        bool: True, если наблюдение активно
    """
    return resource_type in _watch_tasks and not _watch_tasks[resource_type].done()

def get_active_watches() -> Set[ResourceType]:
    """Получение списка типов ресурсов, за которыми ведется наблюдение.

    Returns:
        Set[ResourceType]: Множество активных наблюдений
    """
    return {rt for rt, task in _watch_tasks.items() if not task.done()}
