"""Модуль для работы с WebSocket соединениями."""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Set, Optional, Callable, Awaitable

from fastapi import WebSocket, WebSocketDisconnect
import os

from dashboard_light.state_manager import (
    subscribe, get_resources_by_type, get_resource,
    get_resources_by_namespace
)

logger = logging.getLogger(__name__)

# Типы для аннотаций
ResourceType = str  # 'deployments', 'pods', 'namespaces'
EventType = str  # 'ADDED', 'MODIFIED', 'DELETED'
Connection = WebSocket  # Соединение WebSocket
ConnectionId = str  # Уникальный идентификатор соединения
User = Dict[str, Any]  # Данные пользователя

# Словарь активных соединений по ID
_active_connections: Dict[ConnectionId, Connection] = {}

# Словарь подписок по типу ресурса
_subscriptions: Dict[ResourceType, Set[ConnectionId]] = {}

# Словарь пользовательских данных по ID соединения
_connection_data: Dict[ConnectionId, Dict[str, Any]] = {}

async def handle_connection(websocket: WebSocket, app_config: Dict[str, Any]) -> None:
    """Обработка WebSocket соединения.

    Args:
        websocket: WebSocket соединение
        app_config: Конфигурация приложения
    """
    # Принятие соединения
    await websocket.accept()

    # Генерация уникального ID для соединения
    connection_id = f"{id(websocket)}_{time.time()}"

    try:
        # Получение и проверка аутентификации пользователя
        user = await authenticate_connection(websocket, app_config)

        # Регистрация соединения
        _active_connections[connection_id] = websocket
        _connection_data[connection_id] = {
            "user": user,
            "created_at": time.time(),
            "last_activity": time.time(),
            "subscribed_resources": set()
        }

        logger.info(f"Новое WebSocket соединение установлено: {connection_id}")

        # Отправка сообщения о успешном подключении
        await websocket.send_json({
            "type": "connection",
            "status": "connected",
            "message": "Соединение установлено"
        })

        # Обработка сообщений от клиента
        await handle_messages(connection_id, websocket)
    except WebSocketDisconnect:
        logger.info(f"Клиент отключился: {connection_id}")
    except Exception as e:
        logger.error(f"Ошибка при обработке WebSocket соединения: {str(e)}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Ошибка обработки соединения: {str(e)}"
            })
        except Exception:
            pass
    finally:
        # Очистка при отключении
        await disconnect(connection_id)

async def authenticate_connection(websocket: WebSocket, app_config: Dict[str, Any]) -> User:
    """Аутентификация WebSocket соединения.

    Args:
        websocket: WebSocket соединение
        app_config: Конфигурация приложения

    Returns:
        User: Данные пользователя

    Raises:
        WebSocketDisconnect: Если аутентификация не удалась
    """
    # Проверяем, отключена ли аутентификация в режиме разработки
    auth_disabled = os.environ.get("DISABLE_AUTH", "false").lower() in ["true", "1", "yes", "y"]

    if auth_disabled:
        # В режиме разработки используем тестового пользователя
        return {
            "id": 1,
            "username": "dev-user",
            "name": "Developer",
            "email": "dev@example.com",
            "roles": ["admin"]
        }

    # Получение сессионного cookie для проверки аутентификации
    cookies = websocket.cookies
    session_cookie = cookies.get("session")

    if not session_cookie:
        # Если cookie нет, проверяем настройку анонимного доступа
        auth_config = app_config.get("auth", {})
        allow_anonymous = auth_config.get("allow_anonymous_access", False)

        if not allow_anonymous:
            await websocket.close(code=1008, reason="Требуется аутентификация")
            raise WebSocketDisconnect(code=1008)

        # Возвращаем анонимного пользователя
        return {
            "id": 0,
            "username": "anonymous",
            "name": "Anonymous",
            "roles": [auth_config.get("anonymous_role", "guest")]
        }

    # TODO: Реализовать проверку сессии и получение пользователя
    # В реальной реализации здесь должна быть проверка сессии и получение пользователя

    # Пока возвращаем тестового пользователя
    return {
        "id": 1,
        "username": "test-user",
        "name": "Test User",
        "email": "test@example.com",
        "roles": ["admin"]
    }

