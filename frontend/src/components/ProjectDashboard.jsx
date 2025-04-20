// src/components/ProjectDashboard.jsx
import { useEffect, useCallback, useState } from 'react';
import useK8sApi from '../hooks/useK8sApi';
import useInterval from '../hooks/useInterval';
import Filters from './Filters';
import DeploymentCard from './DeploymentCard';
import DeploymentDetails from './DeploymentDetails';
import Loading from './Loading';

/**
 * Компонент дашборда проектов
 */
export default function ProjectDashboard() {
  const {
    namespaces,
    controllers,
    selectedNamespace,
    isLoading,
    error,
    fetchNamespaces,
    fetchControllers,
    handleNamespaceChange,
    handleClearCache,
  } = useK8sApi({ forNamespaceDashboard: false });

  // Состояние для режима фокуса (выделение одного контроллера)
  const [focusedController, setFocusedController] = useState(null);

  // Состояние для модального окна с деталями контроллера
  const [selectedController, setSelectedController] = useState(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);

  // Интервал обновления данных в миллисекундах (15 секунд)
  const refreshInterval = 15000;

  // Первоначальная загрузка данных
  useEffect(() => {
    fetchNamespaces();
  }, [fetchNamespaces]);

  // Загрузка контроллеров при изменении выбранного неймспейса
  useEffect(() => {
    fetchControllers();
  }, [fetchControllers, selectedNamespace]);

  // Периодическое обновление данных
  useInterval(() => {
    fetchControllers();
  }, refreshInterval);

  // Обработчик обновления данных
  const handleRefresh = useCallback(() => {
    fetchNamespaces();
    fetchControllers();
  }, [fetchNamespaces, fetchControllers]);

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

  // Если идет загрузка и еще нет данных, показываем индикатор загрузки
  if (isLoading && controllers.length === 0) {
    return (
      <div className="p-2 w-full overflow-x-hidden">
        <Loading text="Loading controllers..." />
      </div>
    );
  }

  // Если есть ошибка и нет данных, показываем сообщение об ошибке
  if (error && controllers.length === 0) {
    return (
      <div className="p-2 w-full overflow-x-hidden">
        <div className="bg-red-50 dark:bg-red-900/20 p-4 rounded-lg text-red-700 dark:text-red-400">
          <h3 className="text-lg font-medium mb-2">Error</h3>
          <p>{error}</p>
        </div>
      </div>
    );
  }

  // Функция для определения CSS класса карточки контроллера в зависимости от режима фокуса
  const getControllerCardClass = (controller) => {
    if (focusedController === null) {
      return '';
    }
    return focusedController === controller.name ? '' : 'opacity-40 hover:opacity-70 transition-opacity';
  };

  return (
    <div className="p-2 w-full overflow-x-hidden">
      <div className="mb-3">
        <h1 className="text-xl font-bold text-gray-800 dark:text-white mb-1">Project Status</h1>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Monitor your controllers across namespaces and clusters in real-time.
        </p>
      </div>

      <Filters
        namespaces={namespaces}
        selectedNamespace={selectedNamespace}
        onNamespaceChange={handleNamespaceChange}
        onRefresh={handleRefresh}
        isLoading={isLoading}
      />

      {/* Сетка контроллеров */}
      {controllers.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-6 gap-3 overflow-x-hidden">
          {controllers.map((controller) => (
            <div
              key={`${controller.namespace}-${controller.name}`}
              className={getControllerCardClass(controller)}
            >
              <div className="relative">
                <DeploymentCard
                  deployment={controller}
                  onClick={() => handleOpenDetails(controller)}
                />
              </div>
            </div>
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

      {/* Информация об обновлении и кнопки управления */}
      <div className="mt-3 flex flex-col sm:flex-row justify-between items-center text-xs text-gray-500 dark:text-gray-400 bg-white dark:bg-gray-800 p-2 rounded-lg shadow-sm">
        <div className="mb-2 sm:mb-0">
          <span>Auto-refresh every {refreshInterval / 1000} seconds</span>
          <span className="mx-2">•</span>
          <span>Last update: {new Date().toLocaleTimeString()}</span>
        </div>
        <div className="flex items-center">
          <button
            onClick={handleClearCache}
            className="inline-flex items-center px-2 py-1 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 rounded hover:bg-blue-200 dark:hover:bg-blue-800 transition-colors"
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
          <button
            onClick={handleRefresh}
            className="inline-flex items-center px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors ml-2"
          >
            <svg
              className={`w-3 h-3 mr-1 ${isLoading ? 'animate-spin' : ''}`}
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
            Refresh now
          </button>
        </div>
      </div>

      {/* Модальное окно с деталями контроллера */}
      <DeploymentDetails
        deployment={selectedController}
        isOpen={isDetailsOpen}
        onClose={handleCloseDetails}
      />
    </div>
  );
}