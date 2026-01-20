import { useState, useRef, useEffect } from 'react'
import { Input, Button, Card, Space, Typography, Avatar, Spin } from 'antd'
import { SendOutlined, UserOutlined, RobotOutlined, DeleteOutlined } from '@ant-design/icons'

const { TextArea } = Input
const { Text } = Typography

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

export interface InteractionRequest {
  execution_id: string
  component_id: string
  question: string
  conversation_id: string
}

interface WorkflowChatProps {
  workflowId?: string
  onSendMessage?: (message: string) => Promise<string>
  disabled?: boolean
  onClear?: () => void  // 清除历史对话的回调
  onInteraction?: (interaction: InteractionRequest & { reply: string }) => Promise<string>  // 交互请求回调，返回执行结果
  interactionRequest?: InteractionRequest | null  // 从父组件传入的交互请求
  agentMode?: 'agent' | 'workflow' | 'multi_agent'
}

function WorkflowChat({ workflowId, onSendMessage, disabled = false, onClear, onInteraction, interactionRequest: propInteractionRequest, agentMode = 'workflow' }: WorkflowChatProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [interactionRequest, setInteractionRequest] = useState<InteractionRequest | null>(null)
  const [interactionReply, setInteractionReply] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  
  // 同步父组件传入的交互请求
  useEffect(() => {
    if (propInteractionRequest) {
      // 检查是否已经显示过这个交互请求
      const existingRequest = interactionRequest
      if (!existingRequest || existingRequest.execution_id !== propInteractionRequest.execution_id) {
        setInteractionRequest(propInteractionRequest)
        // 显示交互问题消息（只在第一次显示）
        const interactionMessage: Message = {
          id: `interaction_${propInteractionRequest.execution_id}`,
          role: 'assistant',
          content: `❓ ${propInteractionRequest.question}`,
          timestamp: new Date(),
        }
        setMessages((prev) => {
          // 检查是否已经存在这个消息
          const exists = prev.some(msg => msg.id === interactionMessage.id)
          if (exists) {
            return prev
          }
          return [...prev, interactionMessage]
        })
      }
    } else {
      // 清除交互请求
      setInteractionRequest(null)
      setInteractionReply('')
    }
  }, [propInteractionRequest])

  useEffect(() => {
    // 自动滚动到底部
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // 处理交互回复
  const handleInteractionReply = async () => {
    if (!interactionRequest || !interactionReply.trim()) return
    
    const reply = interactionReply
    setInteractionReply('')
    setLoading(true)
    
    // 显示用户回复消息
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: reply,
      timestamp: new Date(),
    }
    setMessages((prev) => [...prev, userMessage])
    
    // 调用父组件的交互回复处理函数
    try {
      if (onInteraction) {
        const response = await onInteraction({
          ...interactionRequest,
          reply: reply,
        } as any)
        
        // 显示执行结果
        if (response) {
          const assistantMessage: Message = {
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: response,
            timestamp: new Date(),
          }
          setMessages((prev) => [...prev, assistantMessage])
        }
      }
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '抱歉，继续执行时发生了错误，请稍后重试。',
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setInteractionRequest(null)
      setLoading(false)
    }
  }

  const handleSend = async () => {
    if (!input.trim() || loading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      // 调用API发送消息
      const response = onSendMessage
        ? await onSendMessage(input)
        : `这是对"${input}"的回复。工作流ID: ${workflowId || '未指定'}`

      // 只有当响应不为空时才添加消息（交互请求时响应为空）
      if (response && response.trim()) {
        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: response,
          timestamp: new Date(),
        }

        setMessages((prev) => [...prev, assistantMessage])
      }
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '抱歉，发生了错误，请稍后重试。',
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleClear = () => {
    setMessages([])
    setInput('')
    if (onClear) {
      onClear()
    }
  }

  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        // 与左侧/中间区域统一的浅灰蓝科技背景
        background: 'linear-gradient(to bottom, #f8fafc 0%, #ffffff 40%)',
      }}
    >
      {/* 清除按钮 - 只在有消息时显示在顶部 */}
      {messages.length > 0 && (
        <div
          style={{
            padding: '8px 16px',
            borderBottom: '2px solid transparent',
            borderImage: 'linear-gradient(to right, #667eea, #764ba2) 1',
            display: 'flex',
            justifyContent: 'flex-end',
            background: 'linear-gradient(to right, rgba(102,126,234,0.06), rgba(118,75,162,0.06))',
          }}
        >
          <Button
            type="text"
            size="small"
            icon={<DeleteOutlined />}
            onClick={handleClear}
            style={{
              color: '#999',
            }}
            title="清除历史对话"
          >
            清除历史
          </Button>
        </div>
      )}
      
      {/* 消息列表 */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '16px',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}
      >
        {messages.length === 0 && (
          <div
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#999',
              flexDirection: 'column',
              gap: '8px',
            }}
          >
            <RobotOutlined style={{ fontSize: '32px', color: '#d9d9d9' }} />
            <Text type="secondary">
              {agentMode === 'agent'
                ? (disabled ? '等待 Agent 生成完成...' : '开始与 Agent 对话...')
                : agentMode === 'multi_agent'
                ? (disabled ? '等待 Multi-Agent 系统生成完成...' : '开始与 Multi-Agent 系统对话...')
                : (disabled ? '等待工作流生成完成...' : '开始测试工作流...')}
            </Text>
            <Text type="secondary" style={{ fontSize: '12px' }}>
              {agentMode === 'agent'
                ? (disabled
                    ? 'Agent 生成完成后，您可以在这里输入查询与 Agent 对话'
                    : '输入您的查询，Agent 将处理并返回结果')
                : agentMode === 'multi_agent'
                ? (disabled
                    ? 'Multi-Agent 系统生成完成后，您可以在这里输入查询与系统对话'
                    : '输入您的查询，Multi-Agent 系统将处理并返回结果')
                : (disabled
                ? '工作流生成完成后，您可以在这里输入查询来测试工作流'
                    : '输入您的查询，工作流将处理并返回结果')}
            </Text>
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            style={{
              display: 'flex',
              gap: '12px',
              flexDirection: message.role === 'user' ? 'row-reverse' : 'row',
            }}
          >
            <Avatar
              icon={message.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
              style={{
                backgroundColor: message.role === 'user' ? '#3b82f6' : '#8b5cf6',
              }}
            />
            <Card
              style={{
                maxWidth: '70%',
                background: message.role === 'user'
                  ? 'linear-gradient(135deg, rgba(59,130,246,0.12), rgba(139,92,246,0.12))'
                  : 'linear-gradient(135deg, rgba(239,246,255,0.95), rgba(243,244,255,0.95))',
                border: message.role === 'user'
                  ? '1px solid rgba(59,130,246,0.3)'
                  : '1px solid rgba(129,140,248,0.25)',
                boxShadow: '0 4px 10px rgba(15,23,42,0.08)',
              }}
              bodyStyle={{ padding: '12px' }}
            >
              <Text 
                style={{ 
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  display: 'block'
                }}
              >
                {message.content}
              </Text>
              <div style={{ marginTop: '4px', fontSize: '11px', color: '#999' }}>
                {message.timestamp.toLocaleTimeString()}
              </div>
            </Card>
          </div>
        ))}

        {loading && (
          <div style={{ display: 'flex', gap: '12px' }}>
            <Avatar icon={<RobotOutlined />} style={{ backgroundColor: '#8b5cf6' }} />
            <Card
              style={{
                background: 'linear-gradient(135deg, rgba(239,246,255,0.95), rgba(243,244,255,0.95))',
                border: '1px solid rgba(129,140,248,0.35)',
              }}
              bodyStyle={{ padding: '12px' }}
            >
              <Spin size="small" />{' '}
              <Text style={{ marginLeft: '8px', color: '#4b5563' }}>正在思考...</Text>
            </Card>
          </div>
        )}

        {/* 交互请求卡片 */}
        {interactionRequest && (
          <Card
            style={{
              border: '1px solid rgba(102,126,234,0.6)',
              background:
                'linear-gradient(135deg, rgba(102,126,234,0.12) 0%, rgba(118,75,162,0.12) 100%)',
              boxShadow: '0 4px 12px rgba(15,23,42,0.12)',
            }}
            bodyStyle={{ padding: '16px' }}
          >
            <div style={{ marginBottom: '12px' }}>
              <Text
                strong
                style={{
                  display: 'block',
                  marginBottom: '8px',
                  fontSize: 13,
                  color: '#111827',
                }}
              >
                ⚠️ 需要您的回复
              </Text>
              <Text style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {interactionRequest.question}
              </Text>
            </div>
            <Space.Compact style={{ width: '100%' }}>
              <TextArea
                value={interactionReply}
                onChange={(e) => setInteractionReply(e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleInteractionReply()
                  }
                }}
                placeholder="请输入您的回复..."
                rows={2}
                style={{ resize: 'none' }}
                autoFocus
              />
              <Button
                type="primary"
                onClick={handleInteractionReply}
                disabled={!interactionReply.trim()}
                style={{ height: 'auto' }}
              >
                回复
              </Button>
            </Space.Compact>
          </Card>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 输入框 */}
      {!interactionRequest && (
        <div
          style={{
            padding: '16px',
            borderTop: '2px solid transparent',
            borderImage: 'linear-gradient(to right, #667eea, #764ba2) 1',
            background:
              'linear-gradient(to right, rgba(248,250,252,0.95), rgba(239,246,255,0.98))',
          }}
        >
          <Space.Compact style={{ width: '100%' }}>
            <TextArea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={agentMode === 'agent'
                ? (disabled ? "等待 Agent 生成完成..." : "输入查询与 Agent 对话...")
                : agentMode === 'multi_agent'
                ? (disabled ? "等待 Multi-Agent 系统生成完成..." : "输入查询与 Multi-Agent 系统对话...")
                : (disabled ? "等待工作流生成完成..." : "输入查询测试工作流...")}
              rows={2}
              disabled={loading || disabled}
              style={{ resize: 'none' }}
            />
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSend}
              loading={loading}
              disabled={!input.trim() || disabled}
              style={{ height: 'auto' }}
            >
              发送
            </Button>
          </Space.Compact>
        </div>
      )}
    </div>
  )
}

export default WorkflowChat

