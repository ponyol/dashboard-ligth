"""Основные функции для работы с конфигурацией приложения."""

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from dashboard_light.config import schema
from dashboard_light.utils import core as utils

logger = logging.getLogger(__name__)

CONFIG_CACHE: Dict[str, Any] = {}


def load_config_file(config_path: str) -> Dict[str, Any]:
    """Загрузка конфигурации из файла.

    Args:
        config_path: Путь к файлу конфигурации

    Returns:
        Dict[str, Any]: Загруженная конфигурация

    Raises:
        FileNotFoundError: Если файл конфигурации не найден
        ValueError: Если произошла ошибка при парсинге конфигурации
    """
    try:
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Файл конфигурации не найден: {config_path}")

        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)

        logger.info(f"Конфигурация загружена из файла: {config_path}")
        return config_data
    except FileNotFoundError as e:
        logger.error(f"Файл конфигурации не найден: {config_path}")
        raise e
    except yaml.YAMLError as e:
        logger.error(f"Ошибка парсинга YAML конфигурации: {str(e)}")
        raise ValueError(f"Ошибка парсинга YAML конфигурации: {str(e)}")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при загрузке конфигурации: {str(e)}")
        raise


def substitute_env_vars(config: Dict[str, Any]) -> Dict[str, Any]:
    """Подстановка переменных окружения в конфигурацию.

    Ищет значения вида "ENV:VAR_NAME" или "ENV:VAR_NAME:default" и
    заменяет их на значения соответствующих переменных окружения.

    Args:
        config: Конфигурация для обработки

    Returns:
        Dict[str, Any]: Обработанная конфигурация
    """
    def process_value(value: Any) -> Any:
        if isinstance(value, str) and value.startswith("ENV:"):
            # Парсинг строки вида "ENV:VAR_NAME" или "ENV:VAR_NAME:default"
            parts = value[4:].split(":", 1)
            env_name = parts[0]
            default = parts[1] if len(parts) > 1 else None

            # Получение значения из переменной окружения
            return os.environ.get(env_name, default)
        elif isinstance(value, dict):
            return {k: process_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [process_value(item) for item in value]
        else:
            return value

    return process_value(config)


@lru_cache(maxsize=1)
def load_config() -> Dict[str, Any]:
    """Загрузка конфигурации с учетом переменных окружения.

    Returns:
        Dict[str, Any]: Загруженная и валидированная конфигурация
    """
    global CONFIG_CACHE

    # Если конфигурация уже в кэше, возвращаем её
    if CONFIG_CACHE:
        return CONFIG_CACHE

    # Определение пути к файлу конфигурации
    config_path = os.environ.get("CONFIG_PATH", "resources/config.yaml")

    # Загрузка конфигурации из файла
    config_data = load_config_file(config_path)

    # Подстановка переменных окружения
    config_data = substitute_env_vars(config_data)

    # Валидация конфигурации по схеме
    config_data = schema.validate_config(config_data)

    # Сохранение в кэше
    CONFIG_CACHE = config_data

    return config_data


def get_in_config(path: List[str], default: Any = None) -> Any:
    """Получение значения из конфигурации по пути ключей.

    Args:
        path: Список ключей для доступа к вложенным значениям
        default: Значение по умолчанию, если путь не найден

    Returns:
        Any: Найденное значение или значение по умолчанию
    """
    config_data = load_config()
    return utils.get_in(config_data, path, default)


def reload_config() -> Dict[str, Any]:
    """Перезагрузка конфигурации из файла.

    Returns:
        Dict[str, Any]: Обновленная конфигурация
    """
    global CONFIG_CACHE
    CONFIG_CACHE = {}  # Очистка кэша
    load_config.cache_clear()  # Очистка кэша LRU
    return load_config()  # Повторная загрузка
