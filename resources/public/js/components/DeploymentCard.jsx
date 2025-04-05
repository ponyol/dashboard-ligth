/**
 * Компонент карточки деплоймента
 * @param {Object} props - Свойства компонента
 * @param {Object} props.deployment - Данные о деплойменте
 * @param {boolean} props.isFocused - Находится ли карточка в фокусе
 * @param {boolean} props.focusModeEnabled - Включен ли режим фокуса
 * @param {Function} props.onFocusToggle - Обработчик переключения фокуса
 */
function DeploymentCard({ deployment, isFocused, focusModeEnabled, onFocusToggle }) {
  // Определение статусного класса по статусу деплоймента
  const getStatusClass = (status) => {
    switch (status) {
      case 'healthy': return 'border-healthy';
      case 'progressing': return 'border-progressing';
      case 'scaled_zero': return 'border-scaled-zero';
      case 'error': return 'border-error';
      default: return 'border-gray-300 dark:border-gray-600';
    }
  };

  // Определение класса для режима фокуса
  const focusClass = focusModeEnabled && !isFocused ? 'focus-mode-inactive' : '';

  const statusClass = getStatusClass(deployment.status);

  return (
    <div
      className={`bg-white dark:bg-gray-800 rounded-lg shadow-sm border-l-4 ${statusClass} ${focusClass} transition-all duration-300 hover:shadow-md`}
      onClick={() => onFocusToggle && onFocusToggle(deployment)}
    >
      <div className="p-4">
        <div className="flex justify-between items-start mb-2">
          <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 truncate" title={deployment.name}>
            {deployment.name}
          </h3>
          <StatusBadge status={deployment.status} type="deployment" />
        </div>

        <div className="text-sm text-gray-500 dark:text-gray-400 mb-3">
          Namespace: <span className="font-medium">{deployment.namespace}</span>
        </div>

        <div className="flex justify-between mb-2">
          <div className="text-sm">
            <span className="text-gray-500 dark:text-gray-400">Replicas: </span>
            <span className="font-medium text-gray-900 dark:text-gray-100">
              {deployment.replicas.ready}/{deployment.replicas.desired}
            </span>
          </div>

          {deployment.main_container && (
            <div className="text-sm truncate" style={{ maxWidth: '60%' }} title={deployment.main_container.image_tag}>
              <span className="text-gray-500 dark:text-gray-400">Tag: </span>
              <span className="font-mono text-xs bg-gray-100 dark:bg-gray-700 rounded px-1 py-0.5">
                {deployment.main_container.image_tag}
              </span>
            </div>
          )}
        </div>

        {/* Отображение ресурсов, если есть поды */}
        {deployment.pods && deployment.pods.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
            <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">
              Resources: {deployment.pods.length} pod{deployment.pods.length !== 1 ? 's' : ''}
            </div>
            {deployment.pods.slice(0, 2).map((pod) => {
              const metrics = pod.metrics;
              if (!metrics) return null;

              const totalUsage = {
                cpu: metrics.containers.reduce((sum, container) => {
                  return sum + (container.resource_usage.cpu_millicores || 0);
                }, 0),
                memory: metrics.containers.reduce((sum, container) => {
                  return sum + (container.resource_usage.memory_mb || 0);
                }, 0)
              };

              return (
                <div key={pod.name} className="text-xs text-gray-600 dark:text-gray-300 mt-1">
                  <div className="flex justify-between items-center">
                    <span className="truncate" style={{ maxWidth: '180px' }} title={pod.name}>
                      {pod.name}
                    </span>
                    <span className={`px-1.5 py-0.5 rounded-full text-xs ${
                      pod.phase.toLowerCase() === 'running'
                        ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                        : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
                    }`}>
                      {pod.phase}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 mt-1">
                    <div title={`CPU: ${totalUsage.cpu} millicores`}>
                      CPU: {totalUsage.cpu} m
                    </div>
                    <div title={`Memory: ${totalUsage.memory.toFixed(1)} MB`}>
                      Mem: {totalUsage.memory.toFixed(1)} MB
                    </div>
                  </div>
                </div>
              );
            })}
            {deployment.pods.length > 2 && (
              <div className="text-xs text-blue-600 dark:text-blue-400 mt-1 text-center">
                + {deployment.pods.length - 2} more pod(s)
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
