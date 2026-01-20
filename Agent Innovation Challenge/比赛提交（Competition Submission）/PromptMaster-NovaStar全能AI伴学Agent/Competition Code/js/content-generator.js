// 内容生成器 - 流式生成卡片
class ContentGenerator {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.cardIdCounter = 0;
    }

    // 创建内容卡片
    createCard(type, title, content, options = {}) {
        if (!this.container) {
            return null;
        }
        const card = document.createElement('div');
        card.className = `content-card card-${type}`;
        card.id = `card-${this.cardIdCounter++}`;
        
        const iconMap = {
            'question': { icon: 'fa-question-circle', class: 'question' },
            'answer': { icon: 'fa-lightbulb', class: 'answer' },
            'story': { icon: 'fa-book-open', class: 'story' },
            'game': { icon: 'fa-gamepad', class: 'game' },
            'learning': { icon: 'fa-graduation-cap', class: 'learning' }
        };
        
        const iconInfo = iconMap[type] || iconMap['answer'];
        
        card.innerHTML = `
            <div class="card-header">
                <div class="card-icon ${iconInfo.class}">
                    <i class="fas ${iconInfo.icon}"></i>
                </div>
                <div class="card-title">${title}</div>
            </div>
            <div class="card-content" id="content-${card.id}">
                ${content}
            </div>
        `;
        
        // 添加到容器
        this.container.appendChild(card);
        
        // 滚动到底部
        this.scrollToBottom();
        
        // 流式显示文本
        if (options.streaming) {
            this.streamText(card.querySelector('.card-content'), content);
        }
        
        return card;
    }

    // 流式文本显示
    streamText(element, text) {
        element.innerHTML = '';
        let index = 0;
        
        const stream = () => {
            if (index < text.length) {
                const char = text[index];
                const span = document.createElement('span');
                span.className = 'streaming-char';
                span.textContent = char;
                element.appendChild(span);
                index++;
                
                // 控制速度
                const delay = char === '\n' ? 50 : 30;
                setTimeout(stream, delay);
            }
        };
        
        stream();
    }

    // 显示打字机效果
    showTypingIndicator() {
        if (!this.container) {
            return null;
        }
        const card = document.createElement('div');
        card.className = 'content-card';
        card.innerHTML = `
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
        this.container.appendChild(card);
        this.scrollToBottom();
        return card;
    }

    // 移除打字机效果
    removeTypingIndicator(card) {
        if (card && card.parentNode) {
            card.parentNode.removeChild(card);
        }
    }

    // 生成问答卡片
    createQACard(question, answer) {
        const questionCard = this.createCard('question', '你的问题', question);
        
        setTimeout(() => {
            const answerCard = this.createCard('answer', 'Nova的回答', answer, { streaming: true });
        }, 500);
    }

    // 生成故事卡片
    createStoryCard(title, story) {
        return this.createCard('story', title, story, { streaming: true });
    }

    // 生成学习卡片
    createLearningCard(title, content) {
        return this.createCard('learning', title, content, { streaming: true });
    }

    // 生成游戏卡片
    createGameCard(title, gameHtml) {
        const card = this.createCard('game', title, '');
        const contentDiv = card.querySelector('.card-content');
        contentDiv.innerHTML = gameHtml;
        return card;
    }

    // 滚动到底部
    scrollToBottom() {
        setTimeout(() => {
            if (this.container) {
                this.container.scrollTop = this.container.scrollHeight;
            }
        }, 100);
    }

    // 清空内容
    clear() {
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}

// 初始化内容生成器
document.addEventListener('DOMContentLoaded', () => {
    window.contentGenerator = new ContentGenerator('contentStream');
});