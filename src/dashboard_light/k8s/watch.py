"""Модуль для работы с Kubernetes Watch API."""

import asyncio
import logging
import json
from typing import Any, Dict, List, Optional, Callable, Awaitable, Set
from kubernetes import client, watch
from kubernetes.client.exceptions import ApiException

logger = logging.getLogger(__name__)

# Время ожидания перед повторной попыткой подключения в секундах
RECONNECT_TIMEOUT = 5
# Типы событий Kubernetes Watch API
K8S_EVENT_ADDED = "ADDED"
K8S_EVENT_MODIFIED = "MODIFIED"
K8S_EVENT_DELETED = "DELETED"
K8S_EVENT_BOOKMARK = "BOOKMARK"
K8S_EVENT_ERROR = "ERROR"


async def watch_resources(
    k8s_client: Dict[str, Any],
    resource_type: str,
    namespace: Optional[str] = None,
    callback: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None,
    label_selector: Optional[str] = None,
    field_selector: Optional[str] = None,
    resource_version: Optional[str] = None,
    timeout_seconds: Optional[int] = None
) -> None:
    """Асинхронное наблюдение за ресурсами Kubernetes.

    Args:
        k8s_client: Словарь с Kubernetes клиентом и API
        resource_type: Тип ресурса ('deployments', 'pods', 'namespaces', 'statefulsets')
        namespace: Пространство имен для фильтрации (None для всех)
        callback: Асинхронная функция обратного вызова для обработки событий
        label_selector: Селектор меток
        field_selector: Селектор полей
        resource_version: Версия ресурса для начала наблюдения
        timeout_seconds: Таймаут запроса в секундах
    """
    if not callback:
        logger.warning(f"Не указан callback для наблюдения за {resource_type}")
        return

    while True:
        try:
            # Получение функции для наблюдения за ресурсами
            api_instance, watch_func = get_watch_function(
                k8s_client, resource_type, namespace
            )

            if not api_instance or not watch_func:
                logger.error(f"Не удалось получить API для {resource_type}")
                await asyncio.sleep(RECONNECT_TIMEOUT)
                continue

            # Параметры для наблюдения
            kwargs = {}
            if label_selector:
                kwargs["label_selector"] = label_selector
            if field_selector:
                kwargs["field_selector"] = field_selector
            if resource_version:
                kwargs["resource_version"] = resource_version
            if timeout_seconds:
                kwargs["timeout_seconds"] = timeout_seconds

            # Создание наблюдателя
            w = watch.Watch()

            # Стриминг событий
            logger.info(f"Начинаем наблюдение за {resource_type}" +
                       (f" в неймспейсе {namespace}" if namespace else ""))

            async for event in aiter_watch(w, watch_func, **kwargs):
                if not event:
                    continue

                event_type = event.get("type")
                obj = event.get("object")

                if not event_type or not obj:
                    continue

                # Преобразование ресурса в словарь
                try:
                    resource_dict = resource_to_dict(resource_type, obj)
                    # Вызов callback функции с преобразованными данными
                    await callback(event_type, resource_dict)
                except Exception as e:
                    logger.error(f"Ошибка обработки события {event_type} для {resource_type}: {str(e)}")

        except ApiException as e:
            if e.status == 410:  # Gone - использованный resource_version устарел
                logger.warning(f"Resource version для {resource_type} устарела, переподключаемся")
                resource_version = None  # Сбрасываем resource_version для получения новой
            else:
                logger.error(f"API ошибка наблюдения за {resource_type}: {str(e)}")

            await asyncio.sleep(RECONNECT_TIMEOUT)

        except Exception as e:
            logger.error(f"Ошибка наблюдения за {resource_type}: {str(e)}")
            await asyncio.sleep(RECONNECT_TIMEOUT)

        finally:
            try:
                if 'w' in locals():
                    w.stop()
                    logger.info(f"Наблюдение за {resource_type} остановлено, переподключаемся...")
            except Exception as e:
                logger.error(f"Ошибка при остановке наблюдения за {resource_type}: {str(e)}")

            await asyncio.sleep(RECONNECT_TIMEOUT)


