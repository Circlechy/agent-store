// 多Agent协作系统
class AgentSystem {
    constructor() {
        this.agents = {
            companion: new CompanionAgent(),
            teacher: new TeacherAgent(),
            storyteller: new StorytellerAgent()
        };
        this.currentMode = 'learning';
        this.userId = 'default_user';
        this.context = { age: 6 };
        this.useBackend = typeof window.apiClient !== 'undefined';
        this.chatUI = window.chatUI || null;
        this._bindVoiceEvents();
        this.initChatHistory();
    }

    _bindVoiceEvents() {
        document.addEventListener('voice-input-result', (event) => {
            const detail = event.detail || {};
            if (!detail.transcript) return;
            if (window.voiceInputTarget) return;
            if (detail.isFinal) {
                this.processUserInput(detail.transcript, { inputType: 'voice' });
            }
        });

        document.addEventListener('voice-input-error', (event) => {
            const detail = event.detail || {};
            if (detail.error === 'not_supported') {
                this._showSystemNotice('当前浏览器不支持语音输入，请使用文字输入。');
            }
        });
    }

    async initChatHistory() {
        if (this.useBackend && window.apiClient && window.apiClient.getChatHistory) {
            try {
                const history = await window.apiClient.getChatHistory(this.userId);
                this.chatUI = window.chatUI || this.chatUI;
                if (this.chatUI) {
                    this.chatUI.renderHistory(history || []);
                }
            } catch (error) {
                console.warn('Failed to load chat history:', error);
            }
        }
    }

    async clearHistory() {
        if (this.useBackend && window.apiClient && window.apiClient.clearChatHistory) {
            try {
                await window.apiClient.clearChatHistory(this.userId);
            } catch (error) {
                console.warn('Failed to clear chat history:', error);
            }
        }
        if (this.chatUI) {
            this.chatUI.clear();
        }
    }

    // 处理用户输入
    async processUserInput(input, options = {}) {
        if (!input || input.trim() === '') return;

        // 避免短时间内重复触发同一输入导致重复渲染
        const now = Date.now();
        if (this._lastUserInput === input && now - (this._lastUserInputAt || 0) < 300) {
            return;
        }
        this._lastUserInput = input;
        this._lastUserInputAt = now;
        
        const inputType = options.inputType || 'text';
        let targetElement = options.targetElement || null;
        if (!targetElement && options.outputElementId) {
            targetElement = document.getElementById(options.outputElementId);
        }
        if (this.chatUI) {
            this.chatUI.addMessage({
                role: 'user',
                content: input,
                source: inputType
            });
        }
        // 如果是QA类型或Story类型，不显示typing indicator（因为不会显示流式文本）
        const isQAIntent = options.intentOverride === 'qa' || options.intent === 'qa';
        const isStoryIntent = options.intentOverride === 'story' || options.intent === 'story';
        const typingMessage = (!isQAIntent && !isStoryIntent && this.chatUI) ? this.chatUI.showTypingIndicator() : null;
        if (window.novaOrb) {
            window.novaOrb.setState('thinking');
        }
        
        try {
            let response;
            
            // 如果API客户端可用，使用后端API
            if (this.useBackend && window.apiClient) {
                if (targetElement) {
                    response = await this.processWithBackendToElement(
                        input,
                        options.intent || null,
                        targetElement
                    );
                } else {
                    response = await this.processWithBackend(input, options.intent || null, inputType);
                }
            } else {
                // 否则使用本地Agent
                const agent = this.routeToAgent(input);
                response = await agent.process(input);
                if (!response.handled_by) {
                    if (agent.type === 'teacher') {
                        response.handled_by = 'mentor';
                    } else if (agent.type === 'storyteller') {
                        response.handled_by = 'artist';
                    } else {
                        response.handled_by = agent.type || 'companion';
                    }
                }
                if (!response.agents) {
                    response.agents = [response.handled_by];
                }
            }
            
            if (this.chatUI) {
                this.chatUI.removeTypingIndicator(typingMessage);
            }

            if (targetElement && response && typeof response.content === 'string') {
                targetElement.textContent = response.content;
            }

            const agentType = response.type || response.handled_by || 'companion';
            this.displayResponse(input, response, agentType, { skipChatUI: response._streamed });
            if (window.novaOrb) {
                window.novaOrb.setState('speaking');
                setTimeout(() => window.novaOrb.setState('idle'), 1200);
            }
        } catch (error) {
            console.error('Agent processing error:', error);
            if (this.chatUI) {
                this.chatUI.removeTypingIndicator(typingMessage);
                this.chatUI.addMessage({
                    role: 'assistant',
                    content: '抱歉，我遇到了一些问题，请再试一次。'
                });
            }
            if (window.novaOrb) {
                window.novaOrb.setState('idle');
            }
        }
    }

