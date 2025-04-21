// src/components/ProjectDashboard.jsx
import { useEffect, useCallback, useState } from 'react';
import useK8sApi from '../hooks/useK8sApi';
import useWebSocket from '../hooks/useWebSocket';
import Filters from './Filters';
import DeploymentCard from './DeploymentCard';
import DeploymentDetails from './DeploymentDetails';
import Loading from './Loading';

/**
 * Компонент дашборда проектов с поддержкой WebSocket
 */
export default function ProjectDashboard() {
  const {
    namespaces,
    fetchNamespaces,
    handleClearCache,
  } = useK8sApi({ forNamespaceDashboard: false });

  // Состояние для режима фокуса (выделение одного контроллера)
  const [focusedController, setFocusedController] = useState(null);

  // Состояние для модального окна с деталями контроллера
  const [selectedController, setSelectedController] = useState(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);

  // Состояние для выбранного неймспейса и индикации загрузки
  const [selectedNamespace, setSelectedNamespace] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Состояние для контроллеров (statefulsets + deployments)
  const [controllers, setControllers] = useState([]);

  // Используем новый хук для работы с WebSocket
  const {
    isConnected,
    isConnecting,
    lastError,
    resources,
    connect,
    subscribe,
    unsubscribe
  } = useWebSocket({
    onConnect: () => {
      console.log('WebSocket connected, subscribing to resources...');
      setError(null);
      // Подписываемся на необходимые ресурсы при подключении
      if (typeof subscribe === 'function') {
        subscribe('namespaces');
        subscribe('deployments', selectedNamespace || null);
        subscribe('statefulsets', selectedNamespace || null);
      }
      setIsLoading(false);
    },
    onDisconnect: () => {
      console.log('WebSocket disconnected');
      setIsLoading(true);
    },
    onError: (err) => {
      console.error('WebSocket error:', err);
      setError('Error connecting to WebSocket: ' + (err?.message || 'Unknown error'));
      setIsLoading(false);
    }
  });

  // Обработка обновлений ресурсов
  useEffect(() => {
    if (resources && resources.controllers) {
      setControllers(resources.controllers);
    }
  }, [resources.controllers]);

  // Отфильтрованные контроллеры в зависимости от выбранного неймспейса
  const filteredControllers = selectedNamespace
    ? controllers.filter(controller => controller && controller.namespace === selectedNamespace)
    : controllers;

  // Первоначальная загрузка данных через REST API
  useEffect(() => {
    fetchNamespaces();
  }, [fetchNamespaces]);

  // Автоматический выбор первого неймспейса по алфавиту
  useEffect(() => {
    if (namespaces && namespaces.length > 0 && selectedNamespace === '') {
      try {
        const sorted = [...namespaces].sort((a, b) => a.name.localeCompare(b.name));
        setSelectedNamespace(sorted[0].name);
      } catch (error) {
        console.error('Error selecting first namespace:', error);
      }
    }
  }, [namespaces, selectedNamespace]);

  // Изменение подписки при смене неймспейса
  useEffect(() => {
    if (isConnected && typeof subscribe === 'function') {
      console.log('Resubscribing to controllers for namespace:', selectedNamespace || 'all');
      // Переподписываемся на deployments и statefulsets с новым неймспейсом
      subscribe('deployments', selectedNamespace || null);
      subscribe('statefulsets', selectedNamespace || null);
    }
  }, [isConnected, selectedNamespace, subscribe]);

  // Обработчик изменения выбранного неймспейса
  const handleNamespaceChange = useCallback((namespace) => {
    setSelectedNamespace(namespace);
  }, []);

  // Обработчик фокуса на контроллере
  const handleControllerFocus = useCallback((controller) => {
    if (focusedController === controller.name) {
      setFocusedController(null); // Снимаем фокус при повторном клике
    } else {
      setFocusedController(controller.name);
    }
  }, [focusedController]);

  // Обработчик клика на контроллер для открытия деталей
  const handleOpenDetails = useCallback((controller) => {
    setSelectedController(controller);
    setIsDetailsOpen(true);
  }, []);

  // Обработчик закрытия деталей контроллера
  const handleCloseDetails = useCallback(() => {
    setIsDetailsOpen(false);
  }, []);

  // Обработчик обновления данных (переподключение WebSocket)
  const handleRefresh = useCallback(() => {
    setIsLoading(true);
    // Переподключаемся к WebSocket
    if (!isConnected && typeof connect === 'function') {
      connect();
    } else if (typeof subscribe === 'function') {
      // Переподписываемся на все ресурсы
      subscribe('namespaces');
      subscribe('deployments', selectedNamespace || null);
      subscribe('statefulsets', selectedNamespace || null);
      setIsLoading(false);
    }
  }, [isConnected, connect, subscribe, selectedNamespace]);

  // Если идет загрузка и еще нет данных, показываем индикатор загрузки
  if (isLoading && filteredControllers.length === 0) {
    return (
      <div className="p-2 w-full overflow-x-hidden">
        <Loading text="Loading controllers..." />
      </div>
    );
  }

  // Если есть ошибка и нет данных, показываем сообщение об ошибке
  if ((error || lastError) && filteredControllers.length === 0) {
    const errorMessage = error || lastError;
    return (
      <div className="p-2 w-full overflow-x-hidden">
        <div className="bg-red-50 dark:bg-red-900/20 p-4 rounded-lg text-red-700 dark:text-red-400">
          <h3 className="text-lg font-medium mb-2">Error</h3>
          <p>{errorMessage}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-2 w-full overflow-x-hidden">
      <div className="mb-3">
        <h1 className="text-xl font-bold text-gray-800 dark:text-white mb-1">Project Status</h1>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Monitor your controllers across namespaces and clusters in real-time.
        </p>
      </div>

      <Filters
        namespaces={namespaces.length > 0 ? namespaces : resources.namespaces || []}
        selectedNamespace={selectedNamespace}
        onNamespaceChange={handleNamespaceChange}
        onRefresh={handleRefresh}
        isLoading={isLoading || isConnecting}
        isConnected={isConnected}
      />

      {/* Статус WebSocket соединения */}
      <div className={`mb-3 p-2 text-sm rounded-lg ${isConnected ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400' : 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-400'}`}>
        <div className="flex items-center">
          <span className={`inline-block w-2 h-2 rounded-full mr-2 ${isConnected ? 'bg-green-500' : 'bg-yellow-500'}`}></span>
          <span>
            {isConnected 
              ? 'WebSocket connected - receiving real-time updates' 
              : (isConnecting ? 'Connecting to WebSocket...' : 'WebSocket disconnected - data may be stale')}
          </span>
        </div>
      </div>

      {/* Сетка контроллеров */}
      {filteredControllers && filteredControllers.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-6 gap-3 overflow-x-hidden">
          {filteredControllers.map((controller) => (
            controller && (
              <div
                key={`${controller.namespace}-${controller.name}`}
                className={focusedController && focusedController !== controller.name ? 'opacity-40 hover:opacity-70 transition-opacity' : ''}
              >
                <div className="relative">
                  <DeploymentCard
                    deployment={controller}
                    onClick={() => handleOpenDetails(controller)}
                  />
                </div>
              </div>
            )
          ))}
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm text-center">
          <svg
            className="w-12 h-12 text-gray-400 dark:text-gray-500 mx-auto mb-3"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
            ></path>
          </svg>
          <h3 className="text-lg font-medium text-gray-700 dark:text-gray-300 mb-2">No controllers found</h3>
          <p className="text-gray-500 dark:text-gray-400">
            There are no controllers in the selected namespace.
          </p>
        </div>
      )}

      {/* Информация о подключении и кнопки управления */}
      <div className="mt-3 flex flex-col sm:flex-row justify-between items-center text-xs text-gray-500 dark:text-gray-400 bg-white dark:bg-gray-800 p-2 rounded-lg shadow-sm">
        <div className="mb-2 sm:mb-0">
          <span>WebSocket real-time updates</span>
          <span className="mx-2">•</span>
          <span>Last update: {new Date().toLocaleTimeString()}</span>
        </div>
        <div className="flex items-center">
          <button
            onClick={handleClearCache}
            className="inline-flex items-center px-2 py-1 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 rounded hover:bg-blue-200 dark:hover:bg-blue-800 transition-colors mr-2"
          >
            <svg
              className="w-3 h-3 mr-1"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            Clear cache
          </button>
          {!isConnected && (
            <button
              onClick={handleRefresh}
              className="inline-flex items-center px-2 py-1 bg-yellow-100 dark:bg-yellow-900 text-yellow-700 dark:text-yellow-300 rounded hover:bg-yellow-200 dark:hover:bg-yellow-800 transition-colors"
            >
              <svg
                className={`w-3 h-3 mr-1 ${isConnecting ? 'animate-spin' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                ></path>
              </svg>
              Reconnect
            </button>
          )}
        </div>
      </div>

      {/* Модальное окно с деталями контроллера - рендерим только когда открыто */}
      {isDetailsOpen && (
        <DeploymentDetails
          deployment={selectedController}
          isOpen={isDetailsOpen}
          onClose={handleCloseDetails}
        />
      )}
    </div>
  );
}