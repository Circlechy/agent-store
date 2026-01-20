// ============ 聊天功能 ============

function initChat() {
    // 图片上传
    document.getElementById('chat-image-input').addEventListener('change', e => {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = ev => {
                attachedImage = ev.target.result;
                showAttachedImage(attachedImage);
            };
            reader.readAsDataURL(file);
        }
    });

    // 视频上传（临时）
    document.getElementById('chat-video-input').addEventListener('change', async e => {
        const file = e.target.files[0];
        if (file) {
            await uploadTempVideo(file);
        }
    });
    
    // 回车发送
    document.getElementById('chat-input').addEventListener('keypress', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
}

function triggerImagePicker() {
    const input = document.getElementById('chat-image-input');
    if (!input) return;
    if (typeof input.showPicker === 'function') {
        try {
            input.showPicker();
            return;
        } catch (e) {
            // fallback to click
        }
    }
    input.click();
}

function triggerVideoPicker() {
    const input = document.getElementById('chat-video-input');
    if (!input) return;
    if (typeof input.showPicker === 'function') {
        try {
            input.showPicker();
            return;
        } catch (e) {
            // fallback to click
        }
    }
    input.click();
}

async function uploadTempVideo(file) {
    try {
        const formData = new FormData();
        formData.append('file', file);
        showToast('视频上传中...', 'info');
        const response = await fetch('/api/vision/video/upload', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        if (data.success && data.video_id) {
            attachedVideoId = data.video_id;
            attachedVideoName = data.filename || file.name;
            showAttachedVideo(attachedVideoName);
            showToast(`视频已上传`, 'success');
        } else {
            showToast(data.error || '视频上传失败', 'error');
        }
    } catch (error) {
        showToast('视频上传失败: ' + error.message, 'error');
    } finally {
        const input = document.getElementById('chat-video-input');
        if (input) input.value = '';
    }
}

function showAttachedVideo(videoName) {
    const container = document.getElementById('video-attach');
    const nameEl = document.getElementById('attach-video-name');
    if (container && nameEl) {
        nameEl.textContent = videoName || '已上传视频';
        container.style.display = 'inline-flex';
    }
}

function removeAttachedVideo() {
    attachedVideoId = null;
    attachedVideoName = null;
    const container = document.getElementById('video-attach');
    if (container) {
        container.style.display = 'none';
    }
}

function toggleSpeaker() {
    currentSpeaker = currentSpeaker === 'driver' ? 'passenger' : 'driver';
    updateSpeakerDisplay();
    
    // 更新主题色
    updateChatTheme();
    
    fetch('/api/passengers/speaker', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ speaker: currentSpeaker })
    });
    
    const speakerName = getSpeakerName();
    showToast(`切换为${speakerName}`, 'info');
}

// 获取当前说话者的名字
function getSpeakerName() {
    if (currentSpeaker === 'driver') {
        return passengers.driver.name || '主驾';
    } else {
        return passengers.passenger.name || '副驾';
    }
}

// 更新说话者显示（显示实际名字）
function updateSpeakerDisplay() {
    const speakerTag = document.getElementById('speaker-tag');
    if (speakerTag) {
        const name = getSpeakerName();
        const seatLabel = currentSpeaker === 'driver' ? '主驾' : '副驾';
        // 如果名字与默认值不同，显示名字；否则显示座位
        if (name !== '主驾驶员' && name !== '副驾乘客' && name !== '主驾' && name !== '副驾') {
            speakerTag.textContent = name;
        } else {
            speakerTag.textContent = seatLabel;
        }
    }
}

function updateChatTheme() {
    const chatPanel = document.querySelector('.chat-panel');
    if (chatPanel) {
        chatPanel.classList.remove('theme-driver', 'theme-passenger');
        chatPanel.classList.add(currentSpeaker === 'driver' ? 'theme-driver' : 'theme-passenger');
    }
}