    // 使用后端API处理
    async processWithBackend(input, intentOverride = null, inputType = 'text', onStreamStart = null) {
        try {
            // 使用流式响应
            let finalResponse = {
                content: '',
                type: 'companion',
            };
            
            let contentBuffer = '';
            let streamMessageEl = null;
            let streamStarted = false;
            
            await window.apiClient.chatStream(
                input,
                this.userId,
                this.context,
                (chunk) => {
                    if (chunk && chunk.__conversation_id) {
                        finalResponse.conversation_id = chunk.__conversation_id;
                    }
                    if (chunk && typeof chunk.content === 'string' && chunk.content.startsWith("type='tracer_")) {
                        return;
                    }
                    if (chunk && chunk.payload && chunk.payload.traceId) {
                        return;
                    }
                    
                    // 先更新响应信息（以便后续判断）
                    if (chunk.intent) {
                        finalResponse.intent = chunk.intent;
                    }
                    if (chunk.handled_by) {
                        finalResponse.handled_by = chunk.handled_by;
                        if (!finalResponse.agents || finalResponse.agents.length === 0) {
                            finalResponse.agents = [chunk.handled_by];
                        }
                        // 根据handled_by确定类型
                        if (chunk.handled_by === 'mentor') {
                            finalResponse.type = 'teacher';
                        } else if (chunk.handled_by === 'artist') {
                            finalResponse.type = chunk.intent === 'story' ? 'storyteller' : 'artist';
                        }
                    }
                    if (chunk.agents && Array.isArray(chunk.agents)) {
                        finalResponse.agents = chunk.agents;
                    }
                    if (chunk.content) {
                        finalResponse.content = chunk.content;
                    }
                    if (chunk.content_type) {
                        finalResponse.content_type = chunk.content_type;
                    }
                    if (chunk.lesson_type) {
                        finalResponse.lesson_type = chunk.lesson_type;
                    }
                    if (chunk.lesson) {
                        finalResponse.lesson = chunk.lesson;
                    }
                    if (chunk.metadata) {
                        finalResponse.metadata = chunk.metadata;
                    }
                    
                    // 处理流式数据
                    // 如果是QA类型或Story类型，跳过流式文本显示，等待最终的结构化内容
                    const isQA = finalResponse.content_type === 'qa' || finalResponse.lesson_type === 'qa' || finalResponse.intent === 'qa' || intentOverride === 'qa';
                    const isStory = finalResponse.content_type === 'story' || finalResponse.intent === 'story' || intentOverride === 'story';
                    const skipStreaming = isQA || isStory;
                    
                    // 如果检测到QA或Story类型且已经创建了流式消息，立即删除它
                    if (skipStreaming && streamMessageEl && this.chatUI) {
                        this.chatUI.removeMessage(streamMessageEl);
                        streamMessageEl = null;
                        streamStarted = false;
                    }
                    
                    if (chunk.response && typeof chunk.response !== 'string') {
                        // 结构化响应（如学习内容的图文音频数组）
                        finalResponse.response = chunk.response;
                    } else if (chunk.response && !skipStreaming) {
                        contentBuffer += chunk.response;
                        if (!streamStarted) {
                            streamStarted = true;
                            if (typeof onStreamStart === 'function') {
                                onStreamStart();
                            }
                            if (this.chatUI) {
                                streamMessageEl = this.chatUI.addMessage({
                                    role: 'assistant',
                                    content: '',
                                    allowEmpty: true,
                                    agents: finalResponse.agents && finalResponse.agents.length ? finalResponse.agents : undefined,
                                    intent: finalResponse.intent || undefined,
                                    conversation_id: finalResponse.conversation_id
                                });
                            }
                        }
                        if (this.chatUI && streamMessageEl) {
                            this.chatUI.enqueueTyping(streamMessageEl, chunk.response, 18);
                        }
                        // 实时更新显示
                        if (window.contentGenerator) {
                            // 可以在这里实现流式显示
                        }
                    } else if (chunk.response && skipStreaming) {
                        // QA或Story类型：只收集内容，不显示流式文本
                        contentBuffer += chunk.response;
                    }
                },
                intentOverride,
                inputType
            );
            
            // 如果没有流式内容，使用最终响应
            if (!finalResponse.content && contentBuffer) {
                finalResponse.content = contentBuffer;
            }

            if (!finalResponse.agents && finalResponse.handled_by) {
                finalResponse.agents = [finalResponse.handled_by];
            }

            finalResponse._streamed = streamStarted;
            
            // 如果是QA类型或Story类型且已经创建了流式消息，需要删除它（因为会通过displayResponse显示）
            const isQA = finalResponse.content_type === 'qa' || finalResponse.lesson_type === 'qa' || finalResponse.intent === 'qa';
            const isStory = finalResponse.content_type === 'story' || finalResponse.intent === 'story';
            if ((isQA || isStory) && streamMessageEl && this.chatUI) {
                // 删除流式消息，因为会通过displayResponse显示
                this.chatUI.removeMessage(streamMessageEl);
            }
            
            // 如果还是没有内容，使用非流式API
            if (!finalResponse.content) {
                const result = await window.apiClient.chat(input, this.userId, this.context, intentOverride, inputType);
                finalResponse.content = result.content || result.response || '';
                finalResponse.intent = result.intent || '';
                finalResponse.handled_by = result.handled_by || '';
                finalResponse.agents = result.agents || [];
                finalResponse.content_type = result.content_type || '';
                finalResponse.metadata = result.metadata || {};
                if (result.lesson) {
                    finalResponse.lesson = result.lesson;
                    finalResponse.lesson_type = result.lesson_type || result.lesson.lesson_type || '';
                    if (!finalResponse.content && typeof result.lesson.teaching_content === 'string') {
                        finalResponse.content = result.lesson.teaching_content;
                    }
                }
                if (result.response) {
                    finalResponse.response = result.response;
                }
                
                // 根据handled_by确定类型
                if (result.handled_by === 'mentor') {
                    finalResponse.type = 'teacher';
                } else if (result.handled_by === 'artist') {
                    finalResponse.type = result.intent === 'story' || result.content_type === 'story' ? 'storyteller' : 'artist';
                }
            }
            
            return finalResponse;
        } catch (error) {
            console.error('Backend API error:', error);
            // 如果后端失败，回退到本地Agent
            const agent = this.routeToAgent(input);
            return await agent.process(input);
        }
    }

    // 使用后端API处理并输出到指定元素（非流式，避免重复调用）
    async processWithBackendToElement(input, intentOverride, targetElement) {
        targetElement.textContent = '正在生成内容...';

        try {
            const result = await window.apiClient.chat(input, this.userId, this.context, intentOverride);
            let content = result.content || '';
            if (!content && result.lesson && typeof result.lesson.teaching_content === 'string') {
                content = result.lesson.teaching_content;
            }
            if (!content && typeof result.response === 'string') {
                content = result.response;
            }
            targetElement.textContent = content || '暂时没有返回内容，请稍后重试。';
            return {
                content: content || targetElement.textContent,
                lesson: result.lesson,
                lesson_type: result.lesson_type || result.lesson?.lesson_type,
                response: result.response,
                handled_by: result.handled_by,
                type: result.handled_by === 'mentor' ? 'teacher' : 'companion',
            };
        } catch (error) {
            console.error('Backend API error (target element):', error);
            const agent = this.routeToAgent(input);
            const response = await agent.process(input);
            targetElement.textContent = response.content || '';
            return response;
        }
    }

