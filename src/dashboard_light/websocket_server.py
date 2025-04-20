#!/usr/bin/env python
"""Отдельный WebSocket сервер для Dashboard-Light."""

import asyncio
import json
import logging
import os
import sys
import signal
import traceback
from typing import Dict, Any, Set

import websockets

from dashboard_light.config import core as config
from dashboard_light.k8s import core as k8s
from dashboard_light.state_manager import subscribe, get_resources_by_type
from dashboard_light.k8s.watch import start_watching, stop_watching, get_active_watches

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,  # Повышаем уровень логирования для лучшей диагностики
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Также настраиваем логирование websockets библиотеки
websockets_logger = logging.getLogger('websockets')
websockets_logger.setLevel(logging.DEBUG)

# Чтобы увидеть все сообщения в консоли
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
websockets_logger.addHandler(console_handler)

# Список активных соединений
active_connections: Set = set()

# WebSocket сервер
server = None

async def handle_websocket(websocket):
    """Обработка WebSocket соединения."""
    # Добавляем соединение в список активных
    active_connections.add(websocket)

    # Загрузка конфигурации и клиента здесь для отладки
    try:
        logger.info(f"Новое WebSocket соединение: {websocket.remote_address}")

        # Загрузка конфигурации
        logger.debug("Загрузка конфигурации внутри обработчика...")
        app_config = config.load_config()

        # Инициализация Kubernetes клиента
        logger.debug("Инициализация Kubernetes клиента внутри обработчика...")
        k8s_client = k8s.create_k8s_client(app_config)

        # Отправляем сообщение о подключении
        await websocket.send(json.dumps({
            "type": "connection",
            "status": "connected",
            "message": "Соединение с WebSocket сервером установлено"
        }))

        # Проверяем, запущены ли наблюдатели
        active_watches = get_active_watches()
        logger.debug(f"Активные наблюдения: {active_watches}")

        if not active_watches:
            # Запускаем наблюдение за ресурсами
            logger.info("Запуск наблюдателей за ресурсами при первом WebSocket подключении")
            try:
                await start_watching(k8s_client)
                logger.info("Наблюдение за ресурсами запущено успешно")
            except Exception as e:
                logger.error(f"Ошибка при запуске наблюдения: {str(e)}")
                logger.error(traceback.format_exc())

        # Словарь подписок для этого соединения
        subscriptions = {}

        # Обработка входящих сообщений
        async for message in websocket:
            try:
                logger.debug(f"Получено сообщение: {message}")

                # Парсим JSON
                data = json.loads(message)
                message_type = data.get("type")

                if message_type == "subscribe":
                    # Подписка на ресурс
                    resource_type = data.get("resourceType")
                    namespace = data.get("namespace")

                    if resource_type:
                        logger.info(f"Обработка подписки на {resource_type} в {namespace or 'all'}")

                        # Функция для отправки обновлений ресурса
                        async def send_resource_update(event_type, resource_type, resource_data):
                            # Если указан namespace, фильтруем по нему
                            if namespace and resource_data.get("namespace") != namespace:
                                return

                            # Отправляем обновление
                            try:
                                await websocket.send(json.dumps({
                                    "type": "resource",
                                    "eventType": event_type,
                                    "resourceType": resource_type,
                                    "resource": resource_data
                                }))
                            except Exception as e:
                                logger.error(f"Ошибка при отправке обновления: {str(e)}")
                                logger.error(traceback.format_exc())

                        # Регистрируем callback для обновлений
                        try:
                            callback_unsubscribe = subscribe(resource_type, send_resource_update)

                            # Сохраняем информацию о подписке
                            subscription_key = f"{resource_type}:{namespace or 'all'}"
                            subscriptions[subscription_key] = callback_unsubscribe

                            logger.info(f"Подписка на {subscription_key} выполнена успешно")
                        except Exception as e:
                            logger.error(f"Ошибка при подписке: {str(e)}")
                            logger.error(traceback.format_exc())
                            await websocket.send(json.dumps({
                                "type": "error",
                                "message": f"Ошибка при подписке: {str(e)}"
                            }))
                            continue

                        # Отправляем подтверждение подписки
                        await websocket.send(json.dumps({
                            "type": "subscribed",
                            "resourceType": resource_type,
                            "namespace": namespace
                        }))

                        # Отправляем текущее состояние ресурсов
                        resources = get_resources_by_type(resource_type)
                        logger.info(f"Отправка начального состояния: {len(resources)} ресурсов типа {resource_type}")

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
                    logger.debug(f"Получен ping с timestamp: {data.get('timestamp')}")
                    await websocket.send(json.dumps({
                        "type": "pong",
                        "timestamp": data.get("timestamp")
                    }))
                    logger.debug("Отправлен pong")

                else:
                    logger.warning(f"Неизвестный тип сообщения: {message_type}")

            except json.JSONDecodeError:
                logger.warning(f"Получено некорректное JSON сообщение: {message}")
            except Exception as e:
                logger.error(f"Ошибка при обработке сообщения: {str(e)}")
                logger.error(traceback.format_exc())

    except websockets.exceptions.ConnectionClosed as e:
        logger.info(f"Соединение закрыто: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        # Отменяем все подписки
        for subscription_key, unsubscribe_func in subscriptions.items():
            logger.info(f"Отмена подписки {subscription_key} при закрытии соединения")
            unsubscribe_func()

        # Удаляем соединение из списка активных
        active_connections.remove(websocket)
        logger.info(f"Соединение закрыто: {websocket.remote_address}")


async def shutdown(signal, loop):
    """Корректное завершение работы сервера."""
    logger.info(f"Получен сигнал {signal.name}...")

    # Остановка наблюдения за ресурсами
    logger.info("Остановка наблюдения за ресурсами...")
    try:
        await stop_watching()
        logger.info("Наблюдение за ресурсами остановлено успешно")
    except Exception as e:
        logger.error(f"Ошибка при остановке наблюдения: {str(e)}")
        logger.error(traceback.format_exc())

    # Закрытие всех WebSocket соединений
    if active_connections:
        logger.info(f"Закрытие {len(active_connections)} активных соединений...")
        try:
            await asyncio.gather(*(ws.close() for ws in active_connections))
            logger.info(f"Все соединения закрыты")
        except Exception as e:
            logger.error(f"Ошибка при закрытии соединений: {str(e)}")
            logger.error(traceback.format_exc())

    # Остановка WebSocket сервера
    global server
    if server:
        logger.info("Закрытие WebSocket сервера...")
        server.close()
        await server.wait_closed()
        logger.info("WebSocket сервер остановлен")

    # Остановка цикла событий
    logger.info("Остановка цикла событий...")
    loop.stop()


def main():
    """Основная функция для запуска WebSocket сервера."""
    # Настройка асинхронного цикла событий
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Регистрация обработчиков сигналов
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig, lambda s=sig: asyncio.create_task(shutdown(s, loop))
        )

    # Порт для WebSocket сервера
    port = int(os.environ.get("WEBSOCKET_PORT", 8765))

    # Функция для запуска сервера
    async def start():
        global server

        try:
            # Запуск WebSocket сервера
            logger.info(f"Запуск WebSocket сервера на порту {port}...")

            # Настройки сервера для улучшения стабильности
            server = await websockets.serve(
                handle_websocket,
                "0.0.0.0",
                port,
                ping_interval=20,     # Проверка соединения каждые 20 секунд
                ping_timeout=10,      # Ожидание ответа на ping 10 секунд
                close_timeout=10,     # Таймаут закрытия соединения
                max_size=10_485_760,  # Максимальный размер сообщения (10 МБ)
            )

            logger.info(f"WebSocket сервер запущен на порту {port}")

            # Ожидание завершения сервера
            await server.wait_closed()

        except Exception as e:
            logger.error(f"Ошибка при запуске сервера: {str(e)}")
            logger.error(traceback.format_exc())
            loop.stop()

    # Запуск сервера
    try:
        loop.create_task(start())
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        loop.close()
        logger.info("WebSocket сервер завершил работу")


if __name__ == "__main__":
    main()
