import axios from 'axios'

// 动态获取 API 地址
// 1. 优先使用环境变量 VITE_API_BASE_URL（生产环境或前后端分离时使用）
// 2. 开发环境：使用相对路径 /api，让 Vite 代理处理（自动适配局域网）
// 3. 如果设置了 VITE_API_BASE_URL，直接使用（用于前后端分离的场景）
function getApiBaseUrl(): string {
  // 如果设置了环境变量，直接使用（用于前后端分离或生产环境）
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL
  }
  
  // 开发环境：使用相对路径，让 Vite 代理处理
  // 这样无论通过 localhost 还是局域网 IP 访问，都能正确代理到后端
  if (import.meta.env.DEV) {
    return ''  // 使用相对路径，Vite 代理会自动处理
  }
  
  // 生产环境：使用当前页面的 origin（假设前后端在同一域名下）
  if (typeof window !== 'undefined') {
    return window.location.origin
  }
  
  // 默认回退
  return ''
}

const API_BASE_URL = getApiBaseUrl()

const apiClient = axios.create({
  baseURL: API_BASE_URL ? `${API_BASE_URL}/api/v1` : '/api/v1',  // 开发环境使用相对路径
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    // TODO: 添加认证token
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    // 统一错误处理
    const errorMessage = error.response?.data?.detail || error.response?.data?.message || error.message || '未知错误'
    const errorInfo = {
      message: errorMessage,
      status: error.response?.status,
      statusText: error.response?.statusText,
      data: error.response?.data,
      originalError: error,
    }
    console.error('API Error:', errorInfo)
    return Promise.reject(errorInfo)
  }
)

export default apiClient

// API方法
// 注意：以下 API 在新架构中不再使用，已注释
// 如果确认不需要，可以删除这些代码
// 备份文件：api_legacy.ts.backup

// export const workflowAPI = {
//   create: (data: any) => apiClient.post('/workflow/create', data),
//   get: (id: string) => apiClient.get(`/workflow/${id}`),
//   update: (id: string, data: any) => apiClient.put(`/workflow/${id}`, data),
//   delete: (id: string) => apiClient.delete(`/workflow/${id}`),
//   execute: (id: string) => apiClient.post(`/workflow/${id}/execute`),
// }

// export const codegenAPI = {
//   generate: (data: any) => apiClient.post('/codegen/generate', data),
//   validate: (code: string) => apiClient.post('/codegen/validate', { code }),
//   getTemplates: (language: string = 'python') =>
//     apiClient.get(`/codegen/templates?language=${language}`),
// }

// export const nlpAPI = {
//   parse: (data: any) => apiClient.post('/nlp/parse', data),
//   detectIntent: (data: any) => apiClient.post('/nlp/intent', data),
// }

// export const configAPI = {
//   generate: (data: any) => apiClient.post('/config/generate', data),
//   getTemplates: () => apiClient.get('/config/templates'),
// }

export const mermaidAPI = {
  generateFromCode: (code: string) => apiClient.post('/mermaid/generate-from-code', { code }),
  generateFromWorkflow: (workflow: any) => apiClient.post('/mermaid/generate-from-workflow', { workflow }),
}

