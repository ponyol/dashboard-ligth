import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ command }) => {
  const config = {
    plugins: [react()],
    // Настройки для production сборки
    build: {
      // Это позволяет корректно загружать все ресурсы
      assetsDir: 'assets',
      // Без хэшей в именах файлов, чтобы упростить отслеживание изменений
      rollupOptions: {
        output: {
          entryFileNames: 'assets/[name].js',
          chunkFileNames: 'assets/[name].js',
          assetFileNames: 'assets/[name].[ext]'
        }
      }
    }
  };

  // Добавляем прокси только для режима разработки
  if (command === 'serve') {
    config.server = {
      proxy: {
        // HTTP API proxy
        '/api': {
          target: 'http://localhost:3000',
          changeOrigin: true,
        },
        // WebSocket proxy
        '/ws': {
          target: 'ws://localhost:8765',
          ws: true,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/ws/, ''),
        },
      },
    };
  }

  return config;
});