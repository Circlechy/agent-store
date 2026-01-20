import client from './client';
import type { UploadResponse } from './types';

export function getImageUrl(imageId: string): string {
    return `/api/v1/storage/images/${imageId}`;
}

export async function uploadImage(
    file: File,
    autoIndex: boolean = true,
    tags: string[] = [],
    description: string = '',
    onProgress?: (progress: number) => void
): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('auto_index', String(autoIndex));
    formData.append('async_index', 'true');

    if (tags.length > 0) {
        formData.append('tags', tags.join(','));
    }
    if (description) {
        formData.append('description', description);
    }

    const response = await client.post<any, UploadResponse>('/storage/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
            if (e.total && onProgress) {
                onProgress(Math.round((e.loaded * 100) / e.total));
            }
        }
    });
    return response;
}

export async function deleteImage(imageId: string): Promise<void> {
    await client.delete(`/storage/images/${imageId}`);
}

export interface ImageListItem {
    id: string;
    filename: string;
    file_path: string;
    file_size: number;
    width: number;
    height: number;
    format: string;
    created_at: string;
    url: string;
}

export interface ImageListResponse {
    status: string;
    message: string;
    data: ImageListItem[];
    total: number;
    page: number;
    page_size: number;
}

export async function listImages(
    page: number = 1,
    pageSize: number = 20,
    sortBy: string = 'created_at',
    sortOrder: string = 'desc'
): Promise<ImageListResponse> {
    // client.get returns the response body directly due to the interceptor
    const response = await client.get<any, ImageListResponse>('/storage/images', {
        params: {
            page,
            page_size: pageSize,
            sort_by: sortBy,
            sort_order: sortOrder
        }
    });
    return response;
}

export async function getImageInfo(imageId: string) {
    const { data } = await client.get(`/storage/images/${imageId}/info`);
    return data;
}

export async function getStorageStats() {
    const { data } = await client.get('/storage/stats');
    return data;
}