async def aiter_watch(w, watch_func, **kwargs):
    """Асинхронная обертка для синхронного API watch.

    Args:
        w: Объект watch.Watch
        watch_func: Функция API для watch
        **kwargs: Аргументы для функции watch

    Yields:
        Dict: События Watch API
    """
    try:
        async def _aiter():
            loop = asyncio.get_running_loop()
            for event in w.stream(watch_func, **kwargs):
                yield event
                await asyncio.sleep(0)  # Позволяем другим задачам выполняться

        async for event in _aiter():
            yield event

    except Exception as e:
        logger.error(f"Ошибка при асинхронной итерации по событиям: {str(e)}")
        yield None


def get_watch_function(
    k8s_client: Dict[str, Any],
    resource_type: str,
    namespace: Optional[str] = None
) -> tuple:
    """Получение API клиента и функции для наблюдения за ресурсами.

    Args:
        k8s_client: Словарь с Kubernetes клиентом и API
        resource_type: Тип ресурса
        namespace: Пространство имен

    Returns:
        tuple: (api_instance, watch_function)
    """
    # Проверка наличия k8s_client
    if not k8s_client:
        logger.error(f"K8S: k8s_client не передан для наблюдения за {resource_type}")
        return None, None

    # Проверка на mock режим
    if k8s_client.get("is_mock", False):
        logger.info(f"K8S: Работаем в режиме мока, наблюдение за {resource_type} не поддерживается")
        return None, None

    # Получение соответствующего API клиента
    if resource_type in ["pods", "services", "configmaps", "secrets"]:
        api_instance = k8s_client.get("core_v1_api")

        if namespace:
            watch_functions = {
                "pods": api_instance.list_namespaced_pod,
                "services": api_instance.list_namespaced_service,
                "configmaps": api_instance.list_namespaced_config_map,
                "secrets": api_instance.list_namespaced_secret
            }
        else:
            watch_functions = {
                "pods": api_instance.list_pod_for_all_namespaces,
                "services": api_instance.list_service_for_all_namespaces,
                "configmaps": api_instance.list_config_map_for_all_namespaces,
                "secrets": api_instance.list_secret_for_all_namespaces
            }

    elif resource_type in ["deployments", "statefulsets", "replicasets", "daemonsets"]:
        api_instance = k8s_client.get("apps_v1_api")

        if namespace:
            watch_functions = {
                "deployments": api_instance.list_namespaced_deployment,
                "statefulsets": api_instance.list_namespaced_stateful_set,
                "replicasets": api_instance.list_namespaced_replica_set,
                "daemonsets": api_instance.list_namespaced_daemon_set
            }
        else:
            watch_functions = {
                "deployments": api_instance.list_deployment_for_all_namespaces,
                "statefulsets": api_instance.list_stateful_set_for_all_namespaces,
                "replicasets": api_instance.list_replica_set_for_all_namespaces,
                "daemonsets": api_instance.list_daemon_set_for_all_namespaces
            }

    elif resource_type == "namespaces":
        api_instance = k8s_client.get("core_v1_api")
        # Для неймспейсов не используется namespace в запросе
        watch_functions = {"namespaces": api_instance.list_namespace}
    else:
        logger.error(f"Неподдерживаемый тип ресурса: {resource_type}")
        return None, None

    # Проверка инициализации API
    if not api_instance:
        logger.error(f"API клиент для {resource_type} не инициализирован")
        return None, None

    # Получение соответствующей функции
    watch_func = watch_functions.get(resource_type)
    if not watch_func:
        logger.error(f"Не удалось найти функцию для наблюдения за {resource_type}")
        return None, None

    return api_instance, watch_func

