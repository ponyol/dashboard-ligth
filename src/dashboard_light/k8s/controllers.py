"""Модуль для обобщенной работы с контроллерами Kubernetes (Deployments и StatefulSets)."""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Callable

from dashboard_light.k8s import deployments, statefulsets
from dashboard_light.k8s.cache import with_cache

logger = logging.getLogger(__name__)

# Тип контроллера
CONTROLLER_TYPE_DEPLOYMENT = "deployment"
CONTROLLER_TYPE_STATEFULSET = "statefulset"


def list_controllers_for_namespace(
    k8s_client: Dict[str, Any],
    namespace: str
) -> List[Dict[str, Any]]:
    """Получение списка контроллеров (Deployments и StatefulSets) в указанном пространстве имен.

    Args:
        k8s_client: Словарь с Kubernetes клиентом и API
        namespace: Имя пространства имен

    Returns:
        List[Dict[str, Any]]: Список данных о контроллерах
    """
    # Получаем deployments
    deployment_items = deployments.list_deployments_for_namespace(k8s_client, namespace)
    # Добавляем тип контроллера и статус
    for item in deployment_items:
        item["controller_type"] = CONTROLLER_TYPE_DEPLOYMENT
        item["status"] = deployments.get_deployment_status(item)

    # Получаем statefulsets
    statefulset_items = statefulsets.list_statefulsets_for_namespace(k8s_client, namespace)
    # Добавляем тип контроллера и статус
    for item in statefulset_items:
        item["controller_type"] = CONTROLLER_TYPE_STATEFULSET
        item["status"] = statefulsets.get_statefulset_status(item)

    # Объединяем списки
    return deployment_items + statefulset_items


def list_controllers_multi_ns(
    k8s_client: Dict[str, Any],
    namespaces: List[str]
) -> List[Dict[str, Any]]:
    """Получение списка контроллеров (Deployments и StatefulSets) для нескольких пространств имен.

    Args:
        k8s_client: Словарь с Kubernetes клиентом и API
        namespaces: Список имен пространств имен

    Returns:
        List[Dict[str, Any]]: Список данных о контроллерах
    """
    controllers = []

    # Если список пустой, вернуть пустой список
    if not namespaces:
        return []

    # Если есть пустая строка, то получаем все контроллеры для всех неймспейсов
    if "" in namespaces:
        # Получаем все deployments
        deployment_items = deployments.list_deployments_multi_ns(k8s_client, [""])
        # Добавляем тип контроллера и статус
        for item in deployment_items:
            item["controller_type"] = CONTROLLER_TYPE_DEPLOYMENT
            item["status"] = deployments.get_deployment_status(item)
        controllers.extend(deployment_items)

        # Получаем все statefulsets
        statefulset_items = statefulsets.list_statefulsets_multi_ns(k8s_client, [""])
        # Добавляем тип контроллера и статус
        for item in statefulset_items:
            item["controller_type"] = CONTROLLER_TYPE_STATEFULSET
            item["status"] = statefulsets.get_statefulset_status(item)
        controllers.extend(statefulset_items)
    else:
        # Иначе получаем контроллеры для указанных неймспейсов
        for namespace in namespaces:
            ns_controllers = list_controllers_for_namespace(k8s_client, namespace)
            controllers.extend(ns_controllers)

    return controllers


def filter_controllers_by_patterns(
    controllers: List[Dict[str, Any]],
    patterns: List[str]
) -> List[Dict[str, Any]]:
    """Фильтрация контроллеров по списку регулярных выражений имен.

    Args:
        controllers: Список данных о контроллерах
        patterns: Список регулярных выражений для фильтрации по имени

    Returns:
        List[Dict[str, Any]]: Отфильтрованный список данных о контроллерах
    """
    # Если паттерны пустые или есть ".*", возвращаем все контроллеры
    if not patterns or any(pattern == ".*" for pattern in patterns):
        return controllers

    # Компиляция регулярных выражений для оптимизации
    compiled_patterns = [re.compile(pattern) for pattern in patterns]

    # Фильтрация контроллеров
    filtered = [
        controller for controller in controllers
        if any(pattern.match(controller["name"]) for pattern in compiled_patterns)
    ]

    return filtered


def get_controller_by_name_and_namespace(
    k8s_client: Dict[str, Any],
    namespace: str,
    name: str
) -> Tuple[Optional[Dict[str, Any]], str]:
    """Получение контроллера по имени и неймспейсу с определением типа контроллера.

    Args:
        k8s_client: Словарь с Kubernetes клиентом и API
        namespace: Имя пространства имен
        name: Имя контроллера

    Returns:
        Tuple[Optional[Dict[str, Any]], str]: Кортеж (контроллер, тип_контроллера)
    """
    # Сначала ищем среди Deployments
    deployment_list = deployments.list_deployments_for_namespace(k8s_client, namespace)
    for deployment in deployment_list:
        if deployment["name"] == name:
            deployment["controller_type"] = CONTROLLER_TYPE_DEPLOYMENT
            deployment["status"] = deployments.get_deployment_status(deployment)
            return deployment, CONTROLLER_TYPE_DEPLOYMENT

    # Если не нашли, ищем среди StatefulSets
    statefulset_list = statefulsets.list_statefulsets_for_namespace(k8s_client, namespace)
    for statefulset in statefulset_list:
        if statefulset["name"] == name:
            statefulset["controller_type"] = CONTROLLER_TYPE_STATEFULSET
            statefulset["status"] = statefulsets.get_statefulset_status(statefulset)
            return statefulset, CONTROLLER_TYPE_STATEFULSET

    # Если не нашли в обоих списках
    return None, ""


def get_controller_pods(
    k8s_client: Dict[str, Any],
    namespace: str,
    name: str,
    controller_type: str
) -> List[Dict[str, Any]]:
    """Получение подов, связанных с контроллером.

    Args:
        k8s_client: Словарь с Kubernetes клиентом и API
        namespace: Имя пространства имен
        name: Имя контроллера
        controller_type: Тип контроллера (deployment или statefulset)

    Returns:
        List[Dict[str, Any]]: Список подов контроллера
    """
    from dashboard_light.k8s import pods

    if controller_type == CONTROLLER_TYPE_DEPLOYMENT:
        return pods.list_deployment_pods(k8s_client, namespace, name)
    elif controller_type == CONTROLLER_TYPE_STATEFULSET:
        # Для StatefulSet ищем поды по селектору меток
        try:
            # Получаем StatefulSet
            apps_v1_api = k8s_client.get("apps_v1_api")
            statefulset = apps_v1_api.read_namespaced_stateful_set(name, namespace)

            # Получаем селектор меток
            selector = statefulset.spec.selector
            if not selector or not selector.match_labels:
                logger.warning(f"Не удалось получить селектор меток для StatefulSet {name}")
                return []

            # Формируем строку селектора
            label_selector = ",".join([f"{k}={v}" for k, v in selector.match_labels.items()])

            # Получаем поды по селектору
            pod_list = pods.list_pods_for_namespace(k8s_client, namespace, label_selector)
            return pod_list
        except Exception as e:
            logger.error(f"Ошибка при получении подов StatefulSet: {str(e)}")
            return []
    else:
        logger.warning(f"Неизвестный тип контроллера: {controller_type}")
        return []
