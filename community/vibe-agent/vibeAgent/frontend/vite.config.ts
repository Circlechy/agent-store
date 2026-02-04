import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': '/src',
    },
  },
  server: {
    host: '0.0.0.0',  // 监听所有网络接口，允许局域网访问
    port: 3000,
    proxy: {
      '/api': {
        // 代理到后端，使用相对路径让 Vite 自动处理
        // 如果设置了 VITE_API_BASE_URL，会在前端代码中使用，这里代理仍然使用 localhost
        // 因为代理是在服务器端执行的，使用 localhost 是正确的
        target: 'http://localhost:8000',
        changeOrigin: true,
        // 注意：代理只在开发环境有效，生产环境需要配置 Nginx 等反向代理
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})

