import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  server: {
    port: Number(process.env.VITE_PORT) || 5173,
    strictPort: false
  },
  plugins: [vue()]
});
