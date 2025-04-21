"""Модуль для управления состоянием ресурсов и передачи обновлений."""

import asyncio
import logging
from typing import Any, Dict, List, Set, Callable, Awaitable, Optional, Tuple

logger = logging.getLogger(__name__)

# Типы для аннотаций
ResourceType = str  # 'deployments', 'pods', 'namespaces', etc.
ResourceName = str  # Имя ресурса
ResourceNamespace = str  # Неймспейс ресурса
ResourceKey = Tuple[ResourceType, ResourceNamespace, ResourceName]  # Ключ для идентификации ресурса
ResourceData = Dict[str, Any]  # Данные ресурса
ResourceState = Dict[ResourceKey, ResourceData]  # Состояние всех ресурсов
EventType = str  # 'ADDED', 'MODIFIED', 'DELETED'
Callback = Callable[[EventType, ResourceType, ResourceData], Awaitable[None]]  # Callback для оповещения

# Глобальное состояние
_resource_state: ResourceState = {}
_subscribers: Dict[ResourceType, Set[Callback]] = {}
_lock = asyncio.Lock()

async def update_resource_state(
    event_type: EventType,
    resource_type: ResourceType,
    resource_data: ResourceData
) -> None:
    """Обновление состояния ресурса и оповещение подписчиков.

    Args:
        event_type: Тип события ('ADDED', 'MODIFIED', 'DELETED')
        resource_type: Тип ресурса ('deployments', 'pods', 'namespaces', etc.)
        resource_data: Данные о ресурсе
    """
    # Создание ключа ресурса
    namespace = resource_data.get("namespace", "")
    name = resource_data.get("name", "")

    if not name:
        logger.warning(f"Получены данные ресурса без имени: {resource_data}")
        return

    resource_key = (resource_type, namespace, name)
    
    # Используем короткую блокировку только для обновления словаря
    try:
        async with _lock:
            # Обновление состояния в зависимости от типа события
            if event_type == "DELETED":
                _resource_state.pop(resource_key, None)
                logger.debug(f"Удален ресурс {resource_type}/{namespace}/{name}")
            else:  # 'ADDED' или 'MODIFIED'
                _resource_state[resource_key] = resource_data
                logger.debug(f"Обновлен ресурс {resource_type}/{namespace}/{name}")
    except Exception as e:
        logger.error(f"Ошибка при обновлении состояния ресурса: {e}")
        return

    # Создаем задачу для оповещения подписчиков без ожидания ее завершения
    # Это предотвращает блокировку основного цикла
    asyncio.create_task(notify_subscribers(event_type, resource_type, resource_data))

async def notify_subscribers(
    event_type: EventType,
    resource_type: ResourceType,
    resource_data: ResourceData
) -> None:
    """Оповещение всех подписчиков о событии ресурса.

    Args:
        event_type: Тип события ('ADDED', 'MODIFIED', 'DELETED')
        resource_type: Тип ресурса ('deployments', 'pods', 'namespaces', etc.)
        resource_data: Данные о ресурсе
    """
    if resource_type not in _subscribers:
        return
    
    try:
        # Получаем копию списка подписчиков, чтобы не блокировать его при оповещении
        subscribers = set()
        async with _lock:
            subscribers = set(_subscribers.get(resource_type, set()))
        
        # Отправляем оповещения асинхронно без блокировки
        tasks = []
        for callback in subscribers:
            # Создаем отдельную задачу для каждого подписчика
            task = asyncio.create_task(
                safe_notify_subscriber(callback, event_type, resource_type, resource_data)
            )
            tasks.append(task)
        
        # Ждем завершения всех задач с таймаутом
        if tasks:
            # Ждем с таймаутом, но не блокируем, если некоторые задачи зависнут
            done, pending = await asyncio.wait(
                tasks, 
                timeout=5.0,  # Таймаут 5 секунд
                return_when=asyncio.ALL_COMPLETED
            )
            
            # Отменяем висящие задачи
            for task in pending:
                task.cancel()
                
    except Exception as e:
        logger.error(f"Ошибка при оповещении подписчиков: {e}")

async def safe_notify_subscriber(
    callback: Callback,
    event_type: EventType,
    resource_type: ResourceType,
    resource_data: ResourceData
) -> None:
    """Безопасное оповещение подписчика с обработкой ошибок.
    
    Args:
        callback: Функция обратного вызова
        event_type: Тип события
        resource_type: Тип ресурса
        resource_data: Данные о ресурсе
    """
    try:
        await callback(event_type, resource_type, resource_data)
    except Exception as e:
        logger.error(f"Ошибка при оповещении подписчика: {str(e)}")

def subscribe(
    resource_type: ResourceType,
    callback: Callback
) -> Callable[[], None]:
    """Подписка на события ресурса.

    Args:
        resource_type: Тип ресурса ('deployments', 'pods', 'namespaces', etc.)
        callback: Асинхронная функция обратного вызова для получения обновлений

    Returns:
        Callable[[], None]: Функция для отмены подписки
    """
    if resource_type not in _subscribers:
        _subscribers[resource_type] = set()

    _subscribers[resource_type].add(callback)
    logger.debug(f"Добавлена подписка на {resource_type}")

    # Возвращаем функцию для отмены подписки
    def unsubscribe() -> None:
        if resource_type in _subscribers and callback in _subscribers[resource_type]:
            _subscribers[resource_type].remove(callback)
            logger.debug(f"Удалена подписка на {resource_type}")

    return unsubscribe

def get_resources_by_type(resource_type: ResourceType) -> List[ResourceData]:
    """Получение всех ресурсов указанного типа.

    Args:
        resource_type: Тип ресурса ('deployments', 'pods', 'namespaces', etc.)

    Returns:
        List[ResourceData]: Список данных о ресурсах
    """
    resources = []

    for (rtype, _, _), data in _resource_state.items():
        if rtype == resource_type:
            resources.append(data)

    return resources

def get_resource(
    resource_type: ResourceType,
    namespace: ResourceNamespace,
    name: ResourceName
) -> Optional[ResourceData]:
    """Получение конкретного ресурса по типу, неймспейсу и имени.

    Args:
        resource_type: Тип ресурса ('deployments', 'pods', 'namespaces', etc.)
        namespace: Неймспейс ресурса
        name: Имя ресурса

    Returns:
        Optional[ResourceData]: Данные о ресурсе или None, если ресурс не найден
    """
    resource_key = (resource_type, namespace, name)
    return _resource_state.get(resource_key)

def get_resources_by_namespace(
    resource_type: ResourceType,
    namespace: ResourceNamespace
) -> List[ResourceData]:
    """Получение всех ресурсов указанного типа в заданном неймспейсе.

    Args:
        resource_type: Тип ресурса ('deployments', 'pods', 'namespaces', etc.)
        namespace: Неймспейс ресурса

    Returns:
        List[ResourceData]: Список данных о ресурсах
    """
    resources = []

    for (rtype, ns, _), data in _resource_state.items():
        if rtype == resource_type and ns == namespace:
            resources.append(data)

    return resources

def clear_state() -> None:
    """Очистка всего состояния ресурсов."""
    _resource_state.clear()
    logger.debug("Состояние ресурсов очищено")
