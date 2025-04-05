"""Основные функции для работы с Kubernetes API."""

import logging
import os
from typing import Any, Dict, Optional

from kubernetes import client, config

logger = logging.getLogger(__name__)


def create_k8s_client(app_config: Dict[str, Any]) -> Dict[str, Any]:
    """Создание Kubernetes API клиента.

    При запуске внутри кластера будет использовать serviceAccount,
    при запуске вне кластера - kubeconfig или переменные окружения.

    Args:
        app_config: Конфигурация приложения

    Returns:
        Dict[str, Any]: Словарь с Kubernetes клиентом и API
    """
    try:
        logger.info("Инициализация Kubernetes API клиента...")
        use_mock = os.environ.get("K8S_MOCK", "").lower() in ["true", "1", "yes", "y"]
        logger.info(f"Режим эмуляции K8s (MOCK): {use_mock}")

        if use_mock:
            logger.info("Используется MOCK-клиент Kubernetes")
            api_client = client.ApiClient()
        else:
            logger.info("Подключение к кластеру Kubernetes...")
            try:
                # Пытаемся загрузить конфигурацию из кластера
                config.load_incluster_config()
                logger.info("Успешно загружена конфигурация из кластера")
                api_client = client.ApiClient()
            except Exception as e:
                logger.info(f"Не удалось подключиться изнутри кластера: {str(e)}. "
                           "Пробуем локальную конфигурацию")
                # Пытаемся загрузить конфигурацию из kubeconfig
                config.load_kube_config()
                logger.info("Успешно загружена локальная конфигурация")
                api_client = client.ApiClient()

        # Создание API клиентов для различных ресурсов
        core_v1_api = client.CoreV1Api(api_client)
        apps_v1_api = client.AppsV1Api(api_client)
        custom_objects_api = client.CustomObjectsApi(api_client)

        # Проверка доступа к API
        try:
            namespaces = core_v1_api.list_namespace()
            logger.info(f"Kubernetes API аутентификация успешна. "
                       f"Найдено неймспейсов: {len(namespaces.items)}")
        except Exception as e:
            logger.warning(f"Не удалось получить список неймспейсов: {str(e)}")

        return {
            "api_client": api_client,
            "core_v1_api": core_v1_api,
            "apps_v1_api": apps_v1_api,
            "custom_objects_api": custom_objects_api,
        }
    except Exception as e:
        logger.error(f"Ошибка создания Kubernetes API клиента: {str(e)}")
        # Возвращаем минимальный набор для работы в режиме эмуляции
        api_client = client.ApiClient()
        return {
            "api_client": api_client,
            "core_v1_api": client.CoreV1Api(api_client),
            "apps_v1_api": client.AppsV1Api(api_client),
            "custom_objects_api": client.CustomObjectsApi(api_client),
        }


def cleanup_k8s_client(k8s_client: Dict[str, Any]) -> None:
    """Очистка ресурсов Kubernetes клиента.

    Args:
        k8s_client: Словарь с Kubernetes клиентом и API
    """
    if k8s_client and "api_client" in k8s_client:
        api_client = k8s_client["api_client"]
        if api_client:
            api_client.close()
            logger.info("Kubernetes API клиент закрыт")
