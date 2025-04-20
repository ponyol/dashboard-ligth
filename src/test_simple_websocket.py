#!/usr/bin/env python
"""Простой тест WebSocket соединения."""

import asyncio
import json
import logging
import sys

import websockets

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Также настраиваем логирование websockets библиотеки
websockets_logger = logging.getLogger('websockets')
websockets_logger.setLevel(logging.DEBUG)

async def simple_test():
    """Простой тест соединения с WebSocket сервером."""
    uri = "ws://localhost:8765/"

    # Параметры соединения для более стабильной работы
    connection_options = {
        "ping_interval": 5,    # Отправка ping каждые 5 секунд
        "ping_timeout": 10,    # Ожидание ответа 10 секунд
        "close_timeout": 10,   # Таймаут закрытия 10 секунд
        "max_size": 10485760,  # 10MB макс размер сообщения
    }

    logger.info(f"Подключение к {uri}...")

    try:
        async with websockets.connect(uri, **connection_options) as websocket:
            logger.info(f"Соединение установлено!")

            # Ожидаем приветственное сообщение
            try:
                greeting = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                logger.info(f"Получено приветствие: {greeting}")
            except asyncio.TimeoutError:
                logger.warning("Не получено приветственное сообщение в течение 5 секунд")

            # Отправляем простой ping
            ping_message = json.dumps({"type": "ping", "timestamp": "test"})
            logger.info(f"Отправка ping: {ping_message}")
            await websocket.send(ping_message)

            # Ожидаем ответ
            try:
                pong = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                logger.info(f"Получен ответ: {pong}")
            except asyncio.TimeoutError:
                logger.warning("Нет ответа на ping в течение 5 секунд")

            # Поддерживаем соединение в течение некоторого времени
            try:
                # Просто ждем 30 секунд, наблюдая за состоянием соединения
                for i in range(30):
                    logger.info(f"Соединение активно... {i+1}/30 сек")
                    await asyncio.sleep(1)

                    # Каждые 5 секунд отправляем ping
                    if i % 5 == 0 and i > 0:
                        ping_message = json.dumps({"type": "ping", "timestamp": f"test-{i}"})
                        logger.info(f"Отправка регулярного ping: {ping_message}")
                        await websocket.send(ping_message)

                        # Ожидаем ответ
                        try:
                            pong = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                            logger.info(f"Получен ответ: {pong}")
                        except asyncio.TimeoutError:
                            logger.warning("Нет ответа на регулярный ping")
            except Exception as e:
                logger.error(f"Ошибка во время поддержания соединения: {e}")

            # Корректно закрываем соединение
            logger.info("Закрытие соединения...")
            await websocket.close()
            logger.info("Соединение закрыто")

    except websockets.exceptions.ConnectionClosed as e:
        logger.error(f"Соединение закрыто: {e}")
    except Exception as e:
        logger.error(f"Ошибка: {e}")

if __name__ == "__main__":
    # Запуск теста
    asyncio.run(simple_test())
