import { useState, useEffect } from 'react';
import { Menu } from 'lucide-react';
import StreamPlayer from './components/StreamPlayer';
import ControlPanel from './components/ControlPanel';
import './App.css';

function App() {
  const [streams, setStreams] = useState(() => {
    const saved = localStorage.getItem('cctv_streams');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) {
           return parsed.map(item => {
             if (typeof item === 'string') return { id: item, name: item };
             const { isPinned, ...rest } = item;
             return rest;
           });
        }
        return [];
      } catch (e) {
        return [];
      }
    }
    return [];
  });

  const [isPanelOpen, setIsPanelOpen] = useState(true);
  const [focusedStreamId, setFocusedStreamId] = useState(null);

  useEffect(() => {
    localStorage.setItem('cctv_streams', JSON.stringify(streams));
  }, [streams]);

  const addStream = (id, name) => {
    if (!streams.find(s => s.id === id)) {
      setStreams([...streams, {
        id,
        name: name || `Kamera ${streams.length + 1}`
      }]);
    }
  };

  const removeStream = (id) => {
    setStreams(streams.filter(s => s.id !== id));
    if (focusedStreamId === id) setFocusedStreamId(null);
  };

  const updateStream = (oldId, newName, newId) => {
    setStreams(streams.map(s =>
      s.id === oldId ? { ...s, id: newId || s.id, name: newName || s.name } : s
    ));
    if (focusedStreamId === oldId && newId && newId !== oldId) {
        setFocusedStreamId(newId);
    }
  };

  const reorderStreams = (newOrder) => {
    setStreams(newOrder);
  };

  const toggleFocus = (id) => {
    setFocusedStreamId(prev => prev === id ? null : id);
  };

  // Grid Calculation
  const calculateGridDims = (count, hasFocus) => {
    if (count === 0) return { cols: 1, rows: 1 };

    let effectiveCount = count;

    // If a stream is focused, it takes up 2x2 (4 slots).
    // The original stream count included the focused item (1 slot).
    // So we need to add 3 extra virtual slots to accommodate the expansion.
    if (hasFocus) {
        effectiveCount = count + 3;
    }

    let cols = 1;
    let rows = 1;

    if (!hasFocus) {
        // Standard Balanced Grid Logic
        if (count === 1) { cols = 1; rows = 1; }
        else if (count === 2) { cols = 2; rows = 1; }
        else if (count <= 4) { cols = 2; rows = 2; }
        else if (count <= 6) { cols = 3; rows = 2; }
        else if (count <= 8) { cols = 4; rows = 2; }
        else if (count <= 9) { cols = 3; rows = 3; }
        else if (count <= 12) { cols = 4; rows = 3; }
        else if (count <= 16) { cols = 4; rows = 4; }
        else {
            cols = Math.ceil(Math.sqrt(count));
            rows = Math.ceil(count / cols);
        }
    } else {
        // Focus Mode Grid Logic
        // We use the effectiveCount to determine the grid size
        // ensuring we have enough space for the 2x2 hero + other items.
        cols = Math.ceil(Math.sqrt(effectiveCount));
        rows = Math.ceil(effectiveCount / cols);
    }

    return { cols, rows };
  };

  const { cols, rows } = calculateGridDims(streams.length, !!focusedStreamId);

  // Responsive Layout Logic
  const [containerSize, setContainerSize] = useState({ width: window.innerWidth, height: window.innerHeight });

  useEffect(() => {
    const handleResize = () => {
        // We need the size of the available video area.
        // It depends on panel state.
        // Simplest is to check window size and subtract panel if open.
        // Or we can rely on window resize and let the render logic handle the math.
        setContainerSize({ width: window.innerWidth, height: window.innerHeight });
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Calculate available space
  const panelWidth = 320;
  const availableWidth = isPanelOpen ? containerSize.width - panelWidth : containerSize.width;
  const availableHeight = containerSize.height;

  const screenRatio = availableWidth / availableHeight;
  const gridRatio = (cols * 16) / (rows * 9);

  const gridStyle = {
    gridTemplateColumns: `repeat(${cols}, 1fr)`,
    gridTemplateRows: `repeat(${rows}, 1fr)`,
    gridAutoFlow: !!focusedStreamId ? 'dense' : 'row',
    aspectRatio: `${cols * 16} / ${rows * 9}`,
    // If grid is wider than screen, constrain by width.
    // Else (grid is taller), constrain by height.
    width: gridRatio > screenRatio ? '100%' : 'auto',
    height: gridRatio > screenRatio ? 'auto' : '100%',
  };

  return (
    <div className="app-container">
      {!isPanelOpen && (
        <button
          className="panel-toggle-btn"
          onClick={() => setIsPanelOpen(true)}
          title="Menüyü Aç"
        >
          <Menu size={24} />
        </button>
      )}

      <ControlPanel
        streams={streams}
        onAdd={addStream}
        onRemove={removeStream}
        onUpdate={updateStream}
        onReorder={reorderStreams}
        isOpen={isPanelOpen}
        onClose={() => setIsPanelOpen(false)}
      />

      <main
        className={`video-layout-container ${isPanelOpen ? 'panel-open' : ''}`}
      >
        {streams.length === 0 && (
          <div className="empty-state">
            <h2>Sinyal Yok</h2>
            <p>Lütfen menüden yeni bir yayın ekleyin.</p>
          </div>
        )}

        {streams.length > 0 && (
          <div className="auto-grid-container" style={gridStyle}>
            {streams.map((stream) => {
              const isFocused = stream.id === focusedStreamId;
              return (
                <div
                    key={stream.id}
                    className={`video-cell ${isFocused ? 'focused' : ''}`}
                    style={{
                        gridColumn: isFocused ? 'span 2' : 'auto',
                        gridRow: isFocused ? 'span 2' : 'auto',
                        order: isFocused ? -1 : 0
                    }}
                >
                  <div className="video-content">
                      <StreamPlayer
                        videoId={stream.id}
                        label={stream.name}
                        isFocused={isFocused}
                        onToggleFocus={() => toggleFocus(stream.id)}
                      />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
