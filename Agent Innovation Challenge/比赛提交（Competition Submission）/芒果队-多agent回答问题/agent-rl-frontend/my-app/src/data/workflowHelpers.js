// data/workflowHelpers.js
import dagre from 'dagre';

/**
 * Layout configuration - adjust these to optimize the graph appearance
 */
export const LAYOUT_CONFIG = {
  RANK_SEP: 400,     // Horizontal distance between layers (ranksep in dagre)
  NODE_SEP: 180,     // Vertical distance between nodes in same layer (nodesep in dagre)
  MARGIN: 50,        // Graph margin
};

/**
 * Calculate the actual rendered size of a node based on its content
 * This matches the calculation in WorkflowGraph.js
 * @param {Object} node - Node data
 * @param {Array} steps - Steps contained in this node
 * @returns {number} - Diameter of the node (2 * radius)
 */
function calculateNodeSize(node, steps = []) {
  const smallNodeRadius = 15;
  const verticalSpacing = 35;
  const bigNodeRadiusPadding = 50;
  
  // Special nodes (source/tail) have a fixed smaller radius
  if (node.isSpecial) {
    return 50 * 2; // diameter = radius * 2 = 100
  }
  
  // Calculate radius based on number of steps
  const clusterHeight = steps.length > 0
    ? verticalSpacing * (steps.length - 1) + smallNodeRadius * 2
    : smallNodeRadius * 2;
  
  const radius = clusterHeight / 2 + bigNodeRadiusPadding;
  return radius * 2; // Return diameter
}

/**
 * Compute node positions using Dagre layout
 * Dagre is specifically designed for directed graphs and handles DAG layouts excellently
 * @param {Object} bigNodeData - Node metadata
 * @param {Array} connections - Array of [source, target] pairs
 * @param {Object} smallSteps - Optional: steps per node for accurate sizing
 * @returns {Object} - Map of nodeId -> {x, y}
 */
export function computeNodePositions(bigNodeData, connections, smallSteps = {}) {
  // Create a new directed graph
  const g = new dagre.graphlib.Graph();
  
  // Set graph properties
  g.setGraph({
    rankdir: 'LR',                    // Left to Right layout
    nodesep: LAYOUT_CONFIG.NODE_SEP,  // Vertical spacing between nodes in same layer
    ranksep: LAYOUT_CONFIG.RANK_SEP,  // Horizontal spacing between layers
    marginx: LAYOUT_CONFIG.MARGIN,
    marginy: LAYOUT_CONFIG.MARGIN,
    edgesep: 50,                      // Spacing between edges
  });
  
  // Default edge label (dagre requires this)
  g.setDefaultEdgeLabel(() => ({}));
  
  // Add nodes to the graph with their actual sizes
  Object.entries(bigNodeData).forEach(([id, node]) => {
    const steps = smallSteps[id] || [];
    const nodeSize = calculateNodeSize(node, steps);
    
    g.setNode(id, { 
      width: nodeSize, 
      height: nodeSize,
      label: node.label 
    });
  });
  
  // Add edges to the graph
  connections.forEach(([from, to]) => {
    g.setEdge(from, to);
  });
  
  // Compute the layout
  dagre.layout(g);
  
  // Extract positions and adjust coordinates
  // Dagre uses top-left corner positioning, we need center-based
  // Also adjust to match the existing coordinate system
  const positions = {};
  g.nodes().forEach(id => {
    const node = g.node(id);
    // Center the graph around (0, 0) for consistency with previous layout
    positions[id] = {
      x: node.x - 600,  // Adjust X to center horizontally
      y: node.y - 350   // Adjust Y to center vertically
    };
  });
  
  return positions;
}

/**
 * Build a map of all steps across all workflows, grouped by node
 * For each unique stepId, we use the "correct" version (the successful attempt)
 */
export function buildSmallStepsFromWorkflows(workflows) {
  const stepsByNode = {};
  const stepRegistry = {}; // Track all versions of each step
  
  // First pass: collect all step versions
  Object.values(workflows).forEach(workflow => {
    workflow.steps.forEach(step => {
      if (!stepRegistry[step.stepId]) {
        stepRegistry[step.stepId] = [];
      }
      stepRegistry[step.stepId].push({
        ...step,
        workflow: workflow.id,
      });
    });
  });
  
  // Second pass: for each stepId, pick the correct version
  Object.entries(stepRegistry).forEach(([stepId, versions]) => {
    // Skip steps with dashes (like verify, analyze, etc.) and correction steps (b suffix)
    // These are part of the traversal but not permanent nodes
    if (stepId.includes('-') || /\d+b$/.test(stepId)) {
      return;
    }
    
    // Prefer the corrected version if it exists, otherwise use the first
    const correctVersion = versions.find(v => v.correct === true) || versions[0];
    const nodeId = correctVersion.nodeMapping;
    
    if (!stepsByNode[nodeId]) {
      stepsByNode[nodeId] = [];
    }
    
    stepsByNode[nodeId].push({
      id: stepId,
      label: correctVersion.description,
      question: correctVersion.question,
      workflow: correctVersion.workflow,
      reasoning: correctVersion.reasoning,
      correct: true, // smallSteps represent the ideal tasks
      errorType: undefined, // smallSteps don't have errors
      errorDetails: undefined,
    });
  });
  
  return stepsByNode;
}

