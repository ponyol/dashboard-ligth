import { useState, useCallback, useEffect } from 'react';
import { k8sApi } from '../api/api';

export default function useK8sApi() {
  const [namespaces, setNamespaces] = useState([]);
  const [deployments, setDeployments] = useState([]);
  const [selectedNamespace, setSelectedNamespace] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // Загрузка списка неймспейсов
  const fetchNamespaces = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const data = await k8sApi.getNamespaces();
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
  const fetchDeployments = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const data = await k8sApi.getDeployments(selectedNamespace || null);
      setDeployments(data.items || []);
    } catch (err) {
      setError(err.message || 'Ошибка при загрузке деплойментов');
      console.error('Ошибка при загрузке деплойментов:', err);
    } finally {
      setIsLoading(false);
    }
  }, [selectedNamespace]);

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
