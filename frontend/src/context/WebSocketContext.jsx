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
  const ws = useWebSocket(wsUrl, {
    autoReconnect: true,
    onMessage: handleMessage,
    subscriptions: [
      { resourceType: 'deployments' },
      { resourceType: 'pods' },
      { resourceType: 'statefulsets' },
      { resourceType: 'namespaces' }
    ]
  });

  // Инициализация данных из REST API при первом подключении
  useEffect(() => {
    if (ws.status === 'open' && connectionStatus === 'connected') {
      // Здесь можно загрузить начальные данные из REST API
      // Это позволит быстрее отобразить интерфейс, не дожидаясь всех событий от WebSocket
      const fetchInitialData = async () => {
        try{
            const responses = await Promise.all([
                fetch('/api/k8s/deployments'),
                fetch('/api/k8s/namespaces'),
                fetch('/api/k8s/pods'),
            ]);

            const [deploymentsData, namespacesData, podsData] = await Promise.all(
                responses.map(response => response.json())
            );

            dispatch({ type: 'INITIALIZE', resourceType: 'deployments', resources: deploymentsData.items || [] });
            dispatch({ type: 'INITIALIZE', resourceType: 'namespaces', resources: namespacesData.items || [] });
            dispatch({ type: 'INITIALIZE', resourceType: 'pods', resources: podsData.items || [] });
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
