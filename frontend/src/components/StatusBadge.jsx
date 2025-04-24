/**
 * Компонент для отображения статуса с цветовой индикацией
 */
export default function StatusBadge({ status, type = 'deployment' }) {
  // Конфигурация статусов для различных типов ресурсов
  const statusConfig = {
    deployment: {
      healthy: {
        color: 'bg-healthy text-white',
        label: 'Healthy',
        icon: (
          <svg className="w-3.5 h-3.5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
          </svg>
        )
      },
      progressing: {
        color: 'bg-progressing text-gray-900',
        label: 'Progressing',
        icon: (
          <svg className="w-3.5 h-3.5 mr-1 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        )
      },
      scaled_zero: {
        color: 'bg-scaled-zero text-white',
        label: 'Scaled to Zero',
        icon: (
          <svg className="w-3.5 h-3.5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M18 12H6" />
          </svg>
        )
      },
      error: {
        color: 'bg-error text-white',
        label: 'Error',
        icon: (
          <svg className="w-3.5 h-3.5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        )
      }
    },
    statefulset: {
      healthy: {
        color: 'bg-healthy text-white',
        label: 'Healthy',
        icon: (
          <svg className="w-3.5 h-3.5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
          </svg>
        )
      },
      progressing: {
        color: 'bg-progressing text-gray-900',
        label: 'Progressing',
        icon: (
          <svg className="w-3.5 h-3.5 mr-1 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        )
      },
      scaled_zero: {
        color: 'bg-scaled-zero text-white',
        label: 'Scaled to Zero',
        icon: (
          <svg className="w-3.5 h-3.5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M18 12H6" />
          </svg>
        )
      },
      error: {
        color: 'bg-error text-white',
        label: 'Error',
        icon: (
          <svg className="w-3.5 h-3.5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        )
      }
    },
    pod: {
      running: {
        color: 'bg-pod-running text-white',
        label: 'Running',
        icon: (
          <svg className="w-3.5 h-3.5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        )
      },
      succeeded: {
        color: 'bg-pod-succeeded text-white',
        label: 'Succeeded',
        icon: (
          <svg className="w-3.5 h-3.5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        )
      },
      pending: {
        color: 'bg-pod-pending text-gray-900',
        label: 'Pending',
        icon: (
          <svg className="w-3.5 h-3.5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        )
      },
      failed: {
        color: 'bg-pod-failed text-white',
        label: 'Failed',
        icon: (
          <svg className="w-3.5 h-3.5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        )
      },
      terminating: {
        color: 'bg-pod-terminating text-white',
        label: 'Terminating',
        icon: (
          <svg className="w-3.5 h-3.5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        )
      }
    }
  };

  // Получение конфигурации для конкретного статуса
  // Нормализуем статус для подов (приводим к lowercase и обрабатываем типичные варианты статусов Kubernetes)
  let normalizedStatus = status?.toLowerCase() || 'unknown';

  if (type === 'pod') {
    // Преобразуем все возможные статусы подов в стандартизированные
    if (normalizedStatus.includes('run')) normalizedStatus = 'running';
    else if (normalizedStatus.includes('pend')) normalizedStatus = 'pending';
    else if (normalizedStatus.includes('succ')) normalizedStatus = 'succeeded';
    else if (normalizedStatus.includes('fail') || normalizedStatus.includes('crash') || normalizedStatus.includes('error')) normalizedStatus = 'failed';
    else if (normalizedStatus.includes('term')) normalizedStatus = 'terminating';

    // console.log(`Original pod status: ${status} => normalized: ${normalizedStatus}`);
  }

  const config = statusConfig[type]?.[normalizedStatus] || {
    color: 'bg-gray-500 text-white',
    label: status || 'Unknown',
    icon: (
      <svg className="w-3.5 h-3.5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    )
  };

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.color}`}>
      {config.icon}
      {config.label}
    </span>
  );
}
