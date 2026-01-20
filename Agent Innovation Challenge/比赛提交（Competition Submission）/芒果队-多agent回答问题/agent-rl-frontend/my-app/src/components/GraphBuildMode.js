import React, { useEffect, useRef, useState, useMemo } from 'react';
import * as d3 from 'd3';
import { bigNodeData, baseWorkflows, workflowColors, edgeConfigurations } from '../data/realDataStocks';
import { simulateNodeFusion } from '../data/nodeFusionSimulator';
import { 
  getOffsetPoint, 
  smallNodeRadius, 
  diamondSpacing, 
  getDiamondPosition, 
  bigNodeRadiusPadding,
  getAnimationFrameStyles,
  isCurvedEdge,
  getCurveConfiguration,
  calculateCurvePath
} from './utils/graphHelpers';
import ControlPanel from './ControlPanel';
import BuildEventPanel from './BuildEventPanel';
import HTMLRenderer from './utils/HTMLRenderer';
import '../styles/BuildMode.css';

export default function GraphBuildMode() {
  const svgRef = useRef(null);
  const groupRef = useRef(null);
  const zoomTransformRef = useRef(null);
  const zoomBehaviorRef = useRef(null);
  const [currentFrameIndex, setCurrentFrameIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1000); // ms per frame
  const [selectedBigNode, setSelectedBigNode] = useState(null);
  const animationTimerRef = useRef(null);
  const [panelStartIndex, setPanelStartIndex] = useState(null);
  // First-seen flags and event panel state
  const [seenCreate, setSeenCreate] = useState(false);
  const [seenMerge, setSeenMerge] = useState(false);
  const [eventPanelVisible, setEventPanelVisible] = useState(false);
  const [eventPanelDecision, setEventPanelDecision] = useState(null);
  const hideEventTimerRef = useRef(null);

  // Generate animation frames
  const frames = useMemo(() => simulateNodeFusion(baseWorkflows, bigNodeData), []);

  const currentFrame = frames[currentFrameIndex] || frames[0];
  const progress = (currentFrameIndex / (frames.length - 1)) * 100;

  // Track first time we see CREATE or MERGE and drive the BuildEventPanel for 5 seconds
  useEffect(() => {
    const prevFrame = currentFrameIndex > 0 ? frames[currentFrameIndex - 1] : null;
    const prevAction = prevFrame?.action;
    const currAction = currentFrame?.action;

    const didActionStart = currAction && currAction !== prevAction;

    if (didActionStart) {
      if (currAction === 'CREATE' && !seenCreate) {
        setSeenCreate(true);
        setEventPanelDecision({ action: 'CREATE' });
        setEventPanelVisible(true);
        if (hideEventTimerRef.current) clearTimeout(hideEventTimerRef.current);
        hideEventTimerRef.current = setTimeout(() => setEventPanelVisible(false), 5000);
      } else if (currAction === 'MERGE' && !seenMerge) {
        setSeenMerge(true);
        setEventPanelDecision({ action: 'MERGE' });
        setEventPanelVisible(true);
        if (hideEventTimerRef.current) clearTimeout(hideEventTimerRef.current);
        hideEventTimerRef.current = setTimeout(() => setEventPanelVisible(false), 5000);
      }

      // Retain old index marker if needed elsewhere
      setPanelStartIndex(currentFrameIndex);
    }

    return () => {
      // No cleanup here; handled on unmount/reset
    };
  }, [currentFrameIndex, currentFrame, frames, seenCreate, seenMerge]);

  const isPanelVisible = eventPanelVisible;

  // Build nodes from current frame state
  const currentNodes = useMemo(() => {
    if (!currentFrame?.graphState) return [];
    
    const { nodes, steps } = currentFrame.graphState;
    
    // Get previous frame to detect label changes
    const previousFrame = currentFrameIndex > 0 ? frames[currentFrameIndex - 1] : null;
    const previousSteps = previousFrame?.graphState?.steps || {};
    
    return Array.from(nodes).map(nodeId => {
      const nodeData = bigNodeData[nodeId];
      const nodeSteps = steps[nodeId] || [];
      const prevNodeSteps = previousSteps[nodeId] || [];
      
      // Calculate radius based on steps
      const radius = nodeData.isSpecial 
        ? 50 
        : (nodeSteps.length > 0 ? diamondSpacing + smallNodeRadius + bigNodeRadiusPadding : smallNodeRadius + bigNodeRadiusPadding);
      
      // Determine current label based on labelHistory and number of steps
      let currentLabel = nodeData.label;
      let labelChanged = false;
      let currentLabelIndex = -1;
      
      if (nodeData.labelHistory && nodeData.labelHistory.length > 0 && nodeSteps.length > 0) {
        // Extract prefix (e.g., "节点 4: ") from the original label
        const colonIndex = nodeData.label.indexOf(':');
        const prefix = colonIndex >= 0 ? nodeData.label.substring(0, colonIndex + 1) + ' ' : '';
        
        // Use the label from labelHistory based on how many steps we have
        // Clamp to the available labels (in case we have more steps than label history entries)
        currentLabelIndex = Math.min(nodeSteps.length - 1, nodeData.labelHistory.length - 1);
        const historicalLabel = nodeData.labelHistory[currentLabelIndex];
        
        // Combine prefix with historical label
        currentLabel = prefix + historicalLabel;
        
        // Check if label changed from previous frame
        const prevLabelIndex = prevNodeSteps.length > 0 
          ? Math.min(prevNodeSteps.length - 1, nodeData.labelHistory.length - 1)
          : -1;
        
        // Label changed if we have more steps and the label index increased
        if (currentLabelIndex > prevLabelIndex && currentLabelIndex > 0 && currentFrame.highlightNode === nodeId) {
          labelChanged = true;
        }
      }
      
      return {
        ...nodeData,
        id: nodeId,
        radius,
        steps: nodeSteps,
        currentLabel, // Add the dynamic label
        labelChanged, // Flag if label just changed
        currentLabelIndex // Index of current label in history
      };
    });
  }, [currentFrame, currentFrameIndex, frames]);

  // Build edges from current frame state
  const currentEdges = useMemo(() => {
    if (!currentFrame?.graphState?.connections) return [];
    return currentFrame.graphState.connections;
  }, [currentFrame]);

  // Get current workflow ID for highlighting
  const currentWorkflowId = currentFrame?.workflow?.id;

  // Animation control functions
  const handlePlay = () => {
    if (currentFrameIndex >= frames.length - 1) {
      setCurrentFrameIndex(0);
    }
    setIsPlaying(true);
  };

  const handlePause = () => {
    setIsPlaying(false);
  };

  const handleReset = () => {
    setIsPlaying(false);
    setCurrentFrameIndex(0);
    setPanelStartIndex(null);
    setSeenCreate(false);
    setSeenMerge(false);
    setEventPanelVisible(false);
    setEventPanelDecision(null);
    if (hideEventTimerRef.current) clearTimeout(hideEventTimerRef.current);
  };

  const handleStepForward = () => {
    setIsPlaying(false);
    setCurrentFrameIndex(prev => Math.min(prev + 1, frames.length - 1));
  };

  const handleStepBackward = () => {
    setIsPlaying(false);
    setCurrentFrameIndex(prev => Math.max(prev - 1, 0));
  };

  // Auto-advance frames when playing
  useEffect(() => {
    if (isPlaying) {
      animationTimerRef.current = setInterval(() => {
        setCurrentFrameIndex(prev => {
          if (prev >= frames.length - 1) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, speed);
    }

    return () => {
      if (animationTimerRef.current) {
        clearInterval(animationTimerRef.current);
      }
    };
  }, [isPlaying, speed, frames.length]);

  // Arrow key navigation
  useEffect(() => {
    const handleKeyDown = (event) => {
      // Ignore when focused on input elements
      if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
        return;
      }

      switch (event.key) {
        case ' ': // Some browsers
        case 'Spacebar': // Old browsers
        case 'Space': // event.code in modern browsers
          event.preventDefault();
          if (isPlaying) {
            handlePause();
          } else {
            handlePlay();
          }
          break;
        case 'ArrowLeft':
          if (!isPlaying) {
            event.preventDefault();
            handleStepBackward();
          }
          break;
        case 'ArrowRight':
          if (!isPlaying) {
            event.preventDefault();
            handleStepForward();
          }
          break;
        default:
          break;
      }
    };
    // Add event listener to document
    document.addEventListener('keydown', handleKeyDown);

    // Cleanup
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isPlaying, frames.length]); // Include frames.length to ensure handlers are updated

  // Initialize SVG and zoom behavior (only once)
  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);
    
    const g = svg.append('g').attr('class', 'graph-group');
    groupRef.current = g;

    // Define zoom behavior
    const zoom = d3.zoom()
      .scaleExtent([0.5, 3])
      .on('zoom', (event) => {
        zoomTransformRef.current = event.transform;
        g.attr('transform', event.transform);
      });

    zoomBehaviorRef.current = zoom;
    svg.call(zoom);
    
    return () => {
      svg.select('.graph-group').remove();
    };
  }, []); // Only run once

  // Render graph content with D3
  useEffect(() => {
    const g = groupRef.current;
    if (!g) return;

    // Clear previous content
    g.selectAll('*').remove();

    // Only process forward edges (no backtrack edges in build mode)
    const forwardEdges = currentEdges.filter(conn => conn.isBacktrack !== true);
    
    // Separate curved edges from straight edges (only for forward edges)
    // Use data-driven approach to determine which edges should be curved
    const curvedEdges = forwardEdges.filter(conn => 
      isCurvedEdge(conn.from, conn.to, edgeConfigurations)
    );
    const straightEdges = forwardEdges.filter(conn => 
      !isCurvedEdge(conn.from, conn.to, edgeConfigurations)
    );

    // Draw straight edges
    g.selectAll('.edge')
      .data(straightEdges)
      .enter()
      .append('line')
      .attr('class', 'edge')
      .attr('stroke', (conn) => {
        // Use current workflow color if part of current workflow, otherwise first workflow color
        const isCurrentWorkflow = conn.workflows?.includes(currentWorkflowId);
        if (isCurrentWorkflow && currentWorkflowId) {
          return workflowColors[currentWorkflowId];
        }
        const firstWorkflow = conn.workflows?.[0];
        return firstWorkflow ? workflowColors[firstWorkflow] : '#ccc';
      })
      .attr('stroke-width', (conn) => {
        // Thicker line if part of current workflow
        const isCurrentWorkflow = conn.workflows?.includes(currentWorkflowId);
        return isCurrentWorkflow ? 4 : 3;
      })
      .attr('opacity', (conn) => {
        // Higher opacity if part of current workflow
        const isCurrentWorkflow = conn.workflows?.includes(currentWorkflowId);
        return isCurrentWorkflow ? 1.0 : 0.6;
      })
      .attr('marker-end', 'url(#arrowhead-buildmode)')
      .attr('x1', (conn) => {
        const source = currentNodes.find((n) => n.id === conn.from);
        const target = currentNodes.find((n) => n.id === conn.to);
        if (!source || !target) return 0;
        
        const srcX = source.x + 600;
        const srcY = source.y + 350;
        const tgtX = target.x + 600;
        const tgtY = target.y + 350;
        
        const pts = getOffsetPoint(srcX, srcY, tgtX, tgtY, source.radius);
        return pts.x1;
      })
      .attr('y1', (conn) => {
        const source = currentNodes.find((n) => n.id === conn.from);
        const target = currentNodes.find((n) => n.id === conn.to);
        if (!source || !target) return 0;
        
        const srcX = source.x + 600;
        const srcY = source.y + 350;
        const tgtX = target.x + 600;
        const tgtY = target.y + 350;
        
        const pts = getOffsetPoint(srcX, srcY, tgtX, tgtY, source.radius);
        return pts.y1;
      })
      .attr('x2', (conn) => {
        const source = currentNodes.find((n) => n.id === conn.from);
        const target = currentNodes.find((n) => n.id === conn.to);
        if (!source || !target) return 0;
        
        const srcX = source.x + 600;
        const srcY = source.y + 350;
        const tgtX = target.x + 600;
        const tgtY = target.y + 350;
        
        const ptsEnd = getOffsetPoint(srcX, srcY, tgtX, tgtY, target.radius);
        return ptsEnd.x2;
      })
      .attr('y2', (conn) => {
        const source = currentNodes.find((n) => n.id === conn.from);
        const target = currentNodes.find((n) => n.id === conn.to);
        if (!source || !target) return 0;
        
        const srcX = source.x + 600;
        const srcY = source.y + 350;
        const tgtX = target.x + 600;
        const tgtY = target.y + 350;
        
        const ptsEnd = getOffsetPoint(srcX, srcY, tgtX, tgtY, target.radius);
        return ptsEnd.y2;
      });

    // Draw curved edges
    g.selectAll('.edge-curved')
      .data(curvedEdges)
      .enter()
      .append('path')
      .attr('class', 'edge-curved')
      .attr('stroke', (conn) => {
        // Use current workflow color if part of current workflow, otherwise first workflow color
        const isCurrentWorkflow = conn.workflows?.includes(currentWorkflowId);
        if (isCurrentWorkflow && currentWorkflowId) {
          return workflowColors[currentWorkflowId];
        }
        const firstWorkflow = conn.workflows?.[0];
        return firstWorkflow ? workflowColors[firstWorkflow] : '#ccc';
      })
      .attr('stroke-width', (conn) => {
        // Thicker line if part of current workflow
        const isCurrentWorkflow = conn.workflows?.includes(currentWorkflowId);
        return isCurrentWorkflow ? 3 : 2;
      })
      .attr('fill', 'none')
      .attr('opacity', (conn) => {
        // Higher opacity if part of current workflow
        const isCurrentWorkflow = conn.workflows?.includes(currentWorkflowId);
        return isCurrentWorkflow ? 1.0 : 0.6;
      })
      .attr('marker-end', 'url(#arrowhead-buildmode)')
      .attr('d', (conn) => {
        const source = currentNodes.find((n) => n.id === conn.from);
        const target = currentNodes.find((n) => n.id === conn.to);
        if (!source || !target) return '';
        
        const srcX = source.x + 600;
        const srcY = source.y + 350;
        const tgtX = target.x + 600;
        const tgtY = target.y + 350;
        
        // Use data-driven curve calculation
        const curveConfig = getCurveConfiguration(conn.from, conn.to, edgeConfigurations);
        return calculateCurvePath(srcX, srcY, tgtX, tgtY, source.radius, target.radius, curveConfig);
      });


    // Draw big nodes
    const bigNodeGroups = g
      .selectAll('.big-node-group')
      .data(currentNodes, (d) => d.id)
      .enter()
      .append('g')
      .attr('class', 'big-node-group')
      .attr('transform', (d) => `translate(${d.x + 600},${d.y + 350})`);

    // Apply animation styles to highlighted node
    bigNodeGroups
      .append('circle')
      .attr('r', (d) => d.radius)
      .attr('stroke', (d) => {
        if (currentFrame.highlightNode === d.id) {
          const styles = getAnimationFrameStyles(currentFrame.action);
          return styles.stroke;
        }
        return d.isSpecial ? '#333' : '#888';
      })
      .attr('stroke-width', (d) => {
        if (currentFrame.highlightNode === d.id) {
          return 4;
        }
        return d.isSpecial ? 4 : 3;
      })
      .attr('fill', (d) => d.isSpecial ? (d.color || 'rgba(0, 0, 0, 0)') : 'rgba(0, 0, 0, 0)')
      .attr('opacity', (d) => d.isSpecial ? 0.6 : 1)
      .style('filter', (d) => {
        if (currentFrame.highlightNode === d.id) {
          const styles = getAnimationFrameStyles(currentFrame.action);
          return styles.filter;
        }
        return 'none';
      })
      .style('cursor', 'pointer')
      .on('click', (event, d) => {
        event.stopPropagation();
        setSelectedBigNode(d);
      });

    // Add labels for big nodes
    bigNodeGroups.each(function(d) {
      const group = d3.select(this);
      const labelY = d.isSpecial ? 5 : (d.radius + 20);
      const fontSize = d.isSpecial ? 18 : 16;
      const labelText = d.currentLabel || d.label; // Use currentLabel if available
      
      if (!d.isSpecial) {
        const textWidth = labelText.length * fontSize * 0.77;
        const padding = 8;
        
        group.append('rect')
          .attr('x', -textWidth / 2 - padding)
          .attr('y', labelY - fontSize + 2)
          .attr('width', textWidth + padding * 2)
          .attr('height', fontSize + padding)
          .attr('fill', '#fafafa')
          .attr('stroke', '#ddd')
          .attr('stroke-width', 1)
          .attr('rx', 4)
          .attr('opacity', 0.95);
      }
      
      // For SVG text elements, we strip HTML tags since SVG doesn't support HTML directly
      // HTML rendering is supported in React components (panels) where it's more useful
      const strippedText = typeof labelText === 'string' 
        ? labelText.replace(/<[^>]+>/g, '') // Strip HTML tags for SVG
        : labelText;
      
      group.append('text')
        .text(strippedText)
        .attr('text-anchor', 'middle')
        .attr('y', labelY)
        .attr('fill', d.isSpecial ? '#1f2937' : '#555')
        .style('font-weight', d.isSpecial ? '900' : 'bold')
        .style('font-size', `${fontSize}px`)
        .style('letter-spacing', d.isSpecial ? '1px' : 'normal');
    });

    // Draw small nodes
    bigNodeGroups.each(function (d) {
      const group = d3.select(this);
      
      group
        .selectAll('.small-node')
        .data(d.steps, (s) => s.stepId)
        .enter()
        .append('circle')
        .attr('class', 'small-node')
        .attr('r', smallNodeRadius)
        .attr('cy', (s, i) => getDiamondPosition(i, diamondSpacing).cy)
        .attr('cx', (s, i) => getDiamondPosition(i, diamondSpacing).cx)
        .attr('fill', (s) => workflowColors[s.workflow] || '#ddd')
        .attr('stroke', '#999')
        .attr('stroke-width', 1)
        .attr('opacity', 1);

      group
        .selectAll('.small-node-label')
        .data(d.steps, (s) => s.stepId)
        .enter()
        .append('text')
        .attr('class', 'small-node-label')
        .attr('x', (s, i) => getDiamondPosition(i, diamondSpacing).cx)
        .attr('y', (s, i) => getDiamondPosition(i, diamondSpacing).cy + 4)
        .attr('text-anchor', 'middle')
        .style('font-size', '9px')
        .style('fill', '#222')
        .attr('opacity', 1)
        .text((s) => s.stepId);
    });

    // Add click handler to SVG background to clear selection
    const svg = d3.select(svgRef.current);
    svg.on('click', () => setSelectedBigNode(null));

  }, [currentNodes, currentEdges, currentFrame]);

  return (
    <div className="build-mode-container">
      {/* Graph SVG */}
      <div style={{ position: 'relative', width: '100%', maxWidth: 'min(1200px, 95vw)', margin: '-20px auto 0 auto' }}>
        <svg
          ref={svgRef}
          viewBox="0 0 1200 700"
          preserveAspectRatio="xMidYMid meet"
          style={{
            width: '100%',
            height: 'auto',
            maxHeight: '60vh',
            border: '1px solid #ccc',
            borderRadius: 8,
            backgroundColor: '#fafafa'
          }}
        >
          <defs>
            <marker
              id="arrowhead-buildmode"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto"
            >
              <path d="M0,0 L10,5 L0,10 Z" fill="#555" />
            </marker>
          </defs>
        </svg>
        {/* In-graph event panel: positioned within graph boundaries */}
        <div style={{ position: 'absolute', top: 8, left: 8, right: 'auto', bottom: 'auto', zIndex: 10, pointerEvents: 'none' }}>
          <div style={{ pointerEvents: 'auto' }}>
            <BuildEventPanel
              visible={isPanelVisible}
              decisionText={eventPanelDecision}
              onClose={() => {
                setEventPanelVisible(false);
                if (hideEventTimerRef.current) clearTimeout(hideEventTimerRef.current);
              }}
            />
          </div>
        </div>
      </div>

      {/* Big Node Info Box */}
      {selectedBigNode && (
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
            <HTMLRenderer content={selectedBigNode.currentLabel || selectedBigNode.label} tag="span" />
          </h3>
          {selectedBigNode.labelHistory && selectedBigNode.labelHistory.length > 0 && (
            <div style={{ 
              marginTop: 'clamp(8px, 1vh, 12px)',
              padding: 'clamp(8px, 1vh, 10px)',
              background: '#f9fafb',
              borderRadius: 6,
              fontSize: 'clamp(11px, 1.1vh, 12px)',
              color: '#374151',
              lineHeight: 1.5,
              border: '1px solid #e5e7eb',
            }}>
              <div style={{ fontWeight: '600', marginBottom: '6px', color: '#111827' }}>
                标签历史:
              </div>
              <ul style={{ margin: 0, paddingLeft: '16px' }}>
                {selectedBigNode.labelHistory.slice(0, selectedBigNode.currentLabelIndex + 1).map((label, index) => (
                  <li key={index} style={{ 
                    marginBottom: '4px',
                    fontWeight: index === selectedBigNode.currentLabelIndex ? 'bold' : 'normal',
                    color: index === selectedBigNode.currentLabelIndex ? '#1f2937' : '#374151'
                  }}>
                    <HTMLRenderer content={label} tag="span" />
                    {index === selectedBigNode.currentLabelIndex && (
                      <span style={{ marginLeft: '8px', fontSize: '10px', color: '#059669' }}>
                        (当前)
                      </span>
                    )}
                  </li>
                ))}
                {selectedBigNode.currentLabelIndex < selectedBigNode.labelHistory.length - 1 && (
                  <li style={{ 
                    marginBottom: '4px', 
                    color: '#9ca3af', 
                    fontStyle: 'italic',
                    fontSize: '10px'
                  }}>
                    ...还有 {selectedBigNode.labelHistory.length - selectedBigNode.currentLabelIndex - 1} 个标签待发现
                  </li>
                )}
              </ul>
            </div>
          )}
          {selectedBigNode.steps && selectedBigNode.steps.length > 0 && (
            <div style={{ 
              marginTop: 'clamp(8px, 1vh, 12px)',
              padding: 'clamp(8px, 1vh, 10px)',
              background: '#f0f9ff',
              borderRadius: 6,
              fontSize: 'clamp(11px, 1.1vh, 12px)',
              color: '#1e40af',
              lineHeight: 1.5,
              border: '1px solid #bfdbfe',
            }}>
              <div style={{ fontWeight: '600', marginBottom: '6px' }}>
                当前步骤数: {selectedBigNode.steps.length}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Controls Layout: Decision Panel + Progress on left, Controls on right */}
      <div className="build-mode-controls-wrapper">
        {/* Left Side: Decision Panel + Progress */}
        <div className="build-mode-info-panel">
          {/* Decision Panel */}
          <div className={`build-mode-decision-panel action-${currentFrame?.action?.toLowerCase()} ${!currentFrame?.decisionText?.workflow ? 'centered' : ''}`}>
            {currentFrame?.decisionText?.workflow && (
              <div className="decision-workflow">{currentFrame.decisionText.workflow}</div>
            )}
            <div className="decision-details">{currentFrame?.decisionText?.details}</div>
          </div>

          {/* Progress Indicator */}
          <div className="progress-indicator">
            <div className="progress-text">
              步骤 {currentFrameIndex + 1} / 共 {frames.length} 步骤
              {(() => {
                // Check if any node's label changed in this frame
                const changedNode = currentNodes.find(n => n.labelChanged);
                if (changedNode) {
                  return (
                    <span style={{ marginLeft: '10px', color: '#d97706' }}>
                      — 节点名字换成了 <HTMLRenderer content={changedNode.currentLabel} tag="strong" />
                    </span>
                  );
                }
                return null;
              })()}
            </div>
            <div className="progress-bar-container">
              <div className="progress-bar" style={{ width: `${progress}%` }} />
            </div>
          </div>
        </div>

        {/* Right Side: Playback Controls */}
        <div className="build-mode-controls-panel">
          <ControlPanel
            isPlaying={isPlaying}
            onPlayPause={() => isPlaying ? handlePause() : handlePlay()}
            onReset={handleReset}
            onStepForward={handleStepForward}
            onStepBackward={handleStepBackward}
          />
          
          <div className="speed-control">
            <label className="speed-label">速度:</label>
            <input
              type="range"
              min="200"
              max="2000"
              step="100"
              value={2200 - speed}
              onChange={(e) => setSpeed(2200 - Number(e.target.value))}
              className="speed-slider"
            />
            <span className="speed-label">{(2200 - speed) / 1000}x</span>
          </div>
        </div>
      </div>
    </div>
  );
}

