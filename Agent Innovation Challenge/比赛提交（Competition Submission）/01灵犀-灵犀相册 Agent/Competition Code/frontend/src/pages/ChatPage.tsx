import React, { useEffect, useRef, useState } from 'react';
import {
  Layout,
  Input,
  Button,
  List,
  Avatar,
  Card,
  Space,
  Typography,
  Image,
  Tag,
  Spin,
  Tooltip,
} from 'antd';
import {
  SendOutlined,
  UserOutlined,
  RobotOutlined,
  DeleteOutlined,
  PictureOutlined,
  BulbOutlined,
} from '@ant-design/icons';
import { useChatStore } from '../store/chatStore';
import type { ChatMessage } from '../api/types';

const { Content, Footer } = Layout;
const { Text } = Typography;
const { TextArea } = Input;

export const ChatPage: React.FC = () => {
  const { messages, isLoading, sendMessage, clearHistory } = useChatStore();
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSend = async () => {
    if (!inputValue.trim() || isLoading) return;
    const query = inputValue.trim();
    setInputValue('');
    await sendMessage(query);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const renderMessage = (msg: ChatMessage) => {
    const isUser = msg.type === 'user';
    return (
      <div
        key={msg.id}
        style={{
          display: 'flex',
          justifyContent: isUser ? 'flex-end' : 'flex-start',
          marginBottom: 24,
        }}
      >
        <Space align="start" size={16} style={{ flexDirection: isUser ? 'row-reverse' : 'row' }}>
          <Avatar
            icon={isUser ? <UserOutlined /> : <RobotOutlined />}
            style={{ 
                backgroundColor: isUser ? '#1677ff' : '#52c41a',
                flexShrink: 0 
            }}
          />
          <div style={{ maxWidth: 600 }}>
            <Card
              size="small"
              variant="borderless"
              style={{
                backgroundColor: isUser ? '#e6f7ff' : '#f6f6f6',
                borderRadius: isUser ? '16px 4px 16px 16px' : '4px 16px 16px 16px',
                boxShadow: '0 1px 2px rgba(0,0,0,0.05)'
              }}
              styles={{ body: { padding: '12px 16px' } }}
            >
              <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                {msg.content}
              </div>
            </Card>

            {/* Images */}
            {msg.images && msg.images.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <Space size="small" style={{ marginBottom: 8 }}>
                    <PictureOutlined />
                    <Text type="secondary" style={{ fontSize: 12 }}>找到 {msg.images.length} 张图片</Text>
                </Space>
                <div style={{ 
                    background: '#f0f0f0', 
                    padding: 8, 
                    borderRadius: 8,
                    overflowX: 'auto',
                    whiteSpace: 'nowrap'
                }}>
                    <Image.PreviewGroup>
                        <Space size={8}>
                            {msg.images.map(img => (
                                <div key={img.id} style={{ width: 100, height: 100, borderRadius: 4, overflow: 'hidden', display: 'inline-block' }}>
                                    <Image
                                        src={img.preview_url}
                                        width={100}
                                        height={100}
                                        style={{ objectFit: 'cover' }}
                                    />
                                </div>
                            ))}
                        </Space>
                    </Image.PreviewGroup>
                </div>
              </div>
            )}

            {/* Suggestions */}
            {msg.suggestions && msg.suggestions.length > 0 && (
                <div style={{ marginTop: 12 }}>
                    <Space size={[8, 8]} wrap>
                        {msg.suggestions.map((s, i) => (
                            <Tag 
                                key={i} 
                                icon={<BulbOutlined />} 
                                color="blue" 
                                style={{ cursor: 'pointer', borderRadius: 12 }}
                                onClick={() => sendMessage(s)}
                            >
                                {s}
                            </Tag>
                        ))}
                    </Space>
                </div>
            )}
            
            <div style={{ textAlign: isUser ? 'right' : 'left', marginTop: 4 }}>
                <Text type="secondary" style={{ fontSize: 10 }}>
                    {new Date(msg.timestamp).toLocaleTimeString()}
                </Text>
            </div>
          </div>
        </Space>
      </div>
    );
  };

  return (
    <Layout style={{ height: 'calc(100vh - 100px)', background: 'transparent' }}>
        <div style={{ 
            position: 'absolute', 
            top: -60, 
            right: 0, 
            zIndex: 1 
        }}>
             {messages.length > 0 && (
                <Tooltip title="清空对话">
                    <Button 
                        type="text" 
                        danger 
                        icon={<DeleteOutlined />} 
                        onClick={clearHistory}
                    />
                </Tooltip>
            )}
        </div>

      <Content style={{ overflowY: 'auto', padding: '0 16px', scrollBehavior: 'smooth' }}>
        {messages.length === 0 ? (
          <div style={{ 
              height: '100%', 
              display: 'flex', 
              flexDirection: 'column', 
              alignItems: 'center', 
              justifyContent: 'center',
              color: '#999'
          }}>
             <Avatar size={64} icon={<RobotOutlined />} style={{ backgroundColor: '#f0f0f0', color: '#ccc', marginBottom: 24 }} />
             <Typography.Title level={4} style={{ color: '#666' }}>有什么可以帮您？</Typography.Title>
             <Space wrap style={{ maxWidth: 600, justifyItems: 'center', justifyContent: 'center' }}>
                {['查找去年的海边照片', '搜索红色的跑车', '最近上传的文档'].map(text => (
                    <Button key={text} shape="round" onClick={() => sendMessage(text)}>
                        {text}
                    </Button>
                ))}
             </Space>
          </div>
        ) : (
          <div style={{ maxWidth: 800, margin: '0 auto', paddingBottom: 20 }}>
            {messages.map(renderMessage)}
            {isLoading && (
               <div style={{ display: 'flex', marginBottom: 24 }}>
                   <Space align="start" size={16}>
                        <Avatar icon={<RobotOutlined />} style={{ backgroundColor: '#52c41a' }} />
                        <Card size="small" bordered={false} style={{ backgroundColor: '#f6f6f6', borderRadius: '4px 16px 16px 16px' }}>
                             <Space>
                                 <Spin size="small" />
                                 <Text type="secondary">正在思考...</Text>
                             </Space>
                        </Card>
                   </Space>
               </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </Content>
      
      <Footer style={{ background: 'transparent', padding: '16px 0' }}>
        <div style={{ maxWidth: 800, margin: '0 auto' }}>
          <Card 
            styles={{ body: { padding: 8 } }} 
            style={{ 
                borderRadius: 24, 
                boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                border: '1px solid #eee'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8 }}>
                <TextArea
                    value={inputValue}
                    onChange={e => setInputValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="输入消息..."
                    autoSize={{ minRows: 1, maxRows: 6 }}
                    bordered={false}
                    style={{ 
                        resize: 'none', 
                        padding: '8px 12px', 
                        fontSize: 15,
                        lineHeight: 1.6
                    }}
                    disabled={isLoading}
                />
                <Button 
                    type="primary" 
                    shape="circle" 
                    icon={<SendOutlined />} 
                    size="large"
                    onClick={handleSend}
                    disabled={!inputValue.trim() || isLoading}
                    style={{ marginBottom: 4, marginRight: 4 }}
                />
            </div>
          </Card>
          <div style={{ textAlign: 'center', marginTop: 8 }}>
             <Text type="secondary" style={{ fontSize: 12 }}>AI生成内容可能不准确，请核实重要信息</Text>
          </div>
        </div>
      </Footer>
    </Layout>
  );
};
