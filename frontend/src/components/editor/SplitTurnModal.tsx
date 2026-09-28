import React, { useState } from 'react';
import { Turn } from '../../types';
import { useSessionStore } from '../../stores/sessionStore';
import { toast } from '../../stores/toastStore';
import { Scissors, X, Check, Clock } from 'lucide-react';

interface SplitTurnModalProps {
  turn: Turn | null;
  isOpen: boolean;
  onClose: () => void;
}

export const SplitTurnModal: React.FC<SplitTurnModalProps> = ({ turn, isOpen, onClose }) => {
  const { splitTurn } = useSessionStore();
  if (!isOpen || !turn) return null;

  const midPoint = Number(((turn.start + turn.end) / 2).toFixed(2));
  const [splitTime, setSplitTime] = useState<number>(midPoint);

  // Divide words roughly around midpoint for initial recommendation
  const words = turn.text.split(' ');
  const halfIdx = Math.max(1, Math.floor(words.length / 2));
  const [beforeText, setBeforeText] = useState(words.slice(0, halfIdx).join(' '));
  const [afterText, setAfterText] = useState(words.slice(halfIdx).join(' '));

  const handleConfirmSplit = async () => {
    if (!beforeText.trim() || !afterText.trim()) {
      toast.warning('Both split segments must contain text.', 'Split Segment');
      return;
    }
    await splitTurn(turn.id, splitTime, beforeText.trim(), afterText.trim());
    onClose();
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
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-fade-in overflow-y-auto"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="glass-panel-elevated w-full max-w-lg p-5 flex flex-col gap-4 border border-white/10 shadow-2xl my-auto max-h-[90vh] overflow-y-auto"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/5 pb-3">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-cyan-500/20 text-cyan-400">
              <Scissors size={18} />
            </div>
            <div>
              <h3 className="font-semibold text-sm text-slate-100">Split Turn into Two</h3>
              <p className="text-[11px] text-slate-400">Divide audio turn at a timestamp boundary</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-white rounded hover:bg-slate-800">
            <X size={16} />
          </button>
        </div>

        {/* Timestamp Slider */}
        <div className="flex flex-col gap-2 bg-slate-950/80 p-3 rounded-xl border border-white/5">
          <div className="flex justify-between items-center text-xs">
            <span className="text-slate-400 font-medium">Split Timestamp:</span>
            <span className="font-mono text-cyan-400 font-bold bg-slate-900 px-2 py-0.5 rounded border border-white/5">
              {splitTime.toFixed(2)}s
            </span>
          </div>
          <input
            type="range"
            min={turn.start + 0.1}
            max={turn.end - 0.1}
            step={0.05}
            value={splitTime}
            onChange={(e) => setSplitTime(parseFloat(e.target.value))}
            className="w-full accent-cyan-400 cursor-pointer"
          />
          <div className="flex justify-between text-[10px] font-mono text-slate-500">
            <span>Start: {turn.start.toFixed(2)}s</span>
            <span>End: {turn.end.toFixed(2)}s</span>
          </div>
        </div>

        {/* Text Segments */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
          <div className="flex flex-col gap-1.5">
            <label className="text-slate-300 font-medium flex items-center gap-1">
              <span>First Turn ({turn.start.toFixed(2)}s – {splitTime.toFixed(2)}s)</span>
            </label>
            <textarea
              rows={3}
              value={beforeText}
              onChange={(e) => setBeforeText(e.target.value)}
              className="bg-slate-950 p-2.5 rounded-lg border border-white/10 text-slate-200 text-xs focus:outline-none focus:border-cyan-400"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-slate-300 font-medium flex items-center gap-1">
              <span>Second Turn ({splitTime.toFixed(2)}s – {turn.end.toFixed(2)}s)</span>
            </label>
            <textarea
              rows={3}
              value={afterText}
              onChange={(e) => setAfterText(e.target.value)}
              className="bg-slate-950 p-2.5 rounded-lg border border-white/10 text-slate-200 text-xs focus:outline-none focus:border-cyan-400"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 pt-2 border-t border-white/5">
          <button onClick={onClose} className="btn btn-secondary px-3 py-1.5 text-xs">
            Cancel
          </button>
          <button
            onClick={handleConfirmSplit}
            disabled={!beforeText.trim() || !afterText.trim()}
            className="btn btn-primary px-4 py-1.5 text-xs flex items-center gap-1.5 disabled:opacity-50"
          >
            <Check size={14} />
            <span>Apply Split</span>
          </button>
        </div>
      </div>
    </div>
  );
};
