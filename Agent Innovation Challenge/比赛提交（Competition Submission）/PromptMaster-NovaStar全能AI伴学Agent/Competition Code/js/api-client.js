// API客户端 - 对接后端FastAPI服务
class APIClient {
    constructor(baseURL = null) {
        // 优先从 URL 参数获取端口，其次从 localStorage，最后使用默认值
        if (!baseURL) {
            const urlParams = new URLSearchParams(window.location.search);
            const port = urlParams.get('port') || localStorage.getItem('api_port') || '8000';
            baseURL = `http://localhost:${port}`;
        }
        this.baseURL = baseURL;
        this.apiBase = `${baseURL}/api`;
        console.log(`[APIClient] 初始化，API地址: ${this.apiBase}`);
    }

    /**
     * 发送聊天请求（非流式）
     */
    async chat(query, userId = 'default_user', context = {}, intent = null, inputType = 'text') {
        try {
            console.log(`[APIClient] 发送请求到: ${this.apiBase}/chat`);
            const response = await fetch(`${this.apiBase}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query,
                    user_id: userId,
                    intent: intent || undefined,
                    input_type: inputType,
                    context: context || { age: 6 },
                }),
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error(`[APIClient] HTTP错误 ${response.status}:`, errorText);
                throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
            }

            const data = await response.json();
            console.log('[APIClient] 收到响应:', data);
            // 返回完整的数据结构，包括 content_type 和 metadata
            return data.data || data;
        } catch (error) {
            console.error('[APIClient] API chat error:', error);
            // 如果是网络错误，提供更友好的错误信息
            if (error.message === 'Failed to fetch' || error.name === 'TypeError') {
                const friendlyError = new Error(
                    `无法连接到后端服务器 (${this.baseURL})。\n` +
                    `请确保后端服务器正在运行：\n` +
                    `  python api_server.py\n` +
                    `或检查 API 地址配置是否正确。`
                );
                friendlyError.originalError = error;
                throw friendlyError;
            }
            throw error;
        }
    }

    /**
     * 发送聊天请求（流式）
     */
    async chatStream(query, userId = 'default_user', context = {}, onChunk = null, intent = null, inputType = 'text') {
        try {
            const response = await fetch(`${this.apiBase}/chat/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query,
                    user_id: userId,
                    intent: intent || undefined,
                    input_type: inputType,
                    context: context || { age: 6 },
                }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                
                if (done) {
                    break;
                }

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // 保留最后一个不完整的行

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);
                        
                        if (data === '[DONE]') {
                            return;
                        }

                        try {
                            const parsed = JSON.parse(data);
                            if (onChunk && parsed.chunk) {
                                const enriched = Object.assign({}, parsed.chunk, {
                                    __conversation_id: parsed.conversation_id
                                });
                                onChunk(enriched);
                            }
                        } catch (e) {
                            console.error('Failed to parse SSE data:', e);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('API chat stream error:', error);
            throw error;
        }
    }

    /**
     * 通过主入口生成故事
     */
    async generateStory(theme, userId = 'default_user', context = {}, inputType = 'text') {
        try {
            console.log(`[APIClient] 生成故事，主题: ${theme}`);
            const query = `给我讲一个关于${theme}的故事`;
            const result = await this.chat(query, userId, context, 'story', inputType);
            console.log('[APIClient] 故事生成结果:', result);
            return result;
        } catch (error) {
            console.error('[APIClient] API generate story error:', error);
            // 提供更详细的错误信息
            if (error.message && error.message.includes('无法连接到后端服务器')) {
                throw error;  // 使用友好的错误信息
            }
            throw new Error(`生成故事失败: ${error.message || error}`);
        }
    }

    /**
     * 生成成语故事（每日成语）
     */
    async generateIdiomStory(idiom, userId = 'default_user', context = {}, inputType = 'text') {
        try {
            console.log(`[APIClient] 生成成语故事，成语: ${idiom}`);
            const query = `成语故事：${idiom}`;
            const result = await this.chat(query, userId, context, 'story', inputType);
            console.log('[APIClient] 成语故事生成结果:', result);
            return result;
        } catch (error) {
            console.error('[APIClient] API generate idiom story error:', error);
            if (error.message && error.message.includes('无法连接到后端服务器')) {
                throw error;
            }
            throw new Error(`生成成语故事失败: ${error.message || error}`);
        }
    }

    /**
     * 十万个为什么：回答问题
     */
    async answerQuestion(question, userId = 'default_user', context = {}, inputType = 'text') {
        try {
            console.log(`[APIClient] 提问，问题: ${question}`);
            // 通过 chat 接口，指定 intent 为 'qa'
            const result = await this.chat(question, userId, context, 'qa', inputType);
            console.log('[APIClient] 问答结果:', result);
            
            // 解析结果，提取问答内容
            if (result.content && typeof result.content === 'object') {
                return {
                    question: result.content.question || question,
                    answer_content: result.content.answer_content || result.content.answer || result.response || '',
                    image: result.content.image || '',
                    audio: result.content.audio || '',
                    lesson_type: 'qa',
                };
            } else {
                return {
                    question: question,
                    answer_content: result.content || result.response || '',
                    image: '',
                    audio: '',
                    lesson_type: 'qa',
                };
            }
        } catch (error) {
            console.error('[APIClient] API answer question error:', error);
            if (error.message && error.message.includes('无法连接到后端服务器')) {
                throw error;
            }
            throw new Error(`提问失败: ${error.message || error}`);
        }
    }

    /**
     * 获取聊天历史
     */
    async getChatHistory(userId = 'default_user') {
        try {
            const response = await fetch(`${this.apiBase}/chat/history?user_id=${encodeURIComponent(userId)}`, {
                method: 'GET',
            });
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            return data.data || [];
        } catch (error) {
            console.error('API chat history error:', error);
            throw error;
        }
    }

    /**
     * 清空聊天历史
     */
    async clearChatHistory(userId = 'default_user') {
        try {
            const response = await fetch(`${this.apiBase}/chat/history/clear`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ user_id: userId }),
            });
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            return data.data;
        } catch (error) {
            console.error('API clear chat history error:', error);
            throw error;
        }
    }

}

// 创建全局API客户端实例
// 可以通过 URL 参数 ?port=8008 或 localStorage.setItem('api_port', '8008') 配置端口
window.apiClient = new APIClient();
