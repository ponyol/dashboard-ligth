/**
 * Компонент фильтров для дашборда
 */
export default function Filters({
  namespaces,
  selectedNamespace,
  onNamespaceChange,
  onRefresh,
  isLoading
}) {
  // Обработчик изменения выбранного неймспейса
  const handleNamespaceChange = (e) => {
    onNamespaceChange(e.target.value);
  };

  return (
    <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm mb-6 flex items-center">
      <div className="flex-grow">
        <label className="block text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">
          Namespace
        </label>
        <div className="relative">
          <select
            value={selectedNamespace}
            onChange={handleNamespaceChange}
            className="block w-full pl-3 pr-10 py-2 text-base border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            style={{ maxWidth: '300px' }}
          >
            <option value="">All Namespaces</option>
            {namespaces.map((ns) => (
              <option key={ns.name} value={ns.name}>
                {ns.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="ml-4 p-2 bg-blue-50 dark:bg-gray-700 rounded-md hover:bg-blue-100 dark:hover:bg-gray-600 focus:outline-none transition-colors"
          title="Refresh"
        >
          <svg
            className={`w-5 h-5 text-blue-600 dark:text-blue-400 ${isLoading ? 'animate-spin' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            ></path>
          </svg>
        </button>
      </div>
    </div>
  );
}
