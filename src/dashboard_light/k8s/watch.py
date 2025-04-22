"""Модуль для работы с Kubernetes Watch API."""

import asyncio
import logging
import re
import time
import traceback
from typing import Any, Dict, List, Optional, Callable, Awaitable, Tuple, Set

from kubernetes import client, watch
from kubernetes.client.exceptions import ApiException

from dashboard_light.state_manager import update_resource_state
from dashboard_light.config.core import get_in_config
import dashboard_light.k8s.deployments as deployments
import dashboard_light.k8s.pods as pods
import dashboard_light.k8s.namespaces as namespaces
import dashboard_light.k8s.statefulsets as statefulsets

logger = logging.getLogger(__name__)

# Типы для аннотаций
ResourceType = str  # 'deployments', 'pods', 'namespaces', 'statefulsets'
WatchTask = asyncio.Task  # Задача асинхронного наблюдения

# Словарь активных задач наблюдения по типам ресурсов
_watch_tasks: Dict[ResourceType, WatchTask] = {}

# Константы для ограничения повторных подключений
RETRY_INITIAL_DELAY = 1  # Начальная задержка в секундах
RETRY_MAX_DELAY = 60  # Максимальная задержка в секундах
RETRY_BACKOFF_FACTOR = 2  # Коэффициент увеличения задержки

# Словарь функций для получения ресурсов разных типов
_resource_functions = {
    'deployments': {
        'list_func': lambda api: api.list_deployment_for_all_namespaces,
        'api_type': 'apps_v1_api',
        'convert_func': deployments.get_deployment_status
    },
    'pods': {
        'list_func': lambda api: api.list_pod_for_all_namespaces,
        'api_type': 'core_v1_api',
        'convert_func': pods.get_pod_status
    },
    'namespaces': {
        'list_func': lambda api: api.list_namespace,
        'api_type': 'core_v1_api',
        'convert_func': None
    },
    'statefulsets': {
        'list_func': lambda api: api.list_stateful_set_for_all_namespaces,
        'api_type': 'apps_v1_api',
        'convert_func': statefulsets.get_statefulset_status
    }
}

# Глобальная переменная для хранения паттернов неймспейсов
_namespace_patterns: List[str] = []

# Новые глобальные переменные для прямой доставки событий
_direct_subscribers = {}  # Словарь подписчиков для прямой доставки

# Новые функции для прямой доставки событий
def add_direct_subscriber(callback):
    """Добавляет подписчика для прямой доставки событий, минуя state_manager.

    Args:
        callback: Асинхронная функция для обработки событий

    Returns:
        str: ID подписчика для последующего удаления
    """
    subscriber_id = str(id(callback))
    _direct_subscribers[subscriber_id] = callback
    logger.info(f"K8S_WATCH: Добавлен прямой подписчик {subscriber_id}, всего: {len(_direct_subscribers)}")
    return subscriber_id

def remove_direct_subscriber(subscriber_id):
    """Удаляет подписчика прямой доставки.

    Args:
        subscriber_id: ID подписчика
    """
    if subscriber_id in _direct_subscribers:
        del _direct_subscribers[subscriber_id]
        logger.info(f"K8S_WATCH: Удален прямой подписчик {subscriber_id}, осталось: {len(_direct_subscribers)}")

def _get_api_instance(k8s_client: Dict[str, Any], resource_type: ResourceType) -> Any:
    """Получение экземпляра API для указанного типа ресурса.

    Args:
        k8s_client: Словарь с Kubernetes клиентами
        resource_type: Тип ресурса ('deployments', 'pods', 'namespaces')

    Returns:
        Any: Экземпляр API или None, если не найден
    """
    api_type = _resource_functions.get(resource_type, {}).get('api_type')
    if not api_type:
        logger.error(f"Не найден тип API для ресурса {resource_type}")
        return None

    api_instance = k8s_client.get(api_type)
    if not api_instance:
        logger.warning(f"API клиент для {api_type} не инициализирован")
        return None

    return api_instance

def _check_namespace_patterns(namespace: str) -> bool:
    """Проверка соответствия неймспейса заданным паттернам.

    Args:
        namespace: Имя неймспейса для проверки

    Returns:
        bool: True, если неймспейс соответствует хотя бы одному паттерну или паттерны не заданы
    """
    # Если паттерны не заданы, возвращаем True
    if not _namespace_patterns:
        return True

    # Проверяем соответствие каждому паттерну
    for pattern in _namespace_patterns:
        if re.match(pattern, namespace):
            return True

    return False