/**
 * Build stepId → nodeId mapping
 */
export function buildStepIdToNodeIdMapping(smallSteps, workflows) {
  const m = new Map();
  Object.entries(smallSteps).forEach(([nodeId, arr]) => {
    arr.forEach(s => m.set(s.id, nodeId));
  });
  // Also add corrected steps
  Object.values(workflows).forEach(workflow => {
    workflow.steps.forEach(step => {
      if (step.isCorrection) {
        m.set(step.stepId, step.nodeMapping);
      }
    });
  });
  return m;
}

/**
 * Generate traversal from a workflow
 * This converts a workflow's steps into a traversal path
 */
export function workflowToTraversal(workflow) {
  const traversal = [];
  
  workflow.steps.forEach((step, index) => {
    traversal.push({
      stepId: step.stepId,
      nodeMapping: step.nodeMapping, // Include nodeMapping directly
      correct: step.correct,
      errorType: step.errorType,
      errorDetails: step.errorDetails,
      isCorrection: step.isCorrection,
      propagatedError: step.propagatedError,
      question: step.question,
      description: step.description,
      reasoning: step.reasoning,
      pass: step.pass, // Include pass property
      error: step.error,
      // Carry-through optional visualization overrides so renderers can use them
      highlightColor: step.highlightColor,
      arrowColor: step.arrowColor,
    });
  });
  
  return traversal;
}

/**
 * Expand traversal with backtracking logic
 * Uses nodeMapping directly from steps to show the actual path taken,
 * including wrong paths that need correction
 * 
 * Steps can now have nodeMapping: 'tail' to represent verification at target.
 * Backtracking happens FROM tail when errors are discovered there.
 */
export function expandTraversal(base, { startNode = 'source' } = {}) {
  if (!Array.isArray(base) || base.length === 0) return [];
  const out = [];
  let cursor = startNode;
  let lastCorrectNode = startNode;

  // Add initial step from source to first node if starting from source
  if (startNode === 'source' && base.length > 0) {
    const firstNode = base[0].nodeMapping;
    out.push({
      id: 'source-to-first',
      from: 'source',
      to: firstNode,
      correct: true,
      description: '启动工作流程',
      reasoning: '从START节点开始工作流程',
      pass: 1,
    });
    cursor = firstNode;
    lastCorrectNode = firstNode;
  }

  for (let i = 0; i < base.length; i++) {
    const step = base[i];
    const stepNode = step.nodeMapping; // Use nodeMapping directly (can be 'tail')
    const from = cursor;
    const to = stepNode;

    const safeId = `${step.stepId}-step-${i}`;
    
    // Add the step movement
    const stepMove = {
      ...step,
      id: safeId,
      from: step.from || from, // Use explicit from if provided, otherwise use cursor
      to: step.to || to, // Use explicit to if provided, otherwise use stepNode
    };
    
    // Determine if this is the first base step after the synthetic source->first move
    const isFirstBaseStepAfterSource = (i === 0 && startNode === 'source');

    // Skip emitting no-op moves where from === to (unless it's an explicit backtrack step)
    // BUT always emit the very first base step so it appears alongside the source->first move
    if (!(stepMove.backtrack === true) && stepMove.from === stepMove.to && !isFirstBaseStepAfterSource) {
      // Do not advance cursor on a no-op forward step
    } else {
      out.push(stepMove);
      console.log("step", stepMove);
      cursor = stepMove.to;
    }

    // Update lastCorrectNode for truly correct steps (not corrections)
    if (step.correct === true && !step.isCorrection) {
      lastCorrectNode = to;
    } 
    // Handle steps that are already marked as backtrack steps
    else if (step.pass === null && step.backtrack === true) {
      // This is already a backtrack step, add it to output with explicit from/to
      const backtrackStep = {
        ...step,
        id: `${step.stepId}-backtrack-${i}`,
        from: step.from || from,
        to: step.to || to,
      };
      
      out.push(backtrackStep);
      console.log("bactrack step", backtrackStep);
      // Use step.to for backtrack steps, not the derived 'to' variable
      cursor = step.to || to;
    }
  }
  return out;
}

/**
 * Get traversal for a specific workflow
 */
export function getWorkflowTraversal(workflowId, workflows) {
  const workflow = workflows[workflowId];
  if (!workflow) return [];
  
  const base = workflowToTraversal(workflow);
  return expandTraversal(base, { 
    startNode: 'source',
    errorType: workflow.errorType 
  });
}

/**
 * Derive graph connections from workflows
 * Analyzes all workflow paths to determine which nodes connect to which
 * This eliminates the need to manually maintain a connections array
 * 
 * The graph structure includes ALL edges that can be traversed, including:
 * - Correct paths
 * - Incorrect paths (that lead to errors)
 * - Correction paths (backtracking and alternative routes)
 * - Steps with nodeMapping: 'tail' (verification at target)
 * 
 * @param {Object} workflows - All workflow definitions
 * @returns {Array} - Array of [from, to] connection pairs
 */
