import React, { useState } from 'react';
import { useSessionStore } from '../../stores/sessionStore';
import {
  AudioWaveform,
  Upload,
  Download,
  Search,
  Undo2,
  Redo2,
  SlidersHorizontal,
  Mic,
  BookMarked,
  BarChart3,
  Activity,
  Settings,
  PanelRightClose,
  PanelRightOpen,
  CheckCircle2,
  AlertCircle
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
  onOpenUpload,
  onOpenExport,
  onOpenVocabulary,
  onOpenBenchmark,
  onOpenObservability,
  onOpenSettings
}) => {
  const {
    session,
    searchQuery,
    setSearchQuery,
    undo,
    redo,
    isSidebarOpen,
    setIsSidebarOpen,
    isRecordingLive,
    setIsRecordingLive,
    saveStatus
  } = useSessionStore();

  const [isToolsOpen, setIsToolsOpen] = useState(false);

  return (
    <header className="top-nav">
      {/* Left: Brand, Session Title, Save Status Indicator */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-gradient-to-tr from-sky-600 to-cyan-400 flex items-center justify-center shadow-sm">
            <AudioWaveform size={14} className="text-white" />
          </div>
          <span className="font-display font-bold text-sm tracking-tight text-white">
            Diarize<span className="text-cyan-400">Studio</span>
          </span>
        </div>

        <div className="h-4 w-[1px] bg-white/10 mx-1" />

        {/* Session Name */}
        <span className="text-xs font-medium text-slate-200 truncate max-w-[200px]" title={session?.title}>
          {session?.title || 'Untitled Session'}
        </span>

        {/* Save Status Badge (Section 3 of ui.md) */}
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-mono bg-slate-900 border border-white/5">
          {saveStatus === 'saved' ? (
            <>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <span className="text-slate-400">Saved</span>
            </>
          ) : saveStatus === 'saving' ? (
            <>
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
              <span className="text-amber-300">Saving...</span>
            </>
          ) : (
            <>
              <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
              <span className="text-rose-300">Unsaved</span>
            </>
          )}
        </div>
      </div>

      {/* Center: Search & Quick Edit Actions */}
      <div className="flex items-center gap-2 flex-1 max-w-md mx-4">
        {/* Undo / Redo */}
        <div className="flex items-center gap-0.5">
          <button
            onClick={() => undo()}
            className="tool-btn !px-1.5"
            title="Undo (Ctrl+Z)"
          >
            <Undo2 size={13} />
          </button>
          <button
            onClick={() => redo()}
            className="tool-btn !px-1.5"
            title="Redo (Ctrl+Shift+Z)"
          >
            <Redo2 size={13} />
          </button>
        </div>

        {/* Quick Search Input */}
        <div className="relative flex-1">
          <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search transcript, speaker, translation... (Ctrl+F)"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-950/80 pl-7 pr-3 py-1 rounded-md border border-white/10 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-sans"
          />
        </div>
      </div>

      {/* Right: Tools Dropdown, Live Mic, Upload, Export, Sidebar Toggle */}
      <div className="flex items-center gap-2">
        {/* Secondary Tools Dropdown */}
        <div className="relative">
          <button
            onClick={() => setIsToolsOpen(!isToolsOpen)}
            className="btn btn-secondary !py-1 text-xs"
            title="Secondary Tools & Settings"
          >
            <SlidersHorizontal size={13} />
            <span>Tools</span>
          </button>

          {isToolsOpen && (
            <div
              className="absolute right-0 mt-1 w-48 bg-slate-950 border border-white/15 rounded-lg shadow-2xl p-1 z-50 flex flex-col gap-0.5 animate-fade-in"
              onMouseLeave={() => setIsToolsOpen(false)}
            >
              <button
                onClick={() => { onOpenVocabulary(); setIsToolsOpen(false); }}
                className="w-full text-left px-2.5 py-1.5 rounded text-xs text-slate-300 hover:text-white hover:bg-slate-800 flex items-center gap-2"
              >
                <BookMarked size={13} className="text-cyan-400" />
                <span>Custom Vocabulary</span>
              </button>
              <button
                onClick={() => { onOpenBenchmark(); setIsToolsOpen(false); }}
                className="w-full text-left px-2.5 py-1.5 rounded text-xs text-slate-300 hover:text-white hover:bg-slate-800 flex items-center gap-2"
              >
                <BarChart3 size={13} className="text-amber-400" />
                <span>ASR Benchmark</span>
              </button>
              <button
                onClick={() => { onOpenObservability(); setIsToolsOpen(false); }}
                className="w-full text-left px-2.5 py-1.5 rounded text-xs text-slate-300 hover:text-white hover:bg-slate-800 flex items-center gap-2"
              >
                <Activity size={13} className="text-emerald-400" />
                <span>Diagnostics</span>
              </button>
              <div className="h-[1px] bg-white/10 my-1" />
              <button
                onClick={() => { onOpenSettings(); setIsToolsOpen(false); }}
                className="w-full text-left px-2.5 py-1.5 rounded text-xs text-slate-300 hover:text-white hover:bg-slate-800 flex items-center gap-2"
              >
                <Settings size={13} className="text-slate-400" />
                <span>Settings</span>
              </button>
            </div>
          )}
        </div>

        {/* Live Mic Mode Toggle */}
        <button
          onClick={() => setIsRecordingLive(!isRecordingLive)}
          className={`btn ${isRecordingLive ? 'btn-danger animate-pulse' : 'btn-secondary'} !py-1 text-xs`}
          title="Toggle Live Microphone Stream"
        >
          <Mic size={13} className={isRecordingLive ? 'text-rose-400' : 'text-slate-400'} />
          <span>{isRecordingLive ? 'Live On' : 'Live'}</span>
        </button>

        {/* Upload Audio */}
        <button
          onClick={onOpenUpload}
          className="btn btn-secondary !py-1 text-xs"
        >
          <Upload size={13} className="text-cyan-400" />
          <span>Upload</span>
        </button>

        {/* Export */}
        <button
          onClick={onOpenExport}
          disabled={!session || session.turns.length === 0}
          className="btn btn-primary !py-1 text-xs disabled:opacity-40"
        >
          <Download size={13} />
          <span>Export</span>
        </button>

        {/* Toggle Right Inspector Sidebar */}
        <button
          onClick={() => setIsSidebarOpen(!isSidebarOpen)}
          className={`tool-btn !px-1.5 ${isSidebarOpen ? 'active' : ''}`}
          title={isSidebarOpen ? 'Collapse Inspector Panel' : 'Expand Inspector Panel'}
        >
          {isSidebarOpen ? <PanelRightClose size={14} /> : <PanelRightOpen size={14} />}
        </button>
      </div>
    </header>
  );
};
