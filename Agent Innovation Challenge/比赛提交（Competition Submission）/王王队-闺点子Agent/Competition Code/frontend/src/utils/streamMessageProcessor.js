/**
 * 流式消息处理器
 * 处理 deepsearch 系统的流式输出，按代理类型整合和显示
 */

export class StreamMessageProcessor {
  constructor() {
    this.messages = new Map(); // message_id -> message data
    this.planSteps = []; // 存储从 planner 解析出的 steps
    this.collectorTasks = new Map(); // message_id -> task info (用于追踪并发的收集任务)
    this.stepsWithAgents = new Map(); // step_title -> {step info + agents}
    this.agentConfigs = {
      'image_intent_recognition': {
        label: '🖼️ 闺点子看图中',
        color: '#ec4899',
        bgColor: '#fdf2f8',
        showRaw: true
      },
      'entry': {
        label: '📌 闺点子分析',
        color: '#db2777',
        bgColor: '#fff1f2',
        showRaw: false
      },
      'feedback_search_way': {
        label: '🧭 选择搜索方式',
        color: '#db2777',
        bgColor: '#fff1f2',
        showRaw: false
      },
      'planner': {
        label: '📋 闺点子计划',
        color: '#ec4899',
        bgColor: '#fdf2f8',
        showRaw: true
      },
      'tool_select': {
        label: '🔎 挑选宝贝工具',
        color: '#f472b6',
        bgColor: '#fff1f2',
        showRaw: false
      },
      'search': {
        label: '🌐 全网搜寻',
        color: '#ec4899',
        bgColor: '#fdf2f8',
        showRaw: false
      },
      'query_rewrite': {
        label: '✍️ 润色思路',
        color: '#db2777',
        bgColor: '#fff1f2',
        showRaw: false
      },
      'answerability': {
        label: '🔍 过滤杂质',
        color: '#db2777',
        bgColor: '#fff1f2',
        showRaw: false
      },
      'summarize_findings': {
        label: '📊 汇总发现',
        color: '#ec4899',
        bgColor: '#fdf2f8',
        showRaw: false
      },
      'answer': {
        label: '💡 闺点子支招',
        color: '#db2777',
        bgColor: '#fff1f2',
        showRaw: false
      },
      'show_image': {
        label: '🖼️ 闺点子show图',
        color: '#ec4899',
        bgColor: '#fdf2f8',
        showRaw: false
      }
    };
  }