    // 路由到相应的Agent
    routeToAgent(input) {
        const lowerInput = input.toLowerCase();
        
        // 问答相关（十万个为什么）
        if (lowerInput.includes('为什么') || lowerInput.includes('怎么') || lowerInput.includes('如何') || 
            lowerInput.includes('是什么') || lowerInput.includes('什么是') || 
            lowerInput.includes('?') || lowerInput.includes('？') ||
            lowerInput.includes('吗') || lowerInput.includes('呢')) {
            return this.agents.teacher; // 使用 teacher agent 处理问答
        }
        
        // 故事相关
        if (lowerInput.includes('故事') || lowerInput.includes('讲') || lowerInput.includes('睡前')) {
            return this.agents.storyteller;
        }
        
        // 学习相关
        if (lowerInput.includes('学习') || lowerInput.includes('教')) {
            return this.agents.teacher;
        }
        
        // 默认使用陪伴Agent
        return this.agents.companion;
    }

    // 显示响应
    displayResponse(question, response, agentType, options = {}) {
        const intent = response.intent || '';
        const handledBy = response.handled_by || '';
        const agents = response.agents || (handledBy ? [handledBy] : []);
        const content = response.content || response.response || '';

        // 处理故事类型响应
        if (intent === 'story' || response.content_type === 'story') {
            // 解析故事内容
            let storyData = null;
            if (typeof content === 'object' && content !== null) {
                storyData = content;
            } else if (typeof response.content === 'object' && response.content !== null) {
                storyData = response.content;
            }
            
            // 提取故事文本（用于主对话框显示）
            // 格式：直接输出标题，空一行，分段的故事内容（自然分段，不用<br>）
            let storyText = '';
            if (storyData) {
                if (storyData.title && storyData.text) {
                    // 有标题和文本，组合显示：标题，空一行，正文
                    storyText = `${storyData.title}\n\n${storyData.text}`;
                } else if (storyData.text) {
                    // 只有文本
                    storyText = storyData.text;
                } else if (storyData.title && storyData.paragraphs && Array.isArray(storyData.paragraphs)) {
                    // 有多段落，提取文本：标题，空一行，正文段落（自然分段）
                    storyText = `${storyData.title}\n\n`;
                    storyText += storyData.paragraphs.map(p => p.text || p).join('\n\n');
                } else if (typeof content === 'string') {
                    storyText = content;
                } else {
                    storyText = response.response || '（没有返回内容）';
                }
            } else if (typeof content === 'string') {
                storyText = content;
            } else {
                storyText = response.response || '（没有返回内容）';
            }
            
            // 打开弹窗显示多模态内容（图文音频）
            const modal = document.getElementById('storyModal');
            const storyContentDiv = document.getElementById('storyContent');
            if (modal && storyContentDiv) {
                modal.classList.add('active');
                
                if (storyData && storyData.title && storyData.paragraphs) {
                    // 显示多模态故事内容（图文音频）
                    this.displayStoryContent(storyData, storyContentDiv);
                } else if (storyData && storyData.text) {
                    // 只有文本内容
                    storyContentDiv.innerHTML = `<div class="story-text">${storyData.text.replace(/\n/g, '<br>')}</div>`;
                } else {
                    // 降级显示
                    storyContentDiv.textContent = storyText;
                }
                if (window.appController && typeof window.appController.setModalVoiceControlsVisible === 'function') {
                    window.appController.setModalVoiceControlsVisible('story', false);
                }
            }
            
            // 在主对话框中也显示文本（自然分段，不用<br>）
            if (this.chatUI && !options.skipChatUI && storyText) {
                // 直接使用文本，保留换行符，让CSS的white-space: pre-wrap处理
                const messageEl = this.chatUI.addMessage({
                    role: 'assistant',
                    content: storyText,
                    agents: agents.length ? agents : undefined,
                    intent: 'story',
                    conversation_id: response.conversation_id
                });
                // 为故事消息添加样式，保留换行和自然分段
                if (messageEl) {
                    const textEl = messageEl.querySelector('.message-text-preview, .message-text-full, .message-text');
                    if (textEl) {
                        textEl.style.whiteSpace = 'pre-wrap';
                    }
                }
            }
            // 已显示，直接返回，避免重复显示
            return;
        }

        // 处理问答类型响应（十万个为什么）
        if (intent === 'qa' || response.content_type === 'qa' || response.lesson_type === 'qa') {
            // 解析问答内容
            let qaData = null;
            if (typeof content === 'object' && content !== null) {
                qaData = content;
            } else if (typeof response.content === 'object' && response.content !== null) {
                qaData = response.content;
            }
            
            // 提取答案文本（用于主对话框显示）
            let answerText = '';
            if (qaData) {
                answerText = qaData.answer_content || qaData.answer || qaData.content || '';
            } else if (typeof content === 'string') {
                answerText = content;
            } else {
                answerText = response.response || '';
            }
            
            // 打开弹窗显示多模态内容（图文音频）
            const qaModal = document.getElementById('qaModal');
            const qaContentDiv = document.getElementById('qaContent');
            if (qaModal && qaContentDiv && qaData) {
                qaModal.classList.add('active');
                
                // 在弹窗中显示多模态内容
                if (window.appController && typeof window.appController.displayQAContent === 'function') {
                    window.appController.displayQAContent(qaData, qaContentDiv);
                } else {
                    // 降级显示
                    qaContentDiv.textContent = answerText;
                }
                if (window.appController && typeof window.appController.setModalVoiceControlsVisible === 'function') {
                    window.appController.setModalVoiceControlsVisible('qa', false);
                }
            }
            
            // 在主对话框中也显示文本（与弹窗中的文本一致）
            if (this.chatUI && !options.skipChatUI && answerText) {
                // 直接使用文本，保留换行符，让CSS的white-space: pre-wrap处理
                const messageEl = this.chatUI.addMessage({
                    role: 'assistant',
                    content: answerText,
                    agents: agents.length ? agents : ['mentor'],
                    intent: 'qa',
                    conversation_id: response.conversation_id
                });
                // 为QA消息添加样式，保留换行和自然分段
                if (messageEl) {
                    const textEl = messageEl.querySelector('.message-text-preview, .message-text-full, .message-text');
                    if (textEl) {
                        textEl.style.whiteSpace = 'pre-wrap';
                    }
                }
            }
            // 已显示，直接返回，避免重复显示
            return;
        }

        // 处理学习内容响应（智教Mentor）
        // 排除QA类型，因为QA已经在上面处理过了
        const isQA = intent === 'qa' || response.content_type === 'qa' || response.lesson_type === 'qa';
        if (!isQA && (handledBy === 'mentor' || response.lesson || response.lesson_type)) {
            this.displayLearningContent(response);
        }

        if (this.chatUI && !options.skipChatUI) {
            const displayContent = this._buildChatDisplayContent(response, content);
            
            this.chatUI.addMessage({
                role: 'assistant',
                content: displayContent,
                agents: agents.length ? agents : undefined,
                intent,
                conversation_id: response.conversation_id
            });
        }
    }

