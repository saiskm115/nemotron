import React, { useCallback, useRef, useState } from 'react';
import { useSessionStore } from '../../stores/sessionStore';
import { Annotation, AnnotationLabel, ANNOTATION_LABELS } from '../../types';
import { Tag, Trash2, UserCheck, X } from 'lucide-react';

/* ─── Constants ───────────────────────────────────────────────────────── */
const LANE_H = 30;
const LABEL_W = 158;
const MIN_DRAW_SEC = 0.05;

const COLOR_FOR: Record<AnnotationLabel, string> = Object.fromEntries(
  ANNOTATION_LABELS.map(l => [l.id, l.color])
) as Record<AnnotationLabel, string>;

const LABEL_TEXT: Record<AnnotationLabel, string> = Object.fromEntries(
  ANNOTATION_LABELS.map(l => [l.id, l.label])
) as Record<AnnotationLabel, string>;

function formatTimecode(secs: number): string {
  const safe = Math.max(0, secs || 0);
  const m = Math.floor((safe % 3600) / 60);
  const s = Math.floor(safe % 60);
  const cs = Math.floor((safe % 1) * 100);
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `${pad(m)}:${pad(s)}.${pad(cs)}`;
}

interface AnnotationTrackProps {
  totalWidth: number;
  duration: number;
}

/**
 * The manual-annotation lane.
 *
 * In annotate mode a drag anywhere on this lane draws a region; on release the
 * region is saved and the editor opens on it. This is the only place annotations
 * are created, so the label a reviewer draws is always anchored to a time range
 * they can see and hear, never to a remembered position.
 */
