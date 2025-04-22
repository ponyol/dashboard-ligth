"""Модуль для работы с Kubernetes Watch API."""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Callable, Awaitable, Tuple, Set

from kubernetes import client, watch
from kubernetes.client.exceptions import ApiException

from dashboard_light.state_manager import update_resource_state
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

def _convert_to_dict(resource_type: ResourceType, resource: Any) -> Dict[str, Any]:
    """Преобразование объекта Kubernetes в словарь.

    Args:
        resource_type: Тип ресурса ('deployments', 'pods', 'namespaces')
        resource: Объект ресурса Kubernetes

    Returns:
        Dict[str, Any]: Словарь с данными ресурса
    """
    metadata = resource.metadata
    result = {
        "name": metadata.name,
        "namespace": getattr(metadata, "namespace", ""),
    }

    # Дополнительные данные в зависимости от типа ресурса
    if resource_type == 'deployments' or resource_type == 'statefulsets':
        # Переиспользуем существующую логику из deployments.py/statefulsets.py
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

    elif resource_type == 'pods':
        # Переиспользуем существующую логику из pods.py
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

    elif resource_type == 'namespaces':
        # Переиспользуем существующую логику из namespaces.py
        result.update({
            "phase": resource.status.phase,
            "created": metadata.creation_timestamp.isoformat() if metadata.creation_timestamp else None,
            "labels": metadata.labels if metadata.labels else {},
        })

    return result

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
    if resource_type not in _resource_functions:
        logger.error(f"Неизвестный тип ресурса: {resource_type}")
        return

    logger.info(f"Запуск наблюдения за ресурсами типа {resource_type}")

    # В бесконечном цикле пытаемся установить и поддерживать соединение
    while True:
        try:
            # Получение API в зависимости от типа ресурса
            api_instance = _get_api_instance(k8s_client, resource_type)
            if not api_instance:
                logger.error(f"Не удалось получить API для {resource_type}")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * RETRY_BACKOFF_FACTOR, RETRY_MAX_DELAY)
                continue

            # Создание объекта watch и функции для наблюдения
            w = watch.Watch()
            list_func = _resource_functions[resource_type]['list_func'](api_instance)

            # Запуск наблюдения
            logger.info(f"Установка соединения Watch API для {resource_type}")

            # Получаем последнюю версию ресурса для надежного наблюдения
            # Это поможет избежать ошибок 410 Gone (ресурс уже не существует)
            try:
                # Сначала делаем list запрос для получения resourceVersion
                list_result = list_func(timeout_seconds=1)
                resource_version = list_result.metadata.resource_version
                logger.info(f"Получена версия ресурса для {resource_type}: {resource_version}")
            except Exception as e:
                logger.warning(f"Не удалось получить resourceVersion для {resource_type}: {e}")
                resource_version = None  # Будет использована последняя доступная версия
            
            # Создаем очередь для передачи событий из потока в цикл событий
            import queue
            event_queue = queue.Queue()
            
            # Получаем текущий цикл событий для дальнейшего использования
            main_loop = asyncio.get_running_loop()
            
            # Флаг для контроля работы потока
            thread_running = True
            
            # Функция для запуска в отдельном потоке
            def watch_resource_thread():
                """Функция для запуска в отдельном потоке - наблюдение за ресурсами K8s"""
                try:
                    logger.info(f"Запущен поток наблюдения за {resource_type}")
                    
                    # Параметры для функции stream - используем полученную версию ресурса если она есть
                    params = {}
                    if resource_version:
                        # Добавляем resourceVersion если она получена
                        params["resource_version"] = resource_version
                    
                    # Параметрам задаем watch=True явно для активации потока изменений
                    params["watch"] = True
                    
                    # Добавляем timeout для предотвращения долгих блокирующих запросов
                    # Значение должно быть достаточно большим, но не слишком, чтобы не блокировать
                    params["timeout_seconds"] = 300  # 5 минут
                    
                    # Сначала получим текущие данные для инициализации
                    try:
                        logger.info(f"Получение начальных данных для {resource_type}")
                        initial_items = list_func(_preload_content=False).items
                        # Помещаем каждый ресурс как событие ADDED
                        for item in initial_items:
                            initial_event = {
                                'type': 'ADDED',
                                'object': item
                            }
                            event_queue.put(initial_event)
                            main_loop.call_soon_threadsafe(process_queue_event.set)
                        logger.info(f"Получено {len(initial_items)} начальных ресурсов типа {resource_type}")
                    except Exception as e:
                        logger.error(f"Ошибка при получении начальных данных для {resource_type}: {e}")
                    
                    # Теперь запускаем поток наблюдения за изменениями
                    logger.info(f"Запуск стриминга для {resource_type}")
                    try:
                        # Получаем явно метод функции для вызова
                        list_method = list_func.__func__
                        api = list_func.__self__
                        
                        # Выводим детали метода для диагностики
                        logger.info(f"Вызов API метода: {list_method.__name__} для {resource_type}")
                        logger.info(f"Параметры: {params}")
                        
                        # Используем w.stream с API и методом
                        for event in w.stream(list_method, api, **params):
                            # Проверяем, нужно ли продолжать работу
                            if not thread_running:
                                logger.info(f"Получен сигнал остановки потока наблюдения за {resource_type}")
                                break
                                
                            # Помещаем событие в очередь (обычную, не асинхронную)
                            event_queue.put(event)
                            
                            # Планируем обработку очереди в основном цикле
                            main_loop.call_soon_threadsafe(process_queue_event.set)
                            
                            # Добавляем вывод для отладки
                            type_event = event.get('type', 'UNKNOWN')
                            obj = event.get('object', None)
                            name = obj.metadata.name if hasattr(obj, 'metadata') else 'unknown'
                            logger.info(f"K8S_WATCH: Добавлено событие {type_event} для {resource_type}/{name} в очередь")
                    except AttributeError:
                        # Если метод __func__ недоступен, используем стандартный подход
                        logger.info(f"Используем стандартный метод stream для {resource_type}")
                        for event in w.stream(list_func, **params):
                            # Проверяем, нужно ли продолжать работу
                            if not thread_running:
                                logger.info(f"Получен сигнал остановки потока наблюдения за {resource_type}")
                                break
                                
                            # Помещаем событие в очередь (обычную, не асинхронную)
                            event_queue.put(event)
                            
                            # Планируем обработку очереди в основном цикле
                            main_loop.call_soon_threadsafe(process_queue_event.set)
                            
                            # Добавляем вывод для отладки
                            type_event = event.get('type', 'UNKNOWN')
                            obj = event.get('object', None)
                            name = obj.metadata.name if hasattr(obj, 'metadata') else 'unknown'
                            logger.info(f"K8S_WATCH: Добавлено событие {type_event} для {resource_type}/{name} в очередь")
                except Exception as e:
                    logger.error(f"Ошибка в потоке наблюдения за {resource_type}: {e}")
                    # Сигнализируем об ошибке через очередь
                    try:
                        event_queue.put(None)  # None означает, что поток завершился
                        # Планируем обработку в основном цикле
                        main_loop.call_soon_threadsafe(process_queue_event.set)
                    except Exception as e2:
                        logger.error(f"Не удалось отправить сигнал о завершении потока: {e2}")
                finally:
                    logger.info(f"Поток наблюдения за {resource_type} завершен")
            
            # Создаем событие для синхронизации обработки очереди
            process_queue_event = asyncio.Event()
            
            # Запускаем наблюдение в отдельном потоке
            import threading
            watch_thread = threading.Thread(
                target=watch_resource_thread, 
                name=f"watch_{resource_type}",
                daemon=True  # Поток будет завершен при завершении основного потока
            )
            watch_thread.start()
            
            # Обработка событий из очереди в цикле событий asyncio
            try:
                while True:
                    # Ждем сигнала о новых данных или ошибке
                    await process_queue_event.wait()
                    process_queue_event.clear()
                    
                    # Добавляем отладочную информацию
                    queue_size = event_queue.qsize()
                    if queue_size > 0:
                        logger.info(f"K8S_WATCH: Обработка {queue_size} событий из очереди для {resource_type}")
                    
                    # Обрабатываем все события из очереди
                    processed_count = 0
                    while not event_queue.empty():
                        try:
                            # Получаем событие из обычной очереди (не асинхронной)
                            event = event_queue.get_nowait()
                            processed_count += 1
                            
                            # Если получили None, значит поток завершился
                            if event is None:
                                logger.warning(f"Поток наблюдения за {resource_type} завершился, пересоздаем")
                                # Сигнализируем потоку о необходимости остановки
                                thread_running = False
                                break
                            
                            # Проверка на корректность события
                            if not isinstance(event, dict) or 'type' not in event or 'object' not in event:
                                logger.warning(f"K8S_WATCH: Получено некорректное событие: {event}")
                                continue
                            
                            # Получение типа события и ресурса
                            event_type = event['type']  # ADDED, MODIFIED, DELETED
                            resource = event['object']

                            # Логируем информацию о событии
                            name = resource.metadata.name if hasattr(resource, 'metadata') and hasattr(resource.metadata, 'name') else "unknown"
                            namespace = resource.metadata.namespace if hasattr(resource, 'metadata') and hasattr(resource.metadata, 'namespace') else ""
                            logger.info(f"K8S_WATCH: Получено событие {event_type} для {resource_type}/{namespace}/{name}")

                            # Преобразование ресурса в словарь
                            resource_dict = _convert_to_dict(resource_type, resource)

                            # Вывод ключевой информации о ресурсе для отладки
                            logger.info(f"K8S_WATCH: Преобразовано в словарь, имя={resource_dict.get('name')}, namespace={resource_dict.get('namespace', '')}")
                            
                            # Обновление состояния через менеджер состояния
                            await update_resource_state(event_type, resource_type, resource_dict)

                            # Отмечаем, что событие обработано
                            event_queue.task_done()
                            
                            # Выводим информацию о том, что событие полностью обработано
                            if processed_count % 10 == 0 or queue_size - processed_count == 0:
                                logger.info(f"K8S_WATCH: Обработано {processed_count}/{queue_size} событий для {resource_type}")
                                # Даем шанс другим асинхронным задачам выполниться
                                await asyncio.sleep(0.01)
                        except queue.Empty:
                            # Очередь пуста, выходим из внутреннего цикла
                            break
                        except Exception as e:
                            logger.error(f"Ошибка при обработке события из очереди: {e}")
                    
                    # Даем шанс другим асинхронным задачам выполниться
                    await asyncio.sleep(0.01)
                    
                    # Если поток завершился, выходим из основного цикла
                    if not thread_running:
                        break
                    
            except asyncio.CancelledError:
                logger.info(f"Задача наблюдения за {resource_type} отменена")
                # Сигнализируем потоку о необходимости остановки
                thread_running = False
                # Пропускаем исключение дальше, чтобы задача могла корректно завершиться
                raise

            # Если мы здесь, значит соединение закрылось без исключения
            logger.warning(f"Соединение Watch API для {resource_type} закрылось, переподключение...")
            retry_delay = RETRY_INITIAL_DELAY

        except ApiException as e:
            error_msg = str(e)
            if e.status == 410:  # Gone, требуется повторное подключение с новой версией
                logger.warning(f"Ошибка 410 при наблюдении за {resource_type}: {error_msg}")
                logger.info(f"Старая версия ресурса больше недоступна, переподключение с новой версией для {resource_type}")
                # При ошибке 410 начинаем с минимальной задержки для быстрого восстановления 
                retry_delay = 0.1  # Практически мгновенное переподключение
            else:
                logger.error(f"API ошибка при наблюдении за {resource_type} (код {e.status}): {error_msg}")
                retry_delay = min(retry_delay * RETRY_BACKOFF_FACTOR, RETRY_MAX_DELAY)
        except Exception as e:
            logger.error(f"Ошибка при наблюдении за {resource_type}: {e}")
            retry_delay = min(retry_delay * RETRY_BACKOFF_FACTOR, RETRY_MAX_DELAY)
        finally:
            if 'w' in locals():
                w.stop()
            logger.info(f"Повторное подключение через {retry_delay} сек для {resource_type}")
            await asyncio.sleep(retry_delay)

