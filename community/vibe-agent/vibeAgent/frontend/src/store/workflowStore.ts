import { create } from 'zustand'
// 注意：workflowAPI 在新架构中不再使用，此 store 当前未被使用
// 如果需要使用，需要更新为新的 API
// import { workflowAPI } from '../services/api'

interface WorkflowNode {
  id: string
  type: 'task' | 'condition' | 'loop'
  name: string
  code?: string
  config?: Record<string, any>
  dependencies?: string[]
}

interface WorkflowEdge {
  source: string
  target: string
  condition?: string
}

interface Workflow {
  id?: string
  name: string
  description?: string
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  code?: string
  requirements?: string
  dockerfile?: string
  created_at?: string
  updated_at?: string
}

interface WorkflowState {
  currentWorkflow: Workflow | null
  workflows: Workflow[]
  loading: boolean
  error: string | null
  
  // Actions
  setCurrentWorkflow: (workflow: Workflow | null) => void
  createWorkflow: (data: Partial<Workflow>) => Promise<void>
  loadWorkflow: (id: string) => Promise<void>
  updateWorkflow: (id: string, data: Partial<Workflow>) => Promise<void>
  deleteWorkflow: (id: string) => Promise<void>
  executeWorkflow: (id: string) => Promise<void>
}

const useWorkflowStore = create<WorkflowState>((set, get) => ({
  currentWorkflow: null,
  workflows: [],
  loading: false,
  error: null,

  setCurrentWorkflow: (workflow) => {
    set({ currentWorkflow: workflow })
  },

  createWorkflow: async (data) => {
    set({ loading: true, error: null })
    try {
      // TODO: 更新为新的 API
      throw new Error('workflowAPI 已移除，需要使用新的 API')
      // const result = await workflowAPI.create(data)
      set({ 
        currentWorkflow: result,
        loading: false 
      })
    } catch (error: any) {
      set({ 
        error: error.message || '创建工作流失败',
        loading: false 
      })
    }
  },

  loadWorkflow: async (id) => {
    set({ loading: true, error: null })
    try {
      // TODO: 更新为新的 API
      throw new Error('workflowAPI 已移除，需要使用新的 API')
      // const result = await workflowAPI.get(id)
      set({ 
        currentWorkflow: result,
        loading: false 
      })
    } catch (error: any) {
      set({ 
        error: error.message || '加载工作流失败',
        loading: false 
      })
    }
  },

  updateWorkflow: async (id, data) => {
    set({ loading: true, error: null })
    try {
      // TODO: 更新为新的 API
      throw new Error('workflowAPI 已移除，需要使用新的 API')
      // const result = await workflowAPI.update(id, data)
      set({ 
        currentWorkflow: result,
        loading: false 
      })
    } catch (error: any) {
      set({ 
        error: error.message || '更新工作流失败',
        loading: false 
      })
    }
  },

  deleteWorkflow: async (id) => {
    set({ loading: true, error: null })
    try {
      // TODO: 更新为新的 API
      throw new Error('workflowAPI 已移除，需要使用新的 API')
      // await workflowAPI.delete(id)
      set({ 
        currentWorkflow: null,
        loading: false 
      })
    } catch (error: any) {
      set({ 
        error: error.message || '删除工作流失败',
        loading: false 
      })
    }
  },

  executeWorkflow: async (id) => {
    set({ loading: true, error: null })
    try {
      // TODO: 更新为新的 API（使用 incrementalBuildAPI.execute）
      throw new Error('workflowAPI 已移除，需要使用 incrementalBuildAPI.execute')
      // await workflowAPI.execute(id)
      set({ loading: false })
    } catch (error: any) {
      set({ 
        error: error.message || '执行工作流失败',
        loading: false 
      })
    }
  },
}))

export default useWorkflowStore

