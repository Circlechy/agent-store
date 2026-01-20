import { 
    buildSmallStepsFromWorkflows, 
    buildStepIdToNodeIdMapping, 
    getWorkflowTraversal,
    deriveConnectionsFromWorkflows
  } from './workflowHelpers';
  
  import { generateWorkflowColors } from '../components/utils/graphHelpers';

// ============================================================================
// BIG NODES - High-level task categories with layered positions
// ============================================================================
export const bigNodeData = {
  // Layer 0: Source
  source: { id: 'source', label: 'SOURCE', color: '#A7F3D0', isSpecial: true, x: -600, y: 0 },
  
  // Layer 1: First processing nodes (1, 4, 5, 7, 9)
  node1: { id: 'node1', label: '节点 1: 互质条件识别', color: '#F0F0F0', x: -350, y: -300 },
  node4: { id: 'node4', label: '节点 4: 根据题目条件推理', labelHistory: ['根据正因数个数推理', '根据题目条件推理'], color: '#F0F0F0', x: -350, y: -150 },
  node5: { id: 'node5', label: '节点 5: 编写不等式', labelHistory: ['写不等式', '编写不等式', ], color: '#F0F0F0', x: -350, y: 0 },
  node7: { id: 'node7', label: '节点 7: 判断数字是否为质数', labelHistory: ['逐个数字判断质数', '判断数字是否为质数', ], color: '#F0F0F0', x: -350, y: 150 },
  node9: { id: 'node9', label: '节点 9: 列举数字', labelHistory: ['识别并统计因数个数', '根据情况列举数字', '列举数字'], color: '#F0F0F0', x: -350, y: 300 },
  
  // Layer 2: Middle processing nodes (2, 6, 8)
  node2: { id: 'node2', label: '节点 2: 确定数字范围', labelHistory: ['确定答案范围', '确定数字范围'], color: '#F0F0F0', x: -50, y: -180 },
  node6: { id: 'node6', label: '节点 6: 统计答案正确情况', labelHistory: ['统计平方数个数', '统计答案正确情况'], color: '#F0F0F0', x: -50, y: 0 },
  node8: { id: 'node8', label: '节点 8: 计算公式结果', labelHistory: ['计算结果', '计算公式结果'], color: '#F0F0F0', x: -50, y: 180 },
  
  // Layer 3: Final processing nodes (3, 10)
  node3: { id: 'node3', label: '节点 3: 统计/验证代理', color: '#F0F0F0', x: 250, y: -60 },
  node10: { id: 'node10', label: '节点 10: 最小值确定', color: '#F0F0F0', x: 250, y: 90 },
  
  // Layer 4: Target
  tail: { id: 'tail', label: 'TARGET', color: '#FECACA', isSpecial: true, x: 550, y: 0 },
};

// ============================================================================
// WORKFLOW DEFINITIONS - Two-pass structure for error workflows
// ============================================================================

