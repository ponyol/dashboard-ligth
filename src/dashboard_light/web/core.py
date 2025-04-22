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
from dashboard_light.k8s.watch import start_watching, stop_watching
from fastapi import WebSocket
from dashboard_light.web.websockets import clean_inactive_connections
from fastapi.responses import FileResponse
from starlette.websockets import WebSocketState

# Добавить переменную для хранения задачи очистки
_cleanup_task = None

logger = logging.getLogger(__name__)

def create_app(app_config: Dict[str, Any], k8s_client: Dict[str, Any]) -> FastAPI:
    """Создание и настройка FastAPI приложения."""
    # Создание FastAPI приложения
    app = FastAPI(
        title="Dashboard Light",
        description="""Система мониторинга EKS Deployments & Pods""",
        version="0.2.0",
    )

    # ВАЖНО: Первым делом монтируем статические файлы - ДО всех остальных операций
    # Определение пути к статическим файлам
    project_root = Path(__file__).parent.parent.parent.parent
    static_dir = project_root / "resources" / "public"

    # Проверка существования директории
    if static_dir.exists():
        # Монтирование статических файлов
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
        logger.info(f"Смонтированы статические файлы из {static_dir} на корневой путь")

        # Монтирование директории ассетов отдельно, если она существует
        assets_dir = static_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
            logger.info(f"Смонтированы ассеты из {assets_dir} на /assets")
    else:
        logger.warning(f"Директория статических файлов не найдена: {static_dir}")

    # Настройка CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Добавление middleware для сессий
    app.add_middleware(
        SessionMiddleware,
        secret_key=os.environ.get("SESSION_SECRET", secrets.token_hex(32))
    )

    # Добавление пользовательских middleware
    add_middlewares(app)

    # Создание и добавление API роутеров
    main_router = create_router(app_config, k8s_client)
    if main_router is not None:
        app.include_router(main_router)
    else:
        logger.error("Не удалось создать основной роутер - он равен None")
        raise ValueError("Основной роутер приложения не был инициализирован корректно")

    # Добавление хука запуска для ОТЛОЖЕННОГО ЗАПУСКА ТЯЖЕЛЫХ СЕРВИСОВ
    @app.on_event("startup")
    async def startup_event():
        app.state.config = app_config
        app.state.k8s_client = k8s_client

        # Запуск K8s наблюдателей АСИНХРОННО ПОСЛЕ старта приложения
        async def delayed_k8s_watcher_start():
            try:
                # Подождем 1 секунду, чтобы приложение успело ответить на первые запросы
                await asyncio.sleep(1)

                # Здесь асинхронно запускаем наблюдение за ресурсами
                from dashboard_light.k8s.watch import start_watching
                await start_watching(k8s_client, ['deployments', 'pods', 'namespaces', 'statefulsets'])
                logger.info("K8s наблюдатели запущены асинхронно ПОСЛЕ старта приложения")
            except Exception as e:
                logger.error(f"Ошибка при асинхронном запуске K8s наблюдателей: {e}")

        # Запускаем наблюдателей в фоновом режиме
        asyncio.create_task(delayed_k8s_watcher_start())
        logger.info("Запланирован отложенный запуск K8s наблюдателей")

        logger.info("FastAPI приложение запущено")

    # Добавление хука остановки
    @app.on_event("shutdown")
    async def shutdown_event():
        # Остановка всех задач наблюдения
        from dashboard_light.k8s.watch import stop_watching
        await stop_watching()
        logger.info("FastAPI приложение остановлено")

    return app

def start_server(app_config: Dict[str, Any], k8s_client: Dict[str, Any]) -> Dict[str, Any]:
    """Запуск веб-сервера с FastAPI приложением."""
    app = create_app(app_config, k8s_client)

    # Определение параметров запуска сервера
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "3000"))

    # ВАЖНО: увеличиваем таймауты
    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info",
        timeout_keep_alive=120,  # Увеличиваем время ожидания keep-alive
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
