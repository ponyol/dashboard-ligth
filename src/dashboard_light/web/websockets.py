"""Модуль для работы с WebSockets."""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional, Set, Callable, Awaitable
from datetime import datetime

import re
from fastapi import WebSocket, WebSocketDisconnect, status
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)

# Максимальное количество сообщений в очереди на клиента
MAX_QUEUE_SIZE = 100


class ConnectionManager:
    """Менеджер WebSocket соединений."""

    def __init__(self):
        """Инициализация менеджера соединений."""
        self.active_connections: List[WebSocket] = []
        self.connections_by_user: Dict[str, List[WebSocket]] = {}
        self.connections_by_resource: Dict[str, Set[WebSocket]] = {}
        self.connections_by_namespace: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        """Подключение нового клиента.

        Args:
            websocket: WebSocket соединение
            user_id: Идентификатор пользователя
        """
        try:
            # Предполагаем, что соединение уже принято
            # Сохранение информации о пользователе и времени подключения
            websocket.state.user_id = user_id
            websocket.state.connected_at = datetime.now()
            websocket.state.subscriptions = set()
            websocket.state.namespaces = set()

            # Добавление соединения в списки
            self.active_connections.append(websocket)

            if user_id not in self.connections_by_user:
                self.connections_by_user[user_id] = []
            self.connections_by_user[user_id].append(websocket)

            logger.info(f"WebSocket: Пользователь {user_id} подключился")

            # Отправка сообщения о успешном подключении
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json({
                    "type": "connection",
                    "status": "connected",
                    "timestamp": datetime.now().isoformat()
                })
                return True
            return False

        except Exception as e:
            logger.error(f"WebSocket: Ошибка при подключении пользователя {user_id}: {str(e)}")
            # Если соединение активно, отправляем сообщение об ошибке
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Ошибка при настройке соединения: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    })
                except Exception as send_error:
                    logger.error(f"WebSocket: Ошибка при отправке сообщения об ошибке: {str(send_error)}")
            return False

    def disconnect(self, websocket: WebSocket):
        """Отключение клиента.

        Args:
            websocket: WebSocket соединение
        """
        try:
            # Получение информации о пользователе
            user_id = getattr(websocket.state, "user_id", "unknown")

            # Удаление из списков подписок
            for resource_type in list(self.connections_by_resource.keys()):
                if websocket in self.connections_by_resource[resource_type]:
                    self.connections_by_resource[resource_type].remove(websocket)
                    # Удаление пустых множеств
                    if not self.connections_by_resource[resource_type]:
                        del self.connections_by_resource[resource_type]

            # Удаление из списков namespace
            for namespace in list(self.connections_by_namespace.keys()):
                if websocket in self.connections_by_namespace[namespace]:
                    self.connections_by_namespace[namespace].remove(websocket)
                    # Удаление пустых множеств
                    if not self.connections_by_namespace[namespace]:
                        del self.connections_by_namespace[namespace]

            # Удаление из списка по пользователю
            if user_id in self.connections_by_user:
                if websocket in self.connections_by_user[user_id]:
                    self.connections_by_user[user_id].remove(websocket)

                # Удаление пустых списков
                if not self.connections_by_user[user_id]:
                    del self.connections_by_user[user_id]

            # Удаление из списка активных соединений
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

            logger.info(f"WebSocket: Пользователь {user_id} отключился")

        except Exception as e:
            logger.error(f"WebSocket: Ошибка при отключении: {str(e)}")

    async def subscribe(self, websocket: WebSocket, resource_type: str, namespace: Optional[str] = None):
        """Подписка клиента на обновления ресурсов.

        Args:
            websocket: WebSocket соединение
            resource_type: Тип ресурса ('deployments', 'pods', etc.)
            namespace: Пространство имен (None для всех)
        """
        try:
            # Добавление в список подписок по типу ресурса
            if resource_type not in self.connections_by_resource:
                self.connections_by_resource[resource_type] = set()
            self.connections_by_resource[resource_type].add(websocket)

            # Добавление в список подписок пользователя
            if not hasattr(websocket.state, "subscriptions"):
                websocket.state.subscriptions = set()
            websocket.state.subscriptions.add(resource_type)

            # Подписка на namespace если указан
            if namespace:
                if namespace not in self.connections_by_namespace:
                    self.connections_by_namespace[namespace] = set()
                self.connections_by_namespace[namespace].add(websocket)

                if not hasattr(websocket.state, "namespaces"):
                    websocket.state.namespaces = set()
                websocket.state.namespaces.add(namespace)

            # Получение идентификатора пользователя
            user_id = getattr(websocket.state, "user_id", "unknown")

            subscription_info = {
                "resource_type": resource_type,
                "namespace": namespace
            }

            logger.info(f"WebSocket: Пользователь {user_id} подписался на {subscription_info}")

            # Отправка подтверждения подписки
            await websocket.send_json({
                "type": "subscription",
                "status": "subscribed",
                "resource_type": resource_type,
                "namespace": namespace,
                "timestamp": datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"WebSocket: Ошибка при подписке: {str(e)}")
            # Отправка сообщения об ошибке
            try:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Ошибка при подписке на {resource_type}/{namespace}: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                })
            except:
                pass

    async def unsubscribe(self, websocket: WebSocket, resource_type: str, namespace: Optional[str] = None):
        """Отписка клиента от обновлений ресурсов.

        Args:
            websocket: WebSocket соединение
            resource_type: Тип ресурса ('deployments', 'pods', etc.)
            namespace: Пространство имен (None для всех)
        """
        try:
            # Удаление из списка подписок по ресурсу
            if resource_type in self.connections_by_resource and websocket in self.connections_by_resource[resource_type]:
                self.connections_by_resource[resource_type].remove(websocket)
                # Удаление пустых множеств
                if not self.connections_by_resource[resource_type]:
                    del self.connections_by_resource[resource_type]

            # Удаление из списка подписок пользователя
            if hasattr(websocket.state, "subscriptions") and resource_type in websocket.state.subscriptions:
                websocket.state.subscriptions.remove(resource_type)

            # Отписка от namespace если указан
            if namespace:
                if namespace in self.connections_by_namespace and websocket in self.connections_by_namespace[namespace]:
                    self.connections_by_namespace[namespace].remove(websocket)
                    # Удаление пустых множеств
                    if not self.connections_by_namespace[namespace]:
                        del self.connections_by_namespace[namespace]

                if hasattr(websocket.state, "namespaces") and namespace in websocket.state.namespaces:
                    websocket.state.namespaces.remove(namespace)

            # Получение идентификатора пользователя
            user_id = getattr(websocket.state, "user_id", "unknown")

            logger.info(f"WebSocket: Пользователь {user_id} отписался от {resource_type}/{namespace}")

            # Отправка подтверждения отписки
            await websocket.send_json({
                "type": "subscription",
                "status": "unsubscribed",
                "resource_type": resource_type,
                "namespace": namespace,
                "timestamp": datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"WebSocket: Ошибка при отписке: {str(e)}")
            # Отправка сообщения об ошибке
            try:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Ошибка при отписке от {resource_type}/{namespace}: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                })
            except:
                pass

    async def broadcast_resource_event(
        self,
        resource_type: str,
        event_type: str,
        resource: Dict[str, Any],
        namespace: Optional[str] = None
    ):
        """Рассылка события ресурса всем подписанным клиентам.

        Args:
            resource_type: Тип ресурса ('deployments', 'pods', etc.)
            event_type: Тип события ('ADDED', 'MODIFIED', 'DELETED')
            resource: Данные ресурса
            namespace: Пространство имен ресурса (опционально)
        """
        if not resource:
            return

        # Автоматическое определение namespace из ресурса, если не указан явно
        if not namespace and "namespace" in resource:
            namespace = resource["namespace"]

        # Формирование сообщения
        message = {
            "type": "resource",
            "resource_type": resource_type,
            "action": event_type,
            "resource": resource,
            "namespace": namespace,
            "timestamp": datetime.now().isoformat()
        }

        # Список соединений для отправки
        connections_to_send = set()

        # Получение всех подписанных соединений
        if resource_type in self.connections_by_resource:
            connections_to_send.update(self.connections_by_resource[resource_type])

        # Фильтрация по namespace
        if namespace and namespace in self.connections_by_namespace:
            namespace_connections = self.connections_by_namespace[namespace]
            connections_to_send = connections_to_send.intersection(namespace_connections) if connections_to_send else set(namespace_connections)

        # Если нет подписок, выходим
        if not connections_to_send:
            return

        # Фильтрация для каждого соединения по правам доступа
        disconnected = []

        for websocket in connections_to_send:
            try:
                # Проверка доступа пользователя к namespace ресурса
                if namespace and hasattr(websocket.state, "namespaces") and websocket.state.namespaces:
                    if "*" not in websocket.state.namespaces and namespace not in websocket.state.namespaces:
                        # У пользователя нет доступа к этому namespace
                        continue

                # Отправка сообщения
                await websocket.send_json(message)

            except WebSocketDisconnect:
                disconnected.append(websocket)
            except Exception as e:
                logger.error(f"WebSocket: Ошибка при отправке данных: {str(e)}")
                disconnected.append(websocket)

        # Удаление отключенных соединений
        for websocket in disconnected:
            self.disconnect(websocket)


    async def send_error(self, websocket: WebSocket, message: str):
        """Отправка сообщения об ошибке клиенту.

        Args:
            websocket: WebSocket соединение
            message: Текст сообщения об ошибке
        """
        try:
            await websocket.send_json({
                "type": "error",
                "message": message,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"WebSocket: Ошибка при отправке сообщения об ошибке: {str(e)}")

    def get_connection_stats(self) -> Dict[str, Any]:
        """Получение статистики соединений.

        Returns:
            Dict[str, Any]: Статистика соединений
        """
        return {
            "active_connections": len(self.active_connections),
            "users_connected": len(self.connections_by_user),
            "resource_subscriptions": {
                resource_type: len(connections)
                for resource_type, connections in self.connections_by_resource.items()
            },
            "namespace_subscriptions": {
                namespace: len(connections)
                for namespace, connections in self.connections_by_namespace.items()
            }
        }


# Глобальный менеджер соединений
connection_manager = ConnectionManager()


async def filter_namespaces_by_access(
    request: Dict[str, Any],
    app_config: Dict[str, Any],
    user_id: str
) -> List[str]:
    """Функция для фильтрации неймспейсов по правам доступа пользователя.

    Args:
        request: Данные запроса
        app_config: Конфигурация приложения
        user_id: Идентификатор пользователя

    Returns:
        List[str]: Список разрешенных namespace
    """
    # Проверка, отключена ли аутентификация в режиме разработки
    auth_disabled = os.environ.get("DISABLE_AUTH", "false").lower() in ["true", "1", "yes", "y"]

    # Получаем паттерны фильтрации из конфигурации
    namespace_patterns = app_config.get("default", {}).get("namespace_patterns", [])

    if auth_disabled or not namespace_patterns:
        # Если аутентификация отключена или нет паттернов, разрешаем все
        return ["*"]

    # Проверка пользователя в сессии
    user = request.get("user")

    # Если пользователь не аутентифицирован
    if not user:
        # Проверка анонимного доступа
        auth_config = app_config.get("auth", {})
        allow_anonymous = auth_config.get("allow_anonymous_access", False)

        if not allow_anonymous:
            return []

        # Использование роли по умолчанию для анонимов
        anonymous_role = auth_config.get("anonymous_role")
        if not anonymous_role:
            return []

        # Получение разрешенных namespace для роли
        permissions = auth_config.get("permissions", {}).get(anonymous_role, {})
        allowed_patterns = permissions.get("allowed_namespace_patterns", [])

        return allowed_patterns or []

    # Для аутентифицированных пользователей
    roles = user.get("roles", [])

    # Объединение разрешенных паттернов из всех ролей
    allowed_patterns = []
    auth_config = app_config.get("auth", {})
    permissions = auth_config.get("permissions", {})

    for role in roles:
        role_permissions = permissions.get(role, {})
        role_patterns = role_permissions.get("allowed_namespace_patterns", [])
        allowed_patterns.extend(role_patterns)

    # Если список пуст или содержит "*", разрешаем все
    if not allowed_patterns or "*" in allowed_patterns:
        return ["*"]

    return allowed_patterns


async def process_websocket_message(
    websocket: WebSocket,
    data: Dict[str, Any],
    app_config: Dict[str, Any]
):
    """Обработка сообщений от клиента через WebSocket.

    Args:
        websocket: WebSocket соединение
        data: Данные сообщения
        app_config: Конфигурация приложения
    """
    # Проверка состояния соединения перед обработкой
    if websocket.client_state != WebSocketState.CONNECTED:
        logger.warning(f"WebSocket не в состоянии CONNECTED (текущее состояние: {websocket.client_state}), пропуск обработки")
        return
        
    try:
        # Проверка типа сообщения
        message_type = data.get("type", "")
        logger.debug(f"WebSocket: Получено сообщение типа '{message_type}'")

        if not message_type:
            await connection_manager.send_error(websocket, "Не указан тип сообщения")
            return

        # Получение идентификатора пользователя
        user_id = getattr(websocket.state, "user_id", "anonymous")

        # Обработка пинга (самое простое сообщение, обрабатываем первым)
        if message_type == "ping":
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })
            return

        # Обработка подписки на ресурсы
        if message_type == "subscribe":
            resource_type = data.get("resource_type")
            namespace = data.get("namespace")

            if not resource_type:
                await connection_manager.send_error(websocket, "Не указан тип ресурса для подписки")
                return

            # Проверка доступа к namespace, если указан
            if namespace:
                # Просто заглушка для имитации проверки доступа
                user_namespaces = await filter_namespaces_by_access(
                    {"user": {"id": user_id, "roles": ["admin"]}},
                    app_config,
                    user_id
                )

                # Если у пользователя нет доступа к этому namespace
                if user_namespaces != ["*"] and namespace not in user_namespaces:
                    await connection_manager.send_error(
                        websocket,
                        f"Нет доступа к namespace {namespace}"
                    )
                    return

            # Подписка на ресурс (только если соединение все еще активно)
            if websocket.client_state == WebSocketState.CONNECTED:
                await connection_manager.subscribe(websocket, resource_type, namespace)
            else:
                logger.warning(f"WebSocket: Соединение закрылось перед подпиской на {resource_type}")

        # Обработка отписки от ресурсов
        elif message_type == "unsubscribe":
            resource_type = data.get("resource_type")
            namespace = data.get("namespace")

            if not resource_type:
                await connection_manager.send_error(websocket, "Не указан тип ресурса для отписки")
                return

            # Отписка от ресурса (только если соединение все еще активно)
            if websocket.client_state == WebSocketState.CONNECTED:
                await connection_manager.unsubscribe(websocket, resource_type, namespace)
            else:
                logger.warning(f"WebSocket: Соединение закрылось перед отпиской от {resource_type}")

        # Запрос статистики
        elif message_type == "stats":
            stats = connection_manager.get_connection_stats()
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json({
                    "type": "stats",
                    "data": stats,
                    "timestamp": datetime.now().isoformat()
                })

        # Неизвестный тип сообщения
        else:
            await connection_manager.send_error(websocket, f"Неизвестный тип сообщения: {message_type}")

    except Exception as e:
        logger.error(f"WebSocket: Ошибка обработки сообщения: {str(e)}")
        # Проверяем состояние соединения перед отправкой ошибки
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await connection_manager.send_error(websocket, f"Ошибка обработки сообщения: {str(e)}")
            else:
                logger.warning(f"WebSocket: Невозможно отправить сообщение об ошибке - соединение закрыто")
        except Exception as send_error:
            logger.error(f"WebSocket: Не удалось отправить сообщение об ошибке: {str(send_error)}")
