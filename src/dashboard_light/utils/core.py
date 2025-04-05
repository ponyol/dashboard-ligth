"""Основные утилитарные функции."""

import logging
import os
import re
from functools import reduce
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Union

logger = logging.getLogger(__name__)

# Типовая переменная для обобщенных функций
T = TypeVar('T')


def deep_merge(d1: Dict[str, Any], d2: Dict[str, Any]) -> Dict[str, Any]:
    """Глубокое объединение вложенных словарей.

    Если ключи имеют словари в качестве значений, они рекурсивно объединяются.
    В противном случае значение из второго словаря перезаписывает значение из первого.

    Args:
        d1: Первый словарь
        d2: Второй словарь

    Returns:
        Dict[str, Any]: Объединенный словарь
    """
    result = d1.copy()

    for key, value in d2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def get_in(data: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    """Получение значения из вложенного словаря по пути ключей.

    Args:
        data: Словарь данных
        keys: Список ключей для доступа к вложенным значениям
        default: Значение по умолчанию, если путь не найден

    Returns:
        Any: Найденное значение или значение по умолчанию
    """
    try:
        return reduce(lambda d, k: d.get(k, {}), keys[:-1], data).get(keys[-1], default)
    except (AttributeError, IndexError):
        return default


def dissoc_in(data: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    """Удаляет значение по пути ключей в словаре.

    Args:
        data: Словарь данных
        keys: Список ключей для доступа к вложенным значениям

    Returns:
        Dict[str, Any]: Обновленный словарь
    """
    if not keys:
        return data

    result = data.copy()

    if len(keys) == 1:
        if keys[0] in result:
            del result[keys[0]]
    else:
        sub_dict = get_in(data, keys[:-1])
        if isinstance(sub_dict, dict) and keys[-1] in sub_dict:
            sub_dict_copy = sub_dict.copy()
            del sub_dict_copy[keys[-1]]

            # Обновление исходного словаря
            current = result
            for key in keys[:-2]:
                current = current.setdefault(key, {})
            current[keys[-2]] = sub_dict_copy

    return result


def format_error(e: Exception, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Форматирование информации об ошибке для логирования.

    Args:
        e: Объект исключения
        context: Дополнительный контекст ошибки

    Returns:
        Dict[str, Any]: Отформатированная информация об ошибке
    """
    error_info = {
        "error_message": str(e),
        "error_type": type(e).__name__,
        "traceback": str(e.__traceback__),
    }

    if context:
        error_info.update(context)

    return error_info


def parse_int(s: str) -> Optional[int]:
    """Безопасное преобразование строки в целое число.

    Args:
        s: Строка для преобразования

    Returns:
        Optional[int]: Преобразованное число или None при ошибке
    """
    try:
        return int(s.strip())
    except (ValueError, AttributeError, TypeError):
        return None


def env_value(name: str, default: Any = None) -> Any:
    """Получение значение из переменной окружения с поддержкой значения по умолчанию.

    Args:
        name: Имя переменной окружения
        default: Значение по умолчанию

    Returns:
        Any: Значение переменной окружения или значение по умолчанию
    """
    return os.environ.get(name, default)


def parse_boolean(value: Union[str, bool, int]) -> bool:
    """Преобразование значения в булево значение.

    Args:
        value: Значение для преобразования

    Returns:
        bool: Преобразованное булево значение
    """
    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return value != 0

    if isinstance(value, str):
        return value.lower().strip() in {"true", "yes", "1", "y", "t"}

    return bool(value)


def sanitize_filename(filename: str) -> str:
    """Очистка имени файла от недопустимых символов.

    Args:
        filename: Имя файла для очистки

    Returns:
        str: Очищенное имя файла
    """
    # Замена недопустимых символов на подчеркивание
    sanitized = re.sub(r'[^a-zA-Z0-9\-_.]', '_', filename)
    # Замена множественных подчеркиваний на одно
    sanitized = re.sub(r'_{2,}', '_', sanitized)
    return sanitized


def human_readable_size(size_bytes: int) -> str:
    """Преобразование размера в байтах в человеко-читаемый формат.

    Args:
        size_bytes: Размер в байтах

    Returns:
        str: Человеко-читаемый размер
    """
    units = ['B', 'KB', 'MB', 'GB', 'TB']

    unit_index = 0
    value = float(size_bytes)

    while value >= 1024 and unit_index < len(units) - 1:
        value /= 1024
        unit_index += 1

    return f"{value:.2f} {units[unit_index]}"


def compose(*funcs: Callable) -> Callable:
    """Композиция функций (в стиле функционального программирования).

    Создает функцию, которая является композицией переданных функций.
    (compose(f, g, h))(x) эквивалентно f(g(h(x))).

    Args:
        *funcs: Набор функций для композиции

    Returns:
        Callable: Композиция функций
    """
    def compose_two(f: Callable, g: Callable) -> Callable:
        return lambda x: f(g(x))

    if not funcs:
        return lambda x: x

    return reduce(compose_two, funcs)


def pipe(value: Any, *funcs: Callable) -> Any:
    """Применение цепочки функций к значению (в стиле функционального программирования).

    Args:
        value: Начальное значение
        *funcs: Функции для применения

    Returns:
        Any: Результат применения всех функций
    """
    return reduce(lambda v, f: f(v), funcs, value)
