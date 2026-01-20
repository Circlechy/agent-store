export interface ImageResult {
    id: string;
    score: number;
    metadata: {
        filename: string;
        file_path: string;
        file_size?: number;
        width?: number;
        height?: number;
        format?: string;
        created_at: string;
        tags: string[];
        description?: string;
    };
    preview_url?: string;
}

export interface ChatRequest {
    query: string;
    session_id?: string;
    top_k?: number;
    score_threshold?: number;
}

export interface ChatResponse {
    session_id: string;
    answer: string;
    intent: string;
    optimized_query: string;
    results?: {
        total: number;
        images: ImageResult[];
    };
    suggestions: string[];
    timestamp: string;
}

export interface UploadResponse {
    status: string;
    message: string;
    data: {
        id: string;
        filename: string;
        file_path: string;
        full_path: string;
        file_size: number;
        width: number;
        height: number;
        format: string;
        created_at: string;
        url: string;
        indexed: boolean | string;
        index_mode: string;
    };
}

export interface ChatMessage {
    id: string;
    type: 'user' | 'agent';
    content: string;
    images?: ImageResult[];
    suggestions?: string[];
    timestamp: Date;
}