def resource_to_dict(resource_type: str, obj: Any) -> Dict[str, Any]:
    """Преобразование объекта ресурса Kubernetes в словарь."""
    try:
        # Извлечение метаданных
        metadata = obj.metadata
        resource_dict = {
            "name": metadata.name,
            "namespace": getattr(metadata, "namespace", None),
            "labels": metadata.labels if metadata.labels else {},
            "resource_version": metadata.resource_version,
            "uid": metadata.uid,
            "creation_timestamp": metadata.creation_timestamp.isoformat() if metadata.creation_timestamp else None
        }

        # Обработка разных типов ресурсов
        if resource_type == "pods":
            # Форматируем под напрямую, не используя list_pods_for_namespace
            spec = obj.spec
            status = obj.status

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

            # Формирование данных о поде
            resource_dict.update({
                "phase": status.phase if status else "Unknown",
                "containers": containers,
                "pod_ip": status.pod_ip if status else None,
                "host_ip": status.host_ip if status else None,
                "started_at": status.start_time.isoformat() if status and status.start_time else None,
            })

            # Добавление информации о владельце (owner references)
            if metadata.owner_references:
                owner_refs = []
                for ref in metadata.owner_references:
                    owner_refs.append({
                        "name": ref.name,
                        "kind": ref.kind,
                        "uid": ref.uid,
                    })
                resource_dict["owner_references"] = owner_refs

        elif resource_type in ["deployments", "statefulsets"]:
            # Форматируем deployment/statefulset напрямую
            spec = obj.spec
            status = obj.status

            # Информация о репликах
            replicas_data = {
                "desired": spec.replicas if spec and hasattr(spec, "replicas") else 0,
                "ready": status.ready_replicas if status and hasattr(status, "ready_replicas") else 0,
                "available": status.available_replicas if status and hasattr(status, "available_replicas") else 0,
                "updated": status.updated_replicas if status and hasattr(status, "updated_replicas") else 0,
            }

            resource_dict["replicas"] = replicas_data

            # Информация о главном контейнере
            if spec and hasattr(spec, "template") and spec.template and hasattr(spec.template, "spec") and spec.template.spec and hasattr(spec.template.spec, "containers") and spec.template.spec.containers:
                main_container = spec.template.spec.containers[0]
                image = main_container.image
                image_tag = image.split(":")[-1] if ":" in image else "latest"

                resource_dict["main_container"] = {
                    "name": main_container.name,
                    "image": image,
                    "image_tag": image_tag,
                }

            # Добавление статуса
            if resource_type == "deployments":
                from dashboard_light.k8s.deployments import get_deployment_status
                resource_dict["status"] = get_deployment_status(resource_dict)
            elif resource_type == "statefulsets":
                from dashboard_light.k8s.statefulsets import get_statefulset_status
                resource_dict["status"] = get_statefulset_status(resource_dict)

            # Добавление информации о контроллере для WebSocket
            resource_dict["controller_type"] = "deployment" if resource_type == "deployments" else "statefulset"

        elif resource_type == "namespaces":
            # Обработка неймспейсов
            status = obj.status
            resource_dict.update({
                "phase": status.phase if status else "Unknown",
            })
            # Удаление namespace для неймспейсов, так как это не имеет смысла
            resource_dict.pop("namespace", None)

        return resource_dict

    except Exception as e:
        logger.error(f"Ошибка при преобразовании {resource_type} в словарь: {str(e)}")
        # Возвращаем базовую информацию, если не удалось преобразовать
        return {
            "name": getattr(obj.metadata, "name", "unknown"),
            "namespace": getattr(obj.metadata, "namespace", None),
            "error": f"Ошибка преобразования: {str(e)}"
        }
# def resource_to_dict(resource_type: str, obj: Any) -> Dict[str, Any]:
#     """Преобразование объекта ресурса Kubernetes в словарь.

#     Args:
#         resource_type: Тип ресурса
#         obj: Объект Kubernetes API

#     Returns:
#         Dict[str, Any]: Словарь с данными ресурса
#     """
#     try:
#         # Извлечение метаданных
#         metadata = obj.metadata
#         resource_dict = {
#             "name": metadata.name,
#             "namespace": getattr(metadata, "namespace", None),
#             "labels": metadata.labels if metadata.labels else {},
#             "resource_version": metadata.resource_version,
#             "uid": metadata.uid,
#             "creation_timestamp": metadata.creation_timestamp.isoformat() if metadata.creation_timestamp else None
#         }

