// frontend/src/context/WebSocketContext.jsx
import React, { createContext, useContext, useState, useEffect, useReducer } from 'react';
import useWebSocket from '../hooks/useWebSocket';

// Создание контекста
const WebSocketContext = createContext(null);

// Редьюсер для управления состоянием ресурсов
function resourceReducer(state, action) {
  switch (action.type) {
    case 'INITIALIZE':
      return {
        ...state,
        [action.resourceType]: action.resources
      };
    case 'ADDED':
    case 'MODIFIED':
      const resources = state[action.resourceType] || [];
      const index = resources.findIndex(r =>
        r.name === action.resource.name &&
        r.namespace === action.resource.namespace
      );

      if (index >= 0) {
        // Обновление существующего ресурса
        const updatedResources = [...resources];
        updatedResources[index] = action.resource;
        return {
          ...state,
          [action.resourceType]: updatedResources
        };
      } else {
        // Добавление нового ресурса
        return {
          ...state,
          [action.resourceType]: [...resources, action.resource]
        };
      }
    case 'DELETED':
      return {
        ...state,
        [action.resourceType]: (state[action.resourceType] || []).filter(r =>
          r.name !== action.resource.name ||
          r.namespace !== action.resource.namespace
        )
      };
    default:
      return state;
  }
}

// Провайдер WebSocket
export function WebSocketProvider({ children }) {
  const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/k8s/ws`;

  // Состояние соединения
  const [lastMessage, setLastMessage] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');

  // Состояние ресурсов
  const [resources, dispatch] = useReducer(resourceReducer, {
    deployments: [],
    pods: [],
    statefulsets: [],
    namespaces: []
  });

  // Обработчик сообщений WebSocket
  const handleMessage = (message) => {
    setLastMessage(message);

    // Обработка различных типов сообщений
    switch (message.type) {
      case 'connection':
        setConnectionStatus(message.status);
        break;
      case 'resource':
        // Обработка событий ресурсов
        dispatch({
          type: message.action,
          resourceType: message.resource_type,
          resource: message.resource
        });
        break;
      case 'error':
        console.error('WebSocket error:', message.message);
        break;
      default:
        // Прочие сообщения
        break;
    }
  };

  // Инициализация WebSocket
  // Инициализация WebSocket с задержкой подписок
  const ws = useWebSocket(wsUrl, {
    autoReconnect: true,
    bufferMessages: true,
    onMessage: handleMessage,
    // Убираем автоматические подписки, будем подписываться после успешного подключения
  });
  
  // Подписываемся на ресурсы только после успешного подключения
  // ВРЕМЕННО ОТКЛЮЧЕНО для отладки
  /*
  useEffect(() => {
    if (ws.status === 'open') {
      // Небольшая задержка перед подпиской для уверенности, что соединение стабильно
      const subscribeTimeout = setTimeout(() => {
        console.log('WebSocket: Отправка подписок после установки соединения');
        
        // Подписка на ресурсы
        [
          { resourceType: 'deployments' },
          { resourceType: 'pods' },
          { resourceType: 'statefulsets' },
          { resourceType: 'namespaces' }
        ].forEach(subscription => {
          ws.send({
            type: 'subscribe',
            resource_type: subscription.resourceType,
            namespace: subscription.namespace || null
          });
        });
      }, 500); // Полсекунды задержки
      
      return () => clearTimeout(subscribeTimeout);
    }
  }, [ws.status, ws.send]);
  */

  // Инициализация данных из REST API при первом подключении
  useEffect(() => {
    if (ws.status === 'open' && connectionStatus === 'connected') {
      // Здесь можно загрузить начальные данные из REST API
      // Это позволит быстрее отобразить интерфейс, не дожидаясь всех событий от WebSocket
      const fetchInitialData = async () => {
        try {
          // Пример загрузки деплойментов
          const deploymentsResponse = await fetch('/api/k8s/deployments');
          const deploymentsData = await deploymentsResponse.json();

          dispatch({
            type: 'INITIALIZE',
            resourceType: 'deployments',
            resources: deploymentsData.items || []
          });

          // Загрузка namespace
          const namespacesResponse = await fetch('/api/k8s/namespaces');
          const namespacesData = await namespacesResponse.json();

          dispatch({
            type: 'INITIALIZE',
            resourceType: 'namespaces',
            resources: namespacesData.items || []
          });

          // Загрузка подов
          const podsResponse = await fetch('/api/k8s/pods');
          const podsData = await podsResponse.json();

          dispatch({
            type: 'INITIALIZE',
            resourceType: 'pods',
            resources: podsData.items || []
          });

        } catch (error) {
          console.error('Ошибка при загрузке начальных данных:', error);
        }
      };

      fetchInitialData();
    }
  }, [ws.status, connectionStatus]);

  // Значение контекста
  const value = {
    // Состояние соединения
    status: ws.status,
    error: ws.error,
    connectionStatus,

    // Ресурсы
    deployments: resources.deployments || [],
    pods: resources.pods || [],
    statefulsets: resources.statefulsets || [],
    namespaces: resources.namespaces || [],

    // Методы
    subscribe: (resourceType, namespace) => {
      ws.send({
        type: 'subscribe',
        resource_type: resourceType,
        namespace: namespace || null
      });
    },

    unsubscribe: (resourceType, namespace) => {
      ws.send({
        type: 'unsubscribe',
        resource_type: resourceType,
        namespace: namespace || null
      });
    },

    reconnect: ws.reconnect,
    close: ws.close
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
}

// Хук для использования контекста
export function useWebSocketContext() {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocketContext должен использоваться внутри WebSocketProvider');
  }
  return context;
}
