import { 
    buildSmallStepsFromWorkflows, 
    buildStepIdToNodeIdMapping, 
    getWorkflowTraversal,
    deriveConnectionsFromWorkflows,
    cloneWithSuffix,
    makeBacktrackOrResumeSummary,
    createWorkflowTransitionStep
  } from './workflowHelpers';
  
  import { generateWorkflowColors } from '../components/utils/graphHelpers';

// ============================================================================
// BIG NODES - High-level task categories with layered positions
// ============================================================================
export const bigNodeData = {
  // Layer 0: Source
  source: { id: 'source', label: 'SOURCE', color: '#A7F3D0', isSpecial: true, x: -600, y: 0 },
  
  // Layer 1: First processing nodes (1, 2)
  node1: { id: 'node1', label: '节点 1: 进入应用程序', color: '#F0F0F0', x: -350, y: -200 },
  node2: { id: 'node2', label: '节点 2: 信息获取与解析', color: '#F0F0F0', x: -350, y: 0 },
  
  // Layer 2: Middle processing nodes (3, 4, 6)
  node3: { id: 'node3', label: '节点 3: 订购与预约操作', color: '#F0F0F0', x: -50, y: -350 },
  node4: { id: 'node4', label: '节点 4: 查询与检索', color: '#F0F0F0', x: -50, y: 0 },
  node6: { id: 'node6', label: '节点 6: 推理用户意图', color: '#F0F0F0', x: -50, y: 350 },
  
  // Layer 3: Final processing nodes (5)
  node5: { id: 'node5', label: '节点 5: 时间计算', color: '#F0F0F0', x: 200, y: -100 },
  
  // Layer 4: Target
  tail: { id: 'tail', label: 'TARGET', color: '#FECACA', isSpecial: true, x: 550, y: 0 },
};

// ============================================================================
// WORKFLOW DEFINITIONS - Agent-based workflows
// ============================================================================

