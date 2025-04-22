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
    try:
        # Проверка валидности данных
        if not resource_data or not isinstance(resource_data, dict):
            logger.warning(f"STATE_MANAGER: Получены невалидные данные ресурса: {resource_data}")
            return

        # Создание ключа ресурса
        namespace = resource_data.get("namespace", "")
        name = resource_data.get("name", "")

        if not name:
            logger.warning(f"STATE_MANAGER: Получены данные ресурса без имени: {resource_data}")
            return

        resource_key = (resource_type, namespace, name)

        # Для статистики - до изменений
        existing = resource_key in _resource_state

        # Отладочное сообщение для мониторинга входящих данных
        logger.info(f"STATE_MANAGER: Получено событие {event_type} для {resource_type}/{namespace}/{name} (существует: {existing})")

        # Проверяем, что тип ресурса поддерживается
        if resource_type not in ["namespaces", "deployments", "pods", "statefulsets"]:
            logger.warning(f"STATE_MANAGER: Неподдерживаемый тип ресурса: {resource_type}")
            return

        # Используем короткую блокировку только для обновления словаря
        try:
            async with _lock:
                # Обновление состояния в зависимости от типа события
                if event_type == "DELETED":
                    _resource_state.pop(resource_key, None)
                    logger.debug(f"STATE_MANAGER: Удален ресурс {resource_type}/{namespace}/{name}")
                else:  # 'ADDED' или 'MODIFIED' или 'INITIAL'
                    _resource_state[resource_key] = resource_data
                    logger.debug(f"STATE_MANAGER: {'Добавлен' if not existing else 'Обновлен'} ресурс {resource_type}/{namespace}/{name}")

                # Отладка: показать количество хранимых ресурсов
                total_resources = len(_resource_state)
                resources_by_type = {}
                for (rt, _, _), _ in _resource_state.items():
                    resources_by_type[rt] = resources_by_type.get(rt, 0) + 1

                logger.info(f"STATE_MANAGER: Текущее состояние - всего {total_resources} ресурсов: {resources_by_type}")

        except Exception as e:
            logger.error(f"STATE_MANAGER: Ошибка при обновлении состояния ресурса: {e}")
            logger.exception("STATE_MANAGER: Подробности ошибки:")
            return

        # Создаем задачу для оповещения подписчиков без ожидания ее завершения
        # Это предотвращает блокировку основного цикла
        asyncio.create_task(notify_subscribers(event_type, resource_type, resource_data))

    except Exception as e:
        logger.error(f"STATE_MANAGER: Критическая ошибка при обработке события {event_type} для {resource_type}: {e}")
        logger.exception("STATE_MANAGER: Подробности критической ошибки:")

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
        logger.debug(f"STATE_MANAGER: Нет подписчиков для типа ресурса {resource_type}, событие не будет отправлено")
        return

    try:
        # Получаем копию списка подписчиков, чтобы не блокировать его при оповещении
        subscribers = set()
        async with _lock:
            subscribers = set(_subscribers.get(resource_type, set()))

        # Логируем количество подписчиков
        # logger.info(f"STATE_MANAGER: Оповещение {len(subscribers)} подписчиков о событии {event_type} для ресурса {resource_type}/{resource_data.get('namespace', '')}/{resource_data.get('name', '')}")

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

            # Логируем результаты отправки
            # logger.info(f"STATE_MANAGER: Отправлено {len(done)} успешных уведомлений, {len(pending)} не завершились в срок")

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

    # Более подробное логирование для подписок
    subscriber_counts = {rt: len(subs) for rt, subs in _subscribers.items()}
    logger.info(f"STATE_MANAGER: Добавлена подписка на {resource_type}. Текущие подписки: {subscriber_counts}")

    # Возвращаем функцию для отмены подписки
    def unsubscribe() -> None:
        if resource_type in _subscribers and callback in _subscribers[resource_type]:
            _subscribers[resource_type].remove(callback)
            # Обновленная информация о подписках после удаления
            remaining_counts = {rt: len(subs) for rt, subs in _subscribers.items()}
            logger.info(f"STATE_MANAGER: Удалена подписка на {resource_type}. Оставшиеся подписки: {remaining_counts}")

    return unsubscribe

def get_resources_by_type(resource_type: ResourceType) -> List[ResourceData]:
    """Получение всех ресурсов указанного типа.

    Args:
        resource_type: Тип ресурса ('deployments', 'pods', 'namespaces', etc.)

    Returns:
        List[ResourceData]: Список данных о ресурсах
    """
    resources = []

    # Подсчет ресурсов по типам для диагностики
    resource_counts = {}
    for (rtype, _, _), _ in _resource_state.items():
        resource_counts[rtype] = resource_counts.get(rtype, 0) + 1

    # Добавление ресурсов нужного типа в список с гарантированной проверкой валидности
    for (rtype, ns, name), data in _resource_state.items():
        if rtype == resource_type:
            # Проверка обязательных полей
            if not isinstance(data, dict):
                logger.warning(f"STATE_MANAGER: Найден невалидный ресурс {rtype}/{ns}/{name} - не словарь")
                continue

            if 'name' not in data:
                # Добавляем имя из ключа, если его нет в данных
                data['name'] = name
                logger.warning(f"STATE_MANAGER: Восстановлено имя ресурса {rtype}/{ns}/{name}")

            if resource_type == 'namespaces' and 'namespace' in data:
                # У namespace не должно быть поля namespace
                pass
            elif resource_type != 'namespaces' and 'namespace' not in data:
                # Для не-namespace ресурсов добавляем namespace из ключа
                data['namespace'] = ns
                logger.warning(f"STATE_MANAGER: Восстановлен namespace для ресурса {rtype}/{ns}/{name}")

            # Добавляем ресурс после проверок и возможных исправлений
            resources.append(data)

    # Логирование для отладки
    logger.info(f"STATE_MANAGER: Запрошены ресурсы типа {resource_type}, найдено {len(resources)} из {len(_resource_state)} ресурсов в кэше")
    logger.info(f"STATE_MANAGER: Распределение ресурсов по типам: {resource_counts}")

    # Если не найдено ни одного ресурса, но в кэше есть другие ресурсы - это странно, логируем подробнее
    if len(resources) == 0 and len(_resource_state) > 0:
        logger.warning(f"STATE_MANAGER: ВНИМАНИЕ! Запрошены ресурсы типа {resource_type}, но ни один не найден, хотя в кэше есть {len(_resource_state)} ресурсов")
        # Логируем первые несколько ключей для диагностики
        sample_keys = list(_resource_state.keys())[:5]
        logger.warning(f"STATE_MANAGER: Образцы ключей в кэше: {sample_keys}")

        # Для типов, которых точно нет в кэше, выводим предупреждение
        if resource_type not in resource_counts:
            logger.warning(f"STATE_MANAGER: В кэше отсутствуют ресурсы типа {resource_type}")

    # Проверка целостности данных в ресурсах
    for resource in resources:
        if not isinstance(resource, dict):
            logger.error(f"STATE_MANAGER: Невалидный ресурс в списке: {resource}")
            resources.remove(resource)

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
