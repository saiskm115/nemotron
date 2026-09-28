import React from 'react';
import { useSessionStore } from '../../stores/sessionStore';
import { toast } from '../../stores/toastStore';
import {
  MousePointer,
  Hand,
  Scissors,
  GitMerge,
  UserCheck,
  Type,
  Bookmark,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Languages
} from 'lucide-react';

export const EditorToolbar: React.FC = () => {
  const {
    activeTool,
    setActiveTool,
    zoomLevel,
    setZoomLevel,
    duration,
    currentTime,
    addMarker,
    selectedTurnId,
    session,
    mergeTurns,
    splitTurn,
    translitMode,
    setTranslitMode,
    displayMode,
    setDisplayMode
  } = useSessionStore();

  const turns = session?.turns || [];

  const handleToolClick = (tool: typeof activeTool) => {
    setActiveTool(tool);

    if (tool === 'marker') {
      addMarker(currentTime, 'Marker');
      toast.info(`Marker placed at ${currentTime.toFixed(2)}s`, 'Timeline Marker');
    } else if (tool === 'split') {
      if (!selectedTurnId) {
        toast.warning('Please select a segment on the timeline or transcript to split.', 'Split Segment');
        return;
      }
      const t = turns.find(item => item.id === selectedTurnId);
      if (!t) {
        toast.error('Selected segment not found.', 'Split Segment');
        return;
      }
      if (currentTime <= t.start || currentTime >= t.end) {
        toast.warning(
          `Playhead (${currentTime.toFixed(2)}s) must be inside segment range (${t.start.toFixed(2)}s – ${t.end.toFixed(2)}s) to split.`,
          'Split Boundary'
        );
        return;
      }
      toast.confirm(
        `Split segment at playhead position ${currentTime.toFixed(2)}s into two turns?`,
        {
          title: 'Split Segment?',
          confirmLabel: 'Split Segment',
          cancelLabel: 'Cancel',
          confirmVariant: 'primary',
          onConfirm: async () => {
            const words = t.text.split(' ');
            const mid = Math.max(1, Math.floor(words.length / 2));
            await splitTurn(t.id, currentTime, words.slice(0, mid).join(' '), words.slice(mid).join(' '));
          },
          onCancel: () => {
            toast.info('Split operation cancelled', 'Cancelled');
          }
        }
      );
    } else if (tool === 'merge') {
      if (!selectedTurnId) {
        toast.warning('Please select a segment on the timeline or transcript to merge with the next segment.', 'Merge Segments');
        return;
      }
      const idx = turns.findIndex(item => item.id === selectedTurnId);
      if (idx < 0) {
        toast.error('Selected segment not found.', 'Merge Segments');
        return;
      }
      if (idx >= turns.length - 1) {
        toast.warning('Selected segment is the final turn and cannot be merged forward.', 'Merge Segments');
        return;
      }
      const nextTurn = turns[idx + 1];
      toast.confirm(
        `Merge turn #${idx + 1} with turn #${idx + 2} into a single contiguous segment?`,
        {
          title: 'Merge Segments?',
          confirmLabel: 'Merge Segments',
          cancelLabel: 'Cancel',
          confirmVariant: 'primary',
          onConfirm: async () => {
            await mergeTurns(turns[idx].id, nextTurn.id);
          },
          onCancel: () => {
            toast.info('Merge operation cancelled', 'Cancelled');
          }
        }
      );
    }
  };

  const handleFitTimeline = () => {
    if (duration > 0) {
      const containerWidth = window.innerWidth - 360;
      const fitZoom = Math.max(20, Math.min(250, containerWidth / duration));
      setZoomLevel(Math.round(fitZoom));
    }
  };

  return (
    <div className="editor-toolbar">
      {/* Primary Editing Tools */}
      <div className="flex items-center gap-1">
        <button
          onClick={() => handleToolClick('select')}
          className={`tool-btn ${activeTool === 'select' ? 'active' : ''}`}
          title="Select Tool (V)"
        >
          <MousePointer size={13} />
          <span>Select</span>
        </button>

        <button
          onClick={() => handleToolClick('hand')}
          className={`tool-btn ${activeTool === 'hand' ? 'active' : ''}`}
          title="Hand / Pan Tool (H)"
        >
          <Hand size={13} />
          <span>Pan</span>
        </button>

        <button
          onClick={() => handleToolClick('split')}
          className={`tool-btn ${activeTool === 'split' ? 'active' : ''}`}
          title="Split Turn at Playhead (S)"
        >
          <Scissors size={13} />
          <span>Split</span>
        </button>

        <button
          onClick={() => handleToolClick('merge')}
          className={`tool-btn ${activeTool === 'merge' ? 'active' : ''}`}
          title="Merge with Next Turn (M)"
        >
          <GitMerge size={13} />
          <span>Merge</span>
        </button>

        <button
          onClick={() => handleToolClick('speaker')}
          className={`tool-btn ${activeTool === 'speaker' ? 'active' : ''}`}
          title="Speaker Tool (R)"
        >
          <UserCheck size={13} />
          <span>Speaker</span>
        </button>

        <button
          onClick={() => handleToolClick('text')}
          className={`tool-btn ${activeTool === 'text' ? 'active' : ''}`}
          title="Text Edit Tool (T)"
        >
          <Type size={13} />
          <span>Text</span>
        </button>

        <button
          onClick={() => handleToolClick('marker')}
          className={`tool-btn ${activeTool === 'marker' ? 'active' : ''}`}
          title="Add Marker at Current Time (B)"
        >
          <Bookmark size={13} />
          <span>Marker</span>
        </button>
      </div>

      {/* Center / Right: Display & Zoom Controls */}
      <div className="flex items-center gap-3">
        {/* Telugu + English Display Mode Toggles (Section 14 & 18) */}
        <div className="flex items-center gap-1 bg-slate-950 p-0.5 rounded-md border border-white/5 text-[11px]">
          <span className="text-slate-500 px-1 font-medium flex items-center gap-1">
            <Languages size={11} className="text-cyan-400" />
            Script:
          </span>
          {(['script', 'roman', 'codemix'] as const).map(mode => (
            <button
              key={mode}
              onClick={() => setTranslitMode(mode)}
              className={`px-1.5 py-0.5 rounded capitalize transition ${
                translitMode === mode
                  ? 'bg-cyan-500/20 text-cyan-300 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {mode}
            </button>
          ))}
        </div>

        {/* Translation Mode */}
        <div className="flex items-center gap-1 bg-slate-950 p-0.5 rounded-md border border-white/5 text-[11px]">
          <span className="text-slate-500 px-1 font-medium">View:</span>
          {(['both', 'original', 'translation'] as const).map(mode => (
            <button
              key={mode}
              onClick={() => setDisplayMode(mode)}
              className={`px-1.5 py-0.5 rounded capitalize transition ${
                displayMode === mode
                  ? 'bg-cyan-500/20 text-cyan-300 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {mode}
            </button>
          ))}
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center gap-1 bg-slate-950 px-1.5 py-0.5 rounded-md border border-white/5">
          <button
            onClick={() => setZoomLevel(zoomLevel - 15)}
            className="p-1 text-slate-400 hover:text-white rounded hover:bg-slate-800 transition"
            title="Zoom Out (-)"
          >
            <ZoomOut size={13} />
          </button>
          <span className="font-mono text-[11px] text-slate-300 px-1 min-w-[42px] text-center">
            {zoomLevel}px/s
          </span>
          <button
            onClick={() => setZoomLevel(zoomLevel + 15)}
            className="p-1 text-slate-400 hover:text-white rounded hover:bg-slate-800 transition"
            title="Zoom In (+)"
          >
            <ZoomIn size={13} />
          </button>
          <button
            onClick={handleFitTimeline}
            className="p-1 text-slate-400 hover:text-cyan-400 rounded hover:bg-slate-800 transition ml-1"
            title="Fit Entire Timeline (F)"
          >
            <Maximize2 size={12} />
          </button>
        </div>
      </div>
    </div>
  );
};
