// src/components/ReasoningPanel.js
import React, { useState, useRef, useEffect } from 'react';
import HTMLRenderer from './utils/HTMLRenderer';

/**
 * Reasoning Panel component that displays step details, reasoning, and error information
 * Renders as an absolutely positioned overlay outside the SVG
 */
export default function ReasoningPanel({ currentStep, traversal }) {
  const [width, setWidth] = useState(400);
  const [isResizing, setIsResizing] = useState(false);
  const panelRef = useRef(null);
  
  // Handle resize - must be before early returns (React Hooks rules)
  useEffect(() => {
    if (!isResizing) return;
    
    const handleMouseMove = (e) => {
      if (!panelRef.current) return;
      const panelRect = panelRef.current.getBoundingClientRect();
      const newWidth = panelRect.right - e.clientX;
      const clampedWidth = Math.max(250, Math.min(600, newWidth));
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
  
  // Console logging for current step changes
  useEffect(() => {
    if (!Array.isArray(traversal) || traversal.length === 0) return;
    if (typeof currentStep !== 'number' || currentStep < 0 || currentStep >= traversal.length) return;
    const s = traversal[currentStep];
    console.groupCollapsed(`ReasoningPanel: step ${currentStep + 1}/${traversal.length}`);
    console.log('Step summary', {
      stepId: s.stepId,
      from: s.from,
      to: s.to || s.nodeMapping,
      backtrack: s.backtrack === true,
      correct: s.correct,
      pass: s.pass,
      error: s.error,
      errorDetails: s.errorDetails
    });
    if (s.description) console.log('Description:', s.description);
    if (s.reasoning) console.log('Reasoning:', s.reasoning);
    console.groupEnd();
  }, [currentStep, traversal]);
  
  // Don't render if no valid step
  if (currentStep < 0 || currentStep >= traversal.length) return null;
  
  const step = traversal[currentStep];
  if (!step) return null;

  const strokeColor = step.backtrack ? '#facc15' : (step.correct ? '#4ade80' : '#f87171');
  
  // Handle hidden analyze/backtrack steps (pass: null)
  if (step.pass === null || step.hidden === true) {
    return (
      <div
        ref={panelRef}
        style={{
          position: 'absolute',
          top: 'clamp(10px, 2vh, 20px)',
          right: 'clamp(10px, 2vw, 20px)',
          width: `${width}px`,
          maxHeight: '40vh',
          overflowY: 'auto',
          background: '#fff',
          borderRadius: 12,
          boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
          border: '1px solid #f59e0b',
          zIndex: 30,
          userSelect: isResizing ? 'none' : 'auto',
        }}
      >
        {/* Resize Handle */}
        <div
          onMouseDown={() => setIsResizing(true)}
          style={{
            position: 'absolute',
            left: 0,
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
            borderBottom: '1px solid #e5e7eb',
          background: '#fef3c7',
          }}
        >
          <div style={{ fontSize: 'clamp(10px, 1.1vh, 11px)', color: '#6b7280', marginBottom: 'clamp(2px, 0.3vh, 4px)' }}>
            第 {currentStep + 1} 步 / 共 {traversal.length} 步
          </div>
          <div style={{ fontSize: 'clamp(14px, 1.6vh, 16px)', fontWeight: '600', color: '#92400e' }}>
            ↩ 回溯到前一个节点
          </div>
        </div>

        {/* Content */}
        <div style={{ padding: 'clamp(12px, 1.5vh, 16px)' }}>
            <HTMLRenderer
              content={step.to ? (step.errorDetails?.issue || `回到 ${step.to} 重新开始`) : '回到前一个节点重新开始'}
              style={{
                padding: 'clamp(10px, 1.2vh, 12px)',
                background: '#fef3c7',
                borderRadius: 8,
                fontSize: 'clamp(12px, 1.3vh, 13px)',
                color: '#92400e',
                lineHeight: 1.6,
                border: '1px solid #f59e0b',
              }}
            />
        </div>
      </div>
    );
  }
  
  // Normal step rendering - check for reasoning
  if (!step.reasoning) return null;

  return (
    <div
      ref={panelRef}
      style={{
        position: 'absolute',
        top: 'clamp(10px, 2vh, 20px)',
        right: 'clamp(10px, 2vw, 20px)',
        width: `${width}px`,
        maxHeight: '40vh',
        overflowY: 'auto',
        background: '#fff',
        borderRadius: 12,
        boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
        border: `2px solid ${strokeColor}`,
        zIndex: 30,
        userSelect: isResizing ? 'none' : 'auto',
      }}
    >
      {/* Resize Handle */}
      <div
        onMouseDown={() => setIsResizing(true)}
        style={{
          position: 'absolute',
          left: 0,
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
          borderBottom: '1px solid #e5e7eb',
          background: step.correct === false ? '#fee2e2' : step.backtrack ? '#fef3c7' : '#ecfdf5',
        }}
      >
        <div style={{ fontSize: 'clamp(10px, 1.1vh, 11px)', color: '#6b7280', marginBottom: 'clamp(2px, 0.3vh, 4px)' }}>
          第 {currentStep + 1} 步 / 共 {traversal.length} 步
        </div>
        <div style={{ fontSize: 'clamp(14px, 1.6vh, 16px)', fontWeight: '600', color: '#111827' }}>
          {step.question ? (
            <HTMLRenderer content={`子问题: ${step.question}`} tag="span" />
          ) : (
            <HTMLRenderer content={step.description || '步骤描述'} tag="span" />
          )}
          <span style={{ marginLeft: '10px', color: "#FF0000"  }}>
            <strong>{step.error ? `(错误: ${step.error})` : ''}</strong>
          </span>
        </div>
        {step.backtrack && (
          <div style={{ 
            marginTop: 'clamp(4px, 0.5vh, 6px)',
            fontSize: 'clamp(10px, 1.2vh, 12px)',
            color: '#dc2626',
            fontWeight: '500',
          }}>
            ↩ 回溯修理错误
          </div>
        )}
      </div>

      {/* Content */}
      <div style={{ padding: 'clamp(12px, 1.5vh, 16px)' }}>
        {/* Step Description (步骤) */}
        {!step.backtrack && step.description && (
          <div style={{ marginBottom: 'clamp(12px, 1.5vh, 16px)' }}>
            <div style={{ 
              fontSize: 'clamp(11px, 1.2vh, 12px)', 
              color: '#6b7280',
              marginBottom: 'clamp(4px, 0.5vh, 6px)',
              fontWeight: '600',
            }}>
              步骤：
            </div>
            <HTMLRenderer
              content={step.description}
              style={{
                padding: 'clamp(10px, 1.2vh, 12px)',
                background: step.correct === false ? '#fee2e2' : '#f9fafb',
                borderRadius: 8,
                fontSize: 'clamp(12px, 1.3vh, 13px)',
                color: '#374151',
                lineHeight: 1.6,
                border: step.correct === false ? '2px solid #ef4444' : '1px solid #e5e7eb',
              }}
            />
          </div>
        )}

        {/* Reasoning (原因) */}
        {!step.backtrack && step.reasoning && (
          <div style={{ marginBottom: step.correct === false ? 'clamp(12px, 1.5vh, 16px)' : 0 }}>
            <div style={{ 
              fontSize: 'clamp(11px, 1.2vh, 12px)', 
              color: '#6b7280',
              marginBottom: 'clamp(4px, 0.5vh, 6px)',
              fontWeight: '600',
            }}>
              具体任务：
            </div>
            <HTMLRenderer
              content={step.reasoning}
              style={{
                padding: 'clamp(10px, 1.2vh, 12px)',
                background: step.correct === false ? '#fee2e2' : '#f9fafb',
                borderRadius: 8,
                fontSize: 'clamp(12px, 1.3vh, 13px)',
                color: '#374151',
                lineHeight: 1.6,
                border: step.correct === false ? '2px solid #ef4444' : '1px solid #e5e7eb',
              }}
            />
          </div>
        )}

        {/* Error Details */}
        {step.correct === false && step.errorDetails && (
          <>
            <div style={{ marginBottom: 'clamp(8px, 1vh, 10px)' }}>
              <div style={{ 
                fontSize: 'clamp(10px, 1.1vh, 11px)', 
                textTransform: 'uppercase', 
                letterSpacing: '0.05em', 
                color: '#dc2626',
                marginBottom: 'clamp(4px, 0.5vh, 6px)',
                fontWeight: '600',
              }}>
                ⚠ 故障
              </div>
              <HTMLRenderer
                content={step.errorDetails.issue}
                style={{
                  padding: 'clamp(10px, 1.2vh, 12px)',
                  background: '#fee2e2',
                  borderRadius: 8,
                  fontSize: 'clamp(12px, 1.3vh, 13px)',
                  color: '#991b1b',
                  lineHeight: 1.6,
                  border: '1px solid #fca5a5',
                }}
              />
            </div>

            {step.errorDetails.correction && (
              <div>
                <div style={{ 
                  fontSize: 'clamp(10px, 1.1vh, 11px)', 
                  textTransform: 'uppercase', 
                  letterSpacing: '0.05em', 
                  color: '#059669',
                  marginBottom: 'clamp(4px, 0.5vh, 6px)',
                  fontWeight: '600',
                }}>
                  ✓ 修正
                </div>
                <HTMLRenderer
                  content={step.errorDetails.correction}
                  style={{
                    padding: 'clamp(10px, 1.2vh, 12px)',
                    background: '#d1fae5',
                    borderRadius: 8,
                    fontSize: 'clamp(12px, 1.3vh, 13px)',
                    color: '#065f46',
                    lineHeight: 1.6,
                    border: '1px solid #6ee7b7',
                  }}
                />
              </div>
            )}
          </>
        )}

        {/* Backtrack message */}
        {step.backtrack && (
          <HTMLRenderer
            content={`回到 ${step.to} 去改正`}
            style={{
              padding: 'clamp(10px, 1.2vh, 12px)',
              background: '#fef3c7',
              borderRadius: 8,
              fontSize: 'clamp(12px, 1.3vh, 13px)',
              color: '#92400e',
              lineHeight: 1.6,
              border: '1px solid #f59e0b',
            }}
          />
        )}

        {/* Correction step indicator */}
        {step.isCorrection && (
          <div style={{ marginTop: 'clamp(8px, 1vh, 10px)' }}>
            <div
              style={{
                padding: 'clamp(8px, 1vh, 10px)',
                background: '#d1fae5',
                borderRadius: 8,
                fontSize: 'clamp(11px, 1.2vh, 12px)',
                color: '#065f46',
                lineHeight: 1.5,
                border: '1px solid #6ee7b7',
                fontWeight: '500',
              }}
            >
              ✓ 这是修正后的方法
            </div>
          </div>
        )}

        {/* Next Question */}
        {!step.backtrack &&
          currentStep < traversal.length - 1 &&
          !traversal[currentStep + 1]?.backtrack &&
          traversal[currentStep + 1]?.question && (
          <div style={{ marginTop: 'clamp(12px, 1.5vh, 16px)' }}>
            <div style={{ 
              fontSize: 'clamp(11px, 1.2vh, 12px)', 
              color: '#6b7280',
              marginBottom: 'clamp(4px, 0.5vh, 6px)',
              fontWeight: '600',
            }}>
              下一个问题：
            </div>
            <HTMLRenderer
              content={traversal[currentStep + 1].question}
              style={{
                padding: 'clamp(10px, 1.2vh, 12px)',
                background: '#ecfdf5',
                borderRadius: 8,
                fontSize: 'clamp(12px, 1.3vh, 13px)',
                color: '#065f46',
                lineHeight: 1.6,
                border: '1px solid #6ee7b7',
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}

