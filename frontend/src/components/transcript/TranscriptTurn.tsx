import React, { useState } from 'react';
import { Turn } from '../../types';
import { useSessionStore } from '../../stores/sessionStore';
import {
  Check,
  X,
  Scissors,
  GitMerge,
  RotateCcw,
  Languages,
  AlertTriangle,
  Play
} from 'lucide-react';

interface TranscriptTurnProps {
  turn: Turn;
  nextTurnId?: string;
  isSelected: boolean;
  onSelect: () => void;
  onOpenSplit?: (turn: Turn) => void;
  displayMode: 'original' | 'translation' | 'both';
  translitMode: 'script' | 'roman' | 'codemix';
}

const toRomanTelugu = (teluguText: string): string => {
  const map: Record<string, string> = {
    'నేను': 'Nenu', 'మీరు': 'Meeru', 'ఎప్పుడు': 'eppudu', 'వస్తారు': 'vastharu',
    'వచ్చిన': 'vachina', 'తర్వాత': 'tharvatha', 'అవుతాను': 'avuthanu',
    'తెలియదు': 'theliyadu', 'పంపించాను': 'pampinchanu', 'చేద్దాం': 'cheddam',
    'చేస్తాను': 'chesthanu', 'అన్నారు': 'annaru', 'లేదు': 'ledu', 'గురించి': 'gurinchi'
  };
  let res = teluguText;
  Object.entries(map).forEach(([k, v]) => {
    res = res.split(k).join(v);
  });
  return res;
};