export function deriveConnectionsFromWorkflows(workflows) {
  const connectionSet = new Set();
  
  Object.values(workflows).forEach(workflow => {
    // Track previous node for each step
    let previousNode = 'source';
    
    workflow.steps.forEach((step, index) => {
      const currentNode = step.nodeMapping; // Can be 'tail'
      
      // Only add connections for successful steps (correct or corrections)
      // Incorrect steps that get backtracked don't create actual graph edges
      if (step.correct || step.isCorrection) {
        if (previousNode !== currentNode) {
          const connection = `${previousNode}|${currentNode}`;
          connectionSet.add(connection);
        }
        // Advance to the new node
        previousNode = currentNode;
      } else if (step.correct === false) {
        // After an incorrect step, backtrack without creating an edge
        if (step.errorDetails?.backtrackTo) {
          previousNode = step.errorDetails.backtrackTo;
        } else {
          // If no specific backtrack target, stay at current for the correction
          previousNode = currentNode;
        }
      }
    });
    
    // Add connection to tail from the last node
    // Only if we're not already at tail or source
    if (previousNode && previousNode !== 'source' && previousNode !== 'tail') {
      connectionSet.add(`${previousNode}|tail`);
    }
  });
  
  // Convert Set to array of [from, to] pairs
  const connections = Array.from(connectionSet).map(conn => conn.split('|'));
  
  // Sort for consistent ordering (source first, then alphabetically)
  connections.sort((a, b) => {
    if (a[0] === 'source') return -1;
    if (b[0] === 'source') return 1;
    if (a[1] === 'tail') return 1;
    if (b[1] === 'tail') return -1;
    return a[0].localeCompare(b[0]) || a[1].localeCompare(b[1]);
  });
  
  return connections;
}

// ============================================================================
// WORKFLOW COMPOSITION HELPERS - For building complex scenario workflows
// ============================================================================

/**
 * Clone workflow steps with an optional suffix
 * Useful for creating variations of workflows in composite scenarios
 * @param {Array} steps - Array of step objects to clone
 * @param {string} suffix - Optional suffix to append to stepId
 * @returns {Array} - Array of cloned steps with modified stepIds
 */
export function cloneWithSuffix(steps, suffix) {
  return steps.map(s => ({
    ...s,
    stepId: `${s.stepId}${suffix || ''}`,
  }));
}

/**
 * Create a standardized backtrack or resume summary step
 * Used in composite workflows to represent high-level workflow transitions
 * @param {string} workflowShortId - Short identifier for the workflow (e.g., 'w1', 'w2')
 * @param {boolean} backtracking - Whether this is a backtrack (true) or resume (false) step
 * @returns {Object} - Step object representing the summary transition
 */
export function makeBacktrackOrResumeSummary(workflowShortId, backtracking) {
  const toNode = backtracking ? 'source' : 'tail';
  const desc = backtracking
    ? `Backtracking ${workflowShortId} back to ${toNode}`
    : `Resuming ${workflowShortId} to ${toNode}`;
  const reason = backtracking
    ? `把整个工作流 ${workflowShortId} 回溯到`
    : `Forwarding ${workflowShortId} as a whole workflow`;
  return {
    stepId: `${backtracking ? 'backtrack' : 'resume'}-summary-${workflowShortId}`,
    description: desc,
    reasoning: reason,
    nodeMapping: toNode,
    correct: !backtracking,
    pass: backtracking ? null : 2,
    backtrack: !!backtracking,
    errorDetails: {issue: reason}
  };
}

/**
 * Create a return-to-source step for workflow transitions
 * Used when transitioning between different workflows in composite scenarios
 * @param {string} stepId - Unique identifier for the step
 * @param {string} description - Description of the transition
 * @param {string} reasoning - Reasoning for the transition
 * @param {string} fromNode - Node to transition from (usually 'tail')
 * @param {string} workflowContext - Context about which workflows are transitioning
 * @returns {Object} - Step object representing the return to source
 */
export function createReturnToSourceStep(stepId, description, reasoning, fromNode = 'tail', workflowContext = '') {
  return {
    stepId,
    description,
    reasoning,
    nodeMapping: 'source',
    from: fromNode,
    to: 'source',
    correct: false,
    pass: null,
    backtrack: true,
    workflowContext
  };
}

/**
 * Create a standard return-to-source step between workflows
 * Convenience function for common workflow transition pattern
 * @param {string} fromWorkflow - Source workflow identifier
 * @param {string} toWorkflow - Target workflow identifier
 * @returns {Object} - Step object for the transition
 */
export function createWorkflowTransitionStep(fromWorkflow, toWorkflow) {
  return createReturnToSourceStep(
    `return-to-source-between-${fromWorkflow}-${toWorkflow}`,
    '阶段完成后返回起点',
    `完成工作流${fromWorkflow}后，从目标返回到source以开始工作流${toWorkflow}`,
    'tail',
    `${fromWorkflow}->${toWorkflow}`
  );
}

