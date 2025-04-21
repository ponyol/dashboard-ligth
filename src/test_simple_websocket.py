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
        "ping_interval": 5,     # Отправка ping каждые 5 секунд (соответствует серверу)
        "ping_timeout": 5,      # Ожидание ответа 5 секунд (соответствует серверу)
        "close_timeout": 5,     # Таймаут закрытия 5 секунд (соответствует серверу)
        "max_size": 10485760,   # 10MB макс размер сообщения
    }

    logger.info(f"Подключение к {uri}...")

    try:
        async with websockets.connect(uri, **connection_options) as websocket:
            logger.info(f"Соединение установлено!")

            # Задача для обработки входящих сообщений
            async def handle_messages():
                try:
                    while True:
                        try:
                            message = await websocket.recv()
                            try:
                                data = json.loads(message)
                                message_type = data.get('type')
                                
                                if message_type == 'connection':
                                    logger.info(f"Получено приветствие: {message}")
                                elif message_type == 'pong':
                                    logger.info(f"Получен pong: {message}")
                                elif message_type == 'heartbeat':
                                    logger.info(f"Получен heartbeat: {message}")
                                    # Отправляем подтверждение heartbeat
                                    await websocket.send(json.dumps({
                                        "type": "heartbeat_ack",
                                        "timestamp": data.get("timestamp")
                                    }))
                                    logger.debug("Отправлено подтверждение heartbeat")
                                else:
                                    logger.info(f"Получено сообщение: {message}")
                            except json.JSONDecodeError:
                                logger.warning(f"Получен некорректный JSON: {message}")
                        except websockets.exceptions.ConnectionClosed:
                            logger.error("Соединение закрыто сервером")
                            return
                        except Exception as e:
                            logger.error(f"Ошибка при получении сообщения: {e}")
                except asyncio.CancelledError:
                    logger.debug("Задача обработки сообщений отменена")

            # Запускаем задачу обработки сообщений
            message_task = asyncio.create_task(handle_messages())
            
            # В новой версии мы не отправляем собственные ping сообщения,
            # а полагаемся на встроенный механизм ping/pong библиотеки websockets
            ping_task = None
            
            # Ждем 60 секунд
            try:
                logger.info("Тест начался, ждем 60 секунд...")
                await asyncio.sleep(60)
                logger.info("Тест успешно завершен!")
            except asyncio.CancelledError:
                logger.info("Тест прерван")
            finally:
                # Отменяем задачу обработки сообщений
                if message_task and not message_task.done():
                    message_task.cancel()
                    
                    # Ждем завершения задачи
                    try:
                        await asyncio.wait_for(message_task, timeout=2.0)
                    except (asyncio.TimeoutError, asyncio.CancelledError, Exception) as e:
                        if isinstance(e, asyncio.CancelledError):
                            logger.debug("Задача обработки сообщений отменена")
                        else:
                            logger.error(f"Ошибка при отмене задачи: {e}")
                
                # Закрываем соединение
                logger.info("Закрытие соединения...")
                await websocket.close()
                logger.info("Соединение закрыто")

    except websockets.exceptions.ConnectionClosed as e:
        logger.error(f"Соединение закрыто: {e}")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        logger.error(''.join(traceback.format_exception(type(e), e, e.__traceback__)))

if __name__ == "__main__":
    # Включаем обработку исключений для корректного выхода
    import traceback
    
    # Запуск теста
    try:
        asyncio.run(simple_test())
    except KeyboardInterrupt:
        logger.info("Тест прерван пользователем")
    except Exception as e:
        logger.error(f"Необработанная ошибка: {e}")
        logger.error(''.join(traceback.format_exception(type(e), e, e.__traceback__)))