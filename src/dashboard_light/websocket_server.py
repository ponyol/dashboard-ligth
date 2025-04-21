#!/usr/bin/env python
"""Отдельный WebSocket сервер для Dashboard-Light."""

import asyncio
import json
import logging
import os
import sys
import signal
import time
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

# Семафор для ограничения количества одновременных обработчиков соединений
# Это предотвратит перегрузку сервера при большом количестве подключений
connection_semaphore = asyncio.Semaphore(100)  # Максимум 100 одновременных обработчиков

# Счетчики для статистики производительности
stats = {
    "connections_total": 0,      # Всего подключений
    "connections_current": 0,    # Текущих подключений
    "connections_rejected": 0,   # Отклоненных подключений
    "messages_received": 0,      # Полученных сообщений
    "messages_sent": 0,          # Отправленных сообщений
    "errors": 0,                 # Ошибок
}

async def handle_websocket(websocket):
    """Обработка WebSocket соединения с использованием семафора для ограничения нагрузки."""
    
    # Пытаемся захватить семафор без блокировки
    if not connection_semaphore.locked() and connection_semaphore._value <= 0:
        # Если семафор заблокирован, отклоняем соединение
        logger.warning(f"Достигнут предел одновременных соединений, отклоняем {websocket.remote_address}")
        stats["connections_rejected"] += 1
        try:
            await websocket.close(code=1013, reason="Temporary server overload")
        except Exception as e:
            logger.error(f"Ошибка при отклонении соединения: {e}")
        return
        
    # Используем семафор для ограничения числа одновременных обработчиков
    async with connection_semaphore:
        # Добавляем соединение в список активных и обновляем статистику
        active_connections.add(websocket)
        stats["connections_total"] += 1
        stats["connections_current"] += 1
        subscriptions = {}

    try:
        logger.info(f"Новое WebSocket соединение: {websocket.remote_address}")

        # Загрузка конфигурации с обработкой ошибок
        try:
            logger.debug("Загрузка конфигурации внутри обработчика...")
            app_config = config.load_config()
            logger.debug("Конфигурация загружена успешно")
        except FileNotFoundError:
            logger.warning("Файл конфигурации не найден, используем значения по умолчанию")
            app_config = {"auth": {"allow_anonymous_access": True}}
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {str(e)}")
            app_config = {"auth": {"allow_anonymous_access": True}}

        # Инициализация Kubernetes клиента с обработкой ошибок
        try:
            logger.debug("Инициализация Kubernetes клиента внутри обработчика...")
            k8s_client = k8s.create_k8s_client(app_config)
            logger.debug("K8s клиент инициализирован успешно")
        except Exception as e:
            logger.error(f"Ошибка инициализации K8s клиента: {str(e)}")
            k8s_client = {"is_mock": True}

        # Отправляем сообщение о подключении
        await websocket.send(json.dumps({
            "type": "connection",
            "status": "connected",
            "message": "Соединение с WebSocket сервером установлено"
        }))

        # Проверяем наблюдателей только если соединение первое
        if len(active_connections) == 1:
            try:
                active_watches = get_active_watches()
                logger.debug(f"Активные наблюдения: {active_watches}")

                if not active_watches:
                    logger.info("Запуск наблюдателей за ресурсами при первом WebSocket подключении")
                    # Запускаем наблюдение НЕ ожидая завершения (убираем await)
                    asyncio.create_task(start_watching(k8s_client))
                    logger.info("Задача наблюдения за ресурсами запущена в фоне")
            except Exception as e:
                logger.error(f"Ошибка при проверке/запуске наблюдений: {str(e)}")
                logger.error(traceback.format_exc())
        
        # Обработка входящих сообщений
        async for message in websocket:
            try:
                # Обновляем счетчик полученных сообщений
                stats["messages_received"] += 1
                
                logger.debug(f"Получено сообщение: {message[:100]}")  # Логируем только первые 100 символов для больших сообщений

                # Парсим JSON
                try:
                    data = json.loads(message)
                    message_type = data.get("type")
                    logger.debug(f"Тип сообщения: {message_type}")
                except json.JSONDecodeError:
                    logger.warning(f"Получено некорректное JSON сообщение: {message}")
                    stats["errors"] += 1
                    continue
                except Exception as e:
                    logger.error(f"Ошибка при парсинге сообщения: {str(e)}")
                    stats["errors"] += 1
                    continue

                # Обработка ping отдельно от других типов сообщений
                if message_type == "ping":
                    try:
                        logger.debug(f"Обработка ping с timestamp: {data.get('timestamp')}")
                        await websocket.send(json.dumps({
                            "type": "pong",
                            "timestamp": data.get("timestamp")
                        }))
                        stats["messages_sent"] += 1
                        logger.debug("Отправлен pong")
                        continue  # Переходим к следующему сообщению
                    except Exception as e:
                        logger.error(f"Ошибка при обработке ping: {str(e)}")
                        logger.error(traceback.format_exc())
                        stats["errors"] += 1
                        continue

                # Обработка подписки на ресурсы
                elif message_type == "subscribe":
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
                                
                            # Фильтрация неймспейсов по паттернам из конфигурации
                            if resource_type == "namespaces":
                                # Получаем паттерны фильтрации из конфигурации
                                namespace_patterns = app_config.get("default", {}).get("namespace_patterns", [])
                                if namespace_patterns:
                                    from dashboard_light.k8s.namespaces import filter_namespaces_by_pattern
                                    # Проверяем, соответствует ли неймспейс хотя бы одному паттерну
                                    import re
                                    name = resource_data.get("name", "")
                                    matches_pattern = any(re.match(pattern, name) for pattern in namespace_patterns)
                                    if not matches_pattern:
                                        logger.debug(f"Неймспейс {name} не соответствует паттернам {namespace_patterns}")
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

                        # Регистрируем callback для обновлений
                        try:
                            callback_unsubscribe = subscribe(resource_type, send_resource_update)

                            # Сохраняем информацию о подписке
                            subscription_key = f"{resource_type}:{namespace or 'all'}"
                            subscriptions[subscription_key] = callback_unsubscribe

                            logger.info(f"Подписка на {subscription_key} выполнена успешно")
                        except Exception as e:
                            logger.error(f"Ошибка при подписке: {str(e)}")
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
                        
                        # Фильтрация неймспейсов по паттернам из конфигурации
                        if resource_type == "namespaces":
                            # Получаем паттерны фильтрации из конфигурации
                            namespace_patterns = app_config.get("default", {}).get("namespace_patterns", [])
                            if namespace_patterns:
                                from dashboard_light.k8s.namespaces import filter_namespaces_by_pattern
                                resources = filter_namespaces_by_pattern(resources, namespace_patterns)
                                logger.info(f"Применен фильтр по паттернам: {namespace_patterns}. Осталось {len(resources)} неймспейсов")
                        
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

                # Обработка отписки
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

                # Обработка pong сообщений
                elif message_type == "pong":
                    # Просто логируем получение pong сообщения на уровне debug
                    logger.debug(f"Получен pong с timestamp: {data.get('timestamp')}")
                    # Никаких дополнительных действий не требуется
                
                # Обработка остальных типов сообщений
                else:
                    # Логируем неизвестный тип сообщения, но с меньшим уровнем важности
                    logger.info(f"Получен неизвестный тип сообщения: {message_type}")
                    
            except Exception as e:
                logger.error(f"Непредвиденная ошибка при обработке сообщения: {str(e)}")
                logger.error(traceback.format_exc())

    except websockets.exceptions.ConnectionClosed as e:
        logger.info(f"Соединение закрыто: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        logger.info(f"Выполняется очистка для соединения: {websocket.remote_address}")
            
        # Отменяем все подписки
        for subscription_key, unsubscribe_func in subscriptions.items():
            logger.info(f"Отмена подписки {subscription_key} при закрытии соединения")
            try:
                unsubscribe_func()
            except Exception as e:
                logger.error(f"Ошибка при отмене подписки {subscription_key}: {str(e)}")

        # Удаляем соединение из списка активных и обновляем статистику
        try:
            if websocket in active_connections:
                active_connections.remove(websocket)
                stats["connections_current"] -= 1
            logger.info(f"Соединение {websocket.remote_address} удалено из списка активных")
        except Exception as e:
            logger.error(f"Ошибка при удалении соединения из списка: {str(e)}")
            stats["errors"] += 1
            
        logger.info(f"Очистка для соединения {websocket.remote_address} завершена")



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
    conn_count = len(active_connections)
    if active_connections:
        logger.info(f"Закрытие {conn_count} активных соединений...")
        try:
            # Закрываем соединения с кодом сервера перезагружается/выключается
            close_tasks = []
            for ws in active_connections.copy():  # Используем копию, так как список будет изменяться
                try:
                    # Закрываем с кодом 1001 - "going away"
                    close_tasks.append(ws.close(code=1001, reason="Server shutting down"))
                except Exception as e:
                    logger.error(f"Ошибка при закрытии соединения: {e}")
            
            # Ждем закрытия всех соединений с таймаутом
            if close_tasks:
                await asyncio.wait(close_tasks, timeout=5.0)
                
            # Проверяем, остались ли открытые соединения
            remaining = len(active_connections)
            if remaining > 0:
                logger.warning(f"Осталось {remaining} незакрытых соединений после таймаута")
            else:
                logger.info(f"Все {conn_count} соединений успешно закрыты")
        except Exception as e:
            logger.error(f"Ошибка при закрытии соединений: {str(e)}")
            logger.error(traceback.format_exc())

    # Очистка ресурсов
    # Очищаем список активных соединений (на всякий случай)
    active_connections.clear()
    logger.debug("Список активных соединений очищен")

    # Остановка WebSocket сервера
    global server
    if server:
        logger.info("Закрытие WebSocket сервера...")
        server.close()
        try:
            # Ждем с таймаутом
            await asyncio.wait_for(server.wait_closed(), timeout=10.0)
            logger.info("WebSocket сервер остановлен")
        except asyncio.TimeoutError:
            logger.warning("Таймаут при ожидании закрытия WebSocket сервера")
        except Exception as e:
            logger.error(f"Ошибка при ожидании закрытия сервера: {e}")

    # Остановка цикла событий
    logger.info("Остановка цикла событий...")
    loop.stop()
    logger.info("Завершение процесса shutdown завершено")


def main():
    """Основная функция для запуска WebSocket сервера."""
    global server
    
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

            # Настройки сервера для улучшения стабильности при высокой нагрузке
            server = await websockets.serve(
                handle_websocket,
                "0.0.0.0",
                port,
                ping_interval=20,     # Проверка соединения каждые 20 секунд - для снижения нагрузки
                ping_timeout=10,      # Увеличиваем таймаут ожидания ответа на ping
                close_timeout=10,     # Увеличиваем таймаут закрытия соединения
                max_size=1_048_576,   # Уменьшаем максимальный размер сообщения (1 МБ)
                max_queue=256,        # Максимальный размер очереди сообщений для отправки
                open_timeout=10,      # Таймаут для установки соединения
                compression=None,     # Отключаем сжатие для снижения нагрузки на CPU
            )

            logger.info(f"WebSocket сервер запущен на порту {port}")

            # Запуск периодического пинга всех соединений
            asyncio.create_task(periodic_ping_all_connections())
            
            # Запуск задачи вывода статистики
            asyncio.create_task(print_server_stats())

            # Ожидание завершения сервера
            await server.wait_closed()

        except Exception as e:
            logger.error(f"Ошибка при запуске сервера: {str(e)}")
            logger.error(traceback.format_exc())
            loop.stop()

    # Функция для вывода статистики сервера
    async def print_server_stats():
        """Периодически выводит статистику сервера."""
        
        try:
            while True:
                await asyncio.sleep(30)  # Выводим статистику каждые 30 секунд
                
                # Вывод статистики
                logger.info("=== Статистика WebSocket сервера ===")
                logger.info(f"Соединений всего:     {stats['connections_total']}")
                logger.info(f"Соединений активных:  {stats['connections_current']}")
                logger.info(f"Соединений отклонено: {stats['connections_rejected']}")
                logger.info(f"Сообщений получено:   {stats['messages_received']}")
                logger.info(f"Сообщений отправлено: {stats['messages_sent']}")
                logger.info(f"Ошибок:               {stats['errors']}")
                logger.info(f"Семафор:              {connection_semaphore._value}/{connection_semaphore._bound_value}")
                logger.info("====================================")
        except asyncio.CancelledError:
            logger.info("Задача вывода статистики отменена")
        except Exception as e:
            logger.error(f"Ошибка в задаче вывода статистики: {e}")
    
    # Функция для периодической отправки пингов всем подключенным клиентам
    async def periodic_ping_all_connections():
        """Периодически отправляет пинги всем клиентам для поддержания соединения."""
        try:
            while True:
                await asyncio.sleep(5)  # Проверка каждые 5 секунд
                
                if not active_connections:
                    continue
                    
                logger.debug(f"Отправка ping всем {len(active_connections)} активным соединениям")
                
                # Создаем копию списка, так как он может изменяться во время итерации
                connections = active_connections.copy()
                
                # Отправляем ping всем активным соединениям
                for ws in connections:
                    try:
                        # Проверяем, что соединение еще открыто
                        if ws in active_connections:  # Дополнительная проверка
                            # Отправляем application-level ping
                            timestamp = time.time()
                            await ws.send(json.dumps({
                                "type": "ping",
                                "timestamp": timestamp
                            }))
                    except Exception as e:
                        logger.error(f"Ошибка при отправке ping: {e}")
                        # Не удаляем соединение здесь, это будет сделано в обработчике исключений
        except asyncio.CancelledError:
            logger.info("Задача периодической отправки ping отменена")
        except Exception as e:
            logger.error(f"Ошибка в periodic_ping_all_connections: {e}")
            logger.error(traceback.format_exc())

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