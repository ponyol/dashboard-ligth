// Определяем, находимся ли мы в режиме разработки
const isDev = import.meta.env ? import.meta.env.DEV : false;

// Определение WebSocket URL в зависимости от окружения
function determineWebSocketUrl() {
  // Сначала проверяем, есть ли явно заданный URL в window.ENV
  if (window.ENV && window.ENV.WEBSOCKET_URL) {
    return window.ENV.WEBSOCKET_URL;
  }
  
  // В режиме разработки всегда используем прямое подключение к порту 8765
  if (isDev) {
    return 'ws://localhost:8765';
  }
  
  // По умолчанию для production - подключение к тому же хосту, но на порту 8765
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const hostname = window.location.hostname;
  
  // В production всегда используем порт 8765 для WebSocket
  return `${protocol}://${hostname}:8765`;
}

// API конфигурация с возможностью настройки адресов серверов
const API_CONFIG = {
  // HTTP API сервер
  api: {
    baseUrl: '/api', // По умолчанию используем относительный путь
  },
  // WebSocket сервер
  websocket: {
    url: determineWebSocketUrl(), 
  }
};

// Переопределение настроек API URL из window.ENV если они доступны
if (window.ENV && window.ENV.API_URL) {
  API_CONFIG.api.baseUrl = window.ENV.API_URL;
}

// В режиме разработки API будет проксироваться через Vite
if (isDev) {
  API_CONFIG.api.baseUrl = '/api';
}

// Логирование для отладки
console.log(`API URL: ${API_CONFIG.api.baseUrl}`);
console.log(`WebSocket URL: ${API_CONFIG.websocket.url}`);

/**
 * Выполнение запроса к API с обработкой ошибок
 */
const fetchApi = async (endpoint, options = {}) => {
  try {
    const url = `${API_CONFIG.api.baseUrl}${endpoint}`;
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
  getControllers: (namespace = null) => {
    const query = namespace ? `?namespace=${namespace}` : '';
    return fetchApi(`/k8s/controllers${query}`);
  },
  getController: (namespace, name) =>
    fetchApi(`/k8s/controllers/${namespace}/${name}`),
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

/**
 * Экспорт настроек и API клиентов
 */
export { API_CONFIG };

export default { k8s: k8sApi, auth: authApi };