function selectCamera(camType) {
    // 更新按钮激活状态
    document.querySelectorAll('.cam-select-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    const btnId = `cam-${camType}-btn`;
    const btn = document.getElementById(btnId);
    if (btn) {
        btn.classList.add('active');
    }
    
    fetch(`/api/camera/${camType}`)
        .then(r => r.json())
        .then(data => {
            if (data.has_image && data.image_data) {
                attachedImage = data.image_data;
                showAttachedImage(attachedImage);
                showToast(`已选择${getCameraName(camType)}摄像头`, 'success');
            } else {
                // 没有图片，提示上传
                const input = document.createElement('input');
                input.type = 'file';
                input.accept = 'image/*';
                input.onchange = async (e) => {
                    const file = e.target.files[0];
                    if (file) {
                        const reader = new FileReader();
                        reader.onload = async (ev) => {
                            const imageData = ev.target.result;
                            
                            await fetch('/api/camera/set', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ camera_type: camType, image_data: imageData })
                            });
                            
                            attachedImage = imageData;
                            showAttachedImage(imageData);
                            showToast(`${getCameraName(camType)}摄像头已设置`, 'success');
                        };
                        reader.readAsDataURL(file);
                    }
                };
                input.click();
            }
        })
        .catch(() => showToast('获取摄像头失败', 'error'));
}

function getCameraName(type) {
    return { front: '前方', rear: '后方', interior: '车内' }[type] || type;
}

function showAttachedImage(imageData) {
    const container = document.getElementById('image-attach');
    const img = document.getElementById('attach-preview');
    img.src = imageData;
    container.style.display = 'inline-block';
}

function removeAttachedImage() {
    attachedImage = null;
    document.getElementById('image-attach').style.display = 'none';
    
    // 清除所有摄像头按钮的选中状态
    document.querySelectorAll('.cam-select-btn').forEach(btn => {
        btn.classList.remove('active');
    });
}

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    
    if (!message && !attachedImage && !attachedVideoId) {
        showToast('请输入消息', 'info');
        return;
    }
    
    const sendBtn = document.getElementById('send-btn');
    sendBtn.disabled = true;
    
    // 添加用户消息（传递当前说话者和视频名称）
    const videoNameToShow = attachedVideoName;
    addMessage('user', message, attachedImage, false, currentSpeaker, videoNameToShow);
    
    input.value = '';
    const imageToSend = attachedImage;
    const videoIdToSend = attachedVideoId;
    removeAttachedImage();
    clearAttachedVideo();
    
    // 添加加载状态
    const loadingId = addLoadingMessage();
    
    // 获取当前说话者信息
    const speakerName = getSpeakerName();
    const speakerSeat = currentSpeaker === 'driver' ? '主驾' : '副驾';
    const payload = {
        question: message,
        session_id: sessionId,
        user_id: currentSpeaker,
        speaker_name: speakerName,
        speaker_seat: speakerSeat,
        image_data: imageToSend,
        video_id: videoIdToSend,
        use_memory: true,
        tts_playback: ttsPlaybackMode
    };

    activeToolTrace = null;
    toolStepCounter = 0;
    activePlanTrace = null;

    await sendMessageStream(payload, loadingId);
    
    sendBtn.disabled = false;
}

function clearAttachedVideo() {
    attachedVideoId = null;
    attachedVideoName = null;
    const container = document.getElementById('video-attach');
    if (container) {
        container.style.display = 'none';
    }
}

function sendQuickMessage(message) {
    document.getElementById('chat-input').value = message;
    sendMessage();
}

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, ch => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[ch]));
}

