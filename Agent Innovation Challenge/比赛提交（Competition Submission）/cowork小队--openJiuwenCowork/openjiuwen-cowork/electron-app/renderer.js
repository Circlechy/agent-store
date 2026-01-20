// Renderer process script
let currentDirectory = null;
let files = [];
let isProcessing = false;
let isConnected = false;
let currentAssistantMessage = null; // Track current assistant message for streaming
let toolCallsSection = null; // Track tool calls section
let toolCallsTitleText = null; // Track tool calls title text element

// DOM Elements
const selectDirBtn = document.getElementById('selectDirBtn');
const currentDirectoryEl = document.getElementById('currentDirectory');
const fileListEl = document.getElementById('fileList');
const chatArea = document.getElementById('chatArea');
const queryInput = document.getElementById('queryInput');
const sendBtn = document.getElementById('sendBtn');
const emptyState = document.getElementById('emptyState');
const connectionStatus = document.getElementById('connectionStatus');
const statusText = document.getElementById('statusText');
const suggestionChips = document.querySelectorAll('.suggestion-chip');

// Check connection status
async function checkConnection() {
  try {
    // Try to make a simple request to the API
    const response = await fetch('http://localhost:5001/health');
    if (response.ok) {
      setConnectionStatus(true);
    } else {
      setConnectionStatus(false);
    }
  } catch (error) {
    setConnectionStatus(false);
  }
}

function setConnectionStatus(connected) {
  isConnected = connected;
  if (connected) {
    connectionStatus.classList.remove('disconnected');
    connectionStatus.classList.add('connected');
    statusText.textContent = 'Connected';
    selectDirBtn.disabled = false;
  } else {
    connectionStatus.classList.remove('connected');
    connectionStatus.classList.add('disconnected');
    statusText.textContent = 'Backend Disconnected - Start: source venv/bin/activate && python3 api_server.py';
    selectDirBtn.disabled = true;
  }
}

// Check connection every 5 seconds
checkConnection();
setInterval(checkConnection, 5000);

// Event Listeners
selectDirBtn.addEventListener('click', selectDirectory);
sendBtn.addEventListener('click', sendMessage);
queryInput.addEventListener('input', updateSendButton);
queryInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

suggestionChips.forEach(chip => {
  chip.addEventListener('click', () => {
    const query = chip.dataset.query;
    queryInput.value = query;
    updateSendButton();
    sendMessage();
  });
});

async function selectDirectory() {
  // Check if backend is connected before allowing directory selection
  if (!isConnected) {
    addMessage('system', 'Backend is not connected. Please start the Python API server first:\n\nsource venv/bin/activate && python3 api_server.py');
    return;
  }

  try {
    const dir = await window.electronAPI.selectDirectory();
    if (dir) {
      currentDirectory = dir;
      currentDirectoryEl.textContent = dir;
      await loadFiles(dir);
    }
  } catch (error) {
    addMessage('system', `Error selecting directory: ${error.message}`);
  }
}

async function loadFiles(directory) {
  try {
    const result = await window.electronAPI.listDirectory(directory);
    files = result.files || [];
    renderFiles(files);
  } catch (error) {
    addMessage('system', `Error loading files: ${error.message}`);
  }
}

function renderFiles(files) {
  if (files.length === 0) {
    fileListEl.innerHTML = '<div style="padding: 20px; text-align: center; color: #6e6e73; font-size: 13px;">Directory is empty</div>';
    return;
  }

  fileListEl.innerHTML = files.map(file => `
    <div class="file-item" data-path="${file.path}" data-type="${file.type}">
      <svg class="file-icon ${file.type}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        ${file.type === 'directory'
          ? '<path d="M3 7v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-6l-2-2H5a2 2 0 0 0-2 2z"/>'
          : '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>'
        }
      </svg>
      <span class="file-name">${file.name}</span>
    </div>
  `).join('');

  // Add click handlers for files
  document.querySelectorAll('.file-item').forEach(item => {
    item.addEventListener('click', () => {
      document.querySelectorAll('.file-item').forEach(i => i.classList.remove('selected'));
      item.classList.add('selected');
    });

    item.addEventListener('dblclick', async () => {
      const filePath = item.dataset.path;
      const type = item.dataset.type;
      if (type === 'file') {
        try {
          const content = await window.electronAPI.getFileContent(filePath);
          addMessage('assistant', `File: ${filePath}\n\n\`\`\`\n${content.content || content}\n\`\`\``);
        } catch (error) {
          addMessage('system', `Error reading file: ${error.message}`);
        }
      }
    });
  });
}