async def handle_messages(connection_id: ConnectionId, websocket: WebSocket) -> None:
    """Обработка сообщений от клиента.

    Args:
        connection_id: ID соединения
        websocket: WebSocket соединение
    """
    async for message in websocket.iter_json():
        try:
            # Обновление времени последней активности
            if connection_id in _connection_data:
                _connection_data[connection_id]["last_activity"] = time.time()

            # Обработка сообщения
            message_type = message.get("type")

            if message_type == "subscribe":
                # Подписка на ресурс
                resource_type = message.get("resourceType")
                namespace = message.get("namespace")

                if resource_type:
                    await subscribe_to_resource(connection_id, resource_type, namespace)

                    # Отправка текущего состояния для начального заполнения
                    await send_initial_state(connection_id, resource_type, namespace)
            elif message_type == "unsubscribe":
                # Отписка от ресурса
                resource_type = message.get("resourceType")

                if resource_type:
                    await unsubscribe_from_resource(connection_id, resource_type)
            elif message_type == "ping":
                # Ответ на пинг
                await websocket.send_json({"type": "pong", "timestamp": time.time()})
            else:
                logger.warning(f"Неизвестный тип сообщения: {message_type}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"Неизвестный тип сообщения: {message_type}"
                })
        except json.JSONDecodeError:
            logger.warning(f"Получено некорректное JSON сообщение")
            await websocket.send_json({
                "type": "error",
                "message": "Некорректный формат сообщения"
            })
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения: {str(e)}")
            await websocket.send_json({
                "type": "error",
                "message": f"Ошибка обработки сообщения: {str(e)}"
            })

async def subscribe_to_resource(
    connection_id: ConnectionId,
    resource_type: ResourceType,
    namespace: Optional[str] = None
) -> None:
    """Подписка соединения на обновления ресурса.

    Args:
        connection_id: ID соединения
        resource_type: Тип ресурса
        namespace: Опциональный неймспейс для фильтрации
    """
    # Добавление подписки в глобальный словарь
    if resource_type not in _subscriptions:
        _subscriptions[resource_type] = set()

    _subscriptions[resource_type].add(connection_id)

    # Добавление информации о подписке в данные соединения
    if connection_id in _connection_data:
        if "subscribed_resources" not in _connection_data[connection_id]:
            _connection_data[connection_id]["subscribed_resources"] = set()

        _connection_data[connection_id]["subscribed_resources"].add(resource_type)

        if namespace:
            _connection_data[connection_id][f"{resource_type}_namespace"] = namespace

    # Подписка на обновления в менеджере состояния, если это первая подписка на этот ресурс
    if len(_subscriptions.get(resource_type, set())) == 1:
        # Создаем замыкание для фильтрации по namespace
        async def resource_callback(
            event_type: EventType,
            resource_type: ResourceType,
            resource_data: Dict[str, Any]
        ) -> None:
            # Рассылка обновления всем подписчикам
            await broadcast_resource_update(event_type, resource_type, resource_data)

        subscribe(resource_type, resource_callback)

    logger.debug(f"Соединение {connection_id} подписалось на {resource_type}" +
                 (f" в неймспейсе {namespace}" if namespace else ""))

    # Отправка подтверждения подписки
    websocket = _active_connections.get(connection_id)
    if websocket:
        await websocket.send_json({
            "type": "subscribed",
            "resourceType": resource_type,
            "namespace": namespace
        })

async def unsubscribe_from_resource(
    connection_id: ConnectionId,
    resource_type: ResourceType
) -> None:
    """Отписка соединения от обновлений ресурса.

    Args:
        connection_id: ID соединения
        resource_type: Тип ресурса
    """
    # Удаление из словаря подписок
    if resource_type in _subscriptions and connection_id in _subscriptions[resource_type]:
        _subscriptions[resource_type].remove(connection_id)

        # Если больше нет подписчиков, можно очистить словарь
        if not _subscriptions[resource_type]:
            del _subscriptions[resource_type]

    # Удаление из данных соединения
    if connection_id in _connection_data:
        if "subscribed_resources" in _connection_data[connection_id]:
            if resource_type in _connection_data[connection_id]["subscribed_resources"]:
                _connection_data[connection_id]["subscribed_resources"].remove(resource_type)

        # Удаление информации о namespace
        if f"{resource_type}_namespace" in _connection_data[connection_id]:
            del _connection_data[connection_id][f"{resource_type}_namespace"]

    logger.debug(f"Соединение {connection_id} отписалось от {resource_type}")

    # Отправка подтверждения отписки
    websocket = _active_connections.get(connection_id)
    if websocket:
        await websocket.send_json({
            "type": "unsubscribed",
            "resourceType": resource_type
        })

