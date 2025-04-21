#!/usr/bin/env python
"""Клиент для нагрузочного тестирования WebSocket сервера с эмуляцией множества подключений."""

import asyncio
import json
import logging
import sys
import argparse
import time
import random
import signal
from typing import Dict, List, Any, Optional, Set

import websockets

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Счетчики для статистики
stats = {
    "connections_total": 0,          # Всего подключений создано
    "connections_active": 0,         # Активных подключений
    "connections_failed": 0,         # Неудачных подключений
    "connections_closed": 0,         # Закрытых подключений
    "messages_received": 0,          # Всего сообщений получено
    "messages_per_second": 0,        # Сообщений в секунду
    "errors": 0,                     # Ошибок
    "start_time": time.time(),       # Время начала теста
    "resources": {                   # Статистика по типам ресурсов
        "deployments": 0,
        "pods": 0, 
        "namespaces": 0
    }
}

# Активные клиенты
active_clients = []

# Функция для поддержки соединения
async def maintain_connection(client_id: int, url: str, resources: Dict[str, Optional[str]], duration: int = 60):
    """Создает и поддерживает WebSocket соединение.
    
    Args:
        client_id: Идентификатор клиента
        url: WebSocket URL
        resources: Ресурсы для подписки
        duration: Длительность работы в секундах
    """
    global stats, active_clients
    websocket = None
    
    try:
        # Создаем соединение с защитой от сбоев
        logger.debug(f"Клиент {client_id}: подключение к {url}...")
        
        # Добавляем случайную задержку, чтобы не создавать слишком много соединений одновременно
        await asyncio.sleep(random.uniform(0.1, 2.0))
        
        try:
            # Пытаемся установить соединение с таймаутом
            connection_timeout = 15  # 15 секунд на установку соединения
            
            # Используем контекстный менеджер с таймаутом
            async with asyncio.timeout(connection_timeout):
                websocket = await websockets.connect(
                    url, 
                    ping_interval=20, 
                    ping_timeout=10, 
                    close_timeout=5,
                    open_timeout=10,  # Таймаут на установку соединения
                    max_size=1_048_576  # 1 МБ максимальный размер сообщения
                )
        except Exception as e:
            logger.debug(f"Клиент {client_id}: ошибка подключения: {e}")
            stats["connections_failed"] += 1
            stats["errors"] += 1
            return
            
        # Работаем с установленным соединением
        async with websocket:
            # Обновляем статистику
            stats["connections_total"] += 1
            stats["connections_active"] += 1
            active_clients.append(client_id)
            
            logger.debug(f"Клиент {client_id}: подключен")
            
            # Подписываемся на ресурсы
            await subscribe_to_resources(websocket, resources)
            
            # Получаем сообщения до истечения времени
            end_time = time.time() + duration
            
            while time.time() < end_time:
                try:
                    # Таймаут для получения сообщения
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    
                    # Только считаем сообщения, но не обрабатываем их полностью
                    stats["messages_received"] += 1
                    
                    # Минимальная обработка для подсчета ресурсов
                    try:
                        data = json.loads(message)
                        if data.get("type") == "resource":
                            resource_type = data.get("resourceType")
                            if resource_type in stats["resources"]:
                                stats["resources"][resource_type] += 1
                    except:
                        pass
                        
                except asyncio.TimeoutError:
                    # Нормальная ситуация - просто проверяем, не истекло ли время
                    pass
                except websockets.exceptions.ConnectionClosed:
                    logger.debug(f"Клиент {client_id}: соединение закрыто сервером")
                    break
            
            # Корректно закрываем соединение
            logger.debug(f"Клиент {client_id}: закрытие соединения")
            await websocket.close()
            
    except websockets.exceptions.WebSocketException as e:
        logger.debug(f"Клиент {client_id}: ошибка WebSocket: {e}")
        stats["connections_failed"] += 1
        stats["errors"] += 1
    except Exception as e:
        logger.debug(f"Клиент {client_id}: ошибка: {e}")
        stats["errors"] += 1
    finally:
        # Обновляем статистику при завершении
        if client_id in active_clients:
            active_clients.remove(client_id)
            
        stats["connections_active"] -= 1
        stats["connections_closed"] += 1
        logger.debug(f"Клиент {client_id}: завершил работу")

async def subscribe_to_resources(websocket, resources: Dict[str, Optional[str]]) -> None:
    """Подписка на указанные ресурсы.
    
    Args:
        websocket: WebSocket соединение
        resources: Словарь ресурсов для подписки (тип ресурса -> namespace)
    """
    try:
        # Ждем приветственное сообщение
        await asyncio.wait_for(websocket.recv(), timeout=5.0)
        
        # Подписываемся на ресурсы
        for resource_type, namespace in resources.items():
            # Формируем сообщение подписки
            message = {
                "type": "subscribe",
                "resourceType": resource_type
            }
            
            if namespace:
                message["namespace"] = namespace
                
            # Отправляем запрос на подписку
            await websocket.send(json.dumps(message))
            
    except Exception as e:
        # Просто логируем ошибку, но не прекращаем работу
        logger.debug(f"Ошибка при подписке: {e}")

