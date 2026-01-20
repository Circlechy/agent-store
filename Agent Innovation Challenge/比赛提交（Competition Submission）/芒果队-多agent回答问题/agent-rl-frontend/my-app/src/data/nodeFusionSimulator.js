// data/nodeFusionSimulator.js
import { bigNodeData } from './realDataMath';

/**
 * Check if a step is temporary (analysis, backtrack, or correction step)
 * These don't create permanent nodes
 */
function isTemporaryStep(stepId) {
  return stepId.includes('-') || /\d+b$/.test(stepId) || stepId === 'tail';
}

/**
 * Generate decision text explaining why a node was created or merged
 */
function generateDecisionText(step, targetNode, isNewNode, workflow, bigNodeData) {
  const stepDesc = step.description;
  const nodeLabel = bigNodeData[targetNode]?.label || targetNode;
  
  // Extract workflow number from workflow.id (e.g., "workflow1" -> "1")
  const workflowNumber = workflow.id.replace('workflow', '');
  const workflowDisplay = `Workflow ${workflowNumber}: ${workflow.title}`;
  
  if (isNewNode) {
    return {
      action: 'CREATE',
      summary: `创建新的节点${nodeLabel}`,
      details: `步骤“${stepDesc}”引入了一种新的任务类型，该类型与任何现有节点都不匹配。正在创建 ${targetNode}。`,
      workflow: workflowDisplay
    };
  } else {
    return {
      action: 'MERGE',
      summary: `合并到现有的${nodeLabel}`,
      details: `步骤 “${stepDesc}” 与${nodeLabel}的任务类别匹配。正在添加到现有节点。`,
      workflow: workflowDisplay
    };
  }
}

/**
 * Clone current graph state for animation frame
 */
function cloneGraphState(existingNodes, nodeSteps, connections) {
  return {
    nodes: new Set(existingNodes),
    steps: JSON.parse(JSON.stringify(nodeSteps)),
    connections: [...connections]
  };
}

/**
 * Derive connections from nodes that exist at this point
 * Returns array of connection objects with workflow information
 */
function deriveCurrentConnections(nodeSteps, existingNodes, workflows, allBacktrackConnections = []) {
  const connectionMap = new Map(); // Map of "from|to" -> Set of workflows
  const backtrackMap = new Map(); // Map of "from|to" -> Set of workflows for backtrack edges
  
  // For each node's steps, trace workflow paths
  Object.entries(nodeSteps).forEach(([nodeId, steps]) => {
    steps.forEach(step => {
      const workflow = step.workflow;
      
      // Add connection from source to first nodes
      if (step.isFirstInWorkflow && existingNodes.has('source')) {
        const key = 'source|' + nodeId;
        if (!connectionMap.has(key)) {
          connectionMap.set(key, new Set());
        }
        connectionMap.get(key).add(workflow);
      }
      
      // Add connection to tail from last nodes
      if (step.isLastInWorkflow && existingNodes.has('tail')) {
        const key = nodeId + '|tail';
        if (!connectionMap.has(key)) {
          connectionMap.set(key, new Set());
        }
        connectionMap.get(key).add(workflow);
      }
      
      // Add connections between consecutive steps in workflow
      if (step.previousNode && existingNodes.has(step.previousNode) && step.previousNode !== nodeId) {
        const key = step.previousNode + '|' + nodeId;
        if (!connectionMap.has(key)) {
          connectionMap.set(key, new Set());
        }
        connectionMap.get(key).add(workflow);
      }
    });
  });
  
  // Use pre-calculated backtrack connections
  allBacktrackConnections.forEach(backtrackConn => {
    const key = backtrackConn.from + '|' + backtrackConn.to;
    backtrackMap.set(key, new Set(backtrackConn.workflows));
  });
  
  // Process workflows for forward connections only
  Object.values(workflows).forEach(workflow => {
    let previousNode = 'source';
    
    workflow.steps.forEach(step => {
      const currentNode = step.nodeMapping;
      
      // Update previous node for forward connections
      if (step.correct || step.isCorrection) {
        previousNode = currentNode;
      } else if (step.correct === false && step.errorDetails?.backtrackTo) {
        previousNode = step.errorDetails.backtrackTo;
      }
    });
  });
  
  // Convert to array of connection objects
  const forwardConnections = Array.from(connectionMap.entries()).map(([key, workflows]) => {
    const [from, to] = key.split('|');
    return {
      from,
      to,
      workflows: Array.from(workflows),
      isBacktrack: false
    };
  });
  
  const backtrackConnections = Array.from(backtrackMap.entries()).map(([key, workflows]) => {
    const [from, to] = key.split('|');
    return {
      from,
      to,
      workflows: Array.from(workflows),
      isBacktrack: true
    };
  });
  
  return [...forwardConnections, ...backtrackConnections];
}

/**
 * Calculate all backtrack connections from all workflows
 */
