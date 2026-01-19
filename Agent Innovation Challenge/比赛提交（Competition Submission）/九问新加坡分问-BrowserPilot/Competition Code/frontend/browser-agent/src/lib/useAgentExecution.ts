import { create } from "zustand";

export interface SubTask {
  id: string;
  toolName: string;
  agentId: string;
  agentType: "main" | "sub";
  iteration: number;
  status: "executing" | "completed" | "failed" | "cancelled";
  resultPreview?: string;
  subTasks?: SubTask[]; // Nested sub-agent tools
}

interface AgentExecutionState {
  isActive: boolean;
  isDismissed: boolean;
  isMinimized: boolean;
  mainAgentId: string | null;
  mainTaskDescription: string | null;
  currentIteration: number;
  maxIteration: number;
  subtasks: SubTask[];

  // Actions
  startMainAgent: (agentId: string, iteration: number, maxIteration: number) => void;
  setMainTaskDescription: (description: string) => void;
  addSubTask: (task: Omit<SubTask, "subTasks">) => void;
  updateSubTaskStatus: (id: string, status: "executing" | "completed" | "failed" | "cancelled", resultPreview?: string) => void;
  addNestedSubTask: (parentToolName: string, task: Omit<SubTask, "subTasks">) => void;
  updateNestedSubTaskStatus: (parentToolName: string, id: string, status: "executing" | "completed" | "failed" | "cancelled", resultPreview?: string) => void;
  cancelAllExecuting: () => void;
  toggleMinimize: () => void;
  dismiss: () => void;
  reset: () => void;
}

export const useAgentExecution = create<AgentExecutionState>((set, get) => ({
  isActive: false,
  isDismissed: false,
  isMinimized: false,
  mainAgentId: null,
  mainTaskDescription: null,
  currentIteration: 0,
  maxIteration: 0,
  subtasks: [],

  startMainAgent: (agentId: string, iteration: number, maxIteration: number) => {
    const state = get();
    // Only start if not already active, or if dismissed, allow restart
    if (!state.isActive || state.isDismissed) {
      set({
        isActive: true,
        isDismissed: false,
        isMinimized: false,
        mainAgentId: agentId,
        currentIteration: iteration,
        maxIteration: maxIteration,
        mainTaskDescription: null,
        subtasks: [],
      });
    } else {
      // Update iteration for existing agent
      set({
        currentIteration: iteration,
        maxIteration: maxIteration,
      });
    }
  },

  setMainTaskDescription: (description: string) => {
    set({ mainTaskDescription: description });
  },

  addSubTask: (task: Omit<SubTask, "subTasks">) => {
    set((state) => {
      // Check if task with same id already exists
      const exists = state.subtasks.some((t) => t.id === task.id);
      if (exists) return state;
      
      return {
        subtasks: [...state.subtasks, { ...task, subTasks: [] }],
      };
    });
  },

  updateSubTaskStatus: (id: string, status: "executing" | "completed" | "failed" | "cancelled", resultPreview?: string) => {
    set((state) => ({
      subtasks: state.subtasks.map((task) =>
        task.id === id
          ? { ...task, status, resultPreview: resultPreview ?? task.resultPreview }
          : task
      ),
    }));
  },

  addNestedSubTask: (parentToolName: string, task: Omit<SubTask, "subTasks">) => {
    set((state) => ({
      subtasks: state.subtasks.map((parentTask) => {
        // Find parent by matching tool name (agent tools like "agent-browsing")
        if (parentTask.toolName === parentToolName && parentTask.status === "executing") {
          const exists = parentTask.subTasks?.some((t) => t.id === task.id);
          if (exists) return parentTask;
          
          return {
            ...parentTask,
            subTasks: [...(parentTask.subTasks || []), { ...task, subTasks: [] }],
          };
        }
        return parentTask;
      }),
    }));
  },

  updateNestedSubTaskStatus: (parentToolName: string, id: string, status: "executing" | "completed" | "failed" | "cancelled", resultPreview?: string) => {
    set((state) => ({
      subtasks: state.subtasks.map((parentTask) => {
        if (parentTask.toolName === parentToolName) {
          return {
            ...parentTask,
            subTasks: parentTask.subTasks?.map((subTask) =>
              subTask.id === id
                ? { ...subTask, status, resultPreview: resultPreview ?? subTask.resultPreview }
                : subTask
            ),
          };
        }
        return parentTask;
      }),
    }));
  },

  cancelAllExecuting: () => {
    set((state) => ({
      subtasks: state.subtasks.map((task) => {
        // Cancel main task if executing
        const cancelledTask = task.status === "executing"
          ? { ...task, status: "cancelled" as const, resultPreview: "Cancelled by user" }
          : task;

        // Cancel nested subtasks if executing
        if (cancelledTask.subTasks && cancelledTask.subTasks.length > 0) {
          return {
            ...cancelledTask,
            subTasks: cancelledTask.subTasks.map((subTask) =>
              subTask.status === "executing"
                ? { ...subTask, status: "cancelled" as const, resultPreview: "Cancelled by user" }
                : subTask
            ),
          };
        }

        return cancelledTask;
      }),
    }));
  },

  toggleMinimize: () => {
    set((state) => ({ isMinimized: !state.isMinimized }));
  },

  dismiss: () => {
    set({ isDismissed: true });
  },

  reset: () => {
    set({
      isActive: false,
      isDismissed: false,
      isMinimized: false,
      mainAgentId: null,
      mainTaskDescription: null,
      currentIteration: 0,
      maxIteration: 0,
      subtasks: [],
    });
  },
}));

/**
 * Extract main task description from assistant message content
 * Looks for #PLAN# section or uses first paragraph
 */
export function extractTaskDescription(content: string): string | null {
  if (!content) return null;
  
  // Look for #PLAN# section
  const planMatch = content.match(/#PLAN#\s*([\s\S]*?)(?=\n\n|Step \d|$)/i);
  if (planMatch) {
    // Extract numbered items from plan
    const planItems = planMatch[1]
      .split(/\n/)
      .filter((line) => /^\d+\./.test(line.trim()))
      .map((line) => line.trim())
      .slice(0, 3); // First 3 items
    
    if (planItems.length > 0) {
      return planItems.join("\n");
    }
  }
  
  // Fallback: first paragraph (up to first double newline or 200 chars)
  const firstPara = content.split(/\n\n/)[0];
  if (firstPara && firstPara.length > 0) {
    return firstPara.length > 200 ? firstPara.substring(0, 200) + "..." : firstPara;
  }
  
  return null;
}


