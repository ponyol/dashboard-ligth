// frontend/src/hooks/useWebSocket.js
import { useState, useEffect, useCallback, useRef } from 'react';

const RECONNECT_TIMEOUT = 3000; // 3 секунды
const MAX_RECONNECT_TIMEOUT = 30000; // 30 секунд

/**
 * Хук для работы с WebSocket соединением
 * @param {string} url - URL для подключения к WebSocket серверу
 * @param {Object} options - Дополнительные опции
 * @returns {Object} Состояние и методы для работы с WebSocket
 */
export default function useWebSocket(url, options = {}) {
  const [status, setStatus] = useState('closed');
  const [error, setError] = useState(null);
  const [messages, setMessages] = useState([]);

  const socket = useRef(null);
  const reconnectTimeout = useRef(null);
  const reconnectAttempts = useRef(0);
  const pingInterval = useRef(null);

  // Функция для инициализации соединения
  const connect = useCallback(() => {
    // Очистка предыдущего соединения
    if (socket.current) {
      socket.current.close();
    }

    // Очистка таймера переподключения
    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current);
      reconnectTimeout.current = null;
    }

    try {
      setStatus('connecting');
      socket.current = new WebSocket(url);

      // Обработчик открытия соединения
      socket.current.onopen = () => {
        setStatus('open');
        setError(null);
        reconnectAttempts.current = 0;

        // Настройка периодического пинга
        if (pingInterval.current) clearInterval(pingInterval.current);
        pingInterval.current = setInterval(() => {
          if (socket.current && socket.current.readyState === WebSocket.OPEN) {
            socket.current.send(JSON.stringify({ type: 'ping' }));
          }
        }, 30000); // Пинг каждые 30 секунд

        // Подписка на ресурсы, если указаны
        if (options.subscriptions && options.subscriptions.length > 0) {
          options.subscriptions.forEach(subscription => {
            send({
              type: 'subscribe',
              resource_type: subscription.resourceType,
              namespace: subscription.namespace || null
            });
          });
        }
      };

      // Обработчик сообщений
      socket.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // Для событий ресурсов добавляем их в список сообщений
          if (data.type === 'resource') {
            setMessages(prev => [...prev, data]);
          }

          // Вызов пользовательского обработчика, если есть
          if (options.onMessage) {
            options.onMessage(data);
          }
        } catch (e) {
          console.error('Ошибка при обработке сообщения:', e);
        }
      };

      // Обработчик ошибок
      socket.current.onerror = (event) => {
        setError('Ошибка WebSocket соединения');
        console.error('WebSocket error:', event);
      };

      // Обработчик закрытия соединения
      socket.current.onclose = (event) => {
        setStatus('closed');

        // Очистка пинга
        if (pingInterval.current) {
          clearInterval(pingInterval.current);
          pingInterval.current = null;
        }

        // Максимальное количество попыток переподключения
        const MAX_RECONNECT_ATTEMPTS = 3;
        
        // Если соединение было закрыто не по нашей инициативе и не превышено макс. число попыток
        if (!event.wasClean && options.autoReconnect !== false && reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttempts.current += 1;

          // Экспоненциальная задержка для переподключения
          const delay = Math.min(
            RECONNECT_TIMEOUT * Math.pow(1.5, reconnectAttempts.current - 1),
            MAX_RECONNECT_TIMEOUT
          );

          console.log(`Переподключение через ${delay}ms (попытка ${reconnectAttempts.current}/${MAX_RECONNECT_ATTEMPTS})`);

          reconnectTimeout.current = setTimeout(() => {
            connect();
          }, delay);
        } else if (reconnectAttempts.current >= MAX_RECONNECT_ATTEMPTS && options.autoReconnect !== false) {
          console.error(`Превышено максимальное количество попыток переподключения (${MAX_RECONNECT_ATTEMPTS})`);
          setError(`Не удалось подключиться после ${MAX_RECONNECT_ATTEMPTS} попыток`);
        }
      };
    } catch (e) {
      setStatus('error');
      setError(`Ошибка при создании WebSocket: ${e.message}`);
      console.error('Failed to create WebSocket:', e);
    }
  }, [url, options]);

  // Функция отправки данных
  const send = useCallback((data) => {
    if (socket.current && socket.current.readyState === WebSocket.OPEN) {
      socket.current.send(JSON.stringify(data));
      return true;
    }
    return false;
  }, []);

  // Функция закрытия соединения
  const close = useCallback(() => {
    if (socket.current) {
      socket.current.close();
    }

    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current);
      reconnectTimeout.current = null;
    }

    if (pingInterval.current) {
      clearInterval(pingInterval.current);
      pingInterval.current = null;
    }
  }, []);

  // Установка соединения при монтировании компонента
  useEffect(() => {
    connect();

    // Закрытие соединения при размонтировании
    return () => {
      close();
    };
  }, [connect, close]);

  return {
    status,
    error,
    messages,
    send,
    close,
    reconnect: connect
  };
}
