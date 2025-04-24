// frontend/src/components/WebSocketStatus.jsx
import React from 'react';
import { useWebSocketContext } from '../context/WebSocketContext';

/**
 * Компонент для отображения статуса WebSocket соединения
 */
export default function WebSocketStatus() {
  const { status, error } = useWebSocketContext();

  const getStatusColor = () => {
    switch (status) {
      case 'open':
        return {
          bg: 'bg-green-100 dark:bg-green-900/20',
          text: 'text-green-800 dark:text-green-400',
          dot: 'bg-green-500'
        };
      case 'connecting':
        return {
          bg: 'bg-yellow-100 dark:bg-yellow-900/20',
          text: 'text-yellow-800 dark:text-yellow-400',
          dot: 'bg-yellow-500'
        };
      case 'closed':
        return {
          bg: 'bg-gray-100 dark:bg-gray-900/20',
          text: 'text-gray-800 dark:text-gray-400',
          dot: 'bg-gray-500'
        };
      case 'error':
        return {
          bg: 'bg-red-100 dark:bg-red-900/20',
          text: 'text-red-800 dark:text-red-400',
          dot: 'bg-red-500'
        };
      default:
        return {
          bg: 'bg-gray-100 dark:bg-gray-900/20',
          text: 'text-gray-800 dark:text-gray-400',
          dot: 'bg-gray-500'
        };
    }
  };

  const { bg, text, dot } = getStatusColor();

  return (
    <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm ${bg} ${text}`}>
      <span className={`w-2 h-2 rounded-full mr-2 ${dot} ${
        status === 'connecting' ? 'animate-pulse' : ''
      }`}></span>
      WebSocket: {status === 'open' ? 'Connected' : status}
      {error && <span className="ml-2 text-red-600 dark:text-red-400">({error})</span>}
    </div>
  );
}
