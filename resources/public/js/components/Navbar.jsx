/**
 * Компонент верхней панели навигации
 * @param {Object} props - Свойства компонента
 * @param {Function} props.onToggleTheme - Обработчик переключения темы
 */
function Navbar({ onToggleTheme }) {
  const [currentTheme, setCurrentTheme] = React.useState(window.theme.get());
  const [user, setUser] = React.useState(null);

  // Проверка аутентификации пользователя
  React.useEffect(() => {
    const checkAuth = async () => {
      try {
        const userData = await window.api.auth.getCurrentUser();
        setUser(userData);
      } catch (error) {
        console.log('Пользователь не аутентифицирован');
      }
    };

    checkAuth();
  }, []);

  // Обработчик выхода из системы
  const handleLogout = async () => {
    try {
      await window.api.auth.logout();
      setUser(null);
      window.location.reload();
    } catch (error) {
      console.error('Ошибка при выходе из системы:', error);
    }
  };

  // Обработчик переключения темы
  const handleThemeToggle = () => {
    const newTheme = window.theme.toggle();
    setCurrentTheme(newTheme);
    if (onToggleTheme) {
      onToggleTheme(newTheme);
    }
  };

  return (
    <nav className="bg-blue-800 dark:bg-gray-800 text-white px-4 py-3 flex justify-between items-center shadow-md">
      <div className="flex items-center">
        <h1 className="text-xl font-bold">Dashboard Light</h1>
        <span className="ml-2 text-sm bg-blue-700 dark:bg-gray-700 px-2 py-1 rounded">K8s Monitor</span>
      </div>

      <div className="flex items-center space-x-4">
        {/* Кнопка переключения темы */}
        <button
          onClick={handleThemeToggle}
          className="bg-blue-700 dark:bg-gray-700 hover:bg-blue-600 dark:hover:bg-gray-600 rounded p-2 transition-colors"
          title={currentTheme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
        >
          {currentTheme === 'dark' ? (
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" fillRule="evenodd" clipRule="evenodd" />
            </svg>
          ) : (
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
            </svg>
          )}
        </button>

        {/* Информация о пользователе */}
        {user ? (
          <div className="flex items-center">
            <span className="mr-2">{user.name || user.username}</span>
            <button
              onClick={handleLogout}
              className="bg-blue-700 dark:bg-gray-700 hover:bg-blue-600 dark:hover:bg-gray-600 rounded py-1 px-3 transition-colors text-sm"
            >
              Выйти
            </button>
          </div>
        ) : (
          <a
            href="/api/auth/login"
            className="bg-blue-700 dark:bg-gray-700 hover:bg-blue-600 dark:hover:bg-gray-600 rounded py-1 px-3 transition-colors text-sm"
          >
            Войти
          </a>
        )}
      </div>
    </nav>
  );
}
