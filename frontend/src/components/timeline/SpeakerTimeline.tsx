import React, { useRef, useEffect, useState, useMemo, useCallback } from 'react';
import { useSessionStore } from '../../stores/sessionStore';
import { toast } from '../../stores/toastStore';
import { Turn, Speaker } from '../../types';
import { AnnotationTrack } from '../annotations/AnnotationTrack';
import {
  Volume2, VolumeX, AlertTriangle, Bookmark,
  ZoomIn, ZoomOut, Maximize2, Minimize2, ChevronRight, ChevronDown,
  Lock, Unlock, Play, Scissors, GitMerge, Trash2, RotateCcw,
  MessageSquare, Headphones, UploadCloud, FileAudio,
  PanelRightClose, PanelRightOpen, Sparkles
} from 'lucide-react';

/* ─── Constants ───────────────────────────────────────────────────────── */
const LABEL_W = 158;
const LANE_H = 46; // Minimum 40-48px per speaker lane (Section 12 of ui.md)
const WAVEFORM_H = 64;
const RULER_H = 26;
const CAPTION_H = 34;
const MIN_ZOOM = 4;
const MAX_ZOOM = 1200;
const SNAP_SEC = 0.12; // Boundary drag snap radius

/* ─── Helper ──────────────────────────────────────────────────────────── */
function formatTimecode(secs: number): string {
  const safe = Math.max(0, secs || 0);
  const h = Math.floor(safe / 3600);
  const m = Math.floor((safe % 3600) / 60);
  const s = Math.floor(safe % 60);
  const cs = Math.floor((safe % 1) * 100);
  const pad = (n: number) => n.toString().padStart(2, '0');
  // Hour field only appears once the recording is long enough to need it, which is
  // how professional editors keep short clips readable.
  return h > 0
    ? `${pad(h)}:${pad(m)}:${pad(s)}.${pad(cs)}`
    : `${pad(m)}:${pad(s)}.${pad(cs)}`;
}

