"""Модуль управления состоянием ресурсов Kubernetes."""

import asyncio
import logging
import time
from typing import Any, Dict, List, Set, Optional, Callable, Awaitable
from datetime import datetime
import threading
from copy import deepcopy

from dashboard_light.k8s import watch
from dashboard_light.k8s.cache import with_cache, invalidate_by_prefix
from dashboard_light.web.websockets import connection_manager

logger = logging.getLogger(__name__)

# Глобальное хранилище состояния ресурсов
resource_store: Dict[str, Dict[str, Dict[str, Any]]] = {
    "deployments": {},
    "statefulsets": {},
    "pods": {},
    "namespaces": {},
}

# Блокировки для синхронизации доступа к ресурсам
resource_locks: Dict[str, threading.RLock] = {
    "deployments": threading.RLock(),
    "statefulsets": threading.RLock(),
    "pods": threading.RLock(),
    "namespaces": threading.RLock(),
}

# Функция для получения ключа ресурса
def get_resource_key(resource: Dict[str, Any]) -> str:
    """Получение уникального ключа для ресурса.

    Args:
        resource: Словарь с данными ресурса

    Returns:
        str: Уникальный ключ ресурса
    """
    name = resource.get("name", "unknown")
    namespace = resource.get("namespace")

    if namespace:
        return f"{namespace}/{name}"
    else:
        return name


async def handle_resource_event(event_type: str, resource: Dict[str, Any], resource_type: str):
    """Обработка события ресурса из Watch API.

    Args:
        event_type: Тип события ('ADDED', 'MODIFIED', 'DELETED')
        resource: Словарь с данными ресурса
        resource_type: Тип ресурса ('deployments', 'pods', 'namespaces', 'statefulsets')
    """
    if resource_type not in resource_store:
        logger.warning(f"Неизвестный тип ресурса: {resource_type}")
        return

    try:
        # Получение ключа ресурса
        resource_key = get_resource_key(resource)

        # Обработка события в зависимости от типа
        with resource_locks[resource_type]:
            if event_type in [watch.K8S_EVENT_ADDED, watch.K8S_EVENT_MODIFIED]:
                # Добавление или обновление ресурса
                resource_store[resource_type][resource_key] = resource
                # Инвалидация кэша для этого типа ресурсов
                invalidate_by_prefix(resource_type)

                logger.debug(f"Ресурс {resource_type}/{resource_key} обновлен в хранилище")

            elif event_type == watch.K8S_EVENT_DELETED:
                # Удаление ресурса
                if resource_key in resource_store[resource_type]:
                    del resource_store[resource_type][resource_key]
                    # Инвалидация кэша для этого типа ресурсов
                    invalidate_by_prefix(resource_type)

                    logger.debug(f"Ресурс {resource_type}/{resource_key} удален из хранилища")
            # Добавляем логирование для подов в интересующих namespace
            # if resource_type == "pods" and event_type in [watch.K8S_EVENT_ADDED, watch.K8S_EVENT_MODIFIED]:
            #     namespace = resource.get("namespace", "")
            #     if namespace in ["kbs-us-pre-production", "kbs-us-staging"]:
            #         pod_name = resource.get("name", "unknown")
            #         logger.info(f"Событие {event_type} для пода {namespace}/{pod_name}")

        # Отправка события через WebSocket
        namespace = resource.get("namespace")
        await connection_manager.broadcast_resource_event(
            resource_type=resource_type,
            event_type=event_type,
            resource=resource,
            namespace=namespace
        )

    except Exception as e:
        logger.error(f"Ошибка обработки события {event_type} для {resource_type}: {str(e)}")


