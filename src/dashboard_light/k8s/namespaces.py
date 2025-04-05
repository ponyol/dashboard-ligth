"""Модуль для работы с неймспейсами Kubernetes."""

import logging
import re
from typing import Any, Dict, List, Optional

from kubernetes import client
from kubernetes.client.exceptions import ApiException

from dashboard_light.k8s.cache import with_cache

logger = logging.getLogger(__name__)

# Тестовые данные для режима разработки
TEST_NAMESPACES = [
    {"name": "default", "phase": "Active", "created": "2025-01-01T00:00:00Z", "labels": {}},
    {"name": "kube-system", "phase": "Active", "created": "2025-01-01T00:00:00Z", "labels": {}},
    {"name": "project-app1-staging", "phase": "Active", "created": "2025-01-01T00:00:00Z", "labels": {"env": "staging"}},
    {"name": "project-app2-prod", "phase": "Active", "created": "2025-01-01T00:00:00Z", "labels": {"env": "production"}},
]

@with_cache("namespaces")
def list_namespaces(k8s_client: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Получение списка всех неймспейсов в кластере.

    Args:
        k8s_client: Словарь с Kubernetes клиентом и API

    Returns:
        List[Dict[str, Any]]: Список данных о неймспейсах
    """
    # Проверяем, в режиме мока мы или нет
    if k8s_client.get("is_mock", False):
        logger.info("K8S: Работаем в режиме мока, возвращаем тестовые данные")
        return TEST_NAMESPACES

    try:
        logger.info("K8S: Запрос списка неймспейсов из Kubernetes API")
        core_v1_api = k8s_client.get("core_v1_api")

        if not core_v1_api:
            logger.warning("K8S: API клиент не инициализирован, возвращаем тестовые данные")
            return TEST_NAMESPACES

        result = core_v1_api.list_namespace()

        if not result or not result.items:
            logger.warning("K8S: Результат запроса неймспейсов пуст, возвращаем тестовые данные")
            return TEST_NAMESPACES

        items = result.items
        logger.info(f"K8S: Получено элементов: {len(items)}")

        # Преобразование в словари с нужными полями
        namespaces = [
            {
                "name": item.metadata.name,
                "phase": item.status.phase,
                "created": item.metadata.creation_timestamp.isoformat()
                    if item.metadata.creation_timestamp else None,
                "labels": item.metadata.labels if item.metadata.labels else {},
            }
            for item in items
        ]

        return namespaces
    except ApiException as e:
        logger.error(f"K8S: Ошибка API при получении списка неймспейсов: {str(e)}")
        return TEST_NAMESPACES
    except Exception as e:
        logger.error(f"K8S: Ошибка получения списка неймспейсов: {str(e)}")
        return TEST_NAMESPACES


def filter_namespaces_by_pattern(namespaces: List[Dict[str, Any]],
                                patterns: List[str]) -> List[Dict[str, Any]]:
    """Фильтрация неймспейсов по списку регулярных выражений.

    Args:
        namespaces: Список данных о неймспейсах
        patterns: Список регулярных выражений для фильтрации

    Returns:
        List[Dict[str, Any]]: Отфильтрованный список данных о неймспейсах
    """
    # Если паттерны пустые или есть ".*", возвращаем все неймспейсы
    if not patterns or any(pattern == ".*" for pattern in patterns):
        return namespaces

    # Компиляция регулярных выражений для оптимизации
    compiled_patterns = [re.compile(pattern) for pattern in patterns]

    # Фильтрация неймспейсов
    filtered = [
        namespace for namespace in namespaces
        if any(pattern.match(namespace["name"]) for pattern in compiled_patterns)
    ]

    return filtered


def list_filtered_namespaces(k8s_client: Dict[str, Any],
                           patterns: List[str]) -> List[Dict[str, Any]]:
    """Получение отфильтрованных неймспейсов по списку регулярных выражений.

    Args:
        k8s_client: Словарь с Kubernetes клиентом и API
        patterns: Список регулярных выражений для фильтрации

    Returns:
        List[Dict[str, Any]]: Отфильтрованный список данных о неймспейсах
    """
    all_namespaces = list_namespaces(k8s_client)
    return filter_namespaces_by_pattern(all_namespaces, patterns)
