/**
 * Основной компонент дашборда
 */
function Dashboard() {
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
  React.useEffect(() => {
    fetchNamespaces();
  }, [fetchNamespaces]);

  // Загрузка деплойментов при изменении выбранного неймспейса
  React.useEffect(() => {
    fetchDeployments();
  }, [fetchDeployments, selectedNamespace]);

  // Периодическое обновление данных
  useInterval(() => {
    fetchDeployments();
  }, refreshInterval);

  // Обработчик обновления данных
  const handleRefresh = React.useCallback(() => {
    fetchNamespaces();
    fetchDeployments();
  }, [fetchNamespaces, fetchDeployments]);

  return (
    <div className="p-6">
      <Filters
        namespaces={namespaces}
        selectedNamespace={selectedNamespace}
        onNamespaceChange={handleNamespaceChange}
        onRefresh={handleRefresh}
        isLoading={isLoading}
      />

      <DeploymentGrid
        deployments={deployments}
        isLoading={isLoading}
        error={error}
      />

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
