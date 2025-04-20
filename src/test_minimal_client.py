#!/usr/bin/env python
"""Минимальный клиент для тестирования WebSocket."""

import asyncio
import websockets
import json
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def test_websocket():
    """Тестирование WebSocket соединения."""
    uri = "ws://localhost:3000/ws"
    logger.info(f"Подключение к {uri}...")

    try:
        async with websockets.connect(uri) as websocket:
            logger.info("Соединение установлено!")

            # Получаем приветственное сообщение
            response = await websocket.recv()
            logger.info(f"Получено: {response}")

            # Отправляем тестовое сообщение
            message = {"type": "test", "content": "Тестовое сообщение"}
            logger.info(f"Отправка: {message}")
            await websocket.send(json.dumps(message))

            # Получаем ответ
            response = await websocket.recv()
            logger.info(f"Получено: {response}")

            # Отправляем еще одно сообщение
            logger.info("Отправка: Простой текст")
            await websocket.send("Простой текст")

            # Получаем ответ
            response = await websocket.recv()
            logger.info(f"Получено: {response}")

            # Закрываем соединение
            logger.info("Тест завершен успешно!")

    except websockets.exceptions.ConnectionClosed as e:
        logger.error(f"Соединение закрыто: {e}")
    except Exception as e:
        logger.error(f"Ошибка: {e}")

if __name__ == "__main__":
    # Запуск клиента
    asyncio.run(test_websocket())