  /**
   * 处理接收到的消息chunk
   * @param {Object} chunk - 从后端接收到的消息chunk
   * @returns {Object|null} 返回处理后的消息对象，如果不应该显示则返回null
   */
  processChunk(chunk) {
    const isValid = this.isValidMessageChunk(chunk);
    if (!isValid) {
      console.log('❌ StreamProcessor 验证失败:', {
        has_message_id: !!chunk?.message_id,
        has_agent: !!chunk?.agent,
        message_type: chunk?.message_type,
        event: chunk?.event
      });
      return null;
    }

    const { message_id, agent, content, event, created_time, step_title } = chunk;
    const react_index = chunk.react_index !== undefined ? chunk.react_index : null;


    // 初始化消息
    if (event === 'start') {
      const newMessage = {
        id: message_id,
        agent,
        content: '',
        rawChunks: [],
        isComplete: false,
        startTime: created_time,
        endTime: null,
        config: this.agentConfigs[agent] || this.getDefaultConfig(agent),
        stepTitle: step_title || null,
        reactIndex: react_index
      };
      this.messages.set(message_id, newMessage);
      
    // 步骤追踪逻辑
    if (step_title && ['tool_select', 'search', 'query_rewrite', 'answerability', 'summarize_findings'].includes(agent)) {
      // 使用模糊匹配来查找正确的 step
      const matchedStepTitle = this.findMatchingStepTitle(step_title);
      if (matchedStepTitle) {
        const stepAgents = this.getOrCreateStepAgents(matchedStepTitle);
        
        // 更新状态
        stepAgents.status = 'in_progress';
        
        if (agent === 'tool_select' && react_index !== null) {
          stepAgents.currentReactRound = react_index;
        }

        // 使用 agent_name + round 作为唯一标识，支持多轮显示
        const agentKey = react_index !== null ? `${agent}_round_${react_index}` : agent;
        
        stepAgents.agents.set(agentKey, {
          name: agent,
          status: 'running',
          startTime: created_time,
          endTime: null,
          duration: null,
          error: null,
          round: react_index
        });
        
        console.log(`✅ 已为 step "${matchedStepTitle}" 添加 agent "${agent}" (Round: ${react_index})`);
      } else {
        console.error(`❌ 无法找到匹配的 step title: "${step_title}"`);
      }
    }
      
      // 返回初始化的消息，让前端能先显示出"节点"
      return this.formatMessageForDisplay(newMessage);
    }

    // 获取消息
    const message = this.messages.get(message_id);
    if (!message) {
      // 如果错过了 start 事件，尝试补救
      const rescueMessage = {
        id: message_id,
        agent,
        content: content || '',
        rawChunks: [chunk],
        isComplete: event === 'end',
        startTime: created_time,
        endTime: event === 'end' ? created_time : null,
        config: this.agentConfigs[agent] || this.getDefaultConfig(agent),
        stepTitle: step_title || null
      };
      this.messages.set(message_id, rescueMessage);
      return this.formatMessageForDisplay(rescueMessage);
    }

    // 添加chunk内容
    if (event === 'message') {
      message.content += content || '';
      message.rawChunks.push(chunk);
      // 每次收到消息内容都返回，实现流式更新
      return this.formatMessageForDisplay(message);
    }

    // 结束事件
    if (event === 'end') {
      message.isComplete = true;
      message.endTime = created_time;
      
      // 如果是 planner 节点完成，解析 steps
      if (agent === 'planner') {
        this.extractPlanSteps(message.content);
      }
      
      // 更新 Step 内 agent 的完成状态
      if (step_title && ['tool_select', 'search', 'query_rewrite', 'answerability', 'summarize_findings'].includes(agent)) {
        // 使用模糊匹配来查找正确的 step
        const matchedStepTitle = this.findMatchingStepTitle(step_title);
        if (matchedStepTitle) {
          const stepAgents = this.getOrCreateStepAgents(matchedStepTitle);
          // 查找当前轮次或最近的一个该类型的 agent
          const agentKey = react_index !== null ? `${agent}_round_${react_index}` : agent;
          let agentInfo = stepAgents.agents.get(agentKey);
          
          // 容错：如果精确 Key 没找到，尝试按名称找一个正在运行的
          if (!agentInfo) {
            for (const [key, info] of stepAgents.agents) {
              if (info.name === agent && info.status === 'running') {
                agentInfo = info;
                console.log(`💡 容错匹配成功: 通过状态找到正在运行的 agent "${agent}"`);
                break;
              }
            }
          }

          if (agentInfo) {
            agentInfo.status = 'completed';
            agentInfo.endTime = created_time;
            agentInfo.duration = created_time - agentInfo.startTime;
            
            // 如果是 summarize_findings 完成，或者这个 step 的所有任务都已标记完成
            if (agent === 'summarize_findings') {
              stepAgents.status = 'completed';
            }
            
            console.log(`✅ 已完成 agent "${agent}" (Round: ${react_index}) for step "${matchedStepTitle}"`);
          }
        }
      }
      
      return this.formatMessageForDisplay(message);
    }

    return null; // 进行中的消息不立即显示
  }

