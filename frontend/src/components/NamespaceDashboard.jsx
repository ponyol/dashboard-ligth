// src/components/NamespaceDashboard.jsx
import { useEffect, useCallback, useState } from 'react';
import useK8sApi from '../hooks/useK8sApi';
import useInterval from '../hooks/useInterval';
import Filters from './Filters';
import NamespaceCard from './NamespaceCard';
import Loading from './Loading';

/**
 * Компонент дашборда статуса неймспейсов
 */
export default function NamespaceDashboard() {
  const {
    namespaces,
    controllers,
    isLoading,
    error,
    fetchNamespaces,
    fetchControllers,
  } = useK8sApi({ forNamespaceDashboard: true });

  // Удалили состояние для режима фокуса, так как карточки больше не кликабельны
  
  // Интервал обновления данных в миллисекундах (15 секунд)
  const refreshInterval = 15000;

  // Первоначальная загрузка данных
  useEffect(() => {
    const loadData = async () => {
      await fetchNamespaces();
      await fetchControllers();
    };
    
    loadData();
  }, [fetchNamespaces, fetchControllers]);

  // Периодическое обновление данных
  useInterval(() => {
    fetchNamespaces();
    fetchControllers();
  }, refreshInterval);

  // Обработчик обновления данных
  const handleRefresh = useCallback(() => {
    fetchNamespaces();
    fetchControllers();
  }, [fetchNamespaces, fetchControllers]);

  // Удалили обработчик фокуса на неймспейсе, так как карточки больше не кликабельны

  // Расчет количества деплойментов и подов для каждого неймспейса
  const getNamespaceStats = useCallback(() => {
    if (!namespaces || namespaces.length === 0) {
      console.log("No namespaces available for stats calculation");
      return [];
    }
    
    console.log(`Calculating stats for ${namespaces.length} namespaces`);
    console.log(`Have ${controllers?.length || 0} controllers available for stats calculation`);
    
    const stats = {};
    
    // Инициализация статистики для всех неймспейсов
    namespaces.forEach(ns => {
      stats[ns.name] = { 
        namespace: ns,
        deploymentCount: 0, 
        podCount: 0,
        controllers: []
      };
    });
    
    // Проверяем, что controllers определен
    if (controllers && controllers.length > 0) {
      // Логируем примеры контроллеров для проверки структуры данных
      console.log("Sample controller data:", controllers[0]);
      
      // Сначала соберем данные по контроллерам для каждого неймспейса
      controllers.forEach(controller => {
        if (controller && controller.namespace && stats[controller.namespace]) {
          stats[controller.namespace].deploymentCount += 1;
          stats[controller.namespace].controllers.push(controller);
        } else {
          console.log(`Skipping controller with invalid namespace: ${controller?.namespace}`);
        }
      });
      
      // Теперь считаем поды для каждого неймспейса
      Object.keys(stats).forEach(nsName => {
        const nsStats = stats[nsName];
        console.log(`Processing namespace ${nsName} with ${nsStats.controllers.length} controllers`);
        
        // Считаем поды в каждом контроллере
        nsStats.controllers.forEach(controller => {
          if (controller.replicas) {
            // Используем значение ready реплик как количество работающих подов
            const readyReplicas = controller.replicas.ready || 0;
            nsStats.podCount += readyReplicas;
            console.log(`  - Controller ${controller.name}: added ${readyReplicas} pods to count`);
            
            // Также можно проверить поды напрямую, если они доступны
            if (controller.pods && Array.isArray(controller.pods)) {
              // Логирование для отладки
              console.log(`  - Controller ${controller.name} in ${controller.namespace} has ${controller.pods.length} pods directly`);
            }
          } else {
            console.log(`  - Controller ${controller.name} has no replicas information`);
          }
        });
        
        // Убедимся, что подсчет корректный (не отрицательный)
        nsStats.podCount = Math.max(0, nsStats.podCount);
        console.log(`Final counts for ${nsName}: ${nsStats.deploymentCount} deployments, ${nsStats.podCount} pods`);
      });
    } else {
      console.warn("No controllers available to calculate namespace stats");
    }
    
    console.log("Final namespace stats:", stats);
    
    return Object.values(stats);
  }, [namespaces, controllers]);

  // Расчет статистики по неймспейсам
  const namespaceStats = getNamespaceStats();

  // Удалили функцию для определения CSS класса карточки неймспейса, так как режим фокуса больше не используется

  // Если идет загрузка и еще нет данных, показываем индикатор загрузки
  if (isLoading && namespaces.length === 0) {
    return (
      <div className="p-2 w-full overflow-x-hidden">
        <Loading text="Loading namespace data..." />
      </div>
    );
  }

  // Если есть ошибка и нет данных, показываем сообщение об ошибке
  if (error && namespaces.length === 0) {
    return (
      <div className="p-2 w-full overflow-x-hidden">
        <div className="bg-red-50 dark:bg-red-900/20 p-4 rounded-lg text-red-700 dark:text-red-400">
          <h3 className="text-lg font-medium mb-2">Error</h3>
          <p>{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-2 w-full overflow-x-hidden">
      <div className="mb-3">
        <h1 className="text-xl font-bold text-gray-800 dark:text-white mb-1">Namespace Status</h1>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Overview of your namespaces with deployment and pod counts.
        </p>
      </div>

      {/* Кнопка обновления данных */}
      <div className="mb-4 flex justify-end">
        <button
          onClick={handleRefresh}
          className="flex items-center px-3 py-1.5 bg-blue-500 dark:bg-blue-600 text-white dark:text-white rounded hover:bg-blue-600 dark:hover:bg-blue-700 transition-colors"
          disabled={isLoading}
        >
          <svg
            className={`w-4 h-4 mr-1.5 ${isLoading ? 'animate-spin' : ''}`}
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
          {isLoading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {/* Сетка неймспейсов */}
      {namespaceStats.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-6 gap-3 overflow-x-hidden">
          {namespaceStats.map((stats) => (
            <div
              key={stats.namespace.name}
            >
              <NamespaceCard
                namespace={stats.namespace}
                deploymentCount={stats.deploymentCount}
                podCount={stats.podCount}
              />
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
          <h3 className="text-lg font-medium text-gray-700 dark:text-gray-300 mb-2">No namespaces found</h3>
          <p className="text-gray-500 dark:text-gray-400">
            There are no namespaces available in the cluster.
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
        <div>
          <button
            onClick={handleRefresh}
            className="inline-flex items-center px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
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
    </div>
  );
}