    _buildChatDisplayContent(response, rawContent) {
        const content = rawContent || response.content || response.response || '';
        const lesson = response.lesson || {};

        if (typeof content === 'string' && content.trim()) {
            return content;
        }

        if (lesson && typeof lesson.teaching_content === 'string' && lesson.teaching_content.trim()) {
            return lesson.teaching_content;
        }

        if (Array.isArray(content)) {
            const parts = content
                .map(item => (item && (item.text || item.answer_content || item.answer || item.content)) || '')
                .filter(Boolean);
            if (parts.length) {
                return parts.join('\n');
            }
        }

        if (typeof content === 'object' && content !== null) {
            if (typeof content.text === 'string' && content.text.trim()) {
                return content.text;
            }
            if (typeof content.answer_content === 'string' && content.answer_content.trim()) {
                return content.answer_content;
            }
            if (typeof content.answer === 'string' && content.answer.trim()) {
                return content.answer;
            }
            if (typeof content.title === 'string') {
                const bodyText = typeof content.text === 'string' ? content.text : '';
                const merged = `${content.title}\n\n${bodyText}`.trim();
                if (merged) {
                    return merged;
                }
            }
        }

        if (Array.isArray(response.response)) {
            const parts = response.response
                .map(item => (item && (item.text || item.answer_content || item.answer || item.content)) || '')
                .filter(Boolean);
            if (parts.length) {
                return parts.join('\n');
            }
        }

        if (typeof response.response === 'string' && response.response.trim()) {
            return response.response;
        }

        return '（没有返回内容）';
    }

    // 显示故事多模态内容
    displayStoryContent(storyData, container) {
        const title = storyData.title || '故事';
        const paragraphs = storyData.paragraphs || [];
        
        // 收集所有有效的音频URL
        const audioUrls = paragraphs
            .map(para => para.audio)
            .filter(audio => audio && !audio.startsWith('[模拟') && (audio.startsWith('data:audio') || audio.startsWith('http')));
        
        let html = `<div class="story-header" style="text-align: center; margin-bottom: 0.5rem;"><h2 style="margin: 0; font-size: 1.5rem;">${title}</h2></div>`;
        
        // 如果有音频，添加统一的播放控制
        if (audioUrls.length > 0) {
            html += `<div class="story-audio-controls" style="display: flex; justify-content: center; align-items: center; gap: 10px; margin-bottom: 0.75rem; flex-wrap: wrap;">
                <button id="playAllAudio" class="play-all-btn" style="padding: 7px 20px; font-size: 12px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 20px; cursor: pointer; box-shadow: 0 2px 4px rgba(102, 126, 234, 0.2); transition: all 0.2s ease; display: inline-flex; align-items: center; justify-content: center; gap: 6px; font-weight: 500; letter-spacing: 0.2px; white-space: nowrap;">
                    <i class="fas fa-play" style="font-size: 10px;"></i> 播放故事
                </button>
                <button id="stopAllAudio" class="stop-all-btn" style="padding: 7px 20px; font-size: 12px; background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: white; border: none; border-radius: 20px; cursor: pointer; box-shadow: 0 2px 4px rgba(99, 102, 241, 0.2); transition: all 0.2s ease; display: none; align-items: center; justify-content: center; gap: 6px; font-weight: 500; letter-spacing: 0.2px; white-space: nowrap;">
                    <i class="fas fa-stop" style="font-size: 10px;"></i> 停止
                </button>
            </div>
            <div id="audioProgress" style="text-align: center; font-size: 11px; color: #6b7280; min-height: 14px; margin-bottom: 0.5rem;"></div>`;
        }
        
        paragraphs.forEach((para, index) => {
            html += `<div class="story-paragraph" data-index="${para.index || index + 1}">`;
            
            // 段落文本
            if (para.text) {
                html += `<div class="paragraph-text">${para.text.replace(/\n/g, '<br>')}</div>`;
            }
            
            // 段落图片
            if (para.image && !para.image.startsWith('[模拟')) {
                html += `<div class="paragraph-image">`;
                if (para.image.startsWith('data:image') || para.image.startsWith('http')) {
                    html += `<img src="${para.image}" alt="段落 ${para.index || index + 1} 配图" />`;
                }
                html += `</div>`;
            }
            
            // 段落音频（隐藏，用于连续播放）
            if (para.audio && !para.audio.startsWith('[模拟')) {
                html += `<div class="paragraph-audio" style="display: none;">`;
                if (para.audio.startsWith('data:audio') || para.audio.startsWith('http')) {
                    html += `<audio data-audio-index="${index}" preload="auto"><source src="${para.audio}" type="audio/mpeg">您的浏览器不支持音频播放</audio>`;
                }
                html += `</div>`;
            }
            
            html += `</div>`;
        });
        
        container.innerHTML = html;
        
        // 设置自动连续播放逻辑
        if (audioUrls.length > 0) {
            this.setupAutoPlay(container);
        }
    }

    // 在聊天界面显示问答内容
    displayQAContentInChat(qaData, question) {
        const answerText = qaData.answer_content || qaData.answer || '';
        
        if (!this.chatUI) return;
        
        // 只显示答案文本
        this.chatUI.addMessage({
            role: 'assistant',
            content: answerText,
            agents: ['mentor'],
            intent: 'qa'
        });
    }
    
