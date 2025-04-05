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
  isLoading
}) {
  // Обработчик изменения выбранного неймспейса
  const handleNamespaceChange = (e) => {
    onNamespaceChange(e.target.value);
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm mb-6">
      <div className="p-4">
        <h2 className="text-lg font-semibold text-gray-700 dark:text-gray-200 mb-3">Filters</h2>

        <div className="flex items-center justify-between mb-4">
          {/* Селектор неймспейса */}
          <div className="flex-grow mr-4">
            <label className="block text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">
              Namespace
            </label>
            <div className="relative">
              <select
                value={selectedNamespace}
                onChange={handleNamespaceChange}
                className="block w-full pl-3 pr-10 py-2 text-base border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
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

          {/* Кнопка обновления */}
          <div>
            <button
              onClick={onRefresh}
              disabled={isLoading}
              className="flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
            >
              <svg
                className={`w-5 h-5 mr-2 ${isLoading ? 'animate-spin' : ''}`}
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
