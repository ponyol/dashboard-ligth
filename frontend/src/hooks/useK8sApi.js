import { useState, useCallback, useEffect } from 'react';
import { k8sApi } from '../api/api';

export default function useK8sApi(options = {}) {
  const { forNamespaceDashboard = false } = options;
  
  const [namespaces, setNamespaces] = useState([]);
  const [deployments, setDeployments] = useState([]);
  const [controllers, setControllers] = useState([]);
  const [selectedNamespace, setSelectedNamespace] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // Загрузка списка неймспейсов
  const fetchNamespaces = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const data = await k8sApi.getNamespaces();
      const namespaceItems = data.items || [];
      setNamespaces(namespaceItems);

      // Если это НЕ дашборд неймспейсов И есть неймспейсы и нет выбранного неймспейса, выбираем первый по алфавиту
      if (!forNamespaceDashboard && namespaceItems.length > 0) {
        if (!selectedNamespace || !namespaceItems.some(ns => ns.name === selectedNamespace)) {
          // Сортируем неймспейсы по имени и выбираем первый
          const sortedNamespaces = [...namespaceItems].sort((a, b) => 
            a.name.localeCompare(b.name)
          );
          setSelectedNamespace(sortedNamespaces[0].name);
        }
      }
    } catch (err) {
      setError(err.message || 'Ошибка при загрузке неймспейсов');
      console.error('Ошибка при загрузке неймспейсов:', err);
    } finally {
      setIsLoading(false);
    }
  }, [selectedNamespace, forNamespaceDashboard]);

  // Загрузка списка деплойментов
  const fetchDeployments = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      // Если это дашборд неймспейсов, получаем данные для всех неймспейсов
      const namespaceParam = forNamespaceDashboard ? null : (selectedNamespace || null);
      const data = await k8sApi.getDeployments(namespaceParam);
      setDeployments(data.items || []);
    } catch (err) {
      setError(err.message || 'Ошибка при загрузке деплойментов');
      console.error('Ошибка при загрузке деплойментов:', err);
    } finally {
      setIsLoading(false);
    }
  }, [selectedNamespace, forNamespaceDashboard]);

  // Загрузка списка контроллеров (Deployments и StatefulSets)
  const fetchControllers = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      // Если это дашборд неймспейсов, получаем данные для всех неймспейсов
      const namespaceParam = forNamespaceDashboard ? null : (selectedNamespace || null);
      console.log(`Fetching controllers with namespace parameter: ${namespaceParam} (forNamespaceDashboard: ${forNamespaceDashboard})`);
      
      const data = await k8sApi.getControllers(namespaceParam);
      console.log(`Received ${data.items?.length || 0} controllers from API`);
      setControllers(data.items || []);
    } catch (err) {
      setError(err.message || 'Ошибка при загрузке контроллеров');
      console.error('Ошибка при загрузке контроллеров:', err);
    } finally {
      setIsLoading(false);
    }
  }, [selectedNamespace, forNamespaceDashboard]);

  // Обработчик изменения выбранного неймспейса
  const handleNamespaceChange = useCallback((namespace) => {
    setSelectedNamespace(namespace);
  }, []);

  // Обработчик очистки кэша
  const handleClearCache = useCallback(async () => {
    try {
      setIsLoading(true);
      await k8sApi.clearCache();
      // После очистки кэша обновляем данные
      await fetchNamespaces();
      await fetchDeployments();
      await fetchControllers();
    } catch (err) {
      setError(err.message || 'Ошибка при очистке кэша');
      console.error('Ошибка при очистке кэша:', err);
    } finally {
      setIsLoading(false);
    }
  }, [fetchNamespaces, fetchDeployments, fetchControllers]);

  return {
    namespaces,
    deployments,
    controllers,
    selectedNamespace,
    isLoading,
    error,
    fetchNamespaces,
    fetchDeployments,
    fetchControllers,
    handleNamespaceChange,
    handleClearCache,
  };
}