async def send_initial_state(
    connection_id: ConnectionId,
    resource_type: ResourceType,
    namespace: Optional[str] = None
) -> None:
    """Отправка текущего состояния ресурсов после подписки.

    Args:
        connection_id: ID соединения
        resource_type: Тип ресурса
        namespace: Опциональный неймспейс для фильтрации
    """
    websocket = _active_connections.get(connection_id)
    if not websocket:
        return

    # Получение ресурсов в зависимости от наличия namespace
    resources = []
    if namespace:
        resources = get_resources_by_namespace(resource_type, namespace)
    else:
        resources = get_resources_by_type(resource_type)

    # Отправка каждого ресурса отдельным сообщением
    for resource in resources:
        try:
            await websocket.send_json({
                "type": "resource",
                "eventType": "INITIAL",
                "resourceType": resource_type,
                "resource": resource
            })
        except Exception as e:
            logger.error(f"Ошибка при отправке начального состояния: {str(e)}")
            break

    # Отправка сообщения о завершении начальной загрузки
    await websocket.send_json({
        "type": "initial_state_complete",
        "resourceType": resource_type,
        "count": len(resources),
        "namespace": namespace
    })

async def broadcast_resource_update(
    event_type: EventType,
    resource_type: ResourceType,
    resource_data: Dict[str, Any]
) -> None:
    """Рассылка обновления ресурса всем подписчикам.

    Args:
        event_type: Тип события ('ADDED', 'MODIFIED', 'DELETED')
        resource_type: Тип ресурса
        resource_data: Данные о ресурсе
    """
    if resource_type not in _subscriptions:
        return

    # Список соединений для удаления в случае ошибок
    to_remove = []
    resource_namespace = resource_data.get("namespace", "")

    # Рассылка всем подписчикам с учетом фильтрации по namespace
    for connection_id in _subscriptions[resource_type]:
        try:
            # Проверка фильтра по namespace
            if connection_id in _connection_data:
                ns_filter = _connection_data[connection_id].get(f"{resource_type}_namespace")

                # Если указан фильтр и неймспейс не совпадает, пропускаем
                if ns_filter and ns_filter != resource_namespace:
                    continue

            # Получение WebSocket соединения
            websocket = _active_connections.get(connection_id)
            if not websocket:
                to_remove.append(connection_id)
                continue

            # Отправка обновления
            await websocket.send_json({
                "type": "resource",
                "eventType": event_type,
                "resourceType": resource_type,
                "resource": resource_data
            })
        except WebSocketDisconnect:
            to_remove.append(connection_id)
        except Exception as e:
            logger.error(f"Ошибка при отправке обновления: {str(e)}")
            to_remove.append(connection_id)

    # Удаление соединений с ошибками
    for connection_id in to_remove:
        await disconnect(connection_id)

async def disconnect(connection_id: ConnectionId) -> None:
    """Отключение и очистка ресурсов WebSocket соединения.

    Args:
        connection_id: ID соединения
    """
    # Удаление из всех подписок
    for resource_type in list(_subscriptions.keys()):
        if connection_id in _subscriptions[resource_type]:
            _subscriptions[resource_type].remove(connection_id)

            # Если больше нет подписчиков, удаляем ключ
            if not _subscriptions[resource_type]:
                del _subscriptions[resource_type]

    # Закрытие соединения
    websocket = _active_connections.pop(connection_id, None)
    if websocket:
        try:
            await websocket.close()
        except Exception:
            pass

    # Удаление данных соединения
    _connection_data.pop(connection_id, None)

    logger.debug(f"Соединение {connection_id} закрыто и очищено")

async def clean_inactive_connections(max_inactivity_seconds: int = 3600) -> None:
    """Очистка неактивных соединений.

    Args:
        max_inactivity_seconds: Максимально допустимое время неактивности
    """
    current_time = time.time()
    inactive_connections = []

    # Поиск неактивных соединений
    for connection_id, data in _connection_data.items():
        last_activity = data.get("last_activity", 0)
        if current_time - last_activity > max_inactivity_seconds:
            inactive_connections.append(connection_id)

    # Отключение неактивных соединений
    for connection_id in inactive_connections:
        logger.info(f"Отключение неактивного соединения {connection_id}")
        await disconnect(connection_id)

    if inactive_connections:
        logger.info(f"Очищено {len(inactive_connections)} неактивных соединений")
