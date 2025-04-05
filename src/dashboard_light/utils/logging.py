"""Модуль для настройки и управления логированием."""

import functools
import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, Generator, Optional, TypeVar

T = TypeVar('T')

logger = logging.getLogger(__name__)


def configure_logging(level: Optional[str] = None) -> None:
    """Настройка логирования на основе конфигурации.

    Args:
        level: Уровень логирования
    """
    if level is None:
        level = os.environ.get("LOG_LEVEL", "INFO")

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Настройка корневого логгера
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Установка уровня логирования для корневого логгера
    logging.getLogger().setLevel(numeric_level)

    logger.info(f"Уровень логирования установлен: {level.upper()}")


def set_logger_level(logger_name: str, level: str) -> None:
    """Установка уровня логирования для конкретного логгера.

    Args:
        logger_name: Имя логгера
        level: Уровень логирования
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.getLogger(logger_name).setLevel(numeric_level)
    logger.info(f"Уровень логирования для {logger_name} установлен: {level.upper()}")


@contextmanager
def log_timing(message: str, level: int = logging.INFO) -> Generator[None, None, None]:
    """Контекстный менеджер для измерения времени выполнения блока кода.

    Args:
        message: Сообщение для логирования
        level: Уровень логирования

    Yields:
        None
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        logger.log(level, f"{message} (выполнено за {duration:.3f} сек)")


def with_logging(message: str, level: int = logging.INFO) -> Callable:
    """Декоратор для логирования времени выполнения функции.

    Args:
        message: Сообщение для логирования
        level: Уровень логирования

    Returns:
        Callable: Декорированная функция
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            with log_timing(f"{message} - {func.__name__}", level):
                return func(*args, **kwargs)
        return wrapper
    return decorator


@contextmanager
def error_logging(context: Dict[str, Any] = None) -> Generator[None, None, None]:
    """Контекстный менеджер для логирования ошибок при выполнении блока кода.

    Args:
        context: Дополнительный контекст для логирования при ошибке

    Yields:
        None
    """
    try:
        yield
    except Exception as e:
        error_context = {"message": str(e)}
        if context:
            error_context.update(context)

        logger.exception(f"Ошибка: {error_context}")
        raise


# Предопределенные декораторы для удобства
debug_timing = functools.partial(with_logging, level=logging.DEBUG)
info_timing = functools.partial(with_logging, level=logging.INFO)
warn_timing = functools.partial(with_logging, level=logging.WARNING)
