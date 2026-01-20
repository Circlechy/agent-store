// src/components/RLVisualizerSVG.js
import React from 'react';
import { getOffsetPoint, isCurvedEdge, getCurveConfiguration, calculateCurvePath } from './utils/graphHelpers';

/**
 * SVG Overlay component that visualizes the current step in RL traversal
 * Renders inside SVG with zoom/pan transform support
 */
export default function RLVisualizerSVG({ currentStep, traversal, nodeLayout, transform, edgeConfigurations = {} }) {
  const step = traversal[currentStep];
  if (!step) return null;

  // For backtracking steps, swap the source and destination to make arrows point backward
  const isBacktrack = step.backtrack === true;
  const dest = nodeLayout.find(n => n.id === (isBacktrack ? step.to : step.to));
  if (!dest) return null;

  const src = nodeLayout.find(n => n.id === (isBacktrack ? step.from : step.from));
  if (!src) return null;

  // Allow per-step overrides for arrow vs highlight colors
  const colorTokenToHex = (token) => {
    if (!token) return null;
    const t = String(token).toLowerCase();
    switch (t) {
      case 'green': return '#4ade80';
      case 'red': return '#f87171';
      case 'yellow': return '#facc15';
      default: return token; // assume hex or valid CSS color
    }
  };

  const highlightStrokeColor = colorTokenToHex(step.highlightColor)
    ?? (step.backtrack ? '#f87171' : (step.correct ? '#4ade80' : '#f87171'));
  const arrowStrokeColor = colorTokenToHex(step.arrowColor)
    ?? (step.backtrack ? '#f87171' : (step.correct ? '#4ade80' : '#f87171'));

  const markerId = (() => {
    const c = arrowStrokeColor?.toLowerCase();
    if (c === '#4ade80' || step.arrowColor === 'green') return 'arrowhead-green';
    if (c === '#facc15' || step.arrowColor === 'yellow') return 'arrowhead-yellow';
    return 'arrowhead-red';
  })();

  // Check if this is a self-loop (step stays within same node)
  const isSelfLoop = src.id === dest.id;

  // Calculate edge path - straight for normal workflow, curved for specific edges
  let edgePath = null;
  if (!isSelfLoop) {
    // Add offsets BEFORE calling getOffsetPoint (to match WorkflowGraph.js)
    const srcX = src.x + 600;
    const srcY = src.y + 350;
    const destX = dest.x + 600;
    const destY = dest.y + 350;
    
    const p1 = getOffsetPoint(srcX, srcY, destX, destY, src.radius);
    const p2 = getOffsetPoint(srcX, srcY, destX, destY, dest.radius);
    
    const startX = p1.x1;
    const startY = p1.y1;
    const endX = p2.x2;
    const endY = p2.y2;
    
    // Check if this edge needs a curve using data-driven approach
    const shouldCurve = isCurvedEdge(src.id, dest.id, edgeConfigurations);
    
    if (shouldCurve) {
      // Get curve configuration and calculate curved path
      const curveConfig = getCurveConfiguration(src.id, dest.id, edgeConfigurations);
      const srcCenterX = src.x + 600;
      const srcCenterY = src.y + 350;
      const destCenterX = dest.x + 600;
      const destCenterY = dest.y + 350;
      
      edgePath = calculateCurvePath(
        srcCenterX, srcCenterY, destCenterX, destCenterY,
        src.radius, dest.radius, curveConfig
      );
    } else {
      // Use straight lines for all other paths
      edgePath = `M ${startX} ${startY} L ${endX} ${endY}`;
    }
  }

  // Determine segment start based on pass changes; reset highlights when pass changes
  const currentPassKey = (() => {
    const p = step.pass;
    return p === undefined ? '__UNDEF__' : p;
  })();
  let segmentStartIndex = 0;
  for (let i = currentStep - 1; i >= 0; i--) {
    const p = traversal[i]?.pass;
    const key = p === undefined ? '__UNDEF__' : p;
    if (key !== currentPassKey) {
      segmentStartIndex = i + 1;
      break;
    }
  }

  // Build a map of last-visited color per node within the current pass segment to keep highlights
  const visitedNodeToColor = new Map();
  for (let i = segmentStartIndex; i <= currentStep; i++) {
    const s = traversal[i];
    if (!s) continue;
    const nodeId = s.to ?? s.nodeMapping;
    if (!nodeId) continue;
    const node = nodeLayout.find(n => n.id === nodeId);
    if (!node) continue;
    // Derive highlight color for this step
    const stepHighlight = (() => {
      const toHex = (token) => {
        if (!token) return null;
        const t = String(token).toLowerCase();
        if (t === 'green') return '#4ade80';
        if (t === 'red') return '#f87171';
        if (t === 'yellow') return '#facc15';
        return token;
      };
      const explicit = toHex(s.highlightColor);
      if (explicit) return explicit;
      if (s.backtrack === true || s.pass === null) return '#f87171';
      return s.correct ? '#4ade80' : '#f87171';
    })();
    visitedNodeToColor.set(nodeId, { color: stepHighlight, node });
  }

  // Build a list of previously traversed edges within the current pass segment (but not including currentStep)
  const visitedEdges = [];
  for (let i = segmentStartIndex; i < currentStep; i++) {
    const s = traversal[i];
    if (!s) continue;
    const fromId = s.from;
    const toId = s.to ?? s.nodeMapping;
    if (!fromId || !toId || fromId === toId) continue;

    const srcNode = nodeLayout.find(n => n.id === fromId);
    const destNode = nodeLayout.find(n => n.id === toId);
    if (!srcNode || !destNode) continue;

    // Determine arrow color for this historical step
    const histArrowColor = (() => {
      const toHex = (token) => {
        if (!token) return null;
        const t = String(token).toLowerCase();
        if (t === 'green') return '#4ade80';
        if (t === 'red') return '#f87171';
        if (t === 'yellow') return '#facc15';
        return token;
      };
      const explicit = toHex(s.arrowColor) || toHex(s.highlightColor);
      if (explicit) return explicit;
      if (s.backtrack === true || s.pass === null) return '#f87171';
      return s.correct ? '#4ade80' : '#f87171';
    })();

    const histMarkerId = (() => {
      const c = histArrowColor?.toLowerCase();
      if (c === '#4ade80') return 'arrowhead-green';
      if (c === '#facc15') return 'arrowhead-yellow';
      return 'arrowhead-red';
    })();

    // Calculate path (curved if configured)
    const isSelf = srcNode.id === destNode.id;
    if (isSelf) continue;

    const srcX = srcNode.x + 600;
    const srcY = srcNode.y + 350;
    const destX = destNode.x + 600;
    const destY = destNode.y + 350;

    const p1 = getOffsetPoint(srcX, srcY, destX, destY, srcNode.radius);
    const p2 = getOffsetPoint(srcX, srcY, destX, destY, destNode.radius);

    const startX = p1.x1;
    const startY = p1.y1;
    const endX = p2.x2;
    const endY = p2.y2;

    const shouldCurve = isCurvedEdge(srcNode.id, destNode.id, edgeConfigurations);
    let pathD = null;
    if (shouldCurve) {
      const curveConfig = getCurveConfiguration(srcNode.id, destNode.id, edgeConfigurations);
      const srcCenterX = srcNode.x + 600;
      const srcCenterY = srcNode.y + 350;
      const destCenterX = destNode.x + 600;
      const destCenterY = destNode.y + 350;
      pathD = calculateCurvePath(
        srcCenterX, srcCenterY, destCenterX, destCenterY,
        srcNode.radius, destNode.radius, curveConfig
      );
    } else {
      pathD = `M ${startX} ${startY} L ${endX} ${endY}`;
    }

    visitedEdges.push({ key: `${fromId}->${toId}-${i}`, d: pathD, color: histArrowColor, markerId: histMarkerId });
  }

  return (
    <g transform={transform ? transform.toString() : ''} pointerEvents="none">
      {Array.from(visitedNodeToColor.values()).map(({ color, node }) => (
        <circle
          key={`visited-${node.id}`}
          cx={node.renderedX ?? (node.x + 600)}
          cy={node.renderedY ?? (node.y + 350)}
          r={node.radius || 40}
          fill="none"
          stroke={color}
          strokeWidth={9}
          opacity={0.85}
        />
      ))}

      {/* Previously traversed arrows */}
      {visitedEdges.map(edge => (
        <path
          key={`visited-edge-${edge.key}`}
          d={edge.d}
          stroke={edge.color}
          strokeWidth={8}
          strokeLinecap="round"
          fill="none"
          markerEnd={`url(#${edge.markerId})`}
          opacity={0.65}
        />
      ))}

      {/* Current step connector arrow (colored), suppressed on self-loop */}
      {!isSelfLoop && edgePath && (
        <path
          d={edgePath}
          stroke={arrowStrokeColor}
          strokeWidth={10}
          strokeLinecap="round"
          fill="none"
          markerEnd={`url(#${markerId})`}
          opacity={0.75}
        />
      )}
    </g>
  );
}

