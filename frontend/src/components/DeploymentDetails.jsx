import { useEffect, useState } from 'react';
import StatusBadge from './StatusBadge';

/**
 * Компонент для отображения подробной информации о деплойменте
 */
export default function DeploymentDetails({ deployment, onClose, isOpen }) {
  const [selectedTab, setSelectedTab] = useState('overview');

  // Сброс выбранной вкладки при смене деплоймента
  useEffect(() => {
    setSelectedTab('overview');
  }, [deployment?.name]);

  // Если нет деплоймента для отображения или модальное окно закрыто
  if (!deployment || !isOpen) {
    return null;
  }

  // Обработка имени контроллера (удаление суффикса -deploy или -statefulset)
  const displayName = deployment.name.replace(/-deploy$/, '').replace(/-statefulset$/, '');

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Заголовок */}
        <div className="flex justify-between items-center p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center">
            <h2 className="text-xl font-bold text-gray-800 dark:text-white mr-3">{displayName}</h2>
            <StatusBadge status={deployment.status} type={deployment.controller_type || "deployment"} />
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Вкладки */}
        <div className="border-b border-gray-200 dark:border-gray-700">
          <nav className="flex">
            <button
              className={`py-3 px-4 font-medium text-sm border-b-2 ${
                selectedTab === 'overview'
                  ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-white'
              }`}
              onClick={() => setSelectedTab('overview')}
            >
              Overview
            </button>
            <button
              className={`py-3 px-4 font-medium text-sm border-b-2 ${
                selectedTab === 'pods'
                  ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-white'
              }`}
              onClick={() => setSelectedTab('pods')}
            >
              Pods
            </button>
            <button
              className={`py-3 px-4 font-medium text-sm border-b-2 ${
                selectedTab === 'yaml'
                  ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-white'
              }`}
              onClick={() => setSelectedTab('yaml')}
            >
              YAML
            </button>
          </nav>
        </div>

        {/* Содержимое вкладок */}
        <div className="flex-1 overflow-y-auto p-4">
          {/* Вкладка Overview */}
          {selectedTab === 'overview' && (
            <div className="space-y-6">
              {/* Базовая информация */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
                  <h3 className="text-lg font-medium text-gray-800 dark:text-white mb-3">Controller Info</h3>
                  <div className="space-y-2">
                    <div className="grid grid-cols-3 gap-2">
                      <span className="text-gray-500 dark:text-gray-400">Name:</span>
                      <span className="col-span-2 font-medium text-gray-800 dark:text-white">{deployment.name}</span>
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                      <span className="text-gray-500 dark:text-gray-400">Namespace:</span>
                      <span className="col-span-2 font-medium text-gray-800 dark:text-white">{deployment.namespace}</span>
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                      <span className="text-gray-500 dark:text-gray-400">Status:</span>
                      <span className="col-span-2">
                        <StatusBadge status={deployment.status} type={deployment.controller_type || 'deployment'} />
                      </span>
                    </div>
                  </div>
                </div>

                <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
                  <h3 className="text-lg font-medium text-gray-800 dark:text-white mb-3">Replicas</h3>
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-2">
                      <div className="bg-white dark:bg-gray-800 p-3 rounded-lg text-center">
                        <span className="block text-sm text-gray-500 dark:text-gray-400">Desired</span>
                        <span className="block text-xl font-bold text-gray-800 dark:text-white">{deployment.replicas.desired}</span>
                      </div>
                      <div className="bg-white dark:bg-gray-800 p-3 rounded-lg text-center">
                        <span className="block text-sm text-gray-500 dark:text-gray-400">Ready</span>
                        <span className="block text-xl font-bold text-gray-800 dark:text-white">{deployment.replicas.ready}</span>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="bg-white dark:bg-gray-800 p-3 rounded-lg text-center">
                        <span className="block text-sm text-gray-500 dark:text-gray-400">Available</span>
                        <span className="block text-xl font-bold text-gray-800 dark:text-white">{deployment.replicas.available}</span>
                      </div>
                      <div className="bg-white dark:bg-gray-800 p-3 rounded-lg text-center">
                        <span className="block text-sm text-gray-500 dark:text-gray-400">Updated</span>
                        <span className="block text-xl font-bold text-gray-800 dark:text-white">{deployment.replicas.updated}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Информация о контейнере */}
              {deployment.main_container && (
                <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
                  <h3 className="text-lg font-medium text-gray-800 dark:text-white mb-3">Container</h3>
                  <div className="space-y-2">
                    <div className="grid grid-cols-3 gap-2">
                      <span className="text-gray-500 dark:text-gray-400">Name:</span>
                      <span className="col-span-2 font-medium text-gray-800 dark:text-white">
                        {deployment.main_container.name.replace(/-pod$/, '')}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                      <span className="text-gray-500 dark:text-gray-400">Image:</span>
                      <span className="col-span-2 font-medium text-gray-800 dark:text-white break-all">
                        {deployment.main_container.image}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                      <span className="text-gray-500 dark:text-gray-400">Tag:</span>
                      <span className="col-span-2 font-medium text-gray-800 dark:text-white">
                        {deployment.main_container.image_tag}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Метки */}
              {deployment.labels && Object.keys(deployment.labels).length > 0 && (
                <div className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
                  <h3 className="text-lg font-medium text-gray-800 dark:text-white mb-3">Labels</h3>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(deployment.labels).map(([key, value]) => (
                      <span key={key} className="inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                        {key}: {value}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Вкладка Pods */}
          {selectedTab === 'pods' && (
            <div>
              <h3 className="text-lg font-medium text-gray-800 dark:text-white mb-3">Pods</h3>

              {deployment.pods && deployment.pods.length > 0 ? (
                <div className="space-y-4">
                  {deployment.pods.map((pod, index) => (
                    <div key={index} className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
                      <div className="flex justify-between items-center mb-2">
                        <h4 className="font-medium text-gray-800 dark:text-white">{pod.name}</h4>
                        <StatusBadge status={pod.phase.toLowerCase()} type="pod" />
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
                        <div className="bg-white dark:bg-gray-800 p-3 rounded-lg">
                          <h5 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">CPU Usage</h5>
                          <div className="flex justify-between items-center">
                            <span className="text-xl font-bold text-gray-800 dark:text-white">
                              {pod.metrics?.cpu_millicores || 'N/A'} <span className="text-sm font-normal">mCores</span>
                            </span>
                            <div className="w-24 h-3 bg-gray-200 dark:bg-gray-700 rounded-full">
                              <div
                                className="h-3 bg-blue-500 rounded-full"
                                style={{ width: `${Math.min(pod.metrics?.cpu_millicores / 10 || 0, 100)}%` }}
                              ></div>
                            </div>
                          </div>
                        </div>

                        <div className="bg-white dark:bg-gray-800 p-3 rounded-lg">
                          <h5 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">Memory Usage</h5>
                          <div className="flex justify-between items-center">
                            <span className="text-xl font-bold text-gray-800 dark:text-white">
                              {pod.metrics?.memory_mb || 'N/A'} <span className="text-sm font-normal">MB</span>
                            </span>
                            <div className="w-24 h-3 bg-gray-200 dark:bg-gray-700 rounded-full">
                              <div
                                className="h-3 bg-green-500 rounded-full"
                                style={{ width: `${Math.min(pod.metrics?.memory_mb / 10 || 0, 100)}%` }}
                              ></div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="bg-gray-50 dark:bg-gray-700 p-6 rounded-lg text-center">
                  <svg
                    className="w-12 h-12 text-gray-400 mx-auto mb-3"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                  </svg>
                  <p className="text-gray-500 dark:text-gray-400">No active pods found for this deployment.</p>
                </div>
              )}
            </div>
          )}

          {/* Вкладка YAML */}
          {selectedTab === 'yaml' && (
            <div>
              <h3 className="text-lg font-medium text-gray-800 dark:text-white mb-3">YAML Definition</h3>
              <div className="bg-gray-50 dark:bg-gray-700 rounded-lg overflow-hidden">
                <pre className="p-4 overflow-x-auto text-sm text-gray-800 dark:text-gray-200 font-mono">
                  {`apiVersion: apps/v1
kind: ${deployment.controller_type === 'statefulset' ? 'StatefulSet' : 'Deployment'}
metadata:
  name: ${deployment.name}
  namespace: ${deployment.namespace}
spec:
  replicas: ${deployment.replicas.desired}
  selector:
    matchLabels:
${Object.entries(deployment.labels || {}).map(([k, v]) => `      ${k}: ${v}`).join('\n')}
  template:
    metadata:
      labels:
${Object.entries(deployment.labels || {}).map(([k, v]) => `        ${k}: ${v}`).join('\n')}
    spec:
      containers:
      - name: ${deployment.main_container?.name || 'main'}
        image: ${deployment.main_container?.image || 'image:latest'}
${deployment.controller_type === 'statefulset' ? `  serviceName: ${deployment.name}` : ''}
`}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
