/**
 * Компонент боковой панели
 * @param {Object} props - Свойства компонента
 * @param {string} props.activeTab - Активный таб
 * @param {Function} props.onTabChange - Обработчик смены таба
 */
function Sidebar({ activeTab, onTabChange }) {
  const [collapsed, setCollapsed] = React.useState(false);

  // Меню навигации
  const menu = [
    { id: 'status', label: 'Status', icon: 'M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2' },
    { id: 'pods', label: 'Pods', icon: 'M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4' },
    { id: 'settings', label: 'Settings', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z' },
  ];

  // Функция для отображения иконки
  const renderIcon = (pathData) => (
    <svg className={`w-5 h-5 ${collapsed ? 'mx-auto' : 'mr-3'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d={pathData}></path>
    </svg>
  );

  return (
    <div
      className={`fixed left-0 top-14 h-full bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 shadow-md transition-all duration-300 ${
        collapsed ? 'w-16' : 'w-56'
      }`}
    >
      {/* Кнопка сворачивания/разворачивания */}
      <button
        className="absolute -right-3 top-10 bg-white dark:bg-gray-800 rounded-full p-1 shadow-md"
        onClick={() => setCollapsed(!collapsed)}
      >
        <svg
          className={`w-4 h-4 text-gray-600 dark:text-gray-400 transform transition-transform ${collapsed ? 'rotate-0' : 'rotate-180'}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7"></path>
        </svg>
      </button>

      {/* Меню навигации */}
      <nav className="py-6">
        <ul>
          {menu.map(item => (
            <li key={item.id}>
              <button
                className={`w-full flex items-center py-3 px-4 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors ${
                  activeTab === item.id ? 'text-blue-600 dark:text-blue-400 font-medium bg-blue-50 dark:bg-gray-700' : ''
                }`}
                onClick={() => onTabChange(item.id)}
              >
                {renderIcon(item.icon)}
                {!collapsed && <span className="sidebar-text">{item.label}</span>}
              </button>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}
