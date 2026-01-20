import {
  buildSmallStepsFromWorkflows,
  buildStepIdToNodeIdMapping,
  getWorkflowTraversal,
  deriveConnectionsFromWorkflows
} from './workflowHelpers';

import { generateWorkflowColors } from '../components/utils/graphHelpers';

// ============================================================================
// WORKFLOW DEFINITIONS (Finance/Stocks) - Placeholder structure
// - Intentionally omits bigNodeData for now (defined in a later step)
// - Workflows will be populated in a later step
// ============================================================================
export const bigNodeData = {
    // Layer 0: Source
    source: { id: 'source', label: 'SOURCE', color: '#A7F3D0', isSpecial: true, x: -600, y: 0 },
  
    // Layer 1: Input & Condition Nodes
    node1:  { id: 'node1',  label: '节点1: 收集数据', labelHistory: ['收集数据'], color: '#F0F0F0', x: -350, y: -120 },
    node7:  { id: 'node7',  label: '节点7: 确认限定条件', labelHistory: ['选择限定条件', '确认限定条件'], color: '#F0F0F0', x: -350, y: 120 },
  
    // Layer 2: Information / Structural Nodes
    node14: { id: 'node14', label: '节点14: 确认准确性', labelHistory: ['确认准确性'], color: '#F0F0F0', x: -150, y: -360 },
    node8:  { id: 'node8',  label: '节点8: 查询重仓股票', labelHistory: ['查询重仓股票'], color: '#F0F0F0', x: -150, y: -180 },
    node16: { id: 'node16', label: '节点16: 建立模型', labelHistory: ['建立模型'], color: '#F0F0F0', x: -150, y: 0 },
    node2:  { id: 'node2',  label: '节点2: 获取信息，归类并计算', labelHistory: ['归类与权重计算', '获取信息，归类并计算'], color: '#F0F0F0', x: -150, y: 180 },
    node10: { id: 'node10', label: '节点10: 设定候选基金', labelHistory: ['设定候选基金'], color: '#F0F0F0', x: -150, y: 360 },
  
    // Layer 3: Logical & Rule-Based Nodes
    node15: { id: 'node15', label: '节点15: 明确相关规则', labelHistory: ['明确相关规则'], color: '#F0F0F0', x: 150, y: -360 },
    node3:  { id: 'node3',  label: '节点3: 量化风险与收益并筛选', labelHistory: ['量化风险与收益', '量化风险与收益并筛选'], color: '#F0F0F0', x: 150, y: 150 },
  
    // Layer 4: Analysis Node
    node4:  { id: 'node4',  label: '节点4: 分析评估结果', labelHistory: ['分析数据', '分析评估数据', '分析评估结果'], color: '#F0F0F0', x: 150, y: -100 },
  
    // Layer 5: Evaluation / Testing / Reporting Nodes
    node12: { id: 'node12', label: '节点12: 模拟制定测试场景', labelHistory: ['模拟场景', '模拟制定场景', '模拟制定测试场景'], color: '#F0F0F0', x: 500, y: -360 },
    node11: { id: 'node11', label: '节点11: 评测并选择', labelHistory: ['评测并选择'], color: '#F0F0F0', x: 500, y: -180 },
    node5:  { id: 'node5',  label: '节点5: 测试检验', labelHistory: ['测试检验'], color: '#F0F0F0', x: 500, y: 0 },
    node13: { id: 'node13', label: '节点13: 归因并可视化结果', labelHistory: ['归因并可视化结果'], color: '#F0F0F0', x: 500, y: 180 },
    node9:  { id: 'node9',  label: '节点9: 综合匹配与报告', labelHistory: ['综合匹配与报告'], color: '#F0F0F0', x: 500, y: 360 },
  
    // Layer 6: Output & Suggestion Nodes
    node6:  { id: 'node6',  label: '节点6: 提出建议', labelHistory: ['提出建议'], color: '#F0F0F0', x: 900, y: 0 },
  
    // Layer 7: Target
    tail:   { id: 'tail',   label: 'TARGET', color: '#FECACA', isSpecial: true, x: 1150, y: 0 },
  };

  export const baseWorkflows = {
    workflow1: {
      id: 'workflow1',
      title: '基金配置分散度与风险分析',
      problem: '我现在持有易方达蓝筹精选、富国天盈债券和华夏上证50ETF，麻烦分析一下我的配置分散程度和风险，并给出优化意见。',
      expectedAnswer: null,
      errorType: null,
      steps: [
        { stepId: '1', question: '如何收集并确认基金的基础持仓数据？', description: '收集数据', reasoning: '确认并收集基础持仓数据。', nodeMapping: 'node1', correct: true, pass: 1 },
        { stepId: '2', question: '如何根据资产类别和风险因子进行归类与权重计算？', description: '归类与权重计算', reasoning: '把三只基金按“资产类别/风险因子”做归类与分配权重计算。', nodeMapping: 'node2', correct: true, pass: 1 },
        { stepId: '3', question: '怎样量化基金组合的风险与收益？', description: '量化风险与收益', reasoning: '量化风险与收益特征。', nodeMapping: 'node3', correct: true, pass: 1 },
        { stepId: '4', question: '如何分析基金之间的分散度、相关性和重仓重叠？', description: '分析数据', reasoning: '分散度/相关性/重仓重叠分析。', nodeMapping: 'node4', correct: true, pass: 1 },
        { stepId: '5', question: '怎样进行情景与压力测试？', description: '测试检验', reasoning: '情景/压力测试与流动性检验。', nodeMapping: 'node5', correct: true, pass: 1 },
        { stepId: '6', question: '如何提出基金组合的优化建议？', description: '提出建议', reasoning: '优化建议与执行细则。', nodeMapping: 'node6', correct: true, pass: 1 },
        { stepId: 'tail', question: '最终答案是否正确？', description: '确认最终结论', reasoning: '经过前面步骤分析，最终结论合理且与题意一致。', nodeMapping: 'tail', correct: true, pass: 1 },
      ],
    },
  
    workflow2: {
      id: 'workflow2',
      title: '龙虎榜前3股票与重仓基金分析',
      problem: '请帮我找出近一个月龙虎榜前三的股票，看看有哪些基金重仓了这些股票，并分析这些基金的近一年收益情况。',
      expectedAnswer: null,
      errorType: null,
      steps: [
        { stepId: '7', question: '如何确定数据口径、时间窗与数据源？', description: '选择限定条件', reasoning: '确认口径、时间窗与数据源。', nodeMapping: 'node7', correct: true, pass: 1 },
        { stepId: '8', question: '怎样拉取龙虎榜最近30天的数据并生成Top3？', description: '收集数据', reasoning: '拉取龙虎榜最近30天数据并生成“Top3”。', nodeMapping: 'node1', correct: true, pass: 1 },
        { stepId: '9', question: '如何查询这些Top3股票被哪些机构重仓？', description: '查询重仓股票', reasoning: '查询这些Top3股票被哪些公募/社保/QFII/券商重仓。', nodeMapping: 'node8', correct: true, pass: 1 },
        { stepId: '10', question: '如何获取基金近一年净值序列并计算业绩指标？', description: '获取信息并计算', reasoning: '获取这些基金的近一年净值序列并计算业绩指标。', nodeMapping: 'node2', correct: true, pass: 1 },
        { stepId: '11', question: '如何整合股票与基金表现信息形成报告？', description: '综合匹配与报告', reasoning: '把“股票，基金，基金近一年表现”关联起来。', nodeMapping: 'node9', correct: true, pass: 1 },
        { stepId: 'tail', question: '最终答案是否正确？', description: '确认最终结论', reasoning: '经过前面步骤分析，最终结论合理且与题意一致。', nodeMapping: 'tail', correct: true, pass: 1 },
      ],
    },
  
    workflow3: {
        id: 'workflow3',
        title: '混合型基金投资方案评估与配置建议',
        problem: '我想投资20万元选择几只表现较好的混合型基金，请帮我评估哪些基金适合中短期与中长期配置，并分析整体投资方案的收益和风险，还有详细的配置建议及可视化报告。',
        expectedAnswer: null,
        errorType: 'initial-mistake',
        steps: [
          { stepId: '12-wrong', question: '如何明确投资目标、约束与时间？', description: '确定条件', reasoning: '明确投资目标、约束与时间。', nodeMapping: 'node7', correct: true, pass: 1 },
          { stepId: '13-wrong', question: '如何确定候选基金并收集基线数据？', description: '设定候选基金', reasoning: '确定候选基金并收集基线数据。', nodeMapping: 'node10', correct: true, pass: 1 },
          { stepId: '14-wrong', question: '如何根据表现与稳定性指标进行量化筛选？', description: '量化筛选', reasoning: '筛选表现与稳定性指标。', nodeMapping: 'node3', correct: true, pass: 1 },
          { stepId: '15-wrong', question: '如何按时间长短进行基金适配化打分与挑选？', description: '评测并选择', reasoning: '按时间长短做适配化打分与挑选。', error: "路由错误", nodeMapping: 'node4', correct: false, pass: 1 },
          { stepId: '16-wrong', question: '如何构建组合并进行风险收益模拟？', description: '模拟场景', reasoning: '组合构建、风险收益模拟与情景测试。', nodeMapping: 'node12', correct: true, pass: 1, arrowColor: "red", "highlightColor": "green"},
          { stepId: '17-wrong', question: '如何输出可执行的配置建议与报告？', description: '提出建议', reasoning: '输出可执行配置建议、再平衡计划与可视化报告。', nodeMapping: 'node6', correct: true, pass: 1 },
          {
            stepId: 'tail-wrong',
            question: '最终答案是否正确？',
            description: '确认最终结论',
            reasoning: '系统检测到在评估与选择阶段由错误代理执行任务，导致量化筛选结果未被有效使用，进而使后续模拟与建议基于无效输入。',
            nodeMapping: 'tail',
            correct: false,
            pass: 1,
            errorType: 'reasoning-lapse',
            errorDetails: {
              "issue": "在第15步中，规划代理将任务错误地分配给分析代理，导致未进行实际的评测与选择操作。",
              "discoveryMoment": "在目标节点验证阶段发现输出缺失或为空，无法追溯有效基金选择结果。",
              "backtrackTo": "node6",
            },
            backtrack: true,
            arrowColor: 'green', highlightColor: 'red' 
          }, 
        
          { stepId: 'tail-analyze', description: '回溯修理错误', reasoning: '因为答案错了，所以得回溯到节点6提出建议步骤。', nodeMapping: 'tail', from: 'tail', to: 'node6', correct: false, pass: null, backtrack: true },
        { stepId: '17-analyze', description: '回溯修理错误', reasoning: '因为答案错了，所以得回溯到节点12模拟场景步骤。', nodeMapping: 'node6', from: 'node6', to: 'node12', correct: false, pass: null, backtrack: true },
        { stepId: '16-analyze', description: '回溯修理错误', reasoning: '因为答案错了，所以得回溯到节点11评测并选择步骤。', nodeMapping: 'node12', from: 'node12', to: 'node4', correct: false, pass: null, backtrack: true },
        { stepId: '15-analyze', description: '回溯修理错误', reasoning: '因为答案错了，所以得回溯到节点3量化筛选步骤。', nodeMapping: 'node4', from: 'node11', to: 'node3', correct: false, pass: null, backtrack: true },
        { stepId: '14-analyze', description: '回溯修理错误', reasoning: '因为答案错了，所以得回溯到节点10候选基金设定步骤。', nodeMapping: 'node3', from: 'node3', to: 'node10', correct: false, pass: null, backtrack: true },
        { stepId: '13-analyze', description: '回溯修理错误', reasoning: '因为答案错了，所以得回溯到节点7投资条件确定步骤。', nodeMapping: 'node10', from: 'node10', to: 'node7', correct: false, pass: null, backtrack: true },
        { stepId: 'return-to-source', description: '回到起点重新开始', reasoning: '完成错误分析后，返回source节点开始第二轮推理。', nodeMapping: 'source', from: 'node7', to: 'source', correct: false, pass: null, backtrack: true },
        { stepId: '12', question: '如何明确投资目标、约束与时间？（第二轮）', description: '确定条件', reasoning: '明确投资目标、约束与时间。', nodeMapping: 'node7', correct: true, pass: 2 },
        { stepId: '13', question: '如何确定候选基金并收集基线数据？（第二轮）', description: '设定候选基金', reasoning: '确定候选基金并收集基线数据。', nodeMapping: 'node10', correct: true, pass: 2 },
        { stepId: '14', question: '如何根据表现与稳定性指标进行量化筛选？（第二轮）', description: '量化筛选', reasoning: '筛选表现与稳定性指标。', nodeMapping: 'node3', correct: true, pass: 2 },
        { stepId: '15', question: '如何按时间长短进行基金适配化打分与挑选？（第二轮）', description: '评测并选择', reasoning: '按时间长短做适配化打分与挑选。被分配给了错误的代理，发现了错误。', nodeMapping: 'node11', correct: true, pass: 2 },
        { stepId: '16', question: '如何构建组合并进行风险收益模拟？（第二轮）', description: '模拟场景', reasoning: '组合构建、风险收益模拟与情景测试。', nodeMapping: 'node12', correct: true, pass: 2 },
        { stepId: '17', question: '如何输出可执行的配置建议与报告？（第二轮）', description: '提出建议', reasoning: '输出可执行配置建议、再平衡计划与可视化报告。', nodeMapping: 'node6', correct: true, pass: 2 },
        { stepId: 'tail', question: '最终答案是否正确？（第二轮）', description: '确认最终结论', reasoning: '经过前面步骤分析，最终结论合理且与题意一致。', nodeMapping: 'tail', correct: true, pass: 2 },
        ],
      },
      
  
    workflow4: {
      id: 'workflow4',
      title: '三只基金业绩与结构对比分析',
      problem: '我最近对易方达蓝筹精选、华夏成长混合和南方科技创新三只基金感兴趣，能帮我对比它们近1年和近3年的业绩表现、风险指标、持有人结构，并用图表方式展示主要差异吗？',
      expectedAnswer: null,
      errorType: null,
      steps: [
        { stepId: '18', question: '如何确认分析的口径与范围？', description: '确认限定条件', reasoning: '确认口径与分析范围。', nodeMapping: 'node7', correct: true, pass: 1 },
        { stepId: '19', question: '如何抓取净值、持仓与持有人结构数据？', description: '数据采集', reasoning: '抓取净值、持仓、份额/持有人结构等信息。', nodeMapping: 'node1', correct: true, pass: 1 },
        { stepId: '20', question: '如何计算基金的业绩与风险指标？', description: '计算数据', reasoning: '计算业绩与风险指标。', nodeMapping: 'node2', correct: true, pass: 1 },
        { stepId: '21', question: '如何分析基金持仓与持有人结构？', description: '分析评估数据', reasoning: '持仓与持有人结构分析。', nodeMapping: 'node4', correct: true, pass: 1 },
        { stepId: '22', question: '如何进行归因并可视化主要差异？', description: '归因并可视化结果', reasoning: '归因与可视化主要差异。', nodeMapping: 'node13', correct: true, pass: 1 },
        { stepId: 'tail', question: '最终答案是否正确？', description: '确认最终结论', reasoning: '经过前面步骤分析，最终结论合理且与题意一致。', nodeMapping: 'tail', correct: true, pass: 1 },
      ],
    },
  
    workflow5: {
      id: 'workflow5',
      title: '广发证券精选基金申购规则与操作建议',
      problem: '我准备下个月申购广发证券精选基金，请帮我查询这个基金的申购交易规则、费用、资金到账时间、收益计入时间，并给我一个关键节点的日历表和操作建议。',
      expectedAnswer: null,
      errorType: null,
      steps: [
        { stepId: '23', question: '如何确认目标基金的身份与份额类型？', description: '确认限定条件', reasoning: '确认目标基金的精确身份与份额类型。', nodeMapping: 'node7', correct: true, pass: 1 },
        { stepId: '24', question: '如何抓取和核对基金招募说明书与公告？', description: '数据采集', reasoning: '抓取、核对招募说明书与最新公告。', nodeMapping: 'node1', correct: true, pass: 1 },
        { stepId: '25', question: '如何确认申购时间、到账方式与处理节奏？', description: '确认准确性', reasoning: '确认渠道截单时间、资金到帐方式与处理节奏。', nodeMapping: 'node14', correct: true, pass: 1 },
        { stepId: '26', question: '怎样明确申购、收益计入和赎回时间规则？', description: '明确相关规则', reasoning: '明确“申购确认日、收益计入时间、份额可用/可赎回时间”规则。', nodeMapping: 'node15', correct: true, pass: 1 },
        { stepId: '27', question: '如何制定基金交易的关键节点日历？', description: '制定相关场景', reasoning: '制定关键节点日历。', nodeMapping: 'node12', correct: true, pass: 1 },
        { stepId: '28', question: '如何提出优化申购风险与费用的建议？', description: '提出建议', reasoning: '给出风险/费用优化与应急建议。', nodeMapping: 'node6', correct: true, pass: 1 },
        { stepId: 'tail', question: '最终答案是否正确？', description: '确认最终结论', reasoning: '经过前面步骤分析，最终结论合理且与题意一致。', nodeMapping: 'tail', correct: true, pass: 1 },
      ],
    },
  
    workflow6: {
      id: 'workflow6',
      title: '家庭财务健康与现金流评估',
      problem: '我有三口之家，父母都已工作，孩子正在上小学，目前家庭总资产包括两套房产、一辆汽车和一些理财产品，负债主要是房贷，我和妻子每年收入合计40万，还偶尔有奖金。我们每月生活支出约1.5万，如何评估我们未来五年的财务健康和现金流状况？',
      expectedAnswer: null,
      errorType: "reasoning-chain-error",
      steps: [
        { stepId: '29', question: '如何收集并核对家庭的基础财务数据？', description: '收集数据', reasoning: '收集并核对基础数据。', nodeMapping: 'node1', correct: true, pass: 1 },
        { stepId: '30', question: '如何建立5年现金流与净值基线模型？', description: '建立模型', reasoning: '建立 5 年现金流与净值基线模型。', nodeMapping: 'node16', correct: true, pass: 1 },
        { stepId: '31', question: '如何评估关键财务健康和现金流状况', description: '分析评估结果', reasoning: '评估财务健康和<strong style="color:#6EADFF">现金流状况。</strong>', error: "Planner 给出的 Plan 有误", nodeMapping: 'node4', correct: false, pass: 1, arrowColor: 'green', highlightColor: 'red' },
        { stepId: '32', question: '如何执行情景与压力测试？', description: '测试场景', reasoning: '实行情景与压力测试。', nodeMapping: 'node12', correct: true, pass: 1 },
        { stepId: '33', question: '如何提出可执行的财务健康建议？', description: '提出建议', reasoning: '给出可执行建议与定期监控计划。', nodeMapping: 'node6', correct: true, pass: 1 },
        {
          stepId: 'tail',
          question: '最终答案是否正确？',
          description: '确认最终结论',
          reasoning: '检测结果发现财务健康评估中关键指标（债务收入比、流动性覆盖率）未计算，导致整体判断错误。',
          nodeMapping: 'tail',
          correct: false,
          pass: 1,
          errorDetails: {
              "issue": "分析阶段缺乏定量计算，导致建议基于不完整模型。",
              "discoveryMoment": "在目标节点进行分析评估时发现异常。",
              "backtrackTo": "node6"
            },
            backtrack: true,
            arrowColor: 'green', highlightColor: 'red' 
        }, 
        { stepId: '33-analyze', description: '回溯修理错误', reasoning: '因为答案错了，所以得回溯到节点12测试场景步骤。', nodeMapping: 'node6', from: 'node6', to: 'node12', correct: false, pass: null, backtrack: true },
        { stepId: '32-analyze', description: '回溯修理错误', reasoning: '因为答案错了，所以得回溯到节点4分析计算步骤。', nodeMapping: 'node12', from: 'node12', to: 'node4', correct: false, pass: null, backtrack: true },  
        { stepId: '31-analyze', description: '回溯修理错误', reasoning: '因为答案错了，所以得回溯到节点16模型建立步骤。', nodeMapping: 'node4', from: 'tail', to: 'node16', correct: false, pass: null, backtrack: true },
        { stepId: '30-analyze', description: '回溯修理错误', reasoning: '因为答案错了，所以得回溯到节点1数据收集步骤。', nodeMapping: 'node16', from: 'node4', to: 'node1', correct: false, pass: null, backtrack: true },
        { stepId: 'return-to-source', description: '回到起点重新开始', reasoning: '完成错误分析后，返回source节点开始第二轮推理。', nodeMapping: 'source', from: 'node1', to: 'source', correct: false, pass: null, backtrack: true },
        { stepId: '29-b', question: '如何收集并核对家庭的基础财务数据？（第二轮）', description: '收集数据（第二轮）', reasoning: '重新核对并补充家庭年度支出、储蓄比例及债务还款明细。', nodeMapping: 'node1', correct: true, pass: 2, isCorrection: true },
        { stepId: '30-b', question: '如何建立5年现金流与净值基线模型？（第二轮）', description: '建立模型（第二轮）', reasoning: '修正模型假设，更新工资增长率与房贷利率参数。', nodeMapping: 'node16', correct: true, pass: 2, isCorrection: true },
        { stepId: '31-b', question: '如何评估关键财务健康指标与阈值？（第二轮）', description: '分析评估结果（第二轮）', reasoning: '发现了错误，<strong style="color:#6EADFF">问题改成： “如何评估关键财务健康指标与阈值？”。</strong>', nodeMapping: 'node4', correct: true, pass: 2, isCorrection: true },
        { stepId: '32-b', question: '如何执行情景与压力测试？（第二轮）', description: '测试场景（第二轮）', reasoning: '假设利率上升1%、收入下降5%，重新运行模型进行压力测试。', nodeMapping: 'node12', correct: true, pass: 2, isCorrection: true },
        { stepId: '33-b', question: '如何提出可执行的财务健康建议？（第二轮）', description: '提出建议（第二轮）', reasoning: '建议提升应急储备至6个月生活支出，并定期复核现金流模型。', nodeMapping: 'node6', correct: true, pass: 2, isCorrection: true },
        { stepId: 'tail-final', question: '最终结论是否修正正确？（第二轮）', description: '确认最终结论（第二轮）', reasoning: '修正后的模型计算完整，财务健康评估结果合理且与题意一致。', nodeMapping: 'tail', correct: true, pass: 2 }
      
      ],
    },
  };
  
