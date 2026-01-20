import React from 'react';

export default function BuildEventPanel({ visible, decisionText, onClose }) {
  if (!visible || !decisionText) return null;

  return (
    <div
      style={{
        position: 'absolute',
        top: 'clamp(10px, 2vh, 20px)',
        left: 'clamp(10px, 2vw, 20px)',
        width: '340px',
        maxWidth: '32vw',
        maxHeight: '60vh',
        overflowY: 'auto',
        background: '#fff',
        borderRadius: 12,
        boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
        border: '2px solid #e5e7eb',
        zIndex: 35,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: 'clamp(12px, 1.5vh, 16px)',
          borderBottom: '2px solid #e5e7eb',
          background: '#f9fafb',
          position: 'sticky',
          top: 0,
          zIndex: 1,
        }}
      >
        <div>
          <div style={{ fontSize: 'clamp(10px, 1.1vh, 11px)', color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          {decisionText.action === 'CREATE' ? '生成新点' : '融合时'}
          </div>
          <div style={{ fontSize: 'clamp(13px, 1.5vh, 15px)', fontWeight: 600, color: '#111827' }}>
            {decisionText.action === 'CREATE' ? '未超过则生成新的节点' : '超过阈值则融合并更新节点内容'}
          </div>
        </div>
        <button
          onClick={onClose}
          style={{
            border: 'none',
            background: 'transparent',
            cursor: 'pointer',
            fontSize: '16px',
            color: '#6b7280',
          }}
          aria-label="关闭"
          title="关闭"
        >
          ✕
        </button>
      </div>
      {/* Intentionally no body content per request: no workflow/summary/details */}
    </div>
  );
}


