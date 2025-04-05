"""Модуль для работы с подами Kubernetes."""

import logging
import re
from typing import Any, Dict, List, Optional

from kubernetes.client.exceptions import ApiException

from dashboard_light.k8s.cache import with_cache

logger = logging.getLogger(__name__)


@with_cache("pods")
def list_pods_for_namespace(k8s_client: Dict[str, Any], namespace: str,
                          label_selector: Optional[str] = None) -> List[Dict[str, Any]]:
    """Получение списка Pods в указанном пространстве имен.

    Args:
        k8s_client: Словарь с Kubernetes клиентом и API
        namespace: Имя пространства имен
        label_selector: Селектор лейблов для фильтрации

    Returns:
        List[Dict[str, Any]]: Список данных о Pods
    """
    try:
        core_v1_api = k8s_client.get("core_v1_api")

        if not core_v1_api:
            logger.warning(f"K8S: API клиент для Core/v1 не инициализирован, "
                          f"возвращаем пустой список для {namespace}")
            return []

        result = core_v1_api.list_namespaced_pod(
            namespace=namespace,
            label_selector=label_selector
        )

        if not result or not result.items:
            logger.info(f"K8S: Нет Pods в неймспейсе {namespace}")
            return []

        # Преобразование в словари с нужными полями
        pods_data = []
        for item in result.items:
            metadata = item.metadata
            spec = item.spec
            status = item.status

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
            pod_data = {
                "name": metadata.name,
                "namespace": metadata.namespace,
                "phase": status.phase if status else "Unknown",
                "containers": containers,
                "pod_ip": status.pod_ip if status else None,
                "host_ip": status.host_ip if status else None,
                "started_at": status.start_time.isoformat() if status and status.start_time else None,
            }

            # Добавление лейблов
            if metadata.labels:
                pod_data["labels"] = metadata.labels

            # Добавление информации о владельце (owner references)
            if metadata.owner_references:
                owner_refs = []
                for ref in metadata.owner_references:
                    owner_refs.append({
                        "name": ref.name,
                        "kind": ref.kind,
                        "uid": ref.uid,
                    })
                pod_data["owner_references"] = owner_refs

            pods_data.append(pod_data)

        return pods_data
    except ApiException as e:
        logger.error(f"K8S: Ошибка API при получении Pods: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"K8S: Ошибка получения списка Pods: {str(e)}")
        return []


def list_deployment_pods(k8s_client: Dict[str, Any], namespace: str, deployment_name: str) -> List[Dict[str, Any]]:
    """Получение списка Pods, принадлежащих указанному Deployment.

    Args:
        k8s_client: Словарь с Kubernetes клиентом и API
        namespace: Имя пространства имен
        deployment_name: Имя Deployment

    Returns:
        List[Dict[str, Any]]: Список данных о Pods
    """
    # Получение всех подов в неймспейсе
    pods_data = list_pods_for_namespace(k8s_client, namespace)

    # Фильтрация подов, принадлежащих деплойменту через ReplicaSet
    deployment_pods = []
    for pod in pods_data:
        owner_references = pod.get("owner_references", [])

        # Проверка, принадлежит ли под ReplicaSet'у этого деплоймента
        for ref in owner_references:
            if ref.get("kind") == "ReplicaSet" and ref.get("name", "").startswith(deployment_name + "-"):
                deployment_pods.append(pod)
                break

    return deployment_pods


def get_pod_status(pod: Dict[str, Any]) -> str:
    """Получение статуса Pod.

    Args:
        pod: Данные о Pod

    Returns:
        str: Статус Pod (running, succeeded, pending, failed, terminating, error)
    """
    phase = pod.get("phase", "").lower()

    if phase == "running":
        return "running"
    elif phase == "succeeded":
        return "succeeded"
    elif phase == "pending":
        return "pending"
    elif phase == "failed":
        return "failed"
    elif phase == "terminating" or "terminating" in phase:
        return "terminating"
    else:
        return "error"
