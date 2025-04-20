#!/usr/bin/env python
"""Минимальное тестовое приложение для WebSocket."""

import logging
import uvicorn
from fastapi import FastAPI, WebSocket
import json

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Создание простого FastAPI приложения
app = FastAPI(title="WebSocket Test App")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Простой WebSocket эндпоинт для тестирования."""
    logger.info("WebSocket соединение получено")

    # Принимаем соединение
    await websocket.accept()
    logger.info("WebSocket соединение принято")

    # Отправляем приветственное сообщение
    await websocket.send_json({"message": "Привет, WebSocket работает!"})

    # Обрабатываем сообщения от клиента
    try:
        while True:
            # Получаем сообщение от клиента
            data = await websocket.receive_text()
            logger.info(f"Получено сообщение: {data}")

            # Парсим JSON
            try:
                message = json.loads(data)
                # Эхо сообщения обратно
                await websocket.send_json({
                    "type": "echo",
                    "original": message,
                    "message": "Эхо: " + str(message)
                })
            except json.JSONDecodeError:
                # Если не JSON, просто отправляем текст обратно
                await websocket.send_text(f"Эхо: {data}")
    except Exception as e:
        logger.error(f"Ошибка при обработке WebSocket: {e}")

@app.get("/")
async def root():
    """Корневой маршрут."""
    return {"message": "Это тестовое приложение для WebSocket"}

if __name__ == "__main__":
    # Запуск приложения
    logger.info("Запуск тестового WebSocket сервера на порту 3000")
    uvicorn.run(app, host="0.0.0.0", port=3000)
