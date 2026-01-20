import { useEffect, useRef, useState } from 'react'
import { Timeline, Spin, Typography, Tag, Space, Button, Input } from 'antd'
import {
  BulbOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  CodeOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  ApiOutlined,
  ExperimentOutlined,
  DownOutlined,
  UpOutlined,
  EditOutlined,
  SendOutlined,
} from '@ant-design/icons'
// 使用原生方式显示JSON，不依赖react-json-view

const { Text, Paragraph } = Typography
const { TextArea } = Input

export interface BuildStep {
  id: string
  type: 'thinking' | 'planning' | 'searching' | 'creating' | 'coding' | 'testing' | 'optimizing' | 'completed' | 'react_thinking' | 'react_acting' | 'react_observing'
  title: string
  description?: string
  status: 'pending' | 'running' | 'completed' | 'error'
  timestamp?: Date
  // 详细信息
  details?: {
    plan?: any // Plan的完整内容
    thought?: string // React思考内容
    action?: string // React执行动作
    actionInput?: any // React执行输入
    observation?: string // React观察结果
    result?: any // 执行结果
    code?: string // 生成的代码
    testResult?: any // 测试结果
    error?: string // 错误信息
    [key: string]: any // 其他详细信息
  }
  // 子步骤（用于React的思考-执行-观察循环）
  subSteps?: BuildStep[]
  // 思考过程是否正在活跃中（用于在卡片下方实时展示）
  isThinkingActive?: boolean
  // 流式显示的内容（用于前端模拟打字机效果）
  streamingThought?: string
  // 执行动作、观察结果的流式文本（直接由事件实时更新）
  streamingAction?: string
  streamingObservation?: string
  streamingResult?: string  // 执行结果的流式文本
}

interface BuildProcessProps {
  steps: BuildStep[]
  currentStep?: string
  onModify?: (modificationRequest: string) => void
  canModify?: boolean
  agentMode?: 'agent' | 'workflow' | 'multi_agent'
}

