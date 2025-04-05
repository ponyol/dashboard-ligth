// Базовый URL для API
const API_BASE_URL = '/api';

/**
 * Выполнение запроса к API с обработкой ошибок
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

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP Error ${response.status}`);
    }

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
export const k8sApi = {
  getNamespaces: () => fetchApi('/k8s/namespaces'),
  getDeployments: (namespace = null) => {
    const query = namespace ? `?namespace=${namespace}` : '';
    return fetchApi(`/k8s/deployments${query}`);
  },
  getDeployment: (namespace, name) =>
    fetchApi(`/k8s/deployments/${namespace}/${name}`),
  getPods: (namespace = null) => {
    const query = namespace ? `?namespace=${namespace}` : '';
    return fetchApi(`/k8s/pods${query}`);
  },
  clearCache: () => fetchApi('/k8s/cache/clear', { method: 'POST' }),
};

/**
 * API для работы с аутентификацией
 */
export const authApi = {
  getCurrentUser: () => fetchApi('/auth/user').catch(() => null),
  logout: () => fetchApi('/auth/logout'),
};

export default { k8s: k8sApi, auth: authApi };