export const baseWorkflows = {
    workflow1: {
        id: 'workflow1',
        title: '订车票',
        problem: '用户需要订购车票，系统需要进入车票订购应用，解析用户的时间和地点信息，然后根据这些信息订购车票。',
        expectedAnswer: '成功订购车票',
        errorType: null,
        steps: [
          {
            stepId: '1',
            question: '进入哪一个APP？',
            description: '进入app',
            reasoning: '进入车票订购app',
            nodeMapping: 'node1',
            correct: true,
            pass: 1,
          },
          {
            stepId: '2',
            question: '需要获取哪些信息？',
            description: '获取信息',
            reasoning: '解析用户提供自然语言中的时间和地点信息',
            nodeMapping: 'node2',
            correct: true,
            pass: 1,
          },
          {
            stepId: '3',
            question: '如何完成订购操作？',
            description: '订购车票',
            reasoning: '根据时间地点订购车票',
            nodeMapping: 'node3',
            correct: true,
            pass: 1,
          },
          {
            stepId: 'tail',
            question: '最终结果是什么？',
            description: '确认最终结果',
            reasoning: '车票订购流程已成功完成，用户获得了所需的车票。',
            nodeMapping: 'tail',
            correct: true,
            pass: 1,
          },
        ],
    },
    workflow2: {
        id: 'workflow2',
        title: '时间推算',
        problem: '用户需要推算到达时间，系统需要进入车票订购应用，解析时间和地点信息，查询到达时间，然后计算预测到达停车场时间。',
        expectedAnswer: '成功计算到达时间',
        errorType: null,
        steps: [
          {
            stepId: '4',
            question: '进入哪一个APP？',
            description: '进入app',
            reasoning: '进入车票订购app',
            nodeMapping: 'node1',
            correct: true,
            pass: 1,
          },
          {
            stepId: '5',
            question: '需要获取哪些信息？',
            description: '获取信息',
            reasoning: '解析用户提供自然语言中的时间和地点信息',
            nodeMapping: 'node2',
            correct: true,
            pass: 1,
          },
          {
            stepId: '6',
            question: '如何查询到达时间？',
            description: '查询内容',
            reasoning: '根据提供的车票时间地点信息查询到达时间',
            nodeMapping: 'node4',
            correct: true,
            pass: 1,
          },
          {
            stepId: '7',
            question: '如何计算预测到达停车场时间？',
            description: '根据信息计算',
            reasoning: '计算以预测到达停车场时间',
            nodeMapping: 'node5',
            correct: true,
            pass: 1,
          },
          {
            stepId: 'tail',
            question: '最终结果是什么？',
            description: '确认最终结果',
            reasoning: '时间推算流程已成功完成，用户获得了准确的到达时间预测。',
            nodeMapping: 'tail',
            correct: true,
            pass: 1,
          },
        ],
    },
    workflow3: {
        id: 'workflow3',
        title: '叫车',
        problem: '用户需要叫车服务，系统需要进入叫车应用，解析时间和地点信息，然后根据时间与地点预约车辆。',
        expectedAnswer: '成功预约车辆',
        errorType: null,
        steps: [
          {
            stepId: '8',
            question: '进入哪一个APP？',
            description: '进入app',
            reasoning: '进入叫车app',
            nodeMapping: 'node1',
            correct: true,
            pass: 1,
          },
          {
            stepId: '9',
            question: '需要获取哪些信息？',
            description: '获取信息',
            reasoning: '根据已有信息或解析用户提供自然语言中的时间和地点信息',
            nodeMapping: 'node2',
            correct: true,
            pass: 1,
          },
          {
            stepId: '10',
            question: '如何完成预约操作？',
            description: '根据信息预约',
            reasoning: '根据时间与地点预约车辆',
            nodeMapping: 'node3',
            correct: true,
            pass: 1,
          },
          {
            stepId: 'tail',
            question: '最终结果是什么？',
            description: '确认最终结果',
            reasoning: '车辆预约流程已成功完成，用户获得了所需的叫车服务。',
            nodeMapping: 'tail',
            correct: true,
            pass: 1,
          },
        ],
    },
    workflow4: {
        id: 'workflow4',
        title: '查询理解',
        problem: '用户进行查询，系统需要获取用户提供自然语言中的信息，然后根据获取的信息推理用户意图。',
        expectedAnswer: '成功理解用户意图',
        errorType: null,
        steps: [
          {
            stepId: '11',
            question: '需要获取哪些信息？',
            description: '获取信息',
            reasoning: '获取用户提供自然语言中的信息',
            nodeMapping: 'node2',
            correct: true,
            pass: 1,
          },
          {
            stepId: '12',
            question: '如何推理用户意图？',
            description: '推理内容',
            reasoning: '根据获取的信息推理用户意图',
            nodeMapping: 'node6',
            correct: true,
            pass: 1,
          },
          {
            stepId: 'tail',
            question: '最终结果是什么？',
            description: '确认最终结果',
            reasoning: '用户意图推理流程已成功完成，系统准确理解了用户的查询意图。',
            nodeMapping: 'tail',
            correct: true,
            pass: 1,
          },
        ],
    },
    workflow5: {
        id: 'workflow5',
        title: '记忆检索',
        problem: '用户需要检索历史信息，系统需要进入酒店预订应用，解析时间和地点信息，然后根据获取的信息检索历史得到相应答案。',
        expectedAnswer: '成功检索历史信息',
        errorType: "initial-mistake",
        steps: [
          {
            stepId: '13',
            question: '进入哪一个APP？',
            description: '进入app',
            reasoning: '进入酒店预订app',
            nodeMapping: 'node1',
            correct: true,
            pass: 1,
          },
          {
            stepId: '14',
            question: '需要获取哪些信息？',
            description: '获取信息',
            reasoning: '解析用户提供自然语言中的时间和地点信息',
            nodeMapping: 'node2',
            correct: true,
            pass: 1,
          },
          {
            stepId: '15',
            question: '如何检索历史信息？',
            description: '检索历史',
            reasoning: '根据获取的信息检索历史得到相应答案',
            nodeMapping: 'node4',
            correct: true,
            pass: 1,
          },
          {
            stepId: 'tail',
            question: '最终结果是什么？',
            description: '确认最终结果',
            reasoning: '历史信息检索流程已成功完成，用户获得了所需的历史数据。',
            nodeMapping: 'tail',
            correct: true,
            pass: 1,
          },
        ],
    },
    workflow6: {
        id: 'workflow6',
        title: '订酒店',
        problem: '用户需要预订酒店，系统需要进入酒店预订应用，解析时间和地点信息，然后根据时间地点预订酒店。',
        expectedAnswer: '成功预订酒店',
        errorType: null,
        steps: [
          {
            stepId: '16',
            question: '进入哪一个APP？',
            description: '进入app',
            reasoning: '进入酒店预订app',
            nodeMapping: 'node1',
            correct: true,
            pass: 1,
          },
          {
            stepId: '17',
            question: '需要获取哪些信息？',
            description: '获取信息',
            reasoning: '根据已有信息或解析用户提供自然语言中的时间和地点信息',
            nodeMapping: 'node2',
            correct: true,
            pass: 1,
          },
          {
            stepId: '18',
            question: '如何完成预订操作？',
            description: '预订酒店',
            reasoning: '根据时间地点预订酒店',
            nodeMapping: 'node3',
            correct: true,
            pass: 1,
          },
          {
            stepId: 'tail',
            question: '最终结果是什么？',
            description: '确认最终结果',
            reasoning: '酒店预订流程已成功完成，用户获得了所需的酒店预订。',
            nodeMapping: 'tail',
            correct: true,
            pass: 1,
          },
        ],
    },
}