function BuildProcess({ steps, currentStep, onModify, canModify = false, agentMode = 'workflow' }: BuildProcessProps) {
  const timelineRef = useRef<HTMLDivElement>(null)
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set())
  const [modifyInput, setModifyInput] = useState('')
  const [isModifying, setIsModifying] = useState(false)

  useEffect(() => {
    // 自动滚动到当前步骤
    if (timelineRef.current && currentStep) {
      const activeItem = timelineRef.current.querySelector(`[data-step-id="${currentStep}"]`)
      if (activeItem) {
        activeItem.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    }
  }, [currentStep])

  // 当步骤内容更新时，自动滚动到活跃的思考内容
  useEffect(() => {
    if (timelineRef.current) {
      // 查找所有正在思考的步骤
      const thinkingSteps = steps.filter(s => s.isThinkingActive && s.status === 'running')
      if (thinkingSteps.length > 0) {
        const lastThinkingStep = thinkingSteps[thinkingSteps.length - 1]
        const thinkingItem = timelineRef.current.querySelector(`[data-step-id="${lastThinkingStep.id}"]`)
        if (thinkingItem) {
          // 延迟滚动，确保DOM已更新
          setTimeout(() => {
            thinkingItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
          }, 100)
        }
      }
    }
  }, [steps])

  const toggleStepDetails = (stepId: string) => {
    setExpandedSteps((prev) => {
      const newSet = new Set(prev)
      if (newSet.has(stepId)) {
        newSet.delete(stepId)
      } else {
        newSet.add(stepId)
      }
      return newSet
    })
  }

  const handleModify = () => {
    if (!modifyInput.trim() || !onModify) return
    setIsModifying(true)
    onModify(modifyInput.trim())
    setModifyInput('')
    // 注意：isModifying 应该由父组件控制，这里只是临时状态
    setTimeout(() => setIsModifying(false), 100)
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleModify()
    }
  }

  // 根据步骤类型获取表情符号
  const getEmoji = (type: BuildStep['type'], status: BuildStep['status']) => {
    if (status === 'completed') return '✅'
    if (status === 'error') return '❌'
    if (status === 'running') {
      switch (type) {
        case 'thinking':
        case 'react_thinking':
          return '🤔'
        case 'planning':
          return '📋'
        case 'searching':
          return '🔍'
        case 'creating':
          return '✨'
        case 'coding':
        case 'react_acting':
          return '💻'
        case 'testing':
        case 'react_observing':
          return '🧪'
        case 'optimizing':
          return '⚡'
        default:
          return '⚙️'
      }
    }
    // pending 状态
    switch (type) {
      case 'thinking':
      case 'react_thinking':
        return '💭'
      case 'planning':
        return '📝'
      case 'searching':
        return '🔎'
      case 'creating':
        return '🎨'
      case 'coding':
      case 'react_acting':
        return '⚡'
      case 'testing':
      case 'react_observing':
        return '🔬'
      case 'optimizing':
        return '🔄'
      default:
        return '📌'
    }
  }

  const getIcon = (type: BuildStep['type'], status: BuildStep['status']) => {
    if (status === 'running') {
      return <Spin size="small" style={{ color: '#3b82f6' }} />
    }
    if (status === 'completed') {
      return <CheckCircleOutlined style={{ color: '#10b981', fontSize: '16px' }} />
    }
    if (status === 'error') {
      return <CheckCircleOutlined style={{ color: '#ef4444', fontSize: '16px' }} />
    }

    switch (type) {
      case 'thinking':
      case 'react_thinking':
        return <BulbOutlined style={{ color: '#8b5cf6', fontSize: '16px' }} />
      case 'planning':
        return <FileTextOutlined style={{ color: '#3b82f6', fontSize: '16px' }} />
      case 'searching':
        return <FileSearchOutlined style={{ color: '#06b6d4', fontSize: '16px' }} />
      case 'creating':
        return <FileTextOutlined style={{ color: '#f59e0b', fontSize: '16px' }} />
      case 'coding':
      case 'react_acting':
        return <CodeOutlined style={{ color: '#6366f1', fontSize: '16px' }} />
      case 'testing':
      case 'react_observing':
        return <ExperimentOutlined style={{ color: '#10b981', fontSize: '16px' }} />
      case 'optimizing':
        return <SyncOutlined style={{ color: '#8b5cf6', fontSize: '16px' }} />
      case 'completed':
        return <CheckCircleOutlined style={{ color: '#10b981', fontSize: '16px' }} />
      default:
        return <ApiOutlined style={{ color: '#6b7280', fontSize: '16px' }} />
    }
  }

  const getColor = (status: BuildStep['status']) => {
    switch (status) {
      case 'running':
        return '#3b82f6' // 科技蓝
      case 'completed':
        return '#10b981' // 科技绿
      case 'error':
        return '#ef4444' // 科技红
      default:
        return '#6b7280' // 灰色
    }
  }

  const renderStepDetails = (step: BuildStep) => {
    if (!step.details) return null

    const details = step.details
    const hasDetails = Object.keys(details).length > 0

    if (!hasDetails) return null

    return (
      <div style={{ marginTop: '12px', padding: '16px', background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.05) 0%, rgba(139, 92, 246, 0.05) 100%)', borderRadius: '10px', border: '1px solid rgba(59, 130, 246, 0.15)' }}>
        {/* Plan详情 */}
        {details.plan && (
          <div style={{ marginBottom: '14px' }}>
            <Text strong style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', background: 'linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
              <span>📋</span>
              构建计划：
            </Text>
            <div style={{ marginTop: '8px', padding: '8px', background: '#fff', borderRadius: '4px' }}>
              {details.plan.steps && Array.isArray(details.plan.steps) ? (
                <ul style={{ margin: 0, paddingLeft: '20px' }}>
                  {details.plan.steps.map((planStep: any, index: number) => (
                    <li key={index} style={{ marginBottom: '4px' }}>
                      <Text>
                        <Tag color="blue">{planStep.step_name}</Tag>
                        {planStep.description}
                      </Text>
                    </li>
                  ))}
                </ul>
              ) : (
                <pre style={{ margin: 0, fontSize: '12px', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                  {JSON.stringify(details.plan, null, 2)}
                </pre>
              )}
            </div>
          </div>
        )}

        {/* React思考详情 */}
        {details.thought && (
          <div style={{ marginBottom: '14px' }}>
            <Text strong style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
              <span>💭</span>
              思考过程：
            </Text>
            <Paragraph
              style={{
                marginTop: '8px',
                padding: '8px',
                background: '#fff',
                borderRadius: '4px',
                marginBottom: 0,
              }}
            >
              {details.thought}
            </Paragraph>
          </div>
        )}

        {/* React执行详情 */}
        {details.action && (
          <div style={{ marginBottom: '14px' }}>
            <Text strong style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', color: '#6366f1' }}>
              <span>⚡</span>
              执行动作：
            </Text>
            <div style={{ marginTop: '8px', padding: '8px', background: '#fff', borderRadius: '4px' }}>
              <Text code>{details.action}</Text>
              {details.actionInput && (
                <div style={{ marginTop: '8px' }}>
                  <Text type="secondary" style={{ fontSize: '12px' }}>
                    输入参数：
                  </Text>
                  <pre style={{ margin: 0, fontSize: '12px', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                    {JSON.stringify(details.actionInput, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </div>
        )}

        {/* React观察详情 */}
        {details.observation && (
          <div style={{ marginBottom: '14px' }}>
            <Text strong style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', color: '#10b981' }}>
              <span>🔬</span>
              观察结果：
            </Text>
            <Paragraph
              style={{
                marginTop: '8px',
                padding: '8px',
                background: '#fff',
                borderRadius: '4px',
                marginBottom: 0,
              }}
            >
              {details.observation}
            </Paragraph>
          </div>
        )}

        {/* 执行结果 */}
        {details.result && (
          <div style={{ marginBottom: '14px' }}>
            <Text strong style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', color: '#3b82f6' }}>
              <span>📊</span>
              执行结果：
            </Text>
            <div style={{ marginTop: '8px', padding: '8px', background: '#fff', borderRadius: '4px' }}>
              <pre style={{ margin: 0, fontSize: '12px', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {JSON.stringify(details.result, null, 2)}
              </pre>
            </div>
          </div>
        )}

        {/* 生成的代码 */}
        {details.code && (
          <div style={{ marginBottom: '14px' }}>
            <Text strong style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', color: '#6366f1' }}>
              <span>💻</span>
              生成的代码：
            </Text>
            <div
              style={{
                marginTop: '8px',
                padding: '12px',
                background: '#1e1e1e',
                borderRadius: '4px',
                maxHeight: '300px',
                overflow: 'auto',
              }}
            >
              <pre style={{ margin: 0, color: '#d4d4d4', fontSize: '12px', fontFamily: 'monospace' }}>
                {details.code}
              </pre>
            </div>
          </div>
        )}

        {/* 测试结果 */}
        {details.testResult && (
          <div style={{ marginBottom: '14px' }}>
            <Text strong style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', color: details.testResult.success ? '#10b981' : '#ef4444' }}>
              <span>{details.testResult.success ? '✅' : '❌'}</span>
              测试结果：
            </Text>
            <div style={{ marginTop: '8px', padding: '8px', background: '#fff', borderRadius: '4px' }}>
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                <Tag color={details.testResult.success ? 'success' : 'error'}>
                  {details.testResult.success ? '通过' : '失败'}
                </Tag>
                
                {/* 测试用例信息 */}
                {(details.testResult.test_cases && details.testResult.test_cases.length > 0) && (
                  <div>
                    <Text type="secondary" style={{ fontSize: '12px' }}>
                      测试用例：
                    </Text>
                    <div style={{ marginTop: '4px' }}>
                      {details.testResult.test_cases.map((testCase: string, index: number) => (
                        <Tag key={index} color="blue" style={{ marginRight: '4px', marginBottom: '4px' }}>
                          {testCase}
                        </Tag>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* 测试命令 */}
                {details.testResult.command && (
                  <div>
                    <Text type="secondary" style={{ fontSize: '12px' }}>
                      执行命令：
                    </Text>
                    <Text code style={{ fontSize: '11px', display: 'block', marginTop: '4px' }}>
                      {details.testResult.command}
                    </Text>
                  </div>
                )}
                
                {/* 执行时间 */}
                {details.testResult.execution_time !== undefined && (
                  <div>
                    <Text type="secondary" style={{ fontSize: '12px' }}>
                      执行时间：{details.testResult.execution_time.toFixed(2)} 秒
                    </Text>
                  </div>
                )}
                
                {/* 错误信息 */}
                {details.testResult.error && (
                  <div>
                    <Text type="danger" style={{ fontSize: '12px' }}>
                      错误：
                    </Text>
                    <pre
                      style={{
                        marginTop: '4px',
                        padding: '8px',
                        background: '#fff2f0',
                        borderRadius: '4px',
                        fontSize: '11px',
                        maxHeight: '200px',
                        overflow: 'auto',
                        color: '#ff4d4f',
                      }}
                    >
                      {details.testResult.error}
                    </pre>
                  </div>
                )}
                
                {/* 测试输出 */}
                {details.testResult.output && (
                  <div>
                    <Text type="secondary" style={{ fontSize: '12px' }}>
                      输出：
                    </Text>
                    <pre
                      style={{
                        marginTop: '4px',
                        padding: '8px',
                        background: '#f5f5f5',
                        borderRadius: '4px',
                        fontSize: '11px',
                        maxHeight: '200px',
                        overflow: 'auto',
                      }}
                    >
                      {details.testResult.output}
                    </pre>
                  </div>
                )}
              </Space>
            </div>
          </div>
        )}

        {/* 错误信息 */}
        {details.error && (
          <div style={{ marginBottom: '14px' }}>
            <Text strong style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px', color: '#ef4444' }}>
              <span>⚠️</span>
              错误信息：
            </Text>
            <Paragraph
              style={{
                marginTop: '8px',
                padding: '8px',
                background: '#fff2f0',
                borderRadius: '4px',
                marginBottom: 0,
                color: '#ff4d4f',
              }}
            >
              {details.error}
            </Paragraph>
          </div>
        )}

        {/* 其他详细信息 */}
        {Object.keys(details)
          .filter((key) => !['plan', 'thought', 'action', 'actionInput', 'observation', 'result', 'code', 'testResult', 'error'].includes(key))
          .map((key) => (
            <div key={key} style={{ marginBottom: '12px' }}>
              <Text strong style={{ fontSize: '13px' }}>
                {key}：
              </Text>
              <div style={{ marginTop: '8px', padding: '8px', background: '#fff', borderRadius: '4px' }}>
                {typeof details[key] === 'object' ? (
                  <pre style={{ margin: 0, fontSize: '12px', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                    {JSON.stringify(details[key], null, 2)}
                  </pre>
                ) : (
                  <Text>{String(details[key])}</Text>
                )}
              </div>
            </div>
          ))}
      </div>
    )
  }

  return (
    <>
      <style>{`
        @keyframes blink {
          0%, 50% { opacity: 1; }
          51%, 100% { opacity: 0; }
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-4px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.6; }
        }
        @keyframes shimmer {
          0% { background-position: -1000px 0; }
          100% { background-position: 1000px 0; }
        }
        .tech-gradient {
          background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
          background-size: 200% 200%;
          animation: shimmer 3s ease infinite;
        }
        .thinking-gradient {
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          box-shadow: 0 4px 20px rgba(102, 126, 234, 0.3);
        }
      `}</style>
      <div
        ref={timelineRef}
        style={{
          height: '100%',
          overflowY: 'auto',
          padding: '16px',
          background: 'linear-gradient(to bottom, #f8fafc 0%, #ffffff 100%)',
        }}
      >
      <div 
        style={{ 
          marginBottom: '20px', 
          paddingBottom: '16px', 
          borderBottom: '2px solid transparent',
          borderImage: 'linear-gradient(to right, #667eea, #764ba2) 1',
          background: 'linear-gradient(to right, rgba(102, 126, 234, 0.05), rgba(118, 75, 162, 0.05))',
          padding: '12px 16px',
          borderRadius: '8px',
        }}
      >
        <Text strong style={{ fontSize: '18px', background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
          ⚡ 构建过程
        </Text>
      </div>
      {steps.length === 0 ? (
        <div
          style={{
            padding: '60px 40px',
            textAlign: 'center',
            background: 'linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%)',
            borderRadius: '12px',
            border: '2px dashed rgba(102, 126, 234, 0.3)',
          }}
        >
          <div style={{ fontSize: '48px', marginBottom: '16px', opacity: 0.6 }}>⚡</div>
          <Text type="secondary" style={{ fontSize: '14px', color: '#6b7280' }}>
            等待构建开始...
          </Text>
        </div>
      ) : (
        <Timeline
          items={
            // ✅ 按照时间戳排序步骤，确保显示顺序正确
            [...steps].sort((a, b) => {
              if (!a.timestamp || !b.timestamp) return 0
              return a.timestamp.getTime() - b.timestamp.getTime()
            }).map((step) => {
            const isExpanded = expandedSteps.has(step.id)
            const hasDetails = step.details && Object.keys(step.details).length > 0
            const hasSubSteps = step.subSteps && step.subSteps.length > 0

            return {
              key: step.id,
              dot: getIcon(step.type, step.status),
              color: getColor(step.status),
              children: (
                <div
                  data-step-id={step.id}
                  style={{
                    padding: '12px',
                    borderRadius: '8px',
                    backgroundColor: step.status === 'running' 
                      ? 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(139, 92, 246, 0.1) 100%)'
                      : 'transparent',
                    background: step.status === 'running' 
                      ? 'linear-gradient(135deg, rgba(59, 130, 246, 0.08) 0%, rgba(139, 92, 246, 0.08) 100%)'
                      : 'transparent',
                    border: step.status === 'running' 
                      ? '1px solid rgba(59, 130, 246, 0.2)'
                      : '1px solid transparent',
                    boxShadow: step.status === 'running' 
                      ? '0 2px 8px rgba(59, 130, 246, 0.15)'
                      : 'none',
                    transition: 'all 0.3s ease',
                    position: 'relative',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div style={{ flex: 1 }}>
                      <Text
                        strong={step.status === 'running' || step.status === 'completed'}
                        style={{
                          color:
                            step.status === 'running'
                              ? '#3b82f6'
                              : step.status === 'completed'
                              ? '#10b981'
                              : step.status === 'error'
                              ? '#ef4444'
                              : '#4b5563',
                          fontSize: step.status === 'running' ? '15px' : '14px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                        }}
                      >
                        <span style={{ fontSize: '16px' }}>{getEmoji(step.type, step.status)}</span>
                        {step.title}
                      </Text>
                      {step.description && (
                        <div
                          style={{
                            marginTop: '6px',
                            color: step.status === 'running' ? '#3b82f6' : '#6b7280',
                            fontSize: '12px',
                            lineHeight: '1.5',
                          }}
                        >
                          {step.description}
                        </div>
                      )}
                      {step.timestamp && (
                        <div style={{ marginTop: '6px', color: '#9ca3af', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <span>🕐</span>
                          {step.timestamp.toLocaleTimeString()}
                        </div>
                      )}
                    </div>
                    {(hasDetails || hasSubSteps) && (
                      <Button
                        type="text"
                        size="small"
                        icon={isExpanded ? <UpOutlined /> : <DownOutlined />}
                        onClick={() => toggleStepDetails(step.id)}
                        style={{ marginLeft: '8px' }}
                      >
                        {isExpanded ? '收起' : '展开'}
                      </Button>
                    )}
                  </div>
                  {/* 思考过程实时展示（在卡片下方，仅在思考进行中且状态为 running 时显示） */}
                  {step.isThinkingActive && step.status === 'running' && (step.details?.thought || step.streamingThought) && (
                    <div
                      className="thinking-gradient"
                      style={{
                        marginTop: '16px',
                        padding: '16px',
                        borderRadius: '10px',
                        border: '1px solid rgba(102, 126, 234, 0.3)',
                        animation: 'fadeIn 0.4s ease-in, pulse 2s ease-in-out infinite',
                        position: 'relative',
                        overflow: 'hidden',
                      }}
                    >
                      {/* 装饰性渐变背景 */}
                      <div
                        style={{
                          position: 'absolute',
                          top: 0,
                          left: 0,
                          right: 0,
                          height: '3px',
                          background: 'linear-gradient(90deg, #667eea, #764ba2, #f093fb)',
                          opacity: 0.6,
                        }}
                      />
                      <Text 
                        strong 
                        style={{ 
                          fontSize: '13px', 
                          color: '#111827', // 深色字体，和背景渐变形成清晰对比
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          marginBottom: '10px',
                        }}
                      >
                        <span style={{ fontSize: '16px' }}>🧠</span>
                        思考过程：
                      </Text>
                      <Paragraph
                        style={{
                          margin: 0,
                          padding: '12px',
                          background: 'rgba(255, 255, 255, 0.95)',
                          borderRadius: '8px',
                          fontSize: '13px',
                          lineHeight: '1.7',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                          color: '#374151',
                          minHeight: '24px',
                          boxShadow: '0 2px 4px rgba(0, 0, 0, 0.05)',
                        }}
                      >
                        {/* 优先显示流式内容，如果没有则显示完整内容 */}
                        {step.streamingThought !== undefined ? step.streamingThought : step.details?.thought}
                        {/* 闪烁光标：只要步骤还在 running 就一直保留（直到步骤结束） */}
                        {step.status === 'running' && step.isThinkingActive && (
                          <span
                            style={{
                              display: 'inline-block',
                              width: '3px',
                              height: '16px',
                              background: 'linear-gradient(135deg, #667eea, #764ba2)',
                              marginLeft: '4px',
                              animation: 'blink 1s infinite',
                              verticalAlign: 'middle',
                              borderRadius: '2px',
                            }}
                          />
                        )}
                      </Paragraph>
                    </div>
                  )}
                  {/* 执行动作流式展示 */}
                  {step.streamingAction && (
                    <div
                      style={{
                        marginTop: '12px',
                        padding: '10px 12px',
                        borderRadius: '8px',
                        background: 'rgba(59,130,246,0.05)',
                        border: '1px solid rgba(59,130,246,0.25)',
                      }}
                    >
                      <Text strong style={{ fontSize: '12px', color: '#1d4ed8', display: 'block', marginBottom: 4 }}>
                        执行动作（流式）：
                      </Text>
                      <Paragraph
                        style={{
                          margin: 0,
                          fontSize: '12px',
                          lineHeight: 1.6,
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                          color: '#1f2933',
                        }}
                      >
                        {step.streamingAction}
                        {/* 闪烁光标：如果执行动作还在流式显示中，显示光标 */}
                        {step.details?._fullActionText &&
                          step.streamingAction &&
                          step.streamingAction.length < step.details._fullActionText.length && (
                            <span
                              style={{
                                display: 'inline-block',
                                width: '3px',
                                height: '16px',
                                background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
                                marginLeft: '4px',
                                animation: 'blink 1s infinite',
                                verticalAlign: 'middle',
                                borderRadius: '2px',
                              }}
                            />
                          )}
                      </Paragraph>
                    </div>
                  )}
                  {/* 观察结果流式展示 */}
                  {step.streamingObservation && (
                    <div
                      style={{
                        marginTop: '10px',
                        padding: '10px 12px',
                        borderRadius: '8px',
                        background: 'rgba(16,185,129,0.04)',
                        border: '1px solid rgba(16,185,129,0.25)',
                      }}
                    >
                      <Text strong style={{ fontSize: '12px', color: '#047857', display: 'block', marginBottom: 4 }}>
                        观察结果（流式）：
                      </Text>
                      <Paragraph
                        style={{
                          margin: 0,
                          fontSize: '12px',
                          lineHeight: 1.6,
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                          color: '#064e3b',
                        }}
                      >
                        {step.streamingObservation}
                        {/* 闪烁光标：如果观察结果还在流式显示中，显示光标 */}
                        {step.details?._fullObservationText &&
                          step.streamingObservation &&
                          step.streamingObservation.length <
                            step.details._fullObservationText.length && (
                            <span
                              style={{
                                display: 'inline-block',
                                width: '3px',
                                height: '16px',
                                background: 'linear-gradient(135deg, #10b981, #059669)',
                                marginLeft: '4px',
                                animation: 'blink 1s infinite',
                                verticalAlign: 'middle',
                                borderRadius: '2px',
                              }}
                            />
                          )}
                      </Paragraph>
                    </div>
                  )}
                  {isExpanded && (
                    <>
                      {renderStepDetails(step)}
                      {hasSubSteps && (
                        <div style={{ marginTop: '12px' }}>
                          <Text strong style={{ fontSize: '12px', color: '#666' }}>
                            子步骤：
                          </Text>
                          <div style={{ marginTop: '8px', paddingLeft: '16px', borderLeft: '2px solid #e8e8e8' }}>
                            {step.subSteps!.map((subStep) => (
                              <div key={subStep.id} style={{ marginBottom: '8px' }}>
                                <Text style={{ fontSize: '12px' }}>
                                  {getIcon(subStep.type, subStep.status)} {subStep.title}
                                </Text>
                                {subStep.description && (
                                  <div style={{ marginTop: '4px', color: '#999', fontSize: '11px' }}>
                                    {subStep.description}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>
              ),
            }
          }          )}
        />
      )}
      
      {/* 修改工作流输入框 - 只在构建完成且允许修改时显示，Agent 和 Multi-Agent 模式下不显示 */}
      {agentMode === 'workflow' && canModify && steps.some(s => s.status === 'completed' && s.type === 'completed') && (
        <div
          style={{
            padding: '20px',
            borderTop: '2px solid transparent',
            borderImage: 'linear-gradient(to right, #667eea, #764ba2) 1',
            background: 'linear-gradient(135deg, rgba(102, 126, 234, 0.03) 0%, rgba(118, 75, 162, 0.03) 100%)',
            borderRadius: '12px 12px 0 0',
            marginTop: '16px',
          }}
        >
          <div style={{ marginBottom: '12px' }}>
            <Text strong style={{ fontSize: '15px', display: 'flex', alignItems: 'center', gap: '8px', color: '#4b5563' }}>
              <EditOutlined style={{ color: '#8b5cf6' }} />
              ✏️ 修改工作流
            </Text>
            <Text type="secondary" style={{ fontSize: '12px', display: 'block', marginTop: '4px' }}>
              输入自然语言描述您想要的修改，例如："添加一个步骤来验证用户输入"、"删除推荐歌曲的格式化步骤"等
            </Text>
          </div>
          <Space.Compact style={{ width: '100%' }}>
            <TextArea
              value={modifyInput}
              onChange={(e) => setModifyInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="例如：添加一个步骤来验证用户输入..."
              rows={2}
              disabled={isModifying}
              style={{ resize: 'none' }}
            />
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleModify}
              loading={isModifying}
              disabled={!modifyInput.trim()}
              style={{ height: 'auto' }}
            >
              修改
            </Button>
          </Space.Compact>
        </div>
      )}
      </div>
    </>
  )
}

export default BuildProcess
