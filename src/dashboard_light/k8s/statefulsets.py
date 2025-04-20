"""Модуль для работы с StatefulSets Kubernetes."""

import logging
import re
from typing import Any, Dict, List, Optional

from kubernetes import client
from kubernetes.client.exceptions import ApiException

from dashboard_light.k8s.cache import with_cache

logger = logging.getLogger(__name__)

# Тестовые данные для режима разработки
TEST_STATEFULSETS = [
    {
        "name": "test-statefulset-1",
        "namespace": "default",
        "replicas": {
            "desired": 3,
            "ready": 3,
            "updated": 3,
            "available": 3,
        },
        "main_container": {
            "name": "test-container-1",
            "image": "redis:latest",
            "image_tag": "latest",
        },
        "labels": {"app": "test-db-1"},
        "status": "healthy"
    },
    {
        "name": "test-statefulset-2",
        "namespace": "default",
        "replicas": {
            "desired": 2,
            "ready": 1,
            "updated": 1,
            "available": 1,
        },
        "main_container": {
            "name": "test-container-2",
            "image": "postgres:latest",
            "image_tag": "latest",
        },
        "labels": {"app": "test-db-2"},
        "status": "progressing"
    },
    {
        "name": "test-statefulset-3",
        "namespace": "default",
        "replicas": {
            "desired": 0,
            "ready": 0,
            "updated": 0,
            "available": 0,
        },
        "main_container": {
            "name": "test-container-3",
            "image": "mysql:latest",
            "image_tag": "latest",
        },
        "labels": {"app": "test-db-3"},
        "status": "scaled_zero"
    },
    {
        "name": "db-statefulset",
        "namespace": "project-app1-staging",
        "replicas": {
            "desired": 1,
            "ready": 1,
            "updated": 1,
            "available": 1,
        },
        "main_container": {
            "name": "db-main",
            "image": "registry-minor:5000/project/postgres:staging-a1dcf6ff",
            "image_tag": "staging-a1dcf6ff",
        },
        "labels": {"app": "project-db"},
        "status": "healthy"
    }
]

@with_cache("statefulsets")
def list_statefulsets_for_namespace(k8s_client: Dict[str, Any], namespace: str) -> List[Dict[str, Any]]:
    """Получение списка StatefulSets в указанном пространстве имен.

    Args:
        k8s_client: Словарь с Kubernetes клиентом и API
        namespace: Имя пространства имен

    Returns:
        List[Dict[str, Any]]: Список данных о StatefulSets
    """
    # Проверяем, в режиме мока мы или нет
    if k8s_client.get("is_mock", False):
        logger.info(f"K8S: Работаем в режиме мока, возвращаем тестовые данные для неймспейса {namespace}")
        # Возвращаем только те тестовые StatefulSets, которые в указанном неймспейсе
        return [s for s in TEST_STATEFULSETS if s["namespace"] == namespace or namespace == ""]

    try:
        apps_v1_api = k8s_client.get("apps_v1_api")

        if not apps_v1_api:
            logger.warning(f"K8S: API клиент для Apps/v1 не инициализирован, "
                          f"возвращаем пустой список для {namespace}")
            return []

        result = apps_v1_api.list_namespaced_stateful_set(namespace=namespace)

        if not result or not result.items:
            logger.info(f"K8S: Нет StatefulSets в неймспейсе {namespace}")
            return []

        # Преобразование в словари с нужными полями
        statefulsets = []
        for item in result.items:
            metadata = item.metadata
            spec = item.spec
            status = item.status

            # Получение информации о контейнерах
            containers = []
            if spec.template and spec.template.spec and spec.template.spec.containers:
                containers = spec.template.spec.containers

            main_container = containers[0] if containers else None

            # Формирование данных о StatefulSet
            statefulset_data = {
                "name": metadata.name,
                "namespace": metadata.namespace,
                "replicas": {
                    "desired": spec.replicas,
                    "ready": status.ready_replicas if status.ready_replicas else 0,
                    "updated": status.updated_replicas if status.updated_replicas else 0,
                    "available": status.ready_replicas if status.ready_replicas else 0,  # Для statefulset считаем available = ready
                }
            }

            # Добавление информации о главном контейнере, если он есть
            if main_container:
                image = main_container.image
                image_tag = image.split(":")[-1] if ":" in image else "latest"

                statefulset_data["main_container"] = {
                    "name": main_container.name,
                    "image": image,
                    "image_tag": image_tag,
                }

            # Добавление лейблов
            if metadata.labels:
                statefulset_data["labels"] = metadata.labels

            statefulsets.append(statefulset_data)

        return statefulsets
    except ApiException as e:
        logger.error(f"K8S: Ошибка API при получении StatefulSets: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"K8S: Ошибка получения списка StatefulSets: {str(e)}")
        return []


def list_statefulsets_multi_ns(k8s_client: Dict[str, Any], namespaces: List[str]) -> List[Dict[str, Any]]:
    """Получение списка StatefulSets для нескольких пространств имен."""
    # Проверяем, в режиме мока мы или нет
    if k8s_client.get("is_mock", False):
        logger.info(f"K8S: Работаем в режиме мока, возвращаем тестовые данные для неймспейсов {namespaces}")
        # Если список неймспейсов пуст или содержит пустую строку, возвращаем все
        if not namespaces or "" in namespaces:
            return TEST_STATEFULSETS
        # Иначе фильтруем по указанным неймспейсам
        return [s for s in TEST_STATEFULSETS if s["namespace"] in namespaces]

    statefulsets = []
    for namespace in namespaces:
        namespace_statefulsets = list_statefulsets_for_namespace(k8s_client, namespace)
        statefulsets.extend(namespace_statefulsets)

    return statefulsets


def get_statefulset_status(statefulset: Dict[str, Any]) -> str:
    """Определение статуса StatefulSet на основе его параметров.

    Args:
        statefulset: Данные о StatefulSet

    Returns:
        str: Статус StatefulSet (healthy, progressing, scaled_zero, error)
    """
    desired = statefulset.get("replicas", {}).get("desired")
    ready = statefulset.get("replicas", {}).get("ready", 0)

    if desired is None:
        return "error"
    elif desired == 0:
        return "scaled_zero"
    elif ready == desired:
        return "healthy"
    else:
        return "progressing"
