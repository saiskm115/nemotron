import React from 'react';
import { useSessionStore } from '../../stores/sessionStore';
import { Activity, Clock, ShieldAlert, Cpu, CheckCircle } from 'lucide-react';

export const ObservabilityPanel: React.FC = () => {
  const { session } = useSessionStore();
  const obs = session?.metadata?.observability || {};
  const audioMeta = session?.metadata?.audio || {};

  return (
    <div className="glass-panel p-5 flex flex-col gap-4">
      <div className="flex items-center justify-between border-b border-white/5 pb-3">
        <div className="flex items-center gap-2">
          <Activity size={18} className="text-cyan-400" />
          <h3 className="font-semibold text-sm text-slate-100">Session Observability & Processing Quality (Section 46)</h3>
        </div>
        <span className="badge badge-final">Pipeline Verified</span>
      </div>

      {/* Latency & Processing Metrics Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-slate-950/80 p-3 rounded-xl border border-white/5 flex flex-col gap-1">
          <span className="text-[11px] text-slate-400">Audio Duration</span>
          <span className="font-mono text-lg font-bold text-slate-100">{audioMeta.duration_sec || 0}s</span>
          <span className="text-[10px] text-slate-500">16kHz Mono PCM</span>
        </div>

        <div className="bg-slate-950/80 p-3 rounded-xl border border-white/5 flex flex-col gap-1">
          <span className="text-[11px] text-slate-400">Nemotron Diarization Latency</span>
          <span className="font-mono text-lg font-bold text-cyan-400">{obs.diarization_latency_sec || 0}s</span>
          <span className="text-[10px] text-slate-500">10ms Frame Sortformer</span>
        </div>

        <div className="bg-slate-950/80 p-3 rounded-xl border border-white/5 flex flex-col gap-1">
          <span className="text-[11px] text-slate-400">AutoTinglish Whisper ASR Latency</span>
          <span className="font-mono text-lg font-bold text-emerald-400">{obs.asr_latency_sec || 0}s</span>
          <span className="text-[10px] text-slate-500">Word Timestamps</span>
        </div>

        <div className="bg-slate-950/80 p-3 rounded-xl border border-white/5 flex flex-col gap-1">
          <span className="text-[11px] text-slate-400">Total Processing Time</span>
          <span className="font-mono text-lg font-bold text-amber-400">{obs.total_processing_time_sec || 0}s</span>
          <span className="text-[10px] text-slate-500">End-to-End Pipeline</span>
        </div>
      </div>

      {/* Quality Health Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2">
        <div className="p-3 bg-slate-900/60 rounded-xl border border-white/5 flex items-center justify-between">
          <div className="flex flex-col">
            <span className="text-xs text-slate-300 font-medium">Overlapping Speech Regions</span>
            <span className="text-[11px] text-slate-500">Barge-in simultaneous turns</span>
          </div>
          <span className="font-mono text-base font-bold text-rose-400">{obs.overlap_count || 0}</span>
        </div>

        <div className="p-3 bg-slate-900/60 rounded-xl border border-white/5 flex items-center justify-between">
          <div className="flex flex-col">
            <span className="text-xs text-slate-300 font-medium">Distinct Speakers</span>
            <span className="text-[11px] text-slate-500">Attributed & aligned</span>
          </div>
          <span className="font-mono text-base font-bold text-cyan-400">{session?.speakers.length || 0}</span>
        </div>

        <div className="p-3 bg-slate-900/60 rounded-xl border border-white/5 flex items-center justify-between">
          <div className="flex flex-col">
            <span className="text-xs text-slate-300 font-medium">Alignment Engine</span>
            <span className="text-[11px] text-slate-500">Temporal overlap delta</span>
          </div>
          <span className="font-mono text-base font-bold text-emerald-400">{obs.alignment_latency_sec || 0}s</span>
        </div>
      </div>
    </div>
  );
};