function formatToolSteps(steps) {
    if (!steps || steps.length === 0) return '';
    const items = steps.map(step => {
        const tool = step.tool || 'unknown_tool';
        const statusClass = step.success === true ? 'success' : step.success === false ? 'fail' : 'pending';
        const statusText = step.success === true ? '成功' : step.success === false ? '失败' : '进行中';
        const resultSummary = step.result_summary || '';
        return `<div class="tool-step ${statusClass}" data-tool-name="${escapeHtml(tool)}" data-status-text="${statusText}" data-result-summary="${escapeHtml(resultSummary)}"><span class="tool-step-name">${escapeHtml(tool)}</span><span class="tool-step-status">${statusText}</span></div>`;
    }).join('');
    return `<div class="tool-trace"><div class="tool-trace-title">🧰 工具调用</div><div class="tool-trace-list">${items}</div></div>`;
}

function normalizePlanItems(plan) {
    if (!Array.isArray(plan)) return [];
    return plan.filter(step => step && step.node !== 'end');
}

function formatPlanItems(plan, currentNode) {
    const safePlan = normalizePlanItems(plan);
    if (safePlan.length === 0) {
        return '<div class="plan-empty">暂无计划</div>';
    }
    return safePlan.map(step => {
        const task = step.task || '';
        const node = step.node || '';
        const isFinished = step.is_finished === true;
        const isActive = !isFinished && currentNode && node === currentNode;
        const statusClass = isFinished ? 'success' : isActive ? 'active' : 'pending';
        const statusText = isFinished ? '已完成' : isActive ? '进行中' : '待执行';
        return `
            <div class="plan-step ${statusClass}">
                <span class="plan-step-task">${escapeHtml(task || node || '未命名任务')}</span>
                <span class="plan-step-node">${escapeHtml(node || '')}</span>
                <span class="plan-step-status">${statusText}</span>
            </div>
        `;
    }).join('');
}

function createPlanTraceMessage() {
    const container = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant plan-trace-message';
    const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });

    messageDiv.innerHTML = `
        <div class="message-avatar">🧭</div>
        <div class="message-content">
            <div class="message-bubble plan-trace-bubble">
                <div class="plan-trace-title">📋 任务计划</div>
                <div class="plan-trace-list"></div>
            </div>
            <div class="message-time">${time}</div>
        </div>
    `;

    container.appendChild(messageDiv);
    container.scrollTop = container.scrollHeight;

    return {
        root: messageDiv,
        listEl: messageDiv.querySelector('.plan-trace-list')
    };
}

function ensurePlanTrace() {
    if (!activePlanTrace) {
        activePlanTrace = createPlanTraceMessage();
    }
    return activePlanTrace;
}

function updatePlanTrace(plan, currentNode) {
    const trace = ensurePlanTrace();
    trace.listEl.innerHTML = formatPlanItems(plan, currentNode);
}

async function sendMessageStream(payload, loadingId) {
    let response;
    try {
        response = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
    } catch (error) {
        await sendMessageNonStream(payload, loadingId, error);
        return;
    }

    if (!response.ok || !response.body) {
        await sendMessageNonStream(payload, loadingId, new Error('无法建立流式连接'));
        return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    try {
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            buffer = processSseBuffer(buffer, loadingId);
        }
    } catch (error) {
        removeLoadingMessage(loadingId);
        addMessage('assistant', `网络错误：${error.message}`, null, true);
    }
}

function processSseBuffer(buffer, loadingId) {
    let idx;
    const cleanBuffer = buffer.replace(/\r/g, '');
    buffer = cleanBuffer;
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const rawEvent = buffer.slice(0, idx).trim();
        buffer = buffer.slice(idx + 2);
        if (!rawEvent) continue;
        const { eventType, data } = parseSseEvent(rawEvent);
        handleStreamEvent(eventType, data, loadingId);
    }
    return buffer;
}

function parseSseEvent(rawEvent) {
    let eventType = 'message';
    let dataStr = '';
    rawEvent.split('\n').forEach(line => {
        if (line.startsWith('event:')) {
            eventType = line.slice(6).trim();
        } else if (line.startsWith('data:')) {
            dataStr += line.slice(5).trim();
        }
    });
    let data = null;
    if (dataStr) {
        try {
            data = JSON.parse(dataStr);
        } catch (e) {
            data = { message: dataStr };
        }
    }
    return { eventType, data };
}

