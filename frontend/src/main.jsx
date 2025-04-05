import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './index.css';

// Инициализация темы из localStorage
const initializeTheme = () => {
  if (
    localStorage.theme === 'dark' ||
    (!('theme' in localStorage) &&
      window.matchMedia('(prefers-color-scheme: dark)').matches)
  ) {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
};

// Вызываем инициализацию темы перед рендерингом
initializeTheme();

// Рендерим приложение
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>
);
