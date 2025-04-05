/**
 * Хук для работы с Kubernetes API
 */
function useK8sApi() {
  const [namespaces, setNamespaces] = React.useState([]);
  const [deployments, setDeployments] = React.useState([]);
  const [selectedNamespace, setSelectedNamespace] = React.useState('');
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState(null);

  // Загрузка списка неймспейсов
  const fetchNamespaces = React.useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const data = await window.api.k8s.getNamespaces();
      setNamespaces(data.items || []);

      // Если выбранного неймспейса нет в списке, сбрасываем его
      if (selectedNamespace && !data.items.some(ns => ns.name === selectedNamespace)) {
        setSelectedNamespace('');
      }
    } catch (err) {
      setError(err.message || 'Ошибка при загрузке неймспейсов');
      console.error('Ошибка при загрузке неймспейсов:', err);
    } finally {
      setIsLoading(false);
    }
  }, [selectedNamespace]);

  // Загрузка списка деплойментов
  const fetchDeployments = React.useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const data = await window.api.k8s.getDeployments(selectedNamespace || null);
      setDeployments(data.items || []);
    } catch (err) {
      setError(err.message || 'Ошибка при загрузке деплойментов');
      console.error('Ошибка при загрузке деплойментов:', err);
    } finally {
      setIsLoading(false);
    }
  }, [selectedNamespace]);

  // Обработчик изменения выбранного неймспейса
  const handleNamespaceChange = React.useCallback((namespace) => {
    setSelectedNamespace(namespace);
  }, []);

  // Обработчик очистки кэша
  const handleClearCache = React.useCallback(async () => {
    try {
      setIsLoading(true);
      await window.api.k8s.clearCache();
      // После очистки кэша обновляем данные
      await fetchNamespaces();
      await fetchDeployments();
    } catch (err) {
      setError(err.message || 'Ошибка при очистке кэша');
      console.error('Ошибка при очистке кэша:', err);
    } finally {
      setIsLoading(false);
    }
  }, [fetchNamespaces, fetchDeployments]);

  return {
    namespaces,
    deployments,
    selectedNamespace,
    isLoading,
    error,
    fetchNamespaces,
    fetchDeployments,
    handleNamespaceChange,
    handleClearCache,
  };
}
