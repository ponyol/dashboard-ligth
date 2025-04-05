// src/App.jsx
import { useState, useEffect } from 'react'
import Dashboard from './components/Dashboard'
import './App.css'

function App() {
  const [theme, setTheme] = useState('light')

  // Инициализация темы при загрузке
  useEffect(() => {
    const savedTheme = localStorage.getItem('dashboard-light-theme') || 'light'
    setTheme(savedTheme)
    if (savedTheme === 'dark') {
      document.documentElement.classList.add('dark')
    }
  }, [])

  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light'
    setTheme(newTheme)
    localStorage.setItem('dashboard-light-theme', newTheme)
    document.documentElement.classList.toggle('dark')
  }

  return (
    <div className={`${theme} min-h-screen bg-gray-100 dark:bg-gray-900`}>
      <div className="bg-blue-800 dark:bg-gray-800 text-white px-4 py-3 flex justify-between items-center shadow-md">
        <div className="flex items-center">
          <h1 className="text-xl font-bold">Dashboard Light</h1>
          <span className="ml-2 text-sm bg-blue-700 dark:bg-gray-700 px-2 py-1 rounded">K8s Monitor</span>
        </div>

        <button
          onClick={toggleTheme}
          className="bg-blue-700 dark:bg-gray-700 hover:bg-blue-600 dark:hover:bg-gray-600 rounded p-2 transition-colors"
          title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
        >
          {theme === 'dark' ? (
            <svg className="w-full" fill="currentColor" viewBox="0 0 20 20">
              <path d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" fillRule="evenodd" clipRule="evenodd" />
            </svg>
          ) : (
            <svg className="w-full" fill="currentColor" viewBox="0 0 20 20">
              <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
            </svg>
          )}
        </button>
      </div>

      <Dashboard />
    </div>
  )
}

export default App
