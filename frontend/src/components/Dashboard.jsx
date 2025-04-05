// src/components/Dashboard.jsx
import { useEffect, useCallback, useState } from 'react';
import useK8sApi from '../hooks/useK8sApi';
import useInterval from '../hooks/useInterval';
import Filters from './Filters';
import DeploymentCard from './DeploymentCard';
import DeploymentDetails from './DeploymentDetails';
import Loading from './Loading';

/**
 * Основной компонент дашборда
 */
export default function Dashboard() {
  const {
    namespaces,
    deployments,
    selectedNamespace,
    isLoading,
    error,
    fetchNamespaces,
    fetchDeployments,
    handleNamespaceChange,
    handleClearCache,
  } = useK8sApi();

  // Состояние для режима фокуса (выделение одного деплоймента)
  const [focusedDeployment, setFocusedDeployment] = useState(null);

  // Состояние для модального окна с деталями деплоймента
  const [selectedDeployment, setSelectedDeployment] = useState(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);

  // Интервал обновления данных в миллисекундах (15 секунд)
  const refreshInterval = 15000;

  // Первоначальная загрузка данных
  useEffect(() => {
    fetchNamespaces();
  }, [fetchNamespaces]);

  // Загрузка деплойментов при изменении выбранного неймспейса
  useEffect(() => {
    fetchDeployments();
  }, [fetchDeployments, selectedNamespace]);

  // Периодическое обновление данных
  useInterval(() => {
    fetchDeployments();
  }, refreshInterval);

  // Обработчик обновления данных
  const handleRefresh = useCallback(() => {
    fetchNamespaces();
    fetchDeployments();
  }, [fetchNamespaces, fetchDeployments]);

  // Обработчик фокуса на деплойменте
  const handleDeploymentFocus = useCallback((deployment) => {
    if (focusedDeployment === deployment.name) {
      setFocusedDeployment(null); // Снимаем фокус при повторном клике
    } else {
      setFocusedDeployment(deployment.name);
    }
  }, [focusedDeployment]);

  // Обработчик клика на деплоймент для открытия деталей
  const handleOpenDetails = useCallback((deployment) => {
    setSelectedDeployment(deployment);
    setIsDetailsOpen(true);
  }, []);

  // Обработчик закрытия деталей деплоймента
  const handleCloseDetails = useCallback(() => {
    setIsDetailsOpen(false);
  }, []);

  // Если идет загрузка и еще нет данных, показываем индикатор загрузки
  if (isLoading && deployments.length === 0) {
    return (
      <div className="p-6">
        <Loading text="Loading deployments..." />
      </div>
    );
  }

  // Если есть ошибка и нет данных, показываем сообщение об ошибке
  if (error && deployments.length === 0) {
    return (
      <div className="p-6">
        <div className="bg-red-50 dark:bg-red-900/20 p-4 rounded-lg text-red-700 dark:text-red-400">
          <h3 className="text-lg font-medium mb-2">Error</h3>
          <p>{error}</p>
        </div>
      </div>
    );
  }

  // Функция для определения CSS класса карточки деплоймента в зависимости от режима фокуса
  const getDeploymentCardClass = (deployment) => {
    if (focusedDeployment === null) {
      return '';
    }
    return focusedDeployment === deployment.name ? '' : 'opacity-40 hover:opacity-70 transition-opacity';
  };

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-800 dark:text-white mb-2">Deployments Status</h1>
        <p className="text-gray-600 dark:text-gray-400">
          Monitor your deployments across namespaces and clusters in real-time.
        </p>
      </div>

      <Filters
        namespaces={namespaces}
        selectedNamespace={selectedNamespace}
        onNamespaceChange={handleNamespaceChange}
        onRefresh={handleRefresh}
        isLoading={isLoading}
      />

      {/* Сетка деплойментов */}
      {deployments.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {deployments.map((deployment) => (
            <div
              key={`${deployment.namespace}-${deployment.name}`}
              className={getDeploymentCardClass(deployment)}
            >
              <DeploymentCard
                deployment={deployment}
                onClick={() => handleOpenDetails(deployment)}
              />
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-sm text-center">
          <svg
            className="w-16 h-16 text-gray-400 dark:text-gray-500 mx-auto mb-4"
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
          <h3 className="text-xl font-medium text-gray-700 dark:text-gray-300 mb-2">No deployments found</h3>
          <p className="text-gray-500 dark:text-gray-400">
            There are no deployments in the selected namespace.
          </p>
        </div>
      )}

      {/* Информация об обновлении и кнопки управления */}
      <div className="mt-8 flex flex-col sm:flex-row justify-between items-center text-sm text-gray-500 dark:text-gray-400 bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm">
        <div className="mb-3 sm:mb-0">
          <span>Auto-refresh every {refreshInterval / 1000} seconds</span>
          <span className="mx-2">•</span>
          <span>Last update: {new Date().toLocaleTimeString()}</span>
        </div>
        <div className="flex items-center">
          <button
            onClick={handleClearCache}
            className="inline-flex items-center px-3 py-1 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 rounded hover:bg-blue-200 dark:hover:bg-blue-800 transition-colors"
          >
            <svg
              className="w-4 h-4 mr-1"
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
            className="inline-flex items-center px-3 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors ml-2"
          >
            <svg
              className={`w-4 h-4 mr-1 ${isLoading ? 'animate-spin' : ''}`}
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

      {/* Модальное окно с деталями деплоймента */}
      <DeploymentDetails
        deployment={selectedDeployment}
        isOpen={isDetailsOpen}
        onClose={handleCloseDetails}
      />
    </div>
  );
}
