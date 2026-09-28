import React, { useState, useEffect, useRef } from 'react';
import { useSessionStore } from '../../stores/sessionStore';
import { api, UploadProgress } from '../../services/api';
import { toast } from '../../stores/toastStore';
import {
  UploadCloud, FileAudio, Check, AlertOctagon,
  Loader2, X, RefreshCw, Sparkles, Sliders, Users, FileText, Languages
} from 'lucide-react';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSessionCreated?: (session: any) => void;
}

const STAGES = [
  { id: 'uploading', label: 'Audio Upload', desc: 'Streaming audio stream to server', icon: UploadCloud },
  { id: 'preprocessing', label: '16kHz Audio Preprocessing', desc: 'Decoding AAC/AMR/M4A/WAV, resampling, mono normalization & peaks', icon: Sliders },
  { id: 'diarizing', label: 'Nemotron-3 Speaker Diarization', desc: 'Neural speaker segmentation & overlap detection', icon: Users },
  { id: 'transcribing', label: 'Telugu-English ASR', desc: 'AutoTinglish Whisper code-mixed speech recognition', icon: FileText },
  { id: 'aligning', label: 'Alignment & Translation', desc: 'Turn assembly & Sarvam neural translation', icon: Languages }
];

const ALLOWED_AUDIO_EXTS = [
  'wav', 'mp3', 'flac', 'ogg', 'oga', 'opus',
  'm4a', 'aac', 'amr', '3gp', '3gpp',
  'wma', 'webm', 'caf', 'mp4', 'aiff', 'aif'
];
const CALL_RECORDING_EXTS = ['aac', 'm4a', 'amr', '3gp', '3gpp', 'opus'];