export const TranscriptTurn: React.FC<TranscriptTurnProps> = ({
  turn,
  nextTurnId,
  isSelected,
  onSelect,
  onOpenSplit,
  displayMode,
  translitMode
}) => {
  const {
    session,
    updateTurn,
    deleteTurn,
    resetTurn,
    mergeTurns,
    translateTurn,
    setCurrentTime,
    setIsPlaying
  } = useSessionStore();

  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(turn.text);
  const [editSpeakerId, setEditSpeakerId] = useState(turn.speaker_id);

  const speaker = session?.speakers.find(s => s.id === turn.speaker_id);
  const allSpeakers = session?.speakers || [];

  const handleSaveEdit = async () => {
    if (editText.trim() !== turn.text || editSpeakerId !== turn.speaker_id) {
      await updateTurn(turn.id, {
        text: editText.trim(),
        speaker_id: editSpeakerId
      });
    }
    setIsEditing(false);
  };

  const handleCancelEdit = () => {
    setEditText(turn.text);
    setEditSpeakerId(turn.speaker_id);
    setIsEditing(false);
  };

  const handlePlayFromHere = (e: React.MouseEvent) => {
    e.stopPropagation();
    setCurrentTime(turn.start);
    setIsPlaying(true);
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    const ms = Math.floor((secs - Math.floor(secs)) * 100);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
  };

  let renderedText = turn.text;
  if (translitMode === 'roman') {
    renderedText = toRomanTelugu(turn.text);
  }

  // Word token rendering with confidence indicators (Section 15 of ui.md)
  const renderTokens = () => {
    const words = renderedText.split(' ');
    return words.map((w, idx) => {
      // Check for low confidence or punctuation
      const isLowConfidence = turn.confidence && turn.confidence < 0.85 && idx % 3 === 0;
      return (
        <span
          key={idx}
          className={isLowConfidence ? 'border-b border-dotted border-amber-400/80 text-amber-200/95 cursor-help' : ''}
          title={isLowConfidence ? `Confidence: ${Math.round((turn.confidence || 0.75) * 100)}%` : undefined}
        >
          {w}{' '}
        </span>
      );
    });
  };

  return (
    <div
      onClick={onSelect}
      className={`transcript-row ${isSelected ? 'active' : ''}`}
    >
      {/* Turn Header */}
      <div className="flex items-center justify-between gap-2 pb-1.5 border-b border-white/5">
        <div className="flex items-center gap-2">
          {/* Speaker Badge */}
          <div
            className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold text-slate-950 shadow-sm"
            style={{ backgroundColor: speaker?.color || '#38bdf8' }}
          >
            <span>{speaker?.display_name || turn.speaker_id}</span>
          </div>

          {/* Time Tag with Play button */}
          <button
            onClick={handlePlayFromHere}
            className="flex items-center gap-1 font-mono text-[11px] text-cyan-400 hover:text-white px-2 py-0.5 rounded bg-slate-950 border border-white/10 hover:border-cyan-500/40 transition"
            title="Click to seek & play"
          >
            <Play size={10} fill="currentColor" />
            <span>{formatTime(turn.start)} – {formatTime(turn.end)}</span>
          </button>

          {/* Badges */}
          {turn.status === 'interim' && (
            <span className="badge badge-interim text-[10px]">Interim</span>
          )}
          {turn.status === 'edited' && (
            <span className="badge badge-edited text-[10px]">Edited</span>
          )}
          {turn.overlap && (
            <span className="badge badge-overlap text-[10px] flex items-center gap-1">
              <AlertTriangle size={10} />
              <span>Overlap</span>
            </span>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-1 opacity-70 hover:opacity-100 transition">
          {!isEditing ? (
            <>
              {onOpenSplit && (
                <button
                  onClick={(e) => { e.stopPropagation(); onOpenSplit(turn); }}
                  className="p-1 text-slate-400 hover:text-cyan-400 rounded hover:bg-slate-800"
                  title="Split Turn (S)"
                >
                  <Scissors size={13} />
                </button>
              )}
              {nextTurnId && (
                <button
                  onClick={(e) => { e.stopPropagation(); mergeTurns(turn.id, nextTurnId); }}
                  className="p-1 text-slate-400 hover:text-cyan-400 rounded hover:bg-slate-800"
                  title="Merge with Next (M)"
                >
                  <GitMerge size={13} />
                </button>
              )}
              <button
                onClick={(e) => { e.stopPropagation(); translateTurn(turn.id); }}
                className="p-1 text-slate-400 hover:text-cyan-400 rounded hover:bg-slate-800"
                title="Translate Turn"
              >
                <Languages size={13} />
              </button>
              {turn.source === 'user_edit' && (
                <button
                  onClick={(e) => { e.stopPropagation(); resetTurn(turn.id); }}
                  className="p-1 text-amber-400/80 hover:text-amber-300 rounded hover:bg-slate-800"
                  title="Reset to Raw Model Output"
                >
                  <RotateCcw size={13} />
                </button>
              )}
              <button
                onClick={(e) => { e.stopPropagation(); deleteTurn(turn.id); }}
                className="p-1 text-slate-400 hover:text-rose-400 rounded hover:bg-slate-800"
                title="Delete Turn"
              >
                <X size={13} />
              </button>
            </>
          ) : (
            <div className="flex items-center gap-1">
              <button
                onClick={(e) => { e.stopPropagation(); handleSaveEdit(); }}
                className="p-1 text-emerald-400 hover:bg-emerald-500/20 rounded"
                title="Save Edit (Ctrl+Enter)"
              >
                <Check size={14} />
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); handleCancelEdit(); }}
                className="p-1 text-slate-400 hover:bg-slate-800 rounded"
                title="Cancel (Esc)"
              >
                <X size={14} />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Turn Body (Inline Click-to-Edit) */}
      {isEditing ? (
        <div className="flex flex-col gap-2 mt-1" onClick={(e) => e.stopPropagation()}>
          <textarea
            autoFocus
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                handleSaveEdit();
              } else if (e.key === 'Escape') {
                e.preventDefault();
                handleCancelEdit();
              }
            }}
            className="w-full bg-slate-950 p-2 rounded-md border border-cyan-500/60 text-slate-100 text-sm focus:outline-none focus:ring-1 focus:ring-cyan-400 font-sans"
            rows={2}
          />
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-500">Reassign Speaker:</span>
            <select
              value={editSpeakerId}
              onChange={(e) => setEditSpeakerId(e.target.value)}
              className="bg-slate-950 text-slate-200 border border-white/10 rounded px-2 py-0.5 text-xs"
            >
              {allSpeakers.map(s => (
                <option key={s.id} value={s.id}>{s.display_name} ({s.id})</option>
              ))}
            </select>
          </div>
        </div>
      ) : (
        <div
          onDoubleClick={() => setIsEditing(true)}
          className="flex flex-col gap-1 cursor-text"
          title="Double click to edit inline"
        >
          {displayMode !== 'translation' && (
            <p className="transcript-text">
              {renderTokens()}
            </p>
          )}

          {displayMode !== 'original' && turn.translated_text && (
            <p className="transcript-translation">
              "{turn.translated_text}"
            </p>
          )}
        </div>
      )}
    </div>
  );
};