function formatSpeakingTime(secs: number): string {
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

interface SpeakerTimelineProps {
  onOpenUpload?: () => void;
}

/* ─── Component ───────────────────────────────────────────────────────── */
export const SpeakerTimeline: React.FC<SpeakerTimelineProps> = ({ onOpenUpload }) => {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const waveformCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const minimapRef = useRef<HTMLCanvasElement | null>(null);
  const isDraggingPlayhead = useRef(false);

  const {
    session, duration, currentTime, zoomLevel, selectedTurnId,
    activeTool, markers, setCurrentTime, setSelectedTurnId,
    updateTurn, retranscribeTurn, retranscribingTurnId, splitTurn, mergeTurns, setZoomLevel,
    setIsPlaying, isPlaying, addMarker, deleteTurn, resetTurn,
    timelineMode, setTimelineMode, toggleTimelineFocus, toggleTimelineExpand,
    isSidebarOpen, setIsSidebarOpen
  } = useSessionStore();

  const speakers = session?.speakers ?? [];
  const turns = session?.turns ?? [];
  const audioMeta = (session?.metadata as any)?.audio;
  // Prefer the resolution pyramid so zooming in reveals real detail instead of
  // magnifying a fixed coarse envelope; fall back to the legacy single level.
  const peakLevels: number[][] = audioMeta?.peak_levels?.length ? audioMeta.peak_levels : [audioMeta?.peaks ?? []];
  const peaks = peakLevels[0] ?? [];

  const [mutedSpeakers, setMutedSpeakers] = useState<Record<string, boolean>>({});
  const [soloSpeakers, setSoloSpeakers] = useState<Record<string, boolean>>({});
  const [lockedSpeakers, setLockedSpeakers] = useState<Record<string, boolean>>({});
  const [collapsedSpeakers, setCollapsedSpeakers] = useState<Record<string, boolean>>({});
  const [followPlayhead, setFollowPlayhead] = useState(true);
  const [masterMuted, setMasterMuted] = useState(false);
  const [viewport, setViewport] = useState({ start: 0, width: 900 });

  const [draggingBoundary, setDraggingBoundary] = useState<{
    turnId: string; boundary: 'start' | 'end'; initialX: number; initialTime: number; currentTime: number;
  } | null>(null);
  const [hoveredTurnId, setHoveredTurnId] = useState<string | null>(null);

  // Context Menu State
  const [contextMenu, setContextMenu] = useState<{
    x: number; y: number; turnId: string;
  } | null>(null);

  const totalWidth = Math.max(900, (duration || 1) * zoomLevel);
  const cursorX = duration > 0 ? (currentTime / duration) * totalWidth : 0;

  /* ── Effective gain per speaker: solo overrides mute ────────────────── */
  const soloActive = useMemo(() => Object.values(soloSpeakers).some(Boolean), [soloSpeakers]);

  useEffect(() => {
    useSessionStore.getState().setSpeakerGains?.({
      masterMuted,
      soloActive,
      muted: mutedSpeakers,
      solo: soloSpeakers,
    });
  }, [masterMuted, soloActive, mutedSpeakers, soloSpeakers]);

  /* ── Visible viewport, tracked so the waveform canvas stays bounded ─── */
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const read = () => {
      const trackWidth = Math.max(1, el.clientWidth - LABEL_W);
      const start = el.scrollLeft / zoomLevel;
      setViewport({ start, width: trackWidth / zoomLevel });
    };
    read();
    el.addEventListener('scroll', read, { passive: true });
    const observer = new ResizeObserver(read);
    observer.observe(el);
    return () => {
      el.removeEventListener('scroll', read);
      observer.disconnect();
    };
  }, [zoomLevel, totalWidth]);

  /* ── Close context menu on window click ─────────────────────────────── */
  useEffect(() => {
    const handleCloseMenu = () => setContextMenu(null);
    window.addEventListener('click', handleCloseMenu);
    return () => window.removeEventListener('click', handleCloseMenu);
  }, []);

  /* ── Ruler ticks ─────────────────────────────────────────────────────── */
  const rulerTicks = useMemo(() => {
    const totalSecs = Math.ceil(duration || 60);
    let step = 30;
    if (zoomLevel < 20) step = 120;
    else if (zoomLevel < 40) step = 60;
    else if (zoomLevel < 80) step = 30;
    else if (zoomLevel < 130) step = 10;
    else if (zoomLevel < 190) step = 5;
    else step = 1;

    const ticks: Array<{ sec: number; label: string; major: boolean }> = [];
    for (let s = 0; s <= totalSecs; s += step) {
      const mins = Math.floor(s / 60);
      const secs = s % 60;
      const label = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
      ticks.push({ sec: s, label, major: secs === 0 });
    }
    return ticks;
  }, [duration, zoomLevel]);

  /* ── Peak level selection ───────────────────────────────────────────── */
  const activePeaks = useMemo(() => {
    if (!peakLevels.length) return [];
    // One bar per ~2 screen pixels keeps the drawing dense without over-sampling.
    const wanted = Math.max(64, Math.round(totalWidth / 2));
    let best = peakLevels[0];
    for (const level of peakLevels) {
      if (level.length <= wanted) best = level;
    }
    return best;
  }, [peakLevels, totalWidth]);

  /* ── Waveform rendering ─────────────────────────────────────────────── */
  useEffect(() => {
    const canvas = waveformCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const parent = canvas.parentElement;
    const cssWidth = Math.max(1, parent?.clientWidth ?? totalWidth);
    // Backing store is the size of the element, never the length of the recording.
    // A canvas as wide as `totalWidth` overflows the browser's maximum dimension at
    // high zoom and silently stops drawing.
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = Math.round(cssWidth * dpr);
    canvas.height = Math.round(WAVEFORM_H * dpr);
    canvas.style.width = `${cssWidth}px`;
    canvas.style.height = `${WAVEFORM_H}px`;

    const width = canvas.width;
    const height = canvas.height;
    const centerY = height / 2;
    const barH = height - 10 * dpr;
    ctx.clearRect(0, 0, width, height);

    // Time window currently on screen, mapped into canvas pixels.
    const viewStart = viewport.start;
    const viewSpan = viewport.width;
    const scale = width / Math.max(0.001, viewSpan);
    const xForTime = (t: number) => (t - viewStart) * scale;

    // Speaker zone shading, clipped to the visible window.
    const colors = new Map(speakers.map((s) => [s.id, s.color]));
    turns.forEach((turn) => {
      if (turn.end < viewStart || turn.start > viewStart + viewSpan) return;
      const color = colors.get(turn.speaker_id) || '#38bdf8';
      const startX = Math.max(0, xForTime(turn.start));
      const endX = Math.min(width, xForTime(turn.end));
      ctx.fillStyle = `${color}18`;
      ctx.fillRect(startX, 0, Math.max(1, endX - startX), height);
      ctx.fillStyle = color;
      ctx.fillRect(startX, 0, Math.max(1, endX - startX), 2 * dpr);
    });

    // Amplitude bars from the resolution level that matches the zoom.
    const data = activePeaks;
    if (data.length > 0 && viewSpan > 0) {
      const bars = Math.max(1, Math.floor(width / (2 * dpr)));
      for (let i = 0; i < bars; i++) {
        const t0 = viewStart + (i / bars) * viewSpan;
        const t1 = viewStart + ((i + 1) / bars) * viewSpan;
        const i0 = Math.floor((t0 / (duration || 1)) * data.length);
        const i1 = Math.max(i0 + 1, Math.ceil((t1 / (duration || 1)) * data.length));
        let peak = 0;
        for (let k = i0; k < i1 && k < data.length; k++) peak = Math.max(peak, data[k]);
        const h = Math.max(2 * dpr, peak * barH);
        const x = (i / bars) * width;
        ctx.fillStyle = t1 <= currentTime ? '#38bdf8cc' : 'rgba(51,65,85,0.85)';
        ctx.fillRect(x, centerY - h / 2, Math.max(1, width / bars - 1), h);
      }
    } else {
      ctx.strokeStyle = 'rgba(148,163,184,0.35)';
      ctx.beginPath();
      ctx.moveTo(0, centerY);
      ctx.lineTo(width, centerY);
      ctx.stroke();
    }

    ctx.strokeStyle = 'rgba(255,255,255,0.06)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, centerY);
    ctx.lineTo(width, centerY);
    ctx.stroke();
  }, [activePeaks, currentTime, duration, turns, speakers, viewport, totalWidth]);

  /* ── Mini-map rendering ──────────────────────────────────────────────── */
  useEffect(() => {
    const canvas = minimapRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const W = canvas.width;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    // Background
    ctx.fillStyle = '#0a0e18';
    ctx.fillRect(0, 0, W, H);

    // Speaker segments in minimap
    speakers.forEach((spk, si) => {
      const laneY = (si / Math.max(1, speakers.length)) * H;
      const laneH = H / Math.max(1, speakers.length);
      const spkTurns = turns.filter(t => t.speaker_id === spk.id);
      spkTurns.forEach(turn => {
        const x = (turn.start / (duration || 1)) * W;
        const w = Math.max(1, ((turn.end - turn.start) / (duration || 1)) * W);
        ctx.fillStyle = spk.color + 'cc';
        ctx.fillRect(x, laneY + 1, w, laneH - 2);
      });
    });

    // Playhead in minimap
    const ph = (currentTime / (duration || 1)) * W;
    ctx.fillStyle = '#f43f5e';
    ctx.fillRect(ph, 0, 1.5, H);

    // Viewport indicator
    if (scrollRef.current) {
      const scroll = scrollRef.current.scrollLeft;
      const viewW = scrollRef.current.clientWidth - LABEL_W;
      const vpX = (scroll / totalWidth) * W;
      const vpW = Math.max(4, (viewW / totalWidth) * W);
      ctx.strokeStyle = 'rgba(56,189,248,0.9)';
      ctx.lineWidth = 1;
      ctx.strokeRect(vpX + 0.5, 0.5, vpW, H - 1);
      ctx.fillStyle = 'rgba(56,189,248,0.10)';
      ctx.fillRect(vpX, 0, vpW, H);
    }
  }, [totalWidth, currentTime, duration, speakers, turns, zoomLevel, viewport]);

  /* ── Seek helpers ────────────────────────────────────────────────────── */
  const seekToX = useCallback((clientX: number) => {
    if (!scrollRef.current || duration <= 0) return;
    const rect = scrollRef.current.getBoundingClientRect();
    const scrollLeft = scrollRef.current.scrollLeft;
    const trackX = clientX - rect.left + scrollLeft - LABEL_W;
    const clampedX = Math.max(0, Math.min(trackX, totalWidth));
    setCurrentTime((clampedX / totalWidth) * duration);
  }, [duration, totalWidth, setCurrentTime]);

  const handleTimelineMouseDown = (e: React.MouseEvent) => {
    const relX = e.clientX - (scrollRef.current?.getBoundingClientRect().left ?? 0);
    if (relX > LABEL_W && e.button === 0) {
      isDraggingPlayhead.current = true;
      seekToX(e.clientX);
    }
  };

  /* ── Snap a dragged boundary to a nearby segment edge ────────────────── */
  const snapTime = useCallback((time: number, excludeTurnId: string, boundary: 'start' | 'end') => {
    let best = time;
    let bestDelta = SNAP_SEC;
    const consider = (candidate: number) => {
      const delta = Math.abs(candidate - time);
      if (delta < bestDelta) {
        bestDelta = delta;
        best = candidate;
      }
    };
    turns.forEach((turn) => {
      if (turn.id === excludeTurnId) return;
      consider(turn.start);
      consider(turn.end);
    });
    return Math.max(0, Math.min(best, duration || 0));
  }, [turns, duration]);

  /* ── Wheel zoom, anchored on the pointer ────────────────────────────── */
  const handleWheel = useCallback((e: React.WheelEvent) => {
    if (duration <= 0) return;
    // Plain wheel scrolls the timeline; ctrl/cmd + wheel zooms, as in every
    // professional NLE. Horizontal wheels and trackpads pan.
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const el = scrollRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const anchorPx = e.clientX - rect.left - LABEL_W + el.scrollLeft;
      const anchorTime = anchorPx / zoomLevel;
      const factor = e.deltaY < 0 ? 1.18 : 1 / 1.18;
      const next = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoomLevel * factor));
      if (next === zoomLevel) return;
      setZoomLevel(next);
      requestAnimationFrame(() => {
        const current = scrollRef.current;
        if (current) current.scrollLeft = Math.max(0, anchorTime * next - (e.clientX - rect.left - LABEL_W));
      });
      return;
    }
    if (Math.abs(e.deltaX) > Math.abs(e.deltaY) || e.shiftKey) {
      e.preventDefault();
      if (scrollRef.current) scrollRef.current.scrollLeft += e.deltaX || e.deltaY;
    }
  }, [duration, zoomLevel, setZoomLevel]);

  /* ── Global mouse handlers ───────────────────────────────────────────── */
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (isDraggingPlayhead.current) {
        seekToX(e.clientX);
      } else if (draggingBoundary) {
        const deltaX = e.clientX - draggingBoundary.initialX;
        const deltaTime = zoomLevel > 0 ? deltaX / zoomLevel : (duration > 0 ? (deltaX / totalWidth) * duration : 0);
        const rawTargetTime = Math.max(0, Math.min(draggingBoundary.initialTime + deltaTime, duration || 0));
        const turn = turns.find(t => t.id === draggingBoundary.turnId);
        if (turn) {
          if (lockedSpeakers[turn.speaker_id]) return;
          const rounded = Math.round(rawTargetTime * 100) / 100;
          if (draggingBoundary.boundary === 'start' && rounded < turn.end - 0.1) {
            // Snap to neighbouring segment edges so edits meet cleanly.
            const snapped = Math.min(snapTime(rounded, turn.id, 'start'), turn.end - 0.1);
            setDraggingBoundary(prev => prev ? { ...prev, currentTime: snapped } : null);
          } else if (draggingBoundary.boundary === 'end' && rounded > turn.start + 0.1) {
            const snapped = Math.max(snapTime(rounded, turn.id, 'end'), turn.start + 0.1);
            setDraggingBoundary(prev => prev ? { ...prev, currentTime: snapped } : null);
          }
        }
      }
    };
    const handleMouseUp = () => {
      isDraggingPlayhead.current = false;
      if (draggingBoundary) {
        const turn = turns.find(t => t.id === draggingBoundary.turnId);
        if (turn) {
          const finalStart = draggingBoundary.boundary === 'start' ? draggingBoundary.currentTime : turn.start;
          const finalEnd = draggingBoundary.boundary === 'end' ? draggingBoundary.currentTime : turn.end;
          const initial = draggingBoundary.initialTime;
          const current = draggingBoundary.currentTime;

          // If boundary extended or contracted by >= 50ms, re-transcribe the modified section!
          if (Math.abs(current - initial) >= 0.05 && finalEnd > finalStart + 0.05) {
            retranscribeTurn(turn.id, finalStart, finalEnd);
          }
        }
        setDraggingBoundary(null);
      }
    };
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [draggingBoundary, duration, totalWidth, turns, seekToX, lockedSpeakers, retranscribeTurn, snapTime]);

  /* ── Minimap click to seek ───────────────────────────────────────────── */
  const handleMinimapClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    setCurrentTime(ratio * (duration || 0));
    // Also scroll timeline to show that position
    if (scrollRef.current) {
      const targetScroll = ratio * totalWidth - scrollRef.current.clientWidth / 2 + LABEL_W;
      scrollRef.current.scrollLeft = Math.max(0, targetScroll);
    }
  };

  /* ── Auto-scroll playhead into view ──────────────────────────────────── */
  useEffect(() => {
    if (!scrollRef.current || !isPlaying || !followPlayhead) return;
    const viewLeft = scrollRef.current.scrollLeft;
    const viewRight = viewLeft + scrollRef.current.clientWidth - LABEL_W;
    const ph = cursorX;
    if (ph < viewLeft || ph > viewRight - 40) {
      scrollRef.current.scrollLeft = Math.max(0, ph - 80);
    }
  }, [cursorX, isPlaying, followPlayhead]);

  /* ── Fit Entire Timeline (Horizontal duration fitting - Section 15 of ui.md) ── */
  const handleFitTimeline = useCallback(() => {
    if (duration > 0 && scrollRef.current) {
      const viewW = scrollRef.current.clientWidth - LABEL_W - 24;
      if (viewW > 50) {
        const fitZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, Math.floor(viewW / duration)));
        setZoomLevel(fitZoom);
        if (scrollRef.current) scrollRef.current.scrollLeft = 0;
      }
    }
  }, [duration, setZoomLevel]);

  /* ── Fit to Selection (Section 16 of ui.md) ──────────────────────────── */
  const handleFitSelection = useCallback(() => {
    if (!scrollRef.current) return;
    const targetTurn = turns.find(t => t.id === selectedTurnId) || turns[0];
    if (targetTurn && duration > 0) {
      const viewW = scrollRef.current.clientWidth - LABEL_W - 24;
      const turnSpan = Math.max(0.5, targetTurn.end - targetTurn.start);
      const selZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, Math.floor((viewW * 0.70) / turnSpan)));
      setZoomLevel(selZoom);
      setTimeout(() => {
        if (scrollRef.current) {
          const totalW = duration * selZoom;
          const turnStartPx = (targetTurn.start / duration) * totalW;
          scrollRef.current.scrollLeft = Math.max(0, turnStartPx - viewW * 0.15);
        }
      }, 50);
    }
  }, [turns, selectedTurnId, duration, setZoomLevel]);

  /* ── Reset Zoom to 100% (60px/s - Section 14 of ui.md) ──────────────── */
  const handleZoom100 = useCallback(() => {
    setZoomLevel(60);
  }, [setZoomLevel]);

  /* ── Keyboard shortcuts for zoom ─────────────────────────────────────── */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === '+' || e.key === '=') {
        e.preventDefault();
        setZoomLevel(Math.min(MAX_ZOOM, Math.round(zoomLevel * 1.25)));
      } else if (e.key === '-' || e.key === '_') {
        e.preventDefault();
        setZoomLevel(Math.max(MIN_ZOOM, Math.round(zoomLevel / 1.25)));
      } else if (e.key === '0') {
        e.preventDefault();
        handleZoom100();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [zoomLevel, setZoomLevel, handleZoom100]);

  const handleFit = handleFitTimeline;

  // Turn context menu item helper
  const activeTurn = turns.find(t => t.id === contextMenu?.turnId);

  /* ── Render ──────────────────────────────────────────────────────────── */
  return (
    <div className="timeline-viewport" style={{ userSelect: 'none', height: '100%' }}>
      {/* ── Mini controls row / Workspace Toolbar (Section 1, 2, 3, 14, 15, 19, 21) ── */}
      <div style={{
        height: 32, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 8px', background: '#070a12',
        borderBottom: '1px solid var(--border-subtle)', flexShrink: 0
      }}>
        {/* Left: Mode Title + Speaker/Turn Stats */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 10.5, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', letterSpacing: '0.04em' }}>
            TIMELINE WORKSPACE
          </span>
          <span style={{
            fontSize: 9.5, padding: '1px 6px', borderRadius: 99,
            background: timelineMode === 'focus' ? 'rgba(56,189,248,0.2)' : timelineMode === 'expanded' ? 'rgba(245,158,11,0.2)' : 'rgba(255,255,255,0.06)',
            color: timelineMode === 'focus' ? 'var(--accent-cyan)' : timelineMode === 'expanded' ? 'var(--accent-amber)' : 'var(--text-muted)',
            fontWeight: 600, fontFamily: 'var(--font-mono)'
          }}>
            {timelineMode === 'focus' ? 'Focus Mode' : timelineMode === 'expanded' ? 'Expanded' : 'Normal'}
          </span>
          {speakers.length > 0 && (
            <span style={{ fontSize: 10, color: 'var(--text-dim)', marginLeft: 4 }}>
              {speakers.length} speakers · {turns.length} turns
            </span>
          )}
        </div>

        {/* Center/Right: Zoom controls, Fit buttons, Follow Playhead, Mode Switchers */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {/* Follow Playhead Toggle */}
          <button
            onClick={() => setFollowPlayhead(!followPlayhead)}
            className={`tool-btn !px-2 !h-6 text-[10px] ${followPlayhead ? 'active' : ''}`}
            title="Auto-scroll to follow playhead during playback"
          >
            {followPlayhead ? '✓ Follow' : 'Follow'}
          </button>

          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)', padding: '0 4px' }}>
            {formatTimecode(currentTime)}
          </span>

          <div style={{ width: 1, height: 14, background: 'rgba(255,255,255,0.1)', margin: '0 2px' }} />

          {/* Zoom Controls: -, 100%, +, Fit Timeline, Fit Selection */}
          <button
            onClick={() => setZoomLevel(Math.max(MIN_ZOOM, zoomLevel - 15))}
            className="tool-btn !px-1.5 !h-6 text-xs"
            title="Zoom Out (-)"
          >
            <ZoomOut size={11} />
          </button>
          <button
            onClick={handleZoom100}
            className="tool-btn !px-1.5 !h-6 text-[10px] font-mono"
            title="Reset Zoom to 100% (60px/s) — or press 0"
          >
            {zoomLevel}px
          </button>
          <button
            onClick={() => setZoomLevel(Math.min(MAX_ZOOM, zoomLevel + 15))}
            className="tool-btn !px-1.5 !h-6 text-xs"
            title="Zoom In (+). Ctrl+wheel zooms at the pointer."
          >
            <ZoomIn size={11} />
          </button>

          {/* Fit Entire Timeline Button (Section 15) */}
          <button
            onClick={handleFitTimeline}
            className="tool-btn !px-2 !h-6 text-xs"
            title="Fit Timeline — Scale full audio horizontally inside viewport"
          >
            <Maximize2 size={11} className="text-cyan-400" />
            <span className="text-[10px]">Fit Timeline</span>
          </button>

          {/* Fit Selection Button (Section 16) */}
          <button
            onClick={handleFitSelection}
            disabled={!selectedTurnId && turns.length === 0}
            className="tool-btn !px-2 !h-6 text-xs"
            title="Fit Selection — Zoom to active speaker segment"
          >
            <span className="text-[10px]">Fit Sel</span>
          </button>

          <div style={{ width: 1, height: 14, background: 'rgba(255,255,255,0.1)', margin: '0 2px' }} />

          {/* Expand Timeline Button (Section 2) */}
          {timelineMode !== 'focus' && (
            <button
              onClick={toggleTimelineExpand}
              className={`tool-btn !px-2 !h-6 text-xs ${timelineMode === 'expanded' ? 'active' : ''}`}
              title={timelineMode === 'expanded' ? "Compact Timeline" : "Expand Timeline Height"}
            >
              <span className="text-[10px]">{timelineMode === 'expanded' ? '⛶ Compact' : '⛶ Expand'}</span>
            </button>
          )}

          {/* Focus Mode / Maximize Button (Section 3, 8, 9, 21) */}
          <button
            onClick={toggleTimelineFocus}
            className={`tool-btn !px-2.5 !h-6 text-xs ${timelineMode === 'focus' ? 'active !bg-cyan-500/20 !border-cyan-500/40 text-cyan-300' : ''}`}
            title={timelineMode === 'focus' ? "Exit Timeline Focus (Esc)" : "Focus Timeline — Ctrl+Shift+F"}
          >
            {timelineMode === 'focus' ? (
              <>
                <Minimize2 size={11} />
                <span className="text-[10px] font-semibold">Restore</span>
              </>
            ) : (
              <>
                <Maximize2 size={11} />
                <span className="text-[10px] font-semibold">Focus Timeline</span>
              </>
            )}
          </button>

          {/* Right Sidebar Toggle (Section 19 & 20) */}
          <button
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className={`tool-btn !px-2 !h-6 text-xs ${isSidebarOpen ? '' : 'active'}`}
            title={isSidebarOpen ? "Hide Right Sidebar" : "Show Right Sidebar"}
          >
            {isSidebarOpen ? <PanelRightClose size={12} /> : <PanelRightOpen size={12} />}
            <span className="text-[10px]">{isSidebarOpen ? 'Hide' : 'Sidebar'}</span>
          </button>
        </div>
      </div>

      {/* ── Main scrollable timeline container (Synced horizontal & vertical scrolling) ── */}
      <div
        ref={scrollRef}
        onMouseDown={handleTimelineMouseDown}
        onWheel={handleWheel}
        style={{
          overflowX: 'auto',
          overflowY: 'auto',
          position: 'relative',
          flex: '1 1 0',
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0
        }}
      >
        <div style={{ width: `${totalWidth + LABEL_W}px`, position: 'relative', display: 'flex', flexDirection: 'column' }}>

          {/* ── 1. Time Ruler ────────────────────────────────────────────── */}
          <div className="time-ruler" style={{
            display: 'flex', height: `${RULER_H}px`,
            borderBottom: '1px solid rgba(255,255,255,0.08)',
            position: 'sticky', top: 0, zIndex: 30,
            background: '#060910', flexShrink: 0
          }}>
            {/* Corner cell */}
            <div style={{
              width: LABEL_W, minWidth: LABEL_W,
              padding: '0 10px',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              fontSize: 9.5, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)',
              letterSpacing: '0.08em',
              borderRight: '1px solid rgba(255,255,255,0.08)',
              position: 'sticky', left: 0, zIndex: 40, background: '#060910',
              flexShrink: 0
            }}>
              <span>TRACKS</span>
              <span>TIME</span>
            </div>

            {/* Ticks */}
            <div style={{ position: 'relative', flex: 1, height: '100%' }}>
              {rulerTicks.map((tick) => {
                const leftPos = (tick.sec / (duration || 1)) * totalWidth;
                return (
                  <div
                    key={tick.sec}
                    style={{
                      position: 'absolute', left: `${leftPos}px`,
                      top: 0, bottom: 0,
                      borderLeft: `1px solid ${tick.major ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.07)'}`,
                      display: 'flex', flexDirection: 'column', justifyContent: 'flex-end',
                      paddingLeft: 3, paddingBottom: 3,
                      pointerEvents: 'none'
                    }}
                  >
                    <span style={{
                      fontSize: 9.5, fontFamily: 'var(--font-mono)',
                      color: tick.major ? 'rgba(148,163,184,0.9)' : 'rgba(100,116,139,0.7)',
                      letterSpacing: '0.04em', whiteSpace: 'nowrap'
                    }}>
                      {tick.label}
                    </span>
                  </div>
                );
              })}

              {/* Markers */}
              {markers.map((m) => {
                const mLeft = (m.time / (duration || 1)) * totalWidth;
                return (
                  <div
                    key={m.id}
                    style={{
                      position: 'absolute', left: `${mLeft}px`, top: 0, zIndex: 40,
                      transform: 'translateX(-50%)',
                      display: 'flex', alignItems: 'center', gap: 2,
                      background: '#f59e0b', borderRadius: '0 3px 3px 3px',
                      padding: '1px 5px', fontSize: 9, fontWeight: 700,
                      color: '#111', cursor: 'pointer', boxShadow: '0 2px 6px rgba(0,0,0,0.4)',
                      whiteSpace: 'nowrap'
                    }}
                    title={`${m.label} — ${formatTimecode(m.time)}`}
                    onClick={(e) => { e.stopPropagation(); setCurrentTime(m.time); }}
                  >
                    <Bookmark size={9} fill="currentColor" />
                    <span>{m.label}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* ── 2. Master Waveform Track ──────────────────────────────────── */}
          <div style={{
            display: 'flex', height: `${WAVEFORM_H}px`,
            borderBottom: '1px solid rgba(255,255,255,0.07)',
            flexShrink: 0
          }}>
            <div style={{
              width: LABEL_W, minWidth: LABEL_W,
              background: '#090d17',
              borderRight: '1px solid rgba(255,255,255,0.07)',
              padding: '0 8px',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              position: 'sticky', left: 0, zIndex: 20, boxShadow: '4px 0 8px rgba(0,0,0,0.3)',
              flexShrink: 0
            }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 1, overflow: 'hidden' }}>
                <span style={{ fontWeight: 600, color: 'rgba(241,245,249,0.9)', fontSize: 11 }}>
                  Master Audio
                </span>
                <span style={{ fontSize: 9.5, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                  {audioMeta?.sample_rate ? `${(audioMeta.sample_rate / 1000).toFixed(0)} kHz` : '16 kHz'}
                  {audioMeta?.channels ? ` · ${audioMeta.channels === 1 ? 'Mono' : `${audioMeta.channels}ch`}` : ' · Mono'}
                  {typeof audioMeta?.peak_db === 'number'
                    ? ` · ${audioMeta.peak_db.toFixed(1)} dBFS`
                    : ''}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <button
                  onClick={(e) => { e.stopPropagation(); setMasterMuted(!masterMuted); }}
                  style={{
                    color: masterMuted ? '#f43f5e' : 'rgba(100,116,139,0.7)',
                    background: 'none', border: 'none', cursor: 'pointer', padding: 2, borderRadius: 3
                  }}
                  title={masterMuted ? 'Unmute Master' : 'Mute Master Audio'}
                >
                  {masterMuted ? <VolumeX size={11} /> : <Volume2 size={11} />}
                </button>
              </div>
            </div>
            <div style={{ position: 'relative', flex: 1, background: 'rgba(7,9,15,0.6)' }}>
              <canvas
                ref={waveformCanvasRef}
                style={{ display: 'block', height: WAVEFORM_H, width: '100%', cursor: 'crosshair' }}
              />
            </div>
          </div>

          {/* ── 3. Speaker Lanes ──────────────────────────────────────────── */}
          {speakers.length === 0 ? (
            <div className="timeline-empty" style={{
              height: 90, display: 'flex', flexDirection: 'column', alignItems: 'center',
              justifyContent: 'center', gap: 8, padding: 16
            }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                No diarization speakers detected yet — upload audio or start live streaming
              </div>
              {onOpenUpload && (
                <button
                  onClick={onOpenUpload}
                  className="btn btn-primary px-3 py-1 text-xs flex items-center gap-1.5"
                >
                  <UploadCloud size={13} />
                  <span>Upload Audio File</span>
                </button>
              )}
            </div>
          ) : (
            speakers.map((spk) => {
              const speakerTurns = turns.filter((t) => t.speaker_id === spk.id);
              const isMuted = mutedSpeakers[spk.id];
              const isSolo = soloSpeakers[spk.id];
              const isLocked = lockedSpeakers[spk.id];
              const isCollapsed = collapsedSpeakers[spk.id];
              const laneH = isCollapsed ? 22 : LANE_H;

              return (
                <div
                  key={spk.id}
                  style={{
                    display: 'flex',
                    height: laneH + 2,
                    borderBottom: '1px solid rgba(255,255,255,0.04)',
                    flexShrink: 0,
                    transition: 'height 0.15s ease'
                  }}
                >
                  {/* Label column with Mute, Solo, Lock (Section 38 & 39) */}
                  <div style={{
                    width: LABEL_W, minWidth: LABEL_W,
                    background: '#090d17',
                    borderRight: '1px solid rgba(255,255,255,0.07)',
                    padding: '0 6px',
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    position: 'sticky', left: 0, zIndex: 20,
                    boxShadow: '4px 0 8px rgba(0,0,0,0.25)',
                    flexShrink: 0
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4, overflow: 'hidden', flex: 1 }}>
                      {/* Collapse toggle */}
                      <button
                        onClick={() => setCollapsedSpeakers(p => ({ ...p, [spk.id]: !p[spk.id] }))}
                        style={{ color: 'rgba(100,116,139,0.7)', background: 'none', border: 'none', cursor: 'pointer', padding: 0, flexShrink: 0 }}
                      >
                        {isCollapsed ? <ChevronRight size={10} /> : <ChevronDown size={10} />}
                      </button>
                      {/* Speaker colour dot */}
                      <span style={{
                        width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
                        backgroundColor: spk.color,
                        boxShadow: `0 0 5px ${spk.color}88`
                      }} />
                      <span style={{
                        fontWeight: 600, fontSize: 11, color: isMuted ? 'var(--text-muted)' : 'rgba(241,245,249,0.88)',
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'
                      }} title={spk.display_name}>
                        {spk.display_name}
                      </span>
                    </div>

                    {/* Track Controls: [M] [S] [Lock] (Section 38 & 39) */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 2, flexShrink: 0 }}>
                      {/* Mute */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setMutedSpeakers(p => ({ ...p, [spk.id]: !p[spk.id] }));
                        }}
                        style={{
                          width: 16, height: 16, borderRadius: 3, fontSize: 9, fontWeight: 700,
                          background: isMuted ? '#f43f5e' : 'rgba(255,255,255,0.06)',
                          color: isMuted ? '#fff' : 'rgba(148,163,184,0.7)',
                          border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center'
                        }}
                        title={isMuted ? 'Unmute' : 'Mute speaker'}
                      >
                        M
                      </button>

                      {/* Solo */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSoloSpeakers(p => ({ ...p, [spk.id]: !p[spk.id] }));
                        }}
                        style={{
                          width: 16, height: 16, borderRadius: 3, fontSize: 9, fontWeight: 700,
                          background: isSolo ? '#38bdf8' : 'rgba(255,255,255,0.06)',
                          color: isSolo ? '#000' : 'rgba(148,163,184,0.7)',
                          border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center'
                        }}
                        title={isSolo ? 'Disable Solo' : 'Solo speaker'}
                      >
                        S
                      </button>

                      {/* Lock */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setLockedSpeakers(p => ({ ...p, [spk.id]: !p[spk.id] }));
                        }}
                        style={{
                          width: 16, height: 16, borderRadius: 3,
                          background: isLocked ? 'rgba(245,158,11,0.2)' : 'transparent',
                          color: isLocked ? '#f59e0b' : 'rgba(100,116,139,0.5)',
                          border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center'
                        }}
                        title={isLocked ? 'Unlock track' : 'Lock track from edits'}
                      >
                        {isLocked ? <Lock size={9} /> : <Unlock size={9} />}
                      </button>
                    </div>
                  </div>

                  {/* Lane track */}
                  <div style={{ position: 'relative', flex: 1, background: `${spk.color}08` }}>
                    <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: `${spk.color}30` }} />

                    {!isCollapsed && speakerTurns.map((turn) => {
                      const isBeingDragged = draggingBoundary && draggingBoundary.turnId === turn.id;
                      const curStart = isBeingDragged && draggingBoundary.boundary === 'start' ? draggingBoundary.currentTime : turn.start;
                      const curEnd   = isBeingDragged && draggingBoundary.boundary === 'end'   ? draggingBoundary.currentTime : turn.end;
                      const left  = (curStart / (duration || 1)) * totalWidth;
                      const right = (curEnd   / (duration || 1)) * totalWidth;
                      const width = Math.max(16, right - left);
                      const isSelected = selectedTurnId === turn.id;
                      const isHovered  = hoveredTurnId  === turn.id;
                      const isLockedTrack = lockedSpeakers[spk.id];
                      const isRetranscribing = retranscribingTurnId === turn.id;

                      return (
                        <div
                          key={turn.id}
                          onMouseEnter={() => setHoveredTurnId(turn.id)}
                          onMouseLeave={() => setHoveredTurnId(null)}
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedTurnId(turn.id);
                            setCurrentTime(turn.start);
                          }}
                          onContextMenu={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            setSelectedTurnId(turn.id);
                            setContextMenu({ x: e.clientX, y: e.clientY, turnId: turn.id });
                          }}
                          style={{
                            position: 'absolute',
                            left: `${left}px`,
                            width: `${width}px`,
                            height: 34,
                            top: 5,
                            borderRadius: 5,
                            backgroundColor: isSelected
                              ? `${spk.color}55`
                              : isHovered
                              ? `${spk.color}3a`
                              : `${spk.color}28`,
                            border: isRetranscribing
                              ? '1.5px dashed #06b6d4'
                              : `1.5px solid ${isSelected ? '#ffffffdd' : isHovered ? spk.color : `${spk.color}90`}`,
                            display: 'flex', alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '0 6px',
                            cursor: isLockedTrack ? 'default' : 'grab',
                            transition: isBeingDragged ? 'none' : 'background 0.1s, border-color 0.1s',
                            overflow: 'hidden',
                            boxShadow: isRetranscribing
                              ? '0 0 12px rgba(6,182,212,0.6)'
                              : isSelected
                              ? `0 0 0 1px ${spk.color}55, 0 2px 8px rgba(0,0,0,0.4)`
                              : undefined,
                            zIndex: isSelected ? 20 : isHovered ? 15 : 5
                          }}
                          title={`Speaker: ${spk.display_name}\nStart: ${formatTimecode(curStart)}\nEnd: ${formatTimecode(curEnd)}\nDuration: ${formatTimecode(curEnd - curStart)}\n"${turn.text}"`}
                        >
                          {/* Left drag handle */}
                          {!isLockedTrack && (
                            <div
                              onMouseDown={(e) => {
                                e.stopPropagation();
                                setDraggingBoundary({ turnId: turn.id, boundary: 'start', initialX: e.clientX, initialTime: turn.start, currentTime: turn.start });
                              }}
                              className="segment-drag-handle-left"
                            />
                          )}

                          {/* Text label with timecode */}
                          <div style={{
                            display: 'flex', alignItems: 'center', gap: 5,
                            overflow: 'hidden', flex: 1, minWidth: 0
                          }}>
                            {width > 70 && (
                              <span style={{
                                fontSize: 9, fontFamily: 'var(--font-mono)',
                                color: `${spk.color}dd`, flexShrink: 0, fontWeight: 600
                              }}>
                                {formatTimecode(curStart)}
                              </span>
                            )}
                            <span style={{
                              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                              fontSize: 10.5, color: 'rgba(241,245,249,0.92)',
                              fontFamily: 'var(--font-telugu)',
                              fontWeight: 500, flex: 1, minWidth: 0
                            }}>
                              {isRetranscribing ? 'Re-transcribing section...' : turn.text}
                            </span>
                          </div>

                          {/* Badges */}
                          {isRetranscribing && (
                            <span style={{
                              flexShrink: 0, marginLeft: 3,
                              display: 'flex', alignItems: 'center', gap: 2,
                              background: 'rgba(6,182,212,0.85)', borderRadius: 3,
                              padding: '1px 4px', fontSize: 8, fontWeight: 700, color: '#fff'
                            }} className="animate-pulse">
                              <Sparkles size={8} /> RE-TRANSCRIBING
                            </span>
                          )}
                          {!isRetranscribing && turn.overlap && (
                            <span style={{
                              flexShrink: 0, marginLeft: 3,
                              display: 'flex', alignItems: 'center', gap: 2,
                              background: 'rgba(244,63,94,0.85)', borderRadius: 3,
                              padding: '1px 4px', fontSize: 8, fontWeight: 700, color: '#fff'
                            }}>
                              <AlertTriangle size={8} /> OVERLAP
                            </span>
                          )}

                          {/* Right drag handle */}
                          {!isLockedTrack && (
                            <div
                              onMouseDown={(e) => {
                                e.stopPropagation();
                                setDraggingBoundary({ turnId: turn.id, boundary: 'end', initialX: e.clientX, initialTime: turn.end, currentTime: turn.end });
                              }}
                              className="segment-drag-handle-right"
                            />
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })
          )}

          {/* ── 4. Transcript / Caption Track (Section 29 & Section 11) ────────── */}
          {speakers.length > 0 && turns.length > 0 && (
            <div style={{
              display: 'flex',
              height: `${CAPTION_H}px`,
              borderBottom: '1px solid rgba(255,255,255,0.06)',
              background: 'rgba(15,23,42,0.6)',
              flexShrink: 0
            }}>
              {/* Transcript track label */}
              <div style={{
                width: LABEL_W, minWidth: LABEL_W,
                background: '#070a12',
                borderRight: '1px solid rgba(255,255,255,0.07)',
                padding: '0 8px',
                display: 'flex', alignItems: 'center', gap: 6,
                position: 'sticky', left: 0, zIndex: 20,
                boxShadow: '4px 0 8px rgba(0,0,0,0.25)',
                flexShrink: 0
              }}>
                <MessageSquare size={12} style={{ color: '#38bdf8' }} />
                <span style={{ fontSize: 11, fontWeight: 600, color: 'rgba(241,245,249,0.85)' }}>
                  Transcript
                </span>
                <span style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  Captions
                </span>
              </div>

              {/* Transcript blocks lane */}
              <div style={{ position: 'relative', flex: 1, background: 'rgba(56,189,248,0.02)' }}>
                {turns.map((turn) => {
                  const left = (turn.start / (duration || 1)) * totalWidth;
                  const right = (turn.end / (duration || 1)) * totalWidth;
                  const width = Math.max(20, right - left);
                  const isSelected = selectedTurnId === turn.id;
                  const spk = speakers.find(s => s.id === turn.speaker_id);

                  return (
                    <div
                      key={`caption_${turn.id}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedTurnId(turn.id);
                        setCurrentTime(turn.start);
                      }}
                      style={{
                        position: 'absolute',
                        left: `${left}px`,
                        width: `${width}px`,
                        height: 24,
                        top: 4,
                        borderRadius: 4,
                        backgroundColor: isSelected ? 'rgba(56,189,248,0.25)' : 'rgba(30,41,59,0.7)',
                        border: `1px solid ${isSelected ? '#38bdf8' : 'rgba(255,255,255,0.1)'}`,
                        display: 'flex', alignItems: 'center', gap: 4,
                        padding: '0 6px', cursor: 'pointer', overflow: 'hidden',
                        zIndex: isSelected ? 15 : 5
                      }}
                      title={`[${formatTimecode(turn.start)} → ${formatTimecode(turn.end)}] ${spk?.display_name}: "${turn.text}"`}
                    >
                      <span style={{
                        width: 5, height: 5, borderRadius: '50%',
                        backgroundColor: spk?.color || '#38bdf8', flexShrink: 0
                      }} />
                      <span style={{
                        fontSize: 10, fontFamily: 'var(--font-telugu)',
                        color: isSelected ? '#fff' : 'rgba(241,245,249,0.85)',
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'
                      }}>
                        {turn.text}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── 5. Manual annotation lane (Section 41) ───────────────────── */}
          <AnnotationTrack totalWidth={totalWidth} duration={duration} />

          {/* ── 6. Playhead needle (Spans all tracks) ────────────────────── */}
          <div
            style={{ position: 'absolute', left: `${cursorX + LABEL_W}px`, top: 0, bottom: 0, width: 2 }}
            className="playhead-line"
          >
            <div
              className="playhead-handle"
              onMouseDown={(e) => { e.stopPropagation(); isDraggingPlayhead.current = true; }}
              title="Drag playhead"
            />
          </div>
        </div>
      </div>

      {/* ── Right-Click Context Menu (Section 36) ────────────────────────── */}
      {contextMenu && activeTurn && (
        <div
          onClick={(e) => e.stopPropagation()}
          style={{
            position: 'fixed',
            left: Math.min(contextMenu.x, window.innerWidth - 200),
            top: Math.min(contextMenu.y, window.innerHeight - 300),
            width: 190,
            background: '#0c101a',
            border: '1px solid rgba(255,255,255,0.15)',
            borderRadius: 8,
            boxShadow: '0 16px 36px rgba(0,0,0,0.8)',
            padding: 4,
            zIndex: 100,
            display: 'flex',
            flexDirection: 'column',
            gap: 1
          }}
        >
          <div style={{ padding: '4px 8px', fontSize: 10, color: 'var(--text-muted)', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
            Segment: {formatTimecode(activeTurn.start)} – {formatTimecode(activeTurn.end)}
          </div>

          <button
            onClick={() => {
              setCurrentTime(activeTurn.start);
              setIsPlaying(true);
              setContextMenu(null);
            }}
            style={{ textAlign: 'left', padding: '6px 8px', borderRadius: 4, fontSize: 11, color: '#f1f5f9', background: 'transparent', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <Play size={11} className="text-cyan-400" />
            <span>Play From Here</span>
          </button>

          <button
            onClick={() => {
              if (currentTime > activeTurn.start && currentTime < activeTurn.end) {
                splitTurn(activeTurn.id, currentTime, activeTurn.text.slice(0, Math.floor(activeTurn.text.length / 2)), activeTurn.text.slice(Math.floor(activeTurn.text.length / 2)));
              } else {
                toast.warning(`Playhead (${currentTime.toFixed(2)}s) must be inside segment range (${activeTurn.start.toFixed(2)}s – ${activeTurn.end.toFixed(2)}s) to split.`, 'Split Segment');
              }
              setContextMenu(null);
            }}
            style={{ textAlign: 'left', padding: '6px 8px', borderRadius: 4, fontSize: 11, color: '#f1f5f9', background: 'transparent', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <Scissors size={11} className="text-amber-400" />
            <span>Split At Playhead</span>
          </button>

          <button
            onClick={() => {
              addMarker(activeTurn.start, `Review: ${activeTurn.text.slice(0, 15)}`);
              setContextMenu(null);
            }}
            style={{ textAlign: 'left', padding: '6px 8px', borderRadius: 4, fontSize: 11, color: '#f1f5f9', background: 'transparent', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <Bookmark size={11} className="text-emerald-400" />
            <span>Add Marker</span>
          </button>

          {activeTurn.source === 'user_edit' && (
            <button
              onClick={() => {
                resetTurn(activeTurn.id);
                setContextMenu(null);
              }}
              style={{ textAlign: 'left', padding: '6px 8px', borderRadius: 4, fontSize: 11, color: '#f1f5f9', background: 'transparent', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <RotateCcw size={11} className="text-blue-400" />
              <span>Reset to Model Output</span>
            </button>
          )}

          <div style={{ height: 1, background: 'rgba(255,255,255,0.06)', margin: '2px 0' }} />

          <button
            onClick={() => {
              deleteTurn(activeTurn.id);
              setContextMenu(null);
            }}
            style={{ textAlign: 'left', padding: '6px 8px', borderRadius: 4, fontSize: 11, color: '#f43f5e', background: 'transparent', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <Trash2 size={11} />
            <span>Delete Segment</span>
          </button>
        </div>
      )}

      {/* ── Focus Mode Compact Floating Inspector (Section 23 of ui.md) ── */}
      {timelineMode === 'focus' && selectedTurnId && (
        (() => {
          const selTurn = turns.find(t => t.id === selectedTurnId);
          if (!selTurn) return null;
          const selSpk = speakers.find(s => s.id === selTurn.speaker_id);
          return (
            <div
              className="focus-segment-inspector animate-fade-in"
              style={{
                position: 'absolute',
                top: 40,
                right: 14,
                zIndex: 60,
                width: 260,
                background: 'rgba(12, 16, 26, 0.95)',
                backdropFilter: 'blur(10px)',
                border: '1px solid rgba(56, 189, 248, 0.35)',
                borderRadius: 9,
                boxShadow: '0 12px 32px rgba(0,0,0,0.65)',
                padding: '9px 12px',
                display: 'flex',
                flexDirection: 'column',
                gap: 5
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: 4 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: selSpk?.color || '#38bdf8' }} />
                  <span style={{ fontSize: 11, fontWeight: 700, color: '#f1f5f9' }}>
                    {selSpk?.display_name || selTurn.speaker_id}
                  </span>
                  <span style={{ fontSize: 9, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                    SEGMENT
                  </span>
                </div>
                <button
                  onClick={() => setSelectedTurnId(null)}
                  style={{ color: 'var(--text-muted)', background: 'none', border: 'none', cursor: 'pointer', padding: 2, fontSize: 11 }}
                  title="Close Inspector"
                >
                  ✕
                </button>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                <span>{formatTimecode(selTurn.start)} → {formatTimecode(selTurn.end)}</span>
                <span style={{ color: 'var(--accent-cyan)' }}>{(selTurn.end - selTurn.start).toFixed(2)}s</span>
              </div>

              <div style={{
                fontSize: 11, fontFamily: 'var(--font-telugu)', color: 'rgba(241,245,249,0.92)',
                maxHeight: 46, overflow: 'hidden', textOverflow: 'ellipsis',
                background: 'rgba(0,0,0,0.35)', padding: '4px 6px', borderRadius: 4, lineHeight: 1.3
              }}>
                {selTurn.text}
              </div>

              <div style={{ display: 'flex', gap: 4, marginTop: 2 }}>
                <button
                  onClick={() => { setCurrentTime(selTurn.start); setIsPlaying(true); }}
                  className="tool-btn !h-5 !px-2 text-[10px]"
                  title="Play segment"
                >
                  <Play size={9} className="text-cyan-400" /> Play
                </button>
                <button
                  onClick={() => {
                    if (currentTime > selTurn.start && currentTime < selTurn.end) {
                      splitTurn(selTurn.id, currentTime, selTurn.text.slice(0, Math.floor(selTurn.text.length / 2)), selTurn.text.slice(Math.floor(selTurn.text.length / 2)));
                    }
                  }}
                  className="tool-btn !h-5 !px-2 text-[10px]"
                  title="Split at playhead"
                >
                  <Scissors size={9} className="text-amber-400" /> Split
                </button>
                <button
                  onClick={() => deleteTurn(selTurn.id)}
                  className="tool-btn !h-5 !px-2 text-[10px]"
                  title="Delete segment"
                >
                  <Trash2 size={9} className="text-rose-400" /> Delete
                </button>
              </div>
            </div>
          );
        })()
      )}

      {/* ── Mini-map navigator ────────────────────────────────────────── */}
      {speakers.length > 0 && (
        <div style={{
          height: 24, background: '#0a0e18', borderTop: '1px solid rgba(255,255,255,0.06)',
          display: 'flex', alignItems: 'stretch', flexShrink: 0
        }}>
          <div style={{
            width: LABEL_W, minWidth: LABEL_W, flexShrink: 0,
            display: 'flex', alignItems: 'center', paddingLeft: 8,
            borderRight: '1px solid rgba(255,255,255,0.06)'
          }}>
            <span style={{ fontSize: 9, color: 'var(--text-dim)', letterSpacing: '0.05em', fontFamily: 'var(--font-mono)' }}>
              MINIMAP
            </span>
          </div>
          <canvas
            ref={minimapRef}
            width={800}
            height={24}
            style={{ flex: 1, cursor: 'crosshair', display: 'block' }}
            onClick={handleMinimapClick}
            title="Click to navigate"
          />
        </div>
      )}
    </div>
  );
};
