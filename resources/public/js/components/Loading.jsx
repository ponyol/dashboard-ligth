/**
 * Компонент индикатора загрузки
 * @param {Object} props - Свойства компонента
 * @param {string} props.text - Текст сообщения загрузки
 */
function Loading({ text = "Loading..." }) {
  return (
    <div className="flex flex-col items-center justify-center py-12">
      <svg
        className="w-10 h-10 text-blue-600 dark:text-blue-400 animate-spin"
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
      <p className="mt-3 text-gray-600 dark:text-gray-400">{text}</p>
    </div>
  );
}