export const UploadModal: React.FC<UploadModalProps> = ({ isOpen, onClose, onSessionCreated }) => {
  const { setSession } = useSessionStore();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('Telugu English Executive Meeting');
  const [asrMode, setAsrMode] = useState<'codemix' | 'normal' | 'verbatim'>('codemix');
  const [primaryLang, setPrimaryLang] = useState('unknown');
  const [targetLang, setTargetLang] = useState('en-IN');
  const [autoTranslate, setAutoTranslate] = useState(true);

  // Upload & Progress State
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState<UploadProgress>({
    stage: 'uploading',
    stageIndex: 1,
    percent: 0,
    detail: 'Initializing audio pipeline...'
  });
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [errorStage, setErrorStage] = useState<string | null>(null);

  const timerRef = useRef<any>(null);

  useEffect(() => {
    if (!isOpen) {
      if (timerRef.current) clearInterval(timerRef.current);
      setElapsedSeconds(0);
      setIsUploading(false);
      setError(null);
      setErrorStage(null);
      return;
    }
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isUploading) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isUploading, onClose]);

  // Elapsed timer tracker during processing
  useEffect(() => {
    if (isUploading) {
      setElapsedSeconds(0);
      timerRef.current = setInterval(() => {
        setElapsedSeconds((sec) => sec + 1);
      }, 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isUploading]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      const ext = selected.name.split('.').pop()?.toLowerCase() || '';

      if (ext && !ALLOWED_AUDIO_EXTS.includes(ext)) {
        toast.error(
          `Format ".${ext}" is not supported. Please select a call recording or audio file (AAC, M4A, AMR, 3GP, OPUS, WAV, MP3, OGG, FLAC, WMA).`,
          'Unsupported Format'
        );
        return;
      }

      setFile(selected);
      setError(null);
      setErrorStage(null);
      if (!title || title === 'Telugu English Executive Meeting') {
        setTitle(selected.name.replace(/\.[^/.]+$/, ''));
      }

      const isCallFormat = CALL_RECORDING_EXTS.includes(ext);
      toast.info(
        `Selected ${isCallFormat ? 'call recording' : 'audio file'}: ${selected.name} (${(selected.size / (1024 * 1024)).toFixed(2)} MB)`,
        isCallFormat ? 'Call Recording Loaded' : 'File Loaded'
      );
    }
  };

  const handleUpload = async () => {
    if (!file) {
      toast.warning('Please choose an audio file to process.', 'No File Selected');
      return;
    }

    // Confirmation Toast Dialogue before initiating processing
    const confirmed = await toast.ask(
      `Process "${file.name}" (${(file.size / (1024 * 1024)).toFixed(2)} MB) with Nemotron-3 Diarization and AutoTinglish ASR?`,
      {
        title: 'Start Diarization Pipeline?',
        confirmLabel: 'Start Processing',
        cancelLabel: 'Review Settings',
        confirmVariant: 'primary'
      }
    );

    if (!confirmed) {
      toast.info('Upload paused. You can review settings or select another file.', 'Upload Cancelled');
      return;
    }

    executePipelineUpload();
  };

  const executePipelineUpload = async () => {
    if (!file) return;

    setIsUploading(true);
    setError(null);
    setErrorStage(null);
    setProgress({
      stage: 'uploading',
      stageIndex: 1,
      percent: 5,
      detail: 'Connecting to backend and preparing audio payload...'
    });

    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', title);
    formData.append('asr_mode', asrMode);
    formData.append('primary_language', primaryLang);
    formData.append('target_language', targetLang);
    formData.append('auto_translate', autoTranslate ? 'true' : 'false');

    try {
      const session = await api.uploadAudioWithProgress(formData, (p) => {
        setProgress(p);
      });

      // Brief pause to display 100% completion before closing
      setTimeout(() => {
        setSession(session);
        setIsUploading(false);
        toast.success('Audio successfully processed and diarized!', 'Pipeline Complete');
        if (onSessionCreated) onSessionCreated(session);
        else onClose();
      }, 500);
    } catch (err: any) {
      const msg = err.message || 'Audio processing failed';
      setError(msg);
      setErrorStage(progress.detail || 'Nemotron-3 Diarization Pipeline');
      setIsUploading(false);
      toast.error(msg, 'Diarization Failed');
    }
  };

  const formatElapsed = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}s`;
  };

  if (!isOpen) return null;

  return (
    <div
      onClick={isUploading ? undefined : onClose}
      role="dialog"
      aria-modal="true"
      className="modal-overlay fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 overflow-y-auto"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className={`glass-panel-elevated w-full max-w-lg p-6 flex flex-col gap-4 border border-white/10 animate-fade-in my-auto max-h-[92vh] overflow-y-auto ${
          error ? 'border-rose-500/50 animate-error-glow' : ''
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/5 pb-3">
          <div className="flex items-center gap-2">
            <UploadCloud size={20} className={error ? 'text-rose-400' : 'text-cyan-400'} />
            <h3 className="font-semibold text-base text-slate-100">
              {isUploading ? 'Diarization Pipeline in Progress' : 'Upload Audio for Diarization & ASR'}
            </h3>
          </div>
          {!isUploading && (
            <button
              onClick={onClose}
              className="p-1 text-slate-400 hover:text-white rounded hover:bg-slate-800 transition"
              aria-label="Close dialog"
            >
              <X size={16} />
            </button>
          )}
        </div>

        {/* ── Active Progression View ────────────────────────────────────────── */}
        {isUploading && (
          <div className="flex flex-col gap-5 py-2">
            {/* Visual Equalizer / Sound Wave Graphic */}
            <div className="flex items-center justify-between p-4 rounded-xl bg-slate-950/70 border border-cyan-500/20 shadow-inner">
              <div className="flex flex-col">
                <span className="text-xs font-semibold text-cyan-300 flex items-center gap-1.5">
                  <Sparkles size={14} className="text-cyan-400" />
                  Neural Processing Active
                </span>
                <span className="text-[11px] text-slate-400 mt-0.5">
                  {title || 'Audio Stream'}
                </span>
              </div>

              {/* Dynamic Equalizer Spectrum Bars */}
              <div className="flex items-end gap-1 h-9 px-3">
                {[0.2, 0.6, 0.9, 0.4, 0.8, 1.0, 0.5, 0.9, 0.7, 0.3, 0.85, 0.5, 0.95, 0.4, 0.7, 0.2].map((factor, i) => (
                  <div
                    key={i}
                    style={{
                      width: 3.5,
                      borderRadius: 2,
                      background: 'linear-gradient(180deg, #38bdf8 0%, #6366f1 100%)',
                      animation: 'eqBounce 0.9s infinite ease-in-out',
                      animationDelay: `${(i * 0.055).toFixed(2)}s`,
                      height: `${Math.max(18, factor * 100)}%`
                    }}
                  />
                ))}
              </div>

              <div className="flex flex-col items-end">
                <span className="text-[10px] uppercase font-mono tracking-wider text-slate-500">Elapsed</span>
                <span className="text-xs font-mono font-bold text-cyan-400">{formatElapsed(elapsedSeconds)}</span>
              </div>
            </div>

            {/* Numerical Percentage Counter & Progression Bar */}
            <div className="flex flex-col gap-2">
              <div className="flex items-baseline justify-between">
                <span className="text-xs font-medium text-slate-300">
                  {progress.stage === 'complete' ? 'Completed' : 'Overall Progress'}
                </span>
                <span
                  data-testid="upload-progress-percent"
                  className="text-3xl font-extrabold font-mono text-cyan-400 drop-shadow-[0_0_12px_rgba(56,189,248,0.5)]"
                >
                  {progress.percent}%
                </span>
              </div>

              {/* High-Tech Progress Bar Track */}
              <div className="w-full h-3 bg-slate-950 rounded-full border border-white/10 overflow-hidden relative shadow-inner">
                <div
                  style={{
                    width: `${progress.percent}%`,
                    background: progress.percent === 100
                      ? 'linear-gradient(90deg, #10b981, #059669)'
                      : 'linear-gradient(90deg, #06b6d4 0%, #3b82f6 50%, #8b5cf6 100%)'
                  }}
                  className="h-full rounded-full transition-all duration-300 ease-out relative"
                >
                  {/* Shimmer Light Sweep */}
                  <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-shimmer" />
                </div>
              </div>

              {/* Live Status Text */}
              <div className="flex items-center gap-2 text-xs text-slate-300 mt-1">
                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
                <span className="font-medium text-slate-200">{progress.detail}</span>
              </div>
            </div>

            {/* 5-Stage Step Tracker */}
            <div className="flex flex-col gap-2 pt-2 border-t border-white/5">
              <span className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">
                Pipeline Stages
              </span>
              <div className="flex flex-col gap-2">
                {STAGES.map((stg, idx) => {
                  const stageNum = idx + 1;
                  const isDone = progress.percent === 100 || progress.stageIndex > stageNum;
                  const isActive = !isDone && progress.stageIndex === stageNum;
                  const StgIcon = stg.icon;

                  return (
                    <div
                      key={stg.id}
                      className={`flex items-center gap-3 p-2 rounded-lg border transition ${
                        isActive
                          ? 'border-cyan-500/40 bg-cyan-950/20 text-cyan-200 animate-pulse-badge'
                          : isDone
                          ? 'border-emerald-500/20 bg-emerald-950/10 text-slate-300'
                          : 'border-white/5 bg-slate-950/40 text-slate-500'
                      }`}
                    >
                      <div
                        className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 text-xs ${
                          isDone
                            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                            : isActive
                            ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/50'
                            : 'bg-slate-800 text-slate-500'
                        }`}
                      >
                        {isDone ? <Check size={13} className="text-emerald-400" /> : <StgIcon size={12} />}
                      </div>

                      <div className="flex flex-col flex-1 min-w-0">
                        <span className={`text-xs font-medium ${isActive ? 'text-cyan-200' : isDone ? 'text-slate-200' : 'text-slate-400'}`}>
                          {stg.label}
                        </span>
                        <span className="text-[10px] text-slate-400 truncate">{stg.desc}</span>
                      </div>

                      <div className="shrink-0 text-[11px] font-mono">
                        {isDone && <span className="text-emerald-400 font-semibold">Done</span>}
                        {isActive && (
                          <div className="flex items-center gap-1 text-cyan-400">
                            <Loader2 size={12} className="animate-spin" />
                            <span>Active</span>
                          </div>
                        )}
                        {!isDone && !isActive && <span className="text-slate-600">Pending</span>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* ── Failure View with Animated Shake & Diagnostics ──────────────────── */}
        {error && !isUploading && (
          <div className="p-4 bg-rose-500/10 border border-rose-500/40 rounded-xl text-rose-300 text-xs flex flex-col gap-3 animate-error-shake">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-rose-500/20 text-rose-400 border border-rose-500/30 shrink-0">
                <AlertOctagon size={24} />
              </div>
              <div className="flex flex-col gap-1 flex-1">
                <span className="font-semibold text-rose-200 text-sm">Diarization Pipeline Failed</span>
                <span className="text-rose-300/90 leading-relaxed">{error}</span>
                {errorStage && (
                  <span className="text-[11px] text-rose-400/80 font-mono mt-0.5">
                    Stage: {errorStage}
                  </span>
                )}
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-rose-500/20">
              <button
                onClick={() => {
                  setError(null);
                  setErrorStage(null);
                }}
                className="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 text-xs border border-white/10 transition"
              >
                Choose Another File
              </button>
              <button
                onClick={executePipelineUpload}
                className="px-3.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-semibold text-xs flex items-center gap-1.5 shadow transition"
              >
                <RefreshCw size={12} />
                <span>Retry Diarization</span>
              </button>
            </div>
          </div>
        )}

        {/* ── Regular File Selection & Config Form (when not uploading) ───────── */}
        {!isUploading && !error && (
          <>
            {/* File Drag Area */}
            <label className="border-2 border-dashed border-white/15 hover:border-cyan-500/50 rounded-xl p-5 flex flex-col items-center justify-center gap-2 cursor-pointer bg-slate-950/50 transition">
              <FileAudio size={36} className={file ? 'text-cyan-400' : 'text-slate-500'} />
              <span className="text-xs font-semibold text-slate-200 text-center">
                {file ? file.name : 'Click to browse or drop Call Recordings & Audio'}
              </span>
              <span className="text-[11px] text-slate-400 text-center">
                {file ? `${(file.size / (1024 * 1024)).toFixed(2)} MB • Ready to process` : 'Standardizes any telephony or voice format to 16kHz mono'}
              </span>
              
              {/* Call Recording Format Badges */}
              <div className="flex flex-wrap justify-center gap-1.5 mt-1">
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-950/70 text-emerald-300 border border-emerald-500/30 font-semibold tracking-wide">AAC</span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-950/70 text-emerald-300 border border-emerald-500/30 font-semibold tracking-wide">M4A</span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-950/70 text-emerald-300 border border-emerald-500/30 font-semibold tracking-wide">AMR / 3GP</span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-950/70 text-emerald-300 border border-emerald-500/30 font-semibold tracking-wide">OPUS</span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-950/70 text-cyan-300 border border-cyan-500/30 font-semibold tracking-wide">WAV</span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-950/70 text-cyan-300 border border-cyan-500/30 font-semibold tracking-wide">MP3</span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-950/70 text-cyan-300 border border-cyan-500/30 font-semibold tracking-wide">OGG</span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-800/80 text-slate-300 border border-slate-700 font-semibold tracking-wide">FLAC / WMA</span>
              </div>

              <input
                type="file"
                accept="audio/*,video/*,.aac,.m4a,.mp4,.amr,.3gp,.3gpp,.opus,.wav,.mp3,.flac,.ogg,.oga,.wma,.webm,.caf,.aiff,.aif"
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

            {/* Primary Spoken Language Selector */}
            <div className="flex flex-col gap-1">
              <div className="flex justify-between items-center">
                <label className="text-xs text-slate-300 font-medium">Primary Spoken Language:</label>
                <span className="text-[10px] text-cyan-400 bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-500/30">
                  {primaryLang === 'unknown' ? 'Auto-Detect + Fallback' : primaryLang.toUpperCase()}
                </span>
              </div>
              <select
                value={primaryLang}
                onChange={(e) => setPrimaryLang(e.target.value)}
                className="bg-slate-950 p-2 rounded-lg border border-cyan-500/40 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-cyan-400"
              >
                <option value="unknown">Auto-Detect (English, Telugu, Hindi with Smart Fallback)</option>
                <option value="en">English (Indian / US / UK)</option>
                <option value="te">Telugu / Tinglish (Code-mixed)</option>
                <option value="hi">Hindi / Hinglish</option>
              </select>
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

            {/* ASR Mode Selection */}
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
          </>
        )}

        {/* Footer */}
        {!isUploading && !error && (
          <div className="flex justify-end gap-2 pt-2 border-t border-white/5">
            <button
              onClick={onClose}
              className="btn btn-secondary px-4 py-2 text-xs"
            >
              Cancel
            </button>
            <button
              onClick={handleUpload}
              disabled={!file}
              className="btn btn-primary px-5 py-2 text-xs flex items-center gap-2 disabled:opacity-50"
            >
              <Check size={14} />
              <span>Process Audio</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