export const AnnotationTrack: React.FC<AnnotationTrackProps> = ({ totalWidth, duration }) => {
  const {
    session, annotations, isAnnotating, setIsAnnotating, selectedAnnotationId, setSelectedAnnotationId,
    addAnnotation, setCurrentTime,
  } = useSessionStore();

  const speakers = session?.speakers ?? [];

  const [draft, setDraft] = useState<{ start: number; end: number } | null>(null);
  const [editing, setEditing] = useState<Annotation | null>(null);
  const [editorPos, setEditorPos] = useState<{ left: number; top: number } | null>(null);
  const [draftText, setDraftText] = useState('');
  const [draftLabel, setDraftLabel] = useState<AnnotationLabel>('note');
  const [draftSpeaker, setDraftSpeaker] = useState<string>('');
  const laneRef = useRef<HTMLDivElement | null>(null);
  const originRef = useRef<number | null>(null);

  const timeAt = useCallback((clientX: number) => {
    const el = laneRef.current;
    if (!el || duration <= 0) return 0;
    const rect = el.getBoundingClientRect();
    const x = clientX - rect.left;
    return Math.max(0, Math.min((x / totalWidth) * duration, duration));
  }, [duration, totalWidth]);

  const onMouseDown = (e: React.MouseEvent) => {
    if (!isAnnotating || e.button !== 0) return;
    e.stopPropagation();
    const t = timeAt(e.clientX);
    originRef.current = t;
    setDraft({ start: t, end: t });
  };

  const onMouseMove = (e: React.MouseEvent) => {
    if (originRef.current === null) return;
    setDraft({ start: originRef.current, end: timeAt(e.clientX) });
  };

  const commit = async () => {
    const origin = originRef.current;
    originRef.current = null;
    setDraft(null);
    if (origin === null) return;

    const start = Math.min(origin, draft?.end ?? origin);
    const end = Math.max(origin, draft?.end ?? origin);
    if (end - start < MIN_DRAW_SEC) {
      // A click rather than a drag: label the point the reviewer is pointing at.
      const created = await addAnnotation({
        start,
        end: Math.min(start + MIN_DRAW_SEC, duration || start + MIN_DRAW_SEC),
        text: '',
        label: draftLabel,
        speaker_id: draftSpeaker || null,
      });
      if (created) openEditor(created);
      return;
    }
    const created = await addAnnotation({
      start,
      end,
      text: draftText,
      label: draftLabel,
      speaker_id: draftSpeaker || null,
    });
    if (created) {
      openEditor(created);
      setDraftText('');
    }
  };

  const openEditor = (annotation: Annotation) => {
    // The timeline content is far wider than the window, so the editor is
    // anchored to the block's real screen position rather than to the content
    // box, and clamped so it never opens off the edge of the viewport.
    const el = laneRef.current;
    if (el) {
      const rect = el.getBoundingClientRect();
      const x = rect.left + (annotation.start / (duration || 1)) * totalWidth;
      const width = 320;
      const left = Math.max(8, Math.min(x, window.innerWidth - width - 8));
      const top = Math.max(8, rect.bottom + 6);
      setEditorPos({ left, top: Math.min(top, window.innerHeight - 320) });
    }
    setEditing(annotation);
    setSelectedAnnotationId(annotation.id);
    setCurrentTime(annotation.start);
    // Load the annotation being opened into the form, otherwise editing a saved
    // label would silently show (and save) the previous one's text and kind.
    setDraftText(annotation.text ?? '');
    setDraftLabel(annotation.label);
    setDraftSpeaker(annotation.speaker_id ?? '');
  };

  const width = (a: { start: number; end: number }) =>
    Math.max(3, ((a.end - a.start) / (duration || 1)) * totalWidth);
  const left = (a: { start: number }) => (a.start / (duration || 1)) * totalWidth;

  return (
    <div style={{ display: 'flex', height: `${LANE_H}px`, borderTop: '1px solid rgba(255,255,255,0.06)', flexShrink: 0 }}>
      {/* Track header */}
      <div style={{
        width: LABEL_W, minWidth: LABEL_W, background: '#090d17',
        borderRight: '1px solid rgba(255,255,255,0.07)',
        display: 'flex', alignItems: 'center', gap: 6, padding: '0 8px',
        position: 'sticky', left: 0, zIndex: 20, boxShadow: '4px 0 8px rgba(0,0,0,0.3)',
        flexShrink: 0
      }}>
        <button
          onClick={(e) => { e.stopPropagation(); setIsAnnotating(!isAnnotating); }}
          title={isAnnotating ? 'Stop annotating' : 'Drag on this lane to draw an annotation'}
          style={{
            display: 'flex', alignItems: 'center', gap: 4, height: 20, padding: '0 7px',
            borderRadius: 4, fontSize: 10, fontWeight: 600, letterSpacing: '0.04em',
            border: `1px solid ${isAnnotating ? '#38bdf8' : 'rgba(255,255,255,0.14)'}`,
            background: isAnnotating ? 'rgba(56,189,248,0.18)' : 'rgba(255,255,255,0.04)',
            color: isAnnotating ? '#7dd3fc' : 'rgba(148,163,184,0.9)',
            cursor: 'pointer', whiteSpace: 'nowrap'
          }}
        >
          <Tag size={10} />
          {isAnnotating ? 'DRAWING' : 'ANNOTATE'}
        </button>
        <span style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          {annotations.length}
        </span>
      </div>

      {/* Drawing surface */}
      <div
        ref={laneRef}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={commit}
        onMouseLeave={commit}
        style={{
          position: 'relative', flex: 1, height: '100%',
          background: isAnnotating
            ? 'repeating-linear-gradient(45deg, rgba(56,189,248,0.06) 0 8px, rgba(56,189,248,0.02) 8px 16px)'
            : 'rgba(255,255,255,0.015)',
          cursor: isAnnotating ? 'crosshair' : 'default',
          overflow: 'hidden'
        }}
      >
        {/* Saved annotations */}
        {annotations.map((a) => {
          const color = COLOR_FOR[a.label] ?? '#38bdf8';
          const selected = a.id === selectedAnnotationId;
          return (
            <div
              key={a.id}
              onClick={(e) => { e.stopPropagation(); openEditor(a); }}
              title={`${LABEL_TEXT[a.label] ?? a.label}: ${a.text || '(no text)'}\n${formatTimecode(a.start)} → ${formatTimecode(a.end)}`}
              style={{
                position: 'absolute', left: `${left(a)}px`, top: 4, height: LANE_H - 9,
                width: `${width(a)}px`, minWidth: 6,
                background: `${color}${selected ? '55' : '30'}`,
                border: `1.5px solid ${color}${selected ? 'ff' : '99'}`,
                borderRadius: 4, boxShadow: selected ? `0 0 8px ${color}66` : 'none',
                display: 'flex', alignItems: 'center', padding: '0 5px', gap: 3,
                overflow: 'hidden', whiteSpace: 'nowrap', cursor: 'pointer',
                fontSize: 9.5, color: '#e2e8f0'
              }}
            >
              <Tag size={8} color={color} style={{ flexShrink: 0 }} />
              {width(a) > 46 && (
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {a.text || LABEL_TEXT[a.label]}
                </span>
              )}
            </div>
          );
        })}

        {/* Region being drawn right now */}
        {draft && Math.abs(draft.end - draft.start) > 0.001 && (
          <div style={{
            position: 'absolute', left: `${left(draft)}px`, top: 4,
            height: LANE_H - 9, width: `${width(draft)}px`,
            background: 'rgba(56,189,248,0.25)', border: '1.5px dashed #38bdf8',
            borderRadius: 4, display: 'flex', alignItems: 'center', padding: '0 5px',
            fontSize: 9.5, fontFamily: 'var(--font-mono)', color: '#bae6fd', pointerEvents: 'none'
          }}>
            {width(draft) > 40 && `(${(draft.end - draft.start).toFixed(2)}s)`}
          </div>
        )}

        {annotations.length === 0 && !draft && !isAnnotating && (
          <span style={{
            position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
            fontSize: 9.5, color: 'var(--text-muted)', pointerEvents: 'none'
          }}>
            No annotations — press ANNOTATE and drag to label a region
          </span>
        )}
      </div>

      {/* Editor popover, anchored to the window rather than the timeline content,
          which is far wider than the viewport at any real zoom level. */}
      {editing && editorPos && (
        <AnnotationEditor
          annotation={editing}
          position={editorPos}
          speakerNames={speakers.map(s => ({ id: s.id, name: s.display_name, color: s.color }))}
          text={draftText}
          label={draftLabel}
          speakerId={draftSpeaker}
          onText={setDraftText}
          onLabel={setDraftLabel}
          onSpeaker={setDraftSpeaker}
          onClose={() => { setEditing(null); setSelectedAnnotationId(null); }}
        />
      )}
    </div>
  );
};

