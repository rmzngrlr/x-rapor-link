import React, { useState } from 'react';
import { Maximize2, Minimize2 } from 'lucide-react';
import { getEmbedUrl } from '../utils/youtube';

const StreamPlayer = ({ videoId, label, isFocused, onToggleFocus }) => {
  const [isHovered, setIsHovered] = useState(false);

  if (!videoId) return null;

  return (
    <div
      className="stream-player-container"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <iframe
        src={getEmbedUrl(videoId)}
        title={`YouTube Stream ${videoId}`}
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        allowFullScreen
      ></iframe>

      {/* Overlay Label (Visible on Hover) */}
      <div
        className={`player-overlay ${isHovered ? 'visible' : ''}`}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          padding: '10px',
          background: 'linear-gradient(to bottom, rgba(0,0,0,0.8) 0%, rgba(0,0,0,0) 100%)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          opacity: isHovered ? 1 : 0,
          transition: 'opacity 0.2s',
          pointerEvents: 'none',
        }}
      >
        <div style={{ color: '#fff', fontSize: '0.9rem', fontWeight: '500', textShadow: '0 1px 2px #000' }}>
          {label || videoId}
        </div>

        {onToggleFocus && (
          <button
            onClick={(e) => {
                e.stopPropagation();
                onToggleFocus();
            }}
            className="focus-toggle-btn"
            style={{
                background: 'rgba(255, 255, 255, 0.2)',
                border: 'none',
                borderRadius: '4px',
                color: 'white',
                padding: '6px',
                cursor: 'pointer',
                pointerEvents: 'auto',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                backdropFilter: 'blur(2px)',
                transition: 'background 0.2s'
            }}
            title={isFocused ? "Küçült" : "Odakla"}
            onMouseOver={(e) => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.4)'}
            onMouseOut={(e) => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.2)'}
          >
            {isFocused ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
          </button>
        )}
      </div>
    </div>
  );
};

export default StreamPlayer;