function handleStreamEvent(eventType, data, loadingId) {
    if (eventType === 'tool_start') {
        upsertToolStep(data, 'pending');
    } else if (eventType === 'tool_end') {
        upsertToolStep(data, data?.success === false ? 'fail' : 'success');
    } else if (eventType === 'plan_update' || eventType === 'plan') {
        if (data?.plan) {
            updatePlanTrace(data.plan, data?.current_node);
        }
    } else if (eventType === 'final') {
        removeLoadingMessage(loadingId);
        if (data && data.tool_steps && (!activeToolTrace || data.tool_steps.length > 0)) {
            addOrUpdateToolTraceFromSteps(data.tool_steps);
        }
        const answerText = data?.answer || '已完成';
        addMessage('assistant', answerText);
        
        // 检查是否有举报表单
        if (data?.report_form) {
            handleReportFormResponse({ report_form: data.report_form });
        }
        
        if (ttsPlaybackMode === 'browser_audio') {
            const played = playAudioBase64(data?.audio_base64, data?.audio_mime);
            if (!played) {
                maybeSpeakAssistant(answerText);
            }
        } else {
            maybeSpeakAssistant(answerText);
        }
    } else if (eventType === 'error') {
        removeLoadingMessage(loadingId);
        addMessage('assistant', `抱歉，出现了错误：${data?.error || '未知错误'}`, null, true);
    }
}

function sendMessageNonStream(payload, loadingId, error) {
    if (error) {
        console.warn('流式失败，回退到非流式:', error);
    }
    return fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
        .then(r => r.json())
        .then(data => {
            removeLoadingMessage(loadingId);
            if (data.success) {
                if (data.tool_steps && data.tool_steps.length > 0) {
                    addMessage('assistant', formatToolSteps(data.tool_steps));
                }
                addMessage('assistant', data.answer);
                if (ttsPlaybackMode === 'browser_audio') {
                    const played = playAudioBase64(data?.audio_base64, data?.audio_mime);
                    if (!played) {
                        maybeSpeakAssistant(data.answer);
                    }
                } else {
                    maybeSpeakAssistant(data.answer);
                }
            } else {
                addMessage('assistant', `抱歉，出现了错误：${data.error || '未知错误'}`, null, true);
            }
        })
        .catch(err => {
            removeLoadingMessage(loadingId);
            addMessage('assistant', `网络错误：${err.message}`, null, true);
        });
}

function createToolTraceMessage() {
    const container = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant tool-trace-message';
    const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });

    messageDiv.innerHTML = `
        <div class="message-avatar">🧰</div>
        <div class="message-content">
            <div class="message-bubble tool-trace-bubble">
                <div class="tool-trace-title">工具执行中</div>
                <div class="tool-trace-list"></div>
            </div>
            <div class="message-time">${time}</div>
        </div>
    `;

    container.appendChild(messageDiv);
    container.scrollTop = container.scrollHeight;

    return {
        root: messageDiv,
        listEl: messageDiv.querySelector('.tool-trace-list'),
        stepMap: new Map()
    };
}

function ensureToolTrace() {
    if (!activeToolTrace) {
        activeToolTrace = createToolTraceMessage();
    }
    return activeToolTrace;
}

