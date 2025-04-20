#!/usr/bin/env python
"""Отдельный WebSocket сервер без FastAPI."""

import asyncio
import json
import logging
import os
import sys
import signal
import websockets

# Добавляем родительскую директорию в путь для импорта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dashboard_light.config import core as config
from dashboard_light.k8s import core as k8s
from dashboard_light.state_manager import update_resource_state, subscribe, get_resources_by_type
from dashboard_light.k8s.watch import start_watching, stop_watching, get_active_watches

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Список активных соединений
active_connections = set()

# Настройка приложения
async def setup_app():
    """Инициализация приложения."""
    try:
        # Загрузка конфигурации
        logger.info("Загрузка конфигурации...")
        app_config = config.load_config()
        logger.info("Конфигурация загружена успешно")

        # Инициализация Kubernetes клиента
        logger.info("Инициализация Kubernetes клиента...")
        k8s_client = k8s.create_k8s_client(app_config)
        logger.info("Kubernetes клиент инициализирован")

        return app_config, k8s_client
    except Exception as e:
        logger.error(f"Ошибка при инициализации: {str(e)}")
        return {}, {}

# Обработчик WebSocket соединений
async def handle_websocket(websocket, path, app_config, k8s_client):
    """Обработка WebSocket соединения."""
    # Добавляем соединение в список активных
    active_connections.add(websocket)

    try:
        logger.info(f"Новое WebSocket соединение: {websocket.remote_address}")

        # Отправляем сообщение о подключении
        await websocket.send(json.dumps({
            "type": "connection",
            "status": "connected",
            "message": "Соединение с WebSocket сервером установлено"
        }))

        # Проверяем, запущены ли наблюдатели
        active_watches = get_active_watches()
        if not active_watches:
            # Запускаем наблюдение за ресурсами
            logger.info("Запуск наблюдателей за ресурсами при первом WebSocket подключении")
            await start_watching(k8s_client)

        # Словарь подписок для этого соединения
        subscriptions = {}

        # Обработка входящих сообщений
        async for message in websocket:
            try:
                # Парсим JSON
                data = json.loads(message)
                message_type = data.get("type")

                if message_type == "subscribe":
                    # Подписка на ресурс
                    resource_type = data.get("resourceType")
                    namespace = data.get("namespace")

                    if resource_type:
                        # Функция для отправки обновлений ресурса
                        async def send_resource_update(event_type, resource_type, resource_data):
                            # Если указан namespace, фильтруем по нему
                            if namespace and resource_data.get("namespace") != namespace:
                                return

                            # Отправляем обновление
                            await websocket.send(json.dumps({
                                "type": "resource",
                                "eventType": event_type,
                                "resourceType": resource_type,
                                "resource": resource_data
                            }))

                        # Регистрируем callback для обновлений
                        callback_unsubscribe = subscribe(resource_type, send_resource_update)

                        # Сохраняем информацию о подписке
                        subscription_key = f"{resource_type}:{namespace or 'all'}"
                        subscriptions[subscription_key] = callback_unsubscribe

                        logger.info(f"Подписка на {subscription_key}")

                        # Отправляем подтверждение подписки
                        await websocket.send(json.dumps({
                            "type": "subscribed",
                            "resourceType": resource_type,
                            "namespace": namespace
                        }))

                        # Отправляем текущее состояние ресурсов
                        resources = get_resources_by_type(resource_type)
                        for resource in resources:
                            # Если указан namespace, фильтруем по нему
                            if namespace and resource.get("namespace") != namespace:
                                continue

                            await websocket.send(json.dumps({
                                "type": "resource",
                                "eventType": "INITIAL",
                                "resourceType": resource_type,
                                "resource": resource
                            }))

                        # Отправляем сообщение о завершении начальной загрузки
                        await websocket.send(json.dumps({
                            "type": "initial_state_complete",
                            "resourceType": resource_type,
                            "count": len(resources),
                            "namespace": namespace or "all"
                        }))

                elif message_type == "unsubscribe":
                    # Отписка от ресурса
                    resource_type = data.get("resourceType")
                    namespace = data.get("namespace")

                    if resource_type:
                        # Формируем ключ подписки
                        subscription_key = f"{resource_type}:{namespace or 'all'}"

                        # Если есть такая подписка, удаляем её
                        if subscription_key in subscriptions:
                            unsubscribe_func = subscriptions.pop(subscription_key)
                            unsubscribe_func()

                            logger.info(f"Отписка от {subscription_key}")

                            # Отправляем подтверждение отписки
                            await websocket.send(json.dumps({
                                "type": "unsubscribed",
                                "resourceType": resource_type,
                                "namespace": namespace
                            }))

                elif message_type == "ping":
                    # Обработка пинга
                    await websocket.send(json.dumps({
                        "type": "pong",
                        "timestamp": data.get("timestamp")
                    }))

                else:
                    logger.warning(f"Неизвестный тип сообщения: {message_type}")

            except json.JSONDecodeError:
                logger.warning(f"Получено некорректное JSON сообщение: {message}")
            except Exception as e:
                logger.error(f"Ошибка при обработке сообщения: {str(e)}")

    except websockets.exceptions.ConnectionClosed as e:
        logger.info(f"Соединение закрыто: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {str(e)}")
    finally:
        # Отменяем все подписки
        for unsubscribe_func in subscriptions.values():
            unsubscribe_func()

        # Удаляем соединение из списка активных
        active_connections.remove(websocket)
        logger.info(f"Соединение закрыто: {websocket.remote_address}")

async def main():
    """Основная функция для запуска сервера."""
    # Инициализация приложения
    app_config, k8s_client = await setup_app()

    # Запуск WebSocket сервера
    port = 8765  # Используем другой порт, чтобы не конфликтовать с основным приложением
    host = "0.0.0.0"

    # Обработчик сигналов для корректного завершения
    stop = asyncio.Future()

    def handle_signal(signal, frame):
        logger.info("Получен сигнал завершения")
        stop.set_result(None)

    # Регистрация обработчиков сигналов
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, handle_signal)

    # Запуск сервера
    logger.info(f"Запуск WebSocket сервера на {host}:{port}")
    async with websockets.serve(
        lambda ws, path: handle_websocket(ws, path, app_config, k8s_client),
        host, port
    ):
        # Ожидание сигнала завершения
        await stop

    # Остановка наблюдения
    logger.info("Остановка наблюдения за ресурсами...")
    await stop_watching()

    logger.info("Сервер остановлен")

if __name__ == "__main__":
    # Запуск приложения
    asyncio.run(main())