def get_resource(resource_type: str, namespace: Optional[str] = None, name: Optional[str] = None) -> Any:
    """Получение ресурса или списка ресурсов из хранилища.

    Args:
        resource_type: Тип ресурса
        namespace: Пространство имен (опционально)
        name: Имя ресурса (опционально)

    Returns:
        Any: Ресурс, список ресурсов или None
    """
    if resource_type not in resource_store:
        logger.warning(f"Неизвестный тип ресурса: {resource_type}")
        return None

    try:
        with resource_locks[resource_type]:
            # Если указаны namespace и name, ищем конкретный ресурс
            if namespace and name:
                resource_key = f"{namespace}/{name}"
                return deepcopy(resource_store[resource_type].get(resource_key))

            # Если указан только namespace, ищем все ресурсы в этом namespace
            elif namespace:
                result = []
                for key, resource in resource_store[resource_type].items():
                    if resource.get("namespace") == namespace:
                        result.append(deepcopy(resource))
                return result

            # Если указано только имя, ищем ресурс с этим именем во всех namespace
            elif name:
                for key, resource in resource_store[resource_type].items():
                    if resource.get("name") == name:
                        return deepcopy(resource)
                return None

            # Если ничего не указано, возвращаем все ресурсы
            else:
                return list(deepcopy(resource_store[resource_type]).values())

    except Exception as e:
        logger.error(f"Ошибка получения ресурса {resource_type}/{namespace}/{name}: {str(e)}")
        return None


def update_resource_store(resource_type: str, resources: List[Dict[str, Any]]):
    """Обновление хранилища ресурсов новыми данными.

    Args:
        resource_type: Тип ресурса
        resources: Список ресурсов для обновления
    """
    if resource_type not in resource_store:
        logger.warning(f"Неизвестный тип ресурса: {resource_type}")
        return

    try:
        with resource_locks[resource_type]:
            # Создаем новый словарь с ресурсами
            new_store = {}

            for resource in resources:
                resource_key = get_resource_key(resource)
                new_store[resource_key] = resource

            # Обновляем хранилище новыми данными
            resource_store[resource_type] = new_store

            logger.debug(f"Хранилище {resource_type} обновлено, ресурсов: {len(new_store)}")

    except Exception as e:
        logger.error(f"Ошибка обновления хранилища {resource_type}: {str(e)}")

async def start_watchers(k8s_client: Dict[str, Any], resources_to_watch: List[str] = None):
    """Запуск наблюдателей для всех типов ресурсов."""
    if not resources_to_watch:
        resources_to_watch = list(resource_store.keys())

    logger.info(f"Запуск наблюдателей для ресурсов: {resources_to_watch}")

    try:
        # Создаем асинхронные задачи для каждого типа ресурса
        for resource_type in resources_to_watch:
            # Создаем обработчик событий для конкретного типа ресурса
            handler = lambda event_type, resource, rt=resource_type: handle_resource_event(event_type, resource, rt)

            # Запускаем наблюдателя в ФОНОВОЙ задаче
            if resource_type == "namespaces":
                # Для namespace не нужно указывать namespace
                asyncio.create_task(
                    watch.watch_resources(
                        k8s_client=k8s_client,
                        resource_type=resource_type,
                        callback=handler
                    )
                )
            else:
                # Для остальных ресурсов наблюдаем за всеми namespace
                asyncio.create_task(
                    watch.watch_resources(
                        k8s_client=k8s_client,
                        resource_type=resource_type,
                        callback=handler
                    )
                )

        logger.info("Все наблюдатели запущены")
    except Exception as e:
        logger.error(f"Ошибка при запуске наблюдателей: {str(e)}")

# async def start_watchers(k8s_client: Dict[str, Any], resources_to_watch: List[str] = None):
#     """Запуск наблюдателей для всех типов ресурсов."""
#     if not resources_to_watch:
#         resources_to_watch = list(resource_store.keys())

#     logger.info(f"Запуск наблюдателей для ресурсов: {resources_to_watch}")

#     # Создаем асинхронные задачи для каждого типа ресурса
#     for resource_type in resources_to_watch:
#         # Создаем обработчик событий для конкретного типа ресурса
#         handler = lambda event_type, resource, rt=resource_type: handle_resource_event(event_type, resource, rt)