function upsertToolStep(data, status) {
    if (!data) return;
    const trace = ensureToolTrace();
    const toolId = data.tool_call_id || `step-${toolStepCounter++}`;
    const toolName = data.tool || 'unknown_tool';
    const resultSummary = data.result_summary || '';
    let item = trace.stepMap.get(toolId);

    if (!item) {
        item = document.createElement('div');
        item.className = 'tool-step pending';
        item.dataset.toolId = toolId;
        item.innerHTML = `
            <span class="tool-step-name">${toolName}</span>
            <span class="tool-step-status">进行中</span>
        `;
        trace.listEl.appendChild(item);
        trace.stepMap.set(toolId, item);
    }

    const statusEl = item.querySelector('.tool-step-status');
    const statusText = status === 'success' ? '成功' : status === 'fail' ? '失败' : '进行中';
    item.classList.remove('success', 'fail', 'pending');
    item.classList.add(status || 'pending');
    statusEl.textContent = statusText;
    item.dataset.toolName = toolName;
    item.dataset.statusText = statusText;
    if (resultSummary) {
        item.dataset.resultSummary = resultSummary;
    }
}

function ensureToolDetailModal() {
    if (toolDetailModal) return toolDetailModal;
    const root = document.createElement('div');
    root.className = 'tool-detail-modal';
    root.innerHTML = `
        <div class="tool-detail-backdrop"></div>
        <div class="tool-detail-card" role="dialog" aria-modal="true">
            <div class="tool-detail-header">
                <div class="tool-detail-title">工具详情</div>
                <button class="tool-detail-close" type="button">✕</button>
            </div>
            <div class="tool-detail-body">
                <div class="tool-detail-row">
                    <div class="tool-detail-label">状态</div>
                    <div class="tool-detail-value tool-detail-status"></div>
                </div>
                <div class="tool-detail-row">
                    <div class="tool-detail-label">结果</div>
                    <pre class="tool-detail-pre tool-detail-result"></pre>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(root);
    const backdrop = root.querySelector('.tool-detail-backdrop');
    const closeBtn = root.querySelector('.tool-detail-close');
    backdrop.addEventListener('click', closeToolDetailModal);
    closeBtn.addEventListener('click', closeToolDetailModal);
    toolDetailModal = {
        root,
        card: root.querySelector('.tool-detail-card'),
        titleEl: root.querySelector('.tool-detail-title'),
        statusEl: root.querySelector('.tool-detail-status'),
        resultEl: root.querySelector('.tool-detail-result')
    };
    return toolDetailModal;
}

function closeToolDetailModal() {
    if (!toolDetailModal) return;
    toolDetailModal.root.style.display = 'none';
}

function showToolDetailModal(stepEl) {
    const modal = ensureToolDetailModal();
    const toolName = stepEl.dataset.toolName || stepEl.querySelector('.tool-step-name')?.textContent?.trim() || 'unknown_tool';
    const statusText = stepEl.dataset.statusText || stepEl.querySelector('.tool-step-status')?.textContent?.trim() || '未知';
    const resultSummary = stepEl.dataset.resultSummary || '';

    modal.titleEl.textContent = toolName;
    modal.statusEl.textContent = statusText;
    modal.resultEl.textContent = resultSummary || '无';

    modal.root.style.display = 'block';
    requestAnimationFrame(() => {
        const rect = stepEl.getBoundingClientRect();
        const card = modal.card;
        const cardRect = card.getBoundingClientRect();
        const padding = 12;
        let left = rect.left;
        let top = rect.bottom + 8;

        if (left + cardRect.width + padding > window.innerWidth) {
            left = window.innerWidth - cardRect.width - padding;
        }
        if (left < padding) left = padding;

        if (top + cardRect.height + padding > window.innerHeight) {
            top = rect.top - cardRect.height - 8;
        }
        if (top < padding) top = padding;

        card.style.left = `${left}px`;
        card.style.top = `${top}px`;
    });
}

function addOrUpdateToolTraceFromSteps(steps) {
    if (!steps || steps.length === 0) return;
    const trace = ensureToolTrace();
    steps.forEach(step => {
        const toolId = step.tool_call_id || `step-${toolStepCounter++}`;
        const hasStatus = step.success === true || step.success === false;
        const existing = trace.stepMap.get(toolId);

        if (!hasStatus && existing) {
            if (step.tool) {
                existing.dataset.toolName = step.tool;
            }
            if (step.result_summary) {
                existing.dataset.resultSummary = step.result_summary;
            }
            return;
        }

        upsertToolStep({
            tool_call_id: toolId,
            tool: step.tool,
            result_summary: step.result_summary,
            success: step.success
        }, hasStatus ? (step.success ? 'success' : 'fail') : 'pending');
    });
}

function addMessage(role, content, imageData = null, isError = false, speaker = null, videoName = null) {
    const container = document.getElementById('chat-messages');
    
    // 移除欢迎消息（如果是第一条真正的消息）
    const welcome = container.querySelector('.welcome-message');
    if (welcome && container.querySelectorAll('.message').length === 0) {
        welcome.style.display = 'none';
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    // 如果是用户消息，添加说话者标记（用于区分主驾/副驾消息颜色）
    if (role === 'user' && speaker) {
        messageDiv.dataset.speaker = speaker;
        messageDiv.classList.add(`speaker-${speaker}`);
    }
    
    const avatar = role === 'user' ? '👤' : '🤖';
    const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    
    // 获取说话者名字用于显示
    let speakerLabel = '';
    if (role === 'user' && speaker) {
        const speakerName = speaker === 'driver' ? 
            (passengers.driver.name !== '主驾驶员' ? passengers.driver.name : '主驾') : 
            (passengers.passenger.name !== '副驾乘客' ? passengers.passenger.name : '副驾');
        speakerLabel = `<span class="speaker-label">${speakerName}</span>`;
    }
    
    let imageHtml = '';
    if (imageData) {
        imageHtml = `<div class="message-image"><img src="${imageData}" alt=""></div>`;
    }
    
    let videoHtml = '';
    if (videoName) {
        videoHtml = `<div class="message-video"><span class="video-icon">🎬</span><span class="video-label">${escapeHtml(videoName)}</span></div>`;
    }
    
    messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            ${speakerLabel}
            ${imageHtml}
            ${videoHtml}
            <div class="message-bubble ${isError ? 'error' : ''}">${formatMessage(content)}</div>
            <div class="message-time">${time}</div>
        </div>
    `;
    
    container.appendChild(messageDiv);
    container.scrollTop = container.scrollHeight;
}

