/**
 * Хук для периодического выполнения функций
 * @param {Function} callback - Функция для выполнения
 * @param {number} delay - Интервал в миллисекундах
 */
function useInterval(callback, delay) {
  const savedCallback = React.useRef();

  // Сохраняем новый колбэк
  React.useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  // Устанавливаем интервал
  React.useEffect(() => {
    function tick() {
      savedCallback.current();
    }

    if (delay !== null) {
      const id = setInterval(tick, delay);
      return () => clearInterval(id);
    }
  }, [delay]);
}