#         # Обработка разных типов ресурсов
#         if resource_type == "pods":
#             from dashboard_light.k8s.pods import list_pods_for_namespace
#             # Используем готовую функцию, которая уже форматирует поды
#             mock_k8s_client = {"is_mock": True}  # Чтобы не вызвать реальный API
#             pod_data = list_pods_for_namespace(mock_k8s_client, resource_dict["namespace"] or "default")
#             # Находим под с таким же именем
#             pod = next((p for p in pod_data if p["name"] == resource_dict["name"]), None)
#             if pod:
#                 return pod

#             # Если не нашли или список пустой (mock), форматируем вручную
#             spec = obj.spec
#             status = obj.status

#             # Получение информации о контейнерах
#             container_specs = spec.containers if spec and spec.containers else []
#             containers = []

#             for container_spec in container_specs:
#                 image = container_spec.image
#                 image_tag = image.split(":")[-1] if ":" in image else "latest"

#                 containers.append({
#                     "name": container_spec.name,
#                     "image": image,
#                     "image_tag": image_tag,
#                 })

#             # Формирование данных о поде
#             resource_dict.update({
#                 "phase": status.phase if status else "Unknown",
#                 "containers": containers,
#                 "pod_ip": status.pod_ip if status else None,
#                 "host_ip": status.host_ip if status else None,
#                 "started_at": status.start_time.isoformat() if status and status.start_time else None,
#             })

#             # Добавление информации о владельце (owner references)
#             if metadata.owner_references:
#                 owner_refs = []
#                 for ref in metadata.owner_references:
#                     owner_refs.append({
#                         "name": ref.name,
#                         "kind": ref.kind,
#                         "uid": ref.uid,
#                     })
#                 resource_dict["owner_references"] = owner_refs

#         elif resource_type in ["deployments", "statefulsets"]:
#             # Использование существующих функций форматирования
#             if resource_type == "deployments":
#                 from dashboard_light.k8s.deployments import list_deployments_for_namespace, get_deployment_status
#             elif resource_type == "statefulsets":
#                 from dashboard_light.k8s.statefulsets import list_statefulsets_for_namespace, get_statefulset_status

#             # Создаем словарь с данными
#             spec = obj.spec
#             status = obj.status

#             # Информация о репликах
#             resource_dict.update({
#                 "replicas": {
#                     "desired": spec.replicas,
#                     "ready": status.ready_replicas if status.ready_replicas else 0,
#                     "available": status.available_replicas if status.available_replicas else 0,
#                     "updated": status.updated_replicas if status.updated_replicas else 0,
#                 }
#             })

#             # Информация о главном контейнере
#             if spec.template and spec.template.spec and spec.template.spec.containers:
#                 main_container = spec.template.spec.containers[0]
#                 image = main_container.image
#                 image_tag = image.split(":")[-1] if ":" in image else "latest"

#                 resource_dict["main_container"] = {
#                     "name": main_container.name,
#                     "image": image,
#                     "image_tag": image_tag,
#                 }

#             # Добавление статуса
#             if resource_type == "deployments":
#                 resource_dict["status"] = get_deployment_status(resource_dict)
#             elif resource_type == "statefulsets":
#                 resource_dict["status"] = get_statefulset_status(resource_dict)

#             # Добавление информации о контроллере для WebSocket
#             resource_dict["controller_type"] = "deployment" if resource_type == "deployments" else "statefulset"

#         elif resource_type == "namespaces":
#             # Обработка неймспейсов
#             status = obj.status
#             resource_dict.update({
#                 "phase": status.phase if status else "Unknown",
#             })
#             # Удаление namespace для неймспейсов, так как это не имеет смысла
#             resource_dict.pop("namespace", None)

#         return resource_dict

#     except Exception as e:
#         logger.error(f"Ошибка при преобразовании {resource_type} в словарь: {str(e)}")
#         # Возвращаем базовую информацию, если не удалось преобразовать
#         return {
#             "name": getattr(obj.metadata, "name", "unknown"),
#             "namespace": getattr(obj.metadata, "namespace", None),
#             "error": f"Ошибка преобразования: {str(e)}"
#         }