export const incrementalBuildAPI = {
  start: async function* (
    data: { user_input: string; workflow_name?: string; max_iterations?: number; agent_mode?: string },
    onEvent?: (event: any) => void
  ) {
    // 使用 fetch 进行 SSE 流式响应（支持 POST）
    const API_BASE_URL = getApiBaseUrl()
    // 新的 API 路径：/api/v1/agent/start
    const response = await fetch(`${API_BASE_URL}/api/v1/agent/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify({
        user_input: data.user_input,
        workflow_name: data.workflow_name,
        max_iterations: data.max_iterations || 3,
        agent_mode: data.agent_mode || 'workflow',  // 默认 workflow 保持向后兼容
      }),
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`)
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()

    if (!reader) {
      throw new Error('Response body is not readable')
    }

    let buffer = ''
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.trim() === '') continue
          if (line.startsWith('data: ')) {
            try {
              const eventData = JSON.parse(line.slice(6))
              if (onEvent) {
                onEvent(eventData)
              }
              yield eventData
            } catch (e) {
              console.error('Failed to parse SSE event:', e, line)
            }
          }
        }
      }
    } finally {
      reader.releaseLock()
    }
  },
  // 注意：plan 端点在新架构中可能不需要（直接在 start 中处理）
  execute: async function* (
    data: { workflow_dir: string; query: string; conversation_id?: string },
    onEvent?: (event: any) => void
  ) {
    // 使用 fetch 进行 SSE 流式响应（支持 POST）
    const API_BASE_URL = getApiBaseUrl()
    const response = await fetch(`${API_BASE_URL}/api/v1/agent/execute`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify({
        workflow_dir: data.workflow_dir,
        query: data.query,
        conversation_id: data.conversation_id,
      }),
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`)
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()

    if (!reader) {
      throw new Error('Response body is not readable')
    }

    let buffer = ''
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.trim() === '') continue
          if (line.startsWith('data: ')) {
            try {
              const eventData = JSON.parse(line.slice(6))
              if (onEvent) {
                onEvent(eventData)
              }
              yield eventData
            } catch (e) {
              console.error('Failed to parse SSE event:', e, line)
            }
          }
        }
      }
    } finally {
      reader.releaseLock()
    }
  },
  continue: async function* (
    data: { execution_id: string; reply_value: string; component_id: string },
    onEvent?: (event: any) => void
  ) {
    // 使用 fetch 进行 SSE 流式响应（支持 POST）
    const API_BASE_URL = getApiBaseUrl()
    const response = await fetch(`${API_BASE_URL}/api/v1/agent/continue`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify({
        execution_id: data.execution_id,
        reply_value: data.reply_value,
        component_id: data.component_id,
      }),
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`)
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()

    if (!reader) {
      throw new Error('Response body is not readable')
    }

    let buffer = ''
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.trim() === '') continue
          if (line.startsWith('data: ')) {
            try {
              const eventData = JSON.parse(line.slice(6))
              if (onEvent) {
                onEvent(eventData)
              }
              yield eventData
            } catch (e) {
              console.error('Failed to parse SSE event:', e, line)
            }
          }
        }
      }
    } finally {
      reader.releaseLock()
    }
  },
  clearHistory: (data: { workflow_dir: string; conversation_id: string }) =>
    apiClient.post('/agent/clear-history', data),
  modify: async function* (
    data: { workflow_dir: string; modification_request: string; original_user_input: string; workflow_description?: string },
    onEvent?: (event: any) => void
  ) {
    // 使用 fetch 进行 SSE 流式响应（支持 POST）
    const API_BASE_URL = getApiBaseUrl()
    // 新的 API 路径：/api/v1/agent/modify
    const response = await fetch(`${API_BASE_URL}/api/v1/agent/modify`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify({
        workflow_dir: data.workflow_dir,
        modification_request: data.modification_request,
        original_user_input: data.original_user_input,
        workflow_description: data.workflow_description,
      }),
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`)
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    if (!reader) {
      throw new Error('Response body is not readable')
    }

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.trim() === '') continue
          if (line.startsWith('data: ')) {
            try {
              const eventData = JSON.parse(line.slice(6))
              if (onEvent) {
                onEvent(eventData)
              }
              yield eventData
            } catch (e) {
              console.error('Failed to parse SSE event:', e, line)
            }
          }
        }
      }
    } finally {
      reader.releaseLock()
    }
  },
  // 获取工作流文件列表或单个文件内容
  // 新的 API 路径：/api/v1/agent/files
  getFiles: async (data: { workflow_dir: string; file_name?: string }) => {
    return apiClient.post('/agent/files', data)
  },
}

// 部署 API
export const deployAPI = {
  deploy: (data: { workflow_dir: string }) =>
    apiClient.post('/workflow/deploy', data),
}

