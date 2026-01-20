// src/components/GraphVisualiser.js
import React, { useEffect, useState, useCallback, useMemo } from 'react';
import WorkflowGraph from './WorkflowGraph';
import RLVisualizerSVG from './RLVisualizerSVG';
import ReasoningPanel from './ReasoningPanel';
import WorkflowTracker from './WorkflowTracker';
import ControlPanel from './ControlPanel';
import '../styles/BuildMode.css'; // Import for progress indicator styles
import { connections, workflows, edgeConfigurations } from '../data/realDataStocks';
import { getWorkflowTraversal } from '../data/workflowHelpers';


export default function GraphVisualiser({ mode: parentMode, setMode: setParentMode }) {
  const [viewMode, setViewMode] = useState('default'); // 'default' | 'traverse' (internal view state)
  const [currentStep, setCurrentStep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [nodeLayout, setNodeLayout] = useState([]); // [{ id, x, y, width, height }, ...]
  const [transform, setTransform] = useState(null); // { k, x, y } if you're using zoom/pan
  const [selectedWorkflow, setSelectedWorkflow] = useState('workflow2'); // Default to workflow2
  const [speed, setSpeed] = useState(1800); // ms per frame
  
  // Memoize callbacks to prevent unnecessary re-renders
  const handleLayoutComputed = useCallback((layout) => {
    setNodeLayout(layout);
  }, []);
  
  const handleTransformChange = useCallback((transform) => {
    setTransform(transform);
  }, []);

  // Dynamically generate workflow traversals
  const workflowTraversals = useMemo(() => {
    return Object.keys(workflows).reduce((acc, workflowId) => {
      acc[workflowId] = getWorkflowTraversal(workflowId, workflows);
      return acc;
    }, {});
  }, [workflows]);

  // Helper function to determine workflow status
  const getWorkflowStatus = (workflow) => {
    if (!workflow.errorType) {
      return 'Correct ✅';
    }
    
    switch (workflow.errorType) {
      case 'reasoning-chain-error':
        return 'Reasoning Error ⚠️';
      case 'agent-error':
        return 'Agent Error ⚠️';
      default:
        return 'Error ⚠️';
    }
  };

  // Generate workflow options dynamically
  const workflowOptions = Object.values(workflows).map(workflow => ({
    value: workflow.id,
    label: `Workflow ${workflow.id.replace('workflow', '')}: ${workflow.title} (${getWorkflowStatus(workflow)})`
  }));

  // Get current traversal based on selected workflow
  const currentTraversal = workflowTraversals[selectedWorkflow] || [];
  
  const currentWorkflowData = workflows[selectedWorkflow];

  // Calculate progress for progress indicator
  const progress = currentTraversal.length > 1 
    ? (currentStep / (currentTraversal.length - 1)) * 100 
    : 0;

  // Drive traversal playback
  useEffect(() => {
    if (!isPlaying || viewMode !== 'traverse') return;
    const t = setInterval(() => {
      setCurrentStep(s => Math.min(s + 1, currentTraversal.length - 1));
    }, speed);
    return () => clearInterval(t);
  }, [isPlaying, viewMode, currentTraversal.length, speed]);

  // Reset step when workflow changes
  useEffect(() => {
    setCurrentStep(0);
    setIsPlaying(false);
  }, [selectedWorkflow]);

  // Arrow key navigation
  useEffect(() => {
    const handleKeyDown = (event) => {
      const isTextInput = event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA' || event.target.isContentEditable;

      // Spacebar toggles play/pause in traverse mode (unless typing in inputs)
      if (viewMode === 'traverse' && !isTextInput) {
        const isSpace = event.code === 'Space' || event.key === ' ' || event.key === 'Spacebar' || event.key === 'Space';
        if (isSpace) {
          event.preventDefault();
          setIsPlaying(v => !v);
          return;
        }
      }

      // Arrow keys only when in traverse mode, paused, and not typing in inputs
      if (viewMode !== 'traverse' || isPlaying || isTextInput) {
        return;
      }

      switch (event.key) {
        case 'ArrowLeft':
          event.preventDefault();
          setCurrentStep(s => Math.max(s - 1, 0));
          break;
        case 'ArrowRight':
          event.preventDefault();
          setCurrentStep(s => Math.min(s + 1, currentTraversal.length - 1));
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
  }, [viewMode, isPlaying, currentTraversal.length]);

  return (
    <>
      {/* Graph container */}
      <div style={{ position: 'relative' }}>
        <WorkflowGraph
          onLayoutComputed={handleLayoutComputed}
          onTransformChange={handleTransformChange}
          selectedWorkflow={viewMode === 'traverse' ? selectedWorkflow : null}
          currentStep={viewMode === 'traverse' ? currentStep : null}
          traversal={viewMode === 'traverse' ? currentTraversal : null}
        >
          {/* Traversal overlay */}
          {viewMode === 'traverse' && nodeLayout.length > 0 && (
            <RLVisualizerSVG
              traversal={currentTraversal}
              currentStep={currentStep}
              nodeLayout={nodeLayout}
              transform={transform}
              edgeConfigurations={edgeConfigurations}
            />
          )}
        </WorkflowGraph>
        
        {/* Workflow Tracker - rendered outside SVG on left side */}
        {viewMode === 'traverse' && (
          <WorkflowTracker
            traversal={currentTraversal}
            currentStep={currentStep}
            selectedWorkflow={selectedWorkflow}
          />
        )}
        
        {/* Reasoning Panel - rendered outside SVG on right side */}
        {viewMode === 'traverse' && (
          <ReasoningPanel
            traversal={currentTraversal}
            currentStep={currentStep}
          />
        )}
      </div>

      {/* Controls Layout: Workflow Selector + Progress on left, Controls on right */}
      <div className="build-mode-controls-wrapper" style={{ maxWidth: 'min(1200px, 95vw)', margin: '0 auto' }}>
        {/* Left Side: Workflow Selector + Progress */}
        <div className="build-mode-info-panel">
          {/* Workflow Selector */}
          <div style={{ 
            display: 'flex', 
            flexDirection: 'column', 
            gap: 'clamp(5px, 1vh, 10px)',
            background: '#f9fafb',
            padding: 'clamp(10px, 1.5vh, 15px) clamp(15px, 2vw, 20px)',
            borderRadius: 8,
            border: '1px solid #e5e7eb',
          }}>
            <label style={{ fontWeight: 'bold', fontSize: 'clamp(12px, 1.4vh, 14px)', color: '#374151' }}>
              选择 Workflow:
            </label>
            <select 
              value={selectedWorkflow}
              onChange={(e) => setSelectedWorkflow(e.target.value)}
              style={{
                padding: 'clamp(6px, 0.8vh, 8px) clamp(8px, 1vw, 12px)',
                fontSize: 'clamp(12px, 1.4vh, 14px)',
                borderRadius: 6,
                border: '1px solid #d1d5db',
                backgroundColor: '#fff',
                cursor: 'pointer',
              }}
            >
              {workflowOptions.map(option => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            {currentWorkflowData && (
              <div style={{ 
                marginTop: 'clamp(4px, 0.8vh, 8px)', 
                padding: 'clamp(8px, 1vh, 10px)',
                background: '#fff',
                borderRadius: 6,
                fontSize: 'clamp(11px, 1.3vh, 13px)',
                color: '#6b7280',
              }}>
                <div style={{ fontWeight: 'bold', color: '#111827', marginBottom: 'clamp(2px, 0.4vh, 4px)', fontSize: 'clamp(12px, 1.4vh, 14px)' }}>
                  {currentWorkflowData.title}
                </div>
                <div>{currentWorkflowData.problem}</div>
                
              </div>
            )}
          </div>

          {/* Progress Indicator - only show in traverse mode */}
          {viewMode === 'traverse' && (
            <div className="progress-indicator">
              <div className="progress-text">
                步骤 {currentStep + 1} / 共 {currentTraversal.length} 步骤
              </div>
              <div className="progress-bar-container">
                <div className="progress-bar" style={{ width: `${progress}%` }} />
              </div>
            </div>
          )}
        </div>

        {/* Right Side: Playback Controls */}
        <div className="build-mode-controls-panel">
          <button 
            onClick={() => setViewMode(m => (m === 'traverse' ? 'default' : 'traverse'))}
            style={{
              padding: 'clamp(10px, 1.2vh, 12px) clamp(15px, 2vw, 20px)',
              fontSize: 'clamp(13px, 1.4vh, 14px)',
              fontWeight: '600',
              borderRadius: 8,
              border: '1px solid #d1d5db',
              backgroundColor: viewMode === 'traverse' ? '#3b82f6' : '#6b7280',
              color: '#fff',
              cursor: 'pointer',
              minWidth: '150px',
            }}
          >
            {viewMode === 'traverse' ? '✓ 遍历中' : '开始遍历'}
          </button>

          {/* Playback controls */}
          {viewMode === 'traverse' && (
            <>
              <ControlPanel
                isPlaying={isPlaying}
                onPlayPause={() => setIsPlaying(v => !v)}
                onReset={() => setCurrentStep(0)}
                onStepForward={() =>
                  setCurrentStep(s => Math.min(s + 1, currentTraversal.length - 1))
                }
                onStepBackward={() =>
                  setCurrentStep(s => Math.max(s - 1, 0))
                }
              />
              
              <div className="speed-control">
                <label className="speed-label">速度:</label>
                <input
                  type="range"
                  min="200"
                  max="3000"
                  step="100"
                  value={3200 - speed}
                  onChange={(e) => setSpeed(3200 - Number(e.target.value))}
                  className="speed-slider"
                />
                <span className="speed-label">{((3200 - speed) / 1000).toFixed(1)}x</span>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}