function formatMessage(content) {
    // 简单的格式化：换行转<br>，代码块等
    return content
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/`(.*?)`/g, '<code>$1</code>');
}

function addLoadingMessage() {
    const container = document.getElementById('chat-messages');
    const id = 'loading-' + Date.now();
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant loading';
    messageDiv.id = id;
    messageDiv.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">
            <div class="message-bubble">
                <span>思考中</span>
                <div class="typing-indicator">
                    <span></span><span></span><span></span>
                </div>
            </div>
        </div>
    `;
    
    container.appendChild(messageDiv);
    container.scrollTop = container.scrollHeight;
    
    return id;
}

function removeLoadingMessage(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function clearChat() {
    openClearChatModal();
}

function openClearChatModal() {
    const modal = document.getElementById('clear-chat-modal');
    if (modal) {
        modal.style.display = 'flex';
    }
}

function closeClearChatModal() {
    const modal = document.getElementById('clear-chat-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

async function clearChatAction(action) {
    if (action === 'session') {
        await clearCurrentConversation();
        closeClearChatModal();
        return;
    }

    if (action === 'memory') {
        await clearMemoryHistory();
        closeClearChatModal();
        return;
    }

    if (action === 'all') {
        await clearCurrentConversation();
        await clearMemoryHistory();
        closeClearChatModal();
    }
}

async function clearCurrentConversation() {
    try {
        await fetch('/api/chat/clear', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId })
        });

        sessionId = 'session_' + Date.now();
        localStorage.setItem('chatSessionId', sessionId);
        console.log('[对话] 已生成新的会话ID:', sessionId);

        const container = document.getElementById('chat-messages');
        container.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-avatar">🚗</div>
                <div class="welcome-text">
                    <h4>你好，我是智能座舱助手</h4>
                    <p>我可以帮你控制空调、车窗、音乐等，也可以识别图片、导航规划。试试说：</p>
                    <div class="welcome-suggestions">
                        <button class="suggestion-btn" onclick="sendQuickMessage('打开空调，温度调到24度')">🌡️ 打开空调</button>
                        <button class="suggestion-btn" onclick="sendQuickMessage('播放周杰伦的歌')">🎵 播放音乐</button>
                        <button class="suggestion-btn" onclick="sendQuickMessage('导航去最近的加油站')">📍 附近导航</button>
                        <button class="suggestion-btn" onclick="sendQuickMessage('开启约会模式')">💕 场景模式</button>
                    </div>
                </div>
            </div>
        `;

        showToast('当前对话已清空', 'success');
    } catch (error) {
        showToast('清空当前对话失败', 'error');
    }
}

