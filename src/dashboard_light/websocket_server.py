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
from dashboard_light.state_manager import subscribe, get_resources_by_type, update_resource_state
from dashboard_light.k8s.watch import start_watching, stop_watching, get_active_watches
from dashboard_light.utils.logging import configure_logging

# Настройка логирования с использованием централизованной функции
# Уровень логирования будет взят из переменной окружения LOG_LEVEL
configure_logging()
logger = logging.getLogger(__name__)

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

async def ensure_k8s_watchers_running(k8s_client):
    """Функция для обеспечения запуска наблюдателей Kubernetes.
    
    Args:
        k8s_client: Словарь с Kubernetes клиентами
        
    Returns:
        bool: True если наблюдатели запущены успешно, False в противном случае
    """
    try:
        # Проверка клиента на валидность
        if not k8s_client or not isinstance(k8s_client, dict):
            logger.error("WEBSOCKET_SERVER: K8s клиент невалиден")
            return False
            
        if "is_mock" in k8s_client and k8s_client["is_mock"]:
            logger.warning("WEBSOCKET_SERVER: Используется макет K8s клиента, наблюдатели не будут запущены")
            # В режиме эмуляции имитируем успешный запуск
            return True
            
        # Проверяем, запущены ли уже наблюдатели
        active_watches = get_active_watches()
        logger.info(f"WEBSOCKET_SERVER: Текущие активные наблюдения: {active_watches}")
        
        # Если есть активные наблюдения за основными ресурсами, считаем что все работает
        required_resources = ['deployments', 'pods', 'namespaces', 'statefulsets']
        if all(resource in active_watches for resource in required_resources):
            logger.info("WEBSOCKET_SERVER: Все необходимые наблюдатели уже запущены")
            return True
            
        # Останавливаем существующие наблюдатели для чистого запуска
        logger.info("WEBSOCKET_SERVER: Останавливаем текущие наблюдатели перед перезапуском")
        await stop_watching()
        
        # Запускаем наблюдение за всеми требуемыми ресурсами
        logger.info(f"WEBSOCKET_SERVER: Запуск наблюдения за ресурсами: {required_resources}")
        watch_tasks = await start_watching(k8s_client, required_resources)
        
        # Проверяем результаты
        logger.info(f"WEBSOCKET_SERVER: Запущены наблюдатели: {list(watch_tasks.keys())}")
        
        # Немного ждем для инициализации наблюдателей
        await asyncio.sleep(1)
        
        # Проверяем активные наблюдения после запуска
        active_watches = get_active_watches()
        logger.info(f"WEBSOCKET_SERVER: Активные наблюдения после запуска: {active_watches}")
        
        # Проверяем, что запущены все необходимые наблюдатели
        missing_resources = [r for r in required_resources if r not in active_watches]
        if missing_resources:
            logger.error(f"WEBSOCKET_SERVER: Не удалось запустить наблюдатели для: {missing_resources}")
            return False
            
        logger.info("WEBSOCKET_SERVER: Все наблюдатели успешно запущены")
        return True
        
    except Exception as e:
        logger.error(f"WEBSOCKET_SERVER: Ошибка при запуске наблюдателей: {e}")
        logger.error(traceback.format_exc())
        return False

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
            logger.info("WEBSOCKET_SERVER: Инициализация Kubernetes клиента внутри обработчика...")
            
            try:
                # Пытаемся создать полноценный K8s клиент с подключением к кластеру
                k8s_client = k8s.create_k8s_client(app_config)
                
                # Проверка, что k8s_client содержит необходимые API
                if "core_v1_api" not in k8s_client or "apps_v1_api" not in k8s_client:
                    logger.error("WEBSOCKET_SERVER: K8s клиент не содержит необходимые API!")
                    logger.error(f"WEBSOCKET_SERVER: Доступные ключи в k8s_client: {k8s_client.keys()}")
                    raise ValueError("Kubernetes клиент не содержит необходимые API")
                    
                # Проверяем, что клиент не в режиме эмуляции
                if k8s_client.get("is_mock"):
                    logger.warning("WEBSOCKET_SERVER: K8s клиент в режиме эмуляции, реальные данные не будут доступны")
                    # Если используется mock-клиент, отправляем предупреждение клиенту
                    await websocket.send(json.dumps({
                        "type": "warning",
                        "message": "Kubernetes API работает в режиме эмуляции. Реальные данные кластера не доступны."
                    }))
                else:
                    logger.info(f"WEBSOCKET_SERVER: K8s клиент инициализирован успешно через {k8s_client.get('connection_method', 'unknown')}")
                    logger.info(f"WEBSOCKET_SERVER: Доступные API: {list(k8s_client.keys())}")
                
            except Exception as k8s_error:
                # Если не удалось создать клиент с подключением к кластеру,
                # логируем ошибку и создаем минимальный клиент для базовой работы
                logger.error(f"WEBSOCKET_SERVER: Критическая ошибка при инициализации K8s клиента: {str(k8s_error)}")
                logger.error(traceback.format_exc())
                
                # Отправляем сообщение об ошибке клиенту
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": f"Не удалось подключиться к Kubernetes API: {str(k8s_error)}"
                }))
                
                # Создаем заглушку для предотвращения ошибок
                k8s_client = {
                    "is_mock": True,
                    "core_v1_api": None,
                    "apps_v1_api": None,
                    "custom_objects_api": None,
                    "api_client": None
                }
                
        except Exception as e:
            # Этот блок перехватывает все остальные ошибки, которые могут произойти
            # в процессе обработки подключения к K8s
            logger.error(f"WEBSOCKET_SERVER: Непредвиденная ошибка: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Отправляем сообщение об ошибке клиенту
            try:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": f"Произошла непредвиденная ошибка: {str(e)}"
                }))
            except:
                pass
                
            # Создаем заглушку в самом крайнем случае
            k8s_client = {
                "is_mock": True,
                "core_v1_api": None,
                "apps_v1_api": None
            }

        # Отправляем сообщение о подключении
        await websocket.send(json.dumps({
            "type": "connection",
            "status": "connected",
            "message": "Соединение с WebSocket сервером установлено"
        }))

        # Запускаем наблюдателей для всех соединений
        # Всегда запускаем наблюдателей для каждого соединения
        # Это гарантирует, что если наблюдатели не запустились ранее, они будут запущены сейчас
        try:
            try:
                watchers_running = await ensure_k8s_watchers_running(k8s_client)
                
                if watchers_running:
                    logger.info("WEBSOCKET_SERVER: K8s наблюдатели успешно запущены и работают")
                    
                    # При успешном запуске наблюдателей нет необходимости в тестовых данных,
                    # так как реальные данные должны приходить напрямую от K8s API
                    logger.info("WEBSOCKET_SERVER: Ждем получения реальных данных от Kubernetes API")
                    
                else:
                    logger.warning("WEBSOCKET_SERVER: Не удалось запустить K8s наблюдатели")
                    
                    # Отправляем сообщение об ошибке клиенту
                    try:
                        await websocket.send(json.dumps({
                            "type": "error",
                            "message": "К сожалению, серверу не удалось запустить наблюдение за ресурсами Kubernetes. Функциональность WebSocket будет ограничена."
                        }))
                    except Exception as send_error:
                        logger.error(f"WEBSOCKET_SERVER: Не удалось отправить сообщение об ошибке: {send_error}")
                
            except Exception as e:
                logger.error(f"WEBSOCKET_SERVER: Непредвиденная ошибка при запуске наблюдателей: {str(e)}")
                logger.error(traceback.format_exc())
        except Exception as e:
            logger.error(f"WEBSOCKET_SERVER: Глобальная ошибка: {str(e)}")
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
                            # Отладочное сообщение при получении обновления
                            logger.info(f"WEBSOCKET_SERVER: Получено обновление {event_type} для {resource_type}/{resource_data.get('namespace', '')}/{resource_data.get('name', '')}")
                            
                            # Если указан namespace, фильтруем по нему
                            if namespace and resource_data.get("namespace") != namespace:
                                logger.debug(f"WEBSOCKET_SERVER: Пропуск обновления из-за несовпадения namespace: запрошен {namespace}, получен {resource_data.get('namespace', '')}")
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

                            # Отправляем обновление, только если соединение открыто
                            try:
                                # Проверяем, что соединение всё ещё активно
                                from websockets.exceptions import ConnectionClosed
                                
                                # Сначала просто проверим, что соединение в active_connections
                                if websocket not in active_connections:
                                    logger.debug(f"Соединение уже не активно, пропускаем отправку обновления {resource_type}")
                                    return
                                
                                # Объективно проверяем состояние соединения
                                # Разные версии websockets используют разные атрибуты
                                try:
                                    is_closed = False
                                    # Проверяем сначала атрибут closed (более новые версии)
                                    if hasattr(websocket, 'closed'):
                                        is_closed = websocket.closed
                                    # Затем проверяем метод open (более старые версии)
                                    elif hasattr(websocket, 'open') and callable(getattr(websocket, 'open')):
                                        is_closed = not websocket.open
                                    # Если оба метода не доступны, проверяем state
                                    elif hasattr(websocket, 'state'):
                                        from websockets.protocol import State
                                        is_closed = websocket.state != State.OPEN if hasattr(State, 'OPEN') else True
                                        
                                    if is_closed:
                                        logger.debug(f"Соединение закрыто, пропускаем отправку обновления {resource_type}")
                                        if websocket in active_connections:
                                            active_connections.remove(websocket)
                                        return
                                except Exception as e:
                                    logger.debug(f"Ошибка при проверке состояния соединения: {e}")
                                    # Предполагаем, что соединение может быть повреждено
                                    if websocket in active_connections:
                                        active_connections.remove(websocket)
                                    return
                                
                                # Добавим дополнительную проверку данных перед отправкой
                                if not resource_data or not isinstance(resource_data, dict):
                                    logger.warning(f"WEBSOCKET_SERVER: Некорректные данные для отправки: {resource_data}")
                                    return
                                    
                                if resource_type not in ["namespaces", "deployments", "pods", "statefulsets"]:
                                    logger.warning(f"WEBSOCKET_SERVER: Неизвестный тип ресурса: {resource_type}")
                                    return
                                    
                                # Проверим наличие имени ресурса
                                if "name" not in resource_data:
                                    logger.warning(f"WEBSOCKET_SERVER: Отсутствует имя ресурса в данных: {resource_data}")
                                    return
                                
                                # Формируем сообщение для отправки
                                message = {
                                    "type": "resource",
                                    "eventType": event_type,
                                    "resourceType": resource_type,
                                    "resource": resource_data
                                }
                                
                                # Теперь можно безопасно отправить сообщение
                                resource_name = resource_data.get('name', 'unknown')
                                resource_ns = resource_data.get('namespace', '')
                                logger.info(f"WEBSOCKET_SERVER: Отправка обновления {resource_type}/{resource_ns}/{resource_name}")
                                await websocket.send(json.dumps(message))
                                stats["messages_sent"] += 1
                                logger.info(f"WEBSOCKET_SERVER: Обновление {resource_type}/{resource_name} успешно отправлено")
                            except ConnectionClosed:
                                # Соединение было закрыто, удаляем его из активных
                                logger.debug(f"Соединение закрыто при попытке отправки, удаляем из активных")
                                if websocket in active_connections:
                                    active_connections.remove(websocket)
                                return
                            except Exception as e:
                                logger.error(f"Ошибка при отправке обновления: {str(e)}")
                                # Если произошла ошибка, возможно, соединение повреждено
                                # Удаляем соединение из активных для предотвращения повторных ошибок
                                if websocket in active_connections:
                                    active_connections.remove(websocket)

                        # Регистрируем callback для обновлений
                        try:
                            # Проверяем типы ресурсов, которые мы наблюдаем через Watch API
                            from dashboard_light.k8s.watch import get_active_watches
                            active_watches = get_active_watches()
                            logger.info(f"WEBSOCKET_SERVER: Активные наблюдения: {active_watches}")
                            
                            if resource_type not in active_watches:
                                logger.warning(f"WEBSOCKET_SERVER: Запрошена подписка на {resource_type}, но этот тип ресурса не отслеживается через Watch API!")
                                
                                # Пытаемся запустить наблюдение, если тип ресурса валидный
                                if resource_type in ["namespaces", "deployments", "pods", "statefulsets"]:
                                    logger.info(f"WEBSOCKET_SERVER: Попытка запустить наблюдение за {resource_type}...")
                                    try:
                                        from dashboard_light.k8s.watch import start_watching
                                        # Запускаем наблюдение только за этим ресурсом
                                        await start_watching(k8s_client, [resource_type])
                                        logger.info(f"WEBSOCKET_SERVER: Наблюдение за {resource_type} запущено по запросу")
                                    except Exception as start_error:
                                        logger.error(f"WEBSOCKET_SERVER: Не удалось запустить наблюдение за {resource_type}: {start_error}")
                            
                            # Регистрируем обработчик
                            callback_unsubscribe = subscribe(resource_type, send_resource_update)

                            # Сохраняем информацию о подписке
                            subscription_key = f"{resource_type}:{namespace or 'all'}"
                            subscriptions[subscription_key] = callback_unsubscribe

                            logger.info(f"Подписка на {subscription_key} выполнена успешно. Текущие подписки: {list(subscriptions.keys())}")
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
                        stats["messages_sent"] += 1

                        # Отправляем текущее состояние ресурсов
                        resources = get_resources_by_type(resource_type)
                        logger.info(f"WEBSOCKET_SERVER: Отправка начального состояния: {len(resources)} ресурсов типа {resource_type}")
                        
                        # Проверка, есть ли какие-то ресурсы для отправки
                        if len(resources) == 0:
                            logger.warning(f"WEBSOCKET_SERVER: Нет данных для отправки начального состояния типа {resource_type}")
                            
                            # Если в кэше нет данных, запустим наблюдателей принудительно
                            logger.info(f"WEBSOCKET_SERVER: Принудительное получение начальных данных для {resource_type}")
                            try:
                                # Получаем необходимый API клиент
                                from dashboard_light.k8s.watch import _get_api_instance, _resource_functions, _convert_to_dict
                                api_instance = _get_api_instance(k8s_client, resource_type)
                                
                                if api_instance:
                                    # Получаем функцию для получения списка ресурсов
                                    list_func = _resource_functions[resource_type]['list_func'](api_instance)
                                    
                                    # Получаем текущие ресурсы
                                    items = list_func().items
                                    
                                    for item in items:
                                        # Преобразуем в словарь
                                        resource_dict = _convert_to_dict(resource_type, item)
                                        
                                        # Обновляем состояние через менеджер
                                        await update_resource_state("ADDED", resource_type, resource_dict)
                                    
                                    logger.info(f"WEBSOCKET_SERVER: Принудительно получено {len(items)} ресурсов типа {resource_type}")
                                    
                                    # Получаем обновленные ресурсы
                                    resources = get_resources_by_type(resource_type)
                                    logger.info(f"WEBSOCKET_SERVER: После принудительного обновления: {len(resources)} ресурсов типа {resource_type}")
                            except Exception as e:
                                logger.error(f"WEBSOCKET_SERVER: Ошибка при принудительном получении данных: {e}")
                        
                        # Фильтрация неймспейсов по паттернам из конфигурации
                        if resource_type == "namespaces":
                            # Получаем паттерны фильтрации из конфигурации
                            namespace_patterns = app_config.get("default", {}).get("namespace_patterns", [])
                            if namespace_patterns:
                                from dashboard_light.k8s.namespaces import filter_namespaces_by_pattern
                                resources = filter_namespaces_by_pattern(resources, namespace_patterns)
                                logger.info(f"Применен фильтр по паттернам: {namespace_patterns}. Осталось {len(resources)} неймспейсов")
                        
                        # Счетчик отправленных ресурсов для отладки
                        sent_count = 0
                        
                        for resource in resources:
                            # Если указан namespace, фильтруем по нему
                            if namespace and resource.get("namespace") != namespace:
                                continue

                            # Формируем сообщение с начальными данными
                            initial_message = {
                                "type": "resource",
                                "eventType": "INITIAL",
                                "resourceType": resource_type,
                                "resource": resource
                            }
                            
                            # Отправляем сообщение
                            await websocket.send(json.dumps(initial_message))
                            stats["messages_sent"] += 1
                            sent_count += 1
                            
                            # Периодически сообщаем о прогрессе для крупных объемов данных
                            if sent_count % 20 == 0:
                                logger.info(f"WEBSOCKET_SERVER: Отправлено {sent_count} из {len(resources)} начальных ресурсов")

                        # Финальное сообщение о количестве отправленных ресурсов
                        logger.info(f"WEBSOCKET_SERVER: Отправлено всего {sent_count} начальных ресурсов типа {resource_type}")

                        # Отправляем сообщение о завершении начальной загрузки
                        await websocket.send(json.dumps({
                            "type": "initial_state_complete",
                            "resourceType": resource_type,
                            "count": sent_count,
                            "namespace": namespace or "all"
                        }))
                        stats["messages_sent"] += 1

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
        # Защищаем получение информации о соединении, так как оно может быть уже закрыто
        connection_info = "unknown"
        try:
            connection_info = websocket.remote_address
        except Exception:
            # Если не можем получить remote_address, используем id объекта
            connection_info = f"id:{id(websocket)}"
        
        logger.info(f"Выполняется очистка для соединения: {connection_info}")
        
        # Объявляем закрытие соединения и помечаем его как неактивное
        try:
            # Проверяем состояние соединения с использованием универсального метода
            is_closed = True  # По умолчанию считаем закрытым, чтобы не пытаться закрыть повторно
            
            try:
                # Проверяем сначала атрибут closed (более новые версии)
                if hasattr(websocket, 'closed'):
                    is_closed = websocket.closed
                # Затем проверяем метод open (более старые версии)
                elif hasattr(websocket, 'open') and callable(getattr(websocket, 'open')):
                    is_closed = not websocket.open
                # Если оба метода не доступны, проверяем state
                elif hasattr(websocket, 'state'):
                    from websockets.protocol import State
                    is_closed = websocket.state != State.OPEN if hasattr(State, 'OPEN') else True
            except Exception as e:
                logger.debug(f"Ошибка при проверке состояния соединения в finally: {e}")
                is_closed = True  # Предполагаем закрытое соединение при ошибке
            
            # Явно закрываем соединение, если оно еще не закрыто
            if not is_closed:
                # Используем asyncio.shield для защиты от отмены задачи
                # во время выполнения закрытия
                try:
                    await asyncio.shield(
                        websocket.close(code=1001, reason="Connection cleanup")
                    )
                except Exception as close_error:
                    logger.debug(f"Ошибка при закрытии соединения: {close_error}")
        except Exception as e:
            logger.debug(f"Ошибка при проверке/закрытии соединения: {e}")
            
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
            logger.info(f"Соединение {connection_info} удалено из списка активных")
        except Exception as e:
            logger.error(f"Ошибка при удалении соединения из списка: {str(e)}")
            stats["errors"] += 1
            
        logger.info(f"Очистка для соединения {connection_info} завершена")



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


