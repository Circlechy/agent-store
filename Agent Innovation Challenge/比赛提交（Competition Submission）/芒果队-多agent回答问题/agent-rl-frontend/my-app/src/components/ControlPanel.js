import React from 'react';
import { Play, Pause, RotateCcw, SkipBack, SkipForward } from 'lucide-react';

export default function ControlPanel({
  isPlaying,
  onPlayPause,
  onReset,
  onStepForward,
  onStepBackward,
}) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 'clamp(8px, 1vw, 12px)',
        justifyContent: 'center',
        alignItems: 'center',
        marginTop: 'clamp(10px, 2vh, 20px)',
        userSelect: 'none',
      }}
    >
      {/* Step Backward */}
      <button
        onClick={onStepBackward}
        style={buttonStyle}
        title="上一步"
      >
        <SkipBack size={18} />
      </button>

      {/* Play / Pause */}
      <button
        onClick={onPlayPause}
        style={{ ...buttonStyle, backgroundColor: isPlaying ? '#FFE066' : '#90E0EF' }}
        title={isPlaying ? '暂停' : '播放'}
      >
        {isPlaying ? <Pause size={18} /> : <Play size={18} />}
      </button>

      {/* Step Forward */}
      <button
        onClick={onStepForward}
        style={buttonStyle}
        title="下一步"
      >
        <SkipForward size={18} />
      </button>

      {/* Reset */}
      <button
        onClick={onReset}
        style={{ ...buttonStyle, backgroundColor: '#E9ECEF' }}
        title="重置"
      >
        <RotateCcw size={18} />
      </button>
    </div>
  );
}

const buttonStyle = {
  border: 'none',
  borderRadius: '8px',
  backgroundColor: '#f4f4f4',
  padding: 'clamp(8px, 1vh, 10px)',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
  transition: 'all 0.2s ease',
  minWidth: 'clamp(35px, 4vw, 45px)',
  minHeight: 'clamp(35px, 4vh, 45px)',
};
