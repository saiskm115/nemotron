import React, { useState } from 'react';
import { useSessionStore } from '../../stores/sessionStore';
import { api } from '../../services/api';
import { toast } from '../../stores/toastStore';
import { Download, FileText, Code, FileSpreadsheet, X, Check } from 'lucide-react';

interface ExportMenuProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ExportMenu: React.FC<ExportMenuProps> = ({ isOpen, onClose }) => {
  const { session } = useSessionStore();
  const [includeTranslation, setIncludeTranslation] = useState(true);

  if (!isOpen || !session) return null;

  const exportFormats = [
    { id: 'srt', label: 'SRT Subtitles', ext: '.srt', desc: 'Standard SubRip subtitle file with speaker tags', icon: FileText },
    { id: 'vtt', label: 'WebVTT', ext: '.vtt', desc: 'HTML5 WebVTT caption format', icon: FileText },
    { id: 'txt', label: 'Plain Text', ext: '.txt', desc: 'Readable meeting minutes format', icon: FileText },
    { id: 'json', label: 'Structured JSON', ext: '.json', desc: 'Complete canonical metadata, tokens & turns', icon: Code },
    { id: 'docx', label: 'Word Document', ext: '.docx', desc: 'Formatted Microsoft Word meeting transcript', icon: FileSpreadsheet }
  ] as const;

  const handleDownload = async (format: 'srt' | 'vtt' | 'txt' | 'json' | 'docx') => {
    if (!session) {
      toast.error('No active session available to export.', 'Export Error');
      return;
    }
    const formatObj = exportFormats.find(f => f.id === format);
    toast.confirm(
      `Generate and download ${formatObj?.label || format.toUpperCase()} (${formatObj?.ext || format})?`,
      {
        title: 'Export File?',
        confirmLabel: 'Download',
        cancelLabel: 'Cancel',
        confirmVariant: 'primary',
        onConfirm: async () => {
          try {
            const url = api.getExportUrl(session.id, format, includeTranslation);
            const res = await fetch(url);
            if (!res.ok) {
              throw new Error(`Server returned error: ${res.status} ${res.statusText}`);
            }
            const blob = await res.blob();
            const blobUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = blobUrl;
            a.download = `${session.title || 'transcript'}.${format}`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(blobUrl);
            toast.success(`${format.toUpperCase()} export downloaded successfully!`, 'Export Completed');
          } catch (err: any) {
            toast.error(err.message || 'Failed to download export file', 'Export Failed');
          }
        },
        onCancel: () => {
          toast.info('Export cancelled', 'Cancelled');
        }
      }
    );
  };

  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return (
    <div
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 overflow-y-auto"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="glass-panel-elevated w-full max-w-md p-5 flex flex-col gap-4 border border-white/10 animate-fade-in my-auto max-h-[90vh] overflow-y-auto"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/5 pb-3">
          <div className="flex items-center gap-2">
            <Download size={18} className="text-cyan-400" />
            <h3 className="font-semibold text-base text-slate-100">Export Transcript</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-white rounded hover:bg-slate-800"
          >
            <X size={16} />
          </button>
        </div>

        {/* Translation Toggle */}
        <label className="flex items-center gap-2 p-2.5 bg-slate-950 rounded-lg border border-white/5 cursor-pointer text-xs text-slate-200">
          <input
            type="checkbox"
            checked={includeTranslation}
            onChange={(e) => setIncludeTranslation(e.target.checked)}
            className="rounded border-slate-700 text-cyan-500 focus:ring-0"
          />
          <span>Include English translations in exported file</span>
        </label>

        {/* Format List */}
        <div className="flex flex-col gap-2">
          {exportFormats.map(fmt => {
            const Icon = fmt.icon;
            return (
              <div
                key={fmt.id}
                className="flex items-center justify-between p-3 rounded-lg bg-slate-900/60 hover:bg-slate-800/80 border border-white/5 transition"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-slate-950 text-cyan-400 border border-white/5">
                    <Icon size={16} />
                  </div>
                  <div>
                    <h4 className="text-xs font-semibold text-slate-100">{fmt.label}</h4>
                    <p className="text-[11px] text-slate-400">{fmt.desc}</p>
                  </div>
                </div>

                <button
                  onClick={() => handleDownload(fmt.id)}
                  className="btn btn-primary px-3 py-1.5 text-xs flex items-center gap-1.5"
                >
                  <Download size={13} />
                  <span>Download</span>
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
