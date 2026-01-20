import client from './client';
import type { ChatRequest, ChatResponse } from './types';

export async function sendChatMessage(params: ChatRequest, options?: { signal?: AbortSignal }): Promise<ChatResponse> {
    return await client.post<any, ChatResponse>('/agent/chat', params, { signal: options?.signal });
}

export async function createSession(userId?: string): Promise<string> {
    const res = await client.post<any, { status: string; session_id: string; message?: string }>(
        '/agent/session/create',
        userId ?? null
    );
    return res.session_id;
}