    setupAutoPlay(container) {
        const playBtn = container.querySelector('#playAllAudio');
        const stopBtn = container.querySelector('#stopAllAudio');
        const progressDiv = container.querySelector('#audioProgress');
        const audioElements = Array.from(container.querySelectorAll('audio[data-audio-index]'))
            .sort((a, b) => {
                const indexA = parseInt(a.getAttribute('data-audio-index')) || 0;
                const indexB = parseInt(b.getAttribute('data-audio-index')) || 0;
                return indexA - indexB;
            });
        
        let currentAudioIndex = -1;
        let isPlaying = false;
        
        const updateProgress = () => {
            if (progressDiv && currentAudioIndex >= 0 && currentAudioIndex < audioElements.length) {
                const current = currentAudioIndex + 1;
                const total = audioElements.length;
                progressDiv.textContent = `正在播放：段落 ${current} / ${total}`;
            } else if (progressDiv) {
                progressDiv.textContent = '';
            }
        };
        
        const playNext = () => {
            if (!isPlaying) return;
            
            currentAudioIndex++;
            
            if (currentAudioIndex >= audioElements.length) {
                // 所有音频播放完成
                isPlaying = false;
                currentAudioIndex = -1;
                playBtn.style.display = 'inline-flex';
                stopBtn.style.display = 'none';
                if (progressDiv) {
                    progressDiv.textContent = '播放完成';
                    setTimeout(() => {
                        progressDiv.textContent = '';
                    }, 2000);
                }
                return;
            }
            
            const audio = audioElements[currentAudioIndex];
            updateProgress();
            
            // 高亮当前播放的段落
            const paragraph = audio.closest('.story-paragraph');
            if (paragraph) {
                // 移除之前的高亮
                container.querySelectorAll('.story-paragraph').forEach(p => {
                    p.style.backgroundColor = '';
                    p.style.transition = '';
                });
                // 高亮当前段落
                paragraph.style.backgroundColor = '#f0f8ff';
                paragraph.style.transition = 'background-color 0.3s';
                
                // 滚动到当前段落
                paragraph.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
            
            // 播放当前音频
            audio.play().catch(err => {
                console.error('播放音频失败:', err);
                // 如果播放失败，继续播放下一个
                playNext();
            });
        };
        
        const stopAll = () => {
            isPlaying = false;
            audioElements.forEach(audio => {
                audio.pause();
                audio.currentTime = 0;
            });
            currentAudioIndex = -1;
            playBtn.style.display = 'inline-flex';
            stopBtn.style.display = 'none';
            if (progressDiv) {
                progressDiv.textContent = '';
            }
            
            // 移除高亮
            container.querySelectorAll('.story-paragraph').forEach(p => {
                p.style.backgroundColor = '';
            });
        };
        
        // 为每个音频添加播放完成事件监听
        audioElements.forEach((audio, index) => {
            audio.addEventListener('ended', () => {
                if (isPlaying && index === currentAudioIndex) {
                    // 移除当前段落高亮
                    const paragraph = audio.closest('.story-paragraph');
                    if (paragraph) {
                        paragraph.style.backgroundColor = '';
                    }
                    // 播放下一个
                    setTimeout(() => {
                        playNext();
                    }, 300); // 短暂延迟，让过渡更自然
                }
            });
            
            audio.addEventListener('error', () => {
                console.error(`段落 ${index + 1} 音频加载失败，跳过`);
                if (isPlaying && index === currentAudioIndex) {
                    setTimeout(() => {
                        playNext();
                    }, 300);
                }
            });
        });
        
        // 添加按钮hover效果
        playBtn.addEventListener('mouseenter', () => {
            playBtn.style.transform = 'translateY(-1px)';
            playBtn.style.boxShadow = '0 4px 10px rgba(102, 126, 234, 0.35)';
            playBtn.style.background = 'linear-gradient(135deg, #7c8ef5 0%, #8a5dd1 100%)';
        });
        playBtn.addEventListener('mouseleave', () => {
            playBtn.style.transform = 'translateY(0)';
            playBtn.style.boxShadow = '0 2px 6px rgba(102, 126, 234, 0.25)';
            playBtn.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
        });
        
        stopBtn.addEventListener('mouseenter', () => {
            stopBtn.style.transform = 'translateY(-1px)';
            stopBtn.style.boxShadow = '0 4px 10px rgba(99, 102, 241, 0.35)';
            stopBtn.style.background = 'linear-gradient(135deg, #7578f3 0%, #9a6df8 100%)';
        });
        stopBtn.addEventListener('mouseleave', () => {
            stopBtn.style.transform = 'translateY(0)';
            stopBtn.style.boxShadow = '0 2px 6px rgba(99, 102, 241, 0.25)';
            stopBtn.style.background = 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)';
        });
        
        // 播放按钮事件
        playBtn.addEventListener('click', () => {
            isPlaying = true;
            currentAudioIndex = -1;
            playBtn.style.display = 'none';
            stopBtn.style.display = 'inline-flex';
            playNext();
        });
        
        // 停止按钮事件
        stopBtn.addEventListener('click', () => {
            stopAll();
        });
    }