async function clearMemoryHistory() {
    try {
        const response = await fetch('/api/memory/clear', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ clear_all: true })
        });
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || '清空失败');
        }
        showToast('记忆历史已清空', 'success');
    } catch (error) {
        showToast('清空记忆历史失败', 'error');
    }
}

async function loadChatHistory() {
    try {
        const response = await fetch(`/api/chat/history/${sessionId}`);
        const data = await response.json();
        
        if (data.success && data.messages && data.messages.length > 0) {
            const container = document.getElementById('chat-messages');
            const welcome = container.querySelector('.welcome-message');
            if (welcome) welcome.style.display = 'none';
            
            data.messages.forEach(msg => {
                addMessage(msg.role, msg.content);
            });
        }
    } catch (error) {
        // 静默失败
    }
}

// ============ 交通违规举报功能 ============

// 当前举报表单数据
let currentReportForm = null;

/**
 * 渲染举报卡片到聊天气泡中
 */
function renderReportCard(reportForm) {
    const fields = reportForm.fields;
    
    // 构建字段HTML
    let fieldsHtml = '';
    const displayFields = [
        { key: 'violation_type', label: '违规类型' },
        { key: 'report_time', label: '时间' },
        { key: 'location', label: '地点' },
        { key: 'vehicle_type', label: '车型' },
        { key: 'license_plate', label: '车牌' }
    ];
    
    displayFields.forEach(({ key, label }) => {
        const field = fields[key];
        if (field) {
            const value = field.value || '';
            const valueClass = !value ? 'missing' : (field.auto_filled ? 'auto' : '');
            const displayValue = value || '待填写';
            fieldsHtml += `
                <div class="report-card-field">
                    <span class="report-card-label">${label}：</span>
                    <span class="report-card-value ${valueClass}">${escapeHtml(displayValue)}</span>
                </div>
            `;
        }
    });
    
    return `
        <div class="report-card-bubble">
            <div class="report-card-header">
                <span class="report-card-icon">🚨</span>
                <span class="report-card-title">${reportForm.form_title || '交通违规举报'}</span>
            </div>
            <div class="report-card-body">
                ${fieldsHtml}
            </div>
            <div class="report-card-footer">
                <button class="report-card-btn" onclick="openReportPanel()">查看/编辑举报表单</button>
            </div>
        </div>
    `;
}

/**
 * 显示举报表单模态框
 */
function openReportPanel() {
    const modal = document.getElementById('report-modal');
    if (modal) {
        modal.style.display = 'flex';
        // 禁止背景滚动
        document.body.style.overflow = 'hidden';
    }
}

/**
 * 关闭举报表单模态框
 */
function closeReportPanel() {
    const modal = document.getElementById('report-modal');
    if (modal) {
        modal.style.display = 'none';
        // 恢复背景滚动
        document.body.style.overflow = '';
    }
}

/**
 * 用数据填充举报表单
 */
