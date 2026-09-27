import React, { useState } from 'react';
import { useSessionStore } from '../../stores/sessionStore';
import { Users, GitMerge, Clock, Hash, Edit2, Check } from 'lucide-react';

export const SpeakerList: React.FC = () => {
  const { session, updateSpeaker, mergeSpeakers } = useSessionStore();
  const [editingSpkId, setEditingSpkId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [editColor, setEditColor] = useState('');

  // Merging state
  const [isMerging, setIsMerging] = useState(false);
  const [sourceId, setSourceId] = useState('');
  const [targetId, setTargetId] = useState('');

  const speakers = session?.speakers || [];

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
    <div className="glass-panel p-4 flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/5 pb-3">
        <div className="flex items-center gap-2">
          <Users size={18} className="text-cyan-400" />
          <h3 className="font-semibold text-sm text-slate-100">Speaker Management</h3>
        </div>

        <button
          onClick={() => setIsMerging(!isMerging)}
          className="btn btn-secondary px-3 py-1.5 text-xs text-cyan-300 hover:text-white"
        >
          <GitMerge size={14} />
          <span>Merge Speakers</span>
        </button>
      </div>

      {/* Merge Dialog */}
      {isMerging && (
        <div className="p-3 bg-slate-950/90 rounded-xl border border-cyan-500/30 flex flex-col gap-3">
          <p className="text-xs text-slate-300 font-medium">
            Merge all turns from source speaker into target speaker:
          </p>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <label className="text-[11px] text-slate-400 block mb-1">Source Speaker (will be removed):</label>
              <select
                value={sourceId}
                onChange={(e) => setSourceId(e.target.value)}
                className="w-full bg-slate-900 border border-white/10 p-1.5 rounded text-slate-200"
              >
                <option value="">Select source...</option>
                {speakers.map(s => (
                  <option key={s.id} value={s.id}>{s.display_name} ({s.id})</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[11px] text-slate-400 block mb-1">Target Speaker (will receive turns):</label>
              <select
                value={targetId}
                onChange={(e) => setTargetId(e.target.value)}
                className="w-full bg-slate-900 border border-white/10 p-1.5 rounded text-slate-200"
              >
                <option value="">Select target...</option>
                {speakers.map(s => (
                  <option key={s.id} value={s.id}>{s.display_name} ({s.id})</option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex justify-end gap-2 mt-1">
            <button
              onClick={() => setIsMerging(false)}
              className="btn btn-secondary px-3 py-1 text-xs"
            >
              Cancel
            </button>
            <button
              disabled={!sourceId || !targetId || sourceId === targetId}
              onClick={handlePerformMerge}
              className="btn btn-primary px-3 py-1 text-xs disabled:opacity-50"
            >
              Confirm Merge
            </button>
          </div>
        </div>
      )}

      {/* Speaker Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {speakers.map((spk) => {
          const isEdit = editingSpkId === spk.id;
          return (
            <div
              key={spk.id}
              className="glass-panel p-3.5 rounded-xl border border-white/5 flex flex-col gap-2.5 bg-slate-900/50"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span
                    className="w-3.5 h-3.5 rounded-full ring-2 ring-white/10 shrink-0"
                    style={{ backgroundColor: spk.color }}
                  />
                  {isEdit ? (
                    <input
                      type="text"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      className="bg-slate-950 px-2 py-0.5 rounded text-xs text-white border border-cyan-400 focus:outline-none"
                    />
                  ) : (
                    <span className="font-semibold text-sm text-slate-100">{spk.display_name}</span>
                  )}
                  <span className="text-[10px] text-slate-500 font-mono bg-slate-950 px-1.5 py-0.5 rounded">
                    {spk.model_label || spk.id}
                  </span>
                </div>

                {isEdit ? (
                  <div className="flex items-center gap-1">
                    <input
                      type="color"
                      value={editColor}
                      onChange={(e) => setEditColor(e.target.value)}
                      className="w-6 h-6 rounded cursor-pointer bg-transparent border-0"
                    />
                    <button
                      onClick={() => handleSaveEdit(spk.id)}
                      className="p-1 text-emerald-400 hover:bg-emerald-500/20 rounded"
                    >
                      <Check size={14} />
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => handleStartEdit(spk)}
                    className="p-1 text-slate-400 hover:text-white rounded hover:bg-slate-800"
                  >
                    <Edit2 size={13} />
                  </button>
                )}
              </div>

              {/* Analytics row */}
              <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-400 pt-1 border-t border-white/5">
                <div className="flex items-center gap-1.5">
                  <Clock size={12} className="text-slate-500" />
                  <span>Speaking time:</span>
                  <span className="font-mono text-slate-200">{formatSecs(spk.total_speaking_time)}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Hash size={12} className="text-slate-500" />
                  <span>Turns:</span>
                  <span className="font-mono text-slate-200">{spk.turn_count}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
