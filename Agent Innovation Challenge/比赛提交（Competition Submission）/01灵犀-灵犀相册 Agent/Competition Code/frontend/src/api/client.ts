import axios, { AxiosInstance, AxiosResponse, AxiosError, InternalAxiosRequestConfig } from 'axios';

// 定义API响应的基本结构
export interface ApiResponse<T = any> {
    status: 'success' | 'error';
    message: string;
    data?: T;
    // 兼容其他可能的字段
    [key: string]: any;
}

const client: AxiosInstance = axios.create({
    baseURL: '/api/v1',
    timeout: 600000, // 增加超时时间到600秒
    headers: {
        'Content-Type': 'application/json',
    },
});

// 请求拦截器
client.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
        // 可以在这里添加 token
        // const token = localStorage.getItem('token');
        // if (token) {
        //     config.headers.Authorization = `Bearer ${token}`;
        // }
        return config;
    },
    (error: AxiosError) => {
        return Promise.reject(error);
    }
);

// 响应拦截器
client.interceptors.response.use(
    (response: AxiosResponse) => {
        // 开发环境打印完整的响应数据以验证数据一致性
        if (import.meta.env.DEV) {
            console.log(`[API Response] ${response.config.url}:`, response.data);
        }
        // 直接返回 response.data，这样调用方拿到的是 ApiResponse
        return response.data;
    },
    (error: AxiosError) => {
        let message = '请求失败';

        if (axios.isCancel(error) || error.code === 'ERR_CANCELED') {
            message = '请求已取消或超时，请稍后重试';
        } else if (error.code === 'ECONNABORTED') {
            message = '请求超时，请检查网络连接或稍后重试';
        } else if (error.response) {
            // 后端返回的错误信息
            message = (error.response.data as any)?.message || error.message || '服务器错误';
        } else if (error.request) {
            // 请求发出但没有收到响应
            message = '网络错误，无法连接到服务器';
        }

        console.error('API Error:', message, error);
        // 这里可以触发全局的错误提示，但为了解耦，建议在调用层处理或使用 EventBus
        return Promise.reject(new Error(message));
    }
);

export default client;
