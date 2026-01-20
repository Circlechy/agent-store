import { StrictMode, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import { ConfigProvider, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import './index.css'
import App from './App.tsx'
import { useThemeStore } from './store/themeStore'

const RootApp = () => {
  const { isDarkMode } = useThemeStore();

  useEffect(() => {
    if (isDarkMode) {
      document.body.classList.add('dark');
      // Dark Mode: Deep Midnight Blue Mesh Gradient
      document.body.style.background = `
        radial-gradient(at 0% 0%, hsla(253,16%,7%,1) 0, transparent 50%), 
        radial-gradient(at 50% 0%, hsla(225,39%,30%,1) 0, transparent 50%), 
        radial-gradient(at 100% 0%, hsla(339,49%,30%,1) 0, transparent 50%), 
        radial-gradient(at 0% 100%, hsla(339,49%,30%,1) 0, transparent 50%), 
        radial-gradient(at 100% 100%, hsla(225,39%,30%,1) 0, transparent 50%), 
        radial-gradient(at 0% 50%, hsla(339,49%,30%,1) 0, transparent 50%), 
        radial-gradient(at 100% 50%, hsla(225,39%,30%,1) 0, transparent 50%), 
        #141414
      `;
      document.body.style.minHeight = '100vh';
    } else {
      document.body.classList.remove('dark');
      // Light Mode: Soft Pastel Mesh Gradient
      document.body.style.background = `
        radial-gradient(at 0% 0%, hsla(253,16%,72%,1) 0, transparent 50%), 
        radial-gradient(at 50% 0%, hsla(225,39%,85%,1) 0, transparent 50%), 
        radial-gradient(at 100% 0%, hsla(339,49%,85%,1) 0, transparent 50%), 
        radial-gradient(at 0% 100%, hsla(339,49%,85%,1) 0, transparent 50%), 
        radial-gradient(at 100% 100%, hsla(225,39%,85%,1) 0, transparent 50%), 
        radial-gradient(at 0% 50%, hsla(339,49%,85%,1) 0, transparent 50%), 
        radial-gradient(at 100% 50%, hsla(225,39%,85%,1) 0, transparent 50%), 
        #f5f7fa
      `;
      document.body.style.minHeight = '100vh';
    }
  }, [isDarkMode]);

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: isDarkMode ? theme.darkAlgorithm : theme.defaultAlgorithm,
        token: {
          colorPrimary: '#1677ff',
        },
      }}
    >
      <App />
    </ConfigProvider>
  );
};

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RootApp />
  </StrictMode>,
)
