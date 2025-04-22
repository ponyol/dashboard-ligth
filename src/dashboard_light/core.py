"""Точка входа в приложение Dashboard-Light."""

import logging
import signal
import sys
import asyncio
from functools import partial
from typing import Any, Callable, Dict, List, Optional

from dashboard_light.config import core as config
from dashboard_light.k8s import core as k8s
from dashboard_light.web import core as web
from dashboard_light.k8s.watch import stop_watching
from dashboard_light.utils.logging import configure_logging

# Настройка логирования с использованием централизованной функции
# Уровень логирования будет взят из переменной окружения LOG_LEVEL
configure_logging()
logger = logging.getLogger(__name__)

def setup_signal_handlers(cleanup_func: Callable[[], None]) -> None:
    """Настройка обработчиков сигналов для корректного завершения приложения."""
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda signum, frame: cleanup_func())




def start_app() -> Dict[str, Any]:
    """Запуск всех компонентов приложения.

    Returns:
        Dict[str, Any]: Словарь с компонентами приложения
    """
    logger.info("Запуск Dashboard-Light (HTTP API сервер)...")
    logger.warning("=== ВАЖНО! ИНФОРМАЦИЯ О МИГРАЦИИ ===")
    logger.warning("HTTP API сервер больше не используется для активного опроса данных Kubernetes.")
    logger.warning("Вместо этого используется WebSocket сервер, который работает параллельно.")
    logger.warning("Периодический опрос API Kubernetes отключен в пользу механизма Watch API.")
    logger.warning("HTTP API сервер оставлен только для обратной совместимости и будет выдавать предупреждения.")
    logger.warning("=== КОНЕЦ ВАЖНОГО СООБЩЕНИЯ ===")

    try:
        # Загрузка конфигурации
        app_config = config.load_config()
        logger.info("Конфигурация загружена успешно")

        # Инициализация Kubernetes клиента
        k8s_client = k8s.create_k8s_client(app_config)
        logger.info("Kubernetes клиент инициализирован")

        # Запуск веб-сервера
        web_server = web.start_server(app_config, k8s_client)
        logger.info("Веб-сервер запущен")

        return {
            "config": app_config,
            "k8s_client": k8s_client,
            "web_server": web_server,
        }
    except Exception as e:
        logger.error(f"Ошибка при запуске приложения: {str(e)}")
        sys.exit(1)

def stop_app(components: Dict[str, Any]) -> None:
    """Остановка всех компонентов приложения.

    Args:
        components: Словарь с компонентами приложения
    """
    logger.info("Остановка Dashboard-Light...")

    # Остановка веб-сервера
    web_server = components.get("web_server")
    if web_server:
        web.stop_server(web_server)
        logger.info("Веб-сервер остановлен")

    # Очистка ресурсов K8s клиента
    k8s_client = components.get("k8s_client")
    if k8s_client:
        k8s.cleanup_k8s_client(k8s_client)
        logger.info("Kubernetes клиент остановлен")

    # Остановка наблюдения за ресурсами
    try:
        # Создаем новый цикл событий, если текущий недоступен
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # Если нет текущего цикла событий, создаем новый
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        # Останавливаем наблюдение
        if loop.is_running():
            asyncio.create_task(stop_watching())
        else:
            loop.run_until_complete(stop_watching())
        logger.info("Наблюдение за ресурсами остановлено")
    except Exception as e:
        logger.error(f"Ошибка при остановке наблюдения: {str(e)}")

    logger.info("Приложение Dashboard-Light остановлено")

    # Явно завершаем процесс
    sys.exit(0)


def main() -> None:
    """Основная функция для запуска приложения."""
    components = start_app()

    # Настройка обработчиков сигналов для корректного завершения
    setup_signal_handlers(partial(stop_app, components))

    try:
        # Бесконечный цикл для поддержания работы основного приложения
        # до получения сигнала остановки
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки приложения")
    finally:
        stop_app(components)

if __name__ == "__main__":
    main()