  /**
   * 从 planner 的响应中提取 steps
   */
  extractPlanSteps(content) {
    try {
      const parsed = JSON.parse(content);
      if (parsed && parsed.steps && Array.isArray(parsed.steps)) {
        this.planSteps = parsed.steps.map((step, index) => ({
          id: `step-${index}`,
          title: step.title || step.thought || `步骤 ${index + 1}`,
          status: 'pending' // pending, running, completed
        }));
        console.log('📋 解析到的计划步骤:', this.planSteps);
        
        // 为每个 step 初始化 stepsWithAgents
        for (const step of this.planSteps) {
          this.getOrCreateStepAgents(step.title);
        }
        console.log('🔧 已初始化 stepsWithAgents:', Array.from(this.stepsWithAgents.keys()));
      }
    } catch (e) {
      console.warn('⚠️ 无法解析 planner 响应为 JSON:', e);
    }
  }

  /**
   * 验证是否为有效的消息chunk
   */
  isValidMessageChunk(chunk) {
    return chunk &&
           chunk.message_id &&
           chunk.agent &&
           chunk.message_type === 'message_chunk' &&
           ['start', 'message', 'end'].includes(chunk.event);
  }

  /**
   * 格式化消息用于前端显示
   */
  formatMessageForDisplay(message) {
    const config = message.config;

    return {
      id: message.id,
      role: 'assistant',
      content: message.content.trim(),
      timestamp: message.startTime,
      agent: message.agent,
      agentLabel: config.label,
      agentColor: config.color,
      bgColor: config.bgColor,
      showRaw: config.showRaw,
      rawData: message.rawChunks,
      isComplete: message.isComplete,
      duration: message.endTime ? (message.endTime - message.startTime) : 0
    };
  }

  /**
   * 获取默认配置
   */
  getDefaultConfig(agent) {
    return {
      label: `🤖 ${agent}`,
      color: '#6b7280',
      bgColor: '#f9fafb',
      showRaw: true
    };
  }

  /**
   * 获取所有活跃的消息（用于调试）
   */
  getActiveMessages() {
    return Array.from(this.messages.values()).filter(msg => !msg.isComplete);
  }

  /**
   * 清理完成的消息
   */
  cleanupCompletedMessages() {
    for (const [messageId, message] of this.messages) {
      if (message.isComplete) {
        // 可以在这里添加清理逻辑，比如限制保留的消息数量
      }
    }
  }

  /**
   * 追踪信息收集任务
   */
  trackCollectorTask(messageId, event, stepTitle = null) {
    if (event === 'start') {
      let stepIndex = -1;
      
      // 如果提供了 stepTitle，精确匹配
      if (stepTitle) {
        stepIndex = this.planSteps.findIndex(step => 
          step.title === stepTitle && step.status === 'pending'
        );
      }
      
      // 如果没有找到，或者没有提供 stepTitle，找第一个 pending 的步骤
      if (stepIndex === -1) {
        stepIndex = this.planSteps.findIndex(step => step.status === 'pending');
      }
      
        if (stepIndex !== -1) {
          this.planSteps[stepIndex].status = 'running';
          this.collectorTasks.set(messageId, stepIndex);
          
          // 同时同步更新 stepsWithAgents 的状态
          const stepTitle = this.planSteps[stepIndex].title;
          const stepData = this.getOrCreateStepAgents(stepTitle);
          if (stepData) {
            stepData.status = 'in_progress';
          }
          
          console.log(`🟢 信息收集任务开始 [${stepIndex + 1}]: ${this.planSteps[stepIndex].title}`);
        }
      } else if (event === 'end') {
        // 标记对应的步骤为 completed
        const stepIndex = this.collectorTasks.get(messageId);
        if (stepIndex !== undefined && this.planSteps[stepIndex]) {
          this.planSteps[stepIndex].status = 'completed';
          
          // 同时同步更新 stepsWithAgents 的状态
          const stepTitle = this.planSteps[stepIndex].title;
          const stepData = this.stepsWithAgents.get(stepTitle);
          if (stepData) {
            stepData.status = 'completed';
          }
          
          this.collectorTasks.delete(messageId);
          console.log(`🔴 信息收集任务完成 [${stepIndex + 1}]: ${this.planSteps[stepIndex].title}`);
        }
      }
  }

  /**
   * 获取当前的计划步骤状态
   */
  getPlanSteps() {
    return [...this.planSteps];
  }

