import { useState, useEffect, useRef, useCallback } from 'react';
import { API_CONFIG } from '../api/api';

export default function useWebSocket(options = {}) {
  const { onConnect, onDisconnect, onError, retryInterval = 5000 } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [lastError, setLastError] = useState(null);
  const [resources, setResources] = useState({
    namespaces: [],
    deployments: [],
    statefulsets: [],
    controllers: [],
    pods: []


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
  const reconnectTimeoutRef = useRef(null);

  useEffect(() => {


    handlersRef.current = {
      onConnect: onConnect || handlersRef.current.onConnect,
      onDisconnect: onDisconnect || handlersRef.current.onDisconnect,
      onError: onError || handlersRef.current.onError
    };
  }, [onConnect, onDisconnect, onError]);

  const connect = useCallback(() => {
    try {
      if (socketRef.current && (socketRef.current.readyState === WebSocket.OPEN || socketRef.current.readyState === WebSocket.CONNECTING)) {
        console.log('WebSocket already connected or connecting');
        return;
      }

      setIsConnecting(true);
      console.log(`Connecting to WebSocket at ${API_CONFIG.websocket.url}`);

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
            const messageType = data.type || '';

            if (messageType === 'resource_batch') {
                const batchResources = data.resources || [];
                const resourceType = data.resourceType;
                handleResourceBatch(resourceType, batchResources);
            } else if (messageType === 'resource') {
                handleResourceUpdate(data);
            }else if (messageType === 'error') {
                console.error('WebSocket error message:', data.message);
                setLastError(data.message);
                handlersRef.current.onError(new Error(data.message));
          }
          // else if (messageType === 'subscribed') {
          //   // Подтверждение подписки
          //   console.log(`Successfully subscribed to ${data.resourceType} in namespace ${data.namespace || 'all'}`);
          // }
          // else if (messageType === 'unsubscribed') {
          //   // Подтверждение отписки
          //   console.log(`Successfully unsubscribed from ${data.resourceType} in namespace ${data.namespace || 'all'}`);
          // }
            else if (messageType === 'ping' || messageType === 'pong') {
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

 const handleResourceBatch = useCallback((resourceType, batchResources) => {
    setResources((prevResources) => {
        const newResources = { ...prevResources };
        const typeKey = resourceType;

        if (!Array.isArray(newResources[typeKey])) {
            newResources[typeKey] = [];
        }

        const currentResources = [...newResources[typeKey]];
        for (const resource of batchResources) {
            const index = currentResources.findIndex(
                (item) =>
                    item && item.name === resource.name && (resourceType === 'namespaces' || item.namespace === resource.namespace)
            );
            if (index !== -1) {
                currentResources[index] = resource;
            } else {
                currentResources.push(resource);
            }
        }
        newResources[typeKey] = currentResources;
        return newResources;
    });
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
        socketRef.current.send(
            JSON.stringify({
                type: 'pong',
                timestamp: timestamp,
            })
        );
    }
}, []);

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

      setResources(prevResources => {
        try {

          const newResources = {...prevResources};


          let typeKey = resourceType;

          // Для deployments и statefulsets используем соответствующие массивы
          if (resourceType === 'deployments' || resourceType === 'statefulsets') {
            resource.controller_type = resourceType === 'deployments' ? 'deployment' : 'statefulset';

            let allControllers = [...(prevResources.deployments || []), ...(prevResources.statefulsets || [])];
            const controllerIndex = allControllers.findIndex(item => item.namespace === resource.namespace && item.name === resource.name);
            if (controllerIndex > -1) {
              allControllers[controllerIndex] = resource;
            } else {
              allControllers.push(resource);
            }

            newResources.controllers = allControllers;

          } else{
             newResources[typeKey] = [...(prevResources[typeKey] || [])];
           }

          if (resourceType === 'namespaces' && !resource.status) {
            resource.status = resource.phase || 'Active';
           }

          // Проверяем, что у нас есть массив для данного типа ресурсов
          if (!Array.isArray(newResources[typeKey])) {
            newResources[typeKey] = [];
          }

          // Копируем текущие ресурсы данного типа
          const currentResources = [...newResources[typeKey]];


          let index = -1;
          if (resourceType === 'namespaces') {

            index = currentResources.findIndex(item =>
              item && item.name === resource.name
            );
          } else {

            index = currentResources.findIndex(item =>
              item && item.namespace === resource.namespace && item.name === resource.name
            );
          }

          if (eventType === 'ADDED' || eventType === 'MODIFIED' || eventType === 'INITIAL') {
               handleAddedOrModified(index, currentResources, resource, resourceType)
            }
            else if (eventType === 'DELETED') {
                if (index !== -1){
                  currentResources.splice(index, 1);
                   console.log(`Removed ${resourceType} resource at index ${index}`);
                }
            }
            else {
                console.warn(`Unknown event type: ${eventType}`);
            }

           newResources[typeKey] = currentResources;
          return newResources;
        } catch (err) {
          console.error('Error updating resources state:', err);
          return prevResources;
        }
      });
    } catch (err) {
      console.error('Error in handleResourceUpdate:', err);
    }
  }, []);
 const handleAddedOrModified = useCallback((index, currentResources, resource, resourceType) => {
      try {
          if (index !== -1) {
              currentResources[index] = resource;
          } else {
              currentResources.push(resource);
          }
          return currentResources;
      } catch (err) {
          console.error('Error in handleResourceUpdate:', err);
      }
  }, []);

 const subscribe = useCallback((resourceType, namespace = null) => {
    try {
      // Проверяем валидность входных параметров
      if (!resourceType || typeof resourceType !== 'string') {
        console.error('Invalid resourceType provided to subscribe:', resourceType);
        return false;
      }

      if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
        console.error('Cannot subscribe: WebSocket not initialized or not connected');
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

 const unsubscribe = useCallback((resourceType, namespace = null) => {
    try {
         if (!resourceType || typeof resourceType !== 'string') {
                console.error('Invalid resourceType provided to unsubscribe:', resourceType);
                return false;
            }



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
       if (namespace && typeof namespace === 'string') {
                unsubscriptionMessage.namespace = namespace;
            }

      try {

        socketRef.current.send(JSON.stringify(unsubscriptionMessage));

        const key = resourceType;
        subscriptionsRef.current.delete(key);
        console.log(
            `Unsubscribed from ${resourceType} in namespace ${namespace || 'all'}`
        );
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
