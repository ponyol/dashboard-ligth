#!/usr/bin/env python
"""Отдельный WebSocket сервер без FastAPI."""

import asyncio
import json
import logging
import os
import sys
import signal
import websockets

# Добавляем родительскую директорию в путь для импорта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dashboard_light.config import core as config
from dashboard_light.k8s import core as k8s
from dashboard_light.state_manager import update_resource_state, subscribe, get_resources_by_type
from dashboard_light.k8s.watch import start_watching, stop_watching, get_active_watches
from dashboard_light.utils.logging import configure_logging
from dashboard_light.websocket_server import run_server

# Настройка логирования с использованием централизованной функции
# Уровень логирования будет взят из переменной окружения LOG_LEVEL
configure_logging()
logger = logging.getLogger(__name__)

"""
Этот файл является оберткой для запуска WebSocket сервера из модуля dashboard_light.websocket_server.
Большая часть реализации была перенесена в тот модуль для лучшей модульности и переиспользования кода.
"""

if __name__ == "__main__":
    # Запуск WebSocket сервера из модуля dashboard_light.websocket_server
    run_server()
