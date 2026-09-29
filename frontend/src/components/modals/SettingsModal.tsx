import React, { useEffect, useState } from 'react';
import { useSessionStore } from '../../stores/sessionStore';
import { api } from '../../services/api';
import { ASRModelOption } from '../../types';
import { Settings, X, ShieldCheck, Cpu, Mic, Languages } from 'lucide-react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
  const { session, updateSettings } = useSessionStore();
  const [models, setModels] = useState<ASRModelOption[]>([]);

  useEffect(() => {
    if (!isOpen || models.length) return;
    api.listASRModels().then(setModels).catch(() => setModels([]));
  }, [isOpen, models.length]);

  if (!isOpen) return null;

  const currentSettings = session?.settings;
  const observability = (session?.metadata as any)?.observability ?? {};
  const asrModel = currentSettings?.asr_model ?? models.find((m) => m.selected)?.id ?? '';
  const selected = models.find((m) => m.id === asrModel);
  const isLocal = selected ? selected.local : true;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content animate-fade-in" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <div className="flex items-center gap-2">
            <Settings size={18} className="text-cyan-400" />
            <h3 className="font-semibold text-sm text-slate-100">DiarizeStudio Engine Settings</h3>
          </div>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-white rounded hover:bg-slate-800">
            <X size={16} />
          </button>
        </div>

        {/* Content */}
        <div className="flex flex-col gap-4 text-xs">
          {/* Transcription model */}
          <div className="p-3 rounded-lg bg-slate-950 border border-white/5 flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-200 flex items-center gap-1.5">
                <Cpu size={12} className="text-cyan-400" /> Transcription Model
              </span>
              <span className="badge badge-final text-[10px]">{selected?.local ? 'On-device' : 'Cloud'}</span>
            </div>
            <select
              value={asrModel}
              onChange={(e) => updateSettings({ asr_model: e.target.value })}
              disabled={!models.length}
              aria-label="Transcription model"
              className="bg-slate-900 border border-white/10 p-1.5 rounded text-slate-200 text-xs disabled:opacity-50"
            >
              {models.map((m) => (
                <option key={m.id} value={m.id} disabled={!m.available}>
                  {m.label}{m.available ? '' : ' (unavailable)'}
                </option>
              ))}
            </select>
            <p className="text-[11px] text-slate-400">
              {selected?.description ?? 'Loading available models…'}
            </p>
            {!selected?.available && selected?.unavailable_reason && (
              <p className="text-[11px] text-amber-400">Unavailable: {selected.unavailable_reason}</p>
            )}
            <div className="flex items-center gap-2 pt-1">
              <span className="text-slate-400">Transcription Mode:</span>
              <select
                value={currentSettings?.asr_mode ?? 'codemix'}
                onChange={(e) => updateSettings({ asr_mode: e.target.value as any })}
                className="bg-slate-900 border border-white/10 p-1 rounded text-slate-200 text-xs"
              >
                <option value="codemix">MODE B: Code-mixed (Preserve English terms)</option>
                <option value="normal">MODE A: Normal Readable</option>
                <option value="verbatim">MODE C: Verbatim (Fillers & Hesitations)</option>
              </select>
            </div>
            {observability.asr_model && (
              <p className="text-[10px] text-slate-500 font-mono">
                This session was transcribed with: {observability.asr_model} ({observability.asr_language ?? 'n/a'})
              </p>
            )}
          </div>

          {/* Diarization engine */}
          <div className="p-3 rounded-lg bg-slate-950 border border-white/5 flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-200 flex items-center gap-1.5">
                <Mic size={12} className="text-emerald-400" /> Diarization Engine
              </span>
              <span className="badge badge-final text-[10px]">
                {observability.diarization_method === 'sortformer'
                  ? 'NVIDIA Sortformer'
                  : observability.diarization_method === 'nemotron_endpoint'
                  ? 'Nemotron Endpoint'
                  : 'Neural (local)'}
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Voice activity detection followed by speaker-embedding clustering. Overlapping speech is
              labelled only when the active model actually predicts it.
            </p>
            {observability.diarization_speaker_count != null && (
              <p className="text-[10px] text-slate-500 font-mono">
                Speakers detected in this session: {observability.diarization_speaker_count} ·
                latency {observability.diarization_latency_sec}s
              </p>
            )}
          </div>

          {/* Language handling */}
          <div className="p-3 rounded-lg bg-slate-950 border border-white/5 flex flex-col gap-2">
            <span className="font-semibold text-slate-200 flex items-center gap-1.5">
              <Languages size={12} className="text-violet-400" /> Language Handling
            </span>
            <p className="text-[11px] text-slate-400">
              The spoken language you choose is passed to the model. For Svanita this locks the output
              script, so Telugu audio comes back in Telugu while English words inside it stay in Latin.
              Choose <em>Auto-detect</em> when the language is unknown.
            </p>
          </div>

          {/* Privacy */}
          <div className="p-3 rounded-lg bg-emerald-950/20 border border-emerald-500/20 flex items-center justify-between text-xs text-emerald-300">
            <div className="flex items-center gap-2">
              <ShieldCheck size={16} className="text-emerald-400 shrink-0" />
              <div className="flex flex-col">
                <span className="font-semibold">
                  {isLocal ? 'Local Sovereign Processing' : 'Cloud Processing Enabled'}
                </span>
                <span className="text-[10px] text-slate-400">
                  {isLocal
                    ? 'Audio and models execute locally on-device. No audio leaves the machine.'
                    : `Audio is uploaded to the ${selected?.label ?? 'selected cloud provider'}.`}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end pt-2 border-t border-white/5">
          <button onClick={onClose} className="btn btn-primary px-4 py-1.5 text-xs">
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
