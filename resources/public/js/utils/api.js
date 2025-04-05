/**
 * Модуль для работы с API
 */

// Базовый URL для API
const API_BASE_URL = '/api';

/**
 * Выполнение запроса к API с обработкой ошибок
 * @param {string} endpoint - Эндпоинт API
 * @param {Object} options - Опции для fetch
 * @returns {Promise<Object>} - Данные от API
 */
const fetchApi = async (endpoint, options = {}) => {
  try {
    const url = `${API_BASE_URL}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    // Если статус не OK (200-299)
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP Error ${response.status}`);
    }

    // Для 204 No Content
    if (response.status === 204) {
      return null;
    }

    return await response.json();
  } catch (error) {
    console.error(`API Error (${endpoint}):`, error);
    throw error;
  }
};

/**
 * API для работы с Kubernetes
 */
const k8sApi = {
  /**
   * Получение списка неймспейсов
   * @returns {Promise<Object>} - Список неймспейсов
   */
  getNamespaces: () => fetchApi('/k8s/namespaces'),

  /**
   * Получение списка деплойментов
   * @param {string} namespace - Фильтр по неймспейсу (опционально)
   * @returns {Promise<Object>} - Список деплойментов
   */
  getDeployments: (namespace = null) => {
    const query = namespace ? `?namespace=${namespace}` : '';
    return fetchApi(`/k8s/deployments${query}`);
  },

  /**
   * Получение информации о деплойменте
   * @param {string} namespace - Имя неймспейса
   * @param {string} name - Имя деплоймента
   * @returns {Promise<Object>} - Информация о деплойменте
   */
  getDeployment: (namespace, name) => fetchApi(`/k8s/deployments/${namespace}/${name}`),

  /**
   * Получение списка подов
   * @param {string} namespace - Фильтр по неймспейсу (опционально)
   * @returns {Promise<Object>} - Список подов
   */
  getPods: (namespace = null) => {
    const query = namespace ? `?namespace=${namespace}` : '';
    return fetchApi(`/k8s/pods${query}`);
  },

  /**
   * Получение информации о поде
   * @param {string} namespace - Имя неймспейса
   * @param {string} name - Имя пода
   * @returns {Promise<Object>} - Информация о поде
   */
  getPod: (namespace, name) => fetchApi(`/k8s/pods/${namespace}/${name}`),

  /**
   * Очистка кэша API
   * @returns {Promise<Object>} - Результат операции
   */
  clearCache: () => fetchApi('/k8s/cache/clear', { method: 'POST' }),
};

/**
 * API для работы с аутентификацией
 */
const authApi = {
  /**
   * Получение информации о текущем пользователе
   * @returns {Promise<Object>} - Информация о пользователе
   */
  getCurrentUser: () => fetchApi('/auth/user').catch(() => null),

  /**
   * Выход из системы
   * @returns {Promise<void>}
   */
  logout: () => fetchApi('/auth/logout'),
};

/**
 * API для проверки состояния здоровья
 */
const healthApi = {
  /**
   * Проверка состояния здоровья приложения
   * @returns {Promise<Object>} - Информация о состоянии
   */
  check: () => fetchApi('/health'),
};

// Экспорт API для использования в компонентах
window.api = {
  k8s: k8sApi,
  auth: authApi,
  health: healthApi,
};