async def print_stats():
    """Выводит текущую статистику работы клиентов."""
    global stats
    
    # Формат вывода
    template = """
╔══════════════════════════════════════════════════════
║ Dashboard-Light WebSocket Load Test
╠══════════════════════════════════════════════════════
║ Время работы:       {duration:.2f} сек
║ Подключений:        {connections_total} (активных: {connections_active})
║ Неудачных:          {connections_failed}
║ Закрытых:           {connections_closed}
║ Сообщений:          {messages_received}
║ Сообщений/сек:      {messages_per_second:.2f}
║ Ошибок:             {errors}
╠══════════════════════════════════════════════════════
║ Deployments:        {deployments}
║ Pods:               {pods}
║ Namespaces:         {namespaces}
╚══════════════════════════════════════════════════════
"""
    
    while True:
        # Обновляем статистику сообщений в секунду
        current_time = time.time()
        duration = current_time - stats["start_time"]
        
        if duration > 0:
            stats["messages_per_second"] = stats["messages_received"] / duration
            
        # Формируем данные для шаблона
        template_data = {
            "duration": duration,
            **stats,
            **stats["resources"]
        }
        
        # Выводим статистику
        print("\033[H\033[J", end="")  # Очистка экрана
        print(template.format(**template_data))
        
        # Ждем перед следующим обновлением
        await asyncio.sleep(1)

async def run_load_test(url: str, num_clients: int, resources: Dict[str, Optional[str]], duration: int = 60) -> None:
    """Запускает тест с указанным количеством клиентов.
    
    Args:
        url: WebSocket URL для подключения
        num_clients: Количество одновременных клиентов
        resources: Ресурсы для подписки
        duration: Длительность работы клиентов
    """
    logger.info(f"Запуск теста с {num_clients} клиентами на {duration} секунд")
    
    # Сбрасываем статистику
    stats["start_time"] = time.time()
    stats["connections_total"] = 0
    stats["connections_active"] = 0
    stats["connections_failed"] = 0
    stats["connections_closed"] = 0
    stats["messages_received"] = 0
    stats["errors"] = 0
    stats["resources"] = {"deployments": 0, "pods": 0, "namespaces": 0}
    
    # Создаем задачи для вывода статистики
    stats_task = asyncio.create_task(print_stats())
    
    # Создаем задачи для клиентов
    client_tasks = []
    for i in range(num_clients):
        # Небольшая случайная задержка для равномерного запуска клиентов
        await asyncio.sleep(random.uniform(0.1, 0.5))
        
        # Создаем задачу для клиента
        task = asyncio.create_task(
            maintain_connection(i, url, resources, duration)
        )
        client_tasks.append(task)
        
    # Ждем завершения всех клиентов
    await asyncio.gather(*client_tasks)
    
    # Отменяем вывод статистики
    stats_task.cancel()
    
    # Выводим итоговую статистику
    logger.info(f"Тест завершен. Обработано {stats['messages_received']} сообщений за {duration} секунд")
    logger.info(f"Средняя скорость: {stats['messages_per_second']:.2f} сообщений в секунду")
    logger.info(f"Ошибок: {stats['errors']}")

async def shutdown(signal, loop):
    """Корректное завершение работы."""
    logger.info(f"Получен сигнал {signal.name}, завершение работы...")
    
    # Отменяем все задачи
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    
    for task in tasks:
        task.cancel()
        
    logger.info(f"Отменено {len(tasks)} задач")
    
    # Останавливаем цикл событий
    loop.stop()

def main():
    """Основная функция для запуска нагрузочного тестирования."""
    # Настройка аргументов командной строки
    parser = argparse.ArgumentParser(description="WebSocket нагрузочное тестирование для Dashboard-Light")
    parser.add_argument("--url", default="ws://localhost:8765/",
                     help="WebSocket URL (по умолчанию: ws://localhost:8765/)")
    parser.add_argument("--clients", type=int, default=50,
                     help="Количество одновременных клиентов (по умолчанию: 50)")
    parser.add_argument("--duration", type=int, default=60,
                     help="Длительность теста в секундах (по умолчанию: 60)")
    parser.add_argument("--namespace", help="Фильтр по namespace (опционально)")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO",
                     help="Уровень логирования (по умолчанию: INFO)")
    
    args = parser.parse_args()
    
    # Настройка уровня логирования
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Определение списка ресурсов для подписки
    resources = {
        "deployments": args.namespace,
        "pods": args.namespace,
        "namespaces": None  # Namespaces не фильтруются по namespace
    }
    
    # Настройка асинхронного цикла событий
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Регистрация обработчиков сигналов
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig, lambda s=sig: asyncio.create_task(shutdown(s, loop))
        )
    
    # Запуск теста
    try:
        logger.info(f"Запуск нагрузочного теста на {args.url} с {args.clients} клиентами на {args.duration} секунд")
        loop.run_until_complete(run_load_test(args.url, args.clients, resources, args.duration))
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания. Завершение работы.")
    finally:
        loop.close()
        logger.info("Тест завершен.")

if __name__ == "__main__":
    main()