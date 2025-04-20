// src/components/Filters.jsx
import { useState } from 'react';

/**
 * Компонент фильтров для дашборда
 */
export default function Filters({
  namespaces,
  selectedNamespace,
  onNamespaceChange,
  onRefresh,
  isLoading,
  showNamespaceFilter = true // По умолчанию показываем фильтр неймспейсов
}) {
  // Обработчик изменения выбранного неймспейса
  const handleNamespaceChange = (e) => {
    onNamespaceChange(e.target.value);
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm mb-3">
      <div className="p-3">
        <h2 className="text-md font-semibold text-gray-700 dark:text-gray-200 mb-2">Filters</h2>

        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between">
          {/* Селектор неймспейса - показываем только если showNamespaceFilter=true */}
          {showNamespaceFilter && (
            <div className="flex-grow mb-2 sm:mb-0 sm:mr-3 w-full sm:w-auto">
              <div className="relative">
                <select
                  value={selectedNamespace}
                  onChange={handleNamespaceChange}
                  className="block pl-2 pr-8 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
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
          )}

          {/* Кнопка обновления */}
          <div className={showNamespaceFilter ? "" : "ml-auto"}>
            <button
              onClick={onRefresh}
              disabled={isLoading}
              className="flex items-center px-3 py-1 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
            >
              <svg
                className={`w-4 h-4 mr-1 ${isLoading ? 'animate-spin' : ''}`}
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
              Refresh
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
