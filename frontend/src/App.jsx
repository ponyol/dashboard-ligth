// src/App.jsx
import { useState, useEffect } from 'react';
import Dashboard from './components/Dashboard';
import Sidebar from './components/Sidebar';
import './App.css';

function App() {
  const [theme, setTheme] = useState('light');
  const [menuCollapsed, setMenuCollapsed] = useState(true);

  // Инициализация темы при загрузке
  useEffect(() => {
    const savedTheme = localStorage.getItem('dashboard-light-theme') || 'light';
    setTheme(savedTheme);
    if (savedTheme === 'dark') {
      document.documentElement.classList.add('dark');
    }

    // Загрузка состояния меню
    const savedMenuState = localStorage.getItem('dashboard-light-menu') === 'collapsed';
    setMenuCollapsed(savedMenuState);
  }, []);

  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
    localStorage.setItem('dashboard-light-theme', newTheme);
    document.documentElement.classList.toggle('dark');
  };

  const toggleMenu = () => {
    const newState = !menuCollapsed;
    setMenuCollapsed(newState);
    localStorage.setItem('dashboard-light-menu', newState ? 'collapsed' : 'expanded');
  };

  return (
    <div className={`${theme} full-screen-app flex flex-col h-screen w-screen m-0 p-0 bg-gray-100 dark:bg-gray-900 overflow-hidden`}>
      {/* Верхний заголовок */}
      <div className="bg-blue-800 dark:bg-gray-800 text-white px-4 py-2 flex justify-between items-center shadow-md z-10 w-full">
        <div className="flex items-center">
          <button
            onClick={toggleMenu}
            className="mr-3 text-white hover:text-blue-200 dark:hover:text-gray-300"
            aria-label="Toggle menu"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <h1 className="text-xl font-bold">Dashboard Light</h1>
          <span className="ml-2 text-sm bg-blue-700 dark:bg-gray-700 px-2 py-1 rounded">K8s Monitor</span>
        </div>

        <button
          onClick={toggleTheme}
          className="bg-blue-700 dark:bg-gray-700 hover:bg-blue-600 dark:hover:bg-gray-600 rounded p-2 transition-colors"
          title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
        >
          {theme === 'dark' ? (
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" fillRule="evenodd" clipRule="evenodd" />
            </svg>
          ) : (
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
            </svg>
          )}
        </button>
      </div>

      {/* Основной контент с сайдбаром и панелью содержимого */}
      <div className="flex flex-1 overflow-hidden w-full">
        <Sidebar collapsed={menuCollapsed} />
        <main className="flex-1 w-full overflow-x-hidden overflow-y-auto bg-gray-100 dark:bg-gray-900">
          <Dashboard />
        </main>
      </div>
    </div>
  );
}

export default App;
