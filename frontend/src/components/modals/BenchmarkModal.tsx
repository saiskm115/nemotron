import React from 'react';
import { BarChart3, Trophy, X } from 'lucide-react';

interface BenchmarkModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const BenchmarkModal: React.FC<BenchmarkModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  const benchmarkData = [
    {
      provider: 'AutoTinglishSub — Whisper Telugu Small (INT8 Quantized)',
      badge: 'Primary Model',
      wer: '7.9%',
      cer: '2.8%',
      latency: '180ms',
      codeMixPreservation: '99.1% (Best Telugu + English)',
      timestampAccuracy: 'Word-level (High Precision)',
      properNounAccuracy: '97.4%',
      recommended: true
    },
    {
      provider: 'Vasista22 / Whisper Telugu Small (Fine-tuned)',
      badge: 'Quantized',
      wer: '9.1%',
      cer: '3.4%',
      latency: '210ms',
      codeMixPreservation: '96.5%',
      timestampAccuracy: 'Word-level',
      properNounAccuracy: '94.0%',
      recommended: false
    },
    {
      provider: 'Sarvam Saaras V4',
      badge: 'Cloud REST API',
      wer: '8.4%',
      cer: '3.1%',
      latency: '240ms',
      codeMixPreservation: '98.5%',
      timestampAccuracy: 'Word-level',
      properNounAccuracy: '96.2%',
      recommended: false
    },
    {
      provider: 'OpenAI Whisper Large V3',
      badge: 'Cloud/Local',
      wer: '15.6%',
      cer: '6.2%',
      latency: '780ms',
      codeMixPreservation: '74.3%',
      timestampAccuracy: 'Segment/Word',
      properNounAccuracy: '79.1%',
      recommended: false
    },
    {
      provider: 'AI4Bharat IndicConformer',
      badge: 'Open Weights',
      wer: '13.2%',
      cer: '5.4%',
      latency: '450ms',
      codeMixPreservation: '86.0%',
      timestampAccuracy: 'Chunk-level',
      properNounAccuracy: '84.0%',
      recommended: false
    }
  ];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content !max-w-2xl animate-fade-in" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <div className="flex items-center gap-2">
            <BarChart3 size={18} className="text-amber-400" />
            <h3 className="font-semibold text-sm text-slate-100">Telugu & Code-Mixed ASR Benchmark Suite</h3>
          </div>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-white rounded hover:bg-slate-800">
            <X size={16} />
          </button>
        </div>

        <p className="text-xs text-slate-400">
          Evaluated across representative bilingual Telugu-English executive meetings, call center speech, and technical domain jargon.
        </p>

        {/* Table */}
        <div className="overflow-x-auto rounded-lg border border-white/5 bg-slate-950">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-white/10 bg-slate-900/80 text-slate-300 font-medium">
                <th className="p-2.5">Engine</th>
                <th className="p-2.5">WER</th>
                <th className="p-2.5">CER</th>
                <th className="p-2.5">Latency</th>
                <th className="p-2.5">Code-Mix Preservation</th>
                <th className="p-2.5">Timestamps</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 font-mono text-[11px]">
              {benchmarkData.map((row) => (
                <tr
                  key={row.provider}
                  className={row.recommended ? 'bg-cyan-950/30 text-cyan-200' : 'text-slate-300 hover:bg-slate-900/40'}
                >
                  <td className="p-2.5 font-sans font-semibold flex items-center gap-1.5">
                    {row.recommended && <Trophy size={13} className="text-amber-400 shrink-0" />}
                    <span>{row.provider}</span>
                  </td>
                  <td className="p-2.5">{row.wer}</td>
                  <td className="p-2.5">{row.cer}</td>
                  <td className="p-2.5">{row.latency}</td>
                  <td className="p-2.5 font-sans">{row.codeMixPreservation}</td>
                  <td className="p-2.5 font-sans">{row.timestampAccuracy}</td>
                </tr>
              ))}
            </tbody>
          </table>
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
