import React, { useState, useRef } from 'react';
import { Plus, Trash2, X, MonitorPlay, GripVertical, Edit2, Save, RotateCcw, Maximize, Minimize } from 'lucide-react';
import { extractVideoId } from '../utils/youtube';

const ControlPanel = ({ streams, onAdd, onRemove, onUpdate, onReorder, isOpen, onClose }) => {
  const [inputUrl, setInputUrl] = useState('');
  const [inputName, setInputName] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState('');
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Toggle Fullscreen
  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().then(() => {
            setIsFullscreen(true);
        }).catch(err => {
            console.error(`Error attempting to enable full-screen mode: ${err.message} (${err.name})`);
        });
    } else {
        if (document.exitFullscreen) {
            document.exitFullscreen().then(() => {
                setIsFullscreen(false);
            });
        }
    }
  };

  // Drag and Drop State
  const dragItem = useRef(null);
  const dragOverItem = useRef(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');

    const videoId = extractVideoId(inputUrl);

    if (!videoId) {
      setError('Geçersiz YouTube linki.');
      return;
    }

    if (editingId) {
        // Update Mode
        // If changing ID, check if new ID already exists (and it's not the same stream we are editing)
        if (streams.find(s => s.id === videoId && s.id !== editingId)) {
            setError('Bu yayın (farklı bir isimle) zaten listede ekli.');
            return;
        }
        onUpdate(editingId, inputName.trim() || null, videoId);
        setEditingId(null);
    } else {
        // Add Mode
        if (streams.find(s => s.id === videoId)) {
            setError('Bu yayın zaten listede ekli.');
            return;
        }
        onAdd(videoId, inputName.trim() || null);
    }

    setInputUrl('');
    setInputName('');
  };

  const startEditing = (stream) => {
    setEditingId(stream.id);
    setInputName(stream.name);
    // Since we only store the ID, we construct a standard watch URL for editing display
    // It is enough to extract the ID back from it.
    setInputUrl(`https://www.youtube.com/watch?v=${stream.id}`);
    setError('');
  };

  const cancelEditing = () => {
    setEditingId(null);
    setInputName('');
    setInputUrl('');
    setError('');
  };

  // DnD Handlers
  const handleSort = () => {
    // Duplicate items
    let _streams = [...streams];

    // Remove and save the dragged item content
    const draggedItemContent = _streams.splice(dragItem.current, 1)[0];

    // Switch the position
    _streams.splice(dragOverItem.current, 0, draggedItemContent);

    // Reset position refs
    dragItem.current = null;
    dragOverItem.current = null;

    // Update parent state
    onReorder(_streams);
  };

  return (
    <div className={`control-panel ${isOpen ? 'open' : ''}`}>
      <div className="panel-header">
        <h2><MonitorPlay size={24} /> Yayın Yönetimi</h2>
        <div className="header-actions">
            <button className="icon-btn" onClick={toggleFullscreen} title={isFullscreen ? "Tam Ekrandan Çık" : "Tam Ekran Yap"}>
                {isFullscreen ? <Minimize size={20} /> : <Maximize size={20} />}
            </button>
            <button className="close-btn" onClick={onClose} title="Paneli Kapat">
                <X size={24} />
            </button>
        </div>
      </div>

      <form onSubmit={handleSubmit} className={`add-form ${editingId ? 'editing-mode' : ''}`}>
        <div className="input-group-col">
          {editingId && <div className="editing-label">Düzenleniyor: {streams.find(s => s.id === editingId)?.name}</div>}
          <input
            type="text"
            placeholder="Yayın İsmi (İsteğe bağlı)"
            value={inputName}
            onChange={(e) => setInputName(e.target.value)}
            className="text-input"
          />
          <div className="url-row">
            <input
              type="text"
              placeholder="YouTube Linki"
              value={inputUrl}
              onChange={(e) => setInputUrl(e.target.value)}
              className="text-input"
            />
            <button type="submit" title={editingId ? "Güncelle" : "Ekle"} className={`add-btn ${editingId ? 'update-btn' : ''}`}>
              {editingId ? <Save size={20} /> : <Plus size={20} />}
            </button>
            {editingId && (
                <button type="button" onClick={cancelEditing} className="cancel-btn" title="İptal">
                    <RotateCcw size={20} />
                </button>
            )}
          </div>
        </div>
        {error && <div className="error-msg">{error}</div>}
      </form>

      <div className="stream-list">
        <h3>Ekli Yayınlar ({streams.length})</h3>
        {streams.length === 0 && (
          <p className="empty-msg">Henüz yayın eklenmedi.</p>
        )}
        <ul className="sortable-list">
          {streams.map((stream, index) => (
            <li
              key={stream.id}
              className="stream-item"
              draggable
              onDragStart={(e) => (dragItem.current = index)}
              onDragEnter={(e) => (dragOverItem.current = index)}
              onDragEnd={handleSort}
              onDragOver={(e) => e.preventDefault()}
            >
              <div className="drag-handle-icon">
                <GripVertical size={16} />
              </div>
              <div className="stream-info">
                <span className="stream-name">{stream.name}</span>
                <span className="stream-id">{stream.id}</span>
              </div>
              <div className="action-buttons">
                <button
                    onClick={() => startEditing(stream)}
                    className="action-btn edit-btn"
                    title="Düzenle"
                >
                    <Edit2 size={16} />
                </button>
                <button
                    onClick={() => onRemove(stream.id)}
                    className="action-btn remove-btn"
                    title="Yayını Kaldır"
                >
                    <Trash2 size={16} />
                </button>
              </div>
            </li>
          ))}
        </ul>
      </div>

      <div className="panel-footer">
        <p>MŞ'nin Tensipleriyle...</p>
      </div>
    </div>
  );
};

export default ControlPanel;
