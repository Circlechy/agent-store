import React, { useState } from 'react';
import { Layout, Button, theme } from 'antd';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  MessageOutlined,
  PictureOutlined,
  CloudUploadOutlined,
  HomeOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  GithubOutlined,
  BulbOutlined,
  BulbFilled,
  SunOutlined,
  MoonOutlined,
  CameraFilled,
  ProjectOutlined,
} from '@ant-design/icons';
import { useThemeStore } from '../../store/themeStore';

const { Header, Sider, Content } = Layout;

const MainLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const { isDarkMode, toggleTheme } = useThemeStore();
  const {
    token: { colorBgContainer, borderRadiusLG },
  } = theme.useToken();
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    {
      key: '/',
      icon: <HomeOutlined />,
      label: '首页',
    },
    {
      key: '/chat',
      icon: <MessageOutlined />,
      label: '智能对话',
    },
    {
      key: '/gallery',
      icon: <PictureOutlined />,
      label: '图片画廊',
    },
    {
      key: '/upload',
      icon: <CloudUploadOutlined />,
      label: '上传图片',
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh', background: 'transparent' }}>
      <Sider 
        trigger={null} 
        collapsible 
        collapsed={collapsed} 
        theme={isDarkMode ? 'dark' : 'light'} 
        width={220}
        style={{
          boxShadow: '0 4px 30px rgba(0,0,0,0.1)',
          zIndex: 10,
          height: '100vh',
          position: 'sticky',
          top: 0,
          left: 0,
          backgroundColor: isDarkMode ? 'rgba(20, 20, 20, 0.65)' : 'rgba(255, 255, 255, 0.65)',
          backdropFilter: 'blur(20px) saturate(180%)',
          WebkitBackdropFilter: 'blur(20px) saturate(180%)',
          borderRight: isDarkMode ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid rgba(255, 255, 255, 0.4)',
          transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'transparent' }}>
          <div style={{ 
            height: 80, 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            paddingTop: 12,
            marginBottom: 8,
            background: 'transparent'
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '8px 16px',
              borderRadius: 16,
              background: isDarkMode ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.3)', // Increased opacity for glass effect
              border: isDarkMode ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(255,255,255,0.4)',
              transition: 'all 0.3s ease',
              cursor: 'pointer',
              backdropFilter: 'blur(12px)', // Increased blur
              WebkitBackdropFilter: 'blur(12px)',
              boxShadow: isDarkMode ? '0 4px 12px rgba(0,0,0,0.2)' : '0 4px 12px rgba(0,0,0,0.05)' // Subtle shadow
            }}
            onClick={() => navigate('/')}
            >
                <div style={{
                    width: 32,
                    height: 32,
                    background: 'linear-gradient(135deg, #1677ff 0%, #36cfc9 100%)',
                    borderRadius: 10,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    boxShadow: '0 4px 10px rgba(22, 119, 255, 0.3)'
                }}>
                    <CameraFilled style={{ fontSize: 18, color: '#fff' }} />
                </div>
                
                {!collapsed && (
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <h1 style={{ 
                            fontSize: '1.1rem', 
                            fontWeight: '800', 
                            margin: 0,
                            lineHeight: 1.2,
                            background: isDarkMode 
                                ? 'linear-gradient(90deg, #fff 0%, #e6f4ff 100%)' 
                                : 'linear-gradient(90deg, #1677ff 0%, #36cfc9 100%)',
                            WebkitBackgroundClip: 'text',
                            WebkitTextFillColor: 'transparent',
                            letterSpacing: '-0.5px'
                        }}>
                            智能相册
                        </h1>
                        <span style={{ 
                            fontSize: '0.65rem', 
                            color: isDarkMode ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.45)',
                            fontWeight: 600,
                            letterSpacing: '1px',
                            textTransform: 'uppercase'
                        }}>
                            AI Powered
                        </span>
                    </div>
                )}
            </div>
          </div>
          
          {/* Custom Navigation Menu */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '16px 12px' }}>
            {menuItems.map((item) => {
              const isActive = location.pathname === item.key;
              return (
                <div
                  key={item.key}
                  onClick={() => navigate(item.key)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: collapsed ? 'center' : 'flex-start',
                    padding: collapsed ? '12px 0' : '12px 16px',
                    marginBottom: 8,
                    cursor: 'pointer',
                    borderRadius: 16,
                    backgroundColor: isActive 
                      ? (isDarkMode ? 'rgba(255, 255, 255, 0.1)' : '#e6f4ff')
                      : 'transparent',
                    color: isActive
                      ? (isDarkMode ? '#fff' : '#1677ff')
                      : (isDarkMode ? 'rgba(255, 255, 255, 0.65)' : 'rgba(0, 0, 0, 0.88)'),
                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    position: 'relative',
                    overflow: 'hidden',
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive) {
                      e.currentTarget.style.backgroundColor = isDarkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.02)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) {
                      e.currentTarget.style.backgroundColor = 'transparent';
                    }
                  }}
                >
                  {/* Active Indicator (Glow effect) */}
                  {isActive && (
                    <div style={{
                      position: 'absolute',
                      left: 0,
                      top: 0,
                      bottom: 0,
                      width: 4,
                      backgroundColor: isDarkMode ? '#fff' : '#1677ff',
                      borderRadius: '0 4px 4px 0',
                      opacity: collapsed ? 0 : 1, // Hide sidebar line in collapsed mode for cleaner look
                    }} />
                  )}
                  
                  <span style={{ 
                    fontSize: 20, 
                    display: 'flex', 
                    alignItems: 'center',
                    color: isActive ? (isDarkMode ? '#fff' : '#1677ff') : 'inherit',
                    transition: 'color 0.3s',
                    marginRight: collapsed ? 0 : 12,
                    filter: isActive ? 'drop-shadow(0 2px 4px rgba(22, 119, 255, 0.2))' : 'none'
                  }}>
                    {item.icon}
                  </span>
                  
                  {!collapsed && (
                    <span style={{ 
                      fontSize: 15, 
                      fontWeight: isActive ? 600 : 400,
                      whiteSpace: 'nowrap',
                      opacity: collapsed ? 0 : 1,
                      transition: 'opacity 0.2s',
                    }}>
                      {item.label}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
          
          {/* GitHub Link & Architecture */}
          <div style={{
            padding: '16px',
            borderTop: isDarkMode ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid rgba(0, 0, 0, 0.04)',
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
            justifyContent: collapsed ? 'center' : 'flex-start',
            background: 'transparent'
          }}>
            <Button
              type="text"
              icon={<ProjectOutlined style={{ fontSize: 18 }} />}
              onClick={() => navigate('/architecture')}
              block={!collapsed}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: collapsed ? 'center' : 'flex-start',
                height: 48,
                color: isDarkMode ? 'rgba(255, 255, 255, 0.65)' : 'rgba(0, 0, 0, 0.65)'
              }}
            >
              {!collapsed && <span style={{ marginLeft: 8 }}>产品架构</span>}
            </Button>
            
            <Button
              type="text"
              icon={<GithubOutlined style={{ fontSize: 18 }} />}
              onClick={() => window.open('https://github.com/harbour-z/ImgEmbedding2VecDB', '_blank')}
              block={!collapsed}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: collapsed ? 'center' : 'flex-start',
                height: 48,
                color: isDarkMode ? 'rgba(255, 255, 255, 0.65)' : 'rgba(0, 0, 0, 0.65)'
              }}
            >
              {!collapsed && <span style={{ marginLeft: 8 }}>GitHub 仓库</span>}
            </Button>
          </div>
        </div>
      </Sider>
      <Layout style={{ background: 'transparent' }}>
        <Header style={{ 
            padding: '0 24px 0 0', 
            // Remove background: colorBgContainer to allow transparency
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between',
            position: 'sticky',
            top: 0,
            zIndex: 9,
            boxShadow: '0 4px 30px rgba(0, 0, 0, 0.03)',
            backdropFilter: 'blur(20px) saturate(180%)',
            WebkitBackdropFilter: 'blur(20px) saturate(180%)',
            backgroundColor: isDarkMode ? 'rgba(20, 20, 20, 0.65)' : 'rgba(255, 255, 255, 0.65)',
            borderBottom: isDarkMode ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid rgba(255, 255, 255, 0.4)',
            transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', paddingLeft: 16 }}>
              <Button
                type="text"
                icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
                onClick={() => setCollapsed(!collapsed)}
                style={{
                  fontSize: '16px',
                  width: 64,
                  height: 64,
                }}
              />
          </div>
          
          <div 
            onClick={toggleTheme}
            style={{
              width: 68,
              height: 32,
              borderRadius: 20,
              backgroundColor: isDarkMode ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.06)',
              border: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.06)'}`,
              position: 'relative',
              cursor: 'pointer',
              transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
              display: 'flex',
              alignItems: 'center',
              padding: 2,
              marginRight: 24,
              boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.05)',
              userSelect: 'none'
            }}
            title={isDarkMode ? "切换到亮色模式" : "切换到暗黑模式"}
          >
            {/* 滑块 */}
            <div style={{
              width: 26,
              height: 26,
              borderRadius: '50%',
              backgroundColor: isDarkMode ? '#141414' : '#fff',
              transform: isDarkMode ? 'translateX(36px)' : 'translateX(0)',
              transition: 'all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)', // 使用弹性曲线
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
              zIndex: 2,
              position: 'relative' // 确保滑块在图标之上
            }}>
               <div style={{ position: 'relative', width: '100%', height: '100%' }}>
                  <SunOutlined style={{
                      position: 'absolute',
                      top: '50%',
                      left: '50%',
                      transform: `translate(-50%, -50%) scale(${isDarkMode ? 0 : 1})`,
                      opacity: isDarkMode ? 0 : 1,
                      transition: 'all 0.3s',
                      color: '#faad14',
                      fontSize: 14
                  }} />
                  <MoonOutlined style={{
                      position: 'absolute',
                      top: '50%',
                      left: '50%',
                      transform: `translate(-50%, -50%) scale(${isDarkMode ? 1 : 0})`,
                      opacity: isDarkMode ? 1 : 0,
                      transition: 'all 0.3s',
                      color: '#fff',
                      fontSize: 14
                  }} />
               </div>
            </div>
          </div>
        </Header>
        <Content
          style={{
            margin: '24px 16px',
            padding: 24,
            minHeight: 280,
            background: isDarkMode ? 'rgba(30, 30, 30, 0.6)' : 'rgba(255, 255, 255, 0.6)',
            backdropFilter: 'blur(20px) saturate(180%)',
            WebkitBackdropFilter: 'blur(20px) saturate(180%)',
            border: isDarkMode ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid rgba(255, 255, 255, 0.4)',
            boxShadow: isDarkMode ? '0 8px 32px 0 rgba(0, 0, 0, 0.37)' : '0 8px 32px 0 rgba(31, 38, 135, 0.07)',
            borderRadius: borderRadiusLG,
            overflow: 'auto',
            transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;
