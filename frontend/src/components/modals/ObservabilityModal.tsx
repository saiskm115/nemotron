import React from 'react';
import { useSessionStore } from '../../stores/sessionStore';
import { Activity, Clock, ShieldCheck, X } from 'lucide-react';

interface ObservabilityModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ObservabilityModal: React.FC<ObservabilityModalProps> = ({ isOpen, onClose }) => {
  const { session } = useSessionStore();
  if (!isOpen) return null;

  const obs = session?.metadata?.observability || {};
  const audioMeta = session?.metadata?.audio || {};

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content animate-fade-in" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <div className="flex items-center gap-2">
            <Activity size={18} className="text-emerald-400" />
            <h3 className="font-semibold text-sm text-slate-100">Session Diagnostics & Pipeline Observability</h3>
          </div>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-white rounded hover:bg-slate-800">
            <X size={16} />
          </button>
        </div>

        {/* Latency & Processing Metrics Grid */}
        <div className="grid grid-cols-2 gap-2.5">
          <div className="bg-slate-950 p-2.5 rounded-lg border border-white/5 flex flex-col gap-0.5">
            <span className="text-[10px] text-slate-500 font-medium">Audio Duration</span>
            <span className="font-mono text-base font-bold text-slate-100">{audioMeta.duration_sec || 0}s</span>
            <span className="text-[10px] text-slate-500">16kHz Mono PCM</span>
          </div>

          <div className="bg-slate-950 p-2.5 rounded-lg border border-white/5 flex flex-col gap-0.5">
            <span className="text-[10px] text-slate-500 font-medium">Nemotron Diarization</span>
            <span className="font-mono text-base font-bold text-cyan-400">{obs.diarization_latency_sec || 0}s</span>
            <span className="text-[10px] text-slate-500">10ms Frame Sortformer</span>
          </div>

          <div className="bg-slate-950 p-2.5 rounded-lg border border-white/5 flex flex-col gap-0.5">
            <span className="text-[10px] text-slate-500 font-medium">AutoTinglish Whisper ASR</span>
            <span className="font-mono text-base font-bold text-emerald-400">{obs.asr_latency_sec || 0}s</span>
            <span className="text-[10px] text-slate-500">Word Timestamps</span>
          </div>

          <div className="bg-slate-950 p-2.5 rounded-lg border border-white/5 flex flex-col gap-0.5">
            <span className="text-[10px] text-slate-500 font-medium">Total Pipeline Time</span>
            <span className="font-mono text-base font-bold text-amber-400">{obs.total_processing_time_sec || 0}s</span>
            <span className="text-[10px] text-slate-500">End-to-End Processing</span>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-2 pt-1 text-xs">
          <div className="p-2 bg-slate-950 rounded-lg border border-white/5 flex flex-col">
            <span className="text-[10px] text-slate-500">Overlaps Detected</span>
            <span className="font-mono font-bold text-rose-400 text-sm">{obs.overlap_count || 0}</span>
          </div>
          <div className="p-2 bg-slate-950 rounded-lg border border-white/5 flex flex-col">
            <span className="text-[10px] text-slate-500">Speakers Attributed</span>
            <span className="font-mono font-bold text-cyan-400 text-sm">{session?.speakers.length || 0}</span>
          </div>
          <div className="p-2 bg-slate-950 rounded-lg border border-white/5 flex flex-col">
            <span className="text-[10px] text-slate-500">Total Turns</span>
            <span className="font-mono font-bold text-emerald-400 text-sm">{session?.turns.length || 0}</span>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end pt-2 border-t border-white/5">
          <button onClick={onClose} className="btn btn-primary px-4 py-1.5 text-xs">
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