function updateSendButton() {
  sendBtn.disabled = !queryInput.value.trim() || isProcessing;
}

async function sendMessage() {
  const query = queryInput.value.trim();
  if (!query || isProcessing) return;

  // Check if backend is connected
  if (!isConnected) {
    addMessage('system', 'Backend is not connected. Please start the Python API server first:\n\nsource venv/bin/activate && python3 api_server.py');
    return;
  }

  if (!currentDirectory) {
    addMessage('system', 'Please select a directory first');
    return;
  }

  queryInput.value = '';
  updateSendButton();

  // Remove empty state
  if (emptyState) {
    emptyState.style.display = 'none';
  }

  // Add user message
  addMessage('user', query);

  // Show processing state
  isProcessing = true;
  updateSendButton();

  try {
    // Use streaming API
    const response = await fetch('http://localhost:5001/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query: query,
        current_directory: currentDirectory
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    // Read stream
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let fullAnswer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            handleStreamChunk(data);
          } catch (e) {
            console.error('Error parsing SSE data:', e);
          }
        }
      }
    }

    // If there was any tool execution, show expand hint
    if (toolCallsSection) {
      const expandHint = toolCallsSection.querySelector('.expand-hint');
      if (expandHint) {
        expandHint.style.display = 'block';
      }
    }

    // Refresh files list if operations were performed
    await loadFiles(currentDirectory);

  } catch (error) {
    addMessage('system', `Error: ${error.message}`);
  }

  isProcessing = false;
  updateSendButton();
}

