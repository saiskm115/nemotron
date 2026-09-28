import React, { useEffect } from 'react';
import { useSessionStore } from './stores/sessionStore';
import { api } from './services/api';
import { Header } from './components/navigation/Header';
import { EditorToolbar } from './components/editor/EditorToolbar';
import { SpeakerTimeline } from './components/timeline/SpeakerTimeline';
import { AudioPlayer } from './components/audio/AudioPlayer';
import { TranscriptPanel } from './components/transcript/TranscriptPanel';
import { RightSidebar } from './components/inspector/RightSidebar';

import { UploadModal } from './components/audio/UploadModal';
import { ExportMenu } from './components/export/ExportMenu';
import { SettingsModal } from './components/modals/SettingsModal';
import { VocabularyModal } from './components/modals/VocabularyModal';
import { BenchmarkModal } from './components/modals/BenchmarkModal';
import { ObservabilityModal } from './components/modals/ObservabilityModal';
import { ToastContainer } from './components/common/ToastContainer';
import { useModalStore } from './stores/modalStore';
import { toast } from './stores/toastStore';

export const App: React.FC = () => {
  const {
    session, setSession, isLoading, error,
    timelineMode, setTimelineMode, toggleTimelineFocus,
    timelineHeight, setTimelineHeight
  } = useSessionStore();

  const {
    isUploadOpen, isExportOpen, isSettingsOpen,
    isVocabularyOpen, isBenchmarkOpen, isObservabilityOpen,
    openUpload, closeUpload, closeExport, closeSettings,
    closeVocabulary, closeBenchmark, closeObservability
  } = useModalStore();

  const [isDraggingSplitter, setIsDraggingSplitter] = React.useState(false);
  const dragStartY = React.useRef(0);
  const dragStartHeight = React.useRef(0);

  // Global window unhandled error & rejection listeners to show error toasts
  React.useEffect(() => {
    const handleUnhandledRejection = (e: PromiseRejectionEvent) => {
      const msg = e.reason?.message || String(e.reason || 'An unexpected promise error occurred');
      toast.error(msg, 'Network / Async Error');
    };
    const handleError = (e: ErrorEvent) => {
      if (e.message) {
        toast.error(e.message, 'Runtime Error');
      }
    };
    window.addEventListener('unhandledrejection', handleUnhandledRejection);
    window.addEventListener('error', handleError);
    return () => {
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
      window.removeEventListener('error', handleError);
    };
  }, []);

  // Show toast when session store error changes
  React.useEffect(() => {
    if (error) {
      toast.error(error, 'Action Error');
    }
  }, [error]);

  // Keyboard Shortcuts (Section 8 & 9 of ui.md)
  // ESC -> Exit Focus Mode
  // Ctrl+Shift+F -> Toggle Focus Mode
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)) return;

      if (e.key === 'Escape' && timelineMode === 'focus') {
        e.preventDefault();
        setTimelineMode('normal');
        return;
      }

      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'f') {
        e.preventDefault();
        toggleTimelineFocus();
        return;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [timelineMode, setTimelineMode, toggleTimelineFocus]);

  // Drag handling for Timeline / Transcript Splitter (Section 5 of ui.md)
  const handleSplitterMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsDraggingSplitter(true);
    dragStartY.current = e.clientY;
    dragStartHeight.current = timelineHeight;
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';
  };

  React.useEffect(() => {
    if (!isDraggingSplitter) return;

    const handlePointerMove = (e: PointerEvent) => {
      const deltaY = e.clientY - dragStartY.current;
      const minH = 250;
      const maxH = Math.max(minH, window.innerHeight - 240);
      const nextH = Math.max(minH, Math.min(maxH, dragStartHeight.current + deltaY));
      setTimelineHeight(nextH);
    };

    const handlePointerUp = () => {
      setIsDraggingSplitter(false);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isDraggingSplitter, setTimelineHeight]);

  // Attempt to load the MOST RECENT successfully-processed session on startup.
  useEffect(() => {
    const init = async () => {
      try {
        const sessions = await api.listSessions();
        const complete = sessions
          .filter(s => s.processing_status === 'complete' && s.duration > 0)
          .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

        if (complete.length > 0) {
          setSession(complete[0]);
        }
      } catch (e) {
        console.warn('Could not load sessions from backend:', e);
      }
    };
    init();
  }, []);

  // Compute dynamic timeline container styles
  const timelineStyle: React.CSSProperties = React.useMemo(() => {
    if (timelineMode === 'focus') {
      return {
        flex: '1 1 0',
        minHeight: 0,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden'
      };
    }
    if (timelineMode === 'expanded') {
      return {
        flex: '0 0 auto',
        height: '75vh',
        minHeight: 380,
        maxHeight: 'calc(100vh - 220px)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden'
      };
    }
    return {
      flex: '0 0 auto',
      height: `${timelineHeight}px`,
      minHeight: 250,
      maxHeight: 'calc(100vh - 240px)',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden'
    };
  }, [timelineMode, timelineHeight]);

  return (
    <div className={`editor-shell ${timelineMode === 'focus' ? 'timeline-focus-mode' : ''} ${isDraggingSplitter ? 'select-none' : ''}`}>
      <Header
        onOpenUpload={openUpload}
        onOpenExport={() => useModalStore.getState().openExport()}
        onOpenVocabulary={() => useModalStore.getState().openVocabulary()}
        onOpenBenchmark={() => useModalStore.getState().openBenchmark()}
        onOpenObservability={() => useModalStore.getState().openObservability()}
        onOpenSettings={() => useModalStore.getState().openSettings()}
      />

      <EditorToolbar />

      <div style={{ display: 'flex', flex: '1 1 0', overflow: 'hidden', minHeight: 0 }}>
        <div style={{ display: 'flex', flexDirection: 'column', flex: '1 1 0', overflow: 'hidden', minWidth: 0 }}>
          {/* Timeline Workspace (Dynamic / Resizable) */}
          <div style={timelineStyle}>
            <SpeakerTimeline onOpenUpload={openUpload} />
          </div>

          {/* Audio Transport Bar */}
          <AudioPlayer />

          {/* Draggable Divider (Hidden in Focus Mode) */}
          {timelineMode !== 'focus' && (
            <div
              className={`timeline-splitter ${isDraggingSplitter ? 'dragging' : ''}`}
              onMouseDown={handleSplitterMouseDown}
              title="Drag to resize Timeline / Transcript height"
            >
              <div className="timeline-splitter-handle" />
            </div>
          )}

          {/* Transcript Viewport (Hidden in Focus Mode) */}
          {timelineMode !== 'focus' && (
            <div style={{ flex: '1 1 0', minHeight: 150, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
              <TranscriptPanel onOpenUpload={openUpload} />
            </div>
          )}
        </div>

        <RightSidebar />
      </div>

      {/* Loading overlay */}
      {isLoading && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 100,
          background: 'rgba(7,9,15,0.75)', backdropFilter: 'blur(6px)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 14
        }}>
          <div style={{
            width: 40, height: 40, borderRadius: '50%',
            border: '3px solid rgba(56,189,248,0.15)', borderTop: '3px solid #38bdf8',
            animation: 'spin 0.8s linear infinite'
          }} />
          <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
            Processing audio pipeline…
          </span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            Diarization → ASR → Alignment → Translation
          </span>
        </div>
      )}

      {/* Modals */}
      <UploadModal
        isOpen={isUploadOpen}
        onClose={closeUpload}
        onSessionCreated={(sess) => { setSession(sess); closeUpload(); }}
      />
      <ExportMenu isOpen={isExportOpen} onClose={closeExport} />
      <SettingsModal isOpen={isSettingsOpen} onClose={closeSettings} />
      <VocabularyModal isOpen={isVocabularyOpen} onClose={closeVocabulary} />
      <BenchmarkModal isOpen={isBenchmarkOpen} onClose={closeBenchmark} />
      <ObservabilityModal isOpen={isObservabilityOpen} onClose={closeObservability} />

      {/* Global Toast Notification Container (Top of all layers & modals) */}
      <ToastContainer />

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
};