// ============================================================================
// DEFAULT TRAVERSALS
// ============================================================================

// Build composite/scenario workflows after base workflows are declared
function withScenarioWorkflows(base) {

  // Scenario 1.1 (workflow7): w1 -> w3, then wrong at tail and backtrack
  const workflow7 = {
    id: 'workflow7',
    title: '场景1.1：工作流1→3，然后在目标处发现错误并完全回溯',
    problem: '先执行订车票，再执行叫车；在目标发现路径错误，需要回溯全部步骤。',
    expectedAnswer: '回溯后重新开始',
    errorType: 'reasoning-chain-error',
    steps: [
      ...cloneWithSuffix(base.workflow1.steps, '-w1'),
      // Ensure we restart from source between workflows
      createWorkflowTransitionStep('w1', 'w3'),
      ...cloneWithSuffix(base.workflow3.steps, '-w3'),
      {
        stepId: 'tail-w3',
        question: '答案是否合理？',
        description: '在目标节点验证答案（发现路径选择错误）',
        reasoning: '在目标处发现整个工作路径选择错误，需要回溯叫车相关步骤。',
        nodeMapping: 'tail',
        correct: false,
        pass: 1,
        errorType: 'reasoning-lapse',
        errorDetails: {
          issue: '发现选取了错误路径，需撤回叫车相关步骤。',
          discoveryMoment: '在目标节点验证阶段发现异常。',
          backtrackTo: 'node3'
        },
        backtrack: true
      },
      { stepId: '10-w3-analyze', description: '回溯：检查时间/预约操作', reasoning: '从目标回溯到预约操作', nodeMapping: 'node3', from: 'tail', to: 'node3', correct: false, pass: null, backtrack: true },
      { stepId: '9-w3-analyze', description: '回溯：检查信息获取', reasoning: '从预约操作回溯到信息获取', nodeMapping: 'node2', from: 'node3', to: 'node2', correct: false, pass: null, backtrack: true },
      { stepId: '8-w3-analyze', description: '回溯：检查进入APP', reasoning: '从信息获取回溯到进入APP', nodeMapping: 'node1', from: 'node2', to: 'node1', correct: false, pass: null, backtrack: true },
      { stepId: 'return-to-source', description: '回到起点重新开始', reasoning: '完成错误分析后，返回source节点', nodeMapping: 'source', from: 'node1', to: 'source', correct: false, pass: null, backtrack: true },
      makeBacktrackOrResumeSummary('w1', true),
    ],
  };

  // Scenario 1.2 (workflow8): w1 -> w2 -> w3, keep intermediate tails
  const workflow8 = {
    id: 'workflow8',
    title: '场景1.2：组合任务（工作流1→2→3）',
    problem: '连续完成订车票、时间推算与叫车，形成一个更大的任务链。',
    expectedAnswer: '成功完成组合任务',
    errorType: null,
    steps: [
      ...cloneWithSuffix(base.workflow1.steps, '-w1'),
      // Restart from source between segments
      createWorkflowTransitionStep('w1', 'w2'),
      ...cloneWithSuffix(base.workflow2.steps, '-w2'),
      createWorkflowTransitionStep('w2', 'w3'),
      ...cloneWithSuffix(base.workflow3.steps, '-w3'),
    ],
  };

  // Scenario 2 (workflow9): w4 -> w5 -> w6 -> tail -> backtrack w6 -> backtrack w5 -> backtrack w4 -> w4 -> changed w5 -> w6 -> tail
  const workflow9 = {
    id: 'workflow9',
    title: '场景2：查询→记忆检索→订酒店→目标处回溯→修正后重做',
    problem: '先查询理解，再记忆检索，再订酒店；在目标发现问题后回溯三段并重做（更换记忆检索策略），最终完成。',
    expectedAnswer: '成功完成，包含回溯与二次修正过程',
    errorType: 'initial-mistake',
    steps: [
      // Forward: w4 -> w5 -> w6
      ...cloneWithSuffix(base.workflow4.steps, '-w4'),
      createWorkflowTransitionStep('w4', 'w5'),
      ...cloneWithSuffix(base.workflow5.steps, '-w5'),
      createWorkflowTransitionStep('w5', 'w6'),
      ...cloneWithSuffix(base.workflow6.steps, '-w6'),
      // Tail verification error to trigger backtrack from w6
      {
        stepId: 'tail-wrong2',
        question: '答案是否合理？',
        description: '在目标节点验证答案（发现组合路径错误）',
        reasoning: '在目标发现问题，需回溯全部三段以更换策略。',
        nodeMapping: 'tail',
        correct: false,
        pass: 1,
        errorDetails: {
              "issue": "结果不满足'最小'要求。",
              "discoveryMoment": "在目标节点进行最小性检验时发现异常。",
              "backtrackTo": "source"
            },
        backtrack: true
      },
      // Backtrack summaries: w6 -> source, then w5 -> source, then w4 -> source
      makeBacktrackOrResumeSummary('w6', true),
      makeBacktrackOrResumeSummary('w5', true),
      makeBacktrackOrResumeSummary('w4', true),
      // Resume: w4 (again), then changed w5 (second pass), then w6, then final tail
      makeBacktrackOrResumeSummary('w4-b', false),
      { stepId: '13-b', question: '进入哪一个APP？（第二轮）', description: '进入app（第二轮）', reasoning: '进入酒店预订app（第二轮）', nodeMapping: 'node1', correct: true, pass: 2, isCorrection: true },
      { stepId: '14-b', question: '需要获取哪些信息？（第二轮）', description: '获取信息（第二轮）', reasoning: '解析用户提供自然语言中的时间和地点信息（第二轮）', nodeMapping: 'node2', correct: true, pass: 2, isCorrection: true },
      { stepId: '15-b', question: '如何检索历史信息？（第二轮）', description: '检索历史（第二轮）', reasoning: '采用修正后的记忆函数进行检索（第二轮）', nodeMapping: 'node4', correct: true, pass: 2, isCorrection: true },
      makeBacktrackOrResumeSummary('w6-b', false),
      { stepId: 'tail-final-b', question: '修正后的答案正确吗？（第二轮）', description: '确认修正后的答案（第二轮）', reasoning: '验证通过，组合策略已修正。', nodeMapping: 'tail', correct: true, pass: 2, isCorrection: true },
    ],
  };

  return {
    ...base,
    workflow7,
    workflow8,
    workflow9,
  };
}

