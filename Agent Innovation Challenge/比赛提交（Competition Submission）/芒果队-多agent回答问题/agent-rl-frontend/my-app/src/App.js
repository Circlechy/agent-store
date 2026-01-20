import React, { useState } from 'react';
import GraphVisualiser from './components/GraphVisualiser';
import GraphBuildMode from './components/GraphBuildMode';

function App() {
  const [mode, setMode] = useState('build'); // 'graph' or 'build'

  return (
    <div className="App">
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        marginBottom: '20px',
        padding: '0 20px'
      }}>
        <h1>工作流图演示</h1>
        
        {/* Mode Toggle */}
        <div style={{
          display: 'flex',
          gap: '10px',
          background: 'white',
          padding: '6px',
          borderRadius: '12px',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)'
        }}>
          <button
            onClick={() => setMode('build')}
            style={{
              padding: '10px 20px',
              border: 'none',
              borderRadius: '8px',
              fontSize: '14px',
              fontWeight: '600',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              background: mode === 'build' ? '#3b82f6' : 'transparent',
              color: mode === 'build' ? 'white' : '#6b7280'
            }}
          >
            🎬 构建模式
          </button>
          <button
            onClick={() => setMode('graph')}
            style={{
              padding: '10px 20px',
              border: 'none',
              borderRadius: '8px',
              fontSize: '14px',
              fontWeight: '600',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              background: mode === 'graph' ? '#3b82f6' : 'transparent',
              color: mode === 'graph' ? 'white' : '#6b7280'
            }}
          >
            📊 图形视图
          </button>
        </div>
      </div>

      {/* Render both components, hide inactive one to preserve state */}
      <div style={{ display: mode === 'graph' ? 'block' : 'none' }}>
        <GraphVisualiser mode={mode} setMode={setMode} />
      </div>
      <div style={{ display: mode === 'build' ? 'block' : 'none' }}>
        <GraphBuildMode />
      </div>
    </div>
  );
}

export default App;
