import React, { useState } from 'react';
import { useSessionStore } from '../../stores/sessionStore';
import {
  Users,
  Sliders,
  Radio,
  Clock,
  Hash,
  Edit2,
  Check,
  GitMerge,
  AlertTriangle,
  Languages,
  Sparkles,
  ChevronRight,
  ShieldCheck,
  FileAudio
} from 'lucide-react';

export const RightSidebar: React.FC = () => {
  const {
    session,
    selectedTurnId,
    isSidebarOpen,
    sidebarTab,
    setSidebarTab,
    updateSpeaker,
    mergeSpeakers,
    updateTurn,
    currentTime,
    setCurrentTime
  } = useSessionStore();

  const [editingSpkId, setEditingSpkId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [editColor, setEditColor] = useState('');

  // Speaker merging state
  const [isMerging, setIsMerging] = useState(false);
  const [sourceId, setSourceId] = useState('');
  const [targetId, setTargetId] = useState('');

  const speakers = session?.speakers || [];
  const turns = session?.turns || [];
  const selectedTurn = turns.find(t => t.id === selectedTurnId);
  const selectedSpeaker = speakers.find(s => s.id === selectedTurn?.speaker_id);

  if (!isSidebarOpen) return null;

  const handleStartEdit = (spk: any) => {
    setEditingSpkId(spk.id);
    setEditName(spk.display_name);
    setEditColor(spk.color);
  };

  const handleSaveEdit = async (spkId: string) => {
    await updateSpeaker(spkId, {
      display_name: editName,
      color: editColor
    });
    setEditingSpkId(null);
  };

  const handlePerformMerge = async () => {
    if (!sourceId || !targetId || sourceId === targetId) return;
    await mergeSpeakers(sourceId, targetId);
    setIsMerging(false);
    setSourceId('');
    setTargetId('');
  };

  const formatSecs = (s: number) => {
    const mins = Math.floor(s / 60);
    const secs = Math.floor(s % 60);
    return `${mins}m ${secs}s`;
  };

  return (
    <aside className="inspector-sidebar">
      {/* Sidebar Tabs */}
      <div className="flex items-center border-b border-white/10 bg-slate-950 px-2 py-1 gap-1 text-xs">
        <button
          onClick={() => setSidebarTab('speakers')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition ${
            sidebarTab === 'speakers'
              ? 'bg-slate-800 text-cyan-300 font-semibold shadow-sm'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Users size={13} />
          <span>Speakers ({speakers.length})</span>
        </button>

        <button
          onClick={() => setSidebarTab('properties')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition ${
            sidebarTab === 'properties'
              ? 'bg-slate-800 text-cyan-300 font-semibold shadow-sm'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Sliders size={13} />
          <span>Inspector</span>
        </button>
      </div>

      {/* Tab 1: Speakers Management */}
      {sidebarTab === 'speakers' && (
        <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-3">
          <div className="flex items-center justify-between pb-1 border-b border-white/5">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Diarized Voices
            </span>
            <button
              onClick={() => setIsMerging(!isMerging)}
              className="btn btn-secondary !py-0.5 text-[11px] text-cyan-300 hover:text-white"
            >
              <GitMerge size={12} />
              <span>Merge</span>
            </button>
          </div>

          {/* Merge Dialog */}
          {isMerging && (
            <div className="p-2.5 bg-slate-950 rounded-lg border border-cyan-500/30 flex flex-col gap-2 animate-fade-in text-xs">
              <span className="text-[11px] text-slate-300 font-medium">Merge source into target:</span>
              <div className="flex flex-col gap-1.5">
                <select
                  value={sourceId}
                  onChange={(e) => setSourceId(e.target.value)}
                  className="bg-slate-900 border border-white/10 p-1 rounded text-slate-200 text-xs"
                >
                  <option value="">Source speaker...</option>
                  {speakers.map(s => (
                    <option key={s.id} value={s.id}>{s.display_name} ({s.id})</option>
                  ))}
                </select>
                <select
                  value={targetId}
                  onChange={(e) => setTargetId(e.target.value)}
                  className="bg-slate-900 border border-white/10 p-1 rounded text-slate-200 text-xs"
                >
                  <option value="">Target speaker...</option>
                  {speakers.map(s => (
                    <option key={s.id} value={s.id}>{s.display_name} ({s.id})</option>
                  ))}
                </select>
              </div>
              <div className="flex justify-end gap-1.5 mt-1">
                <button onClick={() => setIsMerging(false)} className="btn btn-secondary !py-0.5 text-[11px]">
                  Cancel
                </button>
                <button
                  disabled={!sourceId || !targetId || sourceId === targetId}
                  onClick={handlePerformMerge}
                  className="btn btn-primary !py-0.5 text-[11px] disabled:opacity-50"
                >
                  Confirm Merge
                </button>
              </div>
            </div>
          )}

          {/* Speaker Cards */}
          <div className="flex flex-col gap-2">
            {speakers.map((spk) => {
              const isEdit = editingSpkId === spk.id;
              return (
                <div
                  key={spk.id}
                  className="p-2.5 rounded-lg bg-slate-900/60 border border-white/5 flex flex-col gap-2"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span
                        className="w-3 h-3 rounded-full shrink-0 shadow-sm"
                        style={{ backgroundColor: spk.color }}
                      />
                      {isEdit ? (
                        <input
                          type="text"
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          className="bg-slate-950 px-1.5 py-0.5 rounded text-xs text-white border border-cyan-400 focus:outline-none"
                        />
                      ) : (
                        <span className="font-semibold text-xs text-slate-200">{spk.display_name}</span>
                      )}
                    </div>

                    {isEdit ? (
                      <div className="flex items-center gap-1">
                        <input
                          type="color"
                          value={editColor}
                          onChange={(e) => setEditColor(e.target.value)}
                          className="w-5 h-5 rounded cursor-pointer bg-transparent border-0"
                        />
                        <button
                          onClick={() => handleSaveEdit(spk.id)}
                          className="p-1 text-emerald-400 hover:bg-emerald-500/20 rounded"
                        >
                          <Check size={12} />
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => handleStartEdit(spk)}
                        className="p-1 text-slate-400 hover:text-white rounded hover:bg-slate-800"
                        title="Rename or Change Color"
                      >
                        <Edit2 size={11} />
                      </button>
                    )}
                  </div>

                  {/* Speaker Metrics */}
                  <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono pt-1 border-t border-white/5">
                    <span>{formatSecs(spk.total_speaking_time)} spoken</span>
                    <span>{spk.turn_count} turns</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Tab 2: Properties Inspector */}
      {sidebarTab === 'properties' && (
        <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-3">
          {selectedTurn ? (
            <div className="flex flex-col gap-3 text-xs">
              <div className="flex items-center justify-between pb-1 border-b border-white/5">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                  Selected Turn Properties
                </span>
                <span className="font-mono text-[10px] text-cyan-400 bg-slate-950 px-1.5 py-0.5 rounded border border-white/5">
                  {selectedTurn.id}
                </span>
              </div>

              {/* Speaker Attribution */}
              <div className="p-2.5 rounded-lg bg-slate-900/60 border border-white/5 flex flex-col gap-1.5">
                <span className="text-[10px] text-slate-500 font-semibold uppercase">Speaker</span>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2.5 h-2.5 rounded-full"
                      style={{ backgroundColor: selectedSpeaker?.color || '#38bdf8' }}
                    />
                    <span className="font-medium text-slate-200">
                      {selectedSpeaker?.display_name || selectedTurn.speaker_id}
                    </span>
                  </div>

                  <select
                    value={selectedTurn.speaker_id}
                    onChange={(e) => updateTurn(selectedTurn.id, { speaker_id: e.target.value })}
                    className="bg-slate-950 text-xs text-slate-300 border border-white/10 rounded px-2 py-0.5"
                  >
                    {speakers.map(s => (
                      <option key={s.id} value={s.id}>{s.display_name}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Timestamps */}
              <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
                <div className="p-2 rounded-lg bg-slate-950 border border-white/5 flex flex-col gap-0.5">
                  <span className="text-[10px] text-slate-500 font-sans">Start Timestamp</span>
                  <span className="text-cyan-400 font-semibold">{selectedTurn.start.toFixed(2)}s</span>
                </div>
                <div className="p-2 rounded-lg bg-slate-950 border border-white/5 flex flex-col gap-0.5">
                  <span className="text-[10px] text-slate-500 font-sans">End Timestamp</span>
                  <span className="text-cyan-400 font-semibold">{selectedTurn.end.toFixed(2)}s</span>
                </div>
              </div>

              {/* Status & Overlap */}
              <div className="p-2.5 rounded-lg bg-slate-900/60 border border-white/5 flex flex-col gap-2">
                <div className="flex justify-between items-center text-[11px]">
                  <span className="text-slate-400">Duration:</span>
                  <span className="font-mono text-slate-200">{(selectedTurn.end - selectedTurn.start).toFixed(2)}s</span>
                </div>

                <div className="flex justify-between items-center text-[11px]">
                  <span className="text-slate-400">Confidence:</span>
                  <span className="font-mono text-emerald-400">
                    {selectedTurn.confidence ? `${Math.round(selectedTurn.confidence * 100)}%` : '95% (High)'}
                  </span>
                </div>

                <div className="flex justify-between items-center text-[11px]">
                  <span className="text-slate-400">Status:</span>
                  <span className="font-mono text-slate-300 uppercase">{selectedTurn.status}</span>
                </div>

                {selectedTurn.overlap && (
                  <div className="p-2 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300 flex items-center gap-1.5 text-[11px]">
                    <AlertTriangle size={13} className="shrink-0" />
                    <span>Overlapping speech / barge-in flagged</span>
                  </div>
                )}
              </div>

              {/* Translation */}
              {selectedTurn.translated_text && (
                <div className="p-2.5 rounded-lg bg-slate-900/60 border border-white/5 flex flex-col gap-1">
                  <span className="text-[10px] text-slate-500 font-semibold uppercase">English Translation</span>
                  <p className="text-xs text-sky-200/90 italic">"{selectedTurn.translated_text}"</p>
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center p-8 text-center text-slate-500 gap-2">
              <Sliders size={24} className="text-slate-700" />
              <span className="text-xs">No turn or timeline segment selected.</span>
              <span className="text-[10px] text-slate-600">Click a speaker block on the timeline or a transcript row to inspect details.</span>
            </div>
          )}
        </div>
      )}
    </aside>
  );
};