async def start_watching(
    k8s_client: Dict[str, Any],
    resource_types: List[ResourceType] = ['deployments', 'pods', 'namespaces', 'statefulsets']
) -> Dict[ResourceType, WatchTask]:
    """Запуск наблюдения за ресурсами указанных типов.

    Args:
        k8s_client: Словарь с Kubernetes клиентами
        resource_types: Список типов ресурсов для наблюдения

    Returns:
        Dict[ResourceType, WatchTask]: Словарь задач наблюдения
    """
    global _watch_tasks
    
    logger.info(f"K8S_WATCH: Запуск наблюдения за ресурсами типов: {resource_types}")
    
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
            test_result = core_v1_api.list_namespace(limit=1)
            logger.info(f"K8S_WATCH: Тестовый запрос к API успешен. Найдено {len(test_result.items)} неймспейсов.")
        elif 'deployments' in resource_types:
            apps_v1_api = k8s_client.get("apps_v1_api")
            test_result = apps_v1_api.list_deployment_for_all_namespaces(limit=1)
            logger.info(f"K8S_WATCH: Тестовый запрос к API успешен. Найдено {len(test_result.items)} деплойментов.")
    except Exception as e:
        logger.error(f"K8S_WATCH: Тестовый запрос к API завершился ошибкой: {e}")
        logger.error("K8S_WATCH: Проверьте подключение к кластеру Kubernetes и права доступа")
        return {}

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