export const workflows = baseWorkflows;  

// ============================================================================
// DERIVED DATA - Build from workflows
// ============================================================================

export const smallSteps = buildSmallStepsFromWorkflows(workflows);
// Ensure source/tail exist for consumers that expect arrays
smallSteps.source = smallSteps.source || [];
smallSteps.tail = smallSteps.tail || [];

export const stepIdToNodeId = buildStepIdToNodeIdMapping(smallSteps, workflows);

// ============================================================================
// GRAPH STRUCTURE - Connections between nodes
// ============================================================================

export const connections = deriveConnectionsFromWorkflows(workflows);

export const edgesData = connections.map(([from, to]) => {
  let label = '';
  if (from === 'source') label = 'source';
  if (to === 'tail') label = 'target';
  return { from, to, label };
});

// ============================================================================
// TRAVERSALS - Dynamically generated from workflows
// ============================================================================

export const traversals = Object.keys(workflows).reduce((acc, workflowId) => {
  acc[workflowId] = getWorkflowTraversal(workflowId, workflows);
  return acc;
}, {});

// ============================================================================
// EDGE CONFIGURATIONS - Keep minimal for now
// ============================================================================

export const edgeConfigurations = {
    // === Node 3 ↔ Node 11 Curves ===
    'node3|node11': {
      isCurved: true,
      curveType: 'up',
      curveOffset: 200,
      controlPoint: 'mid-up'
    },
    'node11|node3': {
      isCurved: true,
      curveType: 'up',
      curveOffset: 200,
      controlPoint: 'mid-up'
    },
  
    // === Node 8 ↔ Node 2 Curves ===
    'node8|node2': {
      isCurved: true,
      curveType: 'right',
      curveOffset: 120,
      controlPoint: 'mid-right'
    },
    'node2|node8': {
      isCurved: true,
      curveType: 'right',
      curveOffset: 120,
      controlPoint: 'mid-right'
    }
  };
  

// ============================================================================
// DYNAMIC COLOR ASSIGNMENT
// ============================================================================

export const workflowColors = generateWorkflowColors(Object.keys(workflows));


