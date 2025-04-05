/**
 * Компонент для отображения статуса
 * @param {Object} props - Свойства компонента
 * @param {string} props.status - Статус (healthy, progressing, scaled_zero, error, etc.)
 * @param {string} props.type - Тип (deployment, pod)
 */
function StatusBadge({ status, type = 'deployment' }) {
  // Цвета и названия для разных статусов
  const statusConfig = {
    deployment: {
      healthy: { color: 'bg-healthy text-white', label: 'Healthy' },
      progressing: { color: 'bg-progressing text-gray-900', label: 'Progressing' },
      scaled_zero: { color: 'bg-scaled-zero text-white', label: 'Scaled to Zero' },
      error: { color: 'bg-error text-white', label: 'Error' },
    },
    pod: {
      running: { color: 'bg-pod-running text-white', label: 'Running' },
      succeeded: { color: 'bg-pod-succeeded text-white', label: 'Succeeded' },
      pending: { color: 'bg-pod-pending text-gray-900', label: 'Pending' },
      failed: { color: 'bg-pod-failed text-white', label: 'Failed' },
      terminating: { color: 'bg-pod-terminating text-white', label: 'Terminating' },
    },
  };

  // Получение конфигурации для статуса
  const config = statusConfig[type]?.[status] || {
    color: 'bg-gray-500 text-white',
    label: status || 'Unknown'
  };

  return (
    <span className={`inline-block px-2 py-1 rounded text-xs font-semibold ${config.color}`}>
      {config.label}
    </span>
  );
}
