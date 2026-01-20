import { useState, useRef, useEffect } from 'react'
import { Layout, Card, Button, Space, Typography, message, Input, Spin } from 'antd'
import { DownloadOutlined, PlayCircleOutlined } from '@ant-design/icons'
import BuildProcess, { BuildStep } from '../components/BuildProcess/BuildProcess'
import CodeDirectory, { FileTreeItem } from '../components/CodeDirectory/CodeDirectory'
import WorkflowChat from '../components/WorkflowChat/WorkflowChat'
import ErrorDisplay from '../components/ErrorDisplay/ErrorDisplay'
import AgentModeSelector, { AgentMode } from '../components/AgentModeSelector'
import { incrementalBuildAPI } from '../services/api'

const { Content } = Layout
const { Title } = Typography

interface WorkflowBuilderProps {
  initialQuery?: string
}

function WorkflowBuilderIncremental({ initialQuery }: WorkflowBuilderProps) {
  const [query, setQuery] = useState(initialQuery || '')
  const [agentMode, setAgentMode] = useState<AgentMode>('workflow')
  const [isBuilding, setIsBuilding] = useState(false)
  const [buildSteps, setBuildSteps] = useState<BuildStep[]>([])
  const [currentStepId, setCurrentStepId] = useState<string | undefined>()
  const [generatedFiles, setGeneratedFiles] = useState<FileTreeItem[]>([])
  const [workflow, setWorkflow] = useState<any>(null)
  const [workflowId, setWorkflowId] = useState<string | undefined>()
  const [savedDirectory, setSavedDirectory] = useState<string | undefined>()
  const [originalUserInput, setOriginalUserInput] = useState<string>('')
  const [workflowDescription, setWorkflowDescription] = useState<string | undefined>()
  const [isModifying, setIsModifying] = useState(false)  // 标记是否在修改流程中
  const [currentIteration, setCurrentIteration] = useState<number>(0)  // 当前迭代编号（0表示不在迭代中）
  const currentIterationRef = useRef<number>(0)  // 使用 ref 确保立即获取最新的迭代编号
  const [error, setError] = useState<any>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const [conversationId, setConversationId] = useState<string | undefined>()  // 对话会话ID
  const [interactionRequest, setInteractionRequest] = useState<any>(null)  // 交互请求
  const [isWaitingInteraction, setIsWaitingInteraction] = useState(false)  // 是否等待交互回复
  const [showChatPanel, setShowChatPanel] = useState(false)  // 控制右侧对话面板显示
  const [activeCodeTab, setActiveCodeTab] = useState<string>('files')  // 控制代码区域的tab
  // 思考过程流式显示定时器映射：stepId -> timer
  const streamingTimersRef = useRef<Map<string, number>>(new Map())
  // 思考过程流式显示状态映射：stepId -> { targetText, currentIndex }
  const streamingStateRef = useRef<Map<string, { targetText: string; currentIndex: number }>>(new Map())
  // 执行结果流式显示定时器映射：stepId -> timer
  const streamingResultTimersRef = useRef<Map<string, number>>(new Map())
  // 执行结果流式显示状态映射：stepId -> { targetText, currentIndex }
  const streamingResultStateRef = useRef<Map<string, { targetText: string; currentIndex: number }>>(new Map())
  // 执行动作流式显示定时器映射：stepId -> timer
  const streamingActionTimersRef = useRef<Map<string, number>>(new Map())
  // 执行动作流式显示状态映射：stepId -> { targetText, currentIndex }
  const streamingActionStateRef = useRef<Map<string, { targetText: string; currentIndex: number }>>(new Map())
  // 观察结果流式显示定时器映射：stepId -> timer
  const streamingObservationTimersRef = useRef<Map<string, number>>(new Map())
  // 观察结果流式显示状态映射：stepId -> { targetText, currentIndex }
  const streamingObservationStateRef = useRef<Map<string, { targetText: string; currentIndex: number }>>(new Map())

  // 组件卸载时清理所有定时器
  useEffect(() => {
    return () => {
      streamingTimersRef.current.forEach((timer) => clearInterval(timer))
      streamingTimersRef.current.clear()
      streamingStateRef.current.clear()
      streamingResultTimersRef.current.forEach((timer) => clearInterval(timer))
      streamingResultTimersRef.current.clear()
      streamingResultStateRef.current.clear()
      streamingActionTimersRef.current.forEach((timer) => clearInterval(timer))
      streamingActionTimersRef.current.clear()
      streamingActionStateRef.current.clear()
      streamingObservationTimersRef.current.forEach((timer) => clearInterval(timer))
      streamingObservationTimersRef.current.clear()
      streamingObservationStateRef.current.clear()
    }
  }, [])

  // 辅助函数：根据 step_type 获取对应的步骤类型
  const getStepTypeFromStepType = (stepType: string): BuildStep['type'] => {
    if (stepType === 'config') return 'creating'
    if (stepType === 'component' || stepType === 'connection') return 'coding'
    if (stepType === 'analyze_modification') return 'planning'  // 分析修改需求属于规划类型
    if (stepType === 'modify_file') return 'coding'  // 修改文件属于编码类型
    return 'coding' // 默认返回 coding
  }

  // 更新步骤状态
  const updateStep = (stepId: string, updates: Partial<BuildStep>) => {
    setBuildSteps((prev) => {
      const existing = prev.find((s) => s.id === stepId)
      if (existing) {
        // 合并details，而不是覆盖
        const mergedDetails = existing.details && updates.details
          ? { ...existing.details, ...updates.details }
          : updates.details || existing.details
        
        // 如果 updates 中没有明确设置 status，保留原有的 status
        const mergedStatus = updates.status !== undefined ? updates.status : existing.status
        
        // 从 updates 中排除 status 和 details，避免覆盖我们合并后的值
        const { status: _, details: __, ...otherUpdates } = updates
        
        return prev.map((step) => 
          step.id === stepId 
            ? { 
                ...step, 
                ...otherUpdates, // 先应用其他更新（不包含 status 和 details）
                status: mergedStatus, // 使用合并后的状态
                details: mergedDetails, // 使用合并后的详情
                // ✅ 保留原有的 timestamp，不要每次更新都改变时间戳
                timestamp: existing.timestamp || new Date()
              } 
            : step
        )
      } else {
        // ✅ 新建步骤时设置当前时间戳
        return [...prev, { id: stepId, ...updates, timestamp: new Date() } as BuildStep]
      }
    })
    setCurrentStepId(stepId)
  }


  // 生成工作流（增量式）
  const handleGenerate = async () => {
    if (!query.trim()) {
      message.warning('请输入工作流描述')
      return
    }

    // 清理所有流式显示定时器
    streamingTimersRef.current.forEach((timer) => clearInterval(timer))
    streamingTimersRef.current.clear()
    streamingStateRef.current.clear()
    streamingResultTimersRef.current.forEach((timer) => clearInterval(timer))
    streamingResultTimersRef.current.clear()
    streamingResultStateRef.current.clear()
    streamingActionTimersRef.current.forEach((timer) => clearInterval(timer))
    streamingActionTimersRef.current.clear()
    streamingActionStateRef.current.clear()
    streamingObservationTimersRef.current.forEach((timer) => clearInterval(timer))
    streamingObservationTimersRef.current.clear()
    streamingObservationStateRef.current.clear()

    // 重置状态
    setIsBuilding(true)
    setError(null)
    setBuildSteps([])
    setCurrentStepId(undefined)
    setGeneratedFiles([])
    setWorkflow(null)
    setWorkflowId(undefined)
    setOriginalUserInput(query)
    setWorkflowDescription(undefined)
    setIsModifying(false)  // 第一次构建不是修改流程
    // 注意：不重置conversationId，保持多轮对话的连续性

    // 创建AbortController用于取消请求
    abortControllerRef.current = new AbortController()

    try {
      // 使用增量构建API
      const eventStream = incrementalBuildAPI.start(
        {
          user_input: query,
          max_iterations: 3,
          agent_mode: agentMode,
        },
        (event) => {
          // 实时处理事件
          handleBuildEvent(event)
        }
      )

      // 处理事件流
      for await (const event of eventStream) {
        handleBuildEvent(event)
      }

      message.success(
        agentMode === 'agent' 
          ? 'Agent 生成完成！' 
          : agentMode === 'multi_agent'
          ? 'Multi-Agent 系统生成完成！'
          : '工作流生成完成！'
      )
    } catch (error: any) {
      console.error('生成工作流失败:', error)
      setError(error)
      message.error({
        content: `生成失败: ${error?.message || '未知错误'}`,
        duration: 8,
      })
    } finally {
      setIsBuilding(false)
      abortControllerRef.current = null
    }
  }

  // 处理构建事件
  const handleBuildEvent = (event: any) => {
    const eventType = event.type
    
    // ✅ 为迭代中的步骤生成唯一ID：如果当前在迭代中，给所有步骤ID加上迭代前缀
    let stepId = event.step_id || `step_${eventType}`
    const modifySessionId = (window as any).currentModifySessionId
    
    // 为迭代中的普通步骤（非 iteration_started/completed 事件）加上迭代前缀
    // 使用 ref 而不是 state，确保获取最新的迭代编号
    if (currentIterationRef.current > 0 && !['iteration_started', 'iteration_completed', 'test_started', 'test_completed', 'test_failed', 'build_completed', 'build_failed'].includes(eventType)) {
      const iterationPrefix = isModifying && modifySessionId
        ? `${modifySessionId}_iteration_${currentIterationRef.current}`
        : `iteration_${currentIterationRef.current}`
      
      // 只有当 stepId 还没有包含迭代前缀时才添加
      if (!stepId.includes(`iteration_${currentIterationRef.current}`)) {
        stepId = `${iterationPrefix}_${stepId}`
        console.log(`✅ [handleBuildEvent] 为迭代步骤添加前缀: ${stepId}, 迭代: ${currentIterationRef.current}, 事件: ${eventType}`)
      }
    }
    
    const stepName = event.step_name || event.message

    switch (eventType) {
      case 'plan_started':
        // ✅ 判断是否是修改流程：检查 step_id、消息内容、isModifying 状态
        const modifySessionIdPlan = (window as any).currentModifySessionId
        const stepIdFromEvent = event.step_id || ''
        const isModifyFlow = isModifying 
          || stepIdFromEvent.startsWith('modify_')
          || event.message?.includes('修改')
          || modifySessionIdPlan
        
        // ✅ 修改流程：必须使用唯一的 step_id，避免覆盖已有步骤
        let planStepId: string
        if (isModifyFlow) {
          // 优先使用事件中的 step_id（如果包含 modify_ 前缀）
          if (stepIdFromEvent && stepIdFromEvent.startsWith('modify_')) {
            // 如果有会话ID，组合使用；否则直接使用事件中的 step_id
            planStepId = modifySessionIdPlan 
              ? `${modifySessionIdPlan}_${stepIdFromEvent}`
              : stepIdFromEvent
          } else if (modifySessionIdPlan) {
            planStepId = `${modifySessionIdPlan}_plan`
          } else {
            // 如果没有会话ID，创建一个（防止覆盖）
            const newModifySessionId = `modify_${Date.now()}`
            ;(window as any).currentModifySessionId = newModifySessionId
            planStepId = `${newModifySessionId}_plan`
          }
          setIsModifying(true)
        } else {
          planStepId = stepIdFromEvent || 'plan'
        }
        
        // ✅ 如果当前在迭代中，给 planStepId 加上迭代前缀（使用 ref 确保获取最新值）
        if (currentIterationRef.current > 0) {
          const iterationPrefix = isModifying && modifySessionIdPlan
            ? `${modifySessionIdPlan}_iteration_${currentIterationRef.current}`
            : `iteration_${currentIterationRef.current}`
          
          if (!planStepId.includes(`iteration_${currentIterationRef.current}`)) {
            planStepId = `${iterationPrefix}_${planStepId}`
            console.log(`✅ [plan_started] 为迭代中的plan步骤添加前缀: ${planStepId}, 迭代: ${currentIterationRef.current}`)
          }
        }
        
        // ✅ 修改流程：使用事件中的消息或 step_name，不再硬编码"分析现有工作流结构"
        const planTitle = event.step_name || event.message || (isModifyFlow ? '开始修改工作流' : '规划阶段')

        updateStep(planStepId, {
          type: 'planning',
          title: planTitle,
          description: event.message || '开始分析...',
          status: 'running',
        })
        break

      case 'plan_completed':
        const planData = event.data
        const stepIdFromEventCompleted = event.step_id || ''
        const isModifyPlan = isModifying 
          || stepIdFromEventCompleted.startsWith('modify_')
          || planData?.plan?.modification_request 
          || planData?.components_to_modify
        const modifySessionIdPlanCompleted = (window as any).currentModifySessionId
        
        if (isModifyPlan) {
          // 修改流程：显示需要修改的组件
          setIsModifying(true)
          const componentsToModify = planData?.plan?.components_to_modify || planData?.components_to_modify || []
          
          // ✅ 确保使用唯一的 step_id（与 plan_started 保持一致）
          let planStepIdCompleted: string
          if (stepIdFromEventCompleted && stepIdFromEventCompleted.startsWith('modify_')) {
            // 优先使用事件中的 step_id（如果包含 modify_ 前缀）
            planStepIdCompleted = modifySessionIdPlanCompleted 
              ? `${modifySessionIdPlanCompleted}_${stepIdFromEventCompleted}`
              : stepIdFromEventCompleted
          } else if (modifySessionIdPlanCompleted) {
            planStepIdCompleted = `${modifySessionIdPlanCompleted}_plan`
          } else {
            // 如果还是没有会话ID，创建一个（防止覆盖）
            const newModifySessionId = `modify_${Date.now()}`
            ;(window as any).currentModifySessionId = newModifySessionId
            planStepIdCompleted = `${newModifySessionId}_plan`
          }
          
          // ✅ 如果当前在迭代中，给 planStepIdCompleted 加上迭代前缀（使用 ref 确保获取最新值）
          if (currentIterationRef.current > 0) {
            const iterationPrefix = isModifying && modifySessionIdPlanCompleted
              ? `${modifySessionIdPlanCompleted}_iteration_${currentIterationRef.current}`
              : `iteration_${currentIterationRef.current}`
            
            if (!planStepIdCompleted.includes(`iteration_${currentIterationRef.current}`)) {
              planStepIdCompleted = `${iterationPrefix}_${planStepIdCompleted}`
              console.log(`✅ [plan_completed] 为迭代中的plan步骤添加前缀: ${planStepIdCompleted}, 迭代: ${currentIterationRef.current}`)
            }
          }
          
          // 如果 plan_completed 事件中包含 all_files，提前更新文件列表
          if (planData?.all_files) {
            const files: FileTreeItem[] = Object.entries(planData.all_files).map(([name, content]) => ({
              name,
              path: name,
              type: 'file',
              content: content as string,
            }))
            setGeneratedFiles(files)
            console.log(`✅ [plan_completed] 更新文件列表，包含 ${files.length} 个文件:`, files.map(f => f.name))
          }

          updateStep(planStepIdCompleted, {
            status: 'completed',
            description: event.message || `分析完成，需要修改 ${componentsToModify.length} 个节点/文件`,
            details: {
              plan: planData?.plan || planData,
              components_to_modify: componentsToModify,
              steps: planData?.steps || [],
            },
          })
          
          // 为每个需要修改的组件创建步骤（分析步骤已经完成，只显示实际修改步骤）
          if (planData?.steps) {
            planData.steps.forEach((step: any) => {
              // ✅ 确保修改流程中的步骤使用唯一的 step_id
              const uniqueStepId = modifySessionIdPlanCompleted && step.step_id
                ? `${modifySessionIdPlanCompleted}_${step.step_id}`
                : step.step_id
              // 分析步骤标记为已完成，实际修改步骤会在后续执行
              const stepStatus = step.status === 'completed' ? 'completed' : 'pending'
              updateStep(uniqueStepId, {
                type: step.step_id.startsWith('analyze_') ? 'planning' : 'coding',
                title: step.step_name || `修改: ${step.component || '组件'}`,
                description: step.description || (step.status === 'completed' ? '分析完成' : '准备修改...'),
                status: stepStatus,
              })
            })
          }
        } else {
          // 原始构建流程
          setIsModifying(false)
          // 不在 plan_completed 时创建步骤，等待 step_started 事件时逐个创建
          // updateStep 内部会自动合并 details，保留已有的思考内容
          updateStep('plan', {
            status: 'completed',
            description: `规划完成，共 ${planData?.steps?.length || 0} 个步骤`,
            details: {
              plan: planData?.plan || planData,
              steps: planData?.steps || [], // 保存步骤信息供后续使用
            },
            isThinkingActive: false, // 停止活跃思考展示
          })
        }
        break

      case 'step_started':
        // ✅ 修改流程：确保使用唯一的 step_id
        const modifySessionIdStep = (window as any).currentModifySessionId
        const uniqueStepId = isModifying && modifySessionIdStep && !stepId.startsWith(modifySessionIdStep)
          ? `${modifySessionIdStep}_${stepId}`
          : stepId
        // 只有在修改流程中，才给步骤标题添加"修改:"前缀
        let stepTitle = stepName
        if (isModifying) {
          // 修改流程：如果标题中还没有"修改"或"添加"，则添加"修改:"前缀
          if (!stepName?.includes('修改') && !stepName?.includes('添加') && !stepName?.includes('删除')) {
            stepTitle = `修改: ${stepName}`
          }
        }
        // 获取步骤类型（从事件数据中或根据 step_id 推断）
        const stepTypeFromData = event.data?.step?.step_type
        let stepType: BuildStep['type']
        if (stepTypeFromData) {
          stepType = getStepTypeFromStepType(stepTypeFromData)
        } else if (stepId === 'analyze_modification' || stepId.includes('analyze_modification')) {
          stepType = 'planning'  // analyze_modification 属于规划类型
        } else if (stepId.startsWith('generate_')) {
          stepType = 'coding'
        } else {
          stepType = 'planning'
        }
        
        updateStep(uniqueStepId, {
          type: stepType,
          status: 'running',
          title: stepTitle,
          description: event.message || stepName,
          details: event.data?.step || {},
        })
        break

      case 'step_thinking':
        // 更新步骤的思考过程，并标记为活跃状态（实时展示在卡片下方）
        // 前端实现流式显示：当收到新的思考内容时，使用打字机效果逐字符显示
        const newThought = event.data?.thought || event.message || '思考中...'

        setBuildSteps((prev) => {
          const existing = prev.find((s) => s.id === stepId)
          const existingThought = existing?.details?.thought || ''
          const existingStreaming = existing?.streamingThought || ''

          // 如果新内容比现有内容长，说明是新的完整内容，启动流式显示
          if (newThought.length > existingThought.length || !existing) {
            // 清除旧的定时器
            const oldTimer = streamingTimersRef.current.get(stepId)
            if (oldTimer) {
              clearInterval(oldTimer)
              streamingTimersRef.current.delete(stepId)
            }

            // 初始化流式显示状态
            streamingStateRef.current.set(stepId, {
              targetText: newThought,
              currentIndex: existingStreaming.length > 0 && newThought.startsWith(existingStreaming)
                ? existingStreaming.length
                : 0
            })

            // 启动流式显示定时器
            const timer = setInterval(() => {
              const state = streamingStateRef.current.get(stepId)
              if (!state) {
                clearInterval(timer)
                streamingTimersRef.current.delete(stepId)
                return
              }

              if (state.currentIndex < state.targetText.length) {
                // 每次显示一个字符（中文按字符，英文按单词）
                let nextIndex = state.currentIndex + 1

                // 如果是中文字符，可以一次显示一个字符；如果是英文，可以一次显示一个单词
                // 为了更好的效果，我们按字符显示，但可以智能判断
                const currentChar = state.targetText[state.currentIndex]
                if (/[\u4e00-\u9fa5]/.test(currentChar)) {
                  // 中文字符，一次显示一个
                  nextIndex = state.currentIndex + 1
                } else {
                  // 非中文字符，可以一次显示更多（比如一个单词）
                  // 找到下一个空格或标点
                  const nextSpace = state.targetText.indexOf(' ', state.currentIndex)
                  const punctMatch = state.targetText.substring(state.currentIndex).match(/[，。！？；：、\n]/)
                  const nextPunct = punctMatch ? state.currentIndex + punctMatch.index! : -1
                  if (nextSpace > 0 && (nextPunct < 0 || nextSpace < nextPunct)) {
                    nextIndex = nextSpace + 1
                  } else if (nextPunct > 0) {
                    nextIndex = nextPunct + 1
                  } else {
                    nextIndex = state.currentIndex + 1
                  }
                }

                state.currentIndex = Math.min(nextIndex, state.targetText.length)

                // 更新显示内容
                setBuildSteps((prevSteps) => {
                  return prevSteps.map((step) =>
                    step.id === stepId
                      ? {
                          ...step,
                          streamingThought: state.targetText.substring(0, state.currentIndex),
                          isThinkingActive: true,
                        }
                      : step
                  )
                })
              } else {
                // 流式显示完成
                clearInterval(timer)
                streamingTimersRef.current.delete(stepId)
                streamingStateRef.current.delete(stepId)

                // 确保最终显示完整内容
                setBuildSteps((prevSteps) => {
                  return prevSteps.map((step) =>
                    step.id === stepId
                      ? {
                          ...step,
                          streamingThought: state.targetText,
                          details: {
                            ...step.details,
                            thought: state.targetText,
                          },
                        }
                      : step
                  )
                })
              }
            }, 30) // 每30ms显示一次，可以根据需要调整速度

            streamingTimersRef.current.set(stepId, timer)
          }

          // 更新步骤状态
          if (existing) {
            return prev.map((step) =>
              step.id === stepId
                ? {
                    ...step,
                    details: {
                      ...step.details,
                      thought: newThought, // 保存完整内容
                    },
                    isThinkingActive: true, // 标记思考过程为活跃状态
                    timestamp: new Date()
                  }
                : step
            )
          } else {
            // 步骤不存在，创建新步骤
            return [...prev, {
              id: stepId,
              type: 'react_thinking',
              title: stepName || '思考中',
              status: 'running',
              details: {
                thought: newThought,
              },
              streamingThought: '', // 初始为空，开始流式显示
              isThinkingActive: true,
              timestamp: new Date()
            } as BuildStep]
          }
        })
        setCurrentStepId(stepId)
        break

      case 'step_acting':
        {
          const fullActionText =
            event.message || event.data?.action || event.data?.action_description || ''
          const actionInput = event.data?.action_input || event.data?.actionInput || {}

          setBuildSteps((prev) => {
            const existing = prev.find((s) => s.id === stepId)
            const existingStreaming = existing?.streamingAction || ''

            // 如果有新的完整内容，需要开启打字机效果
            if (fullActionText && (fullActionText.length > existingStreaming.length || !existing)) {
              // 清理旧的定时器
              const oldTimer = streamingActionTimersRef.current.get(stepId)
              if (oldTimer) {
                clearInterval(oldTimer)
                streamingActionTimersRef.current.delete(stepId)
              }

              // 初始化流式显示状态
              streamingActionStateRef.current.set(stepId, {
                targetText: fullActionText,
                currentIndex:
                  existingStreaming.length > 0 && fullActionText.startsWith(existingStreaming)
                    ? existingStreaming.length
                    : 0,
              })

              // 启动打字机定时器
              const timer = setInterval(() => {
                const state = streamingActionStateRef.current.get(stepId)
                if (!state) {
                  clearInterval(timer)
                  streamingActionTimersRef.current.delete(stepId)
                  return
                }

                if (state.currentIndex < state.targetText.length) {
                  // 每次显示一个字符（中文按字符，英文按单词）
                  let nextIndex = state.currentIndex + 1

                  const currentChar = state.targetText[state.currentIndex]
                  if (/[\u4e00-\u9fa5]/.test(currentChar)) {
                    // 中文字符，一次显示一个
                    nextIndex = state.currentIndex + 1
                  } else {
                    // 非中文字符，可以一次显示更多（比如一个单词）
                    const nextSpace = state.targetText.indexOf(' ', state.currentIndex)
                    const punctMatch =
                      state.targetText.substring(state.currentIndex).match(/[，。！？；：、\n]/)
                    const nextPunct = punctMatch
                      ? state.currentIndex + (punctMatch.index as number)
                      : -1
                    if (nextSpace > 0 && (nextPunct < 0 || nextSpace < nextPunct)) {
                      nextIndex = nextSpace + 1
                    } else if (nextPunct > 0) {
                      nextIndex = nextPunct + 1
                    } else {
                      nextIndex = state.currentIndex + 1
                    }
                  }

                  state.currentIndex = Math.min(nextIndex, state.targetText.length)

                  // 更新显示内容
                  setBuildSteps((prevSteps) =>
                    prevSteps.map((step) =>
                      step.id === stepId
                        ? {
                            ...step,
                            streamingAction: state.targetText.substring(0, state.currentIndex),
                            details: {
                              ...step.details,
                              action: fullActionText,
                              actionInput,
                              _fullActionText: state.targetText,
                            },
                            status:
                              step.status === 'completed' ? step.status : ('running' as const),
                          }
                        : step
                    )
                  )
                } else {
                  // 流式显示完成
                  clearInterval(timer)
                  streamingActionTimersRef.current.delete(stepId)
                  streamingActionStateRef.current.delete(stepId)

                  // 确保最终显示完整内容
                  setBuildSteps((prevSteps) =>
                    prevSteps.map((step) =>
                      step.id === stepId
                        ? {
                            ...step,
                            streamingAction: state.targetText,
                            details: {
                              ...step.details,
                              action: fullActionText,
                              actionInput,
                              _fullActionText: state.targetText,
                            },
                          }
                        : step
                    )
                  )
                }
              }, 30) // 每30ms显示一次

              streamingActionTimersRef.current.set(stepId, timer as unknown as number)
            }

            // 确保步骤存在并更新基础信息
            if (existing) {
              return prev.map((step) =>
                step.id === stepId
                  ? {
                      ...step,
                      status: step.status === 'completed' ? step.status : ('running' as const),
                      details: {
                        ...step.details,
                        action: fullActionText,
                        actionInput,
                        _fullActionText: fullActionText || step.details?._fullActionText,
                      },
                    }
                  : step
              )
            }

            // 步骤不存在时创建新步骤
            return [
              ...prev,
              {
                id: stepId,
                type: getStepTypeFromStepType(event.step_type || ''),
                title: stepName || '执行中',
                status: 'running',
                details: {
                  action: fullActionText,
                  actionInput,
                  _fullActionText: fullActionText,
                },
                streamingAction: '',
                timestamp: new Date(),
              } as BuildStep,
            ]
          })
        }
        break

      case 'step_observing':
        {
          const fullObservationText =
            event.message || event.data?.observation || '观察结果...'

          setBuildSteps((prev) => {
            const existing = prev.find((s) => s.id === stepId)
            const existingStreaming = existing?.streamingObservation || ''

            // 如果有新的完整内容，需要开启打字机效果
            if (
              fullObservationText &&
              (fullObservationText.length > existingStreaming.length || !existing)
            ) {
              const oldTimer = streamingObservationTimersRef.current.get(stepId)
              if (oldTimer) {
                clearInterval(oldTimer)
                streamingObservationTimersRef.current.delete(stepId)
              }

              streamingObservationStateRef.current.set(stepId, {
                targetText: fullObservationText,
                currentIndex:
                  existingStreaming.length > 0 &&
                  fullObservationText.startsWith(existingStreaming)
                    ? existingStreaming.length
                    : 0,
              })

              const timer = setInterval(() => {
                const state = streamingObservationStateRef.current.get(stepId)
                if (!state) {
                  clearInterval(timer)
                  streamingObservationTimersRef.current.delete(stepId)
                  return
                }

                if (state.currentIndex < state.targetText.length) {
                  let nextIndex = state.currentIndex + 1

                  const currentChar = state.targetText[state.currentIndex]
                  if (/[\u4e00-\u9fa5]/.test(currentChar)) {
                    nextIndex = state.currentIndex + 1
                  } else {
                    const nextSpace = state.targetText.indexOf(' ', state.currentIndex)
                    const punctMatch =
                      state.targetText.substring(state.currentIndex).match(/[，。！？；：、\n]/)
                    const nextPunct = punctMatch
                      ? state.currentIndex + (punctMatch.index as number)
                      : -1
                    if (nextSpace > 0 && (nextPunct < 0 || nextSpace < nextPunct)) {
                      nextIndex = nextSpace + 1
                    } else if (nextPunct > 0) {
                      nextIndex = nextPunct + 1
                    } else {
                      nextIndex = state.currentIndex + 1
                    }
                  }

                  state.currentIndex = Math.min(nextIndex, state.targetText.length)

                  setBuildSteps((prevSteps) =>
                    prevSteps.map((step) =>
                      step.id === stepId
                        ? {
                            ...step,
                            streamingObservation: state.targetText.substring(
                              0,
                              state.currentIndex
                            ),
                            details: {
                              ...step.details,
                              observation: fullObservationText,
                              _fullObservationText: state.targetText,
                            },
                            status:
                              step.status === 'completed' ? step.status : ('running' as const),
                          }
                        : step
                    )
                  )
                } else {
                  clearInterval(timer)
                  streamingObservationTimersRef.current.delete(stepId)
                  streamingObservationStateRef.current.delete(stepId)

                  setBuildSteps((prevSteps) =>
                    prevSteps.map((step) =>
                      step.id === stepId
                        ? {
                            ...step,
                            streamingObservation: state.targetText,
                            details: {
                              ...step.details,
                              observation: fullObservationText,
                              _fullObservationText: state.targetText,
                            },
                          }
                        : step
                    )
                  )
                }
              }, 30)

              streamingObservationTimersRef.current.set(stepId, timer as unknown as number)
            }

            // 确保步骤存在并更新基础信息
            if (existing) {
              return prev.map((step) =>
                step.id === stepId
                  ? {
                      ...step,
                      status: step.status === 'completed' ? step.status : ('running' as const),
                      details: {
                        ...step.details,
                        observation: fullObservationText,
                        _fullObservationText:
                          fullObservationText || step.details?._fullObservationText,
                      },
                    }
                  : step
              )
            }

            // 步骤不存在时创建新步骤
            return [
              ...prev,
              {
                id: stepId,
                type: getStepTypeFromStepType(event.step_type || ''),
                title: stepName || '观察中',
                status: 'running',
                details: {
                  observation: fullObservationText,
                  _fullObservationText: fullObservationText,
                },
                streamingObservation: '',
                timestamp: new Date(),
              } as BuildStep,
            ]
          })
        }
        break

      case 'step_completed':
        const result = event.data?.result || {}
        const fileContent = result.file_content || ''
        // ✅ 修改流程：确保使用唯一的 step_id
        const modifySessionIdStepCompleted = (window as any).currentModifySessionId
        const uniqueStepIdCompleted = isModifying && modifySessionIdStepCompleted && !stepId.startsWith(modifySessionIdStepCompleted)
          ? `${modifySessionIdStepCompleted}_${stepId}`
          : stepId
        
        // 构造执行结果的流式文本 - 格式化为 JSON 格式
        let resultText = ''
        if (Object.keys(result).length > 0) {
          // 将 result 对象格式化为 JSON 字符串
          try {
            const formattedResult = JSON.stringify(result, null, 2)
            resultText = `📊执行结果：\n${formattedResult}`
          } catch (e) {
            // 如果 JSON 序列化失败，使用备用格式
            resultText = `📊执行结果：\n${JSON.stringify(result)}`
          }
        } else if (event.message) {
          resultText = `📊执行结果：\n${event.message}`
        } else if (typeof result === 'string' && result) {
          resultText = `📊执行结果：\n${result}`
        } else {
          resultText = '📊执行结果：\n✅ 步骤完成'
        }
        
        // 先立即添加文件到右侧，确保文件生成和步骤完成时间一致
        if (result.file_name && fileContent) {
          const file: FileTreeItem = {
            name: result.file_name,
            path: result.file_name,
            type: 'file',
            content: fileContent,
          }
          setGeneratedFiles((prev) => {
            const existing = prev.find((f) => f.path === file.path)
            if (existing) {
              return prev.map((f) => (f.path === file.path ? file : f))
            }
            return [...prev, file]
          })

          // ✅ 移除立即跳转逻辑，等到 build_completed 时再跳转
          // 这样可以等所有代码生成、测试、修复完成后再跳转到流程图
        }

        // 更新步骤的详细信息，包括执行结果和生成的代码
        // updateStep 内部会自动合并 details，保留已有的思考内容
        setBuildSteps((prev) => {
          const existing = prev.find((s) => s.id === uniqueStepIdCompleted)
          const existingStreamingResult = existing?.streamingResult || ''

          // 如果新内容比现有内容长，说明是新的完整内容，启动流式显示
          if (resultText.length > existingStreamingResult.length || !existing) {
            // 清除旧的定时器
            const oldTimer = streamingResultTimersRef.current.get(uniqueStepIdCompleted)
            if (oldTimer) {
              clearInterval(oldTimer)
              streamingResultTimersRef.current.delete(uniqueStepIdCompleted)
            }

            // 初始化流式显示状态
            streamingResultStateRef.current.set(uniqueStepIdCompleted, {
              targetText: resultText,
              currentIndex: existingStreamingResult.length > 0 && resultText.startsWith(existingStreamingResult)
                ? existingStreamingResult.length
                : 0
            })

            // 启动流式显示定时器
            const timer = setInterval(() => {
              const state = streamingResultStateRef.current.get(uniqueStepIdCompleted)
              if (!state) {
                clearInterval(timer)
                streamingResultTimersRef.current.delete(uniqueStepIdCompleted)
                return
              }

              if (state.currentIndex < state.targetText.length) {
                // 每次显示一个字符（中文按字符，英文按单词）
                let nextIndex = state.currentIndex + 1

                // 如果是中文字符，可以一次显示一个字符；如果是英文，可以一次显示一个单词
                const currentChar = state.targetText[state.currentIndex]
                if (/[\u4e00-\u9fa5]/.test(currentChar)) {
                  // 中文字符，一次显示一个
                  nextIndex = state.currentIndex + 1
                } else {
                  // 非中文字符，可以一次显示更多（比如一个单词）
                  // 找到下一个空格或标点
                  const nextSpace = state.targetText.indexOf(' ', state.currentIndex)
                  const punctMatch = state.targetText.substring(state.currentIndex).match(/[，。！？；：、\n]/)
                  const nextPunct = punctMatch ? state.currentIndex + punctMatch.index! : -1
                  if (nextSpace > 0 && (nextPunct < 0 || nextSpace < nextPunct)) {
                    nextIndex = nextSpace + 1
                  } else if (nextPunct > 0) {
                    nextIndex = nextPunct + 1
                  } else {
                    nextIndex = state.currentIndex + 1
                  }
                }

                state.currentIndex = Math.min(nextIndex, state.targetText.length)

                // 更新显示内容
                setBuildSteps((prevSteps) => {
                  return prevSteps.map((step) =>
                    step.id === uniqueStepIdCompleted
                      ? {
                          ...step,
                          streamingResult: state.targetText.substring(0, state.currentIndex),
                          details: {
                            ...step.details,
                            _fullResultText: state.targetText, // 保存完整文本用于比较
                          },
                        }
                      : step
                  )
                })
              } else {
                // 流式显示完成
                clearInterval(timer)
                streamingResultTimersRef.current.delete(uniqueStepIdCompleted)
                streamingResultStateRef.current.delete(uniqueStepIdCompleted)

                // 确保最终显示完整内容
                setBuildSteps((prevSteps) => {
                  return prevSteps.map((step) =>
                    step.id === uniqueStepIdCompleted
                      ? {
                          ...step,
                          streamingResult: state.targetText,
                          details: {
                            ...step.details,
                            _fullResultText: state.targetText,
                          },
                        }
                      : step
                  )
                })
              }
            }, 30) // 每30ms显示一次，可以根据需要调整速度

            streamingResultTimersRef.current.set(uniqueStepIdCompleted, timer)
          }

          // 更新步骤状态为 completed（文件已经在上方添加）
          return prev.map((step) =>
            step.id === uniqueStepIdCompleted
              ? {
                  ...step,
                  status: 'completed',
                  description: event.message || '步骤完成',
                  details: {
                    ...step.details,
                    result: result,
                    code: fileContent, // 保存生成的代码
                    file_name: result.file_name,
                  },
                  isThinkingActive: false, // 停止活跃思考展示，思考内容将移到卡片内部
                  timestamp: new Date()
                }
              : step
          )
        })

        // 注意：文件添加逻辑已移至流式输出完成的回调中，确保执行结果流式输出完毕后再生成代码文件
        break

      case 'step_failed':
        // ✅ 修改流程：确保使用唯一的 step_id
        const modifySessionIdStepFailed = (window as any).currentModifySessionId
        const uniqueStepIdFailed = isModifying && modifySessionIdStepFailed && !stepId.startsWith(modifySessionIdStepFailed)
          ? `${modifySessionIdStepFailed}_${stepId}`
          : stepId
        updateStep(uniqueStepIdFailed, {
          status: 'error',
          description: event.message || '步骤失败',
          details: {
            error: event.data?.error || event.message,
          },
        })
        break

      case 'test_started':
        console.log(`🧪 [test_started] 收到测试开始事件`, event)
        
        // ✅ 修改流程：使用唯一的 step_id，避免覆盖已有步骤
        const modifySessionIdTest = (window as any).currentModifySessionId
        let testStepId = isModifying && modifySessionIdTest 
          ? `${modifySessionIdTest}_test` 
          : (event.step_id || 'test')
        
        // ✅ 如果当前在迭代中，给测试步骤加上迭代前缀（使用 ref 确保获取最新值）
        if (currentIterationRef.current > 0) {
          const iterationPrefix = isModifying && modifySessionIdTest
            ? `${modifySessionIdTest}_iteration_${currentIterationRef.current}`
            : `iteration_${currentIterationRef.current}`
          
          if (!testStepId.includes(`iteration_${currentIterationRef.current}`)) {
            testStepId = `${iterationPrefix}_${testStepId}`
            console.log(`✅ [test_started] 为迭代中的测试步骤添加前缀: ${testStepId}, 迭代: ${currentIterationRef.current}`)
          }
        }
        
        const testStepName = event.step_name || (isModifying ? '测试修改后的工作流' : '测试阶段')
        console.log(`✅ [test_started] 创建测试步骤: ${testStepId}, 名称: ${testStepName}, 迭代: ${currentIterationRef.current}`)
        
        // 立即创建测试步骤
        updateStep(testStepId, {
          type: 'testing',
          title: testStepName,
          description: event.message || '开始测试生成的代码...',
          status: 'running',
        })
        
        console.log(`✅ [test_started] 测试步骤已创建并添加到界面`)
        break

      case 'test_completed':
        const testResult = event.data?.test_result || {}
        const modifySessionIdTestCompleted = (window as any).currentModifySessionId
        let completedTestStepId = isModifying && modifySessionIdTestCompleted
          ? `${modifySessionIdTestCompleted}_test`
          : (event.step_id || 'test')
        
        // ✅ 如果当前在迭代中，给测试步骤加上迭代前缀（与 test_started 保持一致，使用 ref）
        if (currentIterationRef.current > 0) {
          const iterationPrefix = isModifying && modifySessionIdTestCompleted
            ? `${modifySessionIdTestCompleted}_iteration_${currentIterationRef.current}`
            : `iteration_${currentIterationRef.current}`
          
          if (!completedTestStepId.includes(`iteration_${currentIterationRef.current}`)) {
            completedTestStepId = `${iterationPrefix}_${completedTestStepId}`
            console.log(`✅ [test_completed] 为迭代中的测试步骤添加前缀: ${completedTestStepId}, 迭代: ${currentIterationRef.current}`)
          }
        }
        
        const completedTestStepName = event.step_name || (isModifying ? '测试修改后的工作流' : '测试阶段')
        console.log(`✅ [test_completed] 更新测试步骤: ${completedTestStepId}, 成功: ${testResult.success}, 迭代: ${currentIterationRef.current}`)
        
        // updateStep 内部会自动合并 details，保留已有的思考内容
        updateStep(completedTestStepId, {
          status: 'completed',
          title: completedTestStepName,
          description: event.message || '测试通过！',
          details: {
            testResult: testResult,
          },
          isThinkingActive: false, // 停止活跃思考展示
        })
        
        // ✅ 测试完成后，如果测试失败，不重置迭代编号（后续会进入迭代修复）
        // 如果测试成功，重置迭代编号（同时更新 state 和 ref）
        if (testResult.success) {
          setCurrentIteration(0)
          currentIterationRef.current = 0
          console.log(`✅ [test_completed] 测试成功，重置迭代编号`)
        }
        break

      case 'test_failed':
        const failedTestResult = event.data?.test_result || {}
        const modifySessionIdTestFailed = (window as any).currentModifySessionId
        let failedTestStepId = isModifying && modifySessionIdTestFailed
          ? `${modifySessionIdTestFailed}_test`
          : (event.step_id || 'test')
        
        // ✅ 如果当前在迭代中，给测试步骤加上迭代前缀（与 test_started 保持一致，使用 ref）
        if (currentIterationRef.current > 0) {
          const iterationPrefix = isModifying && modifySessionIdTestFailed
            ? `${modifySessionIdTestFailed}_iteration_${currentIterationRef.current}`
            : `iteration_${currentIterationRef.current}`
          
          if (!failedTestStepId.includes(`iteration_${currentIterationRef.current}`)) {
            failedTestStepId = `${iterationPrefix}_${failedTestStepId}`
            console.log(`✅ [test_failed] 为迭代中的测试步骤添加前缀: ${failedTestStepId}, 迭代: ${currentIterationRef.current}`)
          }
        }
        
        const failedTestStepName = event.step_name || (isModifying ? '测试修改后的工作流' : '测试阶段')
        console.log(`✅ [test_failed] 更新测试步骤: ${failedTestStepId}, 迭代: ${currentIterationRef.current}`)
        
        updateStep(failedTestStepId, {
          status: 'error',
          title: failedTestStepName,
          description: event.message || '测试失败',
          details: {
            testResult: failedTestResult,
            error: failedTestResult.error || event.message,
          },
        })
        break

      case 'iteration_started':
        // ✅ 修复：确保每个迭代都有唯一的步骤ID，避免覆盖之前的步骤
        const modifySessionIdIter = (window as any).currentModifySessionId
        const iterationNum = event.data?.iteration || 1
        
        // 设置当前迭代编号，后续的所有步骤都会使用这个编号作为前缀
        // 同时更新 state 和 ref，确保立即生效
        setCurrentIteration(iterationNum)
        currentIterationRef.current = iterationNum
        console.log(`✅ [iteration_started] 设置当前迭代编号: ${iterationNum}`)
        
        // 生成唯一的迭代步骤ID，不依赖后端发送的 step_id
        // 格式：修改流程为 "{modifySessionId}_iteration_{num}"，正常流程为 "iteration_{num}"
        const iterationStepId = isModifying && modifySessionIdIter
          ? `${modifySessionIdIter}_iteration_${iterationNum}`
          : `iteration_${iterationNum}`
        
        console.log(`✅ [iteration_started] 创建迭代步骤: ${iterationStepId}, 迭代次数: ${iterationNum}, 修改会话: ${modifySessionIdIter || '无'}`)
        
        updateStep(iterationStepId, {
          type: 'optimizing',
          title: isModifying ? `修复迭代 ${iterationNum}` : `迭代改进 ${iterationNum}`,
          description: isModifying ? '根据测试结果修复错误...' : '根据测试结果进行改进...',
          status: 'running',
        })
        break

      case 'iteration_completed':
        // ✅ 修复：使用与 iteration_started 相同的逻辑生成步骤ID
        const modifySessionIdIterCompleted = (window as any).currentModifySessionId
        const iterationNumCompleted = event.data?.iteration || 1
        
        // 确保使用相同的步骤ID生成逻辑
        const iterationStepIdCompleted = isModifying && modifySessionIdIterCompleted
          ? `${modifySessionIdIterCompleted}_iteration_${iterationNumCompleted}`
          : `iteration_${iterationNumCompleted}`
        
        console.log(`✅ [iteration_completed] 更新迭代步骤: ${iterationStepIdCompleted}, 迭代次数: ${iterationNumCompleted}, 成功: ${event.data?.test_result?.success}`)
        
        updateStep(iterationStepIdCompleted, {
          status: event.data?.test_result?.success ? 'completed' : 'error',
          description: event.message || '迭代完成',
          details: {
            testResult: event.data?.test_result,
          },
        })
        break

      case 'build_completed':
        // 根据三种模式动态设置“构建完成”文案
        const modeLabel =
          agentMode === 'agent' ? '智能助手' : agentMode === 'multi_agent' ? '多智能体系统' : '工作流'
        updateStep('completed', {
          type: 'completed',
          title: '构建完成',
          description: `${modeLabel}构建成功！`,
          status: 'completed',
        })
        setCurrentStepId(undefined)
        // ✅ 构建完成，重置迭代编号（同时更新 state 和 ref）
        setCurrentIteration(0)
        currentIterationRef.current = 0
        console.log(`✅ [build_completed] 构建完成，重置迭代编号`)
        
        // 更新生成的文件
        if (event.data?.generated_files) {
          const files: FileTreeItem[] = Object.entries(event.data.generated_files).map(([name, content]) => ({
            name,
            path: name,
            type: 'file',
            content: content as string,
          }))
          setGeneratedFiles(files)
          
          // ✅ 构建完成后，如果是 workflow 模式且有 workflow_builder.py，自动跳转到流程图
          // 在文件更新后立即检查并跳转
          if (agentMode === 'workflow' && event.data.generated_files['workflow_builder.py']) {
            console.log(`✅ [build_completed] 检测到 workflow_builder.py，准备跳转到流程图`)
            // 延迟跳转，确保文件已更新到状态中并渲染完成
            setTimeout(() => {
              console.log(`✅ [build_completed] 跳转到流程图标签页`)
              setActiveCodeTab('diagram')
            }, 300)
          }
        }
        // 保存工作流目录路径
        if (event.data?.saved_directory) {
          setSavedDirectory(event.data.saved_directory)
          // 将目录路径存储到全局，供 CodeDirectory 组件使用
          ;(window as any).workflowDirectory = event.data.saved_directory
        }
        // 保存工作流描述
        if (event.data?.plan?.workflow_description) {
          setWorkflowDescription(event.data.plan.workflow_description)
        }
        break

      case 'build_failed':
        updateStep('failed', {
          type: 'completed',
          title: '构建失败',
          description: event.message || '构建失败',
          status: 'error',
        })
        setError(event.data)
        // ✅ 构建失败，重置迭代编号（同时更新 state 和 ref）
        setCurrentIteration(0)
        currentIterationRef.current = 0
        console.log(`✅ [build_failed] 构建失败，重置迭代编号`)
        break
    }
  }

  const handleDownload = () => {
    // TODO: 实现下载功能
    message.info('下载功能开发中...')
  }

  const handleExecute = async () => {
    if (!workflowId) {
      message.warning('请先生成工作流')
      return
    }
    // TODO: 实现执行功能
    message.info('执行功能开发中...')
  }

  const handleModify = async (modificationRequest: string) => {
    if (!savedDirectory || !originalUserInput) {
      message.warning('工作流尚未生成完成，无法修改')
      return
    }

    setIsBuilding(true)
    setError(null)
    setIsModifying(true)  // 标记为修改流程

    // 不重置步骤，而是在现有步骤后面追加修改步骤
    // 添加一个分隔步骤，表示开始修改
    const modifySessionId = `modify_${Date.now()}`  // 为本次修改创建唯一会话ID
    const separatorStepId = `${modifySessionId}_separator`
    updateStep(separatorStepId, {
      type: 'optimizing',
      title: '━━━ 开始修改工作流 ━━━',
      description: `修改请求: ${modificationRequest}`,
      status: 'completed',
    })
    
    // 存储修改会话ID，用于后续步骤的step_id生成
    ;(window as any).currentModifySessionId = modifySessionId

    try {
      // 使用增量构建API的modify端点
      const eventStream = incrementalBuildAPI.modify(
        {
          workflow_dir: savedDirectory,
          modification_request: modificationRequest,
          original_user_input: originalUserInput,
          workflow_description: workflowDescription,
        },
        (event: any) => {
          handleBuildEvent(event)
        }
      )

      // 处理事件流
      for await (const event of eventStream) {
        handleBuildEvent(event)
      }

      message.success(
        agentMode === 'agent' 
          ? 'Agent 修改完成！' 
          : agentMode === 'multi_agent'
          ? 'Multi-Agent 系统修改完成！'
          : '工作流修改完成！'
      )
      // 清理修改会话ID
      delete (window as any).currentModifySessionId
      setIsModifying(false)
    } catch (error: any) {
      console.error('修改工作流失败:', error)
      setError(error)
      // 清理修改会话ID
      delete (window as any).currentModifySessionId
      setIsModifying(false)
      message.error({
        content: `修改失败: ${error?.message || '未知错误'}`,
        duration: 8,
      })
      updateStep(separatorStepId, {
        status: 'error',
        description: `修改失败: ${error?.message || '未知错误'}`,
      })
    } finally {
      setIsBuilding(false)
    }
  }

  const handleClearHistory = async () => {
    if (!savedDirectory || !conversationId) {
      return
    }
    
    try {
      await incrementalBuildAPI.clearHistory({
        workflow_dir: savedDirectory,
        conversation_id: conversationId,
      })
      
      // 重置会话ID，下次对话会创建新的会话
      setConversationId(undefined)
      message.success('对话历史已清除')
    } catch (error: any) {
      console.error('清除历史失败:', error)
      message.error(`清除历史失败: ${error?.message || '未知错误'}`)
    }
  }

  const handleChatSend = async (message: string): Promise<string> => {
    if (!savedDirectory) {
      return '工作流尚未生成完成，请等待生成完成后再测试。'
    }
    
    if (isWaitingInteraction) {
      return '请先回复上一个交互请求。'
    }
    
    try {
      // 如果没有 conversation_id，生成一个新的
      let currentConvId = conversationId
      if (!currentConvId) {
        currentConvId = `conv_${Date.now()}`
        setConversationId(currentConvId)
      }
      
      // 使用SSE流式响应
      let finalContent = ''
      let hasError = false
      let errorMessage = ''
      
      const eventStream = incrementalBuildAPI.execute(
        {
          workflow_dir: savedDirectory,
          query: message,
          conversation_id: currentConvId,
        },
        (event) => {
          // 实时处理事件
          if (event.type === 'interaction_required') {
            // 检测到交互请求
            setInteractionRequest(event)
            setIsWaitingInteraction(true)
          } else if (event.type === 'execution_completed') {
            // 执行完成
            finalContent = event.content || '执行成功，但未返回输出内容。'
            setIsWaitingInteraction(false)
            setInteractionRequest(null)
            // 更新conversation_id（如果后端返回了新的）
            if (event.conversation_id && event.conversation_id !== currentConvId) {
              setConversationId(event.conversation_id)
            }
          } else if (event.type === 'error') {
            // 执行错误
            hasError = true
            errorMessage = event.error || event.message || '未知错误'
            setIsWaitingInteraction(false)
            setInteractionRequest(null)
          }
        }
      )
      
      // 处理事件流
      for await (const event of eventStream) {
        if (event.type === 'interaction_required') {
          // 检测到交互请求，等待用户回复
          setInteractionRequest(event)
          setIsWaitingInteraction(true)
          // 更新conversation_id（如果后端返回了新的）
          if (event.conversation_id && event.conversation_id !== currentConvId) {
            setConversationId(event.conversation_id)
          }
          // 不返回消息，让WorkflowChat显示交互卡片
          return ''
        } else if (event.type === 'execution_completed') {
          finalContent = event.content || '执行成功，但未返回输出内容。'
          setIsWaitingInteraction(false)
          setInteractionRequest(null)
          // 更新conversation_id（如果后端返回了新的）
          if (event.conversation_id && event.conversation_id !== currentConvId) {
            setConversationId(event.conversation_id)
          }
          break
        } else if (event.type === 'error') {
          hasError = true
          errorMessage = event.error || event.message || '未知错误'
          setIsWaitingInteraction(false)
          setInteractionRequest(null)
          break
        }
      }
      
      if (hasError) {
        return `执行失败: ${errorMessage}`
      }
      
      return finalContent || '执行成功，但未返回输出内容。'
    } catch (error: any) {
      console.error('执行工作流失败:', error)
      setIsWaitingInteraction(false)
      setInteractionRequest(null)
      return `执行失败: ${error?.message || '未知错误'}`
    }
  }

  // 处理交互回复
  const handleInteractionReply = async (interaction: any): Promise<string> => {
    if (!interaction || !interaction.reply) {
      return '无效的交互回复'
    }
    
    try {
      setIsWaitingInteraction(false)
      let finalContent = ''
      let hasError = false
      let errorMessage = ''
      
      const eventStream = incrementalBuildAPI.continue(
        {
          execution_id: interaction.execution_id,
          reply_value: interaction.reply,
          component_id: interaction.component_id,
        },
        (event) => {
          // 实时处理事件
          if (event.type === 'interaction_required') {
            // 还有更多交互请求
            setInteractionRequest(event)
            setIsWaitingInteraction(true)
          } else if (event.type === 'execution_completed') {
            // 执行完成
            finalContent = event.content || '执行成功，但未返回输出内容。'
            setIsWaitingInteraction(false)
            setInteractionRequest(null)
          } else if (event.type === 'error') {
            // 执行错误
            hasError = true
            errorMessage = event.error || event.message || '未知错误'
            setIsWaitingInteraction(false)
            setInteractionRequest(null)
          }
        }
      )
      
      // 处理事件流
      for await (const event of eventStream) {
        if (event.type === 'interaction_required') {
          setInteractionRequest(event)
          setIsWaitingInteraction(true)
          // 不返回消息，让WorkflowChat显示交互卡片
          return ''
        } else if (event.type === 'execution_completed') {
          finalContent = event.content || '执行成功，但未返回输出内容。'
          setIsWaitingInteraction(false)
          setInteractionRequest(null)
          break
        } else if (event.type === 'error') {
          hasError = true
          errorMessage = event.error || event.message || '未知错误'
          setIsWaitingInteraction(false)
          setInteractionRequest(null)
          break
        }
      }
      
      return hasError ? `执行失败: ${errorMessage}` : (finalContent || '执行成功')
    } catch (error: any) {
      console.error('继续执行失败:', error)
      setIsWaitingInteraction(false)
      setInteractionRequest(null)
      return `继续执行失败: ${error?.message || '未知错误'}`
    }
  }

  // 如果还没有开始构建，显示输入界面
  if (!isBuilding && buildSteps.length === 0) {
    return (
      <div
        style={{
          height: 'calc(100vh - 64px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        }}
      >
        <Card
          style={{
            width: '800px',
            maxWidth: '90%',
            boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
          }}
        >
          <div style={{ textAlign: 'center', marginBottom: '32px' }}>
            <Title level={2} style={{ marginBottom: '16px', color: '#1f1f1f' }}>
              Vibe Agent
            </Title>
            <Typography.Text type="secondary" style={{ fontSize: '16px', color: '#666' }}>
              用自然语言描述您的需求，将自动为您生成基于{' '}
              <span
                style={{
                  fontSize: '16px',
                  fontWeight: 600,
                  fontFamily: "'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace",
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundClip: 'text',
                  position: 'relative',
                  display: 'inline-block',
                  padding: '0 4px',
                }}
              >
                openJiuwen
                <span
                  style={{
                    position: 'absolute',
                    bottom: '0',
                    left: '4px',
                    right: '4px',
                    height: '2px',
                    background: 'linear-gradient(90deg, rgba(102, 126, 234, 0.4) 0%, rgba(118, 75, 162, 0.4) 100%)',
                    borderRadius: '1px',
                  }}
                />
              </span>
              {' '}框架的{agentMode === 'agent' ? '智能助手' : agentMode === 'multi_agent' ? '多智能体系统' : '工作流'}
            </Typography.Text>
          </div>
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            {/* Agent 模式选择器 */}
            <AgentModeSelector
              value={agentMode}
              onChange={setAgentMode}
              disabled={isBuilding}
            />
            <Input.TextArea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={
                agentMode === 'agent' 
                  ? '请描述您想要创建的智能助手，例如：创建一个情感咨询助手，能够倾听用户的情感问题并提供专业的心理建议...'
                  : agentMode === 'multi_agent'
                  ? '请描述您想要创建的多智能体系统，例如：创建一个内容创作系统，包含选题、写作、校对、排版等多个智能体协同工作...'
                  : '请描述您想要创建的工作流，例如：创建一个音乐推荐工作流，根据用户喜好和历史听歌记录进行搜索、分析并推荐音乐...'
              }
              rows={6}
              style={{ fontSize: '16px' }}
              onPressEnter={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  if (query.trim()) {
                    handleGenerate()
                  }
                }
              }}
            />
            <div style={{ textAlign: 'right' }}>
              <Button
                type="primary"
                size="large"
                onClick={handleGenerate}
                disabled={!query.trim()}
                loading={isBuilding}
                style={{ minWidth: '120px' }}
              >
                {agentMode === 'agent' ? '生成 Agent' : agentMode === 'multi_agent' ? '生成 Multi-Agent' : '生成工作流'}
              </Button>
            </div>
          </Space>
        </Card>
      </div>
    )
  }

  // 构建中或构建完成，显示三栏布局
  return (
    <Content style={{ height: 'calc(100vh - 64px)', padding: 0, background: '#f5f5f5' }}>
      <Layout style={{ height: '100%', background: '#f5f5f5' }}>
        {/* 左侧：构建过程 */}
        <Layout.Sider
          width={384}
          style={{
            background: '#fff',
            borderRight: '1px solid #e8e8e8',
            overflow: 'hidden',
            boxShadow: '2px 0 8px rgba(0,0,0,0.05)',
          }}
        >
          <BuildProcess 
            steps={buildSteps} 
            currentStep={currentStepId}
            onModify={handleModify}
            canModify={!isBuilding && !!savedDirectory}
            agentMode={agentMode}
          />
        </Layout.Sider>

        {/* 中间：代码目录/流程图 */}
        <Layout.Content
          style={{
            margin: '16px',
            background: '#fff',
            borderRadius: '8px',
            overflow: 'hidden',
            boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
            display: 'flex',
            flexDirection: 'column',
            minHeight: 0,
            flex: 1,
          }}
        >
          {error && (
            <div style={{ padding: '16px' }}>
              <ErrorDisplay error={error} title="生成失败" />
            </div>
          )}
          <div style={{ flex: 1, overflow: 'hidden', minHeight: 0, display: 'flex', flexDirection: 'column' }}>
            {isBuilding || generatedFiles.length > 0 ? (
              <CodeDirectory 
                files={generatedFiles} 
                workflow={workflow}
                workflowDirectory={savedDirectory}
                agentMode={agentMode}
                defaultActiveTab={activeCodeTab}
                onTabChange={setActiveCodeTab}
                isBuildCompleted={!isBuilding && generatedFiles.length > 0 && !!savedDirectory}
                onTestRun={() => setShowChatPanel(true)}
              />
            ) : (
              <div
                style={{
                  height: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#999',
                  flexDirection: 'column',
                  gap: '16px',
                }}
              >
                <Spin size="large" />
                <Typography.Text type="secondary">等待生成代码...</Typography.Text>
              </div>
            )}
          </div>
        </Layout.Content>

        {/* 右侧：对话界面 - 默认隐藏，点击试运行后显示 */}
        {showChatPanel && (
        <Layout.Sider
          width={340}
          style={{
            background: '#fff',
            borderLeft: '1px solid rgba(148,163,184,0.4)',
            overflow: 'hidden',
            boxShadow: '-4px 0 12px rgba(15,23,42,0.06)',
          }}
        >
          <div
            style={{
              padding: '16px',
              borderBottom: '2px solid transparent',
              borderImage: 'linear-gradient(to right, #667eea, #764ba2) 1',
              background: 'linear-gradient(to right, rgba(102,126,234,0.06), rgba(118,75,162,0.06))',
            }}
          >
            <Title
              level={5}
              style={{
                margin: 0,
                fontSize: 16,
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <span role="img" aria-label="chat">
                💬
              </span>
              {agentMode === 'agent' ? 'Agent 对话' : agentMode === 'multi_agent' ? 'Multi-Agent 对话' : '工作流对话'}
            </Title>
            {workflowId && (
              <Typography.Text type="secondary" style={{ fontSize: '12px' }}>
                工作流ID: {workflowId.slice(0, 8)}...
              </Typography.Text>
            )}
          </div>
          <WorkflowChat 
            workflowId={workflowId} 
            onSendMessage={handleChatSend}
            onClear={handleClearHistory}
            disabled={!savedDirectory}
            onInteraction={handleInteractionReply}
            interactionRequest={interactionRequest}
            agentMode={agentMode}
          />
          </Layout.Sider>
        )}
      </Layout>

      {/* 顶部操作栏 */}
      {!isBuilding && workflow && (
        <div
          style={{
            position: 'fixed',
            top: '80px',
            right: '16px',
            zIndex: 100,
            background: '#fff',
            padding: '8px',
            borderRadius: '4px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
          }}
        >
          <Space>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={handleExecute}
            >
              执行工作流
            </Button>
            <Button icon={<DownloadOutlined />} onClick={handleDownload}>
              下载代码
            </Button>
          </Space>
        </div>
      )}
    </Content>
  )
}

export default WorkflowBuilderIncremental

