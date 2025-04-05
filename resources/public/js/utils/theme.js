/**
 * Модуль для управления темой приложения
 */

// Ключ для сохранения темы в localStorage
const THEME_KEY = 'dashboard-light-theme';

/**
 * Класс для темной темы
 * @type {string}
 */
const DARK_CLASS = 'dark';

/**
 * Получение текущей темы
 * @returns {string} - 'dark' или 'light'
 */
const getTheme = () => {
  // Проверка localStorage
  const savedTheme = localStorage.getItem(THEME_KEY);

  if (savedTheme) {
    return savedTheme;
  }

  // Проверка системных настроек
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return 'dark';
  }

  return 'light';
};

/**
 * Установка темы
 * @param {string} theme - 'dark' или 'light'
 */
const setTheme = (theme) => {
  if (theme === 'dark') {
    document.documentElement.classList.add(DARK_CLASS);
  } else {
    document.documentElement.classList.remove(DARK_CLASS);
  }

  // Сохранение в localStorage
  localStorage.setItem(THEME_KEY, theme);
};

/**
 * Переключение темы
 * @returns {string} - Новая тема ('dark' или 'light')
 */
const toggleTheme = () => {
  const currentTheme = getTheme();
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

  setTheme(newTheme);
  return newTheme;
};

// Инициализация темы при загрузке
window.addEventListener('DOMContentLoaded', () => {
  setTheme(getTheme());
});

// Экспорт функций для использования в компонентах
window.theme = {
  get: getTheme,
  set: setTheme,
  toggle: toggleTheme,
};
