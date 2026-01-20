import { create } from 'zustand';
import { sendChatMessage } from '../api/agent';
import { getImageUrl } from '../api/storage';
import type { ChatMessage, ImageResult } from '../api/types';

interface ChatStore {
    sessionId: string | null;
    messages: ChatMessage[];
    isLoading: boolean;
    error: string | null;
    sendMessage: (query: string) => Promise<void>;
    clearHistory: () => void;
}

export const useChatStore = create<ChatStore>((set, get) => ({
    sessionId: localStorage.getItem('chat_session_id'),
    messages: [],
    isLoading: false,
    error: null,

    sendMessage: async (query: string) => {
        const { sessionId, messages } = get();

        const userMessage: ChatMessage = {
            id: crypto.randomUUID(),
            type: 'user',
            content: query,
            timestamp: new Date(),
        };

        set({ messages: [...messages, userMessage], isLoading: true, error: null });

        // Setup AbortController for timeout (120 seconds)
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 120000);

        try {
            const response = await sendChatMessage({
                query,
                session_id: sessionId || undefined,
                top_k: 10,
            }, { signal: controller.signal });

            clearTimeout(timeoutId);

            if (!response || typeof response.session_id !== 'string' || typeof response.answer !== 'string') {
                throw new Error('服务器响应格式异常，请刷新页面后重试。');
            }

            if (response.session_id && response.session_id !== sessionId) {
                localStorage.setItem('chat_session_id', response.session_id);
                set({ sessionId: response.session_id });
            }

            const images: ImageResult[] = response.results?.images?.map(img => ({
                ...img,
                preview_url: getImageUrl(img.id),
            })) || [];

            const agentMessage: ChatMessage = {
                id: crypto.randomUUID(),
                type: 'agent',
                content: response.answer,
                images: images.length > 0 ? images : undefined,
                suggestions: response.suggestions,
                timestamp: new Date(response.timestamp),
            };

            set(state => ({
                messages: [...state.messages, agentMessage],
                isLoading: false,
            }));
        } catch (error: any) {
            clearTimeout(timeoutId);
            
            let errorMessage = error instanceof Error ? error.message : '发送失败';
            
            // Handle Timeout / Abort
            if (error.name === 'CanceledError' || error.name === 'AbortError' || error.code === 'ERR_CANCELED') {
                errorMessage = '请求超时：检索可能较慢（首次加载/向量生成），请稍后重试。';
            }

            // Create an error message bubble
            const errorMessageObj: ChatMessage = {
                id: crypto.randomUUID(),
                type: 'agent',
                content: `❌ ${errorMessage}`,
                timestamp: new Date(),
            };

            set(state => ({
                isLoading: false,
                error: errorMessage,
                messages: [...state.messages, errorMessageObj]
            }));
        }
    },

    clearHistory: () => {
        localStorage.removeItem('chat_session_id');
        set({ sessionId: null, messages: [], error: null });
    },
}));
