import React, { useState } from 'react';
import { useSessionStore } from '../../stores/sessionStore';
import { api } from '../../services/api';
import { UploadCloud, FileAudio, Check, AlertCircle, Loader2, X } from 'lucide-react';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const UploadModal: React.FC<UploadModalProps> = ({ isOpen, onClose }) => {
  const { setSession } = useSessionStore();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('Telugu English Executive Meeting');
  const [asrMode, setAsrMode] = useState<'codemix' | 'normal' | 'verbatim'>('codemix');
  const [primaryLang, setPrimaryLang] = useState('unknown');
  const [targetLang, setTargetLang] = useState('en-IN');
  const [autoTranslate, setAutoTranslate] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      if (!title || title === 'Telugu English Executive Meeting') {
        setTitle(e.target.files[0].name.replace(/\.[^/.]+$/, ""));
      }
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setIsUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', title);
    formData.append('asr_mode', asrMode);
    formData.append('primary_language', primaryLang);
    formData.append('target_language', targetLang);
    formData.append('auto_translate', autoTranslate ? 'true' : 'false');

    try {
      const session = await api.uploadAudio(formData);
      setSession(session);
      setIsUploading(false);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Processing failed');
      setIsUploading(false);
    }
  };

  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isUploading) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isUploading, onClose]);

  return (
    <div
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 overflow-y-auto"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="glass-panel-elevated w-full max-w-lg p-6 flex flex-col gap-4 border border-white/10 animate-fade-in my-auto max-h-[90vh] overflow-y-auto"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/5 pb-3">
          <div className="flex items-center gap-2">
            <UploadCloud size={20} className="text-cyan-400" />
            <h3 className="font-semibold text-base text-slate-100">Upload Audio / Video for Diarization & ASR</h3>
          </div>
          <button
            onClick={onClose}
            disabled={isUploading}
            className="p-1 text-slate-400 hover:text-white rounded hover:bg-slate-800"
          >
            <X size={16} />
          </button>
        </div>

        {error && (
          <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle size={15} className="shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* File Drag Area */}
        <label className="border-2 border-dashed border-white/15 hover:border-cyan-500/50 rounded-xl p-6 flex flex-col items-center justify-center gap-2 cursor-pointer bg-slate-950/50 transition">
          <FileAudio size={36} className={file ? 'text-cyan-400' : 'text-slate-500'} />
          <span className="text-xs font-medium text-slate-200">
            {file ? file.name : 'Click to browse or drop WAV, MP3, M4A, FLAC audio'}
          </span>
          <span className="text-[11px] text-slate-500">
            {file ? `${(file.size / (1024 * 1024)).toFixed(2)} MB` : '16kHz mono will be automatically prepared'}
          </span>
          <input
            type="file"
            accept="audio/*,video/*,.wav,.mp3,.m4a,.flac,.ogg"
            onChange={handleFileChange}
            className="hidden"
          />
        </label>

        {/* Session Title */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400 font-medium">Session Title:</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="bg-slate-950 px-3 py-1.5 rounded-lg border border-white/10 text-xs text-slate-200 focus:outline-none focus:border-cyan-400"
          />
        </div>

        {/* ASR Model Engine Selector */}
        <div className="flex flex-col gap-1">
          <div className="flex justify-between items-center">
            <label className="text-xs text-slate-300 font-medium">Primary ASR Engine:</label>
            <span className="text-[10px] text-cyan-400 bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-500/30">
              Active: AutoTinglishSub
            </span>
          </div>
          <select
            className="bg-slate-950 p-2 rounded-lg border border-cyan-500/40 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-cyan-400"
            defaultValue="auto_tinglish_whisper_telugu"
          >
            <option value="auto_tinglish_whisper_telugu">AutoTinglishSub — Whisper Telugu Small (Quantized INT8) [Recommended]</option>
            <option value="vasista22_whisper_telugu">Vasista22 / Whisper Telugu Small (Fine-tuned)</option>
            <option value="sarvam_saaras_v4">Sarvam Saaras V4 (Cloud REST API)</option>
            <option value="whisper_large">OpenAI Whisper Large V3</option>
          </select>
        </div>

        {/* ASR Mode Selection (Section 3) */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs text-slate-400 font-medium">ASR Transcription Mode:</label>
          <div className="grid grid-cols-3 gap-2 text-xs">
            <button
              type="button"
              onClick={() => setAsrMode('codemix')}
              className={`p-2.5 rounded-lg border text-left flex flex-col gap-1 transition ${
                asrMode === 'codemix'
                  ? 'border-cyan-400 bg-cyan-950/30 text-cyan-200'
                  : 'border-white/5 bg-slate-900/60 text-slate-400 hover:text-slate-200'
              }`}
            >
              <span className="font-semibold text-xs">MODE B: Code-mixed</span>
              <span className="text-[10px] text-slate-400">Preserves Telugu + English spoken terms</span>
            </button>

            <button
              type="button"
              onClick={() => setAsrMode('normal')}
              className={`p-2.5 rounded-lg border text-left flex flex-col gap-1 transition ${
                asrMode === 'normal'
                  ? 'border-cyan-400 bg-cyan-950/30 text-cyan-200'
                  : 'border-white/5 bg-slate-900/60 text-slate-400 hover:text-slate-200'
              }`}
            >
              <span className="font-semibold text-xs">MODE A: Normal</span>
              <span className="text-[10px] text-slate-400">Standard readable transcript</span>
            </button>

            <button
              type="button"
              onClick={() => setAsrMode('verbatim')}
              className={`p-2.5 rounded-lg border text-left flex flex-col gap-1 transition ${
                asrMode === 'verbatim'
                  ? 'border-cyan-400 bg-cyan-950/30 text-cyan-200'
                  : 'border-white/5 bg-slate-900/60 text-slate-400 hover:text-slate-200'
              }`}
            >
              <span className="font-semibold text-xs">MODE C: Verbatim</span>
              <span className="text-[10px] text-slate-400">Preserves fillers, repetitions & pauses</span>
            </button>
          </div>
        </div>

        {/* Translation Options */}
        <div className="flex items-center justify-between p-3 bg-slate-950 rounded-lg border border-white/5">
          <div className="flex flex-col">
            <span className="text-xs text-slate-200 font-medium">Translate to English</span>
            <span className="text-[11px] text-slate-500">Sarvam Translate engine</span>
          </div>
          <input
            type="checkbox"
            checked={autoTranslate}
            onChange={(e) => setAutoTranslate(e.target.checked)}
            className="rounded text-cyan-500 focus:ring-0 w-4 h-4 cursor-pointer"
          />
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 pt-2 border-t border-white/5">
          <button
            onClick={onClose}
            disabled={isUploading}
            className="btn btn-secondary px-4 py-2 text-xs"
          >
            Cancel
          </button>
          <button
            onClick={handleUpload}
            disabled={!file || isUploading}
            className="btn btn-primary px-5 py-2 text-xs flex items-center gap-2 disabled:opacity-50"
          >
            {isUploading ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                <span>Diarizing & Transcribing...</span>
              </>
            ) : (
              <>
                <Check size={14} />
                <span>Process Audio</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