  /**
   * 重置处理器状态
   */
  reset() {
    this.messages.clear();
    this.planSteps = [];
    this.collectorTasks.clear();
    this.stepsWithAgents.clear();
  }

  /**
   * 为 Step 初始化或获取 agents 容器
   */
  getOrCreateStepAgents(stepTitle) {
    if (!stepTitle) return null;
    
    if (!this.stepsWithAgents.has(stepTitle)) {
      this.stepsWithAgents.set(stepTitle, {
        title: stepTitle,
        agents: new Map(), // agent_name -> agent_info
        currentReactRound: null,
        status: 'pending'
      });
      console.log('✨ 创建新的 StepAgents 容器:', stepTitle);
    }
    return this.stepsWithAgents.get(stepTitle);
  }

  /**
   * 查找匹配的 step title
   * 用模糊匹配来处理可能的不一致
   */
  findMatchingStepTitle(step_title) {
    if (!step_title) return null;
    
    // 1. 首先尝试精确匹配
    if (this.stepsWithAgents.has(step_title)) {
      return step_title;
    }
    
    const normalized = step_title.trim().toLowerCase();
    
    // 2. 尝试规范化匹配（忽略大小写和空格）
    for (const existingTitle of this.stepsWithAgents.keys()) {
      if (existingTitle.trim().toLowerCase() === normalized) {
        return existingTitle;
      }
    }

    // 3. 处理常见的 "Step X:" 前缀
    const strippedTitle = normalized.replace(/^step\s*\d+\s*[:：]\s*/i, '').trim();
    if (strippedTitle) {
      for (const existingTitle of this.stepsWithAgents.keys()) {
        const existingStripped = existingTitle.replace(/^step\s*\d+\s*[:：]\s*/i, '').trim().toLowerCase();
        if (existingStripped === strippedTitle) {
          console.log(`📌 前缀剥离精确匹配成功: "${step_title}" <-> "${existingTitle}"`);
          return existingTitle;
        }
      }
    }
    
    // 4. 尝试部分匹配（仅当长度差异较小时，避免误匹配）
    for (const existingTitle of this.stepsWithAgents.keys()) {
      const existingNormalized = existingTitle.toLowerCase();
      // 如果两个标题包含对方，且长度差异不超过 50%
      if (normalized.includes(existingNormalized) || existingNormalized.includes(normalized)) {
        const lenDiff = Math.abs(normalized.length - existingNormalized.length);
        const minLen = Math.min(normalized.length, existingNormalized.length);
        if (lenDiff < minLen * 0.5) {
          console.log(`📌 部分匹配成功: "${step_title}" <-> "${existingTitle}" (Length Diff: ${lenDiff})`);
          return existingTitle;
        }
      }
    }
    
    // 如果都没有，记录警告
    console.warn(`⚠️ 无法匹配 step title: "${step_title}"，已有的 steps:`, 
      Array.from(this.stepsWithAgents.keys()));
    return null;
  }

  /**
   * 为 Step 的特定 agent 更新状态
   */
  updateStepAgent(stepTitle, agentName, agentInfo) {
    const stepAgents = this.getOrCreateStepAgents(stepTitle);
    if (stepAgents) {
      stepAgents.agents.set(agentName, agentInfo);
    }
  }