#         # Запускаем наблюдателя в отдельной задаче и НЕ ЖДЕМ ее завершения
#         if resource_type == "namespaces":
#             # Для namespace не нужно указывать namespace
#             asyncio.create_task(
#                 watch.watch_resources(
#                     k8s_client=k8s_client,
#                     resource_type=resource_type,
#                     callback=handler
#                 )
#             )
#         else:
#             # Для остальных ресурсов наблюдаем за всеми namespace
#             asyncio.create_task(
#                 watch.watch_resources(
#                     k8s_client=k8s_client,
#                     resource_type=resource_type,
#                     callback=handler
#                 )
#             )

#     # НЕ используем await asyncio.gather() здесь, т.к. это блокирует поток событий
#     logger.info("Все наблюдатели запущены")

# async def start_watchers(k8s_client: Dict[str, Any], resources_to_watch: List[str] = None):
#     """Запуск наблюдателей для всех типов ресурсов.

#     Args:
#         k8s_client: Клиент Kubernetes
#         resources_to_watch: Список типов ресурсов для наблюдения (по умолчанию все)
#     """
#     if not resources_to_watch:
#         resources_to_watch = list(resource_store.keys())

#     logger.info(f"Запуск наблюдателей для ресурсов: {resources_to_watch}")

#     # Создаем асинхронные задачи для каждого типа ресурса
#     tasks = []

#     for resource_type in resources_to_watch:
#         # Создаем обработчик событий для конкретного типа ресурса
#         handler = lambda event_type, resource, rt=resource_type: handle_resource_event(event_type, resource, rt)

#         # Запускаем наблюдателя
#         if resource_type == "namespaces":
#             # Для namespace не нужно указывать namespace
#             task = asyncio.create_task(
#                 watch.watch_resources(
#                     k8s_client=k8s_client,
#                     resource_type=resource_type,
#                     callback=handler
#                 )
#             )
#         else:
#             # Для остальных ресурсов наблюдаем за всеми namespace
#             task = asyncio.create_task(
#                 watch.watch_resources(
#                     k8s_client=k8s_client,
#                     resource_type=resource_type,
#                     callback=handler
#                 )
#             )

#         tasks.append(task)

#     # Ждем выполнения всех задач (они бесконечные, поэтому это блокирующий вызов)
#     try:
#         await asyncio.gather(*tasks)
#     except Exception as e:
#         logger.error(f"Ошибка в наблюдателях: {str(e)}")
#         # Перезапуск наблюдателей при ошибке
#         await asyncio.sleep(5)
#         asyncio.create_task(start_watchers(k8s_client, resources_to_watch))

async def startup_state_manager(k8s_client: Dict[str, Any]):
    """Инициализация и запуск менеджера состояния при старте приложения."""
    logger.info("Инициализация менеджера состояния")

    # Инициализация хранилища ресурсов
    for resource_type in resource_store:
        resource_store[resource_type] = {}

    # Запуск наблюдателей - не блокирует выполнение
    await start_watchers(k8s_client)

    logger.info("Менеджер состояния запущен")

# async def startup_state_manager(k8s_client: Dict[str, Any]):
#     """Инициализация и запуск менеджера состояния при старте приложения.

#     Args:
#         k8s_client: Клиент Kubernetes
#     """
#     logger.info("Инициализация менеджера состояния")

#     # Инициализация хранилища ресурсов
#     for resource_type in resource_store:
#         resource_store[resource_type] = {}

#     # Запуск наблюдателей - запуск и возврат без ожидания
#     await start_watchers(k8s_client)
#     # # Запуск наблюдателей
#     # asyncio.create_task(start_watchers(k8s_client))

#     logger.info("Менеджер состояния запущен")


