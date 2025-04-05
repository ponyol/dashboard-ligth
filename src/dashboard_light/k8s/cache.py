"""Модуль для кэширования результатов запросов к Kubernetes API."""

import logging
import time
from functools import wraps
from threading import RLock
from typing import Any, Callable, Dict, Optional, TypeVar

from dashboard_light.config.core import get_in_config

logger = logging.getLogger(__name__)

# Типовая переменная для обобщенных функций
T = TypeVar('T')

# Глобальный кэш
cache_store: Dict[str, Dict[str, Any]] = {}
cache_lock = RLock()

# Значение TTL по умолчанию в секундах
DEFAULT_TTL_SECONDS = 30


def get_cache_ttl(cache_key: str) -> int:
    """Получение TTL для кэша из конфигурации или значения по умолчанию.

    Args:
        cache_key: Ключ кэша

    Returns:
        int: Время жизни записи в кэше в секундах
    """
    path = ["cache", "ttl", cache_key]
    ttl = get_in_config(path)

    if ttl is None:
        ttl = get_in_config(["cache", "default_ttl"], DEFAULT_TTL_SECONDS)

    return ttl


def cache_get(cache_key: str) -> Optional[Any]:
    """Получение значения из кэша с проверкой его актуальности.

    Args:
        cache_key: Ключ кэша

    Returns:
        Optional[Any]: Значение из кэша или None, если запись не найдена или устарела
    """
    with cache_lock:
        cached_item = cache_store.get(cache_key)

        if cached_item:
            ttl = get_cache_ttl(cache_key)
            current_time = time.time()
            update_time = cached_item.get("update_time", 0)
            age_seconds = current_time - update_time

            if age_seconds < ttl:
                logger.debug(f"Используются кэшированные данные для: {cache_key}")
                return cached_item.get("value")
            else:
                logger.debug(f"Кэш устарел: {cache_key}, возраст: {age_seconds:.2f} сек")
                return None

        return None


def cache_put(cache_key: str, value: Any) -> Any:
    """Сохранение значения в кэше с текущим временем.

    Args:
        cache_key: Ключ кэша
        value: Значение для сохранения

    Returns:
        Any: Сохраненное значение
    """
    with cache_lock:
        cache_store[cache_key] = {
            "value": value,
            "update_time": time.time()
        }
        logger.debug(f"Обновление кэша для: {cache_key}")
        return value


def with_cache(cache_key_prefix: str):
    """Декоратор для получения данных с использованием кэширования.

    Args:
        cache_key_prefix: Префикс ключа кэша

    Returns:
        Callable: Декорированная функция
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Формирование ключа кэша из префикса и аргументов
            arg_str = "_".join(str(arg) for arg in args)
            kwarg_str = "_".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = f"{cache_key_prefix}_{arg_str}_{kwarg_str}"

            # Пытаемся получить данные из кэша
            cached_value = cache_get(cache_key)
            if cached_value is not None:
                return cached_value

            # Если в кэше нет, вызываем оригинальную функцию
            result = func(*args, **kwargs)
            return cache_put(cache_key, result)

        return wrapper

    return decorator


def invalidate_cache(cache_key: str) -> None:
    """Инвалидация кэша для указанного ключа.

    Args:
        cache_key: Ключ кэша для инвалидации
    """
    with cache_lock:
        if cache_key in cache_store:
            del cache_store[cache_key]
            logger.debug(f"Кэш инвалидирован для: {cache_key}")


def invalidate_by_prefix(prefix: str) -> None:
    """Инвалидация всех записей кэша, начинающихся с указанного префикса.

    Args:
        prefix: Префикс ключа кэша
    """
    with cache_lock:
        keys_to_delete = [k for k in cache_store if k.startswith(prefix)]
        for key in keys_to_delete:
            del cache_store[key]

        if keys_to_delete:
            logger.debug(f"Инвалидировано {len(keys_to_delete)} записей кэша с префиксом: {prefix}")


def invalidate_all() -> None:
    """Полная инвалидация кэша."""
    with cache_lock:
        cache_store.clear()
        logger.info("Весь кэш очищен")


def initialize_cache() -> None:
    """Инициализация конфигурации кэша."""
    logger.info("Инициализация конфигурации кэша")
    default_ttl = get_in_config(["cache", "default_ttl"], DEFAULT_TTL_SECONDS)
    logger.info(f"Время жизни кэша по умолчанию: {default_ttl} сек")
