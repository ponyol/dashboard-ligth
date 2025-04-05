"""Модуль для работы с деплойментами Kubernetes."""

import logging
import re
from typing import Any, Dict, List, Optional

from kubernetes import client
from kubernetes.client.exceptions import ApiException

from dashboard_light.k8s.cache import with_cache

logger = logging.getLogger(__name__)


@with_cache("deployments")
def list_deployments_for_namespace(k8s_client: Dict[str, Any], namespace: str) -> List[Dict[str, Any]]:
    """Получение списка Deployments в указанном пространстве имен.

    Args:
        k8s_client: Словарь с Kubernetes клиентом и API
        namespace: Имя пространства имен

    Returns:
        List[Dict[str, Any]]: Список данных о Deployments
    """
    try:
        apps_v1_api = k8s_client.get("apps_v1_api")

        if not apps_v1_api:
            logger.warning(f"K8S: API клиент для Apps/v1 не инициализирован, "
                          f"возвращаем пустой список для {namespace}")
            return []

        result = apps_v1_api.list_namespaced_deployment(namespace=namespace)

        if not result or not result.items:
            logger.info(f"K8S: Нет Deployments в неймспейсе {namespace}")
            return []

        # Преобразование в словари с нужными полями
        deployments = []
        for item in result.items:
            metadata = item.metadata
            spec = item.spec
            status = item.status

            # Получение информации о контейнерах
            containers = []
            if spec.template and spec.template.spec and spec.template.spec.containers:
                containers = spec.template.spec.containers

            main_container = containers[0] if containers else None

            # Формирование данных о деплойменте
            deployment_data = {
                "name": metadata.name,
                "namespace": metadata.namespace,
                "replicas": {
                    "desired": spec.replicas,
                    "ready": status.ready_replicas if status.ready_replicas else 0,
                    "available": status.available_replicas if status.available_replicas else 0,
                    "updated": status.updated_replicas if status.updated_replicas else 0,
                }
            }

            # Добавление информации о главном контейнере, если он есть
            if main_container:
                image = main_container.image
                image_tag = image.split(":")[-1] if ":" in image else "latest"

                deployment_data["main_container"] = {
                    "name": main_container.name,
                    "image": image,
                    "image_tag": image_tag,
                }

            # Добавление лейблов
            if metadata.labels:
                deployment_data["labels"] = metadata.labels

            deployments.append(deployment_data)

        return deployments
    except ApiException as e:
        logger.error(f"K8S: Ошибка API при получении Deployments: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"K8S: Ошибка получения списка Deployments: {str(e)}")
        return []


def list_deployments_multi_ns(k8s_client: Dict[str, Any], namespaces: List[str]) -> List[Dict[str, Any]]:
    """Получение списка Deployments для нескольких пространств имен.

    Args:
        k8s_client: Словарь с Kubernetes клиентом и API
        namespaces: Список имен пространств имен

    Returns:
        List[Dict[str, Any]]: Объединенный список данных о Deployments
    """
    deployments = []
    for namespace in namespaces:
        namespace_deployments = list_deployments_for_namespace(k8s_client, namespace)
        deployments.extend(namespace_deployments)

    return deployments


def get_deployment_status(deployment: Dict[str, Any]) -> str:
    """Определение статуса Deployment на основе его параметров.

    Args:
        deployment: Данные о Deployment

    Returns:
        str: Статус Deployment (healthy, progressing, scaled_zero, error)
    """
    desired = deployment.get("replicas", {}).get("desired")
    ready = deployment.get("replicas", {}).get("ready", 0)

    if desired is None:
        return "error"
    elif desired == 0:
        return "scaled_zero"
    elif ready == desired:
        return "healthy"
    else:
        return "progressing"
