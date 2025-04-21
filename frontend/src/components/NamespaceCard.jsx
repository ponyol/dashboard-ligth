// src/components/NamespaceCard.jsx
/**
 * Компонент карточки неймспейса
 */
export default function NamespaceCard({ namespace, deploymentCount, podCount, onClick, compact = false }) {
  // Определение стилей карточки в зависимости от количества подов и деплойментов
  const getStatusStyles = () => {
    console.log(`Namespace card: deploymentCount=${deploymentCount}, podCount=${podCount}`);
    
    if (deploymentCount === 0) {
      // Серый цвет, если нет деплойментов
      return {
        borderColor: 'border-gray-300 dark:border-gray-600',
        bgColor: 'bg-gray-100 dark:bg-gray-700',
        headerBg: 'bg-gray-300 dark:bg-gray-600',
        status: 'scaled_zero' // Добавим статус для сортировки
      };
    } else if (podCount <= 1) {
      // Если есть деплойменты, но подов 0 или 1 - серый цвет
      return {
        borderColor: 'border-gray-300 dark:border-gray-600',
        bgColor: 'bg-gray-100 dark:bg-gray-700',
        headerBg: 'bg-gray-300 dark:bg-gray-600',
        status: 'scaled_zero'
      };
    } else if (podCount >= deploymentCount) {
      // Зеленый цвет, если количество подов равно или больше количества деплойментов
      return {
        borderColor: 'border-healthy',
        bgColor: 'bg-healthy/10',
        headerBg: 'bg-healthy',
        status: 'healthy'
      };
    } else {
      // Желтый цвет, если количество подов меньше количества деплойментов и больше 1
      return {
        borderColor: 'border-progressing',
        bgColor: 'bg-progressing/10',
        headerBg: 'bg-progressing',
        status: 'progressing'
      };
    }
  };

  // Получение стилей в зависимости от количества подов и деплойментов
  const { borderColor, bgColor, headerBg, status } = getStatusStyles();

  // Если включен компактный режим и статус "healthy", показываем компактную версию
  if (compact && status === 'healthy') {
    return (
      <div 
        className={`rounded-lg overflow-hidden shadow-sm border ${borderColor} transition-all duration-300 ${bgColor} hover:bg-healthy/20 cursor-pointer`}
        onClick={() => {
          // Тут можно добавить обработчик клика для раскрытия карточки если нужно
          if (onClick) onClick(namespace.name);
        }}
      >
        {/* Только заголовок для здоровых неймспейсов в компактном режиме */}
        <div className={`${headerBg} px-4 py-2 text-white flex justify-between items-center`}>
          <h3 className="font-medium text-lg truncate" title={namespace.name}>
            {namespace.name}
          </h3>
          <div className="flex items-center text-xs bg-white/20 px-2 py-0.5 rounded-full">
            <span className="mr-1">{podCount}/{deploymentCount}</span>
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
        </div>
      </div>
    );
  }

  // Стандартный режим отображения
  return (
    <div
      className={`rounded-lg overflow-hidden shadow-sm border ${borderColor} transition-all duration-300 ${bgColor}`}
    >
      {/* Заголовок карточки */}
      <div className={`${headerBg} px-4 py-2 text-white flex justify-between items-center`}>
        <h3 className="font-medium text-lg truncate" title={namespace.name}>
          {namespace.name}
        </h3>
        {status === 'healthy' && (
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        )}
      </div>

      {/* Содержимое карточки */}
      <div className="p-4">
        <div className="grid grid-cols-2 gap-4 text-sm">
          {/* Информация о деплойментах */}
          <div className="bg-white/50 dark:bg-gray-800/50 p-3 rounded-lg text-center">
            <div className="text-gray-600 dark:text-gray-400 text-xs mb-1">Deployments</div>
            <div className="font-bold text-2xl text-gray-900 dark:text-gray-100">{deploymentCount}</div>
          </div>

          {/* Информация о подах */}
          <div className="bg-white/50 dark:bg-gray-800/50 p-3 rounded-lg text-center">
            <div className="text-gray-600 dark:text-gray-400 text-xs mb-1">Pods</div>
            <div className="font-bold text-2xl text-gray-900 dark:text-gray-100">{podCount}</div>
          </div>

          {/* Прогресс-бар соотношения подов к деплойментам - всегда показываем */}
          <div className="col-span-2 mt-2">
            <div className="flex justify-between items-center text-xs text-gray-600 dark:text-gray-400 mb-1">
              <span>Pods / Deployments</span>
              <span>{podCount} / {deploymentCount}</span>
            </div>
            <div className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-full">
              <div
                className={`h-2 rounded-full ${
                  deploymentCount === 0
                    ? 'bg-gray-400 dark:bg-gray-600'
                    : podCount >= deploymentCount
                    ? 'bg-healthy'
                    : podCount > 0
                    ? 'bg-progressing'
                    : 'bg-scaled-zero'
                }`}
                style={{
                  width: `${
                    deploymentCount === 0 
                      ? 0 
                      : Math.min((podCount / deploymentCount) * 100, 100)
                  }%`,
                  minWidth: podCount > 0 ? '5%' : '0%' // Минимальная ширина для видимости
                }}
              ></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}