import React, { useEffect, useRef, useState, useMemo } from 'react';
import * as d3 from 'd3';
import { bigNodeData, smallSteps, connections, workflowColors, workflows, edgeConfigurations } from '../data/realDataStocks';
import { getOffsetPoint, smallNodeRadius, diamondSpacing, getDiamondPosition, bigNodeRadiusPadding, isCurvedEdge, getCurveConfiguration, calculateCurvePath } from './utils/graphHelpers';
import HTMLRenderer from './utils/HTMLRenderer';

export default function WorkflowGraph({ onLayoutComputed, onTransformChange, children, selectedWorkflow, currentStep, traversal }) {
  const zoomBehaviorRef = useRef(null);      // To keep reference to zoom behavior
  const currentTransformRef = useRef(null);  // To preserve zoom state

  const svgRef = useRef(null);
  const groupRef = useRef(null);
  const [selectedTask, setSelectedTask] = useState(null);
  

  // Create a mapping of connections to their workflows
  const connectionToWorkflows = useMemo(() => {
    const connMap = {};
    
    Object.values(workflows).forEach(workflow => {
      let previousNode = 'source';
      
      workflow.steps.forEach(step => {
        const currentNode = step.nodeMapping;
        
        if (previousNode !== currentNode) {
          const connKey = `${previousNode}->${currentNode}`;
          if (!connMap[connKey]) {
            connMap[connKey] = [];
          }
          connMap[connKey].push(workflow.id);
        }
        
        if (step.correct || step.isCorrection) {
          previousNode = currentNode;
        } else if (step.correct === false && step.errorDetails?.backtrackTo) {
          previousNode = step.errorDetails.backtrackTo;
        }
      });
    });
    
    return connMap;
  }, []);

  // Derive backtrack connections from traversal data
  const backtrackConnections = useMemo(() => {
    if (!traversal) {
      return [];
    }
    
    // Look for steps with backtrack: true OR pass: null
    const backtrackSteps = traversal.filter(step => {
      const isBacktrack = step.backtrack === true;
      const isPassNull = step.pass === null;
      const hasFromTo = step.from && step.to;
      
      return (isBacktrack || isPassNull) && hasFromTo;
    });
    
    const connections = backtrackSteps.map(step => {
      const conn = [step.from, step.to];
      return conn;
    });
    
    return connections;
  }, [traversal]);

  // Memoize big nodes with radius calculation and manual positions
  const bigNodesWithRadius = useMemo(() => {
    // Prepare big nodes with manual positions and sizes
    return Object.entries(bigNodeData).map(([id, bigNode]) => {
      const steps = smallSteps[id] || [];
      
      // Special nodes (source/tail) have a fixed radius
      if (bigNode.isSpecial) {
        return { 
          ...bigNode, 
          x: bigNode.x, 
          y: bigNode.y, 
          radius: 50, 
          steps: [] 
        };
      }
      
      // Calculate radius based on diamond layout
      // For diamond, we need space from center to furthest point + padding
      const diamondRadius = steps.length > 0 
        ? diamondSpacing + smallNodeRadius + bigNodeRadiusPadding
        : smallNodeRadius + bigNodeRadiusPadding;
      
      return { 
        ...bigNode, 
        x: bigNode.x, 
        y: bigNode.y, 
        radius: diamondRadius, 
        steps 
      };
    });
  }, []);

  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    
    // Preserve current transform before removing the group
    const existingGroup = svg.select('.graph-group');
    if (!existingGroup.empty() && currentTransformRef.current) {
      // Keep the current transform
    } else {
      // First render - initialize with identity
      currentTransformRef.current = d3.zoomIdentity;
    }
    
    svg.select('.graph-group').remove();

    // Append graph group
    const g = svg.append('g').attr('class', 'graph-group');
    groupRef.current = g;

    // Define zoom behavior
    const zoom = d3.zoom()
      .scaleExtent([0.5, 3])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
        currentTransformRef.current = event.transform; // Save transform
        onTransformChange?.(event.transform);
      });

    zoomBehaviorRef.current = zoom;
    svg.call(zoom);
    
    // Restore the preserved transform
    svg.call(zoom.transform, currentTransformRef.current);
    g.attr('transform', currentTransformRef.current);
    onTransformChange?.(currentTransformRef.current);

    // Determine which arrows to show based on pass value
    const currentStepData = currentStep !== null && traversal && traversal[currentStep] ? traversal[currentStep] : null;
    const shouldShowForwardArrows = currentStepData && (currentStepData.pass === 1 || currentStepData.pass === 2);
    
    // Show backtrack arrows if:
    // 1. We have a current step that is a backtrack step (backtrack === true)
    // 2. OR if we have a current step whereby the pass is null (pass === null)
    const shouldShowBacktrackArrows = (currentStepData && (currentStepData.pass === null || currentStepData.backtrack === true)) 
    
    
    // Show static workflow arrows when no traversal is active (default view) but NOT during backtracking
    const shouldShowStaticArrows = ((!traversal || traversal.length === 0) && currentStep === null) && !shouldShowBacktrackArrows;
    
    // During backtracking (pass === null), hide all forward arrows and only show backtrack arrows
    const isBacktracking = shouldShowBacktrackArrows;

    // Draw edges inside zoom group
    // Filter out any forward/static edges that originate from tail
    const forwardEdgesNoTailSource = connections.filter(conn => conn[0] !== 'tail');

    // Separate curved edges from straight edges (after filtering)
    // Use data-driven approach to determine which edges should be curved
    const curvedEdges = forwardEdgesNoTailSource.filter(conn => 
      conn[0] !== conn[1] && isCurvedEdge(conn[0], conn[1], edgeConfigurations)
    );
    const straightEdges = forwardEdgesNoTailSource.filter(conn => 
      conn[0] !== conn[1] && !isCurvedEdge(conn[0], conn[1], edgeConfigurations)
    );
    
    // Draw straight edges (show forward arrows when pass is 1 or 2, or show static arrows when no traversal or during backtracking)
    if (shouldShowForwardArrows || shouldShowStaticArrows) {
      g.selectAll('.edge')
        .data(straightEdges)
        .enter()
        .append('line')
        .attr('class', 'edge')
        .attr('stroke', '#000')
        .attr('stroke-width', 2)
        .attr('opacity', 1)
        .attr('marker-end', 'url(#arrowhead)')
      .attr('x1', (conn) => {
        const source = bigNodesWithRadius.find((n) => n.id === conn[0]);
        const target = bigNodesWithRadius.find((n) => n.id === conn[1]);
        
        if (!source || !target) {
          console.warn('Main edge x1: Source or target node not found', { conn, source, target });
          return 0;
        }
        
        const srcX = source.x + 600;
        const srcY = source.y + 350;
        const tgtX = target.x + 600;
        const tgtY = target.y + 350;
        
        // Debug logging for NaN values
        if (isNaN(srcX) || isNaN(srcY) || isNaN(tgtX) || isNaN(tgtY)) {
          console.error('Main edge x1: NaN values detected', {
            conn,
            source: { id: source.id, x: source.x, y: source.y },
            target: { id: target.id, x: target.x, y: target.y },
            srcX, srcY, tgtX, tgtY
          });
          return 0;
        }
        
        const pts = getOffsetPoint(srcX, srcY, tgtX, tgtY, source.radius);
        return pts.x1;
      })
      .attr('y1', (conn) => {
        const source = bigNodesWithRadius.find((n) => n.id === conn[0]);
        const target = bigNodesWithRadius.find((n) => n.id === conn[1]);
        
        const srcX = source.x + 600;
        const srcY = source.y + 350;
        const tgtX = target.x + 600;
        const tgtY = target.y + 350;
        
        const pts = getOffsetPoint(srcX, srcY, tgtX, tgtY, source.radius);
        return pts.y1;
      })
      .attr('x2', (conn) => {
        const source = bigNodesWithRadius.find((n) => n.id === conn[0]);
        const target = bigNodesWithRadius.find((n) => n.id === conn[1]);
        
        const srcX = source.x + 600;
        const srcY = source.y + 350;
        const tgtX = target.x + 600;
        const tgtY = target.y + 350;
        
        const ptsEnd = getOffsetPoint(srcX, srcY, tgtX, tgtY, target.radius);
        return ptsEnd.x2;
      })
      .attr('y2', (conn) => {
        const source = bigNodesWithRadius.find((n) => n.id === conn[0]);
        const target = bigNodesWithRadius.find((n) => n.id === conn[1]);
        
        const srcX = source.x + 600;
        const srcY = source.y + 350;
        const tgtX = target.x + 600;
        const tgtY = target.y + 350;
        
        const ptsEnd = getOffsetPoint(srcX, srcY, tgtX, tgtY, target.radius);
        return ptsEnd.y2;
      });
    }

    // Draw main curved arrow for backtracking between tail -> source (single arrow)
    if (shouldShowBacktrackArrows && currentStepData) {
      const sourceNode = bigNodesWithRadius.find((n) => n.id === 'source');
      const tailNode = bigNodesWithRadius.find((n) => n.id === 'tail');
      if (sourceNode && tailNode) {
        const isTailToSource = currentStepData.from === 'tail' && currentStepData.to === 'source';

        if (isTailToSource) {
          const src = tailNode;
          const tgt = sourceNode;

          const srcCenterX = src.x + 600;
          const srcCenterY = src.y + 350;
          const tgtCenterX = tgt.x + 600;
          const tgtCenterY = tgt.y + 350;

          const midX = (srcCenterX + tgtCenterX) / 2;
          const controlX = midX;
          const controlY = Math.min(srcCenterY, tgtCenterY) + 720; // arc above both nodes

          // start tangent on source circle
          const startAngle = Math.atan2(controlY - srcCenterY, controlX - srcCenterX);
          const startX = srcCenterX + src.radius * Math.cos(startAngle);
          const startY = srcCenterY + src.radius * Math.sin(startAngle);

          // end tangent on target circle
          const endAngle = Math.atan2(tgtCenterY - controlY, tgtCenterX - controlX);
          const endX = tgtCenterX - tgt.radius * Math.cos(endAngle);
          const endY = tgtCenterY - tgt.radius * Math.sin(endAngle);

          g.append('path')
            .attr('class', 'edge-curved-main-backtrack')
            .attr('stroke', '#000')
            .attr('stroke-width', 3)
            .attr('fill', 'none')
            .attr('opacity', 0.8)
            .attr('marker-end', 'url(#arrowhead-backtrack)')
            .attr('d', `M ${startX},${startY} Q ${controlX},${controlY} ${endX},${endY}`);
        }
      }
    }

    // Draw curved edge for node4 -> node9 (show forward arrows when pass is 1 or 2, or show static arrows when no traversal or during backtracking)
    if (shouldShowForwardArrows || shouldShowStaticArrows) {
      g.selectAll('.edge-curved')
        .data(curvedEdges)
        .enter()
        .append('path')
        .attr('class', 'edge-curved')
        .attr('stroke', '#000')
        .attr('stroke-width', 2)
        .attr('fill', 'none')
        .attr('opacity', 1)
        .attr('marker-end', 'url(#arrowhead)')
      .attr('d', (conn) => {
        const source = bigNodesWithRadius.find((n) => n.id === conn[0]);
        const target = bigNodesWithRadius.find((n) => n.id === conn[1]);
        
        const srcX = source.x + 600;
        const srcY = source.y + 350;
        const tgtX = target.x + 600;
        const tgtY = target.y + 350;
        
        // Use data-driven curve calculation
        const curveConfig = getCurveConfiguration(conn[0], conn[1], edgeConfigurations);
        return calculateCurvePath(srcX, srcY, tgtX, tgtY, source.radius, target.radius, curveConfig);
      });
    }
    
    // Draw main curved arrow between source and tail based on current traversal direction (single arrow)
    if (shouldShowForwardArrows && currentStepData) {
      const sourceNode = bigNodesWithRadius.find((n) => n.id === 'source');
      const tailNode = bigNodesWithRadius.find((n) => n.id === 'tail');
      if (sourceNode && tailNode) {
        const isSourceToTail = currentStepData.from === 'source' && currentStepData.to === 'tail';
        const isTailToSource = currentStepData.from === 'tail' && currentStepData.to === 'source';

        if (isSourceToTail || isTailToSource) {
          const src = isSourceToTail ? sourceNode : tailNode;
          const tgt = isSourceToTail ? tailNode : sourceNode;

          const srcCenterX = src.x + 600;
          const srcCenterY = src.y + 350;
          const tgtCenterX = tgt.x + 600;
          const tgtCenterY = tgt.y + 350;

          // Use data-driven curve calculation for source↔tail
          const curveConfig = getCurveConfiguration(src.id, tgt.id, edgeConfigurations);
          const pathData = calculateCurvePath(srcCenterX, srcCenterY, tgtCenterX, tgtCenterY, src.radius, tgt.radius, curveConfig);

          g.append('path')
            .attr('class', 'edge-curved-main')
            .attr('stroke', '#000')
            .attr('stroke-width', 2)
            .attr('fill', 'none')
            .attr('opacity', 1)
            .attr('marker-end', 'url(#arrowhead)')
            .attr('d', pathData);
        }
      }
    }

    
    if (shouldShowBacktrackArrows && backtrackConnections.length > 0) {
      // Exclude source↔tail from generic backtrack lines; it's rendered as a dedicated curved path
      const filteredBacktracks = backtrackConnections.filter(conn => !(
        (conn[0] === 'tail' && conn[1] === 'source') ||
        (conn[0] === 'source' && conn[1] === 'tail') ||
        (conn[0] === conn[1])
      ));
      
      const backtrackSelection = g.selectAll('.edge-backtrack')
        .data(filteredBacktracks);
      
      // Remove any existing backtrack arrows that are no longer needed
      backtrackSelection.exit().remove();
      
      // Add new backtrack arrows
      const newBacktrackArrows = backtrackSelection.enter()
        .append('path')
        .attr('class', 'edge-backtrack')
        .attr('stroke', '#000')
        .attr('stroke-width', 3)
        .attr('fill', 'none')
        .attr('opacity', 0.8)
        .attr('marker-end', 'url(#arrowhead-backtrack)');
      
      
      // Update all backtrack arrows (both existing and new) - need fresh selection for merge
      g.selectAll('.edge-backtrack')
        .data(filteredBacktracks)
        .merge(newBacktrackArrows)
      .attr('d', (conn) => {
        const source = bigNodesWithRadius.find((n) => n.id === conn[0]);
        const target = bigNodesWithRadius.find((n) => n.id === conn[1]);
        
        if (!source || !target) {
          console.warn('Backtrack edge: Source or target node not found', { conn, source, target });
          return 'M 0,0 L 0,0'; // Return empty path if nodes not found
        }
        
        const srcX = source.x + 600;
        const srcY = source.y + 350;
        const tgtX = target.x + 600;
        const tgtY = target.y + 350;
        
        // Debug logging for NaN values
        if (isNaN(srcX) || isNaN(srcY) || isNaN(tgtX) || isNaN(tgtY)) {
          console.error('Backtrack edge: NaN values detected', {
            conn,
            source: { id: source.id, x: source.x, y: source.y },
            target: { id: target.id, x: target.x, y: target.y },
            srcX, srcY, tgtX, tgtY
          });
          return 'M 0,0 L 0,0'; // Return empty path for NaN values
        }
        
        // Check if this backtrack connection should be curved using data-driven approach
        const isCurvedBacktrack = isCurvedEdge(conn[0], conn[1], edgeConfigurations);
        
        if (isCurvedBacktrack) {
          // Use data-driven curve calculation for backtrack edges
          const curveConfig = getCurveConfiguration(conn[0], conn[1], edgeConfigurations);
          return calculateCurvePath(srcX, srcY, tgtX, tgtY, source.radius, target.radius, curveConfig);
        } else {
          // For non-curved backtrack connections, use straight lines
          const pts = getOffsetPoint(srcX, srcY, tgtX, tgtY, source.radius);
          const ptsEnd = getOffsetPoint(srcX, srcY, tgtX, tgtY, target.radius);
          return `M ${pts.x1},${pts.y1} L ${ptsEnd.x2},${ptsEnd.y2}`;
        }
      });
    }

    // Draw big nodes
    const bigNodeGroups = g
      .selectAll('.big-node-group')
      .data(bigNodesWithRadius, (d) => d.id)
      .enter()
      .append('g')
      .attr('class', 'big-node-group')
      .attr('transform', (d) => `translate(${d.x + 600},${d.y + 350})`);

    bigNodeGroups
      .append('circle')
      .attr('r', (d) => d.radius)
      .attr('stroke', (d) => d.isSpecial ? '#333' : '#888')
      .attr('stroke-width', (d) => d.isSpecial ? 4 : 3)
      .attr('fill', (d) => d.isSpecial ? (d.color || 'rgba(0, 0, 0, 0)') : 'rgba(0, 0, 0, 0)')
      .attr('opacity', (d) => d.isSpecial ? 0.6 : 1);

    // Add labels for big nodes
    bigNodeGroups.each(function(d) {
      const group = d3.select(this);
      const labelY = d.isSpecial ? 5 : (d.radius + 20);
      const fontSize = d.isSpecial ? 18 : 16;
      const labelText = d.label;
      
      // Only add background rectangles for non-special nodes
      if (!d.isSpecial) {
        // Estimate text width (rough approximation: ~0.6 * fontSize per character)
        const textWidth = labelText.length * fontSize * 0.72;
        const padding = 8;
        
        // Add background rectangle
        group.append('rect')
          .attr('x', -textWidth / 2 - padding)
          .attr('y', labelY - fontSize + 2)
          .attr('width', textWidth + padding * 2)
          .attr('height', fontSize + padding)
          .attr('fill', '#fafafa')
          .attr('stroke', '#ddd')
          .attr('stroke-width', 1)
          .attr('rx', 4)
          .attr('opacity', 0.95)
          .attr('pointer-events', 'none');
      }
      
      // Add text label
      group.append('text')
        .text(labelText)
        .attr('text-anchor', 'middle')
        .attr('y', labelY)
        .attr('fill', d.isSpecial ? '#1f2937' : '#555')
        .style('font-weight', d.isSpecial ? '900' : 'bold')
        .style('font-size', `${fontSize}px`)
        .style('letter-spacing', d.isSpecial ? '1px' : 'normal')
        .attr('pointer-events', 'none');
    });

    // Draw small nodes
    bigNodeGroups.each(function (d) {
      const group = d3.select(this);
      
      group
        .selectAll('.small-node')
        .data(d.steps, (s) => s.id)
        .enter()
        .append('circle')
        .attr('class', 'small-node')
        .attr('r', smallNodeRadius)
        .attr('cy', (s, i) => getDiamondPosition(i, diamondSpacing).cy)
        .attr('cx', (s, i) => getDiamondPosition(i, diamondSpacing).cx)
        .attr('fill', (s) => workflowColors[s.workflow] || '#ddd')
        .attr('stroke', '#999')
        .attr('stroke-width', 2)
        .attr('opacity', 1)
        .style('cursor', 'pointer')
        .style('pointer-events', 'all')
        .on('click', (event, s) => {
          event.stopPropagation();
          setSelectedTask(s);
        });

      group
        .selectAll('.small-node-label')
        .data(d.steps, (s) => s.id)
        .enter()
        .append('text')
        .attr('class', 'small-node-label')
        .attr('x', (s, i) => getDiamondPosition(i, diamondSpacing).cx)
        .attr('y', (s, i) => getDiamondPosition(i, diamondSpacing).cy + 4)
        .attr('text-anchor', 'middle')
        .attr('pointer-events', 'none')
        .style('user-select', 'none')
        .style('font-size', '9px')
        .style('fill', '#222')
        .attr('opacity', 1)
        .text((s) => s.id);
    });

    // Clicking outside clears info box
    svg.on('click', (event) => {
      // Only clear if clicking on the SVG background, not on nodes
      if (event.target === svg.node()) {
        setSelectedTask(null);
      }
    });

    onLayoutComputed?.(
      bigNodesWithRadius.map(n => ({
        ...n,
        renderedX: n.x + 600,   // match D3's render offsets
        renderedY: n.y + 350,   // match D3's render offsets
      }))
    );
    
  }, [bigNodesWithRadius, selectedWorkflow, connectionToWorkflows, backtrackConnections, onLayoutComputed, currentStep, traversal]);


  // bottom of WorkflowGraph.js