    // 显示学习内容与配图
    displayLearningContent(response) {
        const modal = document.getElementById('learningModal');
        const contentEl = document.getElementById('learningContent');
        const titleEl = document.getElementById('learningTitle');
        if (!modal || !contentEl) {
            return;
        }

        const lesson = response.lesson || {};
        const lessonType = response.lesson_type || lesson.lesson_type || '';
        let title = '学习内容';
        if (lessonType === 'chinese') {
            const character = lesson.character || '';
            title = character ? `汉字学习：${character}` : '汉字学习';
        }
        if (titleEl) {
            titleEl.textContent = title;
        }

        contentEl.innerHTML = '';
        const mediaItems = Array.isArray(response.response) ? response.response : [];
        const audioItems = mediaItems.filter(
            item => item && typeof item.audio === 'string' && item.audio.trim() && !item.audio.startsWith('[模拟')
        );
        if (audioItems.length) {
            // 使用与睡前故事和十万个为什么一致的样式
            const controls = document.createElement('div');
            controls.className = 'story-audio-controls';
            controls.style.cssText = 'display: flex; justify-content: center; align-items: center; gap: 10px; margin-top: 1rem; margin-bottom: 0.75rem; flex-wrap: wrap;';
            
            const playBtn = document.createElement('button');
            playBtn.id = 'learningPlayAudio';
            playBtn.className = 'play-all-btn';
            playBtn.type = 'button';
            playBtn.style.cssText = 'padding: 7px 20px; font-size: 12px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 20px; cursor: pointer; box-shadow: 0 2px 4px rgba(102, 126, 234, 0.2); transition: all 0.2s ease; display: inline-flex; align-items: center; justify-content: center; gap: 6px; font-weight: 500; letter-spacing: 0.2px; white-space: nowrap;';
            playBtn.innerHTML = '<i class="fas fa-play" style="font-size: 10px;"></i> 播放语音';
            
            const stopBtn = document.createElement('button');
            stopBtn.id = 'learningStopAudio';
            stopBtn.className = 'stop-all-btn';
            stopBtn.type = 'button';
            stopBtn.style.cssText = 'padding: 7px 20px; font-size: 12px; background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: white; border: none; border-radius: 20px; cursor: pointer; box-shadow: 0 2px 4px rgba(99, 102, 241, 0.2); transition: all 0.2s ease; display: none; align-items: center; justify-content: center; gap: 6px; font-weight: 500; letter-spacing: 0.2px; white-space: nowrap;';
            stopBtn.innerHTML = '<i class="fas fa-stop" style="font-size: 10px;"></i> 停止';
            
            const progress = document.createElement('div');
            progress.id = 'learningAudioProgress';
            progress.style.cssText = 'text-align: center; font-size: 11px; color: #6b7280; min-height: 14px; margin-bottom: 0.5rem;';
            
            controls.appendChild(playBtn);
            controls.appendChild(stopBtn);
            contentEl.appendChild(controls);
            contentEl.appendChild(progress);

            const audioContainer = document.createElement('div');
            audioContainer.className = 'learning-audio-container';
            audioItems.forEach((item, index) => {
                const audio = document.createElement('audio');
                audio.dataset.audioIndex = String(index);
                audio.preload = 'auto';
                const source = document.createElement('source');
                source.src = item.audio;
                source.type = 'audio/mpeg';
                audio.appendChild(source);
                audioContainer.appendChild(audio);
            });
            contentEl.appendChild(audioContainer);
            this.setupLearningAudioPlayback(controls, audioContainer);
        }
        mediaItems.forEach((item, index) => {
            if (!item) return;
            const wrapper = document.createElement('div');
            wrapper.className = 'learning-media';

            if (item.text && typeof item.text === 'string' && item.text.trim() && !item.text.startsWith('[模拟')) {
                const textEl = document.createElement('div');
                textEl.className = 'learning-media-text';
                textEl.textContent = item.text.trim();
                wrapper.appendChild(textEl);
            }

            if (item.image && typeof item.image === 'string' && item.image.trim() && !item.image.startsWith('[模拟')) {
                const img = document.createElement('img');
                img.src = item.image;
                img.alt = `学习配图 ${index + 1}`;
                img.loading = 'lazy';
                wrapper.appendChild(img);
            }

            if (wrapper.childNodes.length) {
                contentEl.appendChild(wrapper);
            }
        });

        modal.classList.add('active');
    }

    setupLearningAudioPlayback(controls, audioContainer) {
        const playBtn = controls.querySelector('#learningPlayAudio') || controls.querySelector('.play-all-btn');
        const stopBtn = controls.querySelector('#learningStopAudio') || controls.querySelector('.stop-all-btn');
        const progress = document.getElementById('learningAudioProgress') || controls.querySelector('.learning-audio-progress');
        const audioElements = Array.from(audioContainer.querySelectorAll('audio[data-audio-index]'))
            .sort((a, b) => {
                const indexA = parseInt(a.dataset.audioIndex, 10) || 0;
                const indexB = parseInt(b.dataset.audioIndex, 10) || 0;
                return indexA - indexB;
            });

        let currentIndex = -1;
        let isPlaying = false;

        const updateProgress = () => {
            if (!progress) return;
            if (currentIndex >= 0 && currentIndex < audioElements.length) {
                progress.textContent = `正在播放：${currentIndex + 1} / ${audioElements.length}`;
            } else {
                progress.textContent = '';
            }
        };

        const playNext = () => {
            if (!isPlaying) return;
            currentIndex += 1;
            if (currentIndex >= audioElements.length) {
                isPlaying = false;
                currentIndex = -1;
                if (playBtn) playBtn.style.display = 'inline-flex';
                if (stopBtn) stopBtn.style.display = 'none';
                if (progress) {
                    progress.textContent = '播放完成';
                    setTimeout(() => {
                        progress.textContent = '';
                    }, 2000);
                }
                return;
            }
            updateProgress();
            const audio = audioElements[currentIndex];
            audio.play().catch(err => {
                console.error('播放学习音频失败:', err);
                playNext();
            });
        };

        const stopAll = () => {
            isPlaying = false;
            audioElements.forEach(audio => {
                audio.pause();
                audio.currentTime = 0;
            });
            currentIndex = -1;
            playBtn.style.display = 'inline-flex';
            if (stopBtn) stopBtn.style.display = 'none';
            if (progress) {
                progress.textContent = '';
            }
        };
        
        // 添加按钮hover效果（与睡前故事一致）
        if (playBtn) {
            playBtn.addEventListener('mouseenter', () => {
                playBtn.style.transform = 'translateY(-1px)';
                playBtn.style.boxShadow = '0 4px 10px rgba(102, 126, 234, 0.35)';
                playBtn.style.background = 'linear-gradient(135deg, #7c8ef5 0%, #8a5dd1 100%)';
            });
            playBtn.addEventListener('mouseleave', () => {
                playBtn.style.transform = 'translateY(0)';
                playBtn.style.boxShadow = '0 2px 6px rgba(102, 126, 234, 0.25)';
                playBtn.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
            });
        }
        
        if (stopBtn) {
            stopBtn.addEventListener('mouseenter', () => {
                stopBtn.style.transform = 'translateY(-1px)';
                stopBtn.style.boxShadow = '0 4px 10px rgba(99, 102, 241, 0.35)';
                stopBtn.style.background = 'linear-gradient(135deg, #7578f3 0%, #9a6df8 100%)';
            });
            stopBtn.addEventListener('mouseleave', () => {
                stopBtn.style.transform = 'translateY(0)';
                stopBtn.style.boxShadow = '0 2px 6px rgba(99, 102, 241, 0.25)';
                stopBtn.style.background = 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)';
            });
        }

