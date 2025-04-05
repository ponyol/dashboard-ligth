"""Модуль для работы с метриками Kubernetes."""

import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from kubernetes.client.exceptions import ApiException

from dashboard_light.k8s.cache import with_cache

logger = logging.getLogger(__name__)


def parse_cpu_value(cpu_str: Optional[str]) -> Optional[int]:
    """Преобразование значения CPU из формата Kubernetes (n, m, k, M, G)
    в миллиядра (millicores).

    Args:
        cpu_str: Строка со значением CPU

    Returns:
        Optional[int]: Значение CPU в миллиядрах или None при ошибке
    """
    if not cpu_str:
        return None

    try:
        # Значение с суффиксом "m" (миллиядра)
        if match := re.match(r"(\d+)m", cpu_str):
            return int(match.group(1))

        # Целочисленное значение без суффикса (ядра)
        if match := re.match(r"(\d+)$", cpu_str):
            return int(match.group(1)) * 1000

        # Дробное значение без суффикса (ядра)
        if match := re.match(r"(\d+\.\d+)$", cpu_str):
            return int(float(match.group(1)) * 1000)

        return None
    except Exception as e:
        logger.warning(f"Не удалось преобразовать значение CPU: {cpu_str}, ошибка: {str(e)}")
        return None


def parse_memory_value(mem_str: Optional[str]) -> Optional[float]:
    """Преобразование значения памяти из формата Kubernetes (Ki, Mi, Gi)
    в мегабайты (MB).

    Args:
        mem_str: Строка со значением памяти

    Returns:
        Optional[float]: Значение памяти в мегабайтах или None при ошибке
    """
    if not mem_str:
        return None

    try:
        # Значение с суффиксом "Mi" (мебибайты)
        if match := re.match(r"(\d+)Mi", mem_str):
            return float(match.group(1))

        # Значение с суффиксом "Gi" (гибибайты)
        if match := re.match(r"(\d+)Gi", mem_str):
            return float(match.group(1)) * 1024

        # Значение с суффиксом "Ki" (кибибайты)
        if match := re.match(r"(\d+)Ki", mem_str):
            return float(match.group(1)) / 1024

        # Значение с суффиксом "M" (мегабайты)
        if match := re.match(r"(\d+)M", mem_str):
            return float(match.group(1))

        # Значение с суффиксом "G" (гигабайты)
        if match := re.match(r"(\d+)G", mem_str):
            return float(match.group(1)) * 1024

        # Байты без суффикса
        if match := re.match(r"(\d+)$", mem_str):
            return float(match.group(1)) / (1024 * 1024)

        return None
    except Exception as e:
        logger.warning(f"Не удалось преобразовать значение памяти: {mem_str}, ошибка: {str(e)}")
        return None


@with_cache("metrics")
def list_pod_metrics_for_namespace(k8s_client: Dict[str, Any], namespace: str) -> List[Dict[str, Any]]:
    """Получение метрик Pod из Metrics Server для указанного пространства имен.

    Args:
        k8s_client: Словарь с Kubernetes клиентом и API
        namespace: Имя пространства имен

    Returns:
        List[Dict[str, Any]]: Список метрик для Pods
    """
    try:
        logger.debug(f"Получение метрик для неймспейса {namespace}")
        start_time = time.time()

        custom_objects_api = k8s_client.get("custom_objects_api")

        if not custom_objects_api:
            logger.warning(f"K8S: API клиент для CustomObjects не инициализирован, "
                          f"возвращаем пустой список для {namespace}")
            return []

        # Параметры для запроса метрик
        metrics_group = "metrics.k8s.io"
        metrics_version = "v1beta1"
        metrics_plural = "pods"

        # Выполнение запроса к Metrics Server
        result = custom_objects_api.list_namespaced_custom_object(
            group=metrics_group,
            version=metrics_version,
            namespace=namespace,
            plural=metrics_plural
        )

        if not result or "items" not in result:
            logger.info(f"K8S: Нет метрик для подов в неймспейсе {namespace}")
            return []

        items = result.get("items", [])

        # Преобразование в словари с нужными полями
        metrics_data = []
        for item in items:
            metadata = item.get("metadata", {})
            containers = item.get("containers", [])

            # Обработка метрик контейнеров
            container_metrics = []
            for container in containers:
                name = container.get("name", "")
                usage = container.get("usage", {})

                # Преобразование значений CPU и памяти
                cpu = usage.get("cpu")
                memory = usage.get("memory")
                cpu_millicores = parse_cpu_value(cpu)
                memory_mb = parse_memory_value(memory)

                container_metrics.append({
                    "name": name,
                    "resource_usage": {
                        "cpu": cpu,
                        "memory": memory,
                        "cpu_millicores": cpu_millicores,
                        "memory_mb": memory_mb,
                    }
                })

            # Формирование данных о метриках пода
            pod_metrics = {
                "name": metadata.get("name"),
                "namespace": metadata.get("namespace"),
                "containers": container_metrics,
                "timestamp": metadata.get("timestamp"),
            }

            metrics_data.append(pod_metrics)

        duration = time.time() - start_time
        logger.debug(f"Получение метрик для неймспейса {namespace} выполнено за {duration:.3f} сек")

        return metrics_data
    except ApiException as e:
        logger.error(f"K8S: Ошибка API при получении метрик: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"K8S: Ошибка получения метрик Pod: {str(e)}")
        return []


def get_pod_metrics_by_name(k8s_client: Dict[str, Any], namespace: str, pod_name: str) -> Optional[Dict[str, Any]]:
    """Получение метрик для конкретного Pod по имени.

    Args:
        k8s_client: Словарь с Kubernetes клиентом и API
        namespace: Имя пространства имен
        pod_name: Имя Pod

    Returns:
        Optional[Dict[str, Any]]: Метрики Pod или None, если метрики не найдены
    """
    try:
        # Получение метрик для всех подов в неймспейсе
        metrics_data = list_pod_metrics_for_namespace(k8s_client, namespace)

        # Поиск метрик для указанного пода
        pod_metrics = next((m for m in metrics_data if m.get("name") == pod_name), None)

        if pod_metrics:
            # Расчет возраста метрик
            timestamp = pod_metrics.get("timestamp")
            if timestamp:
                try:
                    # Преобразование строки timestamp в datetime
                    if isinstance(timestamp, str):
                        timestamp_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    else:
                        timestamp_dt = timestamp

                    # Расчет возраста в секундах
                    now = datetime.now().astimezone()
                    age_seconds = (now - timestamp_dt).total_seconds()

                    # Добавление возраста к метрикам
                    pod_metrics["age_seconds"] = age_seconds
                except Exception as e:
                    logger.warning(f"Ошибка при расчете возраста метрик: {str(e)}")

        return pod_metrics
    except Exception as e:
        logger.error(f"Ошибка при получении метрик для пода {pod_name}: {str(e)}")
        return None


def get_total_pod_resource_usage(pod_metrics: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Получение суммарного использования ресурсов для пода.

    Args:
        pod_metrics: Метрики Pod

    Returns:
        Dict[str, Any]: Суммарное использование ресурсов
    """
    if not pod_metrics:
        return {"cpu_millicores": 0, "memory_mb": 0}

    containers = pod_metrics.get("containers", [])

    # Суммирование метрик по всем контейнерам
    cpu_total = sum(
        container.get("resource_usage", {}).get("cpu_millicores", 0) or 0
        for container in containers
    )

    memory_total = sum(
        container.get("resource_usage", {}).get("memory_mb", 0) or 0
        for container in containers
    )

    return {"cpu_millicores": cpu_total, "memory_mb": memory_total}
