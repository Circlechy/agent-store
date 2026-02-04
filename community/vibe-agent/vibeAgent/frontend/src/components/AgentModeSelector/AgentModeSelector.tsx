import React from 'react'
import { Button, Space } from 'antd'
import { RobotOutlined, ApartmentOutlined, TeamOutlined } from '@ant-design/icons'

export type AgentMode = 'agent' | 'workflow' | 'multi_agent'

interface AgentModeSelectorProps {
  value: AgentMode
  onChange: (mode: AgentMode) => void
  disabled?: boolean
}

const AgentModeSelector: React.FC<AgentModeSelectorProps> = ({
  value,
  onChange,
  disabled = false
}) => {
  const modes: Array<{ 
    key: AgentMode
    label: string
    icon: React.ReactNode
    description: string
    gradient: string
    hoverGradient: string
    shadowColor: string
  }> = [
    {
      key: 'agent',
      label: 'Agent',
      icon: <RobotOutlined />,
      description: '智能助手',
      // 柔和的蓝紫色渐变，与主题色协调
      gradient: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
      hoverGradient: 'linear-gradient(135deg, #7c3aed 0%, #a855f7 100%)',
      shadowColor: 'rgba(99, 102, 241, 0.25)'
    },
    {
      key: 'workflow',
      label: 'Workflow',
      icon: <ApartmentOutlined />,
      description: '工作流',
      // 柔和的蓝绿色渐变，代表流程和连接
      gradient: 'linear-gradient(135deg, #06b6d4 0%, #10b981 100%)',
      hoverGradient: 'linear-gradient(135deg, #0891b2 0%, #059669 100%)',
      shadowColor: 'rgba(6, 182, 212, 0.25)'
    },
    {
      key: 'multi_agent',
      label: 'Multi-Agent',
      icon: <TeamOutlined />,
      description: '多智能体',
      // 柔和的橙黄色渐变，代表协作和团队
      gradient: 'linear-gradient(135deg, #f59e0b 0%, #ef4444 100%)',
      hoverGradient: 'linear-gradient(135deg, #d97706 0%, #dc2626 100%)',
      shadowColor: 'rgba(245, 158, 11, 0.25)'
    }
  ]

  return (
    <Space 
      size="large" 
      style={{ 
        width: '100%', 
        justifyContent: 'center', 
        marginBottom: 24,
        flexWrap: 'wrap'
      }}
    >
      {modes.map((mode) => {
        const isSelected = value === mode.key
        return (
          <div
            key={mode.key}
            style={{
              position: 'relative',
              cursor: disabled ? 'not-allowed' : 'pointer',
              transition: 'all 0.3s ease',
              transform: isSelected ? 'translateY(-4px)' : 'translateY(0)',
            }}
            onClick={() => !disabled && onChange(mode.key)}
          >
            <Button
              type={isSelected ? 'primary' : 'default'}
              size="large"
              disabled={disabled}
              style={{
                minWidth: 180,
                height: 100,
                fontSize: 18,
                fontWeight: isSelected ? 'bold' : 600,
                borderRadius: '12px',
                border: isSelected 
                  ? 'none' 
                  : '2px solid #e5e7eb',
                background: isSelected 
                  ? mode.gradient 
                  : '#ffffff',
                color: isSelected ? '#ffffff' : '#4b5563',
                boxShadow: isSelected 
                  ? `0 8px 24px ${mode.shadowColor}` 
                  : '0 2px 8px rgba(0,0,0,0.06)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
                padding: '16px 24px',
                transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                position: 'relative',
                overflow: 'visible',
              }}
              onMouseEnter={(e) => {
                if (!disabled && !isSelected) {
                  e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,0.1)'
                  e.currentTarget.style.transform = 'translateY(-2px)'
                  e.currentTarget.style.borderColor = '#d1d5db'
                  e.currentTarget.style.background = '#f9fafb'
                } else if (!disabled && isSelected) {
                  e.currentTarget.style.background = mode.hoverGradient
                  e.currentTarget.style.boxShadow = `0 10px 28px ${mode.shadowColor.replace('0.25', '0.35')}`
                }
              }}
              onMouseLeave={(e) => {
                if (!disabled && !isSelected) {
                  e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.06)'
                  e.currentTarget.style.transform = 'translateY(0)'
                  e.currentTarget.style.borderColor = '#e5e7eb'
                  e.currentTarget.style.background = '#ffffff'
                } else if (!disabled && isSelected) {
                  e.currentTarget.style.background = mode.gradient
                  e.currentTarget.style.boxShadow = `0 8px 24px ${mode.shadowColor}`
                }
              }}
            >
              <div style={{ 
                fontSize: 32, 
                marginBottom: 2,
                lineHeight: 1,
                color: isSelected ? '#ffffff' : '#6b7280',
                transition: 'color 0.3s ease',
              }}>
                {mode.icon}
              </div>
              <div style={{ 
                fontSize: 18, 
                fontWeight: 'bold',
                lineHeight: 1.2,
                color: isSelected ? '#ffffff' : '#374151',
                transition: 'color 0.3s ease',
              }}>
                {mode.label}
              </div>
              <div style={{ 
                fontSize: 12, 
                opacity: isSelected ? 0.95 : 0.65,
                fontWeight: 'normal',
                lineHeight: 1.2,
                color: isSelected ? '#ffffff' : '#6b7280',
                transition: 'all 0.3s ease',
              }}>
                {mode.description}
              </div>
            </Button>
            {isSelected && (
              <div
                style={{
                  position: 'absolute',
                  bottom: -8,
                  left: '50%',
                  transform: 'translateX(-50%)',
                  width: 50,
                  height: 3,
                  background: mode.gradient,
                  borderRadius: '2px',
                  boxShadow: `0 2px 8px ${mode.shadowColor}`,
                  transition: 'all 0.3s ease',
                }}
              />
            )}
          </div>
        )
      })}
    </Space>
  )
}

export default AgentModeSelector