def _convert_to_dict(resource_type: ResourceType, resource: Any) -> Dict[str, Any]:
    """Преобразование объекта Kubernetes в словарь.

    Args:
        resource_type: Тип ресурса ('deployments', 'pods', 'namespaces')
        resource: Объект ресурса Kubernetes

    Returns:
        Dict[str, Any]: Словарь с данными ресурса
    """
    # Проверка на None
    if not resource:
        logger.warning(f"Получен пустой ресурс для преобразования: тип={resource_type}")
        return {}

    # Проверка наличия metadata
    if not hasattr(resource, 'metadata'):
        logger.warning(f"Ресурс не имеет metadata: тип={resource_type}, ресурс={type(resource)}")
        return {}

    metadata = resource.metadata
    namespace = getattr(metadata, "namespace", "")

    # Для ресурсов кроме 'namespaces' проверяем соответствие неймспейса паттернам
    if resource_type != 'namespaces' and namespace and not _check_namespace_patterns(namespace):
        logger.debug(f"Ресурс не соответствует паттернам неймспейсов: {resource_type}/{namespace}/{metadata.name}")
        return {}  # Пропускаем ресурсы из неподходящих неймспейсов

    # Базовые данные для всех типов ресурсов
    result = {
        "name": metadata.name,
        "namespace": namespace,
    }

    # Дополнительные данные в зависимости от типа ресурса
    if resource_type == 'deployments' or resource_type == 'statefulsets':
        # Преобразование для deployments и statefulsets
        try:
            spec = resource.spec
            status = resource.status

            # Получение информации о контейнерах
            containers = []
            if spec.template and spec.template.spec and spec.template.spec.containers:
                containers = spec.template.spec.containers

            main_container = containers[0] if containers else None

            # Формирование данных о деплойменте/statefulset
            replicas_data = {
                "desired": spec.replicas,
                "ready": status.ready_replicas if status.ready_replicas else 0,
                "updated": status.updated_replicas if status.updated_replicas else 0,
            }

            # Для deployments добавляем available_replicas, для statefulsets используем ready как available
            if resource_type == 'deployments':
                replicas_data["available"] = status.available_replicas if status.available_replicas else 0
            else:  # statefulsets
                replicas_data["available"] = status.ready_replicas if status.ready_replicas else 0

            result.update({
                "replicas": replicas_data
            })

            # Добавление информации о главном контейнере, если он есть
            if main_container:
                image = main_container.image
                image_tag = image.split(":")[-1] if ":" in image else "latest"

                result["main_container"] = {
                    "name": main_container.name,
                    "image": image,
                    "image_tag": image_tag,
                }

            # Добавление лейблов
            if metadata.labels:
                result["labels"] = metadata.labels

            # Добавление информации о владельце (owner references)
            if metadata.owner_references:
                owner_refs = []
                for ref in metadata.owner_references:
                    owner_refs.append({
                        "name": ref.name,
                        "kind": ref.kind,
                        "uid": ref.uid,
                    })
                result["owner_references"] = owner_refs

            # Добавление статуса
            if resource_type == 'deployments':
                result["status"] = deployments.get_deployment_status(result)
            else:  # statefulsets
                result["status"] = statefulsets.get_statefulset_status(result)
        except Exception as e:
            logger.error(f"Ошибка при преобразовании {resource_type}: {e}")
            logger.debug(f"Трассировка: {traceback.format_exc()}")

    elif resource_type == 'pods':
        # Преобразование для pods
        try:
            spec = resource.spec
            status = resource.status

            # Получение информации о контейнерах
            container_specs = spec.containers if spec and spec.containers else []
            containers = []

            for container_spec in container_specs:
                image = container_spec.image
                image_tag = image.split(":")[-1] if ":" in image else "latest"

                containers.append({
                    "name": container_spec.name,
                    "image": image,
                    "image_tag": image_tag,
                })

            # Дополнение данных о поде
            result.update({
                "phase": status.phase if status else "Unknown",
                "containers": containers,
                "pod_ip": status.pod_ip if status else None,
                "host_ip": status.host_ip if status else None,
                "started_at": status.start_time.isoformat() if status and status.start_time else None,
            })

            # Добавление лейблов
            if metadata.labels:
                result["labels"] = metadata.labels

            # Добавление статуса
            result["status"] = pods.get_pod_status(result)
        except Exception as e:
            logger.error(f"Ошибка при преобразовании {resource_type}: {e}")
            logger.debug(f"Трассировка: {traceback.format_exc()}")

    elif resource_type == 'namespaces':
        # Преобразование для namespaces
        try:
            # Проверяем соответствие неймспейса паттернам
            if not _check_namespace_patterns(metadata.name):
                logger.debug(f"Неймспейс не соответствует паттернам: {metadata.name}")
                return {}  # Пропускаем неподходящие неймспейсы

            result.update({
                "phase": resource.status.phase,
                "created": metadata.creation_timestamp.isoformat() if metadata.creation_timestamp else None,
                "labels": metadata.labels if metadata.labels else {},
            })
        except Exception as e:
            logger.error(f"Ошибка при преобразовании {resource_type}: {e}")
            logger.debug(f"Трассировка: {traceback.format_exc()}")

    return result

