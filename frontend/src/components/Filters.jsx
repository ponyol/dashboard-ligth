// src/components/Filters.jsx
import { useState, useEffect, useRef } from 'react';

/**
 * Компонент фильтров для дашборда с улучшенным поиском неймспейсов
 */
export default function Filters({
  namespaces,
  selectedNamespace,
  onNamespaceChange,
  onRefresh,
  isLoading,
  isConnected = true, // Параметр для определения состояния WebSocket
  showNamespaceFilter = true // По умолчанию показываем фильтр неймспейсов
}) {
  // Состояние для поиска
  const [searchTerm, setSearchTerm] = useState('');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);
  const searchInputRef = useRef(null);
  
  // Получение отфильтрованных неймспейсов по поисковому запросу
  const getFilteredNamespaces = () => {
    if (!namespaces || !Array.isArray(namespaces)) {
      return [];
    }
    
    // Если поисковый запрос пустой, возвращаем все неймспейсы
    if (!searchTerm.trim()) {
      return namespaces;
    }
    
    // Фильтруем по вхождению поискового запроса в имя неймспейса (регистронезависимо)
    const normalizedSearch = searchTerm.toLowerCase().trim();
    return namespaces.filter(ns => 
      ns && ns.name && ns.name.toLowerCase().includes(normalizedSearch)
    );
  };
  
  // Отфильтрованные неймспейсы
  const filteredNamespaces = getFilteredNamespaces();
  
  // Обработчик изменения выбранного неймспейса
  const handleNamespaceChange = (namespaceName) => {
    onNamespaceChange(namespaceName);
    setIsDropdownOpen(false);
    setSearchTerm('');
  };
  
  // Обработчик изменения поискового запроса
  const handleSearchChange = (e) => {
    setSearchTerm(e.target.value);
    if (!isDropdownOpen) {
      setIsDropdownOpen(true);
    }
  };
  
  // Обработчик клика на поле ввода
  const handleSearchClick = () => {
    setIsDropdownOpen(true);
  };
  
  // Обработчик нажатия клавиш в поле поиска
  const handleSearchKeyDown = (e) => {
    // Если нажат Enter, выбираем первый результат поиска
    if (e.key === 'Enter' && filteredNamespaces.length > 0) {
      handleNamespaceChange(filteredNamespaces[0].name);
      e.preventDefault();
    }
    
    // Если нажат Esc, закрываем выпадающий список
    if (e.key === 'Escape') {
      setIsDropdownOpen(false);
      e.preventDefault();
    }
    
    // Если нажаты стрелки вверх/вниз, то можно добавить навигацию по списку
  };
  
  // Функция для отображения текста с подсветкой совпадения
  const highlightMatches = (text) => {
    if (!searchTerm.trim() || !text) {
      return text;
    }
    
    try {
      // Находим индекс совпадения (регистронезависимо)
      const index = text.toLowerCase().indexOf(searchTerm.toLowerCase().trim());
      
      if (index >= 0) {
        // Извлекаем часть строки до, внутри и после совпадения
        const before = text.substring(0, index);
        const match = text.substring(index, index + searchTerm.length);
        const after = text.substring(index + searchTerm.length);
        
        return (
          <>
            {before}
            <span className="bg-yellow-100 dark:bg-yellow-800/50 font-medium">
              {match}
            </span>
            {after}
          </>
        );
      }
    } catch (err) {
      console.error('Error highlighting matches:', err);
    }
    
    return text;
  };
  
  // Закрытие выпадающего списка при клике вне него
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsDropdownOpen(false);
      }
    };
    
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);
  
  // Фокус на поле поиска при открытии выпадающего списка
  useEffect(() => {
    if (isDropdownOpen && searchInputRef.current) {
      searchInputRef.current.focus();
    }
  }, [isDropdownOpen]);

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm mb-3">
      <div className="p-3">
        <h2 className="text-md font-semibold text-gray-700 dark:text-gray-200 mb-2">Filters</h2>

        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between">
          {/* Селектор неймспейса с поиском - показываем только если showNamespaceFilter=true */}
          {showNamespaceFilter && (
            <div className="flex-grow mb-2 sm:mb-0 sm:mr-3 w-full sm:w-auto" ref={dropdownRef}>
              <div className="relative">
                {/* Поле ввода для поиска неймспейсов */}
                <div className="relative">
                  <input
                    ref={searchInputRef}
                    type="text"
                    value={searchTerm}
                    onChange={handleSearchChange}
                    onClick={handleSearchClick}
                    onKeyDown={handleSearchKeyDown}
                    placeholder={searchTerm ? "Search namespaces..." : selectedNamespace || "Search namespaces..."}
                    className="block w-full pl-10 pr-10 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  />
                  
                  {/* Иконка поиска слева */}
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <svg 
                      className="h-4 w-4 text-gray-400" 
                      fill="none" 
                      stroke="currentColor" 
                      viewBox="0 0 24 24"
                    >
                      <path 
                        strokeLinecap="round" 
                        strokeLinejoin="round" 
                        strokeWidth="2" 
                        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" 
                      />
                    </svg>
                  </div>
                  
                  {/* Иконка очистки или стрелки справа */}
                  <div className="absolute inset-y-0 right-0 pr-3 flex items-center">
                    {searchTerm ? (
                      <button 
                        onClick={() => setSearchTerm('')}
                        className="text-gray-400 hover:text-gray-500 focus:outline-none"
                      >
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    ) : (
                      <svg 
                        className="h-4 w-4 text-gray-400" 
                        fill="none" 
                        stroke="currentColor" 
                        viewBox="0 0 24 24"
                      >
                        <path 
                          strokeLinecap="round" 
                          strokeLinejoin="round" 
                          strokeWidth="2" 
                          d="M19 9l-7 7-7-7" 
                        />
                      </svg>
                    )}
                  </div>
                </div>
                
                {/* Выпадающий список неймспейсов */}
                {isDropdownOpen && (
                  <div className="absolute z-10 mt-1 w-full bg-white dark:bg-gray-700 shadow-lg rounded-md border border-gray-300 dark:border-gray-600 max-h-60 overflow-auto">
                    {/* Опция "All Namespaces" */}
                    <div 
                      className={`px-3 py-2 cursor-pointer text-sm hover:bg-gray-100 dark:hover:bg-gray-600 ${selectedNamespace === '' ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 font-medium' : ''}`}
                      onClick={() => handleNamespaceChange('')}
                    >
                      All Namespaces
                    </div>
                    
                    {/* Разделитель с информацией о поиске */}
                    {searchTerm && (
                      <div className="px-3 py-1 text-xs text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-800/50">
                        {filteredNamespaces.length > 0 
                          ? `Found ${filteredNamespaces.length} namespace${filteredNamespaces.length !== 1 ? 's' : ''} for "${searchTerm}"`
                          : `No results for "${searchTerm}"`
                        }
                      </div>
                    )}
                    
                    {/* Отфильтрованные неймспейсы */}
                    {filteredNamespaces.length > 0 ? (
                      <div>
                        {filteredNamespaces.map((ns) => (
                          <div
                            key={ns.name}
                            className={`px-3 py-2 cursor-pointer text-sm hover:bg-gray-100 dark:hover:bg-gray-600 ${selectedNamespace === ns.name ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 font-medium' : ''}`}
                            onClick={() => handleNamespaceChange(ns.name)}
                          >
                            {searchTerm ? highlightMatches(ns.name) : ns.name}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
                        No namespaces found
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Кнопка переподключения - показываем только если WebSocket не подключен */}
          {!isConnected && (
            <div className={showNamespaceFilter ? "" : "ml-auto"}>
              <button
                onClick={onRefresh}
                disabled={isLoading}
                className="flex items-center px-3 py-1 text-sm bg-yellow-600 hover:bg-yellow-700 text-white rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:ring-offset-2 disabled:opacity-50"
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
                Reconnect
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}