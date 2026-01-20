// src/components/WorkflowTracker.js
import React, { useState, useRef, useEffect } from 'react';
import { workflows } from '../data/realDataStocks';
import HTMLRenderer from './utils/HTMLRenderer';

/**
 * Workflow Tracker component that displays a vertical timeline of workflow steps
 * Shows normal flow, errors, backtracking analysis, and corrections
 */
export default function WorkflowTracker({ currentStep, traversal, selectedWorkflow }) {
  const [width, setWidth] = useState(350);
  const [isResizing, setIsResizing] = useState(false);
  const [hoveredStep, setHoveredStep] = useState(null);
  const panelRef = useRef(null);
  const currentStepRef = useRef(null);

  // Handle resize
  useEffect(() => {
    if (!isResizing) return;
    
    const handleMouseMove = (e) => {
      if (!panelRef.current) return;
      const panelRect = panelRef.current.getBoundingClientRect();
      const newWidth = e.clientX - panelRect.left;
      const clampedWidth = Math.max(250, Math.min(500, newWidth));
      setWidth(clampedWidth);
    };
    
    const handleMouseUp = () => {
      setIsResizing(false);
    };
    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing]);

  // Auto-scroll to current step
  useEffect(() => {
    if (currentStepRef.current) {
      currentStepRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }
  }, [currentStep]);

  // Console logging of traversal and current step changes
  useEffect(() => {
    if (!traversal || traversal.length === 0 || !selectedWorkflow) return;

    const summary = traversal.map((s, i) => ({
      idx: i + 1,
      stepId: s.stepId,
      from: s.from || '',
      to: s.to || s.nodeMapping || '',
      status: s.backtrack === true ? 'BACKTRACK' : s.correct === true ? 'OK' : s.correct === false ? 'ERR' : 'INFO',
      pass: s.pass,
      desc: s.description || s.question || ''
    }));

    console.groupCollapsed(`WorkflowTracker: traversal updated (${selectedWorkflow}) - ${summary.length} steps`);
    console.table(summary);
    if (typeof currentStep === 'number' && currentStep >= 0 && currentStep < traversal.length) {
      const s = traversal[currentStep];
      console.log('Current step', {
        index1: currentStep + 1,
        stepId: s.stepId,
        from: s.from,
        to: s.to || s.nodeMapping,
        backtrack: s.backtrack === true,
        correct: s.correct,
        pass: s.pass,
        error: s.error,
        errorDetails: s.errorDetails
      });
    }
    console.groupEnd();
  }, [traversal, currentStep, selectedWorkflow]);

  // Don't render if no valid data
  if (!traversal || traversal.length === 0 || !selectedWorkflow) return null;

  const workflowData = workflows[selectedWorkflow];
  if (!workflowData) return null;

  // Helper function to normalize step IDs (strip suffixes like -analyze, -b, -wrong)
  const normalizeStepId = (stepId) => {
    if (!stepId) return stepId;
    // Remove suffixes: -analyze, -b, -wrong, etc.
    return stepId.replace(/-(analyze|b|wrong|final)$/g, '');
  };

  // Extract canonical steps from workflow (unique base step IDs in order)
  const canonicalSteps = [];
  const seenSteps = new Set();
  
  // This code builds "canonicalSteps" by extracting a unique set of normalized steps for the workflow,
  // but skips any step whose stepId is 'return-to-source' or contains 'summary' so it will not appear in the rendered tracker.
  workflowData.steps.forEach(step => {
    
    if (step.stepId.includes('return-to-source')) return; // omit special analysis return step
    if (step.stepId.includes('summary')) return; // omit summary steps
    const normalized = normalizeStepId(step.stepId);
    if (!seenSteps.has(normalized)) {
      seenSteps.add(normalized);
      canonicalSteps.push({
        stepId: normalized,
        originalStep: step,
      });
    }
  });

  // For canonical step state computation, we also want to not consider traversal steps for "return-to-source" or any "summary" steps
  const getCanonicalStepState = (canonicalStepId, canonicalIndex) => {
    // Filter out traversal steps with stepId 'return-to-source'
    const matchingSteps = [];
    let matchingIndices = [];
    
    traversal.forEach((step, idx) => {
      if (typeof step?.stepId !== 'string') return; // skip synthetic moves
      if (step.stepId.includes('return-to-source')) return; // skip this step
      if (step.stepId.includes('summary')) return; // skip summary steps
      const normalized = normalizeStepId(step.stepId);
      if (normalized === canonicalStepId) {
        matchingSteps.push(step);
        matchingIndices.push(idx);
      }
    });

    // Check if currently backtracking through this step
    const currentTraversalStep = traversal[currentStep];
    const isBacktracking = currentTraversalStep?.backtrack === true && 
                          normalizeStepId(currentTraversalStep.stepId) === canonicalStepId;

    // Special case: when traversal begins with the synthetic 'source-to-first' step at index 0,
    // mark the first canonical step as the current one so the first node shows as traversed.
    if (
      currentStep === 0 &&
      traversal[0]?.id === 'source-to-first' &&
      canonicalIndex === 0
    ) {
      const firstMatch = matchingSteps[0] || canonicalSteps[0].originalStep;
      return { type: 'normal', step: firstMatch };
    }

    // Find the most recent matching step at or before currentStep
    let activeStep = null;
    let activeIndex = -1;
    
    for (let i = matchingIndices.length - 1; i >= 0; i--) {
      if (matchingIndices[i] <= currentStep) {
        activeStep = matchingSteps[i];
        activeIndex = matchingIndices[i];
        break;
      }
    }

    // After the synthetic start, do not mark the first canonical step as completed
    // until it is actually visited by a real traversal step.

    // Determine state
    if (activeIndex === currentStep) {
      // If the current step is a backtrack step, mark as backtrack (yellow)
      if (isBacktracking || activeStep?.backtrack === true || activeStep?.pass === null) {
        return { type: 'backtrack', step: activeStep || currentTraversalStep };
      }
      // Current non-backtrack step is blue (normal)
      return { type: 'normal', step: activeStep };
    } else if (activeIndex >= 0 && activeIndex < currentStep) {
      // Past step:
      // - yellow if it was an explicit backtrack step (backtrack:true or pass:null)
      // - red if incorrect (correct === false)
      // - green if completed
      if (activeStep?.backtrack === true || activeStep?.pass === null) {
        return { type: 'backtrack', step: activeStep };
      }
      if (activeStep?.correct === false) return { type: 'error', step: activeStep };
      return { type: 'completed', step: activeStep };
    } 
    // Special handling for first canonical step after synthetic 'source-to-first'
    else if (
      canonicalIndex === 0 &&
      currentStep > 0 &&
      traversal[0]?.id === 'source-to-first'
    ) {
      const firstMatch = matchingSteps[0] || canonicalSteps[0].originalStep;
      if (firstMatch.correct === false) return { type: 'error', step: firstMatch };
      return { type: 'completed', step: firstMatch };
    } 
    else {
      // Future step - not yet reached
      return { type: 'pending', step: canonicalSteps[canonicalIndex].originalStep };
    }
  };

  // Helper function to get step styling based on state
  const getStepStyle = (stateType) => {
    const baseStyle = {
      padding: 'clamp(8px, 1vh, 12px)',
      marginBottom: '4px',
      borderRadius: '6px',
      cursor: 'pointer',
      transition: 'all 0.2s ease',
      fontSize: 'clamp(11px, 1.2vh, 12px)',
      position: 'relative',
    };

    let backgroundColor, borderColor, textColor, fontWeight, opacity, boxShadow;

    switch (stateType) {
      case 'error':
        // Current error state (red)
        backgroundColor = '#fecaca';
        borderColor = '#ef4444';
        textColor = '#991b1b';
        fontWeight = '600';
        boxShadow = '0 2px 8px rgba(0, 0, 0, 0.1)';
        break;
      
      case 'analysis':
        // Currently analyzing
        backgroundColor = '#fecaca';
        borderColor = '#ef4444';
        textColor = '#991b1b';
        fontWeight = '600';
        boxShadow = '0 2px 8px rgba(0, 0, 0, 0.1)';
        break;
      
      case 'correction':
        // Currently correcting
        backgroundColor = '#d1fae5';
        borderColor = '#10b981';
        textColor = '#065f46';
        fontWeight = '600';
        boxShadow = '0 2px 8px rgba(0, 0, 0, 0.1)';
        break;
      
      case 'backtrack':
        // Currently backtracking through this step (yellow)
        backgroundColor = '#fef3c7';
        borderColor = '#f59e0b';
        textColor = '#92400e';
        fontWeight = '600';
        boxShadow = '0 2px 8px rgba(0, 0, 0, 0.1)';
        break;
      
      case 'normal':
        // Current normal step
        backgroundColor = '#dbeafe';
        borderColor = '#3b82f6';
        textColor = '#1e40af';
        fontWeight = '600';
        boxShadow = '0 2px 8px rgba(0, 0, 0, 0.1)';
        break;
      
      case 'completed':
        // Past completed step
        backgroundColor = '#ecfdf5';
        borderColor = '#e5e7eb';
        textColor = '#065f46';
        opacity = 0.8;
        break;
      
      case 'corrected':
        // Past step that was corrected
        backgroundColor = '#d1fae5';
        borderColor = '#e5e7eb';
        textColor = '#047857';
        opacity = 0.8;
        break;
      
      case 'pending':
      default:
        // Future step - not yet reached
      backgroundColor = '#f9fafb';
        borderColor = '#e5e7eb';
      textColor = '#6b7280';
        opacity = 0.6;
        break;
    }
    
    return {
      ...baseStyle,
      backgroundColor,
      border: borderColor ? `${stateType === 'pending' || stateType === 'completed' || stateType === 'corrected' ? '1px' : '2px'} solid ${borderColor}` : '1px solid #e5e7eb',
      color: textColor,
      fontWeight: fontWeight || '500',
      opacity: opacity || 1,
      boxShadow: boxShadow || 'none',
    };
  };

  // Helper function to get step icon
  const getStepIcon = (stateType) => {
    switch (stateType) {
      case 'error':
        return '⚠';
      case 'analysis':
        return '↩';
      case 'correction':
        return '✓';
      case 'backtrack':
        return '↩';
      case 'corrected':
        return '✓';
      case 'completed':
        return '●';
      case 'normal':
        return '●';
      case 'pending':
        return '○';
      default:
        return '●';
    }
  };

  return (
    <div
      ref={panelRef}
      style={{
        position: 'absolute',
        top: 'clamp(10px, 2vh, 20px)',
        left: 'clamp(10px, 2vw, 20px)',
        width: `${width}px`,
        maxHeight: '60vh',
        overflowY: 'auto',
        background: '#fff',
        borderRadius: 12,
        boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
        border: '2px solid #e5e7eb',
        zIndex: 30,
        userSelect: isResizing ? 'none' : 'auto',
      }}
    >
      {/* Resize Handle - on right edge */}
      <div
        onMouseDown={() => setIsResizing(true)}
        style={{
          position: 'absolute',
          right: 0,
          top: 0,
          bottom: 0,
          width: '8px',
          cursor: 'ew-resize',
          background: isResizing ? 'rgba(59, 130, 246, 0.3)' : 'transparent',
          transition: 'background 0.2s ease',
          zIndex: 31,
        }}
        onMouseEnter={(e) => {
          if (!isResizing) {
            e.currentTarget.style.background = 'rgba(59, 130, 246, 0.2)';
          }
        }}
        onMouseLeave={(e) => {
          if (!isResizing) {
            e.currentTarget.style.background = 'transparent';
          }
        }}
      />

      {/* Header */}
      <div
        style={{
          padding: 'clamp(12px, 1.5vh, 16px)',
          borderBottom: '2px solid #e5e7eb',
          background: '#f9fafb',
          position: 'sticky',
          top: 0,
          zIndex: 10,
        }}
      >
        <div style={{ 
          fontSize: 'clamp(10px, 1.1vh, 11px)', 
          color: '#6b7280', 
          marginBottom: 'clamp(2px, 0.3vh, 4px)',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
        }}>
          工作流时间线
        </div>
        <div style={{ 
          fontSize: 'clamp(13px, 1.5vh, 15px)', 
          fontWeight: '600', 
          color: '#111827',
        }}>
          {workflowData.title}
        </div>
      </div>

      {/* Steps List */}
      <div style={{ padding: 'clamp(8px, 1vh, 12px)' }}>
        {canonicalSteps.map((canonical, index) => {
          const state = getCanonicalStepState(canonical.stepId, index);
          const stateType = state.type;
          const step = state.step;
          const stepStyle = getStepStyle(stateType);
          const icon = getStepIcon(stateType);
          
          // Current is only when state is blue (normal)
          const isCurrent = stateType === 'normal';

          return (
            <div
              key={canonical.stepId}
              ref={isCurrent ? currentStepRef : null}
              style={stepStyle}
              onMouseEnter={() => setHoveredStep(index)}
              onMouseLeave={() => setHoveredStep(null)}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                <span style={{ 
                  fontSize: 'clamp(14px, 1.6vh, 16px)',
                  flexShrink: 0,
                  lineHeight: 1,
                }}>
                  {icon}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ 
                  fontWeight: isCurrent ? '800' : '700',
                  fontSize: 'clamp(13px, 1.6vh, 15px)',
                  color: '#111827',
                  letterSpacing: '0.02em',
                  marginBottom: '4px',
                }}>
                    <HTMLRenderer 
                      content={step.question || step.description || canonical.stepId} 
                      tag="span"
                    />
                    {step.nodeMapping && step.nodeMapping !== 'tail' && (
                      <span style={{ 
                        marginLeft: '6px',
                        opacity: 0.7,
                        fontSize: '0.9em',
                      }}>
                        → {step.nodeMapping}
                      </span>
                    )}
                  </div>
                  <div style={{ 
                    fontSize: 'clamp(10px, 1.1vh, 11px)',
                    opacity: 0.8,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}>
                  </div>
                </div>
              </div>

              {/* Tooltip on hover */}
              {hoveredStep === index && step.reasoning && (
                <div
                  style={{
                    position: 'absolute',
                    left: `${width}px`,
                    top: 0,
                    marginLeft: '8px',
                    width: '300px',
                    padding: 'clamp(10px, 1.2vh, 12px)',
                    background: '#fff',
                    border: '1px solid #d1d5db',
                    borderRadius: '8px',
                    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
                    zIndex: 40,
                    fontSize: 'clamp(11px, 1.2vh, 12px)',
                    lineHeight: 1.5,
                    color: '#374151',
                  }}
                >
                  <HTMLRenderer
                    content={step.question || step.description}
                    style={{ fontWeight: '600', marginBottom: '6px', color: '#111827' }}
                    tag="div"
                  />
                  <HTMLRenderer
                    content={step.reasoning}
                    style={{ color: '#6b7280' }}
                    tag="div"
                  />
                  {step.errorDetails && (
                    <div style={{ 
                      marginTop: '8px',
                      padding: '8px',
                      background: '#fecaca',
                      borderRadius: '4px',
                      color: '#991b1b',
                      fontSize: 'clamp(10px, 1.1vh, 11px)',
                    }}>
                      <strong>错误:</strong> <HTMLRenderer content={step.errorDetails.issue} tag="span" />
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
