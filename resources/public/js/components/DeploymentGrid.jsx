/**
 * Компонент сетки деплойментов
 * @param {Object} props - Свойства компонента
 * @param {Array} props.deployments - Список деплойментов
 * @param {boolean} props.isLoading - Флаг загрузки
 * @param {string} props.error - Сообщение об ошибке
 */
function DeploymentGrid({ deployments, isLoading, error }) {
  const [focusedDeployment, setFocusedDeployment] = React.useState(null);

  // Обработчик переключения фокуса
  const handleFocusToggle = (deployment) => {
    if (focusedDeployment && focusedDeployment.name === deployment.name) {
      setFocusedDeployment(null);
    } else {
      setFocusedDeployment(deployment);
    }
  };

  // Если идет загрузка, показываем индикатор
  if (isLoading) {
    return <Loading text="Loading deployments..." />;
  }

  // Если есть ошибка, показываем сообщение
  if (error) {
    return (
      <div className="bg-red-50 dark:bg-red-900/20 p-4 rounded-lg text-red-700 dark:text-red-400">
        <h3 className="text-lg font-medium mb-2">Error</h3>
        <p>{error}</p>
      </div>
    );
  }

  // Если нет деплойментов, показываем сообщение
  if (!deployments || deployments.length === 0) {
    return (
      <div className="bg-gray-50 dark:bg-gray-800 p-6 rounded-lg text-center">
        <svg
          className="w-12 h-12 text-gray-400 dark:text-gray-500 mx-auto mb-3"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
            d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
          ></path>
        </svg>
        <h3 className="text-lg font-medium text-gray-700 dark:text-gray-300 mb-1">No deployments found</h3>
        <p className="text-gray-500 dark:text-gray-400">
          There are no deployments in the selected namespace.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {deployments.map((deployment) => (
        <DeploymentCard
          key={`${deployment.namespace}-${deployment.name}`}
          deployment={deployment}
          isFocused={focusedDeployment && focusedDeployment.name === deployment.name}
          focusModeEnabled={!!focusedDeployment}
          onFocusToggle={handleFocusToggle}
        />
      ))}
    </div>
  );
}
