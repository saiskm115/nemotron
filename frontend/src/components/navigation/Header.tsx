import React, { useState } from 'react';
import { useSessionStore } from '../../stores/sessionStore';
import { toast } from '../../stores/toastStore';
import {
  AudioWaveform, Upload, Download, Search, Undo2, Redo2,
  SlidersHorizontal, Mic, BookMarked, BarChart3, Activity,
  Settings, PanelRightClose, PanelRightOpen,
  FlaskConical, Zap, ChevronDown, RotateCcw
} from 'lucide-react';

interface HeaderProps {
  onOpenUpload: () => void;
  onOpenExport: () => void;
  onOpenVocabulary: () => void;
  onOpenBenchmark: () => void;
  onOpenObservability: () => void;
  onOpenSettings: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  onOpenUpload, onOpenExport, onOpenVocabulary,
  onOpenBenchmark, onOpenObservability, onOpenSettings
}) => {
  const {
    session, searchQuery, setSearchQuery, undo, redo, resetSession,
    isSidebarOpen, setIsSidebarOpen,
    isRecordingLive, setIsRecordingLive, saveStatus
  } = useSessionStore();

  const [isToolsOpen, setIsToolsOpen] = useState(false);

  const SaveDot = () => {
    if (saveStatus === 'saved')
      return <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981', display: 'inline-block' }} />;
    if (saveStatus === 'saving')
      return <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#f59e0b', display: 'inline-block' }} className="animate-pulse-dot" />;
    return <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#f43f5e', display: 'inline-block' }} />;
  };

  const saveLabel = saveStatus === 'saved' ? 'Saved' : saveStatus === 'saving' ? 'Saving…' : 'Unsaved';
  const saveLabelColor = saveStatus === 'saved' ? '#6ee7b7' : saveStatus === 'saving' ? '#fcd34d' : '#fca5a5';

  return (
    <header className="top-nav">
      {/* ── Left: Brand + Session ─────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
        {/* Logo */}
        <div style={{
          width: 28, height: 28, borderRadius: 7,
          background: 'linear-gradient(135deg, #0369a1 0%, #38bdf8 100%)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 2px 8px rgba(56,189,248,0.4)',
          flexShrink: 0
        }}>
          <AudioWaveform size={15} style={{ color: '#fff' }} />
        </div>

        <span style={{
          fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 14.5,
          letterSpacing: '-0.02em', color: '#f1f5f9', whiteSpace: 'nowrap'
        }}>
          Diarize<span style={{ color: '#38bdf8' }}>Studio</span>
        </span>

        <div style={{ width: 1, height: 16, background: 'rgba(255,255,255,0.1)' }} />

        {/* Session title */}
        <span style={{
          fontSize: 12, fontWeight: 500, color: 'rgba(241,245,249,0.75)',
          maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'
        }} title={session?.title}>
          {session?.title ?? 'Untitled Session'}
        </span>

        {/* Save status */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 5, padding: '2px 8px',
          borderRadius: 99, background: 'rgba(0,0,0,0.35)', border: '1px solid rgba(255,255,255,0.07)'
        }}>
          <SaveDot />
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: saveLabelColor, letterSpacing: '0.02em' }}>
            {saveLabel}
          </span>
        </div>
      </div>

      {/* ── Center: Undo/Redo + Search ───────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: '1 1 0', maxWidth: 440, margin: '0 12px' }}>
        <button onClick={() => undo()} className="tool-btn !px-1.5" title="Undo (Ctrl+Z)">
          <Undo2 size={13} />
        </button>
        <button onClick={() => redo()} className="tool-btn !px-1.5" title="Redo (Ctrl+Shift+Z)">
          <Redo2 size={13} />
        </button>

        <div style={{ position: 'relative', flex: 1 }}>
          <Search size={12} style={{
            position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)',
            color: 'var(--text-muted)', pointerEvents: 'none'
          }} />
          <input
            type="text"
            placeholder="Search transcript, speaker, text… (Ctrl+F)"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: '100%', background: 'rgba(7,9,15,0.8)',
              paddingLeft: 28, paddingRight: 10, paddingTop: 5, paddingBottom: 5,
              borderRadius: 7, border: '1px solid rgba(255,255,255,0.09)',
              fontSize: 12, color: 'rgba(241,245,249,0.85)',
              transition: 'border-color 0.15s'
            }}
            onFocus={e => (e.target.style.borderColor = 'rgba(56,189,248,0.5)')}
            onBlur={e => (e.target.style.borderColor = 'rgba(255,255,255,0.09)')}
          />
        </div>
      </div>

      {/* ── Right: Tools + Actions ───────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
        {/* Tools dropdown */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setIsToolsOpen(p => !p)}
            className="btn btn-secondary !py-1"
            style={{ fontSize: 12, gap: 4 }}
          >
            <SlidersHorizontal size={12} />
            <span>Tools</span>
            <ChevronDown size={10} style={{ opacity: 0.6 }} />
          </button>

          {isToolsOpen && (
            <div
              className="animate-fade-in"
              onMouseLeave={() => setIsToolsOpen(false)}
              style={{
                position: 'absolute', right: 0, top: 'calc(100% + 4px)',
                width: 200, background: '#0c101a',
                border: '1px solid rgba(255,255,255,0.12)',
                borderRadius: 10, boxShadow: '0 16px 40px rgba(0,0,0,0.7)',
                padding: 5, zIndex: 50, display: 'flex', flexDirection: 'column', gap: 1
              }}
            >
              {[
                { icon: <BookMarked size={13} style={{ color: '#38bdf8' }} />, label: 'Custom Vocabulary', fn: onOpenVocabulary },
                { icon: <BarChart3 size={13} style={{ color: '#f59e0b' }} />, label: 'ASR Benchmark', fn: onOpenBenchmark },
                { icon: <Activity size={13} style={{ color: '#10b981' }} />, label: 'Diagnostics', fn: onOpenObservability },
              ].map(item => (
                <button
                  key={item.label}
                  onClick={() => { item.fn(); setIsToolsOpen(false); }}
                  style={{
                    width: '100%', textAlign: 'left', padding: '7px 10px', borderRadius: 6,
                    fontSize: 12, color: 'rgba(241,245,249,0.75)', background: 'transparent',
                    border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8,
                    transition: 'background 0.1s, color 0.1s'
                  }}
                  onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.06)'; (e.currentTarget as HTMLElement).style.color = '#f1f5f9'; }}
                  onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent'; (e.currentTarget as HTMLElement).style.color = 'rgba(241,245,249,0.75)'; }}
                >
                  {item.icon}
                  <span>{item.label}</span>
                </button>
              ))}
              <div style={{ height: 1, background: 'rgba(255,255,255,0.07)', margin: '3px 0' }} />
              <button
                onClick={() => { onOpenSettings(); setIsToolsOpen(false); }}
                style={{
                  width: '100%', textAlign: 'left', padding: '7px 10px', borderRadius: 6,
                  fontSize: 12, color: 'rgba(241,245,249,0.65)', background: 'transparent',
                  border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8
                }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.06)'; }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
              >
                <Settings size={13} style={{ color: 'rgba(148,163,184,0.8)' }} />
                <span>Settings</span>
              </button>
              {session && (
                <button
                  onClick={() => {
                    setIsToolsOpen(false);
                    toast.confirm(
                      'Are you sure you want to reset this session? All manual speaker renames, splits, merges, and edits will be reverted to raw model output.',
                      {
                        title: 'Reset Session?',
                        confirmLabel: 'Reset Everything',
                        cancelLabel: 'Keep Edits',
                        confirmVariant: 'danger',
                        onConfirm: async () => {
                          await resetSession();
                        },
                        onCancel: () => {
                          toast.info('Session reset cancelled', 'Cancelled');
                        }
                      }
                    );
                  }}
                  style={{
                    width: '100%', textAlign: 'left', padding: '7px 10px', borderRadius: 6,
                    fontSize: 12, color: '#fca5a5', background: 'transparent',
                    border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8
                  }}
                  onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = 'rgba(244,63,94,0.1)'; }}
                  onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
                >
                  <RotateCcw size={13} style={{ color: '#f87171' }} />
                  <span>Reset Session</span>
                </button>
              )}
            </div>
          )}
        </div>

        {/* Live recording toggle */}
        <button
          onClick={() => setIsRecordingLive(!isRecordingLive)}
          className={isRecordingLive ? 'btn btn-danger !py-1' : 'btn btn-secondary !py-1'}
          style={{ fontSize: 12 }}
          title="Toggle Live Microphone"
        >
          <Mic size={12} style={{ color: isRecordingLive ? '#f43f5e' : undefined }} />
          <span>{isRecordingLive ? 'Stop Live' : 'Live Mic'}</span>
          {isRecordingLive && (
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#f43f5e' }} className="animate-pulse-dot" />
          )}
        </button>

        {/* Upload */}
        <button
          onClick={onOpenUpload}
          className="btn btn-secondary !py-1"
          style={{ fontSize: 12 }}
          title="Upload Audio"
          aria-label="Upload Audio"
        >
          <Upload size={12} style={{ color: '#38bdf8' }} />
          <span>Upload</span>
        </button>

        {/* Export */}
        <button
          onClick={onOpenExport}
          disabled={!session || session.turns.length === 0}
          className="btn btn-primary !py-1"
          style={{ fontSize: 12 }}
        >
          <Download size={12} />
          <span>Export</span>
        </button>

        <div style={{ width: 1, height: 16, background: 'rgba(255,255,255,0.1)' }} />

        {/* Sidebar toggle */}
        <button
          onClick={() => setIsSidebarOpen(!isSidebarOpen)}
          className={`tool-btn !px-1.5 ${isSidebarOpen ? 'active' : ''}`}
          title={isSidebarOpen ? 'Collapse Inspector' : 'Open Inspector'}
        >
          {isSidebarOpen ? <PanelRightClose size={14} /> : <PanelRightOpen size={14} />}
        </button>
      </div>
    </header>
  );
};
