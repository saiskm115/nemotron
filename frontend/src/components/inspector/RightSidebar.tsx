import React, { useState } from 'react';
import { useSessionStore } from '../../stores/sessionStore';
import { toast } from '../../stores/toastStore';
import {
  Users, Sliders, Clock, Edit2, Check, X,
  GitMerge, AlertTriangle, Languages, RotateCcw,
  Hash, Mic2, Activity, ChevronRight, Trash2,
  PieChart, BarChart2, Tag
} from 'lucide-react';
import { AnnotationPanel } from '../annotations/AnnotationPanel';

export const RightSidebar: React.FC = () => {
  const {
    session, selectedTurnId, isSidebarOpen, sidebarTab, setSidebarTab,
    updateSpeaker, mergeSpeakers, updateTurn, translateTurn, setCurrentTime, resetTurn,
    annotations
  } = useSessionStore();

  const [editingSpkId, setEditingSpkId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [editColor, setEditColor] = useState('');
  const [isMerging, setIsMerging] = useState(false);
  const [sourceId, setSourceId] = useState('');
  const [targetId, setTargetId] = useState('');

  const speakers = session?.speakers ?? [];
  const turns = session?.turns ?? [];
  const totalDuration = session?.duration ?? 0;
  const selectedTurn = turns.find(t => t.id === selectedTurnId);
  const selectedSpeaker = speakers.find(s => s.id === selectedTurn?.speaker_id);

  if (!isSidebarOpen) return null;

  const handleStartEdit = (spk: any) => {
    setEditingSpkId(spk.id);
    setEditName(spk.display_name);
    setEditColor(spk.color);
  };
  const handleSaveEdit = async (spkId: string) => {
    if (!editName.trim()) {
      toast.warning('Speaker display name cannot be empty.', 'Speaker Edit');
      return;
    }
    await updateSpeaker(spkId, { display_name: editName.trim(), color: editColor });
    setEditingSpkId(null);
  };
  const handlePerformMerge = async () => {
    if (!sourceId || !targetId) {
      toast.warning('Please select both a source and target speaker.', 'Merge Speakers');
      return;
    }
    if (sourceId === targetId) {
      toast.warning('Cannot merge a speaker into itself.', 'Merge Speakers');
      return;
    }
    const srcSpk = speakers.find(s => s.id === sourceId)?.display_name || sourceId;
    const tgtSpk = speakers.find(s => s.id === targetId)?.display_name || targetId;
    toast.confirm(
      `Merge all speech turns from "${srcSpk}" into "${tgtSpk}"?`,
      {
        title: 'Merge Speakers?',
        confirmLabel: 'Merge Speakers',
        cancelLabel: 'Cancel',
        confirmVariant: 'primary',
        onConfirm: async () => {
          await mergeSpeakers(sourceId, targetId);
          setIsMerging(false);
          setSourceId('');
          setTargetId('');
        },
        onCancel: () => {
          toast.info('Speaker merge cancelled', 'Cancelled');
        }
      }
    );
  };

  const fmt = (s: number) => {
    const m = Math.floor(s / 60), sec = Math.floor(s % 60);
    return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
  };
  const fmtTC = (s: number) => {
    const m = Math.floor(s / 60), sec = Math.floor(s % 60);
    const cs = Math.floor((s % 1) * 100);
    return `${m.toString().padStart(2,'0')}:${sec.toString().padStart(2,'0')}.${cs.toString().padStart(2,'0')}`;
  };

  // Speaker stats
  const totalSpeakingTime = speakers.reduce((a, s) => a + (s.total_speaking_time ?? 0), 0);

  const COLORS = ['#38bdf8','#f43f5e','#10b981','#a855f7','#f59e0b','#06b6d4','#ec4899','#84cc16'];

  return (
    <aside className="inspector-sidebar">
      {/* ── Tabs ────────────────────────────────────────────────────── */}
      <div style={{
        display: 'flex', alignItems: 'center',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
        background: '#090d17', padding: '0 6px', gap: 2, flexShrink: 0
      }}>
        {[
          { key: 'speakers', icon: <Users size={12} />, label: `Speakers (${speakers.length})` },
          { key: 'annotations', icon: <Tag size={12} />, label: `Labels (${annotations.length})` },
          { key: 'properties', icon: <Sliders size={12} />, label: 'Inspector' },
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setSidebarTab(tab.key as any)}
            style={{
              display: 'flex', alignItems: 'center', gap: 5,
              padding: '8px 10px',
              fontSize: 11.5, fontWeight: 500,
              color: sidebarTab === tab.key ? '#38bdf8' : 'rgba(148,163,184,0.7)',
              background: 'none', border: 'none', cursor: 'pointer',
              borderBottom: sidebarTab === tab.key ? '2px solid #38bdf8' : '2px solid transparent',
              marginBottom: -1, transition: 'color 0.13s'
            }}
          >
            {tab.icon}
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* ── Tab: Manual annotations (Section 41) ──────────────────────── */}
      {sidebarTab === 'annotations' && (
        <div style={{ flex: 1, minHeight: 0, display: 'flex' }}>
          <AnnotationPanel />
        </div>
      )}

      {/* ── Tab: Speakers ─────────────────────────────────────────────── */}
      {sidebarTab === 'speakers' && (
        <div style={{ flex: 1, overflowY: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>

          {/* Merge panel trigger */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600 }}>
              Diarized Voices
            </span>
            <button
              onClick={() => setIsMerging(p => !p)}
              className="btn btn-secondary !py-0.5"
              style={{ fontSize: 11, gap: 4, color: '#7dd3fc' }}
            >
              <GitMerge size={11} />
              <span>Merge</span>
            </button>
          </div>

          {/* Merge UI */}
          {isMerging && (
            <div
              className="animate-fade-in"
              style={{
                padding: 12, background: 'rgba(56,189,248,0.05)',
                border: '1px solid rgba(56,189,248,0.2)', borderRadius: 10,
                display: 'flex', flexDirection: 'column', gap: 8
              }}
            >
              <span style={{ fontSize: 11, color: 'rgba(241,245,249,0.8)', fontWeight: 500 }}>
                Merge speaker identity:
              </span>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {[
                  { label: 'Source (will be merged away)', val: sourceId, set: setSourceId },
                  { label: 'Target (will absorb source)',  val: targetId, set: setTargetId },
                ].map(f => (
                  <div key={f.label} style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                    <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{f.label}</span>
                    <select
                      value={f.val}
                      onChange={e => f.set(e.target.value)}
                      style={{ padding: '4px 8px', fontSize: 11.5, borderRadius: 6 }}
                    >
                      <option value="">Select speaker…</option>
                      {speakers.map(s => (
                        <option key={s.id} value={s.id}>{s.display_name} ({s.id})</option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 6 }}>
                <button onClick={() => setIsMerging(false)} className="btn btn-secondary !py-0.5" style={{ fontSize: 11 }}>
                  Cancel
                </button>
                <button
                  disabled={!sourceId || !targetId || sourceId === targetId}
                  onClick={handlePerformMerge}
                  className="btn btn-primary !py-0.5"
                  style={{ fontSize: 11 }}
                >
                  Confirm Merge
                </button>
              </div>
            </div>
          )}

          {/* Speaker cards */}
          {speakers.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '24px 12px', color: 'var(--text-muted)', fontSize: 12 }}>
              <Mic2 size={28} style={{ margin: '0 auto 8px', opacity: 0.3 }} />
              <div>No speakers detected</div>
              <div style={{ fontSize: 10.5, marginTop: 4, color: 'var(--text-dim)' }}>Upload audio to begin diarization</div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
              {speakers.map((spk) => {
                const isEdit = editingSpkId === spk.id;
                const pct = totalSpeakingTime > 0
                  ? Math.round((spk.total_speaking_time / totalSpeakingTime) * 100)
                  : 0;
                const spkTurns = turns.filter(t => t.speaker_id === spk.id);

                return (
                  <div
                    key={spk.id}
                    style={{
                      background: 'rgba(9,13,23,0.8)',
                      border: `1px solid ${spk.color}28`,
                      borderRadius: 10, overflow: 'hidden',
                      transition: 'border-color 0.13s'
                    }}
                  >
                    {/* Card header */}
                    <div style={{
                      padding: '9px 11px',
                      background: `linear-gradient(90deg, ${spk.color}12 0%, transparent 100%)`,
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 7, overflow: 'hidden', flex: 1 }}>
                        {isEdit ? (
                          <input
                            type="color"
                            value={editColor}
                            onChange={e => setEditColor(e.target.value)}
                            style={{ width: 22, height: 22, padding: 0, border: 'none', borderRadius: 4, cursor: 'pointer', background: 'transparent', flexShrink: 0 }}
                          />
                        ) : (
                          <span style={{
                            width: 10, height: 10, borderRadius: '50%', flexShrink: 0,
                            backgroundColor: spk.color, boxShadow: `0 0 7px ${spk.color}88`
                          }} />
                        )}

                        {isEdit ? (
                          <input
                            type="text"
                            value={editName}
                            onChange={e => setEditName(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && handleSaveEdit(spk.id)}
                            style={{
                              flex: 1, padding: '3px 8px', fontSize: 12, borderRadius: 5,
                              border: '1px solid rgba(56,189,248,0.5)', background: '#0a0e18',
                              color: '#f1f5f9'
                            }}
                            autoFocus
                          />
                        ) : (
                          <span style={{
                            fontWeight: 600, fontSize: 12.5,
                            color: 'rgba(241,245,249,0.9)',
                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'
                          }}>
                            {spk.display_name}
                          </span>
                        )}
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: 3, flexShrink: 0 }}>
                        {isEdit ? (
                          <>
                            <button onClick={() => handleSaveEdit(spk.id)}
                              style={{ padding: 4, borderRadius: 4, background: 'rgba(16,185,129,0.15)', border: 'none', cursor: 'pointer', color: '#34d399', display: 'flex' }}>
                              <Check size={12} />
                            </button>
                            <button onClick={() => setEditingSpkId(null)}
                              style={{ padding: 4, borderRadius: 4, background: 'transparent', border: 'none', cursor: 'pointer', color: 'rgba(148,163,184,0.6)', display: 'flex' }}>
                              <X size={12} />
                            </button>
                          </>
                        ) : (
                          <button
                            onClick={() => handleStartEdit(spk)}
                            style={{ padding: 4, borderRadius: 4, background: 'transparent', border: 'none', cursor: 'pointer', color: 'rgba(148,163,184,0.5)', display: 'flex' }}
                            title="Rename / recolor"
                          >
                            <Edit2 size={11} />
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Stats bar */}
                    <div style={{ padding: '6px 11px 8px', display: 'flex', flexDirection: 'column', gap: 5 }}>
                      {/* Speaking time bar */}
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 2 }}>
                        <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{fmt(spk.total_speaking_time ?? 0)} spoken</span>
                        <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: spk.color }}>{pct}%</span>
                      </div>
                      <div className="progress-bar-track">
                        <div className="progress-bar-fill" style={{ width: `${pct}%`, background: spk.color }} />
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 2 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, color: 'var(--text-muted)' }}>
                          <Hash size={10} style={{ color: spk.color, opacity: 0.7 }} />
                          <span>{spk.turn_count ?? spkTurns.length} turns</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                          <Clock size={10} style={{ opacity: 0.7 }} />
                          <span>{spk.id}</span>
                        </div>
                      </div>
                    </div>

                    {/* Color presets (show only in edit mode) */}
                    {isEdit && (
                      <div style={{ padding: '0 11px 9px', display: 'flex', alignItems: 'center', gap: 5 }}>
                        <span style={{ fontSize: 10, color: 'var(--text-muted)', marginRight: 2 }}>Presets:</span>
                        {COLORS.map(c => (
                          <button
                            key={c}
                            onClick={() => setEditColor(c)}
                            style={{
                              width: 14, height: 14, borderRadius: '50%',
                              background: c, border: editColor === c ? '2px solid #fff' : '2px solid transparent',
                              cursor: 'pointer', flexShrink: 0
                            }}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Overall stats */}
          {speakers.length > 0 && (
            <div style={{
              marginTop: 4, padding: 10,
              background: 'rgba(56,189,248,0.04)', borderRadius: 10,
              border: '1px solid rgba(56,189,248,0.1)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                <BarChart2 size={12} style={{ color: '#38bdf8' }} />
                <span style={{ fontSize: 10.5, fontWeight: 600, color: 'rgba(241,245,249,0.7)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Session Overview
                </span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                {[
                  { label: 'Total turns', val: turns.length },
                  { label: 'Speakers', val: speakers.length },
                  { label: 'Duration', val: fmt(totalDuration) },
                  { label: 'Talking time', val: fmt(totalSpeakingTime) },
                ].map(s => (
                  <div key={s.label} style={{
                    padding: '6px 8px', background: 'rgba(0,0,0,0.3)', borderRadius: 7,
                    border: '1px solid rgba(255,255,255,0.05)'
                  }}>
                    <div style={{ fontSize: 9.5, color: 'var(--text-muted)', marginBottom: 2 }}>{s.label}</div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: 'rgba(241,245,249,0.85)', fontFamily: 'var(--font-mono)' }}>{s.val}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Tab: Inspector ──────────────────────────────────────────────── */}
      {sidebarTab === 'properties' && (
        <div style={{ flex: 1, overflowY: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {selectedTurn ? (
            <>
              {/* Turn ID */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600 }}>
                  Turn Properties
                </span>
                <span style={{
                  fontSize: 9.5, fontFamily: 'var(--font-mono)', color: 'rgba(56,189,248,0.7)',
                  background: 'rgba(56,189,248,0.07)', padding: '1px 6px', borderRadius: 4,
                  border: '1px solid rgba(56,189,248,0.15)'
                }}>
                  {selectedTurn.id.slice(0, 12)}…
                </span>
              </div>

              {/* Speaker attribution */}
              <div style={{ background: '#0c1020', borderRadius: 10, border: '1px solid rgba(255,255,255,0.07)', overflow: 'hidden' }}>
                <div style={{ padding: '8px 11px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                  <span style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Speaker</span>
                </div>
                <div style={{ padding: '9px 11px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                    <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: selectedSpeaker?.color ?? '#38bdf8', flexShrink: 0, boxShadow: `0 0 5px ${selectedSpeaker?.color ?? '#38bdf8'}66` }} />
                    <span style={{ fontWeight: 600, fontSize: 12.5, color: 'rgba(241,245,249,0.9)' }}>
                      {selectedSpeaker?.display_name ?? selectedTurn.speaker_id}
                    </span>
                  </div>
                  <select
                    value={selectedTurn.speaker_id}
                    onChange={e => updateTurn(selectedTurn.id, { speaker_id: e.target.value })}
                    style={{ padding: '3px 6px', fontSize: 11, borderRadius: 6 }}
                    title="Reassign speaker"
                  >
                    {speakers.map(s => (
                      <option key={s.id} value={s.id}>{s.display_name}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Timestamps */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 7 }}>
                {[
                  { label: 'Start', val: fmtTC(selectedTurn.start), action: () => setCurrentTime(selectedTurn.start) },
                  { label: 'End',   val: fmtTC(selectedTurn.end),   action: () => setCurrentTime(selectedTurn.end) },
                ].map(f => (
                  <button
                    key={f.label}
                    onClick={f.action}
                    style={{
                      padding: '7px 9px', background: '#080c16',
                      border: '1px solid rgba(255,255,255,0.07)',
                      borderRadius: 8, textAlign: 'left', cursor: 'pointer',
                      transition: 'border-color 0.13s'
                    }}
                    title={`Seek to ${f.label}`}
                    onMouseEnter={e => (e.currentTarget.style.borderColor = 'rgba(56,189,248,0.35)')}
                    onMouseLeave={e => (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.07)')}
                  >
                    <div style={{ fontSize: 9.5, color: 'var(--text-muted)', marginBottom: 3 }}>{f.label} Timestamp</div>
                    <div style={{ fontSize: 12.5, fontFamily: 'var(--font-mono)', color: '#38bdf8', fontWeight: 600 }}>{f.val}</div>
                  </button>
                ))}
              </div>

              {/* Stats row */}
              <div style={{
                background: '#080c16', borderRadius: 9, border: '1px solid rgba(255,255,255,0.06)',
                padding: '8px 11px', display: 'flex', flexDirection: 'column', gap: 6
              }}>
                {[
                  { label: 'Duration', val: `${(selectedTurn.end - selectedTurn.start).toFixed(2)}s` },
                  {
                    label: 'Confidence',
                    val: selectedTurn.confidence
                      ? `${Math.round(selectedTurn.confidence * 100)}%`
                      : '—',
                    color: selectedTurn.confidence
                      ? (selectedTurn.confidence >= 0.9 ? '#34d399' : selectedTurn.confidence >= 0.75 ? '#fcd34d' : '#f87171')
                      : undefined
                  },
                  { label: 'Status', val: selectedTurn.status?.toUpperCase() ?? '—' },
                  { label: 'Source', val: selectedTurn.source ?? 'model' },
                ].map(r => (
                  <div key={r.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11.5 }}>
                    <span style={{ color: 'var(--text-muted)' }}>{r.label}</span>
                    <span style={{
                      fontFamily: 'var(--font-mono)', color: r.color ?? 'rgba(241,245,249,0.8)',
                      fontWeight: 600
                    }}>{r.val}</span>
                  </div>
                ))}

                {/* Duration progress bar */}
                <div>
                  <div className="progress-bar-track" style={{ marginTop: 2 }}>
                    <div className="progress-bar-fill" style={{
                      width: `${Math.min(100, ((selectedTurn.end - selectedTurn.start) / (totalDuration || 1)) * 100 * 10)}%`
                    }} />
                  </div>
                </div>
              </div>

              {/* Overlap warning */}
              {selectedTurn.overlap && (
                <div style={{
                  padding: '9px 11px', background: 'rgba(244,63,94,0.08)',
                  border: '1px solid rgba(244,63,94,0.25)', borderRadius: 9,
                  display: 'flex', alignItems: 'flex-start', gap: 7
                }}>
                  <AlertTriangle size={14} style={{ color: '#fb7185', flexShrink: 0, marginTop: 1 }} />
                  <div>
                    <div style={{ fontSize: 11.5, fontWeight: 600, color: '#fda4af', marginBottom: 2 }}>
                      Overlapping / Barge-in Speech
                    </div>
                    <div style={{ fontSize: 10.5, color: 'rgba(253,164,175,0.7)' }}>
                      Multiple speakers were active simultaneously during this turn.
                    </div>
                  </div>
                </div>
              )}

              {/* Translation */}
              {selectedTurn.translated_text && (
                <div style={{
                  padding: '9px 11px', background: 'rgba(56,189,248,0.05)',
                  border: '1px solid rgba(56,189,248,0.13)', borderRadius: 9
                }}>
                  <div style={{ fontSize: 9.5, color: 'rgba(56,189,248,0.6)', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    Translation
                  </div>
                  <p style={{ fontSize: 12.5, color: '#7dd3fc', fontStyle: 'italic', lineHeight: 1.55 }}>
                    "{selectedTurn.translated_text}"
                  </p>
                </div>
              )}

              {/* Action buttons */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginTop: 2 }}>
                <button
                  onClick={() => {
                    toast.confirm(
                      'Translate this speech turn into English using Sarvam Neural Translation?',
                      {
                        title: 'Translate Turn?',
                        confirmLabel: 'Translate',
                        cancelLabel: 'Cancel',
                        confirmVariant: 'primary',
                        onConfirm: async () => {
                          await translateTurn(selectedTurn.id);
                        },
                        onCancel: () => {
                          toast.info('Translation cancelled', 'Cancelled');
                        }
                      }
                    );
                  }}
                  className="btn btn-secondary"
                  style={{ fontSize: 11.5, justifyContent: 'flex-start', gap: 7 }}
                >
                  <Languages size={12} style={{ color: '#38bdf8' }} />
                  Translate this turn
                </button>
                {selectedTurn.source === 'user_edit' && (
                  <button
                    onClick={() => {
                      toast.confirm(
                        'Revert manual edits and restore original model transcript for this segment?',
                        {
                          title: 'Reset Segment?',
                          confirmLabel: 'Revert',
                          cancelLabel: 'Keep Edits',
                          confirmVariant: 'warning',
                          onConfirm: async () => {
                            await resetTurn(selectedTurn.id);
                          },
                          onCancel: () => {
                            toast.info('Revert cancelled', 'Cancelled');
                          }
                        }
                      );
                    }}
                    className="btn btn-secondary"
                    style={{ fontSize: 11.5, justifyContent: 'flex-start', gap: 7 }}
                  >
                    <RotateCcw size={12} style={{ color: '#f59e0b' }} />
                    Reset to model output
                  </button>
                )}
              </div>
            </>
          ) : (
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              justifyContent: 'center', padding: '40px 16px', textAlign: 'center', gap: 10
            }}>
              <div style={{
                width: 44, height: 44, borderRadius: 12,
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.08)',
                display: 'flex', alignItems: 'center', justifyContent: 'center'
              }}>
                <Sliders size={22} style={{ color: 'rgba(148,163,184,0.3)' }} />
              </div>
              <div style={{ fontSize: 12.5, fontWeight: 500, color: 'rgba(148,163,184,0.5)' }}>
                Nothing selected
              </div>
              <div style={{ fontSize: 11, color: 'rgba(100,116,139,0.6)', lineHeight: 1.55 }}>
                Click a segment on the timeline or a row in the transcript to inspect its properties.
              </div>
            </div>
          )}
        </div>
      )}
    </aside>
  );
};
