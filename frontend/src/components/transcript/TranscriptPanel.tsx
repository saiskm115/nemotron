import React, { useState, useEffect } from 'react';
import { useSessionStore } from '../../stores/sessionStore';
import { TranscriptTurn } from './TranscriptTurn';
import { SplitTurnModal } from '../editor/SplitTurnModal';
import { Turn } from '../../types';
import { FileAudio, Mic, UploadCloud } from 'lucide-react';

interface TranscriptPanelProps {
  onOpenUpload?: () => void;
}

export const TranscriptPanel: React.FC<TranscriptPanelProps> = ({ onOpenUpload }) => {
  const {
    session,
    selectedTurnId,
    searchQuery,
    setSelectedTurnId,
    undo,
    redo,
    mergeTurns,
    displayMode,
    translitMode,
    isRecordingLive,
    setIsRecordingLive
  } = useSessionStore();

  const [turnToSplit, setTurnToSplit] = useState<Turn | null>(null);
  const turns = session?.turns || [];

  // Keyboard shortcuts (Ctrl+Z, Ctrl+Shift+Z, S for split, M for merge)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes((e.target as HTMLElement).tagName)) return;

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
        e.preventDefault();
        if (e.shiftKey) redo();
        else undo();
      } else if (e.key.toLowerCase() === 's' && selectedTurnId) {
        const t = turns.find(item => item.id === selectedTurnId);
        if (t) {
          e.preventDefault();
          setTurnToSplit(t);
        }
      } else if (e.key.toLowerCase() === 'm' && selectedTurnId) {
        const curIdx = turns.findIndex(item => item.id === selectedTurnId);
        if (curIdx >= 0 && curIdx < turns.length - 1) {
          e.preventDefault();
          mergeTurns(turns[curIdx].id, turns[curIdx + 1].id);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedTurnId, turns]);

  // Filter turns by search query
  const filteredTurns = turns.filter(turn => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    const textMatch = turn.text.toLowerCase().includes(q);
    const transMatch = turn.translated_text?.toLowerCase().includes(q);
    const spk = session?.speakers.find(s => s.id === turn.speaker_id);
    const spkMatch = spk?.display_name.toLowerCase().includes(q);
    return textMatch || transMatch || spkMatch;
  });

  return (
    <div className="transcript-viewport">
      {filteredTurns.length > 0 ? (
        filteredTurns.map((turn, idx) => (
          <TranscriptTurn
            key={turn.id}
            turn={turn}
            nextTurnId={idx < filteredTurns.length - 1 ? filteredTurns[idx + 1].id : undefined}
            isSelected={selectedTurnId === turn.id}
            onSelect={() => setSelectedTurnId(turn.id)}
            onOpenSplit={(t) => setTurnToSplit(t)}
            displayMode={displayMode}
            translitMode={translitMode}
          />
        ))
      ) : (
        /* Professional Empty State (Section 41 of ui.md) */
        <div className="flex-1 flex flex-col items-center justify-center p-12 text-center text-slate-400 gap-3 border border-dashed border-white/10 rounded-xl my-6">
          <div className="w-12 h-12 rounded-full bg-slate-900 border border-white/10 flex items-center justify-center text-cyan-400 shadow-inner">
            <FileAudio size={24} />
          </div>
          <div className="flex flex-col gap-1 max-w-sm">
            <h4 className="font-semibold text-slate-200 text-sm">No transcript yet</h4>
            <p className="text-xs text-slate-500">
              Upload an audio/video recording or start a live streaming session to generate speaker-attributed Telugu + English transcripts.
            </p>
          </div>
          <div className="flex items-center gap-2 pt-2">
            {onOpenUpload && (
              <button
                onClick={onOpenUpload}
                className="btn btn-primary px-3 py-1.5 text-xs flex items-center gap-1.5"
              >
                <UploadCloud size={14} />
                <span>Upload Audio</span>
              </button>
            )}
            <button
              onClick={() => setIsRecordingLive(!isRecordingLive)}
              className="btn btn-secondary px-3 py-1.5 text-xs flex items-center gap-1.5 text-rose-300"
            >
              <Mic size={14} />
              <span>{isRecordingLive ? 'Stop Live Mic' : 'Start Live Mic'}</span>
            </button>
          </div>
        </div>
      )}

      {/* Split Turn Modal */}
      <SplitTurnModal
        turn={turnToSplit}
        isOpen={Boolean(turnToSplit)}
        onClose={() => setTurnToSplit(null)}
      />
    </div>
  );
};