export const baseWorkflows = {
    workflow1: {
        id: 'workflow1',
        title: '与 20! 互质的最小整数',
        problem: '找出大于 1 且与前 20 个正整数的乘积互质的最小正整数。',
        expectedAnswer: '23',
        errorType: null,
        steps: [
          {
            stepId: '1',
            question: '怎样判断一个数与 20! 是否互质？',
            description: '明确互质条件',
            reasoning: '若一个数与 20! 互质，则它不能被 2, 3, 5, 7, 11, 13, 17, 19 中任一质数整除。',
            nodeMapping: 'node1',
            correct: true,
            pass: 1,
          },
          {
            stepId: '2',
            question: '有什么范围会把整数会当互质？',
            description: '确定答案范围',
            reasoning: '应找最小的质数且>20。因为若是合数则必含某个≤20的质因子。',
            nodeMapping: 'node2',
            correct: true,
            pass: 1,
          },
          {
            stepId: '3',
            question: '如何验证候选数与20!互质？',
            description: '验证互质性质',
            reasoning: '列出>20的最小质数：23。验证 23与20!无公因子。',
            nodeMapping: 'node3',
            correct: true,
            pass: 1,
          },
          {
            stepId: 'tail',
            question: '最终答案是什么？',
            description: '确认最终答案',
            reasoning: '综上所述，符合条件的最小正整数为 23。',
            nodeMapping: 'tail',
            correct: true,
            pass: 1,
          },
        ],
    },
    workflow2: {
        id: 'workflow2',
        title: '奇数个正因数的整数个数',
        problem: '有多少个小于 103 的正整数有奇数个正因数？',
        expectedAnswer: '10',
        errorType: null,
        steps: [
          {
            stepId: '4',
            question: '什么样的数字才会有奇数个正因数？',
            description: '根据正因数个数推理',
            reasoning: '正整数有奇数个正因数当且仅当它是完全平方数。',
            nodeMapping: 'node4',
            correct: true,
            pass: 1,
          },
          {
            stepId: '5',
            question: '根据这个定义，怎样写出相应的数学表达式？',
            description: '写不等式，找出完全平方数 ',
            reasoning: 'n为正整数且 n² < 103，n ≤ 10。',
            nodeMapping: 'node5',
            correct: true,
            pass: 1,
          },
          {
            stepId: '6',
            question: '不等式有几个数字？',
            description: '统计完全平方数个数',
            reasoning: '满足条件的平方数为 1, 2, …, 10，共 10 个。',
            nodeMapping: 'node6',
            correct: true,
            pass: 1,
          },
          {
            stepId: 'tail',
            question: '最终答案是什么？',
            description: '确认最终答案',
            reasoning: '因此，小于 103 且有奇数个正因数的正整数共有 10 个。',
            nodeMapping: 'tail',
            correct: true,
            pass: 1,
          },
        ],
    },
    workflow3: {
    "id": "workflow3",
    "title": "平方数相差 1 或 2 的质数之和",
    "problem": "求出 100 到 200 之间的质数之和，这些质数比完全平方数大 1 或 2。",
    "expectedAnswer": "298",
    "errorType": "reasoning-chain-error",
    "steps": [
      // Pass 1: Wrong path - error occurs at step 8
      {
        "stepId": "7",
        "question": "题目条件对应的不等式是什么？",
        "description": "写出不等式范围",
        "reasoning": "不等式写成 100 ≤ n² + 1 ≤ 200 或 100 ≤ n² + 2 ≤ 200。",
        "nodeMapping": "node5",
        "correct": true,
        "pass": 1
      },
      {
        "stepId": "8",
        "question": "根据不等式，n的取值范围是什么？",
        "description": "确定 n 的取值范围",
        "reasoning": "n为正整数，则根据不等式：10≤n≤13, 推得 n 为 10, 11, 12, 13。",
        "nodeMapping": "node2",
        "correct": false,
        "pass": 1,
        "errorType": "reasoning-lapse",
        "errorDetails": {
          "issue": "错误地省略了 n = 14，导致遗漏部分候选值。",
          "discoveryMoment": "范围计算时遗漏了边界值。"
        }
      },
      {
        "stepId": "9",
        "question": "这些符合条件的数字哪些是质数？",
        "description": "逐个计算并判断质数",
        "reasoning": "根据范围，检查 n=10, 11, 12, 13，对应的 n²+1 与 n²+2。得到 101 为符合条件的质数。",
        "nodeMapping": "node7",
        "correct": true,
        "pass": 1
      },
      {
        "stepId": "10",
        "question": "所有符合条件的质数之和是多少？",
        "description": "计算结果",
        "reasoning": "仅有一个质数 101，因此和为 101。",
        "nodeMapping": "node8",
        "correct": true,
        "pass": 1
      },
      {
        "stepId": "tail",
        "question": "答案是否合理？",
        "description": "在目标节点验证答案",
        "reasoning": "验证时发现结果 101 明显偏小；检查发现可能遗漏了候选值，需回溯定位问题来源。",
        "nodeMapping": "tail",
        "correct": false,
        "pass": 1,
        "errorType": "reasoning-lapse",
        "errorDetails": {
          "issue": "结果异常偏小，可能遗漏候选值。",
          "discoveryMoment": "在目标节点验证阶段发现异常。",
          "backtrackTo": "node8"
        },
        "backtrack": true
      },
      // Hidden analyze steps
      {
        "stepId": "10-analyze",
        "description": "回溯修理错误",
        "reasoning": "因为答案错了，所以得回溯到node8分析计算步骤。",
        "nodeMapping": "node8",
        "from": "tail",
        "to": "node8",
        "correct": false,
        "pass": null,
        "backtrack": true
      },
      {
        "stepId": "9-analyze",
        "description": "回溯修理错误",
        "reasoning": "因为答案错了，所以得回溯到node7分析质数判断步骤。",
        "nodeMapping": "node7",
        "from": "node8",
        "to": "node7",
        "correct": false,
        "pass": null,
        "backtrack": true
      },
      {
        "stepId": "8-analyze",
        "description": "回溯修理错误",
        "reasoning": "因为答案错了，所以得回溯到node2分析n的取值范围。",
        "nodeMapping": "node2",
        "from": "node7",
        "to": "node2",
        "correct": false,
        "pass": null,
        "backtrack": true
      },
      {
        "stepId": "7-analyze",
        "description": "回溯修理错误",
        "reasoning": "因为答案错了，所以得回溯到node5分析不等式步骤。",
        "nodeMapping": "node5",
        "from": "node2",
        "to": "node5",
        "correct": false,
        "pass": null,
        "backtrack": true
      },
      {
        "stepId": "return-to-source",
        "description": "回到起点重新开始",
        "reasoning": "完成错误分析后，返回source节点开始第二轮推理。",
        "nodeMapping": "source",
        "from": "node5",
        "to": "source",
        "correct": false,
        "pass": null,
        "backtrack": true
      },
      // Pass 2: Correct path
      {
        "stepId": "7-b",
        "question": "题目条件对应的不等式是什么？（第二轮）",
        "description": "写出不等式范围（第二轮）",
        "reasoning": "不等式写成 100 ≤ n² + 1 ≤ 200 或 100 ≤ n² + 2 ≤ 200。",
        "nodeMapping": "node5",
        "correct": true,
        "pass": 2
      },
      {
        "stepId": "8-b",
        "question": "修正后n的正确范围是什么？（第二轮）",
        "description": "修正 n 的取值范围（第二轮）",
        "reasoning": "重新审查不等式，n为正整数，则根据不等式：10≤n≤14，n为10，11，12，13，14。",
        "nodeMapping": "node2",
        "correct": true,
        "pass": 2,
        "isCorrection": true
      },
      {
        "stepId": "9-b",
        "question": "使用完整范围后有哪些质数符合条件？（第二轮）",
        "description": "重新判断所有候选质数（第二轮）",
        "reasoning": "重新检查 n=10–14 的 n²+1 与 n²+2，发现 101 和 197 为符合条件的质数。",
        "nodeMapping": "node7",
        "correct": true,
        "pass": 2,
        "isCorrection": true
      },
      {
        "stepId": "10-b",
        "question": "修正后所有质数之和是多少？（第二轮）",
        "description": "重新计算结果（第二轮）",
        "reasoning": "符合条件的素数为101与197。求和：101+197=298。",
        "nodeMapping": "node8",
        "correct": true,
        "pass": 2,
        "isCorrection": true
      },
      {
        "stepId": "tail-final",
        "question": "修正后的答案正确吗？（第二轮）",
        "description": "确认最终正确答案（第二轮）",
        "reasoning": "修正后结果为 298，验证通过，逻辑与数值一致。",
        "nodeMapping": "tail",
        "correct": true,
        "pass": 2
      }
    ]
    },
    workflow4: {
        id: 'workflow4',
        title: '7 的整数因数个数',
        problem: '7 有多少个整数因数？',
        expectedAnswer: '4',
        errorType: null,
        steps: [
          {
            stepId: '11',
            question: '7是什么性质的数字？',
            description: '识别数字性质',
            reasoning: '7为质数，只能被 1 和自身整除。',
            nodeMapping: 'node7',
            correct: true,
            pass: 1,
          },
          {
            stepId: '12',
            question: '质数有几个因数？',
            description: '识别并统计因数个数',
            reasoning: '因数包含正负两类，7一共有-1，-7，1，7，总计4个因数。',
            nodeMapping: 'node9',
            correct: true,
            pass: 1,
          },
          {
            stepId: 'tail',
            question: '最终答案是什么？',
            description: '确认最终答案',
            reasoning: '因此，7 的整数因数共有 4 个。',
            nodeMapping: 'tail',
            correct: true,
            pass: 1,
          },
        ],
    },
    workflow5: {
        "id": "workflow5",
        "title": "p + 12 为质数的概率（错误代理使用）",
        "problem": "设 p 是 40 到 60 之间的一个质数。p + 12 也是质数的概率是多少？用普通分数表示答案。",
        "expectedAnswer": "3/5",
        "errorType": "initial-mistake",
        "steps": [
          // Pass 1: Wrong path - error occurs at step 14-wrong
          {
            "stepId": "13-wrong",
            "question": "范围中有几个质数？",
            "description": "列出质数",
            "reasoning": "列出 40 ≤ p ≤ 60 的质数为 41, 43, 47, 53, 59五种情况。",
            "nodeMapping": "node9",
            "correct": true,
            "pass": 1
          },
          {
            "stepId": "14-wrong",
            "question": "p+12是否为质数？",
            "description": "识别数字性质，判断数字是否为质数",
            "reasoning": "数字p+12有53，55，59，65，71五种情况。统计代理报告其中 53, 59 为质数。",
            "nodeMapping": "node3",
            "correct": false,
            "pass": 1,
            "errorType": "reasoning-lapse",
            "errorDetails": {
              "issue": "错误代理使用：统计代理代替了验证代理，导致质数判断不准确。",
              "discoveryMoment": "使用了不具备质数验证功能的统计代理。"
            }
          },
          {
            "stepId": "15-wrong",
            "question": "p为质数，p+12也为质数的概率是多少？",
            "description": "计算概率",
            "reasoning": "依据统计代理的结果，5 个 p 中有 2 个成功，概率为 2/5。",
            "nodeMapping": "node6",
            "correct": true,
            "pass": 1
          },
          {
            "stepId": "tail",
            "question": "答案是否合理？",
            "description": "在目标节点验证答案",
            "reasoning": "验证时发现结果 2/5 与逻辑不符。触发回溯流程分析问题来源。",
            "nodeMapping": "tail",
            "correct": false,
            "pass": 1,
            "errorType": "reasoning-lapse",
            "errorDetails": {
              "issue": "概率结果异常。",
              "discoveryMoment": "在目标节点验证阶段发现错误。",
              "backtrackTo": "node6"
            },
            "backtrack": true
          },
          // Hidden analyze steps
          {
            "stepId": "15-analyze",
            "description": "回溯修理错误",
            "reasoning": "因为答案错了，所以得回溯到node6分析计算步骤。",
            "nodeMapping": "node6",
            "from": "tail",
            "to": "node6",
            "correct": false,
            "pass": null,
            "backtrack": true
          },
          {
            "stepId": "14-analyze",
            "description": "回溯修理错误",
            "reasoning": "因为答案错了，所以得回溯到node3分析代理使用情况。",
            "nodeMapping": "node3",
            "from": "node6",
            "to": "node3",
            "correct": false,
            "pass": null,
            "backtrack": true
          },
          {
            "stepId": "13-analyze",
            "description": "回溯修理错误",
            "reasoning": "因为答案错了，所以得回溯到node9分析质数列举步骤。",
            "nodeMapping": "node9",
            "from": "node3",
            "to": "node9",
            "correct": false,
            "pass": null,
            "backtrack": true
          },
          {
            "stepId": "return-to-source",
            "description": "回到起点重新开始",
            "reasoning": "完成错误分析后，返回source节点开始第二轮推理。",
            "nodeMapping": "source",
            "from": "node9",
            "to": "source",
            "correct": false,
            "pass": null,
            "backtrack": true
          },
          // Pass 2: Correct path
          {
            "stepId": "13",
            "question": "范围中有几个质数？（第二轮）",
            "description": "列出质数（第二轮）",
            "reasoning": "列出 40 ≤ p ≤ 60 的质数为 41, 43, 47, 53, 59五种情况。",
            "nodeMapping": "node9",
            "correct": true,
            "pass": 2
          },
          {
            "stepId": "14",
            "question": "p+12是否为质数？（第二轮）",
            "description": "识别数字性质，判断数字是否为质数（第二轮）",
            "reasoning": "数字p+12有53，55，59，65，71五种情况，53，59，71是质数。",
            "nodeMapping": "node7",
            "correct": true,
            "pass": 2,
            "isCorrection": true
          },
          {
            "stepId": "15",
            "question": "p为质数，p+12也为质数的概率是多少？（第二轮）",
            "description": "重新统计正确情况并给出概率（第二轮）",
            "reasoning": "修正后共有 5 个质数 p，p+12质数情况有3个，p质数情况有5个，概率为3/5。",
            "nodeMapping": "node6",
            "correct": true,
            "pass": 2,
            "isCorrection": true
          },
          {
            "stepId": "tail-final",
            "question": "修正后的答案正确吗？（第二轮）",
            "description": "确认最终答案（第二轮）",
            "reasoning": "改用正确代理后结果为 3/5，逻辑与数值一致。",
            "nodeMapping": "tail",
            "correct": true,
            "pass": 2
          }
        ]
    },
    workflow6: {
        "id": "workflow6",
        "title": "加倍减去 13.7 后结果大于 125.28 的最小整数",
        "problem": "一个数加倍，然后减去 13.7。结果大于 125.28。满足这个条件的最小整数是多少？",
        "expectedAnswer": "70",
        "errorType": null,
        "steps": [
          {
            "stepId": "16",
            "question": "题目条件对应的不等式是什么？",
            "description": "编写不等式",
            "reasoning": "根据题意写出不等式：2x - 13.7 > 125.28。",
            "nodeMapping": "node5",
            "correct": true,
            "pass": 1
          },
          {
            "stepId": "17",
            "question": "未知数范围是什么？",
            "description": "确定未知数范围",
            "reasoning": "移项得到 2x > 138.98，因此 x > 69.49。",
            "nodeMapping": "node2",
            "correct": true,
            "pass": 1
          },
          {
            "stepId": "18",
            "question": "满足条件的最小整数是多少？",
            "description": "获取正整数结果",
            "reasoning": "大于 69.49 的最小整数为 70。",
            "nodeMapping": "node10",
            "correct": true,
            "pass": 1
          },
          {
            "stepId": "tail",
            "question": "最小整数是什么？",
            "description": "确认最终答案",
            "reasoning": "因此，满足条件的最小整数为 70。",
            "nodeMapping": "tail",
            "correct": true,
            "pass": 1
          }
        ]
    },
    workflow7: {
        "id": "workflow7",
        "title": "具有 3 个不同质因数的最小完全平方数",
        "problem": "具有 3 个不同质因数的最小完全平方数是多少？",
        "expectedAnswer": "900",
        "errorType": "reasoning-chain-error",
        "steps": [
          // Pass 1: Wrong path - error occurs at step 20
          {
            "stepId": "19",
            "question": "具有3个质因数的完全平方数的条件是什么？",
            "description": "根据条件推理",
            "reasoning": "一个数若为完全平方数，则其素因数分解中每个质因子的指数均为偶数；要使其含有 3 个不同质因数且尽可能小，应选择 3 个较小的质数并使其幂为 2。",
            "nodeMapping": "node4",
            "correct": true,
            "pass": 1
          },
          {
            "stepId": "20",
            "question": "3个最小质数是什么？",
            "description": "获取最小质数",
            "reasoning": "选择三个质数为 2、3、7，准备构造最小的完全平方数。",
            "nodeMapping": "node9",
            "correct": false,
            "pass": 1,
            "errorType": "reasoning-lapse",
            "errorDetails": {
              "issue": "质数集合选择不最小化。选择了 7 而非 5，导致结果偏大。",
              "discoveryMoment": "选择质数时未按最小顺序。"
            }
          },
          {
            "stepId": "21",
            "question": "怎样计算平方数？",
            "description": "计算完全平方数",
            "reasoning": "根据选择的质数计算：(2×3×7)² = 1764。",
            "nodeMapping": "node8",
            "correct": true,
            "pass": 1
          },
          {
            "stepId": "tail",
            "question": "1764是最小的吗？",
            "description": "在目标节点验证答案",
            "reasoning": "验证时发现 1764 不是最小值；存在由更小质数组合构成的更小完全平方数，需回溯定位问题来源。",
            "nodeMapping": "tail",
            "correct": false,
            "pass": 1,
            "errorType": "reasoning-lapse",
            "errorDetails": {
              "issue": "结果不满足'最小'要求。",
              "discoveryMoment": "在目标节点进行最小性检验时发现异常。",
              "backtrackTo": "node8"
            },
            "backtrack": true
          },
          // Hidden analyze steps
          {
            "stepId": "21-analyze",
            "description": "回溯修理错误",
            "reasoning": "因为答案错了，所以得回溯到node8分析计算步骤。",
            "nodeMapping": "node8",
            "from": "tail",
            "to": "node8",
            "correct": false,
            "pass": null,
            "backtrack": true
          },
          {
            "stepId": "20-analyze",
            "description": "回溯修理错误",
            "reasoning": "因为答案错了，所以得回溯到node9分析质数选择。",
            "nodeMapping": "node9",
            "from": "node8",
            "to": "node9",
            "correct": false,
            "pass": null,
            "backtrack": true
          },
          {
            "stepId": "19-analyze",
            "description": "回溯修理错误",
            "reasoning": "因为答案错了，所以得回溯到node4分析推理条件。",
            "nodeMapping": "node4",
            "from": "node9",
            "to": "node4",
            "correct": false,
            "pass": null,
            "backtrack": true
          },
          {
            "stepId": "return-to-source",
            "description": "回到起点重新开始",
            "reasoning": "完成错误分析后，返回source节点开始第二轮推理。",
            "nodeMapping": "source",
            "from": "node4",
            "to": "source",
            "correct": false,
            "pass": null,
            "backtrack": true
          },
          // Pass 2: Correct path
          {
            "stepId": "19-b",
            "question": "具有3个质因数的完全平方数的条件是什么？（第二轮）",
            "description": "根据条件推理（第二轮）",
            "reasoning": "一个数若为完全平方数，则其素因数分解中每个质因子的指数均为偶数；要使其含有 3 个不同质因数且尽可能小，应选择 3 个较小的质数并使其幂为 2。",
            "nodeMapping": "node4",
            "correct": true,
            "pass": 2
          },
          {
            "stepId": "20-b",
            "question": "3个最小质数是什么？（第二轮）",
            "description": "修正最小质数选择（第二轮）",
            "reasoning": "改为选择三个最小的不同质数 2、3、5。",
            "nodeMapping": "node9",
            "correct": true,
            "pass": 2,
            "isCorrection": true
          },
          {
            "stepId": "21-b",
            "question": "怎样计算平方数？（第二轮）",
            "description": "重新计算完全平方数（第二轮）",
            "reasoning": "根据修正的质数集合计算：(2×3×5)² = 900。",
            "nodeMapping": "node8",
            "correct": true,
            "pass": 2,
            "isCorrection": true
          },
          {
            "stepId": "tail-final",
            "question": "900是最小的完全平方数吗？（第二轮）",
            "description": "确认最终正确答案（第二轮）",
            "reasoning": "900 满足'完全平方数且含 3 个不同质因数'，并且在该条件下最小。",
            "nodeMapping": "tail",
            "correct": true,
            "pass": 2
          }
        ]
    }
}

