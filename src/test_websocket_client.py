#!/usr/bin/env python
"""Консольный клиент для тестирования WebSocket API."""

import asyncio
import json
import logging
import sys
import argparse
import datetime
import signal
from typing import Dict, Any, Optional, Set

import websockets

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Множество активных подписок
subscriptions: Set[str] = set()

async def connect_websocket(url: str, resources: Dict[str, Optional[str]]) -> None:
    """Подключение к WebSocket и обработка сообщений.

    Args:
        url: WebSocket URL для подключения
        resources: Словарь ресурсов для подписки (тип ресурса -> namespace)
    """
    try:
        logger.info(f"Подключение к {url}...")

        async with websockets.connect(url) as websocket:
            logger.info(f"Подключено к {url}")

            # Настройка обработчика сигналов для корректного завершения
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(websocket)))

            # Подписка на ресурсы
            await subscribe_to_resources(websocket, resources)

            # Обработка входящих сообщений
            try:
                while True:
                    message = await websocket.recv()
                    await process_message(message)
            except websockets.exceptions.ConnectionClosedOK:
                logger.info("Соединение закрыто корректно")
            except websockets.exceptions.ConnectionClosedError as e:
                logger.error(f"Соединение закрыто с ошибкой: {e}")

    except websockets.exceptions.WebSocketException as e:
        logger.error(f"WebSocket ошибка: {e}")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {e}")

async def subscribe_to_resources(websocket, resources: Dict[str, Optional[str]]) -> None:
    """Подписка на указанные ресурсы.

    Args:
        websocket: WebSocket соединение
        resources: Словарь ресурсов для подписки (тип ресурса -> namespace)
    """
    for resource_type, namespace in resources.items():
        # Формируем сообщение подписки
        message = {
            "type": "subscribe",
            "resourceType": resource_type
        }

        if namespace:
            message["namespace"] = namespace

        # Отправляем запрос на подписку
        await websocket.send(json.dumps(message))

        # Сохраняем информацию о подписке
        subscription_key = f"{resource_type}" + (f":{namespace}" if namespace else "")
        subscriptions.add(subscription_key)

        logger.info(f"Подписка на {subscription_key} отправлена")

async def process_message(message_str: str) -> None:
    """Обработка входящего сообщения WebSocket.

    Args:
        message_str: Строка сообщения в формате JSON
    """
    try:
        message = json.loads(message_str)
        message_type = message.get("type", "unknown")

        # Обработка разных типов сообщений
        if message_type == "resource":
            await handle_resource_event(message)
        elif message_type == "initial_state_complete":
            count = message.get("count", 0)
            resource_type = message.get("resourceType", "unknown")
            namespace = message.get("namespace", "all")
            logger.info(f"Начальное состояние загружено: {resource_type} в {namespace} ({count} элементов)")
        elif message_type == "connection":
            status = message.get("status", "unknown")
            msg = message.get("message", "")
            logger.info(f"Соединение: {status} {msg}")
        elif message_type == "subscribed":
            resource_type = message.get("resourceType", "unknown")
            namespace = message.get("namespace", "all")
            logger.info(f"Подписка подтверждена: {resource_type} в {namespace}")
        elif message_type == "unsubscribed":
            resource_type = message.get("resourceType", "unknown")
            logger.info(f"Отписка подтверждена: {resource_type}")
        elif message_type == "error":
            logger.error(f"Ошибка от сервера: {message.get('message', 'Неизвестная ошибка')}")
        else:
            logger.warning(f"Неизвестный тип сообщения: {message_type}")

    except json.JSONDecodeError:
        logger.error(f"Невозможно декодировать JSON: {message_str}")
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {e}")

async def handle_resource_event(message: Dict[str, Any]) -> None:
    """Обработка события ресурса.

    Args:
        message: Сообщение с событием ресурса
    """
    event_type = message.get("eventType", "UNKNOWN")
    resource_type = message.get("resourceType", "unknown")
    resource = message.get("resource", {})

    name = resource.get("name", "no-name")
    namespace = resource.get("namespace", "no-namespace")

    # Форматируем вывод события
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")

    if event_type == "INITIAL":
        logger.info(f"[{timestamp}] INITIAL {resource_type}/{namespace}/{name}")
    else:
        # Цветовые коды ANSI
        COLOR_GREEN = "\033[92m"
        COLOR_YELLOW = "\033[93m"
        COLOR_RED = "\033[91m"
        COLOR_RESET = "\033[0m"
        COLOR_BLUE = "\033[94m"

        # Выбор цвета в зависимости от типа события
        color = COLOR_GREEN if event_type == "ADDED" else (
                COLOR_YELLOW if event_type == "MODIFIED" else (
                COLOR_RED if event_type == "DELETED" else COLOR_BLUE))

        print(f"{color}[{timestamp}] {event_type} {resource_type}/{namespace}/{name}{COLOR_RESET}")

        # Вывод дополнительной информации в зависимости от типа ресурса
        if resource_type == "deployments":
            replicas = resource.get("replicas", {})
            status = resource.get("status", "unknown")
            print(f"  Status: {status}, Replicas: {replicas.get('ready', 0)}/{replicas.get('desired', 0)}")

            if "main_container" in resource:
                container = resource["main_container"]
                print(f"  Container: {container.get('name')} [{container.get('image_tag')}]")

        elif resource_type == "pods":
            phase = resource.get("phase", "Unknown")
            status = resource.get("status", "unknown")
            print(f"  Status: {status}, Phase: {phase}")

            if "pod_ip" in resource:
                print(f"  Pod IP: {resource['pod_ip']}")

        elif resource_type == "namespaces":
            phase = resource.get("phase", "Unknown")
            created = resource.get("created", "unknown")
            print(f"  Phase: {phase}, Created: {created}")

async def shutdown(websocket) -> None:
    """Корректное завершение работы.

    Args:
        websocket: WebSocket соединение
    """
    logger.info("Завершение работы...")
    await websocket.close()
    asyncio.get_event_loop().stop()

def main():
    """Основная функция приложения."""
    parser = argparse.ArgumentParser(description="WebSocket клиент для тестирования API Streaming")
    parser.add_argument("--url", default="ws://localhost:3000/api/k8s/ws",
                     help="WebSocket URL (по умолчанию: ws://localhost:3000/api/k8s/ws)")
    parser.add_argument("--deployments", action="store_true", help="Подписаться на deployments")
    parser.add_argument("--pods", action="store_true", help="Подписаться на pods")
    parser.add_argument("--namespaces", action="store_true", help="Подписаться на namespaces")
    parser.add_argument("--namespace", help="Фильтр по namespace (опционально)")
    parser.add_argument("--all", action="store_true", help="Подписаться на все типы ресурсов")

    args = parser.parse_args()

    # Определение списка ресурсов для подписки
    resources = {}

    if args.all:
        resources = {
            "deployments": args.namespace,
            "pods": args.namespace,
            "namespaces": None  # Namespaces не фильтруются по namespace
        }
    else:
        if args.deployments:
            resources["deployments"] = args.namespace
        if args.pods:
            resources["pods"] = args.namespace
        if args.namespaces:
            resources["namespaces"] = None

    # Если не указаны ресурсы, подписываемся на все
    if not resources:
        resources = {
            "deployments": args.namespace,
            "pods": args.namespace,
            "namespaces": None
        }

    # Запуск клиента
    logger.info(f"Запуск WebSocket клиента для {args.url}")
    logger.info(f"Подписки: {resources}")

    try:
        asyncio.run(connect_websocket(args.url, resources))
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания. Завершение работы.")

if __name__ == "__main__":
    main()
