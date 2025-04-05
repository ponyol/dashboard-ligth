/**
 * Компонент индикатора загрузки
 */
export default function Loading({ text = "Loading...", fullScreen = false }) {
  const loadingContent = (
    <div className="flex flex-col items-center justify-center p-8">
      <div className="relative">
        <div className="h-16 w-16 rounded-full border-4 border-gray-200 dark:border-gray-700"></div>
        <div className="h-16 w-16 rounded-full border-4 border-blue-600 dark:border-blue-400 border-t-transparent animate-spin absolute top-0 left-0"></div>
      </div>
      <p className="mt-4 text-lg text-gray-600 dark:text-gray-400">{text}</p>
    </div>
  );

  if (fullScreen) {
    return (
      <div className="fixed inset-0 bg-white/80 dark:bg-gray-900/80 flex items-center justify-center z-50">
        {loadingContent}
      </div>
    );
  }

  return loadingContent;
}
