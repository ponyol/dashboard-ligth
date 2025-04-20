#!/usr/bin/env python
"""Тестовый скрипт для проверки API Streaming."""

import asyncio
import logging
import os
import sys
from typing import Dict, Any

# Добавляем родительскую директорию в путь для импорта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dashboard_light.config import core as config
from dashboard_light.k8s import core as k8s
from dashboard_light.state_manager import subscribe, get_resources_by_type
from dashboard_light.k8s.watch import start_watching, stop_watching

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Обработчик событий ресурсов
async def resource_handler(event_type: str, resource_type: str, resource_data: Dict[str, Any]) -> None:
    """Обрабатывает события ресурсов из state_manager."""
    name = resource_data.get('name', 'no-name')
    namespace = resource_data.get('namespace', 'no-namespace')
    logger.info(f"СОБЫТИЕ: {event_type} - {resource_type}/{namespace}/{name}")

    # Показываем некоторые детали ресурса в зависимости от типа
    if resource_type == 'deployments':
        replicas = resource_data.get('replicas', {})
        status = resource_data.get('status', 'unknown')
        logger.info(f"  Статус: {status}, Реплики: {replicas.get('ready', 0)}/{replicas.get('desired', 0)}")

        # Показать контейнер, если есть
        if 'main_container' in resource_data:
            container = resource_data['main_container']
            logger.info(f"  Контейнер: {container.get('name')} [{container.get('image_tag')}]")

    elif resource_type == 'pods':
        phase = resource_data.get('phase', 'Unknown')
        status = resource_data.get('status', 'unknown')
        logger.info(f"  Статус: {status}, Фаза: {phase}")

        # Показать IP, если есть
        pod_ip = resource_data.get('pod_ip')
        if pod_ip:
            logger.info(f"  Pod IP: {pod_ip}")

    elif resource_type == 'namespaces':
        phase = resource_data.get('phase', 'Unknown')
        created = resource_data.get('created', 'unknown')
        logger.info(f"  Фаза: {phase}, Создан: {created}")

async def main():
    """Основная функция для тестирования API Streaming."""
    try:
        # Загрузка конфигурации
        logger.info("Загрузка конфигурации...")
        try:
            app_config = config.load_config()
            logger.info("Конфигурация загружена успешно")
        except Exception as e:
            logger.warning(f"Не удалось загрузить конфигурацию, используем значения по умолчанию: {e}")
            app_config = {}

        # Инициализация Kubernetes клиента
        logger.info("Инициализация Kubernetes клиента...")
        k8s_client = k8s.create_k8s_client(app_config)
        logger.info("Kubernetes клиент инициализирован")

        # Подписка на события ресурсов
        logger.info("Подписка на события ресурсов...")
        unsubscribe_deployments = subscribe('deployments', resource_handler)
        unsubscribe_pods = subscribe('pods', resource_handler)
        unsubscribe_namespaces = subscribe('namespaces', resource_handler)

        # Запуск наблюдения
        logger.info("Запуск наблюдения за ресурсами...")
        watch_tasks = await start_watching(k8s_client, ['deployments', 'pods', 'namespaces'])
        logger.info(f"Наблюдение запущено для: {', '.join(watch_tasks.keys())}")

        # Вывод начального состояния через 5 секунд (даем время на загрузку начальных данных)
        await asyncio.sleep(5)
        logger.info("=== НАЧАЛЬНОЕ СОСТОЯНИЕ ===")

        deployments = get_resources_by_type('deployments')
        logger.info(f"Deployments: {len(deployments)}")

        pods = get_resources_by_type('pods')
        logger.info(f"Pods: {len(pods)}")

        namespaces = get_resources_by_type('namespaces')
        logger.info(f"Namespaces: {len(namespaces)}")

        # Ждем изменений и наблюдаем
        logger.info("\n=== ОЖИДАНИЕ СОБЫТИЙ ===")
        logger.info("Запустите kubectl create/delete/update команды, чтобы увидеть события")
        logger.info("Нажмите Ctrl+C для выхода...")

        # Бесконечный цикл (до Ctrl+C)
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Получен сигнал завершения")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
    finally:
        # Остановка наблюдения
        logger.info("Остановка наблюдения...")
        await stop_watching()
        logger.info("Наблюдение остановлено")

        # Отмена подписок
        unsubscribe_deployments()
        unsubscribe_pods()
        unsubscribe_namespaces()
        logger.info("Подписки отменены")

if __name__ == "__main__":
    asyncio.run(main())