export const workflows = baseWorkflows;
// ============================================================================
// DERIVED DATA - Build from workflows
// ============================================================================

export const smallSteps = buildSmallStepsFromWorkflows(workflows);
// Add empty arrays for source and tail nodes (they have no internal steps)
smallSteps.source = [];
smallSteps.tail = [];


export const stepIdToNodeId = buildStepIdToNodeIdMapping(smallSteps, workflows);

// ============================================================================
// GRAPH STRUCTURE - Connections between nodes
// ============================================================================

// Connection pairs for graph layout computation
// Automatically derived from workflow definitions - no manual maintenance needed!
export const connections = deriveConnectionsFromWorkflows(workflows);

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
export const traversals = Object.keys(workflows).reduce((acc, workflowId) => {
  acc[workflowId] = getWorkflowTraversal(workflowId, workflows);
  return acc;
}, {});

// ============================================================================
// EDGE CONFIGURATIONS - Curved edges for this dataset
// ============================================================================

export const edgeConfigurations = {
  'node4|node9': {
    isCurved: true,
    curveType: 'right',
    curveOffset: 150,
    controlPoint: 'mid-right'
  },
  'node9|node4': {
    isCurved: true,
    curveType: 'right',
    curveOffset: 150,
    controlPoint: 'mid-right'
  },
  'node9|tail': {
    isCurved: true,
    curveType: 'up',
    curveOffset: 150,
    controlPoint: 'mid-up'
  },
  'node8|tail': {
    isCurved: true,
    curveType: 'up',
    curveOffset: 70,
    controlPoint: 'mid-up'
  },
  'tail|node8': {
    isCurved: true,
    curveType: 'up',
    curveOffset: 250,
    controlPoint: 'mid-up'
  }
};

// ============================================================================
// DYNAMIC COLOR ASSIGNMENT
// ============================================================================

// Generate workflow colors dynamically based on workflow IDs
export const workflowColors = generateWorkflowColors(Object.keys(workflows));

