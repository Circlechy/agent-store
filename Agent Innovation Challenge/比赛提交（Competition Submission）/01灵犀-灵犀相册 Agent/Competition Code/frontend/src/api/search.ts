import client from './client';
import type { ImageResult } from './types';

export interface SearchParams {
    query_text?: string;
    query_image_id?: string;
    query_image_url?: string;
    instruction?: string;
    top_k?: number;
    score_threshold?: number;
    filter_tags?: string[];
}

export interface SearchResponse {
    status: string;
    message: string;
    data: ImageResult[];
    query_type: string;
    total: number;
}

export async function searchImages(params: SearchParams): Promise<SearchResponse> {
    const response = await client.post('/search/', params);
    return response as unknown as SearchResponse;
}

export async function searchByText(
    query: string,
    topK: number = 10,
    scoreThreshold?: number,
    tags?: string[]
): Promise<SearchResponse> {
    const response = await client.get('/search/text', {
        params: {
            query,
            top_k: topK,
            score_threshold: scoreThreshold,
            tags
        }
    });
    return response as unknown as SearchResponse;
}

export async function searchByImageId(
    imageId: string,
    topK: number = 10,
    scoreThreshold?: number
): Promise<SearchResponse> {
    const response = await client.get(`/search/image/${imageId}`, {
        params: {
            top_k: topK,
            score_threshold: scoreThreshold
        }
    });
    return response as unknown as SearchResponse;
}