function calculateAllBacktrackConnections(workflows) {
  const backtrackMap = new Map();
  
  Object.values(workflows).forEach(workflow => {
    workflow.steps.forEach(step => {
      // Check for backtrack connections from errorDetails.backtrackTo
      if (step.correct === false && step.errorDetails?.backtrackTo) {
        const backtrackTarget = step.errorDetails.backtrackTo;
        const key = step.nodeMapping + '|' + backtrackTarget;
        
        if (!backtrackMap.has(key)) {
          backtrackMap.set(key, new Set());
        }
        backtrackMap.get(key).add(workflow.id);
      }
      
      // Check for backtrack connections from analyze steps (from/to fields)
      if (step.backtrack && step.from && step.to) {
        const key = step.from + '|' + step.to;
        
        if (!backtrackMap.has(key)) {
          backtrackMap.set(key, new Set());
        }
        backtrackMap.get(key).add(workflow.id);
      }
    });
  });
  
  return Array.from(backtrackMap.entries()).map(([key, workflows]) => {
    const [from, to] = key.split('|');
    return {
      from,
      to,
      workflows: Array.from(workflows),
      isBacktrack: true
    };
  });
}

/**
 * Main function: Simulate node fusion process and generate animation frames
 */
export function simulateNodeFusion(workflows, bigNodeDataInput = bigNodeData) {
  const frames = [];
  const existingNodes = new Set(['source', 'tail']);
  const nodeSteps = { source: [], tail: [] };
  let connections = [];
  
  // Calculate all backtrack connections once at the beginning
  const allBacktrackConnections = calculateAllBacktrackConnections(workflows);
  
  // Add initial frame showing just source and tail
  frames.push({
    frameId: 0,
    action: 'INIT',
    decisionText: {
      action: 'INIT',
      summary: '初始化图结构',
      details: '从源节点和目标节点开始。准备处理工作流。',
      workflow: null
    },
    targetNode: null,
    highlightNode: null,
    graphState: cloneGraphState(existingNodes, nodeSteps, connections),
    step: null,
    workflow: null
  });
  
  // Process each workflow in order
  const workflowArray = Object.values(workflows).sort((a, b) => {
    // Sort by workflow ID (workflow1, workflow2, etc.)
    return a.id.localeCompare(b.id);
  });
  
  workflowArray.forEach((workflow, wfIndex) => {
    // Track previous node for this workflow to create connections
    let previousNodeInWorkflow = 'source';
    
    workflow.steps.forEach((step, stepIndex) => {
      // Skip temporary steps (analysis, corrections, etc.)
      if (isTemporaryStep(step.stepId)) {
        return;
      }
      
      const targetNode = step.nodeMapping;
      
      // Skip if mapping to source or tail
      if (targetNode === 'source' || targetNode === 'tail') {
        return;
      }
      
      const isNewNode = !existingNodes.has(targetNode);
      const decisionText = generateDecisionText(step, targetNode, isNewNode, workflow, bigNodeDataInput);
      
      // Mark if this is first/last step in workflow for connection logic
      const isFirstRealStep = stepIndex === 0 || workflow.steps.slice(0, stepIndex).every(s => isTemporaryStep(s.stepId));
      const isLastRealStep = stepIndex === workflow.steps.length - 1 || workflow.steps.slice(stepIndex + 1).every(s => isTemporaryStep(s.stepId));
      
      // Create enriched step data
      const enrichedStep = {
        ...step,
        workflow: workflow.id,
        isFirstInWorkflow: isFirstRealStep,
        isLastInWorkflow: isLastRealStep,
        previousNode: previousNodeInWorkflow
      };
      
      // If new node, create it
      if (isNewNode) {
        existingNodes.add(targetNode);
        nodeSteps[targetNode] = [];
      }
      
      // Add step to node
      nodeSteps[targetNode].push(enrichedStep);
      
      // Update connections
      connections = deriveCurrentConnections(nodeSteps, existingNodes, workflows, allBacktrackConnections);
      
      // Create animation frame
      frames.push({
        frameId: frames.length,
        action: isNewNode ? 'CREATE' : 'MERGE',
        decisionText: decisionText,
        targetNode: targetNode,
        highlightNode: targetNode,
        graphState: cloneGraphState(existingNodes, nodeSteps, connections),
        step: enrichedStep,
        workflow: workflow
      });
      
      // Update previous node for next iteration
      previousNodeInWorkflow = targetNode;
    });
  });
  
  // Add final frame showing complete graph
  frames.push({
    frameId: frames.length,
    action: 'COMPLETE',
    decisionText: {
      action: 'COMPLETE',
      summary: '图结构构建完成',
      details: `所有 ${workflowArray.length} 工作流已处理。最终图包含 ${existingNodes.size} 个节点，共 ${Object.values(nodeSteps).reduce((sum, steps) => sum + steps.length, 0)} 步。`,
      workflow: null
    },
    targetNode: null,
    highlightNode: null,
    graphState: cloneGraphState(existingNodes, nodeSteps, connections),
    step: null,
    workflow: null
  });
  
  return frames;
}

