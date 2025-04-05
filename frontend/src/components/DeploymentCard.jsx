// src/components/DeploymentCard.jsx
/**
 * Компонент карточки деплоймента
 */
export default function DeploymentCard({ deployment, onClick }) {
  // Определение стилей карточки в зависимости от статуса деплоймента
  const getStatusStyles = (status) => {
    switch (status) {
      case 'healthy':
        return {
          borderColor: 'border-healthy',
          bgColor: 'bg-healthy/10',
          headerBg: 'bg-healthy'
        };
      case 'progressing':
        return {
          borderColor: 'border-progressing',
          bgColor: 'bg-progressing/10',
          headerBg: 'bg-progressing'
        };
      case 'scaled_zero':
        return {
          borderColor: 'border-scaled-zero',
          bgColor: 'bg-scaled-zero/10',
          headerBg: 'bg-scaled-zero'
        };
      case 'error':
        return {
          borderColor: 'border-error',
          bgColor: 'bg-error/10',
          headerBg: 'bg-error'
        };
      default:
        return {
          borderColor: 'border-gray-300 dark:border-gray-600',
          bgColor: 'bg-white dark:bg-gray-800',
          headerBg: 'bg-gray-300 dark:bg-gray-700'
        };
    }
  };

  // Получение стилей в зависимости от статуса
  const { borderColor, bgColor, headerBg } = getStatusStyles(deployment.status);

  // Обработка имени деплоймента (удаление суффикса -deploy)
  const displayName = deployment.name.replace(/-deploy$/, '');

  // Обработка имени контейнера (если есть, удаление суффикса -pod)
  const containerName = deployment.main_container?.name?.replace(/-pod$/, '') || 'N/A';

  // Тег образа
  const imageTag = deployment.main_container?.image_tag || 'N/A';

  return (
    <div
      className={`rounded-lg overflow-hidden shadow-sm border ${borderColor} transition-all duration-300 hover:shadow-md ${bgColor} transform hover:-translate-y-1 cursor-pointer`}
      onClick={onClick}
    >
      {/* Заголовок карточки */}
      <div className={`${headerBg} px-4 py-2 text-white flex justify-between items-center`}>
        <h3 className="font-medium text-lg truncate" title={displayName}>
          {displayName}
        </h3>
        <div className="text-xs px-2 py-1 bg-white/20 rounded">
          {deployment.namespace}
        </div>
      </div>

      {/* Содержимое карточки */}
      <div className="p-4">
        <div className="grid grid-cols-2 gap-3 text-sm">
          {/* Информация о репликах */}
          <div className="col-span-2 mb-2">
            <div className="flex justify-between items-center">
              <span className="text-gray-600 dark:text-gray-400">Replicas:</span>
              <span className="font-semibold text-gray-900 dark:text-gray-100">
                {deployment.replicas.ready || 0}/{deployment.replicas.desired || 0}
              </span>
            </div>
            {/* Прогресс-бар репликации */}
            <div className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-full mt-1">
              <div
                className={`h-2 rounded-full ${
                  deployment.status === 'healthy'
                    ? 'bg-healthy'
                    : deployment.status === 'progressing'
                    ? 'bg-progressing'
                    : 'bg-scaled-zero'
                }`}
                style={{
                  width: `${
                    deployment.replicas.desired === 0
                      ? 0
                      : (deployment.replicas.ready / deployment.replicas.desired) * 100
                  }%`,
                }}
              ></div>
            </div>
          </div>

          {/* Информация о контейнере */}
          <div>
            <div className="text-gray-600 dark:text-gray-400">Container:</div>
            <div className="font-medium text-gray-900 dark:text-gray-100 truncate" title={containerName}>
              {containerName}
            </div>
          </div>

          {/* Информация о теге образа */}
          <div>
            <div className="text-gray-600 dark:text-gray-400">Image Tag:</div>
            <div className="font-medium text-gray-900 dark:text-gray-100 truncate" title={imageTag}>
              {imageTag}
            </div>
          </div>

          {/* Здесь можно добавить информацию о ресурсах при наличии активных подов */}
          {deployment.replicas.ready > 0 && deployment.pods && (
            <div className="col-span-2 mt-2">
              <div className="text-gray-600 dark:text-gray-400 mb-1">Resource Usage:</div>
              <div className="space-y-2">
                {deployment.pods?.slice(0, 3).map((pod, idx) => (
                  <div key={idx} className="bg-gray-50 dark:bg-gray-700 rounded p-2 text-xs">
                    <div className="flex justify-between mb-1">
                      <span>{pod.name}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <span className="text-gray-500 dark:text-gray-400">CPU: </span>
                        <span className="font-medium">{pod.metrics?.cpu_millicores || 'N/A'} m</span>
                      </div>
                      <div>
                        <span className="text-gray-500 dark:text-gray-400">Memory: </span>
                        <span className="font-medium">{pod.metrics?.memory_mb || 'N/A'} MB</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