  /**
   * 提取并格式化 Step 信息
   */
  getStepsData() {
    const stepsArray = [];
    
    // 优先按照 planSteps 的顺序输出，确保与规划一致
    if (this.planSteps && this.planSteps.length > 0) {
      for (const planStep of this.planSteps) {
        const stepData = this.stepsWithAgents.get(planStep.title);
        if (stepData) {
          const agents = [];
          let hasRunningAgent = false;
          let hasCompletedAgent = false;
          let isSummarizeComplete = false;

          for (const [agentKey, agentInfo] of stepData.agents) {
            agents.push({
              ...agentInfo,
              agentKey: agentKey
            });
            if (agentInfo.status === 'running') hasRunningAgent = true;
            if (agentInfo.status === 'completed') {
              hasCompletedAgent = true;
              if (agentInfo.name === 'summarize_findings') isSummarizeComplete = true;
            }
          }

          // 自动推断步骤状态
          let effectiveStatus = stepData.status || planStep.status || 'pending';
          if (isSummarizeComplete) {
            effectiveStatus = 'completed';
          } else if (hasRunningAgent || hasCompletedAgent) {
            effectiveStatus = 'in_progress';
          }

          stepsArray.push({
            title: stepData.title,
            agents,
            currentReactRound: stepData.currentReactRound,
            status: effectiveStatus
          });
        } else {
          // 如果 stepsWithAgents 中还没有，但 planSteps 有，也要显示出来
          stepsArray.push({
            title: planStep.title,
            agents: [],
            currentReactRound: null,
            status: planStep.status || 'pending'
          });
        }
      }
    } else {
      // 备选：如果没有 planSteps，则按创建顺序显示 stepsWithAgents
      for (const [stepTitle, stepData] of this.stepsWithAgents) {
        const agents = [];
        let hasRunningAgent = false;
        let isSummarizeComplete = false;

        for (const [agentKey, agentInfo] of stepData.agents) {
          agents.push({
            ...agentInfo,
            agentKey: agentKey
          });
          if (agentInfo.status === 'running') hasRunningAgent = true;
          if (agentInfo.status === 'completed' && agentInfo.name === 'summarize_findings') {
            isSummarizeComplete = true;
          }
        }

        let effectiveStatus = stepData.status || 'pending';
        if (isSummarizeComplete) effectiveStatus = 'completed';
        else if (hasRunningAgent || agents.length > 0) effectiveStatus = 'in_progress';

        stepsArray.push({
          title: stepTitle,
          agents,
          currentReactRound: stepData.currentReactRound,
          status: effectiveStatus
        });
      }
    }
    return stepsArray;
  }
}

/**
 * 消息显示过滤器
 * 用于后续决定显示哪些类型的消息
 */
export class MessageDisplayFilter {
  constructor() {
    // 显示顶级节点：entry、planner、answer、info_collector
    // entry：入口分类节点
    // planner：规划节点
    // answer：最终答案节点
    // info_collector：用于显示 InfoCollectionPanel（包含 Steps 的 ReAct 过程）
    this.displayAgents = new Set([
      'image_intent_recognition',
      'feedback_search_way',
      'entry',
      'planner',
      'answer',
      'show_image'
      // 注意：info_collector 是虚拟的，用于聚合 Steps 显示，不是实际的agent
    ]);
    
    // 中间节点列表（用于显示加载状态）
    // 这些节点会在各个Step内执行，不单独显示
    this.intermediateAgents = new Set([
      'query_rewrite',
      'tool_select',
      'search',
      'answerability',
      'summarize_findings'
    ]);
  }

  /**
   * 检查消息是否应该显示
   * @param {string} agent - 代理名称
   * @returns {boolean}
   */
  shouldDisplay(agent) {
    return this.displayAgents.has(agent);
  }

  /**
   * 检查是否为中间节点
   * @param {string} agent - 代理名称
   * @returns {boolean}
   */
  isIntermediateAgent(agent) {
    return this.intermediateAgents.has(agent);
  }

  /**
   * 设置显示的代理类型
   * @param {string[]} agents - 要显示的代理列表
   */
  setDisplayAgents(agents) {
    this.displayAgents = new Set(agents);
  }

  /**
   * 添加要显示的代理类型
   * @param {string} agent - 代理名称
   */
  addDisplayAgent(agent) {
    this.displayAgents.add(agent);
  }

  /**
   * 移除要显示的代理类型
   * @param {string} agent - 代理名称
   */
  removeDisplayAgent(agent) {
    this.displayAgents.delete(agent);
  }

  /**
   * 获取当前显示的代理列表
   * @returns {string[]}
   */
  getDisplayAgents() {
    return Array.from(this.displayAgents);
  }
}