class WatchManager:
    """Класс для управления наблюдением за ресурсами Kubernetes."""

    def __init__(self, k8s_client: Dict[str, Any], resource_type: ResourceType):
        """Инициализация менеджера наблюдения.

        Args:
            k8s_client: Словарь с Kubernetes клиентами
            resource_type: Тип ресурса ('deployments', 'pods', 'namespaces', 'statefulsets')
        """
        self.k8s_client = k8s_client
        self.resource_type = resource_type
        self.api_instance = _get_api_instance(k8s_client, resource_type)
        self.list_func = _resource_functions[resource_type]['list_func'](self.api_instance)
        self.watcher = watch.Watch()
        self.resource_version = None
        self.running = False
        self.stop_event = asyncio.Event()
        self.last_event_time = 0
        self.event_queue = asyncio.Queue()
        self.reconnect_delay = RETRY_INITIAL_DELAY

    async def start(self):
        """Запуск процесса наблюдения за ресурсами."""
        if not self.api_instance:
            logger.error(f"WatchManager: Не удалось получить API клиент для {self.resource_type}")
            return

        self.running = True
        self.stop_event.clear()

        # Запускаем две сопрограммы: одну для наблюдения, другую для обработки событий
        watch_task = asyncio.create_task(self._watch_resources())
        process_task = asyncio.create_task(self._process_events())

        # Ждем завершения любой из задач
        done, pending = await asyncio.wait(
            [watch_task, process_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        # Отменяем оставшиеся задачи
        for task in pending:
            task.cancel()

        # Логируем результаты
        for task in done:
            if task.exception():
                logger.error(f"WatchManager: Задача завершилась с ошибкой: {task.exception()}")
            else:
                logger.info(f"WatchManager: Задача успешно завершена")

        # Завершаем наблюдение
        self.running = False

    async def stop(self):
        """Остановка процесса наблюдения."""
        self.running = False
        self.stop_event.set()

        # Остановка наблюдения Watch API
        try:
            self.watcher.stop()
        except Exception as e:
            logger.warning(f"WatchManager: Ошибка при остановке watcher: {e}")

        logger.info(f"WatchManager: Наблюдение за {self.resource_type} остановлено")

    async def _get_latest_resource_version(self) -> str:
        """Получение последней версии ресурса.

        Returns:
            str: Версия ресурса или пустая строка при ошибке
        """
        try:
            # Получаем список с ограничением в 1 элемент для экономии ресурсов
            result = await asyncio.to_thread(
                self.list_func,
                limit=1,
                timeout_seconds=10
            )

            if result and hasattr(result, 'metadata') and hasattr(result.metadata, 'resource_version'):
                version = result.metadata.resource_version
                logger.info(f"WatchManager: Получена новая resource_version для {self.resource_type}: {version}")
                return version
            else:
                logger.warning(f"WatchManager: Не удалось получить resource_version (необычная структура ответа)")
                return ""
        except Exception as e:
            logger.error(f"WatchManager: Ошибка при получении resource_version: {e}")
            return ""

    async def _list_all_resources(self):
        """Получение полного списка ресурсов и обработка их как начальных событий."""
        try:
            logger.info(f"WatchManager: Получение начальных данных для {self.resource_type}")

            # Получаем полный список ресурсов
            result = await asyncio.to_thread(self.list_func)

            if not result or not hasattr(result, 'items'):
                logger.warning(f"WatchManager: Ответ API не содержит атрибут 'items': {type(result)}")
                return

            items = result.items
            logger.info(f"WatchManager: Получено {len(items)} начальных ресурсов типа {self.resource_type}")

            # Сохраняем resource_version для дальнейшего использования
            if hasattr(result, 'metadata') and hasattr(result.metadata, 'resource_version'):
                self.resource_version = result.metadata.resource_version
                logger.info(f"WatchManager: Установлена resource_version для {self.resource_type}: {self.resource_version}")

            # Обрабатываем каждый ресурс как событие ADDED
            for item in items:
                # Преобразуем объект в словарь
                resource_dict = _convert_to_dict(self.resource_type, item)

                # Проверка, не пропущен ли ресурс при преобразовании (например, из-за фильтрации)
                if not resource_dict:
                    continue

                # Создаем событие и добавляем в очередь
                event_data = {
                    'type': 'ADDED',
                    'object': item,
                    'dict': resource_dict  # Сохраняем преобразованный словарь
                }

                await self.event_queue.put(event_data)

            logger.info(f"WatchManager: Все начальные ресурсы обработаны для {self.resource_type}")
        except Exception as e:
            logger.error(f"WatchManager: Ошибка при получении начальных данных для {self.resource_type}: {e}")
            logger.error(f"WatchManager: Трассировка: {traceback.format_exc()}")

    async def _watch_resources(self):
        """Запуск наблюдения за ресурсами и добавление событий в очередь."""
        while self.running and not self.stop_event.is_set():
            try:
                # Первоначальное получение всех ресурсов
                await self._list_all_resources()

                # Если не удалось получить resource_version, пытаемся получить её явно
                if not self.resource_version:
                    self.resource_version = await self._get_latest_resource_version()

                # Параметры для Watch API - оптимизация таймаутов для более частых обновлений
                params = {
                    "timeout_seconds": 1,  # Сильно уменьшаем таймаут для более частого обновления
                    "watch": True          # Явно указываем watch=True
                }

                # Добавляем resource_version, если она есть
                if self.resource_version:
                    params["resource_version"] = self.resource_version

                logger.info(f"WatchManager: Запуск Watch API наблюдения за {self.resource_type} с параметрами: {params}")

                # Используем коллбэк на событие для обратной совместимости
                async def handle_event(event):
                    # Проверяем, что наблюдение всё ещё активно
                    if not self.running or self.stop_event.is_set():
                        return False  # Возвращаем False для остановки наблюдения

                    # Обновляем время последнего события
                    self.last_event_time = time.time()

                    # Преобразуем объект в словарь
                    obj = event.get('object')
                    resource_dict = _convert_to_dict(self.resource_type, obj)

                    # Проверка, не пропущен ли ресурс при преобразовании (например, из-за фильтрации)
                    if not resource_dict:
                        return True  # Продолжаем наблюдение

                    # Добавляем преобразованный словарь в событие
                    event['dict'] = resource_dict

                    # Добавляем событие в очередь с низким приоритетом
                    try:
                        # Используем put_nowait для неблокирующей постановки в очередь
                        self.event_queue.put_nowait(event)
                    except asyncio.QueueFull:
                        # Если очередь переполнена - обработаем позже
                        logger.warning(f"WatchManager: Очередь событий переполнена для {self.resource_type}, событие отброшено")

                    return True  # Продолжаем наблюдение

                # Запускаем асинхронное наблюдение с использованием нашего обработчика
                async for event in self._stream_watch_events(params):
                    if not await handle_event(event):
                        break

                logger.info(f"WatchManager: Наблюдение за {self.resource_type} завершено нормально")

            except ApiException as e:
                if e.status == 410:  # Gone - требуется обновление resource_version
                    logger.warning(f"WatchManager: Ошибка 410 при наблюдении за {self.resource_type} - ресурс устарел")
                    # Сбрасываем resource_version и пробуем заново почти сразу
                    self.resource_version = await self._get_latest_resource_version()
                    self.reconnect_delay = 0.1  # Почти моментальное переподключение
                else:
                    logger.error(f"WatchManager: Ошибка API при наблюдении за {self.resource_type} (код {e.status}): {e}")
                    self.reconnect_delay = min(self.reconnect_delay * RETRY_BACKOFF_FACTOR, RETRY_MAX_DELAY)
            except Exception as e:
                logger.error(f"WatchManager: Ошибка при наблюдении за {self.resource_type}: {e}")
                logger.error(f"WatchManager: Трассировка: {traceback.format_exc()}")
                self.reconnect_delay = min(self.reconnect_delay * RETRY_BACKOFF_FACTOR, RETRY_MAX_DELAY)

            # Если наблюдение прервано, но менеджер всё ещё активен, переподключаемся
            if self.running and not self.stop_event.is_set():
                logger.info(f"WatchManager: Переподключение через {self.reconnect_delay} сек для {self.resource_type}")
                await asyncio.sleep(self.reconnect_delay)
            else:
                break
    # async def _watch_resources(self):
    #     """Запуск наблюдения за ресурсами и добавление событий в очередь."""
    #     while self.running and not self.stop_event.is_set():
    #         try:
    #             # Первоначальное получение всех ресурсов
    #             await self._list_all_resources()

    #             # Если не удалось получить resource_version, пытаемся получить её явно
    #             if not self.resource_version:
    #                 self.resource_version = await self._get_latest_resource_version()

    #             # Параметры для Watch API
    #             params = {
    #                 "timeout_seconds": 5  # Уменьшенный таймаут для более частой проверки статуса
    #             }

    #             # Добавляем resource_version, если она есть
    #             if self.resource_version:
    #                 params["resource_version"] = self.resource_version

    #             logger.info(f"WatchManager: Запуск Watch API наблюдения за {self.resource_type} с параметрами: {params}")

    #             # Используем коллбэк на событие для обратной совместимости
    #             async def handle_event(event):
    #                 # Проверяем, что наблюдение всё ещё активно
    #                 if not self.running or self.stop_event.is_set():
    #                     return False  # Возвращаем False для остановки наблюдения

    #                 # Обновляем время последнего события
    #                 self.last_event_time = time.time()

    #                 # Преобразуем объект в словарь
    #                 obj = event.get('object')
    #                 resource_dict = _convert_to_dict(self.resource_type, obj)

    #                 # Проверка, не пропущен ли ресурс при преобразовании (например, из-за фильтрации)
    #                 if not resource_dict:
    #                     return True  # Продолжаем наблюдение

    #                 # Добавляем преобразованный словарь в событие
    #                 event['dict'] = resource_dict

    #                 # Добавляем событие в очередь
    #                 await self.event_queue.put(event)

    #                 return True  # Продолжаем наблюдение

    #             # Запускаем асинхронное наблюдение с использованием нашего обработчика
    #             async for event in self._stream_watch_events(params):
    #                 if not await handle_event(event):
    #                     break

    #             logger.info(f"WatchManager: Наблюдение за {self.resource_type} завершено нормально")

    #         except ApiException as e:
    #             if e.status == 410:  # Gone - требуется обновление resource_version
    #                 logger.warning(f"WatchManager: Ошибка 410 при наблюдении за {self.resource_type} - ресурс устарел")
    #                 # Сбрасываем resource_version и пробуем заново почти сразу
    #                 self.resource_version = await self._get_latest_resource_version()
    #                 self.reconnect_delay = 0.1  # Почти моментальное переподключение
    #             else:
    #                 logger.error(f"WatchManager: Ошибка API при наблюдении за {self.resource_type} (код {e.status}): {e}")
    #                 self.reconnect_delay = min(self.reconnect_delay * RETRY_BACKOFF_FACTOR, RETRY_MAX_DELAY)
    #         except Exception as e:
    #             logger.error(f"WatchManager: Ошибка при наблюдении за {self.resource_type}: {e}")
    #             logger.error(f"WatchManager: Трассировка: {traceback.format_exc()}")
    #             self.reconnect_delay = min(self.reconnect_delay * RETRY_BACKOFF_FACTOR, RETRY_MAX_DELAY)

    #         # Если наблюдение прервано, но менеджер всё ещё активен, переподключаемся
    #         if self.running and not self.stop_event.is_set():
    #             logger.info(f"WatchManager: Переподключение через {self.reconnect_delay} сек для {self.resource_type}")
    #             await asyncio.sleep(self.reconnect_delay)
    #         else:
    #             break

    async def _stream_watch_events(self, params):
        """Генератор для создания асинхронного потока событий из Watch API.

        Args:
            params: Параметры для Watch API

        Yields:
            dict: События Watch API
        """
        # Создаем новый watcher для этого потока, чтобы избежать конфликтов
        w = watch.Watch()

        try:
            # Оборачиваем синхронный API в асинхронное исполнение
            # чтобы не блокировать цикл событий asyncio
            stream_func = self.list_func
            stream_iter = await asyncio.to_thread(w.stream, stream_func, **params)

            # Итерируем по потоку событий
            for event in stream_iter:
                # Проверяем, нужно ли продолжать
                if not self.running or self.stop_event.is_set():
                    break

                # Логируем информацию о событии
                event_type = event.get('type', 'UNKNOWN')
                obj = event.get('object')
                name = obj.metadata.name if hasattr(obj, 'metadata') and hasattr(obj.metadata, 'name') else 'unknown'
                namespace = obj.metadata.namespace if hasattr(obj, 'metadata') and hasattr(obj.metadata, 'namespace') else ''
                logger.info(f"WatchManager: Получено событие {event_type} для {self.resource_type}/{namespace}/{name}")

                # Возвращаем событие
                yield event

                # Периодический yield None для предотвращения блокировки цикла событий
                await asyncio.sleep(0)
        finally:
            # Всегда останавливаем watcher
            w.stop()

    async def _process_events(self):
        """Обработка событий из очереди и их отправка в state_manager и прямым подписчикам."""
        while self.running and not self.stop_event.is_set():
            try:
                # Обрабатываем пакетами до 20 событий за раз для ускорения
                batch_processed = 0
                max_batch_size = 20

                # Обработка пакета событий
                while batch_processed < max_batch_size:
                    try:
                        # Пробуем получить событие без блокирования
                        event = self.event_queue.get_nowait()

                        # Получаем информацию о событии
                        event_type = event.get('type', 'UNKNOWN')

                        # Если тип события неизвестен, игнорируем его
                        if event_type not in ['ADDED', 'MODIFIED', 'DELETED']:
                            logger.warning(f"WatchManager: Неизвестный тип события: {event_type}")
                            self.event_queue.task_done()
                            continue

                        # Используем предварительно преобразованный словарь, если он есть
                        if 'dict' in event:
                            resource_dict = event['dict']
                        else:
                            # Если нет, преобразуем объект в словарь
                            obj = event.get('object')
                            resource_dict = _convert_to_dict(self.resource_type, obj)

                        # Проверка, не пропущен ли ресурс при преобразовании
                        if not resource_dict:
                            self.event_queue.task_done()
                            continue

                        # Добавляем отметку времени для отслеживания задержки
                        resource_dict["k8s_event_timestamp"] = time.time()

                        # Логируем информацию о событии
                        name = resource_dict.get('name', 'unknown')
                        namespace = resource_dict.get('namespace', '')
                        logger.debug(f"WatchManager: Обработка события {event_type} для {self.resource_type}/{namespace}/{name}")

                        # БЫСТРЫЙ ПУТЬ - прямая отправка подписчикам для минимальной задержки
                        if _direct_subscribers:
                            # Создаем отдельную задачу для неблокирующей отправки
                            asyncio.create_task(self._deliver_to_direct_subscribers(
                                event_type, self.resource_type, resource_dict))

                        # Стандартный путь через state_manager (для совместимости)
                        try:
                            await update_resource_state(event_type, self.resource_type, resource_dict)
                        except Exception as e:
                            logger.error(f"WatchManager: Ошибка при отправке события в state_manager: {e}")

                        # Отмечаем задачу как выполненную
                        self.event_queue.task_done()
                        batch_processed += 1

                    except asyncio.QueueEmpty:
                        # Очередь пуста, выходим из внутреннего цикла
                        break

                # Если ничего не обработали за этот проход, подождем немного
                if batch_processed == 0:
                    await asyncio.sleep(0.01)  # Очень короткая пауза для экономии CPU

            except asyncio.CancelledError:
                # Корректное завершение при отмене
                logger.info(f"WatchManager: Задача обработки событий для {self.resource_type} отменена")
                break
            except Exception as e:
                logger.error(f"WatchManager: Ошибка при обработке события для {self.resource_type}: {e}")
                logger.error(f"WatchManager: Трассировка: {traceback.format_exc()}")
                await asyncio.sleep(0.1)  # Короткая пауза после ошибки

    async def _deliver_to_direct_subscribers(self, event_type, resource_type, resource_data):
        """Доставляет событие напрямую подписчикам, минуя state_manager.

        Args:
            event_type: Тип события ('ADDED', 'MODIFIED', 'DELETED')
            resource_type: Тип ресурса
            resource_data: Данные ресурса
        """
        # Копируем значения словаря, чтобы избежать проблем с параллельным изменением словаря
        try:
            subscribers = list(_direct_subscribers.values())
            if not subscribers:
                return

            # Быстрая доставка подписчикам
            for callback in subscribers:
                try:
                    await callback(event_type, resource_type, resource_data)
                except Exception as e:
                    logger.error(f"WatchManager: Ошибка при прямой доставке события: {e}")
        except Exception as e:
            logger.error(f"WatchManager: Ошибка в _deliver_to_direct_subscribers: {e}")

    # async def _process_events(self):
    #     """Обработка событий из очереди и их отправка в state_manager."""
    #     while self.running and not self.stop_event.is_set():
    #         try:
    #             # Обрабатываем пакетами до 10 событий за раз для ускорения
    #             batch_processed = 0
    #             max_batch_size = 10

    #             # Обработка пакета событий
    #             while batch_processed < max_batch_size:
    #                 try:
    #                     # Пробуем получить событие без длительного блокирования
    #                     event = self.event_queue.get_nowait()

    #                     # Обработка событий как раньше
    #                     event_type = event.get('type', 'UNKNOWN')

    #                     # Если тип события неизвестен, игнорируем его
    #                     if event_type not in ['ADDED', 'MODIFIED', 'DELETED']:
    #                         logger.warning(f"WatchManager: Неизвестный тип события: {event_type}")
    #                         self.event_queue.task_done()
    #                         continue

    #                     # Используем предварительно преобразованный словарь, если он есть
    #                     if 'dict' in event:
    #                         resource_dict = event['dict']
    #                     else:
    #                         # Если нет, преобразуем объект в словарь
    #                         obj = event.get('object')
    #                         resource_dict = _convert_to_dict(self.resource_type, obj)

    #                     # Проверка, не пропущен ли ресурс при преобразовании
    #                     if not resource_dict:
    #                         self.event_queue.task_done()
    #                         continue

    #                     # Логируем информацию о событии
    #                     name = resource_dict.get('name', 'unknown')
    #                     namespace = resource_dict.get('namespace', '')
    #                     logger.info(f"WatchManager: Обработка события {event_type} для {self.resource_type}/{namespace}/{name}")

    #                     # Отправляем событие в state_manager
    #                     try:
    #                         await update_resource_state(event_type, self.resource_type, resource_dict)
    #                         logger.debug(f"WatchManager: Событие {event_type} для {self.resource_type}/{namespace}/{name} отправлено в state_manager")
    #                     except Exception as e:
    #                         logger.error(f"WatchManager: Ошибка при отправке события в state_manager: {e}")

    #                     # Отмечаем задачу как выполненную
    #                     self.event_queue.task_done()
    #                     batch_processed += 1

    #                 except asyncio.QueueEmpty:
    #                     # Очередь пуста, выходим из внутреннего цикла
    #                     break

    #             # Если ничего не обработали за этот проход, подождем немного
    #             if batch_processed == 0:
    #                 await asyncio.sleep(0.1)  # Короткая пауза вместо длительного ожидания

    #         except asyncio.CancelledError:
    #             # Корректное завершение при отмене
    #             logger.info(f"WatchManager: Задача обработки событий для {self.resource_type} отменена")
    #             break
    #         except Exception as e:
    #             logger.error(f"WatchManager: Ошибка при обработке события для {self.resource_type}: {e}")
    #             logger.error(f"WatchManager: Трассировка: {traceback.format_exc()}")
    #             # Короткая пауза после ошибки
    #             await asyncio.sleep(0.5)

async def _watch_resource(
    k8s_client: Dict[str, Any],
    resource_type: ResourceType,
    retry_delay: int = RETRY_INITIAL_DELAY
) -> None:
    """Асинхронное наблюдение за ресурсами указанного типа.

    Args:
        k8s_client: Словарь с Kubernetes клиентами
        resource_type: Тип ресурса ('deployments', 'pods', 'namespaces')
        retry_delay: Задержка перед повторной попыткой подключения
    """
    logger.info(f"Запуск наблюдения за ресурсами типа {resource_type}")

    # Создаем менеджер наблюдения
    watch_manager = WatchManager(k8s_client, resource_type)

    # В бесконечном цикле запускаем и восстанавливаем наблюдение
    while True:
        try:
            # Запускаем наблюдение
            await watch_manager.start()

            # Если наблюдение завершилось без ошибки, перезапускаем его с задержкой
            logger.info(f"Наблюдение за {resource_type} завершилось, перезапуск через {retry_delay} сек")
            await asyncio.sleep(retry_delay)

        except asyncio.CancelledError:
            # Корректное завершение при отмене задачи
            logger.info(f"Задача наблюдения за {resource_type} отменена")
            await watch_manager.stop()
            break

        except Exception as e:
            # Логируем ошибку и пробуем перезапустить с увеличенной задержкой
            logger.error(f"Ошибка при наблюдении за {resource_type}: {e}")
            logger.error(f"Трассировка: {traceback.format_exc()}")

            # Останавливаем текущее наблюдение
            await watch_manager.stop()

            # Увеличиваем задержку для следующей попытки
            retry_delay = min(retry_delay * RETRY_BACKOFF_FACTOR, RETRY_MAX_DELAY)
            logger.info(f"Повторное подключение через {retry_delay} сек для {resource_type}")
            await asyncio.sleep(retry_delay)

async def check_watch_connections():
    """Периодическая проверка состояния соединений Watch API."""
    global _watch_tasks, k8s_client  # Используем глобальную переменную k8s_client

    while True:
        try:
            logger.debug("Проверка состояния соединений Watch API")

            for resource_type, task in list(_watch_tasks.items()):
                # Проверяем, не завершилась ли задача
                if task.done():
                    # Задача завершилась - проверяем, была ли ошибка
                    try:
                        exc = task.exception()
                        if exc:
                            logger.error(f"Задача наблюдения за {resource_type} завершилась с ошибкой: {exc}")
                        else:
                            logger.warning(f"Задача наблюдения за {resource_type} завершилась без ошибки")
                    except (asyncio.CancelledError, asyncio.InvalidStateError):
                        # Задача может быть отменена или в неверном состоянии
                        pass

                    # Перезапускаем задачу
                    logger.info(f"Перезапуск задачи наблюдения за {resource_type}")
                    new_task = asyncio.create_task(
                        _watch_resource(k8s_client, resource_type),
                        name=f"watch_{resource_type}"
                    )
                    _watch_tasks[resource_type] = new_task

            # Проверяем каждые 30 секунд
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            logger.info("Задача проверки соединений Watch API отменена")
            break
        except Exception as e:
            logger.error(f"Ошибка в задаче проверки соединений Watch API: {e}")
            logger.error(f"Трассировка: {traceback.format_exc()}")
            await asyncio.sleep(60)  # При ошибке повторяем через минуту

# Глобальная переменная для хранения k8s_client - нужна для перезапуска задач
k8s_client = None

async def start_watching(
    client: Dict[str, Any],
    resource_types: List[ResourceType] = ['deployments', 'pods', 'namespaces', 'statefulsets']
) -> Dict[ResourceType, WatchTask]:
    """Запуск наблюдения за ресурсами указанных типов.

    Args:
        client: Словарь с Kubernetes клиентами
        resource_types: Список типов ресурсов для наблюдения

    Returns:
        Dict[ResourceType, WatchTask]: Словарь задач наблюдения
    """
    global _watch_tasks, _namespace_patterns, k8s_client

    # Сохраняем клиент для использования в других функциях
    k8s_client = client

    logger.info(f"K8S_WATCH: Запуск наблюдения за ресурсами типов: {resource_types}")

    # Загружаем паттерны неймспейсов из конфигурации
    try:
        _namespace_patterns = get_in_config(["default", "namespace_patterns"], [])
        logger.info(f"K8S_WATCH: Загружены паттерны неймспейсов: {_namespace_patterns}")
    except Exception as e:
        logger.warning(f"K8S_WATCH: Ошибка при загрузке паттернов неймспейсов: {e}")
        _namespace_patterns = []

    # Проверяем наличие необходимых API клиентов
    if not k8s_client:
        logger.error("K8S_WATCH: K8s клиент не инициализирован")
        return {}

    if "core_v1_api" not in k8s_client or "apps_v1_api" not in k8s_client:
        logger.error(f"K8S_WATCH: K8s клиент не содержит необходимые API. Доступные ключи: {list(k8s_client.keys())}")
        return {}

    # Проверяем доступность API с небольшим запросом
    try:
        if 'namespaces' in resource_types:
            core_v1_api = k8s_client.get("core_v1_api")
            test_result = core_v1_api.list_namespace(limit=5)
            logger.info(f"K8S_WATCH: Тестовый запрос к API успешен. "
                       f"Найдено неймспейсов (пример): {[ns.metadata.name for ns in test_result.items[:5]]}")

            # Проверка возможности наблюдения за ресурсами (watch)
            # Это важно для подтверждения, что API поддерживает watch
            watch_test = watch.Watch()
            watch_count = 0
            logger.info("Тестирование Watch API...")
            for _ in watch_test.stream(core_v1_api.list_namespace, timeout_seconds=1, limit=1):
                watch_count += 1
                # Получаем только одно событие для проверки
                break
            watch_test.stop()

            if watch_count > 0:
                logger.info("Watch API работает корректно!")
            else:
                logger.warning("Watch API не вернул ни одного события. Возможны проблемы с обновлениями в реальном времени.")
    except Exception as e:
        logger.warning(f"Не удалось получить список неймспейсов: {str(e)}")
        logger.warning("API подключение создано, но доступ к Kubernetes API может быть ограничен.")

    # Остановка существующих задач
    await stop_watching()
    logger.info("K8S_WATCH: Предыдущие задачи наблюдения остановлены")

    # Запуск новых задач
    for resource_type in resource_types:
        if resource_type in _resource_functions:
            try:
                task = asyncio.create_task(
                    _watch_resource(k8s_client, resource_type),
                    name=f"watch_{resource_type}"
                )
                _watch_tasks[resource_type] = task
                logger.info(f"K8S_WATCH: Создана и запущена задача наблюдения за {resource_type}")
            except Exception as e:
                logger.error(f"K8S_WATCH: Ошибка при создании задачи наблюдения за {resource_type}: {e}")

    # Даем немного времени на инициализацию задач
    await asyncio.sleep(0.5)

    # Проверяем, что задачи запущены и не завершились с ошибкой
    active_tasks = {rt: task for rt, task in _watch_tasks.items()
                    if not task.done() or (task.done() and not task.exception())}

    if not active_tasks:
        logger.error("K8S_WATCH: Не удалось запустить ни одной задачи наблюдения")
    else:
        logger.info(f"K8S_WATCH: Успешно запущены задачи наблюдения: {list(active_tasks.keys())}")

    # Запуск задачи проверки соединений
    asyncio.create_task(check_watch_connections())
    logger.info("Запущена задача проверки соединений Watch API")

    return _watch_tasks

async def stop_watching() -> None:
    """Остановка всех задач наблюдения."""
    global _watch_tasks

    # Создаем список для хранения отменяемых задач
    cancel_tasks = []

    for resource_type, task in _watch_tasks.items():
        if not task.done():
            # Отменяем задачу
            task.cancel()
            # Добавляем в список для ожидания
            cancel_tasks.append(task)
            logger.info(f"Отправлен запрос на отмену задачи наблюдения за {resource_type}")

    # Ждем завершения всех задач с защитой от ошибок
    if cancel_tasks:
        logger.info(f"Ожидание завершения {len(cancel_tasks)} задач наблюдения...")
        try:
            # Ждем завершения задач с таймаутом и игнорированием исключений
            await asyncio.wait(cancel_tasks, timeout=5.0, return_when=asyncio.ALL_COMPLETED)
        except Exception as e:
            logger.error(f"Ошибка при ожидании завершения задач: {e}")

    # Очищаем словарь задач
    _watch_tasks.clear()
    logger.info("Все задачи наблюдения остановлены и словарь очищен")

def is_watching(resource_type: ResourceType) -> bool:
    """Проверка, ведется ли наблюдение за указанным типом ресурса.

    Args:
        resource_type: Тип ресурса

    Returns:
        bool: True, если наблюдение активно
    """
    return resource_type in _watch_tasks and not _watch_tasks[resource_type].done()

def get_active_watches() -> Set[ResourceType]:
    """Получение списка типов ресурсов, за которыми ведется наблюдение.

    Returns:
        Set[ResourceType]: Множество активных наблюдений
    """
    return {rt for rt, task in _watch_tasks.items() if not task.done()}