function fillReportForm(reportForm) {
    currentReportForm = reportForm;
    const fields = reportForm.fields;
    const form = document.getElementById('report-form');
    
    if (!form) return;
    
    // 填充各字段
    Object.keys(fields).forEach(fieldName => {
        const fieldData = fields[fieldName];
        const input = form.querySelector(`[name="${fieldName}"]`);
        
        if (input) {
            if (fieldName === 'report_time' && fieldData.value) {
                // datetime-local 需要特殊格式
                const dt = new Date(fieldData.value.replace(' ', 'T'));
                if (!isNaN(dt.getTime())) {
                    input.value = dt.toISOString().slice(0, 16);
                }
            } else {
                input.value = fieldData.value || '';
            }
            
            // 标记自动填充的字段
            if (fieldData.auto_filled && fieldData.value) {
                input.classList.add('auto-filled');
            } else {
                input.classList.remove('auto-filled');
            }
        }
    });
    
    // 显示车牌警告
    const licenseWarning = document.getElementById('license-warning');
    if (licenseWarning) {
        const licensePlate = fields.license_plate;
        if (licensePlate && licensePlate.warning) {
            licenseWarning.textContent = licensePlate.warning;
            licenseWarning.style.display = 'block';
        } else {
            licenseWarning.style.display = 'none';
        }
    }
    
    // 显示建议
    const suggestionsContainer = document.getElementById('report-suggestions');
    if (suggestionsContainer && reportForm.suggestions) {
        suggestionsContainer.innerHTML = reportForm.suggestions.map(s => 
            `<div class="report-suggestion">${escapeHtml(s)}</div>`
        ).join('');
    }
    
    // 显示图片
    const imagePreview = document.getElementById('report-image-preview');
    const noImageHint = document.getElementById('no-image-hint');
    const reportImage = document.getElementById('report-image');
    
    if (reportForm.has_image && reportForm.image_data) {
        if (imagePreview) imagePreview.style.display = 'block';
        if (noImageHint) noImageHint.style.display = 'none';
        if (reportImage) reportImage.src = reportForm.image_data;
    } else {
        if (imagePreview) imagePreview.style.display = 'none';
        if (noImageHint) noImageHint.style.display = 'block';
    }
}

/**
 * 处理举报表单响应（工具调用结果）
 */
function handleReportFormResponse(reportData) {
    if (!reportData || !reportData.report_form) return;
    
    const reportForm = reportData.report_form;
    
    // 填充并显示表单面板
    fillReportForm(reportForm);
    openReportPanel();
}

/**
 * 提交举报
 */
async function submitReport() {
    const form = document.getElementById('report-form');
    if (!form) return;
    
    const formData = new FormData(form);
    const data = {};
    formData.forEach((value, key) => {
        data[key] = value;
    });
    
    // 验证必填字段
    const required = ['violation_type', 'report_time', 'location'];
    const missing = required.filter(field => !data[field]);
    
    if (missing.length > 0) {
        showToast('请填写必填字段', 'warning');
        return;
    }
    
    // 模拟提交（实际项目中应调用后端API）
    try {
        // 这里可以调用实际的举报API
        // const response = await fetch('/api/report/submit', {
        //     method: 'POST',
        //     headers: { 'Content-Type': 'application/json' },
        //     body: JSON.stringify(data)
        // });
        
        // 更新状态
        const statusBadge = document.querySelector('.status-badge');
        if (statusBadge) {
            statusBadge.textContent = '已提交';
            statusBadge.classList.remove('draft');
            statusBadge.classList.add('submitted');
        }
        
        showToast('举报已提交，感谢您的反馈！', 'success');
        
        // 延迟关闭面板
        setTimeout(() => {
            closeReportPanel();
        }, 1500);
        
    } catch (error) {
        showToast('提交失败，请稍后重试', 'error');
    }
}

// 导出到全局
window.openReportPanel = openReportPanel;
window.closeReportPanel = closeReportPanel;
window.submitReport = submitReport;
window.handleReportFormResponse = handleReportFormResponse;