/* ─── Editor popover ──────────────────────────────────────────────────── */
interface AnnotationEditorProps {
  annotation: Annotation;
  position: { left: number; top: number };
  speakerNames: { id: string; name: string; color: string }[];
  text: string;
  label: AnnotationLabel;
  speakerId: string;
  onText: (v: string) => void;
  onLabel: (v: AnnotationLabel) => void;
  onSpeaker: (v: string) => void;
  onClose: () => void;
}

const AnnotationEditor: React.FC<AnnotationEditorProps> = ({
  annotation, position, speakerNames, text, label, speakerId,
  onText, onLabel, onSpeaker, onClose,
}) => {
  const { editAnnotation, removeAnnotation, applyAnnotationToTurns } = useSessionStore();
  const color = COLOR_FOR[label] ?? '#38bdf8';

  return (
    <div
      onClick={(e) => e.stopPropagation()}
      style={{
        position: 'fixed', left: position.left, top: position.top, zIndex: 200, width: 320,
        background: '#0b1220', border: `1px solid ${color}55`, borderRadius: 8,
        boxShadow: '0 12px 40px rgba(0,0,0,0.65)', padding: 12,
        display: 'flex', flexDirection: 'column', gap: 9
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{
          fontSize: 10, fontWeight: 700, letterSpacing: '0.08em',
          color, display: 'flex', alignItems: 'center', gap: 5
        }}>
          <Tag size={11} /> ANNOTATION
        </span>
        <button onClick={onClose} className="tool-btn !px-1.5 !h-5" title="Close">
          <X size={11} />
        </button>
      </div>

      <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
        {formatTimecode(annotation.start)} → {formatTimecode(annotation.end)}
        <span style={{ color: 'var(--text-muted)' }}>
          {'  '}({(annotation.end - annotation.start).toFixed(2)}s)
        </span>
      </div>

      {/* Label kind */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
        {ANNOTATION_LABELS.map((l) => (
          <button
            key={l.id}
            onClick={() => { onLabel(l.id); editAnnotation(annotation.id, { label: l.id }); }}
            title={l.hint}
            style={{
              fontSize: 9.5, padding: '2px 6px', borderRadius: 4, cursor: 'pointer',
              border: `1px solid ${l.id === label ? l.color : 'rgba(255,255,255,0.12)'}`,
              background: l.id === label ? `${l.color}28` : 'rgba(255,255,255,0.03)',
              color: l.id === label ? l.color : 'rgba(148,163,184,0.85)',
              fontWeight: l.id === label ? 700 : 400
            }}
          >
            {l.label}
          </button>
        ))}
      </div>

      {/* Speaker this label is about */}
      <select
        value={speakerId}
        onChange={(e) => {
          onSpeaker(e.target.value);
          editAnnotation(annotation.id, { speaker_id: e.target.value || null });
        }}
        style={{
          background: '#0f172a', color: '#e2e8f0', border: '1px solid rgba(255,255,255,0.12)',
          borderRadius: 4, padding: '4px 6px', fontSize: 11
        }}
      >
        <option value="">— this region (no speaker) —</option>
        {speakerNames.map(s => (
          <option key={s.id} value={s.id}>{s.name}</option>
        ))}
      </select>

      <textarea
        value={text}
        onChange={(e) => onText(e.target.value)}
        onBlur={() => editAnnotation(annotation.id, { text })}
        placeholder="What did you observe here?"
        rows={3}
        style={{
          background: '#0f172a', color: '#e2e8f0', border: '1px solid rgba(255,255,255,0.12)',
          borderRadius: 4, padding: 6, fontSize: 11, resize: 'vertical',
          fontFamily: 'var(--font-telugu)'
        }}
      />

      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <button
          onClick={() => editAnnotation(annotation.id, { text, label, speaker_id: speakerId || null })}
          className="tool-btn !px-2.5 !h-6 text-[10px]"
          style={{ borderColor: `${color}66`, color }}
        >
          Save
        </button>
        {speakerId && (
          <button
            onClick={() => applyAnnotationToTurns(annotation.id)}
            className="tool-btn !px-2.5 !h-6 text-[10px]"
            title="Re-assign every transcript segment inside this region to the speaker above"
            style={{ borderColor: 'rgba(56,189,248,0.5)', color: '#7dd3fc' }}
          >
            <UserCheck size={10} className="mr-1" /> Apply to segments
          </button>
        )}
        <button
          onClick={() => { removeAnnotation(annotation.id); onClose(); }}
          className="tool-btn !px-2 !h-6 ml-auto"
          title="Delete annotation"
          style={{ borderColor: 'rgba(244,63,94,0.5)', color: '#fb7185' }}
        >
          <Trash2 size={10} />
        </button>
      </div>
    </div>
  );
};
