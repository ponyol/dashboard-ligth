import { useEffect, useRef } from 'react';

/**
 * Хук для периодического выполнения функций
 * @param {Function} callback - Функция для выполнения
 * @param {number} delay - Интервал в миллисекундах
 */
export default function useInterval(callback, delay) {
  const savedCallback = useRef();

  // Сохраняем новый колбэк
  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  // Устанавливаем интервал
  useEffect(() => {
    function tick() {
      savedCallback.current();
    }

    if (delay !== null) {
      const id = setInterval(tick, delay);
      return () => clearInterval(id);
    }
  }, [delay]);
}
