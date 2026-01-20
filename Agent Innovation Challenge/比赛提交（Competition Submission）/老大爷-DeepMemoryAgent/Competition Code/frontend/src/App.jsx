import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// Use relative URL since Vite proxy is configured
const API_BASE = '/api';

function App() {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [fileTree, setFileTree] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContent, setFileContent] = useState('');
  const [expandedFolders, setExpandedFolders] = useState(new Set());
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    loadFileTree();
  }, []);

  const loadFileTree = async () => {
    try {
      const response = await fetch(`${API_BASE}/files/tree`);
      const data = await response.json();
      setFileTree(data);
    } catch (error) {
      console.error('Error loading file tree:', error);
    }
  };

  const handleNewConversation = async () => {
    try {
      await fetch(`${API_BASE}/conversation/new`, { method: 'POST' });
      setMessages([]);
      setInputMessage('');
    } catch (error) {
      console.error('Error creating new conversation:', error);
      alert('Failed to create new conversation');
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = inputMessage.trim();
    setInputMessage('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE}/conversation/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      setMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage = error.message || 'Failed to get response from agent';
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: `Error: ${errorMessage}` 
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileSelect = async (filePath) => {
    setSelectedFile(filePath);
    try {
      const response = await fetch(`${API_BASE}/files/${encodeURIComponent(filePath)}`);
      if (!response.ok) {
        throw new Error('Failed to read file');
      }
      const data = await response.json();
      setFileContent(data.content);
    } catch (error) {
      console.error('Error reading file:', error);
      setFileContent('Error: Failed to read file.');
    }
  };

  const toggleFolder = (itemPath) => {
    setExpandedFolders(prev => {
      const newSet = new Set(prev);
      if (newSet.has(itemPath)) {
        newSet.delete(itemPath);
      } else {
        newSet.add(itemPath);
      }
      return newSet;
    });
  };

  const renderFileTree = (items, depth = 0) => {
    return items.map((item, index) => {
      const isExpanded = expandedFolders.has(item.path);
      const hasChildren = item.children && item.children.length > 0;
      
      return (
        <div key={`${item.path}-${index}`}>
          <div
            className={`file-tree-item ${selectedFile === item.relative_path ? 'selected' : ''} ${!item.is_file ? 'folder' : ''}`}
            style={{ paddingLeft: `${depth * 16 + 12}px` }}
            onClick={() => {
              if (item.is_file) {
                handleFileSelect(item.relative_path);
              } else if (hasChildren) {
                toggleFolder(item.path);
              }
            }}
          >
            {hasChildren && (
              <span className="folder-toggle">
                {isExpanded ? '▼' : '▶'}
              </span>
            )}
            {!hasChildren && <span className="folder-toggle-spacer" />}
            <span className="file-icon">
              {item.is_file ? '📄' : '📁'}
            </span>
            <span>{item.name}</span>
          </div>
          {hasChildren && isExpanded && (
            <div className="file-tree-children">
              {renderFileTree(item.children, depth + 1)}
            </div>
          )}
        </div>
      );
    });
  };

  return (
    <div className="app-container">
      {/* Sidebar */}
      <div className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-title">DeepMemory Agent</div>
          <button className="new-conversation-btn" onClick={handleNewConversation}>
            New Conversation
          </button>
        </div>
        <div className="file-browser">
          <div className="file-tree">
            {fileTree.length > 0 ? renderFileTree(fileTree) : (
              <div className="empty-state">
                <div>No memory files</div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="main-content">
        <div className="conversation-header">
          <div className="conversation-title">Conversation</div>
        </div>
        <div className="conversation-messages">
          {messages.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">💬</div>
              <div>Start a conversation with your agent</div>
            </div>
          ) : (
            messages.map((msg, index) => (
              <div key={index} className={`message ${msg.role}`}>
                <div className="message-header">
                  {msg.role === 'user' ? 'You' : 'Agent'}
                </div>
                <div className="message-content">
                  {msg.role === 'assistant' ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.content}
                    </ReactMarkdown>
                  ) : (
                    msg.content
                  )}
                </div>
              </div>
            ))
          )}
          {isLoading && (
            <div className="message assistant">
              <div className="message-header">Agent</div>
              <div className="message-content">
                <div className="loading"></div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
        <div className="message-input-container">
          <form onSubmit={handleSendMessage} className="message-input-wrapper">
            <textarea
              className="message-input"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              placeholder="Type your message..."
              rows="1"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage(e);
                }
              }}
              disabled={isLoading}
            />
            <button
              type="submit"
              className="send-button"
              disabled={isLoading || !inputMessage.trim()}
            >
              Send
            </button>
          </form>
        </div>
      </div>

      {/* File Viewer */}
      {selectedFile && (
        <div className="file-viewer">
          <div className="file-viewer-header">
            <span>{selectedFile.split('/').pop()}</span>
            <button 
              className="file-viewer-close"
              onClick={() => {
                setSelectedFile(null);
                setFileContent('');
              }}
              aria-label="Close file viewer"
            >
              ×
            </button>
          </div>
          <div className="file-viewer-content">{fileContent}</div>
        </div>
      )}
    </div>
  );
}

export default App;
