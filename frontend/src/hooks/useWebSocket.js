import { useState, useEffect, useRef, useCallback } from 'react';
import { API_CONFIG } from '../api/api';

/**
 * Хук для работы с WebSocket соединением и подписками
 * @param {Object} options - Опции подключения
 * @returns {Object} - API для работы с WebSocket
 */
export default function useWebSocket(options = {}) {
  const { onConnect, onDisconnect, onError, retryInterval = 5000 } = options;

  // Состояния для хранения объектов и статусов
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [lastError, setLastError] = useState(null);
  const [resources, setResources] = useState({
    namespaces: [],
    deployments: [],
    controllers: [],
    pods: [],
    statefulsets: [] // Добавляем отдельный массив для statefulsets
  });

  // Ref для сохранения WebSocket соединения
  const socketRef = useRef(null);
  // Ref для отслеживания активных подписок
  const subscriptionsRef = useRef(new Map());
  // Ref для хранения обработчиков событий
  const handlersRef = useRef({
    onConnect: onConnect || (() => {}),
    onDisconnect: onDisconnect || (() => {}),
    onError: onError || (() => {})
  });
  // Ref для контроля попыток переподключения
  const reconnectTimeoutRef = useRef(null);

  // Обновляем ref с обработчиками при изменении входных опций
  useEffect(() => {
    handlersRef.current = {
      onConnect: onConnect || handlersRef.current.onConnect,
      onDisconnect: onDisconnect || handlersRef.current.onDisconnect,
      onError: onError || handlersRef.current.onError
    };
  }, [onConnect, onDisconnect, onError]);

  // Функция для создания WebSocket соединения
  const connect = useCallback(() => {
    try {
      if (socketRef.current && (socketRef.current.readyState === WebSocket.OPEN || socketRef.current.readyState === WebSocket.CONNECTING)) {
        console.log('WebSocket already connected or connecting');
        return;
      }

      setIsConnecting(true);
      console.log(`Connecting to WebSocket server at ${API_CONFIG.websocket.url}`);

      // Создаем новое WebSocket соединение
      const ws = new WebSocket(API_CONFIG.websocket.url);

      // Обработчик события открытия соединения
      ws.onopen = () => {
        console.log('WebSocket connection established');
        setIsConnected(true);
        setIsConnecting(false);
        setLastError(null);

        // Вызываем пользовательский обработчик
        handlersRef.current.onConnect();

        // Восстанавливаем подписки после переподключения
        if (subscriptionsRef.current.size > 0) {
          console.log(`Restoring ${subscriptionsRef.current.size} subscriptions`);
          subscriptionsRef.current.forEach((namespace, resourceType) => {
            subscribe(resourceType, namespace);
          });
        }
      };

      // Обработчик сообщений
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          // console.debug('Received WebSocket message:', data.type);

          // Обработка разных типов сообщений
          const messageType = data.type || '';

          // В useWebSocket.js добавь обработку нового типа сообщений
          if (messageType === 'resource_batch') {
            // Обработка пакета ресурсов
            const batchResources = data.resources || [];
            const resourceType = data.resourceType;
            const progress = data.progress || 0;

            // console.log(`Получен пакет ${data.batchNumber}/${data.totalBatches} для ${resourceType} (${progress}%)`);

            // Добавляем ресурсы из пакета в состояние
            setResources(prevResources => {
              const newResources = {...prevResources};
              const typeKey = resourceType;

              if (!Array.isArray(newResources[typeKey])) {
                newResources[typeKey] = [];
              }

              // Добавляем ресурсы из пакета к уже имеющимся
              const currentResources = [...newResources[typeKey]];

              // Обрабатываем каждый ресурс в пакете
              for (const resource of batchResources) {
                // Ищем существующий ресурс по имени и namespace
                const index = currentResources.findIndex(item =>
                  item &&
                  item.name === resource.name &&
                  (resourceType === 'namespaces' || item.namespace === resource.namespace)
                );

                if (index !== -1) {
                  // Обновляем существующий ресурс
                  currentResources[index] = resource;
                } else {
                  // Добавляем новый ресурс
                  currentResources.push(resource);
                }
              }

              // Обновляем список ресурсов
              newResources[typeKey] = currentResources;
              return newResources;
            });
          }
          // else if (messageType === 'connection') {
          //   // Сообщение при установке соединения
          //   console.log('Connection message received:', data.message);
          // }
          else if (messageType === 'resource') {
            // Обновление ресурса
            handleResourceUpdate(data);
          }
          // else if (messageType === 'initial_state_complete') {
          //   // Завершение передачи начального состояния
          //   console.log(`Initial state complete for ${data.resourceType}. Received ${data.count} items.`);
          // }
          // else if (messageType === 'subscribed') {
          //   // Подтверждение подписки
          //   console.log(`Successfully subscribed to ${data.resourceType} in namespace ${data.namespace || 'all'}`);
          // }
          // else if (messageType === 'unsubscribed') {
          //   // Подтверждение отписки
          //   console.log(`Successfully unsubscribed from ${data.resourceType} in namespace ${data.namespace || 'all'}`);
          // }
          else if (messageType === 'error') {
            // Ошибка
            console.error('WebSocket error message:', data.message);
            setLastError(data.message);
            handlersRef.current.onError(new Error(data.message));
          }
          else if (messageType === 'ping' || messageType === 'pong') {
            // Пинг-понг для поддержания соединения
            console.debug(`Received ${data.type} message with timestamp ${data.timestamp}`);
            if (messageType === 'ping') {
              sendPong(data.timestamp);
            }
          }
          else {
            console.log('Unknown message type:', messageType);
          }
        } catch (err) {
          console.error('Error parsing WebSocket message:', err, event.data);
        }
      };

      // Обработчик закрытия соединения
      ws.onclose = (event) => {
        console.log(`WebSocket connection closed. Code: ${event.code}, Reason: ${event.reason}`);
        setIsConnected(false);
        setIsConnecting(false);

        // Вызываем пользовательский обработчик
        handlersRef.current.onDisconnect(event);

        // Запускаем переподключение, если соединение было закрыто не вручную
        if (event.code !== 1000) {
          scheduleReconnect();
        }
      };

      // Обработчик ошибок
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setLastError('WebSocket connection error');

        // Вызываем пользовательский обработчик
        handlersRef.current.onError(error);
      };

      // Сохраняем соединение в ref
      socketRef.current = ws;

    } catch (err) {
      console.error('Error creating WebSocket connection:', err);
      setIsConnecting(false);
      setLastError(err.message || 'Unknown connection error');
      handlersRef.current.onError(err);

      // Пробуем переподключиться
      scheduleReconnect();
    }
  }, []);

  // Функция для запланированного переподключения
  const scheduleReconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }

    console.log(`Scheduling reconnect in ${retryInterval}ms`);
    reconnectTimeoutRef.current = setTimeout(() => {
      console.log('Attempting to reconnect...');
      connect();
    }, retryInterval);
  }, [connect, retryInterval]);

  // Функция для отправки pong в ответ на ping
  const sendPong = useCallback((timestamp) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({
        type: 'pong',
        timestamp: timestamp
      }));
    }
  }, []);

  // Функция для обработки обновлений ресурсов
  const handleResourceUpdate = useCallback((data) => {
    try {
      // Проверяем наличие необходимых данных
      if (!data || typeof data !== 'object') {
        console.error('Invalid update data', data);
        return;
      }

      const eventType = data.eventType || '';
      const resourceType = data.resourceType || '';
      const resource = data.resource || null;

      if (!resource || !resourceType) {
        console.error('Invalid resource update message, missing resource or type', data);
        return;
      }

      // Адаптируем логирование для разных типов ресурсов
      // if (resourceType === 'namespaces') {
      //   console.log(`Received ${eventType} event for ${resourceType}/${resource.name}`);
      // } else {
      //   console.log(`Received ${eventType} event for ${resourceType}/${resource.namespace || 'global'}/${resource.name}`);
      // }

      // Обновляем состояние ресурсов
      setResources(prevResources => {
        try {
          // Копируем предыдущее состояние
          const newResources = {...prevResources};

          // Определяем ключ хранения ресурса
          let typeKey = resourceType;

          // Для deployments и statefulsets используем соответствующие массивы и общий массив controllers
          if (resourceType === 'deployments' || resourceType === 'statefulsets') {
            // Сохраняем в специфическом массиве для типа
            if (resourceType === 'deployments') {
              newResources.deployments = [...prevResources.deployments || []];
              typeKey = 'deployments';
            } else {
              newResources.statefulsets = [...prevResources.statefulsets || []];
              typeKey = 'statefulsets';
            }

            // Также добавляем информацию о типе контроллера
            resource.controller_type = resourceType === 'deployments' ? 'deployment' : 'statefulset';

            // После обработки события в специфическом массиве, обновляем общий массив controllers
            setTimeout(() => {
              // Используем setTimeout чтобы не блокировать текущий render
              setResources(prevState => {
                // Комбинируем deployments и statefulsets в controllers
                const allControllers = [
                  ...(prevState.deployments || []),
                  ...(prevState.statefulsets || [])
                ];

                console.log(`Combined controllers: ${allControllers.length} (${prevState.deployments?.length || 0} deployments + ${prevState.statefulsets?.length || 0} statefulsets)`);

                return {
                  ...prevState,
                  controllers: allControllers
                };
              });
            }, 0);
          }

          // Для namespaces проверяем наличие всех необходимых полей
          if (resourceType === 'namespaces' && !resource.status) {
            // Добавляем статус, если его нет
            resource.status = resource.phase || 'Active';
          }

          // Проверяем, что у нас есть массив для данного типа ресурсов
          if (!Array.isArray(newResources[typeKey])) {
            newResources[typeKey] = [];
          }

          // Копируем текущие ресурсы данного типа
          const currentResources = [...newResources[typeKey]];

          // Ищем индекс существующего ресурса (по-разному для разных типов ресурсов)
          let index = -1;
          if (resourceType === 'namespaces') {
            // Для namespaces ищем только по имени, так как у них нет namespace
            index = currentResources.findIndex(item =>
              item && item.name === resource.name
            );
          } else {
            // Для остальных ресурсов ищем по namespace и имени
            index = currentResources.findIndex(item =>
              item && item.namespace === resource.namespace && item.name === resource.name
            );
          }

          // Добавляем детальное логирование для ресурсов
          if (resourceType === 'namespaces' || resourceType === 'deployments' || resourceType === 'statefulsets') {
            const resourceName = resource.name || 'unknown';
            const resourceNamespace = resource.namespace || 'global';
            // console.log(`WebSocket event ${eventType} for ${resourceType}/${resourceNamespace}/${resourceName}`);
          }

          // Обрабатываем разные типы событий
          if (eventType === 'ADDED' || eventType === 'MODIFIED' || eventType === 'INITIAL') {
            if (index !== -1) {
              // Обновляем существующий ресурс
              currentResources[index] = resource;
              // console.log(`Updated existing ${resourceType} resource at index ${index}`);
            } else {
              // Добавляем новый ресурс
              currentResources.push(resource);
              // console.log(`Added new ${resourceType} resource, total: ${currentResources.length}`);
            }
          }
          else if (eventType === 'DELETED') {
            if (index !== -1) {
              // Удаляем ресурс
              currentResources.splice(index, 1);
              console.log(`Removed ${resourceType} resource at index ${index}`);
            }
          }
          else {
            console.warn(`Unknown event type: ${eventType}`);
          }

          // Возвращаем обновленное состояние
          newResources[typeKey] = currentResources;
          // console.log(`Updated resources.${typeKey}: now contains ${currentResources.length} items`);
          return newResources;
        } catch (err) {
          console.error('Error updating resources state:', err);
          return prevResources; // Возвращаем предыдущее состояние в случае ошибки
        }
      });
    } catch (err) {
      console.error('Error in handleResourceUpdate:', err);
    }
  }, []);

  // Функция для подписки на конкретный тип ресурса
  const subscribe = useCallback((resourceType, namespace = null) => {
    try {
      // Проверяем валидность входных параметров
      if (!resourceType || typeof resourceType !== 'string') {
        console.error('Invalid resourceType provided to subscribe:', resourceType);
        return false;
      }

      // Проверяем состояние соединения
      if (!socketRef.current) {
        console.error('Cannot subscribe: WebSocket not initialized');
        return false;
      }

      if (socketRef.current.readyState !== WebSocket.OPEN) {
        console.error('Cannot subscribe: WebSocket not connected');
        return false;
      }

      // Формируем сообщение подписки
      const subscriptionMessage = {
        type: 'subscribe',
        resourceType: resourceType
      };

      // Добавляем namespace, если он указан
      if (namespace && typeof namespace === 'string') {
        subscriptionMessage.namespace = namespace;
      }

      try {
        // Добавляем подробное логирование
        console.log(`Sending subscription request to WebSocket:`, subscriptionMessage);

        // Отправляем запрос на подписку
        socketRef.current.send(JSON.stringify(subscriptionMessage));

        // Сохраняем подписку
        const key = resourceType;
        subscriptionsRef.current.set(key, namespace);

        // Выводим текущие подписки
        console.log(`Subscribed to ${resourceType} in namespace ${namespace || 'all'}`);
        console.log(`Current active subscriptions:`,
          Array.from(subscriptionsRef.current.entries())
            .map(([key, ns]) => `${key}:${ns || 'all'}`)
            .join(', ')
        );
        return true;
      } catch (err) {
        console.error('Error subscribing to resource:', err);
        return false;
      }
    } catch (err) {
      console.error('Unexpected error in subscribe function:', err);
      return false;
    }
  }, []);

  // Функция для отмены подписки
  const unsubscribe = useCallback((resourceType, namespace = null) => {
    try {
      // Проверяем валидность входных параметров
      if (!resourceType || typeof resourceType !== 'string') {
        console.error('Invalid resourceType provided to unsubscribe:', resourceType);
        return false;
      }

      // Проверяем состояние соединения
      if (!socketRef.current) {
        console.error('Cannot unsubscribe: WebSocket not initialized');
        return false;
      }

      if (socketRef.current.readyState !== WebSocket.OPEN) {
        console.error('Cannot unsubscribe: WebSocket not connected');
        return false;
      }

      // Формируем сообщение отписки
      const unsubscriptionMessage = {
        type: 'unsubscribe',
        resourceType: resourceType
      };

      // Добавляем namespace, если он указан
      if (namespace && typeof namespace === 'string') {
        unsubscriptionMessage.namespace = namespace;
      }

      try {
        // Отправляем запрос на отписку
        socketRef.current.send(JSON.stringify(unsubscriptionMessage));

        // Удаляем подписку
        const key = resourceType;
        subscriptionsRef.current.delete(key);

        console.log(`Unsubscribed from ${resourceType} in namespace ${namespace || 'all'}`);
        return true;
      } catch (err) {
        console.error('Error unsubscribing from resource:', err);
        return false;
      }
    } catch (err) {
      console.error('Unexpected error in unsubscribe function:', err);
      return false;
    }
  }, []);

  // Функция для закрытия соединения
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (socketRef.current) {
      try {
        socketRef.current.close(1000, 'Normal closure');
        console.log('WebSocket connection closed manually');
      } catch (err) {
        console.error('Error closing WebSocket connection:', err);
      }
      socketRef.current = null;
    }

    setIsConnected(false);
    setIsConnecting(false);
  }, []);

  // Подключаемся при монтировании компонента
  useEffect(() => {
    connect();

    // Отключаемся при размонтировании
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  // Возвращаем API для работы с WebSocket
  return {
    isConnected,
    isConnecting,
    lastError,
    resources,
    connect,
    disconnect,
    subscribe,
    unsubscribe,
  };
}
