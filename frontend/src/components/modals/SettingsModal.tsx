import React from 'react';
import { useSessionStore } from '../../stores/sessionStore';
import { Settings, X, ShieldCheck, Cpu, Mic, Languages } from 'lucide-react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
  const { session, updateSettings } = useSessionStore();
  if (!isOpen) return null;

  const currentSettings = session?.settings || {
    asr_mode: 'codemix',
    primary_language: 'te-IN',
    target_language: 'en-IN',
    auto_translate: true
  };

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
          {/* ASR Model Engine */}
          <div className="p-3 rounded-lg bg-slate-950 border border-white/5 flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-200">Primary ASR Engine</span>
              <span className="badge badge-final text-[10px]">Active</span>
            </div>
            <p className="text-[11px] text-slate-400">
              AutoTinglishSub Whisper Telugu Small (Quantized INT8 CTranslate2) configured for Telugu + English code-mixed speech.
            </p>
            <div className="flex items-center gap-2 pt-1">
              <span className="text-slate-400">Transcription Mode:</span>
              <select
                value={currentSettings.asr_mode}
                onChange={(e) => updateSettings({ asr_mode: e.target.value as any })}
                className="bg-slate-900 border border-white/10 p-1 rounded text-slate-200 text-xs"
              >
                <option value="codemix">MODE B: Code-mixed (Preserve English terms)</option>
                <option value="normal">MODE A: Normal Readable</option>
                <option value="verbatim">MODE C: Verbatim (Fillers & Hesitations)</option>
              </select>
            </div>
          </div>

          {/* Diarization Engine */}
          <div className="p-3 rounded-lg bg-slate-950 border border-white/5 flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-200">Diarization Engine</span>
              <span className="badge badge-final text-[10px]">Nemotron 3</span>
            </div>
            <p className="text-[11px] text-slate-400">
              NVIDIA Nemotron 3 Diarization with 10ms frame resolution, tracking up to 8 simultaneous speakers and native barge-in / overlap collisions.
            </p>
          </div>

          {/* Privacy & Sovereignty */}
          <div className="p-3 rounded-lg bg-emerald-950/20 border border-emerald-500/20 flex items-center justify-between text-xs text-emerald-300">
            <div className="flex items-center gap-2">
              <ShieldCheck size={16} className="text-emerald-400 shrink-0" />
              <div className="flex flex-col">
                <span className="font-semibold">Local Sovereign Processing</span>
                <span className="text-[10px] text-slate-400">Audio and models execute locally on-device. No audio leaks.</span>
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
