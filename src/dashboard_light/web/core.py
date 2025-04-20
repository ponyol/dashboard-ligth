"""Основной модуль для настройки FastAPI и веб-сервера."""

import logging
import os
from typing import Any, Dict, Optional
from pathlib import Path

from starlette.middleware.sessions import SessionMiddleware
import secrets

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from dashboard_light.web.middleware import add_middlewares
from dashboard_light.web.routes import create_router

import asyncio
from dashboard_light.state_manager import startup_state_manager, initialize_state_from_api

logger = logging.getLogger(__name__)

def create_app(app_config: Dict[str, Any], k8s_client: Dict[str, Any]) -> FastAPI:
    """Создание и настройка FastAPI приложения.

    Args:
        app_config: Конфигурация приложения
        k8s_client: Словарь с Kubernetes клиентом и API

    Returns:
        FastAPI: Настроенное FastAPI приложение
    """
    # Создание FastAPI приложения
    app = FastAPI(
        title="Dashboard Light",
        description="Система мониторинга EKS Deployments & Pods",
        version="0.1.0",
    )

    # Настройка CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # В продакшене нужно ограничить
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Добавление middleware для сессий (отдельный вызов)
    app.add_middleware(
        SessionMiddleware,
        secret_key=os.environ.get("SESSION_SECRET", secrets.token_hex(32))
    )
    # Добавление пользовательских middleware
    add_middlewares(app)

    # Создание и добавление роутеров
    main_router = create_router(app_config, k8s_client)
    if main_router is None:
    #     app.include_router(main_router)
    # else:
        logger.error("Не удалось создать основной роутер - он равен None")
        raise ValueError("Основной роутер приложения не был инициализирован корректно")

    app.include_router(main_router)

    # Переработаем определение пути к статическим файлам
    project_root = Path(__file__).parent.parent.parent.parent  # 4 уровня вверх от web/core.py
    static_dir = project_root / "resources" / "public"
    # Монтирование статических файлов
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
        logger.info(f"Смонтированы статические файлы из {static_dir}")
    else:
        logger.warning(f"Директория статических файлов не найдена: {static_dir}")
    # static_dir = os.path.join(os.path.dirname(__file__), "../../resources/public")
    # if os.path.exists(static_dir):
    #     app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    @app.on_event("startup")
    async def startup_event():
        app.state.config = app_config
        app.state.k8s_client = k8s_client
        logger.info("FastAPI приложение запущено")

        # Инициализация менеджера состояния - запускаем как задачу, а не блокирующе
        try:
            # Создаем фоновую задачу для инициализации состояния
            asyncio.create_task(initialize_manager(k8s_client))
            logger.info("Запущена задача инициализации менеджера состояния")
        except Exception as e:
            logger.error(f"Ошибка при запуске задачи инициализации: {str(e)}")

    # Вспомогательная функция для инициализации менеджера в фоне
    async def initialize_manager(k8s_client: Dict[str, Any]):
        try:
            # Проверяем клиента
            if k8s_client and k8s_client.get("core_v1_api") and k8s_client.get("apps_v1_api"):
                logger.info("K8S клиенты успешно инициализированы")
                # Даем небольшую задержку для разгрузки стартапа
                await asyncio.sleep(2)
                # Инициализируем состояние из API
                await initialize_state_from_api(k8s_client)
                # Запускаем наблюдателей в фоне
                await startup_state_manager(k8s_client)
            else:
                logger.error("K8S клиенты не инициализированы!")
        except Exception as e:
            logger.error(f"Ошибка при инициализации менеджера состояния: {str(e)}")
    # @app.on_event("startup")
    # async def startup_event():
    #     app.state.config = app_config
    #     app.state.k8s_client = k8s_client
    #     logger.info("FastAPI приложение запущено")

    #     # Инициализация менеджера состояния
    #     try:
    #         # Проверяем, правильно ли инициализирован k8s_client перед запуском
    #         if k8s_client and k8s_client.get("core_v1_api") and k8s_client.get("apps_v1_api"):
    #             logger.info("K8S клиенты успешно инициализированы, запускаем менеджер состояния")
    #             # Сначала инициализируем состояние из API для быстрого старта
    #             await asyncio.sleep(2)  # Даем небольшую задержку для полной инициализации
    #             await initialize_state_from_api(k8s_client)
    #             # Затем запускаем наблюдателей для работы в реальном времени
    #             await startup_state_manager(k8s_client)
    #         else:
    #             logger.error("K8S клиенты не инициализированы, нельзя запустить менеджер состояния!")
    #             # Попытка реинициализировать клиент
    #             from dashboard_light.k8s.core import create_k8s_client
    #             new_k8s_client = create_k8s_client(app_config)
    #             if new_k8s_client and new_k8s_client.get("core_v1_api"):
    #                 logger.info("K8S клиенты успешно переинициализированы")
    #                 app.state.k8s_client = new_k8s_client
    #                 await initialize_state_from_api(new_k8s_client)
    #                 await startup_state_manager(new_k8s_client)
    #             else:
    #                 logger.error("Не удалось инициализировать K8S клиенты даже после повторной попытки!")
    #     except Exception as e:
    #         logger.error(f"Ошибка при инициализации менеджера состояния: {str(e)}")

    # Добавление хука запуска для сохранения зависимостей в контексте приложения
    # @app.on_event("startup")
    # async def startup_event():
    #     app.state.config = app_config
    #     app.state.k8s_client = k8s_client
    #     logger.info("FastAPI приложение запущено")

    # Добавление хука остановки
    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("FastAPI приложение остановлено")

    return app


def start_server(app_config: Dict[str, Any], k8s_client: Dict[str, Any]) -> Dict[str, Any]:
    """Запуск веб-сервера с FastAPI приложением.

    Args:
        app_config: Конфигурация приложения
        k8s_client: Словарь с Kubernetes клиентом и API

    Returns:
        Dict[str, Any]: Словарь с информацией о запущенном сервере
    """
    app = create_app(app_config, k8s_client)

    # Определение параметров запуска сервера
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "3000"))
    reload = os.getenv("RELOAD", "false").lower() == "true"

    # Запуск сервера в отдельном потоке
    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
    server = uvicorn.Server(config)

    # Запуск сервера в отдельном потоке
    import threading
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    logger.info(f"Веб-сервер запущен на http://{host}:{port}")

    return {
        "app": app,
        "server": server,
        "thread": thread,
        "host": host,
        "port": port,
    }


def stop_server(server_info: Dict[str, Any]) -> None:
    """Остановка веб-сервера.

    Args:
        server_info: Словарь с информацией о запущенном сервере
    """
    if server_info and "server" in server_info:
        server = server_info["server"]
        if hasattr(server, "should_exit"):
            server.should_exit = True
            logger.info("Отправлен сигнал остановки веб-сервера")
