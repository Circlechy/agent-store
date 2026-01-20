// utils/graphHelpers.js
function getOffsetPoint(x1, y1, x2, y2, offset) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const dist = Math.sqrt(dx * dx + dy * dy);
  
  // Handle case where source and target are at the same position
  if (dist < 1e-6) {
    // Fallback to a deterministic horizontal direction to avoid zero-length edges
    const ux = 1;
    const uy = 0;
    return {
      x1: x1 + ux * offset,
      y1: y1 + uy * offset,
      x2: x2 - ux * offset,
      y2: y2 - uy * offset,
    };
  }
  
  return {
    x1: x1 + (dx / dist) * offset,
    y1: y1 + (dy / dist) * offset,
    x2: x2 - (dx / dist) * offset,
    y2: y2 - (dy / dist) * offset,
  };
}

const bigNodeRadiusPadding = 15;
const smallNodeRadius = 12;
const verticalSpacing = 35;
const diamondSpacing = 30; // Distance from center for hex layout

const COLOR_PALETTE = [
  '#34D399', // Emerald Green
  '#60A5FA', // Bright Blue
  '#FFC9DE', // Hot Pink
  '#FBBF24', // Amber Yellow
  '#A78BFA', // Purple
  '#FB923C', // Orange
  '#2DD4BF', // Teal
];

/**
 * Dynamically assign colors to workflows based on their IDs
 * @param {Array<string>} workflowIds - Array of workflow IDs
 * @returns {Object} - Map of workflowId -> color
 */
function generateWorkflowColors(workflowIds) {
  const colors = {};
  workflowIds.forEach((id, index) => {
    if (index < COLOR_PALETTE.length) {
      colors[id] = COLOR_PALETTE[index];
    } else {
      // Fallback to grayscale if more than 7 workflows
      console.warn(`More than ${COLOR_PALETTE.length} workflows detected. Using grayscale for workflow: ${id}`);
      colors[id] = '#E0E0E0';
    }
  });
  return colors;
}

/**
 * Get hexagonal position for a small node based on its index
 * Positions follow a regular hexagon around the center, starting at top and moving clockwise:
 * 0=top, 1=top-right, 2=bottom-right, 3=bottom, 4=bottom-left, 5=top-left
 * Note: We keep the same function name to avoid refactoring call sites.
 */
function getDiamondPosition(index, spacing = 40) {
  const anglesDeg = [90, 30, -30, -90, -150, 150];
  const a = anglesDeg[index % 6] * (Math.PI / 180);
  const cx = Math.cos(a) * spacing;
  const cy = -Math.sin(a) * spacing; // negative to make 90deg point upwards in SVG coords
  return { cx, cy };
}

/**
 * Get animation styles for node based on action type
 * @param {string} action - 'CREATE', 'MERGE', or null
 * @returns {Object} - CSS style properties for animation
 */
function getAnimationFrameStyles(action) {
  if (action === 'CREATE') {
    return {
      animation: 'nodeCreate 0.6s ease-out',
      strokeWidth: 4,
      stroke: '#10b981', // green
      filter: 'drop-shadow(0 0 8px rgba(16, 185, 129, 0.6))'
    };
  } else if (action === 'MERGE') {
    return {
      animation: 'nodeMerge 0.6s ease-out',
      strokeWidth: 4,
      stroke: '#3b82f6', // blue
      filter: 'drop-shadow(0 0 8px rgba(59, 130, 246, 0.6))'
    };
  }
  return {
    strokeWidth: 3,
    stroke: '#888'
  };
}

/**
 * Calculate node appearance properties for build mode
 * @param {Object} node - Node data
 * @param {Array} steps - Steps in the node
 * @returns {Object} - Size and position properties
 */
function calculateNodeAppearance(node, steps = []) {
  const radius = node.isSpecial 
    ? 50 
    : (steps.length > 0 ? diamondSpacing + smallNodeRadius + bigNodeRadiusPadding : smallNodeRadius + bigNodeRadiusPadding);
  
  return {
    radius,
    x: node.x,
    y: node.y,
    opacity: 1
  };
}

/**
 * Generate descriptive label for why a merge happened
 * @param {string} nodeLabel - Label of the target node
 * @param {string} stepDescription - Description of the step being merged
 * @returns {string} - Human-readable explanation
 */
function generateNodeLabel(nodeLabel, stepDescription) {
  return `${stepDescription} → ${nodeLabel}`;
}

/**
 * Get curve configuration for an edge
 * @param {string} from - Source node ID
 * @param {string} to - Target node ID
 * @param {Object} edgeConfigurations - Edge configuration object
 * @returns {Object} - Curve configuration or default straight line config
 */
function getCurveConfiguration(from, to, edgeConfigurations) {
  const key = `${from}|${to}`;
  return edgeConfigurations[key] || { isCurved: false };
}

/**
 * Check if an edge should be curved
 * @param {string} from - Source node ID
 * @param {string} to - Target node ID
 * @param {Object} edgeConfigurations - Edge configuration object
 * @returns {boolean} - True if edge should be curved
 */
function isCurvedEdge(from, to, edgeConfigurations) {
  const config = getCurveConfiguration(from, to, edgeConfigurations);
  return config.isCurved === true;
}

/**
 * Calculate curved path for an edge
 * @param {number} srcX - Source X coordinate
 * @param {number} srcY - Source Y coordinate
 * @param {number} tgtX - Target X coordinate
 * @param {number} tgtY - Target Y coordinate
 * @param {number} srcRadius - Source node radius
 * @param {number} tgtRadius - Target node radius
 * @param {Object} config - Curve configuration
 * @returns {string|null} - SVG path string or null for straight line
 */
function calculateCurvePath(srcX, srcY, tgtX, tgtY, srcRadius, tgtRadius, config) {
  if (!config.isCurved) {
    return null; // Use straight line
  }

  let controlX, controlY;
  
  switch (config.curveType) {
    case 'right':
      controlX = srcX + config.curveOffset;
      controlY = (srcY + tgtY) / 2;
      break;
    case 'up':
      controlX = (srcX + tgtX) / 2;
      controlY = srcY + config.curveOffset;
      break;
    case 'arc':
      controlX = (srcX + tgtX) / 2;
      controlY = Math.min(srcY, tgtY) + config.curveOffset;
      break;
    default:
      return null;
  }

  // Calculate start and end points with tangents
  const startAngle = Math.atan2(controlY - srcY, controlX - srcX);
  const startX = srcX + srcRadius * Math.cos(startAngle);
  const startY = srcY + srcRadius * Math.sin(startAngle);
  
  const endAngle = Math.atan2(tgtY - controlY, tgtX - controlX);
  const endX = tgtX - tgtRadius * Math.cos(endAngle);
  const endY = tgtY - tgtRadius * Math.sin(endAngle);
  
  return `M ${startX} ${startY} Q ${controlX} ${controlY} ${endX} ${endY}`;
}

export {
  getOffsetPoint,
  bigNodeRadiusPadding,
  smallNodeRadius,
  verticalSpacing,
  diamondSpacing,
  getDiamondPosition,
  COLOR_PALETTE,
  generateWorkflowColors,
  getAnimationFrameStyles,
  calculateNodeAppearance,
  generateNodeLabel,
  getCurveConfiguration,
  isCurvedEdge,
  calculateCurvePath,
};