function handleStreamChunk(chunk) {
  const type = chunk.type;
  const toolName = chunk.tool_name;
  const inputs = chunk.inputs;
  const outputs = chunk.outputs;

  // Handle different chunk types
  if (type === 'tool_start' || type === 'tool_completed') {
    // Create or get tool calls section
    if (!toolCallsSection) {
      toolCallsSection = createToolCallsSection();
      chatArea.appendChild(toolCallsSection);
    }
    // Append to tool calls section
    appendToToolCalls(chunk);
  } else if (type === 'answer') {
    // Append answer to current assistant message
    if (!currentAssistantMessage) {
      currentAssistantMessage = addMessage('assistant', '');
    }
    // Format and append content
    const formattedContent = chunk.content
      .replace(/\n/g, '<br>')
      .replace(/```([\s\S]*?)```/g, '<pre style="background: rgba(0,0,0,0.05); padding: 10px; border-radius: 6px; margin: 8px 0; overflow-x: auto;"><code>$1</code></pre>')
      .replace(/`([^`]+)`/g, '<code style="background: rgba(0,0,0,0.05); padding: 2px 6px; border-radius: 4px;">$1</code>');
    currentAssistantMessage.innerHTML += formattedContent;
    chatArea.scrollTop = chatArea.scrollHeight;

    // Update title to "Agent is completed!" when answer is received
    if (toolCallsTitleText) {
      toolCallsTitleText.textContent = 'Agent is completed!';
      toolCallsTitleText.style.color = '#10b981';
    }
  } else if (type === 'error') {
    addMessage('system', chunk.content);
  }
}

function createToolCallsSection() {
  // Create the collapsible tool calls section
  const section = document.createElement('div');
  section.className = 'tool-calls-section';

  const sectionId = `tool-calls-${Date.now()}`;
  const contentId = `tool-calls-content-${Date.now()}`;

  section.innerHTML = `
    <div class="tool-calls-header" onclick="toggleToolCalls('${contentId}', this)">
      <div style="display: flex; align-items: center; gap: 8px; font-size: 13px;">
        <span class="toggle-icon" id="${contentId}-icon">▶</span>
        <span class="tool-calls-title-text" id="${contentId}-title">Agent is running...</span>
        <span style="color: #666; font-size: 12px;">(click to view details)</span>
      </div>
    </div>
    <div id="${contentId}" class="tool-calls-content" style="display: none;">
      <div class="tool-calls-list" id="${contentId}-list"></div>
      <div class="expand-hint" style="display: none; text-align: center; padding: 8px; color: #666; font-size: 12px;">
        ↑ Click to hide details ↑
      </div>
    </div>
  `;

  return section;
}

function appendToToolCalls(chunk) {
  const list = toolCallsSection.querySelector('.tool-calls-list');
  if (!list) return;

  const type = chunk.type;
  const toolName = chunk.tool_name;
  const inputs = chunk.inputs;
  const outputs = chunk.outputs;
  const content = chunk.content;

  const icon = type === 'tool_start' ? '⚡' : '✓';
  const statusText = type === 'tool_start' ? 'Executing' : 'Completed';
  const statusColor = type === 'tool_start' ? '#0071e3' : '#10b981';

  // Format inputs/outputs for display
  const formatData = (data) => {
    if (!data || typeof data !== 'object') return String(data);
    const entries = Object.entries(data);
    if (entries.length === 0) return '(none)';
    return entries.map(([k, v]) => {
      const value = typeof v === 'object' ? JSON.stringify(v, null, 2) : String(v);
      const displayValue = value.length > 500 ? value.substring(0, 500) + '...' : value;
      return `<div style="margin: 4px 0;"><span style="color: #666;">${k}:</span> <span style="font-family: monospace;">${displayValue.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</span></div>`;
    }).join('');
  };

  const toolItem = document.createElement('div');
  toolItem.className = 'tool-item';
  toolItem.innerHTML = `
    <div class="tool-item-header">
      <span style="color: ${statusColor}; margin-right: 8px;">${icon}</span>
      <span style="font-weight: 500;">${statusText}:</span>
      <span style="font-family: monospace; background: rgba(0,0,0,0.05); padding: 2px 6px; border-radius: 4px;">${toolName}</span>
    </div>
    ${inputs ? `<div class="tool-item-detail"><strong>Inputs:</strong>${formatData(inputs)}</div>` : ''}
    ${outputs ? `<div class="tool-item-detail"><strong>Outputs:</strong>${formatData({output: outputs})}</div>` : ''}
  `;

  list.appendChild(toolItem);
}

function toggleToolCalls(contentId, header) {
  const content = document.getElementById(contentId);
  const icon = document.getElementById(`${contentId}-icon`);
  const expandHint = content.querySelector('.expand-hint');

  if (content.style.display === 'none') {
    content.style.display = 'block';
    icon.textContent = '▼';
    if (expandHint) {
      expandHint.style.display = 'block';
    }
  } else {
    content.style.display = 'none';
    icon.textContent = '▶';
    if (expandHint) {
      expandHint.style.display = 'none';
    }
  }
}

function addMessage(type, content) {
  const messageEl = document.createElement('div');
  messageEl.className = `message ${type}`;

  if (type === 'assistant' && typeof content === 'string') {
    // Format the response with basic markdown-like formatting
    content = content
      .replace(/\n/g, '<br>')
      .replace(/```([\s\S]*?)```/g, '<pre style="background: rgba(0,0,0,0.05); padding: 10px; border-radius: 6px; margin: 8px 0; overflow-x: auto;"><code>$1</code></pre>')
      .replace(/`([^`]+)`/g, '<code style="background: rgba(0,0,0,0.05); padding: 2px 6px; border-radius: 4px;">$1</code>');
  }

  messageEl.innerHTML = content;
  chatArea.appendChild(messageEl);
  chatArea.scrollTop = chatArea.scrollHeight;

  return messageEl;
}

// Auto-resize textarea
queryInput.addEventListener('input', function() {
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 120) + 'px';
});
