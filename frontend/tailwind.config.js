/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class', // Поддержка темной темы
  theme: {
    extend: {
      colors: {
        // Цвета для статусов Deployments согласно ТЗ
        'healthy': '#28a745',      // Зеленый (Running/Healthy)
        'progressing': '#ffc107',  // Желтый/Оранжевый (Progressing/Unhealthy)
        'scaled-zero': '#6c757d',  // Серый/Синий (Scaled to Zero/Idle)
        'error': '#dc3545',        // Красный (Error)

        // Цвета для статусов StatefulSets (такие же, как для Deployments)
        'statefulset-healthy': '#28a745',      // Зеленый (Running/Healthy)
        'statefulset-progressing': '#ffc107',  // Желтый/Оранжевый (Progressing/Unhealthy)
        'statefulset-scaled-zero': '#6c757d',  // Серый/Синий (Scaled to Zero/Idle)
        'statefulset-error': '#dc3545',        // Красный (Error)

        // Цвета для статусов Pods согласно ТЗ
        'pod-running': '#28a745',    // Зеленый
        'pod-succeeded': '#17a2b8',  // Информационный синий
        'pod-pending': '#ffc107',    // Желтый
        'pod-failed': '#dc3545',     // Красный
        'pod-terminating': '#6c757d' // Серый
      },
      boxShadow: {
        'card': '0 2px 4px rgba(0, 0, 0, 0.05), 0 1px 2px rgba(0, 0, 0, 0.1)',
      }
    },
  },
  plugins: [],
}