return (
  <div
    style={{
      position: 'relative',
      width: '100%',
      maxWidth: 'min(1200px, 95vw)',
      margin: '1vh auto',
      userSelect: 'none'
    }}
  >
    <svg
      ref={svgRef}
      viewBox="0 0 1200 700"
      preserveAspectRatio="xMidYMid meet"
      style={{
        position: 'relative',
        width: '100%',
        height: 'auto',
        maxHeight: '60vh',
        border: '1px solid #ccc',
        borderRadius: 8,
        backgroundColor: '#fafafa'
      }}
    >
      {/* Static marker defs: define once, never recreated */}
      <defs>
        <marker
          id="arrowhead"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="6"
          markerHeight="6"
          orient="auto"
        >
          <path d="M0,0 L10,5 L0,10 Z" fill="#000" />
        </marker>

        {/* Dynamic workflow arrowheads */}
        {Object.entries(workflowColors).map(([workflowId, color]) => (
          <marker
            key={workflowId}
            id={`arrowhead-${workflowId}`}
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto"
          >
            <path d="M0,0 L10,5 L0,10 Z" fill={color} />
          </marker>
        ))}

        {/* RLVisualiser uses these */}
        <marker id="arrowhead-green" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="4" markerHeight="4" orient="auto">
          <path d="M0,0 L10,5 L0,10 Z" fill="#4ade80" />
        </marker>
        <marker id="arrowhead-yellow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="4" markerHeight="4" orient="auto">
          <path d="M0,0 L10,5 L0,10 Z" fill="#facc15" />
        </marker>
        <marker id="arrowhead-red" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="4" markerHeight="4" orient="auto">
          <path d="M0,0 L10,5 L0,10 Z" fill="#f87171" />
        </marker>
        <marker id="arrowhead-backtrack" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto">
          <path d="M0,0 L10,5 L0,10 Z" fill="#000" />
        </marker>
      </defs>

      {/* Keep D3 group render area */}
      {children}
    </svg>

    {/* Info Box */}
    {selectedTask && (
      <div
        style={{
          position: 'absolute',
          top: 'clamp(10px, 2vh, 20px)',
          left: 'clamp(10px, 1vw, 20px)',
          width: 'clamp(250px, 30vw, 350px)',
          padding: 'clamp(12px, 1.5vh, 16px)',
          background: '#fff',
          borderRadius: 10,
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          zIndex: 20,
          fontSize: 'clamp(12px, 1.2vh, 14px)',
        }}
      >
        <h3 style={{ 
          margin: '0 0 8px 0', 
          fontSize: 'clamp(14px, 1.5vh, 16px)',
          color: '#111827',
          fontWeight: '600'
        }}>
          子步骤 {selectedTask.id}: {selectedTask.label}
        </h3>
        <p style={{ 
          margin: '0 0 8px 0',
          fontSize: 'clamp(11px, 1.1vh, 12px)',
          color: '#6b7280',
          fontWeight: '500'
        }}>
          从 {selectedTask.workflow || '未知工作流'}
        </p>
        {selectedTask.question && (
          <div style={{
            padding: 'clamp(8px, 1vh, 10px)',
            background: '#f9fafb',
            borderRadius: 6,
            fontSize: 'clamp(12px, 1.2vh, 13px)',
            color: '#374151',
            lineHeight: 1.5,
            border: '1px solid #e5e7eb',
          }}>
            <strong>问题:</strong> <HTMLRenderer content={selectedTask.question} tag="span" />
          </div>
        )}
      </div>
    )}
  </div>
);

}