# Функция для инициализации начального состояния из существующих данных
async def initialize_state_from_api(k8s_client: Dict[str, Any]):
    """Инициализация начального состояния из API Kubernetes.

    Args:
        k8s_client: Клиент Kubernetes
    """
    try:
        logger.info("Инициализация начального состояния из API Kubernetes")

        # Еще раз проверяем, что клиент правильно инициализирован
        if not k8s_client or not k8s_client.get("core_v1_api") or not k8s_client.get("apps_v1_api"):
            logger.error("K8S клиент не инициализирован полностью, пропускаем инициализацию состояния")
            return

        # Проверяем правильную инициализацию клиентов
        if "core_v1_api" not in k8s_client or k8s_client["core_v1_api"] is None:
            logger.error("K8S: core_v1_api не инициализирован, невозможно получить данные!")
            return

        if "apps_v1_api" not in k8s_client or k8s_client["apps_v1_api"] is None:
            logger.error("K8S: apps_v1_api не инициализирован, невозможно получить данные!")
            return

        # Инициализация для namespace
        from dashboard_light.k8s.namespaces import list_namespaces
        namespaces = list_namespaces(k8s_client)
        update_resource_store("namespaces", namespaces)

        # Инициализация для deployments
        from dashboard_light.k8s.deployments import list_deployments_multi_ns
        deployments = list_deployments_multi_ns(k8s_client, [""])
        update_resource_store("deployments", deployments)

        # Инициализация для statefulsets
        from dashboard_light.k8s.statefulsets import list_statefulsets_multi_ns
        statefulsets = list_statefulsets_multi_ns(k8s_client, [""])
        update_resource_store("statefulsets", statefulsets)

        # Инициализация для pods
        from dashboard_light.k8s.pods import list_pods_for_namespace
        # Собираем поды из всех namespace
        all_pods = []
        for namespace in namespaces:
            ns_name = namespace.get("name", "")
            if ns_name:
                pods = list_pods_for_namespace(k8s_client, ns_name)
                all_pods.extend(pods)
        update_resource_store("pods", all_pods)
        # Статистика и логирование подов
        if all_pods:
            logger.info(f"Инициализировано подов: {len(all_pods)}")

            # Статистика по namespace
            namespace_pod_counts = {}
            for pod in all_pods:
                ns = pod.get("namespace", "unknown")
                namespace_pod_counts[ns] = namespace_pod_counts.get(ns, 0) + 1

            # Вывод кол-ва подов в интересующих namespace
            # for target_ns in ["kbs-us-pre-production", "kbs-us-staging"]:
            #     count = namespace_pod_counts.get(target_ns, 0)
            #     if count > 0:
            #         # Выводим список подов в этом namespace
            #         ns_pods = [pod.get("name") for pod in all_pods if pod.get("namespace") == target_ns]
            #         logger.info(f"Поды в namespace {target_ns}: {ns_pods}")
            #     else:
            #         logger.warning(f"В namespace {target_ns} не найдено подов!")

            logger.info(f"Статистика подов по namespace: {namespace_pod_counts}")
        else:
            logger.warning("Не удалось инициализировать ни одного пода!")

        log_store_contents()
        logger.info("Начальное состояние инициализировано")

    except Exception as e:
        logger.error(f"Ошибка инициализации начального состояния: {str(e)}")

def log_store_contents():
    """Вывод в лог содержимого хранилища ресурсов."""
    try:
        for resource_type, resources in resource_store.items():
            resource_count = len(resources)
            logger.info(f"Хранилище {resource_type}: {resource_count} элементов")

            # Проверяем поды в конкретных namespace
            # if resource_type == "pods":
            #     for target_ns in ["kbs-us-pre-production", "kbs-us-staging"]:
            #         ns_pods = [key for key, pod in resources.items() if pod.get("namespace") == target_ns]
            #         if ns_pods:
            #             logger.info(f"Поды в {target_ns} в хранилище: {ns_pods}")
            #         else:
            #             logger.warning(f"В хранилище нет подов из namespace {target_ns}")
    except Exception as e:
        logger.error(f"Ошибка при выводе содержимого хранилища: {str(e)}")