        audioElements.forEach((audio, index) => {
            audio.addEventListener('ended', () => {
                if (isPlaying && index === currentIndex) {
                    setTimeout(() => playNext(), 200);
                }
            });
            audio.addEventListener('error', () => {
                if (isPlaying && index === currentIndex) {
                    setTimeout(() => playNext(), 200);
                }
            });
        });

        playBtn.addEventListener('click', () => {
            isPlaying = true;
            currentIndex = -1;
            playBtn.style.display = 'none';
            if (stopBtn) stopBtn.style.display = 'inline-flex';
            playNext();
        });

        if (stopBtn) {
            stopBtn.addEventListener('click', () => {
                stopAll();
            });
        }
    }

    // 生成故事
    async generateStory(theme, options = {}) {
        if (this.useBackend && window.apiClient) {
            try {
                const inputType = options.inputType || 'text';
                console.log('[generateStory] 调用后端API生成故事，主题:', theme);
                const result = await window.apiClient.generateStory(theme, this.userId, this.context, inputType);
                console.log('[generateStory] 后端返回结果:', result);
                
                // 解析返回结果 - 后端返回格式: { success: true, data: { content: {...}, content_type: 'story', ... } }
                const data = result.data || result;
                
                // 检查是否是故事类型
                if (data.content_type === 'story' && data.content && typeof data.content === 'object') {
                    const storyContent = data.content;
                    const storyTitle = storyContent.title || `《${theme}的冒险》`;
                    
                    console.log('[generateStory] 解析故事内容:', {
                        title: storyTitle,
                        hasText: !!storyContent.text,
                        paragraphsCount: storyContent.paragraphs?.length || 0
                    });
                    
                    const storyResponse = {
                        intent: 'story',
                        content_type: 'story',
                        content: storyContent,
                        handled_by: data.handled_by || 'artist',
                        agents: data.agents && data.agents.length ? data.agents : ['artist'],
                        metadata: data.metadata || {},
                    };
                    this.displayResponse(theme, storyResponse, 'storyteller');
                    
                    return {
                        title: storyTitle,
                        content: storyContent,  // 返回完整的故事对象，包含 paragraphs
                        type: 'storyteller'
                    };
                } else {
                    // 如果不是预期的故事格式，记录警告并抛出错误
                    console.error('[generateStory] 返回数据格式不符合预期:', data);
                    console.error('[generateStory] content_type:', data.content_type);
                    console.error('[generateStory] content:', data.content);
                    throw new Error(`后端返回的数据格式不符合预期: content_type=${data.content_type}, content类型=${typeof data.content}`);
                }
            } catch (error) {
                console.error('[generateStory] 后端故事生成失败:', error);
                console.error('[generateStory] 错误详情:', error.message);
                // 不回退到本地Agent，直接抛出错误让调用者处理
                throw error;
            }
        }
        
        // 如果没有启用后端，使用本地Agent
        console.log('[generateStory] 使用本地Agent生成故事（后端未启用）');
        const storyText = await this.agents.storyteller.generateStory(theme);
        const storyContent = typeof storyText === 'string'
            ? { title: `《${theme}的冒险》`, text: storyText }
            : storyText;
        const storyResponse = {
            intent: 'story',
            content_type: 'story',
            content: storyContent,
            handled_by: 'artist',
            agents: ['artist'],
        };
        this.displayResponse(theme, storyResponse, 'storyteller');
        return {
            title: storyContent?.title || `《${theme}的冒险》`,
            content: storyContent,
            type: 'storyteller',
        };
    }

    // 生成成语故事（每日成语）
    async generateIdiomStory(idiom, options = {}) {
        if (this.useBackend && window.apiClient) {
            try {
                const inputType = options.inputType || 'text';
                console.log('[generateIdiomStory] 调用后端API生成成语故事，成语:', idiom);
                const result = await window.apiClient.generateIdiomStory(idiom, this.userId, this.context, inputType);
                console.log('[generateIdiomStory] 后端返回结果:', result);

                const data = result.data || result;
                if (data.content_type === 'story' && data.content && typeof data.content === 'object') {
                    const storyContent = data.content;
                    const storyTitle = storyContent.title || `${idiom}的成语故事`;

                    console.log('[generateIdiomStory] 解析成语故事内容:', {
                        title: storyTitle,
                        hasText: !!storyContent.text,
                        paragraphsCount: storyContent.paragraphs?.length || 0
                    });

                    const storyResponse = {
                        intent: 'story',
                        content_type: 'story',
                        content: storyContent,
                        handled_by: data.handled_by || 'artist',
                        agents: data.agents && data.agents.length ? data.agents : ['artist'],
                        metadata: data.metadata || {},
                    };
                    this.displayResponse(idiom, storyResponse, 'storyteller');

                    return {
                        title: storyTitle,
                        content: storyContent,
                        type: 'storyteller'
                    };
                } else {
                    console.error('[generateIdiomStory] 返回数据格式不符合预期:', data);
                    console.error('[generateIdiomStory] content_type:', data.content_type);
                    console.error('[generateIdiomStory] content:', data.content);
                    throw new Error(`后端返回的数据格式不符合预期: content_type=${data.content_type}, content类型=${typeof data.content}`);
                }
            } catch (error) {
                console.error('[generateIdiomStory] 后端成语故事生成失败:', error);
                console.error('[generateIdiomStory] 错误详情:', error.message);
                throw error;
            }
        }

        console.log('[generateIdiomStory] 使用本地Agent生成成语故事（后端未启用）');
        const storyText = await this.agents.storyteller.generateStory(`成语故事：${idiom}`);
        const storyContent = typeof storyText === 'string'
            ? { title: `${idiom}的成语故事`, text: storyText }
            : storyText;
        const storyResponse = {
            intent: 'story',
            content_type: 'story',
            content: storyContent,
            handled_by: 'artist',
            agents: ['artist'],
        };
        this.displayResponse(idiom, storyResponse, 'storyteller');
        return {
            title: storyContent?.title || `${idiom}的成语故事`,
            content: storyContent,
            type: 'storyteller',
        };
    }

    _showSystemNotice(message) {
        if (this.chatUI) {
            this.chatUI.addMessage({
                role: 'assistant',
                content: message
            });
        }
    }

}

