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
        
        # Проверка режима эмуляции
        use_mock = os.environ.get("K8S_MOCK", "").lower() in ["true", "1", "yes", "y"]
        logger.info(f"Режим эмуляции K8s (MOCK): {use_mock}")

        if use_mock:
            logger.info("Используется MOCK-клиент Kubernetes")
            api_client = client.ApiClient()
            return {
                "is_mock": True,
                "api_client": None,
                "core_v1_api": None,
                "apps_v1_api": None,
                "custom_objects_api": None,
            }
            
        # Проверяем переменные для доступа к K8s
        kubeconfig_env = os.environ.get("KUBECONFIG")
        kubeconfig_fallback = os.path.expanduser("~/.kube/config")
        
        if kubeconfig_env:
            logger.info(f"Найдена переменная KUBECONFIG: {kubeconfig_env}")
        elif os.path.exists(kubeconfig_fallback):
            logger.info(f"Найден стандартный kubeconfig: {kubeconfig_fallback}")
            
        # Пробуем разные методы подключения
        config_attempts = [
            # Метод 1: Подключение изнутри кластера
            {
                "name": "in-cluster config",
                "loader": config.load_incluster_config,
                "args": [],
                "kwargs": {}
            },
            # Метод 2: Подключение через kubeconfig
            {
                "name": "kubeconfig",
                "loader": config.load_kube_config,
                "args": [],
                "kwargs": {}
            }
        ]
        
        api_client = None
        success_method = None
        errors = []
        
        for method in config_attempts:
            try:
                logger.info(f"Попытка загрузки конфигурации K8s через {method['name']}...")
                method["loader"](*method["args"], **method["kwargs"])
                api_client = client.ApiClient()
                success_method = method["name"]
                logger.info(f"Успешно загружена конфигурация через {method['name']}")
                break
            except Exception as e:
                error_msg = str(e)
                logger.info(f"Не удалось загрузить конфигурацию через {method['name']}: {error_msg}")
                errors.append(f"{method['name']}: {error_msg}")
                
        if not api_client:
            error_details = "\n".join(errors)
            logger.error(f"Не удалось загрузить конфигурацию K8s ни одним из способов:\n{error_details}")
            raise RuntimeError("Ошибка загрузки конфигурации Kubernetes")
            
        # Создание API клиентов для различных ресурсов
        core_v1_api = client.CoreV1Api(api_client)
        apps_v1_api = client.AppsV1Api(api_client)
        custom_objects_api = client.CustomObjectsApi(api_client)

        # Проверка доступа к API
        try:
            namespaces = core_v1_api.list_namespace(limit=5)
            logger.info(f"Kubernetes API аутентификация успешна! "
                       f"Найдено неймспейсов (пример): {[ns.metadata.name for ns in namespaces.items[:5]]}")
                
            # Проверка возможности наблюдения за ресурсами (watch)
            # Это важно для подтверждения, что API поддерживает watch
            watch_test = watch.Watch()
            watch_count = 0
            logger.info("Тестирование Watch API...")
            for _ in watch_test.stream(core_v1_api.list_namespace, timeout_seconds=1, limit=1):
                watch_count += 1
                # Получаем только одно событие для проверки
                break
            watch_test.stop()
                
            if watch_count > 0:
                logger.info("Watch API работает корректно!")
            else:
                logger.warning("Watch API не вернул ни одного события. Возможны проблемы с обновлениями в реальном времени.")
        except Exception as e:
            logger.warning(f"Не удалось получить список неймспейсов: {str(e)}")
            logger.warning("API подключение создано, но доступ к Kubernetes API может быть ограничен.")

        # Возвращаем словарь с клиентами API
        return {
            "api_client": api_client,
            "core_v1_api": core_v1_api,
            "apps_v1_api": apps_v1_api,
            "custom_objects_api": custom_objects_api,
            "connection_method": success_method
        }
    except Exception as e:
        logger.error(f"Критическая ошибка при создании Kubernetes API клиента: {str(e)}")
        logger.exception("Подробности ошибки:")
        raise  # Пробрасываем ошибку дальше, чтобы приложение знало о проблеме с K8s API


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