export const workflows = withScenarioWorkflows(workflows);

// ============================================================================
// DERIVED DATA - Build from workflowsWithScenarios
// ============================================================================

export const smallSteps = buildSmallStepsFromWorkflows(workflowsWithScenarios);
// Add empty arrays for source and tail nodes (they have no internal steps)
smallSteps.source = [];
smallSteps.tail = [];


export const stepIdToNodeId = buildStepIdToNodeIdMapping(smallSteps, workflowsWithScenarios);

// ============================================================================
// GRAPH STRUCTURE - Connections between nodes
// ============================================================================

// Connection pairs for graph layout computation
// Automatically derived from workflow definitions - no manual maintenance needed!
export const connections = deriveConnectionsFromWorkflows(workflowsWithScenarios);

// Edge data with labels (for rendering)
export const edgesData = connections.map(([from, to]) => {
  let label = '';
  if (from === 'source') label = 'source';
  if (to === 'tail') label = 'target';
  return { from, to, label };
});

// ============================================================================
// TRAVERSALS - Dynamically generated from workflows
// ============================================================================

// Generate all traversals dynamically
export const traversals = Object.keys(workflowsWithScenarios).reduce((acc, workflowId) => {
  acc[workflowId] = getWorkflowTraversal(workflowId, workflowsWithScenarios);
  return acc;
}, {});



// ============================================================================
// EDGE CONFIGURATIONS - Curved edges for this dataset
// ============================================================================

export const edgeConfigurations = {
  'source|tail': {
    isCurved: true,
    curveType: 'arc',
    curveOffset: 720,
    controlPoint: 'arc-above'
  },
  'tail|source': {
    isCurved: true,
    curveType: 'arc',
    curveOffset: 720,
    controlPoint: 'arc-above'
  }
};

// ============================================================================
// DYNAMIC COLOR ASSIGNMENT
// ============================================================================

// Generate workflow colors dynamically based on workflow IDs
export const workflowColors = generateWorkflowColors(Object.keys(workflowsWithScenarios));