// 陪伴Agent - 回答"十万个为什么"
class CompanionAgent {
    constructor() {
        this.type = 'companion';
        this.knowledgeBase = {
            '为什么': [
                '这是一个很好的问题！让我想想...',
                '这个问题很有趣呢！',
                '你观察得很仔细！'
            ],
            '天空': '天空是蓝色的，是因为太阳光中的蓝色光被大气层散射了。',
            '星星': '星星是遥远的太阳，它们离我们非常非常远，所以看起来很小。',
            '月亮': '月亮是地球的卫星，它围绕地球转，所以每天晚上我们都能看到它。',
            '太阳': '太阳是一颗恒星，它给我们光和热，让地球上的生命能够存在。',
            '水': '水是由氢和氧组成的，它在不同温度下会变成冰、水或水蒸气。',
            '动物': '动物是地球上的好朋友，它们和我们一样需要食物、水和家。'
        };
    }

    async process(input) {
        // 模拟AI思考时间
        await this.delay(1000 + Math.random() * 1000);
        
        // 简单的关键词匹配（实际应用中应该使用真正的AI）
        let answer = this.findAnswer(input);
        
        if (!answer) {
            answer = this.generateDefaultAnswer(input);
        }
        
        return {
            content: answer,
            type: this.type
        };
    }

    findAnswer(input) {
        const lowerInput = input.toLowerCase();
        
        for (const [key, value] of Object.entries(this.knowledgeBase)) {
            if (lowerInput.includes(key)) {
                if (Array.isArray(value)) {
                    return value[Math.floor(Math.random() * value.length)] + ' ' + this.generateDefaultAnswer(input);
                }
                return value;
            }
        }
        
        return null;
    }

    generateDefaultAnswer(input) {
        const answers = [
            `关于"${input}"，这是一个很有趣的话题！让我用简单的方式解释给你听：这是一个很神奇的现象，科学家们一直在研究它。你可以继续问我更多问题哦！`,
            `你问得很好！"${input}"确实值得我们去了解。简单来说，这是大自然的一个奇妙之处。`,
            `这个问题很棒！"${input}"涉及到很多有趣的知识。让我想想怎么用最简单的方式告诉你...`
        ];
        
        return answers[Math.floor(Math.random() * answers.length)];
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// 教师Agent - 学习启蒙
class TeacherAgent {
    constructor() {
        this.type = 'teacher';
    }

    async process(input) {
        await this.delay(1500);
        
        // 根据输入生成学习内容
        let content = this.generateLearningContent(input);
        
        return {
            content: content,
            type: this.type
        };
    }

    generateLearningContent(input) {
        if (input.includes('汉字') || input.includes('字')) {
            return this.generateChineseContent();
        } else if (input.includes('数字') || input.includes('数学')) {
            return this.generateMathContent();
        } else {
            return `关于"${input}"的学习内容：\n\n让我为你准备一些有趣的学习材料。学习是一个探索的过程，我们一起慢慢来！`;
        }
    }

    generateChineseContent() {
        return `汉字学习时间！\n\n今天我们来认识"水"字：\n\n💧 水字像流动的水滴\n💧 它由三笔组成\n💧 和水相关的词：河水、海水、雨水\n\n你能想到更多和水相关的词吗？`;
    }

    generateMathContent() {
        return `数学启蒙！\n\n让我们来数数：\n\n1️⃣ 一个苹果\n2️⃣ 两个苹果\n3️⃣ 三个苹果\n\n1 + 1 = 2\n2 + 1 = 3\n\n数学是不是很有趣？`;
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// 故事Agent - 生成睡前故事
class StorytellerAgent {
    constructor() {
        this.type = 'storyteller';
    }

    async process(input) {
        await this.delay(2000);
        
        const theme = this.extractTheme(input);
        const story = await this.generateStory(theme);
        
        return {
            title: `《${theme}的冒险》`,
            content: story,
            type: this.type
        };
    }

    async generateStory(theme) {
        // 模拟故事生成
        await this.delay(1000);
        
        const stories = {
            '小兔子': `从前，有一只可爱的小兔子，它住在一个美丽的森林里。\n\n有一天，小兔子决定去探险。它跳啊跳，来到了一个神奇的花园。花园里开满了五颜六色的花朵，还有一只友好的蝴蝶在飞舞。\n\n小兔子和蝴蝶成了好朋友，它们一起在花园里玩耍，度过了愉快的一天。\n\n晚上，小兔子回到了家，把今天的冒险告诉了妈妈。妈妈温柔地摸了摸小兔子的头，说："你真勇敢！"\n\n小兔子带着甜甜的笑容进入了梦乡...`,
            '太空': `在遥远的太空中，有一个勇敢的小宇航员。\n\n他驾驶着宇宙飞船，飞向了未知的星球。在旅途中，他遇到了友好的外星人朋友，它们有着闪闪发光的眼睛。\n\n小宇航员和外星人一起探索了美丽的星空，看到了很多神奇的景象。他们看到了会发光的星星，还有像彩虹一样的星云。\n\n最后，小宇航员安全地回到了地球，带着满满的回忆和新的朋友。`,
            '默认': `在一个充满魔法的地方，住着一个好奇的小朋友。\n\n这个小朋友总是对世界充满好奇，喜欢问"为什么"。有一天，他遇到了一位智慧的魔法师。\n\n魔法师告诉他："每一个问题都是探索的开始，每一个答案都是知识的种子。"\n\n小朋友听了很开心，他明白了学习是一件快乐的事情。从那以后，他更加热爱探索，也更加热爱学习了。`
        };
        
        return stories[theme] || stories['默认'];
    }

    extractTheme(input) {
        const themes = ['小兔子', '太空', '海洋', '森林', '城堡'];
        for (const theme of themes) {
            if (input.includes(theme)) {
                return theme;
            }
        }
        return '小冒险';
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// 初始化Agent系统
document.addEventListener('DOMContentLoaded', () => {
    if (window.agentSystem) {
        return;
    }
    try {
        window.agentSystem = new AgentSystem();
        console.log('AgentSystem initialized successfully');
    } catch (error) {
        console.error('Failed to initialize AgentSystem:', error);
    }
});