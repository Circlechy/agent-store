// 聊天UI渲染器
class ChatUI {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.messageId = 0;
        this._typingStates = new WeakMap();
        this._lastMessageSignature = null;
        this._lastMessageAt = 0;
        this.collapseLimit = 20;
        this.agentLabels = {
            mentor: '智教Agent',
            artist: '创意Agent',
            companion: '陪伴Agent',
            commander: '主控Agent',
            storyteller: '故事Agent'
        };
    }

    renderHistory(messages = []) {
        this.clear();
        messages.forEach(message => this.addMessage(message));
    }

    addMessage(message) {
        if (!this.container || !message) {
            return null;
        }
        if (message.content == null && !message.allowEmpty) {
            return null;
        }
        const role = message.role || 'assistant';
        const contentText = message.content || '';
        const conversationId = message.conversation_id || '';
        if (conversationId && this.container) {
            const existing = this.container.querySelector(
                `.companion-message[data-conversation-id="${conversationId}"][data-role="${role}"]`
            );
            if (existing) {
                return existing;
            }
        }
        const signature = `${role}::${contentText}`;
        const now = Date.now();
        if (contentText && this._lastMessageSignature === signature && now - this._lastMessageAt < 800) {
            return null;
        }
        this._lastMessageSignature = signature;
        this._lastMessageAt = now;
        const isUser = role === 'user';
        const messageEl = document.createElement('div');
        messageEl.className = `companion-message ${isUser ? 'user-message' : 'nova-message'}`;
        messageEl.dataset.messageId = String(this.messageId++);
        messageEl.dataset.role = role;
        if (conversationId) {
            messageEl.dataset.conversationId = conversationId;
        }

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        const avatarIcon = document.createElement('i');
        avatarIcon.className = `fas ${this._getAvatarIcon(role, message.source)}`;
        avatar.appendChild(avatarIcon);

        const content = document.createElement('div');
        content.className = 'message-content';

        const text = document.createElement('div');
        text.className = 'message-text';
        if (isUser) {
            text.textContent = contentText;
        } else {
            const previewSpan = document.createElement('span');
            previewSpan.className = 'message-text-preview';
            const fullSpan = document.createElement('span');
            fullSpan.className = 'message-text-full';
            text.appendChild(previewSpan);
            text.appendChild(fullSpan);
        }
        content.appendChild(text);

        if (!isUser) {
            const actions = this._buildCollapseActions();
            content.appendChild(actions);
        }

        const agents = this._normalizeAgents(message);
        if (agents.length) {
            messageEl.dataset.agents = agents.join(',');
        }

        const meta = this._buildMeta(message);
        if (meta) {
            content.appendChild(meta);
        }

        messageEl.appendChild(avatar);
        messageEl.appendChild(content);
        this.container.appendChild(messageEl);
        if (!isUser) {
            this._setAssistantText(messageEl, contentText);
        }
        this.scrollToBottom();
        return messageEl;
    }

    updateMessageText(messageEl, text) {
        if (!messageEl) return;
        if (messageEl.dataset.role === 'user') {
            const textEl = messageEl.querySelector('.message-text');
            if (!textEl) return;
            textEl.textContent = text || '';
        } else {
            this._setAssistantText(messageEl, text || '');
        }
        this.scrollToBottom();
    }

    enqueueTyping(messageEl, text, speed = 20) {
        if (!messageEl || !text) return;
        const textEl = messageEl.querySelector('.message-text');
        if (!textEl) return;

        let state = this._typingStates.get(messageEl);
        if (!state) {
            state = { buffer: '', timer: null };
            this._typingStates.set(messageEl, state);
        }

        state.buffer += String(text);
        if (state.timer) return;

        const interval = Math.max(10, Number(speed) || 20);
        state.timer = setInterval(() => {
            if (!state.buffer.length) {
                clearInterval(state.timer);
                state.timer = null;
                return;
            }
            const nextChar = state.buffer[0];
            state.buffer = state.buffer.slice(1);
            if (messageEl.dataset.role === 'user') {
                textEl.textContent += nextChar;
            } else {
                this._setAssistantText(messageEl, nextChar, { append: true });
            }
            this.scrollToBottom();
        }, interval);
    }

    showTypingIndicator() {
        if (!this.container) return null;
        const messageEl = document.createElement('div');
        messageEl.className = 'companion-message nova-message';
        messageEl.dataset.messageId = `typing-${this.messageId++}`;

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        const avatarIcon = document.createElement('i');
        avatarIcon.className = 'fas fa-robot';
        avatar.appendChild(avatarIcon);

        const content = document.createElement('div');
        content.className = 'message-content';

        const text = document.createElement('div');
        text.className = 'message-text';
        text.innerHTML = `
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
        content.appendChild(text);

        messageEl.appendChild(avatar);
        messageEl.appendChild(content);
        this.container.appendChild(messageEl);
        this.scrollToBottom();
        return messageEl;
    }

    removeTypingIndicator(messageEl) {
        if (messageEl && messageEl.parentNode) {
            messageEl.parentNode.removeChild(messageEl);
        }
    }

    removeMessage(messageEl) {
        if (messageEl && messageEl.parentNode) {
            messageEl.parentNode.removeChild(messageEl);
        }
    }

    showVoiceIndicator() {
        if (!this.container) return null;
        const existing = this.container.querySelector('.voice-status-message');
        if (existing) {
            return existing;
        }
        const messageEl = document.createElement('div');
        messageEl.className = 'companion-message user-message voice-status-message';
        messageEl.dataset.messageId = `voice-${this.messageId++}`;

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        const avatarIcon = document.createElement('i');
        avatarIcon.className = 'fas fa-microphone';
        avatar.appendChild(avatarIcon);

        const content = document.createElement('div');
        content.className = 'message-content';

        const text = document.createElement('div');
        text.className = 'message-text voice-status-text';
        text.textContent = '语音识别中…';
        content.appendChild(text);

        messageEl.appendChild(avatar);
        messageEl.appendChild(content);
        this.container.appendChild(messageEl);
        this.scrollToBottom();
        return messageEl;
    }

    removeVoiceIndicator() {
        if (!this.container) return;
        const existing = this.container.querySelector('.voice-status-message');
        if (existing && existing.parentNode) {
            existing.parentNode.removeChild(existing);
        }
    }

    clear() {
        if (this.container) {
            this.container.innerHTML = '';
        }
    }

    scrollToBottom() {
        setTimeout(() => {
            if (this.container) {
                this.container.scrollTop = this.container.scrollHeight;
            }
        }, 60);
    }

    _getAvatarIcon(role, source) {
        if (role === 'user') {
            return source === 'voice' ? 'fa-microphone' : 'fa-user';
        }
        return 'fa-robot';
    }

    _buildMeta(message) {
        const role = message.role || 'assistant';
        const meta = document.createElement('div');
        meta.className = 'message-meta';

        if (role === 'user') {
            const tag = document.createElement('span');
            tag.className = 'meta-tag';
            tag.textContent = message.source === 'voice' ? '语音输入' : '文字输入';
            meta.appendChild(tag);
        } else {
            const agents = this._normalizeAgents(message);
            if (agents.length) {
                const tag = document.createElement('span');
                tag.className = 'meta-tag';
                tag.textContent = '子智能体';
                meta.appendChild(tag);

                const label = document.createElement('span');
                label.textContent = agents.map(agent => this.agentLabels[agent] || agent).join(' / ');
                meta.appendChild(label);
            }
        }

        return meta.childNodes.length ? meta : null;
    }

    _normalizeAgents(message) {
        if (Array.isArray(message.agents) && message.agents.length) {
            return message.agents.filter(Boolean);
        }
        if (message.agent) {
            return [message.agent];
        }
        if (message.handled_by) {
            return [message.handled_by];
        }
        return [];
    }

    _buildCollapseActions() {
        const actions = document.createElement('div');
        actions.className = 'message-text-actions';

        const expandBtn = document.createElement('button');
        expandBtn.type = 'button';
        expandBtn.className = 'message-toggle expand';
        expandBtn.textContent = '展开';

        const collapseBtn = document.createElement('button');
        collapseBtn.type = 'button';
        collapseBtn.className = 'message-toggle collapse';
        collapseBtn.textContent = '折叠';

        expandBtn.addEventListener('click', (event) => {
            event.preventDefault();
            const messageEl = actions.closest('.companion-message');
            if (messageEl) {
                messageEl.dataset.expandState = 'expanded';
                this._setCollapsed(messageEl, false);
            }
        });

        collapseBtn.addEventListener('click', (event) => {
            event.preventDefault();
            const messageEl = actions.closest('.companion-message');
            if (messageEl) {
                messageEl.dataset.expandState = 'collapsed';
                this._setCollapsed(messageEl, true);
            }
        });

        actions.appendChild(expandBtn);
        actions.appendChild(collapseBtn);
        return actions;
    }

    _setAssistantText(messageEl, text, options = {}) {
        if (!messageEl) return;
        const textEl = messageEl.querySelector('.message-text');
        if (!textEl) return;
        const fullEl = textEl.querySelector('.message-text-full');
        const previewEl = textEl.querySelector('.message-text-preview');
        if (!fullEl || !previewEl) {
            textEl.textContent = text || '';
            return;
        }

        const append = options.append === true;
        const currentText = textEl.dataset.fullText || '';
        const nextText = append ? currentText + String(text || '') : String(text || '');
        textEl.dataset.fullText = nextText;

        fullEl.textContent = nextText;
        previewEl.textContent = this._getCollapsedText(nextText);

        const actionsEl = messageEl.querySelector('.message-text-actions');
        const shouldCollapse = nextText.length > this.collapseLimit;
        if (actionsEl) {
            actionsEl.style.display = shouldCollapse ? 'flex' : 'none';
        }

        const explicitState = messageEl.dataset.expandState;
        if (explicitState === 'expanded') {
            this._setCollapsed(messageEl, false);
        } else if (explicitState === 'collapsed') {
            this._setCollapsed(messageEl, true);
        } else {
            const isCompanion = this._isCompanionMessage(messageEl);
            this._setCollapsed(messageEl, shouldCollapse && !isCompanion);
        }
    }

    _isCompanionMessage(messageEl) {
        if (!messageEl) return false;
        const agents = (messageEl.dataset.agents || '')
            .split(',')
            .map(item => item.trim())
            .filter(Boolean);
        return agents.includes('companion');
    }

    _getCollapsedText(text) {
        const rawText = String(text || '');
        if (rawText.length <= this.collapseLimit) {
            return rawText;
        }
        return `${rawText.slice(0, this.collapseLimit)}…`;
    }

    _setCollapsed(messageEl, isCollapsed) {
        if (!messageEl) return;
        if (isCollapsed) {
            messageEl.classList.add('collapsed');
            messageEl.classList.remove('expanded');
        } else {
            messageEl.classList.add('expanded');
            messageEl.classList.remove('collapsed');
        }
    }
}

// 初始化聊天UI
document.addEventListener('DOMContentLoaded', () => {
    window.chatUI = new ChatUI('chatHistory');
    document.addEventListener('voice-input-start', () => {
        if (window.chatUI) {
            window.chatUI.showVoiceIndicator();
        }
    });
    document.addEventListener('voice-input-end', () => {
        if (window.chatUI) {
            window.chatUI.removeVoiceIndicator();
        }
    });
    document.addEventListener('voice-input-error', () => {
        if (window.chatUI) {
            window.chatUI.removeVoiceIndicator();
        }
    });
});
