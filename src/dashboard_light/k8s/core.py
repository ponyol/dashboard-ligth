"""Основные функции для работы с Kubernetes API."""

import logging
import os
from typing import Any, Dict, Optional

from kubernetes import client, config

logger = logging.getLogger(__name__)

def create_k8s_client(app_config: Dict[str, Any]) -> Dict[str, Any]:
    """Создание Kubernetes API клиента."""
    try:
        logger.info("Инициализация Kubernetes API клиента...")

        # Проверка режима эмуляции
        use_mock = os.environ.get("K8S_MOCK", "").lower() in ["true", "1", "yes", "y"]

        if use_mock:
            logger.info("Используется MOCK-клиент Kubernetes")
            return {"is_mock": True, "api_client": None, "core_v1_api": None, "apps_v1_api": None, "custom_objects_api": None}

        # Используем простой и быстрый способ инициализации - только создание клиентов без тестовых запросов
        # Это критически ускорит старт приложения
        try:
            # Пытаемся загрузить конфигурацию из переменной окружения или стандартного пути
            config.load_kube_config()
            logger.info("Загружена конфигурация K8s из kubeconfig")
        except Exception:
            try:
                # Если не получилось, пробуем in-cluster config
                config.load_incluster_config()
                logger.info("Загружена in-cluster конфигурация K8s")
            except Exception as e:
                logger.error(f"Ошибка при загрузке конфигурации K8s: {e}")
                logger.warning("Используем mock-клиент из-за ошибки конфигурации")
                return {"is_mock": True, "api_client": None, "core_v1_api": None, "apps_v1_api": None, "custom_objects_api": None}

        # Создание API клиентов с ограниченным кэшированием
        api_client = client.ApiClient()
        core_v1_api = client.CoreV1Api(api_client)
        apps_v1_api = client.AppsV1Api(api_client)
        custom_objects_api = client.CustomObjectsApi(api_client)

        # Возвращаем словарь с клиентами API
        return {
            "api_client": api_client,
            "core_v1_api": core_v1_api,
            "apps_v1_api": apps_v1_api,
            "custom_objects_api": custom_objects_api,
            "connection_method": "kubeconfig"
        }
    except Exception as e:
        logger.error(f"Критическая ошибка при создании Kubernetes API клиента: {e}")
        logger.warning("Используем mock-клиент из-за критической ошибки")
        return {"is_mock": True, "api_client": None, "core_v1_api": None, "apps_v1_api": None, "custom_objects_api": None}

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
