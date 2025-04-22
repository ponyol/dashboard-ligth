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

# В файле src/dashboard_light/web/core.py, полностью перепишем функцию create_app:

# def create_app(app_config: Dict[str, Any], k8s_client: Dict[str, Any]) -> FastAPI:
#     """Создание и настройка FastAPI приложения.

#     Args:
#         app_config: Конфигурация приложения
#         k8s_client: Словарь с Kubernetes клиентом и API

#     Returns:
#         FastAPI: Настроенное FastAPI приложение
#     """
#     # Создание FastAPI приложения
#     app = FastAPI(
#         title="Dashboard Light",
#         description="""Система мониторинга EKS Deployments & Pods

# ## ВАЖНОЕ ПРИМЕЧАНИЕ О DEPRECATION
# **ВНИМАНИЕ:** REST API больше не является основным способом получения данных.
# Все HTTP API эндпоинты считаются устаревшими.

# Для получения данных в реальном времени используйте WebSocket подключение
# на эндпоинте: `/api/k8s/ws`

# WebSocket-сервер обеспечивает более эффективный способ доставки обновлений,
# используя Watch API Kubernetes для получения мгновенных обновлений ресурсов.
#         """,
#         version="0.2.0",
#     )

#     # Настройка CORS
#     app.add_middleware(
#         CORSMiddleware,
#         allow_origins=["*"],  # В продакшене нужно ограничить
#         allow_credentials=True,
#         allow_methods=["*"],
#         allow_headers=["*"],
#     )

#     # Добавление middleware для сессий (отдельный вызов)
#     app.add_middleware(
#         SessionMiddleware,
#         secret_key=os.environ.get("SESSION_SECRET", secrets.token_hex(32))
#     )
#     # Добавление пользовательских middleware
#     add_middlewares(app)

#     # Импортируем модули для WebSocket тут, чтобы избежать циклических импортов
#     from dashboard_light.web.websockets import handle_connection
#     from dashboard_light.k8s.watch import start_watching, get_active_watches
#     import websockets.exceptions

#     # Напрямую добавляем WebSocket эндпоинт в приложение
#     @app.websocket("/api/k8s/ws")
#     async def websocket_endpoint(websocket: WebSocket):
#         """WebSocket эндпоинт для получения обновлений в реальном времени."""
#         try:
#             # Проверяем, запущены ли наблюдатели
#             active_watches = get_active_watches()
#             if not active_watches:
#                 # Запускаем наблюдение за ресурсами
#                 logger.info("Запуск наблюдателей за ресурсами при первом WebSocket подключении")
#                 await start_watching(k8s_client)

#             # Обработка WebSocket соединения
#             await handle_connection(websocket, app_config)
#         except Exception as e:
#             logger.error(f"Ошибка в WebSocket обработчике: {str(e)}")
#             if not websocket.client_state == WebSocketState.DISCONNECTED:
#                 await websocket.close(code=1011, reason=f"Internal server error: {str(e)}")

#     # Создание и добавление API роутеров
#     main_router = create_router(app_config, k8s_client)
#     if main_router is not None:
#         app.include_router(main_router)
#     else:
#         logger.error("Не удалось создать основной роутер - он равен None")
#         raise ValueError("Основной роутер приложения не был инициализирован корректно")

#     # Определение пути к статическим файлам
#     project_root = Path(__file__).parent.parent.parent.parent  # 4 уровня вверх от web/core.py
#     static_dir = project_root / "resources" / "public"

#     # Проверка существования директории
#     if static_dir.exists():
#         # Монтирование статических файлов
#         app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
#         logger.info(f"Смонтированы статические файлы из {static_dir} на корневой путь")

#         # Монтирование директории ассетов отдельно, если она существует
#         assets_dir = static_dir / "assets"
#         if assets_dir.exists():
#             app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
#             logger.info(f"Смонтированы ассеты из {assets_dir} на /assets")
#     else:
#         logger.warning(f"Директория статических файлов не найдена: {static_dir}")

#     # Добавление хука запуска для сохранения зависимостей в контексте приложения
#     @app.on_event("startup")
#     async def startup_event():
#         global _cleanup_task

#         app.state.config = app_config
#         app.state.k8s_client = k8s_client

#         # Запуск задачи периодической очистки неактивных соединений
#         async def periodic_cleanup():
#             while True:
#                 try:
#                     await clean_inactive_connections(max_inactivity_seconds=1800)  # 30 минут
#                     await asyncio.sleep(300)  # Проверка каждые 5 минут
#                 except asyncio.CancelledError:
#                     logger.info("Задача очистки неактивных соединений остановлена")
#                     break
#                 except Exception as e:
#                     logger.error(f"Ошибка в задаче очистки соединений: {str(e)}")
#                     await asyncio.sleep(60)  # При ошибке ждем 1 минуту перед повтором

#         _cleanup_task = asyncio.create_task(periodic_cleanup())
#         logger.info("Запущена задача очистки неактивных WebSocket соединений")

#         logger.info("FastAPI приложение запущено")

#     # Добавление хука остановки
#     @app.on_event("shutdown")
#     async def shutdown_event():
#         global _cleanup_task

#         # Остановка всех задач наблюдения
#         await stop_watching()

#         # Остановка задачи очистки соединений
#         if _cleanup_task and not _cleanup_task.done():
#             _cleanup_task.cancel()
#             try:
#                 await _cleanup_task
#             except asyncio.CancelledError:
#                 pass

#         logger.info("FastAPI приложение остановлено")

#     return app

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

# def start_server(app_config: Dict[str, Any], k8s_client: Dict[str, Any]) -> Dict[str, Any]:
#     """Запуск веб-сервера с FastAPI приложением.

#     Args:
#         app_config: Конфигурация приложения
#         k8s_client: Словарь с Kubernetes клиентом и API

#     Returns:
#         Dict[str, Any]: Словарь с информацией о запущенном сервере
#     """
#     app = create_app(app_config, k8s_client)

#     # Определение параметров запуска сервера
#     host = os.getenv("HOST", "0.0.0.0")
#     port = int(os.getenv("PORT", "3000"))
#     reload = os.getenv("RELOAD", "false").lower() == "true"

#     # Запуск сервера в отдельном потоке
#     config = uvicorn.Config(
#         app=app,
#         host=host,
#         port=port,
#         reload=reload,
#         log_level="info",
#     )
#     server = uvicorn.Server(config)

#     # Запуск сервера в отдельном потоке
#     import threading
#     thread = threading.Thread(target=server.run, daemon=True)
#     thread.start()

#     logger.info(f"Веб-сервер запущен на http://{host}:{port}")

#     return {
#         "app": app,
#         "server": server,
#         "thread": thread,
#         "host": host,
#         "port": port,
#     }
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
