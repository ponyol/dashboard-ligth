// src/components/NamespaceDashboard.jsx
import { useEffect, useCallback, useState, memo } from 'react';
import useK8sApi from '../hooks/useK8sApi';
import useWebSocket from '../hooks/useWebSocket'; 
import Filters from './Filters';
import NamespaceCard from './NamespaceCard';
import Loading from './Loading';

/**
 * Компонент дашборда статуса неймспейсов с поддержкой WebSocket
 */

const NamespaceTable = memo(({ namespaceStats, optimizedView }) => {
    return namespaceStats.map((stats) => (
      <div key={stats.namespace.name}>
        <NamespaceCard namespace={stats.namespace} deploymentCount={stats.deploymentCount} podCount={stats.podCount} compact={optimizedView} />
      </div>
    ))
  })


export default function NamespaceDashboard() {
  const {
    handleClearCache,
  } = useK8sApi({ forNamespaceDashboard: true });

  // Состояние для индикации загрузки и ошибок
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Состояние для отслеживания компактного режима сортировки
  const [optimizedView, setOptimizedView] = useState(false);

  // Используем новый хук для работы с WebSocket
  const {
    isConnected,
    isConnecting,
    lastError,
    resources,
    connect,
    subscribe,
  } = useWebSocket({
    onConnect: () => {
      setError(null);
      // Подписываемся на необходимые ресурсы при подключении
      subscribe('namespaces');
      subscribe('deployments');
      subscribe('statefulsets');
      subscribe('pods');
    },
    onDisconnect: () => {
      // console.log('WebSocket disconnected');
      setIsLoading(true);
    },
    onError: (err) => {
      console.error('WebSocket error:', err);
      setError('Error connecting to WebSocket: ' + (err.message || 'Unknown error'));
      setIsLoading(false);
    }
  });

  // Обработчик обновления данных (переподключение WebSocket)
  const handleRefresh = useCallback(() => {
    setIsLoading(true);
    // Переподключаемся к WebSocket
    if (!isConnected) {
      connect();
    } else {
      // Переподписываемся на все ресурсы
      subscribe('namespaces');
      subscribe('deployments');
      subscribe('statefulsets');
      subscribe('pods');
      setIsLoading(false);
    }
  }, [isConnected, connect, subscribe]);

  // Расчет количества деплойментов и подов для каждого неймспейса
  const getNamespaceStats = useCallback(() => {
    if (!resources.namespaces || resources.namespaces.length === 0) {
      console.log("No namespaces available for stats calculation");
      return [];
    }

    const stats = {};

    // Инициализация статистики для всех неймспейсов
    if (resources.namespaces && resources.namespaces.length > 0) {
        resources.namespaces.forEach(ns => {
            stats[ns.name] = {
                namespace: ns,
                deploymentCount: 0,
                podCount: 0,
                controllers: []
            };
        });
      };

    // Подготовка объекта для привязки подов к контроллерам
    const podsByController = {};

    // Группируем поды по контроллеру
    if (resources.pods && resources.pods.length > 0) {
      // Выведем пример данных пода для отладки и вывода всей структуры


      resources.pods.forEach(pod => {
        if (pod.namespace) {
          // Находим владельца пода разными способами - в разных реализациях Kubernetes API поля могут отличаться
          const owner = pod.owner || pod.controller_name ||
                        (pod.owner_references && pod.owner_references.length > 0 && pod.owner_references[0].name);

          if (owner) {
            const key = `${pod.namespace}/${owner}`;
            if (!podsByController[key]) {
              podsByController[key] = [];
            }

            // Убедимся, что у пода есть статус
            if (!pod.status) {
              pod.status = pod.phase || 'unknown';
            }

            podsByController[key].push(pod);
          }
        }
      });

    }

    
    // Проверяем, что controllers определен
    if (resources.controllers && resources.controllers.length > 0) {
      // Логируем примеры контроллеров для проверки структуры данных
      // console.log("Sample controller data:", resources.controllers[0]);

      // Сначала соберем данные по контроллерам для каждого неймспейса
      resources.controllers.forEach(controller => {
        if (controller && controller.namespace && stats[controller.namespace]) {
          stats[controller.namespace].deploymentCount += 1;

          // Добавляем поды к контроллеру
          const controllerKey = `${controller.namespace}/${controller.name}`;
          if (podsByController[controllerKey]) {
            controller.pods = podsByController[controllerKey];
            console.log(`Added ${controller.pods.length} pods to ${controller.name} in ${controller.namespace}`);
          } else {
            controller.pods = [];
          }

          stats[controller.namespace].controllers.push(controller);
        } else {
          console.log(`Skipping controller with invalid namespace: ${controller?.namespace}`);
        }
      });

      // Теперь считаем поды для каждого неймспейса
      Object.keys(stats).forEach(nsName => {
        const nsStats = stats[nsName];

        // Считаем поды в каждом контроллере
        nsStats.controllers.forEach(controller => {
          if (controller.replicas) {
            // Используем значение ready реплик как количество работающих подов
            const readyReplicas = controller.replicas.ready || 0;
            nsStats.podCount += readyReplicas;

          }
        });

        // Убедимся, что подсчет корректный (не отрицательный)
        nsStats.podCount = Math.max(0, nsStats.podCount);
      });
    } else {
      console.warn("No controllers available to calculate namespace stats");
    }

    // Определяем статус каждого неймспейса для сортировки
    Object.values(stats).forEach(ns => {
      if (ns.deploymentCount === 0) {
        ns.status = 'scaled_zero';
      } else if (ns.podCount <= 1) {
        ns.status = 'scaled_zero';
      } else if (ns.podCount >= ns.deploymentCount) {
        ns.status = 'healthy';
      } else {
        ns.status = 'progressing';
      }
    });

    return Object.values(stats);
  }, [resources]);

  // Сортировка и организация неймспейсов
  const sortNamespaces = useCallback((stats) => {
    if (!stats || stats.length === 0) return [];

    // Сначала сортируем по статусу, затем по алфавиту
    return [...stats].sort((a, b) => {
      // Сортировка по статусу: healthy -> progressing -> scaled_zero
      const statusOrder = { 'healthy': 1, 'progressing': 2, 'scaled_zero': 3 };
      if (statusOrder[a.status] !== statusOrder[b.status]) {
        return statusOrder[a.status] - statusOrder[b.status];
      }

      // Внутри одного статуса сортируем по алфавиту
      return a.namespace.name.localeCompare(b.namespace.name);
    });
  }, []);

  // Расчет статистики по неймспейсам

  const namespaceStats = sortNamespaces(getNamespaceStats());

  // Убираем показ индикатора загрузки при начальной загрузке страницы
  // Пользователь будет видеть WebSocket статус и пустую страницу до загрузки данных

  // Если есть ошибка и нет данных, показываем сообщение об ошибке
  if ((error || lastError) && namespaceStats.length === 0) {
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
        <h1 className="text-xl font-bold text-gray-800 dark:text-white mb-1">Namespace Status</h1>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Overview of your namespaces with deployment and pod counts.
        </p>
      </div>  

      {/* Панель управления с индикатором состояния WebSocket и переключателем оптимизации */}
      <div className="mb-4 flex flex-col sm:flex-row justify-between gap-2">
        {/* Индикатор состояния WebSocket */}
        <div className={`text-sm rounded-lg p-2 flex-grow ${isConnected ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400' : 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-400'}`}>
          <div className="flex items-center">
            <span className={`inline-block w-2 h-2 rounded-full mr-2 ${isConnected ? 'bg-green-500' : 'bg-yellow-500'}`}></span>
            <span>
              {isConnected
                ? 'WebSocket connected - receiving real-time updates'
                : (isConnecting ? 'Connecting to WebSocket...' : 'WebSocket disconnected - data may be stale')}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Переключатель компактного режима */}
          <div className="flex items-center justify-end gap-2 bg-gray-50 dark:bg-gray-800 p-2 rounded-lg">
            <label htmlFor="optimized-view" className="flex items-center cursor-pointer">
              <span className="text-sm text-gray-700 dark:text-gray-300 mr-2">Оптимизированный вид</span>
              <div className="relative">
                <input
                  type="checkbox"
                  id="optimized-view"
                  className="sr-only"
                  checked={optimizedView}
                  onChange={() => setOptimizedView(!optimizedView)}
                />
                <div className={`block w-10 h-6 rounded-full transition-colors ${optimizedView ? 'bg-healthy' : 'bg-gray-300 dark:bg-gray-600'}`}></div>
                <div className={`absolute left-1 top-1 bg-white w-4 h-4 rounded-full transition-transform ${optimizedView ? 'transform translate-x-4' : ''}`}></div>
              </div>
            </label>
          </div>

          {/* Кнопка переподключения - отображается только когда соединение разорвано */}
          {!isConnected && (
            <button
              onClick={handleRefresh}
              className="flex items-center px-3 py-1.5 bg-yellow-500 dark:bg-yellow-600 text-white dark:text-white rounded hover:bg-yellow-600 dark:hover:bg-yellow-700 transition-colors"
              disabled={isConnecting}
            >
              <svg
                className={`w-4 h-4 mr-1.5 ${isConnecting ? 'animate-spin' : ''}`}
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
              {isConnecting ? 'Connecting...' : 'Reconnect'}
            </button>
          )}
        </div>
      </div>

      {namespaceStats.length > 0 ? (
        <>
          {/* Разделитель для здоровых неймспейсов в компактном режиме */}
          {namespaceStats.some(ns => ns.status === 'healthy') && (
            <div className="mb-4">
              <h3 className="text-lg font-semibold text-healthy mb-2 flex items-center">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                Healthy Namespaces
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-6 gap-3 overflow-x-hidden">{
                  <NamespaceTable namespaceStats={namespaceStats.filter(stats => stats.status === 'healthy')} optimizedView={optimizedView} />}
              </div>
            </div>
          )}

          {/* Разделитель для прогрессирующих неймспейсов */}
          {namespaceStats.some(ns => ns.status === 'progressing') && (
            <div className="mb-4">
              <h3 className="text-lg font-semibold text-progressing mb-2 flex items-center">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Progressing Namespaces
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-6 gap-3 overflow-x-hidden">{
                namespaceStats
                  .filter(stats => stats.status === 'progressing')
                  .map((stats) => ( <div key={stats.namespace.name}>
                      <NamespaceCard
                        namespace={stats.namespace}
                        deploymentCount={stats.deploymentCount}
                        podCount={stats.podCount}
                        compact={optimizedView}
                        controllers={stats.controllers} 
                      />
                    </div>
                  ))
                }
              </div>
            </div>
          )}
          
          {/* Разделитель для неактивных неймспейсов */}
          {namespaceStats.some(ns => ns.status === 'scaled_zero') && (
            <div className="mb-4">
              <h3 className="text-lg font-semibold text-gray-500 dark:text-gray-400 mb-2 flex items-center">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                </svg>
                Inactive Namespaces
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-6 gap-3 overflow-x-hidden">{
                namespaceStats
                  .filter(stats => stats.status === 'scaled_zero')
                  .map((stats) => ( <div key={stats.namespace.name}>
                      <NamespaceCard
                        namespace={stats.namespace}
                        deploymentCount={stats.deploymentCount}
                        podCount={stats.podCount}
                        compact={optimizedView}
                      />
                    </div>
                  ))
                }
              </div>
            </div>
          )}
        </>
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
    </div>
  );
}

