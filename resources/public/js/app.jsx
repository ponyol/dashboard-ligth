/**
 * Основной компонент приложения
 */
function App() {
  const [activeTab, setActiveTab] = React.useState('status');
  const [theme, setTheme] = React.useState(window.theme.get());

  // Обработчик смены таба
  const handleTabChange = (tabId) => {
    setActiveTab(tabId);
  };

  // Обработчик смены темы
  const handleThemeChange = (newTheme) => {
    setTheme(newTheme);
  };

  // Определение контента в зависимости от активного таба
  const renderContent = () => {
    switch (activeTab) {
      case 'status':
        return <Dashboard />;
      case 'pods':
        return (
          <div className="p-6">
            <h2 className="text-xl font-medium mb-4">Pods</h2>
            <p className="text-gray-600 dark:text-gray-400">
              This page is under development. Please check back later.
            </p>
          </div>
        );
      case 'settings':
        return (
          <div className="p-6">
            <h2 className="text-xl font-medium mb-4">Settings</h2>
            <p className="text-gray-600 dark:text-gray-400">
              This page is under development. Please check back later.
            </p>
          </div>
        );
      default:
        return <Dashboard />;
    }
  };

  return (
    <div className={`${theme}`}>
      <Navbar onToggleTheme={handleThemeChange} />

      <div className="flex min-h-screen pt-14 bg-gray-50 dark:bg-gray-900 transition-colors duration-300">
        <Sidebar
          activeTab={activeTab}
          onTabChange={handleTabChange}
        />

        <div className="ml-56 flex-grow transition-all duration-300">
          {renderContent()}
        </div>
      </div>
    </div>
  );
}

// Рендеринг приложения при загрузке DOM
// document.addEventListener('DOMContentLoaded', () => {
//   ReactDOM.render(<App />, document.getElementById('root'));
// });
// В конце app.jsx:
// Рендеринг приложения при загрузке DOM
document.addEventListener('DOMContentLoaded', () => {
  try {
    console.log("Пытаемся рендерить App");
    const rootElement = document.getElementById('root');
    console.log("Root element:", rootElement);

    ReactDOM.render(
      React.createElement(App),
      rootElement
    );
    console.log("Рендеринг завершен");
  } catch (error) {
    console.error("Ошибка при рендеринге:", error);
  }
});