# Порт для WebSocket сервера по умолчанию
DEFAULT_WEBSOCKET_PORT = 8765

async def start_websocket_server(port=None):
    """Запуск WebSocket сервера.
    
    Args:
        port: Порт для WebSocket сервера. По умолчанию берется из переменной окружения 
             WEBSOCKET_PORT или используется значение 8765.
    """
    global server
    
    # Определяем порт
    if port is None:
        port = int(os.environ.get("WEBSOCKET_PORT", DEFAULT_WEBSOCKET_PORT))
        
    logger.info(f"Запуск WebSocket сервера на порту {port}")
    
    try:
        # Запуск WebSocket сервера
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

        # Запуск периодического пинга всех соединений
        asyncio.create_task(periodic_ping_all_connections())
        
        # Запуск задачи вывода статистики
        asyncio.create_task(print_server_stats())
        
        logger.info(f"WebSocket сервер запущен на порту {port}")
        
        return server
    except Exception as e:
        logger.error(f"Ошибка при запуске сервера: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def run_server(port=None):
    """Основная функция для запуска WebSocket сервера.
    
    Args:
        port: Порт для WebSocket сервера. По умолчанию берется из переменной окружения 
             WEBSOCKET_PORT или используется значение 8765.
    """
    # Определяем порт
    if port is None:
        port = int(os.environ.get("WEBSOCKET_PORT", DEFAULT_WEBSOCKET_PORT))
    
    # Настройка асинхронного цикла событий
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Регистрация обработчиков сигналов
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig, lambda s=sig: asyncio.create_task(shutdown(s, loop))
        )
        
    # Определяем асинхронную функцию для запуска сервера
    async def _run_server_async():
        global server
        try:
            # Запуск WebSocket сервера
            logger.info(f"Запуск WebSocket сервера на порту {port}...")
            
            # Используем нашу собственную функцию для запуска сервера
            server = await start_websocket_server(port)
            
            # Ожидание завершения сервера (сервер продолжает работу)
            await server.wait_closed()

        except Exception as e:
            logger.error(f"Ошибка при запуске сервера: {str(e)}")
            logger.error(traceback.format_exc())
            loop.stop()
            
    # Запуск асинхронной функции в цикле событий
    try:
        # Создаем и запускаем задачу старта сервера
        loop.create_task(_run_server_async())
        # Запускаем цикл событий
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        loop.close()
        logger.info("WebSocket сервер завершил работу")


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
            # Безопасное получение значения семафора
            try:
                if hasattr(connection_semaphore, '_bound_value'):
                    semaphore_info = f"{connection_semaphore._value}/{connection_semaphore._bound_value}"
                else:
                    # У более новых версий asyncio может быть другой API
                    semaphore_info = f"{connection_semaphore._value}/100" # Используем константу из определения семафора
                logger.info(f"Семафор:              {semaphore_info}")
            except Exception as e:
                logger.info(f"Семафор:              информация недоступна ({str(e)})")
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
            from websockets.exceptions import ConnectionClosed
            
            for ws in connections:
                try:
                    # Проверяем, что соединение все еще в списке активных
                    if ws not in active_connections:
                        continue
                        
                    # Проверяем, что соединение не закрыто явно
                    # Разные версии websockets используют разные атрибуты
                    try:
                        is_closed = False
                        # Проверяем сначала атрибут closed (более новые версии)
                        if hasattr(ws, 'closed'):
                            is_closed = ws.closed
                        # Затем проверяем метод open (более старые версии)
                        elif hasattr(ws, 'open') and callable(getattr(ws, 'open')):
                            is_closed = not ws.open
                        # Если оба метода не доступны, проверяем state
                        elif hasattr(ws, 'state'):
                            from websockets.protocol import State
                            is_closed = ws.state != State.OPEN if hasattr(State, 'OPEN') else True
                            
                        if is_closed:
                            logger.debug(f"Соединение закрыто, удаляем из активных")
                            if ws in active_connections:
                                active_connections.remove(ws)
                            continue
                    except Exception as e:
                        logger.debug(f"Ошибка при проверке состояния соединения: {e}")
                        # Предполагаем, что соединение может быть повреждено
                        if ws in active_connections:
                            active_connections.remove(ws)
                        continue
                        
                    # Отправляем application-level ping
                    timestamp = time.time()
                    await ws.send(json.dumps({
                        "type": "ping",
                        "timestamp": timestamp
                    }))
                except ConnectionClosed:
                    # Соединение было закрыто, удаляем его из активных
                    logger.debug(f"Соединение закрыто при попытке отправки ping, удаляем из активных")
                    if ws in active_connections:
                        active_connections.remove(ws)
                except Exception as e:
                    logger.error(f"Ошибка при отправке ping: {e}")
                    # Удаляем соединение из активных для предотвращения повторных ошибок
                    if ws in active_connections:
                        active_connections.remove(ws)
    except asyncio.CancelledError:
        logger.info("Задача периодической отправки ping отменена")
    except Exception as e:
        logger.error(f"Ошибка в periodic_ping_all_connections: {e}")
        logger.error(traceback.format_exc())

# Код удален, т.к. он перемещен в функцию run_server


# Только если модуль запущен напрямую, а не импортирован
if __name__ == "__main__":
    # Настройка логирования в начале программы
    configure_logging()
    # Запуск сервера
    run_server()