// src/components/Dashboard.jsx
import { useEffect, useCallback, useState } from 'react';
import useK8sApi from '../hooks/useK8sApi';
import useInterval from '../hooks/useInterval';
import useWebSocket from '../hooks/useWebSocket';
import Filters from './Filters';
import DeploymentCard from './DeploymentCard';
import DeploymentDetails from './DeploymentDetails';
import Loading from './Loading';

/**
 * Основной компонент дашборда
 */
export default function Dashboard() {
  // Get API client for initial loading and traditional HTTP calls
  const {
    namespaces: httpNamespaces,
    controllers: httpControllers,
    selectedNamespace,
    isLoading: httpIsLoading,
    error: httpError,
    fetchNamespaces,
    fetchControllers,
    handleNamespaceChange,
    handleClearCache,
  } = useK8sApi();

  // Get WebSocket client for real-time updates
  const {
    isConnected: wsConnected,
    isConnecting: wsConnecting,
    lastError: wsError,
    resources: wsResources,
    subscribe,
    unsubscribe,
  } = useWebSocket();

  // Состояние для режима фокуса (выделение одного контроллера)
  const [focusedController, setFocusedController] = useState(null);

  // Состояние для модального окна с деталями контроллера
  const [selectedController, setSelectedController] = useState(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);

  // Интервал обновления данных в миллисекундах (15 секунд)
  const refreshInterval = 15000;

  // Первоначальная загрузка данных
  // Первоначальная загрузка данных - только при первом рендере
  useEffect(() => {
    fetchNamespaces();
  }, [fetchNamespaces]);

  // Загрузка контроллеров при изменении выбранного неймспейса
  useEffect(() => {
    fetchControllers();
  }, [fetchControllers, selectedNamespace]);

  // Подписка на обновления неймспейсов через WebSocket - не зависит от выбранного namespace
  useEffect(() => {
    if (wsConnected) {
      console.log('Subscribing to namespaces updates via WebSocket');
      subscribe('namespaces', null);

      // Очистка при размонтировании
      return () => {
        console.log('Unsubscribing from namespaces updates');
        unsubscribe('namespaces');
      };
    }
  }, [wsConnected, subscribe, unsubscribe]);

  // Подписка на WebSocket обновления контроллеров при изменении namespace
  useEffect(() => {
    if (wsConnected) {
      // Отписываемся от предыдущих обновлений
      unsubscribe('deployments');
      unsubscribe('statefulsets');
      // unsubscribe('pods');

      // Подписываемся на обновления сначала с null namespace, чтобы получить все данные
      // Это важно, чтобы иметь все контроллеры для последующей фильтрации
      subscribe('deployments', null);
      subscribe('statefulsets', null);
      subscribe('pods', null);

      console.log(`Subscribed to controllers WebSocket updates for all namespaces`);
      console.log(`Current namespace filter (client-side): ${selectedNamespace || 'all'}`);
    }

    // Очистка при размонтировании
    return () => {
      if (wsConnected) {
        unsubscribe('deployments');
        unsubscribe('statefulsets');
        // unsubscribe('pods');
      }
    };
  }, [wsConnected, subscribe, unsubscribe]); // Убран selectedNamespace из зависимостей

  // Отключаем периодическое обновление данных, так как теперь используем WebSocket
  // useInterval(() => {
  //   fetchControllers();
  // }, refreshInterval);

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

  // Комбинируем данные из HTTP API и WebSocket
  // Приоритет отдаем данным из WebSocket, если они есть
  const namespaces = wsResources.namespaces && wsResources.namespaces.length > 0
    ? wsResources.namespaces
    : httpNamespaces;

  // Приоритет отдаем данным из WebSocket, если они есть, но применяем фильтрацию по выбранному namespace
  let controllersToShow = wsResources.controllers && wsResources.controllers.length > 0
    ? wsResources.controllers
    : httpControllers;

  // Фильтруем контроллеры по выбранному неймспейсу если он задан
  if (selectedNamespace) {
    controllersToShow = controllersToShow.filter(c => c.namespace === selectedNamespace);
  }

  // Сортируем контроллеры по имени для более стабильного отображения
  const controllers = controllersToShow.sort((a, b) => a.name.localeCompare(b.name));

  // Debugging info для отслеживания обновлений данных
  useEffect(() => {
    console.log(`WebSocket resources updated:
      Namespaces: ${wsResources.namespaces?.length || 0}
      Controllers (total): ${wsResources.controllers?.length || 0}
      Controllers (filtered): ${controllers.length}
    `);

    // Выводим HTTP данные для сравнения
    console.log(`HTTP API data:
      Namespaces: ${httpNamespaces?.length || 0}
      Controllers: ${httpControllers?.length || 0}
    `);

    // Вывод информации о фильтрации
    if (selectedNamespace) {
      console.log(`Filtering by namespace: ${selectedNamespace}`);
      console.log(`Controllers after filtering: ${controllers.length}`);
    }

    // Добавляем отдельную функцию для отчета по статистике
    try {
      console.log("=== Namespace Statistics ===");

      // Безопасно проверяем наличие данных
      const hasNamespaces = Array.isArray(wsResources.namespaces) || Array.isArray(httpNamespaces);
      const hasControllers = Array.isArray(wsResources.controllers) || Array.isArray(httpControllers);

      if (!hasNamespaces) {
        console.log("No namespaces available to calculate stats");
      }

      if (!hasControllers) {
        console.log("No controllers available to calculate namespace stats");
      }

      // Только если есть и неймспейсы и контроллеры, выполняем анализ
      if (hasNamespaces && hasControllers) {
        // Используем данные из WebSocket если они есть, иначе из HTTP API
        const namespacesToAnalyze = (wsResources.namespaces?.length > 0)
          ? wsResources.namespaces
          : (Array.isArray(httpNamespaces) ? httpNamespaces : []);

        const controllerData = (wsResources.controllers?.length > 0)
          ? wsResources.controllers
          : (Array.isArray(httpControllers) ? httpControllers : []);

        console.log(`Analyzing ${namespacesToAnalyze.length} namespaces and ${controllerData.length} controllers`);

        // Создаем карту для группировки контроллеров по неймспейсам
        const namespaceStats = {};

        // Инициализируем статистику для каждого неймспейса
        namespacesToAnalyze.forEach(ns => {
          if (ns && typeof ns === 'object' && ns.name) {
            namespaceStats[ns.name] = { controllers: 0, pods: 0 };
          } else {
            console.warn("Invalid namespace object:", ns);
          }
        });

        // Дополнительный вывод для отладки структуры данных
        console.log("Sample namespace object:", namespacesToAnalyze[0]);
        console.log("Sample controller object:", controllerData[0]);

        // Подсчитываем контроллеры для каждого неймспейса
        controllerData.forEach(controller => {
          if (!controller) return;

          const namespace = controller.namespace;
          if (namespace && namespaceStats[namespace]) {
            namespaceStats[namespace].controllers++;

            // Подсчитываем поды, если информация о них есть
            if (controller.pods && Array.isArray(controller.pods)) {
              namespaceStats[namespace].pods += controller.pods.length;
            }
          }
        });

        // Выводим статистику для каждого неймспейса
        console.log("Namespace statistics (name - controllers - pods):");

        // Подсчитаем общее количество контроллеров и подов
        let totalControllers = 0;
        let totalPods = 0;

        // Выводим только непустые неймспейсы и считаем общую статистику
        Object.entries(namespaceStats).forEach(([namespace, stats]) => {
          totalControllers += stats.controllers;
          totalPods += stats.pods;

          // Выводим только непустые неймспейсы для уменьшения шума
          if (stats.controllers > 0 || stats.pods > 0) {
            console.log(`${namespace} - ${stats.controllers} - ${stats.pods}`);
          }
        });

        // Выводим суммарную статистику
        console.log(`TOTAL - ${totalControllers} controllers - ${totalPods} pods`);

        // Проверяем текущий выбранный неймспейс
        if (selectedNamespace) {
          console.log(`Selected namespace: ${selectedNamespace}`);
          console.log(`Controllers in selected namespace: ${namespaceStats[selectedNamespace]?.controllers || 0}`);
          console.log(`Pods in selected namespace: ${namespaceStats[selectedNamespace]?.pods || 0}`);
        } else {
          console.log("No namespace selected (showing all namespaces)");
        }
      }

      console.log("=== End of Namespace Statistics ===");
    } catch (error) {
      console.error("Error generating namespace statistics:", error);
    }
  }, [wsResources, httpNamespaces, httpControllers, controllers, selectedNamespace]);

  const isLoading = httpIsLoading || wsConnecting;
  const error = wsError || httpError;

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

  // Функция getControllerTypeText удалена, так как больше не используется

  return (
    <div className="p-2 w-full overflow-x-hidden">
      <div className="mb-3">
        <h1 className="text-xl font-bold text-gray-800 dark:text-white mb-1">Controllers Status</h1>
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
          {wsConnected ? (
            <span className="bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 px-2 py-0.5 rounded-full font-medium">
              WebSocket connected
            </span>
          ) : wsConnecting ? (
            <span className="bg-yellow-100 dark:bg-yellow-900 text-yellow-700 dark:text-yellow-300 px-2 py-0.5 rounded-full font-medium">
              Connecting...
            </span>
          ) : (
            <span className="bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300 px-2 py-0.5 rounded-full font-medium">
              WebSocket disconnected
            </span>
          )}
          <span className="mx-2">•</span>
          <span>
            {wsConnected
              ? 'Real-time updates via WebSocket'
              : 'Using HTTP API (WebSocket not connected)'}
          </span>
          <span className="mx-2">•</span>
          <span>Last update: {new Date().toLocaleTimeString()}</span>
          <span className="mx-2">•</span>
          <span>
            Data source: {wsResources.controllers && wsResources.controllers.length > 0
              ? `WebSocket (${wsResources.controllers.length} items)`
              : `HTTP (${httpControllers.length} items)`}
          </span>
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
