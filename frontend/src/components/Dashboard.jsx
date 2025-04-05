// src/components/Dashboard.jsx
import { useEffect, useCallback } from 'react';
import useK8sApi from '../hooks/useK8sApi';
import useInterval from '../hooks/useInterval';
import Filters from './Filters';
import Loading from './Loading';
import StatusBadge from './StatusBadge';

/**
 * Компонент карточки деплоймента
 */
function DeploymentCard({ deployment }) {
  // Определение статусного класса по статусу деплоймента
  const getStatusClass = (status) => {
    switch (status) {
      case 'healthy': return 'border-healthy';
      case 'progressing': return 'border-progressing';
      case 'scaled_zero': return 'border-scaled-zero';
      case 'error': return 'border-error';
      default: return 'border-gray-300 dark:border-gray-600';
    }
  };

  const statusClass = getStatusClass(deployment.status);

  return (
    <div className={`bg-white dark:bg-gray-800 rounded-lg shadow-sm border-l-4 ${statusClass} transition-all duration-300 hover:shadow-md`}>
      <div className="p-4">
        <div className="flex justify-between items-start mb-2">
          <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 truncate" title={deployment.name}>
            {deployment.name}
          </h3>
          <StatusBadge status={deployment.status} type="deployment" />
        </div>

        <div className="text-sm text-gray-500 dark:text-gray-400 mb-3">
          Namespace: <span className="font-medium">{deployment.namespace}</span>
        </div>

        {deployment.replicas && (
          <div className="text-sm">
            <span className="text-gray-500 dark:text-gray-400">Replicas: </span>
            <span className="font-medium text-gray-900 dark:text-gray-100">
              {deployment.replicas.ready || 0}/{deployment.replicas.desired || 0}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

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

  // Если идет загрузка, показываем индикатор
  if (isLoading && !deployments.length) {
    return <Loading text="Loading deployments..." />;
  }

  // Если есть ошибка, показываем сообщение
  if (error && !deployments.length) {
    return (
      <div className="bg-red-50 dark:bg-red-900/20 p-4 rounded-lg text-red-700 dark:text-red-400">
        <h3 className="text-lg font-medium mb-2">Error</h3>
        <p>{error}</p>
      </div>
    );
  }

  return (
    <div className="p-6">
      <Filters
        namespaces={namespaces}
        selectedNamespace={selectedNamespace}
        onNamespaceChange={handleNamespaceChange}
        onRefresh={handleRefresh}
        isLoading={isLoading}
      />

      {/* Сетка деплойментов */}
      {deployments.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {deployments.map((deployment) => (
            <DeploymentCard
              key={`${deployment.namespace}-${deployment.name}`}
              deployment={deployment}
            />
          ))}
        </div>
      ) : (
        <div className="bg-gray-50 dark:bg-gray-800 p-6 rounded-lg text-center">
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
          <h3 className="text-lg font-medium text-gray-700 dark:text-gray-300 mb-1">No deployments found</h3>
          <p className="text-gray-500 dark:text-gray-400">
            There are no deployments in the selected namespace.
          </p>
        </div>
      )}

      {/* Отображение времени последнего обновления и кнопки очистки кэша */}
      <div className="mt-8 text-center text-sm text-gray-500 dark:text-gray-400 flex justify-center items-center">
        <span>
          Auto-refresh every {refreshInterval / 1000} seconds
        </span>
        <button
          onClick={handleClearCache}
          className="ml-4 underline hover:text-blue-600 dark:hover:text-blue-400"
        >
          Clear cache
        </button>
      </div>
    </div>
  );
}
