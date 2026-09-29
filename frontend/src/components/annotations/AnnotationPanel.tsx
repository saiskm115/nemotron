import React, { useMemo, useState } from 'react';
import { useSessionStore } from '../../stores/sessionStore';
import { Annotation, AnnotationLabel, ANNOTATION_LABELS } from '../../types';
import { Tag, Trash2, UserCheck, Search } from 'lucide-react';

const COLOR_FOR: Record<AnnotationLabel, string> = Object.fromEntries(
  ANNOTATION_LABELS.map(l => [l.id, l.color])
) as Record<AnnotationLabel, string>;

const LABEL_TEXT: Record<AnnotationLabel, string> = Object.fromEntries(
  ANNOTATION_LABELS.map(l => [l.id, l.label])
) as Record<AnnotationLabel, string>;

function formatTimecode(secs: number): string {
  const m = Math.floor((secs % 3600) / 60);
  const s = Math.floor(secs % 60);
  const cs = Math.floor((secs % 1) * 100);
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `${pad(m)}:${pad(s)}.${pad(cs)}`;
}

/**
 * Reviewer-facing list of every manual label on the recording.
 *
 * Groups by label kind so a pass over "all the errors" or "all the questions" is
 * one click, which is how annotations actually get used in a review cycle.
 */
export const AnnotationPanel: React.FC = () => {
  const { session, annotations, setCurrentTime, selectedAnnotationId, setSelectedAnnotationId,
          removeAnnotation, applyAnnotationToTurns, isAnnotating, setIsAnnotating } = useSessionStore();
  const [filter, setFilter] = useState<AnnotationLabel | 'all'>('all');
  const [query, setQuery] = useState('');

  const speakers = session?.speakers ?? [];

  const speakerName = useMemo(() => {
    const map = new Map<string, string>(speakers.map(s => [s.id, s.display_name]));
    return (id?: string | null): string | undefined => (id ? map.get(id) ?? id : undefined);
  }, [speakers]);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return annotations.filter(a => {
      if (filter !== 'all' && a.label !== filter) return false;
      if (!needle) return true;
      return (a.text || '').toLowerCase().includes(needle);
    });
  }, [annotations, filter, query]);

  const counts = useMemo(() => {
    const tally = new Map<AnnotationLabel, number>();
    annotations.forEach(a => tally.set(a.label, (tally.get(a.label) ?? 0) + 1));
    return tally;
  }, [annotations]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div style={{ padding: 10, display: 'flex', flexDirection: 'column', gap: 8, borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', color: 'var(--text-dim)' }}>
            ANNOTATIONS ({annotations.length})
          </span>
          <button
            onClick={() => setIsAnnotating(!isAnnotating)}
            className="tool-btn !px-2 !h-6 text-[10px]"
            style={isAnnotating ? { borderColor: '#38bdf8', color: '#7dd3fc' } : undefined}
            title="Drag on the annotation lane to draw one"
          >
            <Tag size={10} className="mr-1" /> {isAnnotating ? 'Drawing' : 'Add'}
          </button>
        </div>

        <div style={{ position: 'relative' }}>
          <Search size={11} style={{
            position: 'absolute', left: 7, top: '50%', transform: 'translateY(-50%)',
            color: 'var(--text-muted)', pointerEvents: 'none'
          }} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search annotations"
            style={{
              width: '100%', boxSizing: 'border-box', padding: '4px 8px 4px 24px',
              background: '#0f172a', color: '#e2e8f0', fontSize: 11,
              border: '1px solid rgba(255,255,255,0.12)', borderRadius: 4
            }}
          />
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          <button
            onClick={() => setFilter('all')}
            style={{
              fontSize: 9.5, padding: '2px 6px', borderRadius: 4, cursor: 'pointer',
              border: `1px solid ${filter === 'all' ? '#38bdf8' : 'rgba(255,255,255,0.12)'}`,
              background: filter === 'all' ? 'rgba(56,189,248,0.18)' : 'rgba(255,255,255,0.03)',
              color: filter === 'all' ? '#7dd3fc' : 'rgba(148,163,184,0.85)'
            }}
          >
            All
          </button>
          {ANNOTATION_LABELS.filter(l => counts.get(l.id)).map(l => (
            <button
              key={l.id}
              onClick={() => setFilter(l.id)}
              style={{
                fontSize: 9.5, padding: '2px 6px', borderRadius: 4, cursor: 'pointer',
                border: `1px solid ${filter === l.id ? l.color : 'rgba(255,255,255,0.12)'}`,
                background: filter === l.id ? `${l.color}28` : 'rgba(255,255,255,0.03)',
                color: filter === l.id ? l.color : 'rgba(148,163,184,0.85)',
                display: 'flex', alignItems: 'center', gap: 4
              }}
            >
              <span style={{ width: 6, height: 6, borderRadius: 3, background: l.color }} />
              {l.label} {counts.get(l.id)}
            </button>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        {visible.length === 0 && (
          <div style={{ padding: 24, textAlign: 'center', fontSize: 11, color: 'var(--text-muted)' }}>
            {annotations.length === 0
              ? 'No annotations yet. Press Add, then drag on the annotation lane under the waveform.'
              : 'No annotations match this filter.'}
          </div>
        )}

        {visible.map((a: Annotation) => {
          const color = COLOR_FOR[a.label] ?? '#38bdf8';
          const selected = a.id === selectedAnnotationId;
          return (
            <div
              key={a.id}
              onClick={() => { setSelectedAnnotationId(a.id); setCurrentTime(a.start); }}
              style={{
                padding: '8px 10px', borderBottom: '1px solid rgba(255,255,255,0.05)',
                borderLeft: `3px solid ${color}`,
                background: selected ? `${color}14` : 'transparent',
                cursor: 'pointer'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                <span style={{
                  fontSize: 9, fontWeight: 700, letterSpacing: '0.06em', color,
                  padding: '1px 5px', borderRadius: 3, background: `${color}22`
                }}>
                  {LABEL_TEXT[a.label] ?? a.label}
                </span>
                <span style={{ fontSize: 9.5, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
                  {formatTimecode(a.start)} · {(a.end - a.start).toFixed(2)}s
                </span>
                <div style={{ marginLeft: 'auto', display: 'flex', gap: 3 }}>
                  {a.speaker_id && (
                    <button
                      onClick={(e) => { e.stopPropagation(); applyAnnotationToTurns(a.id); }}
                      title={`Re-assign segments in this region to ${speakerName(a.speaker_id)}`}
                      className="tool-btn !px-1.5 !h-5"
                      style={{ borderColor: 'rgba(56,189,248,0.45)', color: '#7dd3fc' }}
                    >
                      <UserCheck size={10} />
                    </button>
                  )}
                  <button
                    onClick={(e) => { e.stopPropagation(); removeAnnotation(a.id); }}
                    title="Delete annotation"
                    className="tool-btn !px-1.5 !h-5"
                    style={{ borderColor: 'rgba(244,63,94,0.45)', color: '#fb7185' }}
                  >
                    <Trash2 size={10} />
                  </button>
                </div>
              </div>

              {a.speaker_id && (
                <div style={{ fontSize: 9.5, color: '#7dd3fc', marginBottom: 2 }}>
                  → {speakerName(a.speaker_id)}
                </div>
              )}
              {a.text && (
                <div style={{ fontSize: 11, color: 'rgba(226,232,240,0.9)', fontFamily: 'var(--font-telugu)', wordBreak: 'break-word' }}>
                  {a.text}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
