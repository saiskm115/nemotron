import React, { useRef, useEffect, useState, useMemo } from 'react';
import { useSessionStore } from '../../stores/sessionStore';
import { Turn, Speaker } from '../../types';
import {
  Volume2,
  VolumeX,
  AlertTriangle,
  Layers,
  Sparkles,
  Scissors,
  Bookmark
} from 'lucide-react';

export const SpeakerTimeline: React.FC = () => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const waveformCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const isDraggingPlayhead = useRef(false);

  const {
    session,
    duration,
    currentTime,
    zoomLevel,
    selectedTurnId,
    activeTool,
    markers,
    setCurrentTime,
    setSelectedTurnId,
    updateTurn,
    splitTurn,
    mergeTurns
  } = useSessionStore();

  const speakers = session?.speakers || [];
  const turns = session?.turns || [];
  const peaks = session?.metadata?.audio?.peaks || [];

  // Mute / Solo track states
  const [mutedSpeakers, setMutedSpeakers] = useState<Record<string, boolean>>({});
  const [soloSpeaker, setSoloSpeaker] = useState<string | null>(null);

  // Dragging boundary state for micro-adjusting start / end
  const [draggingBoundary, setDraggingBoundary] = useState<{
    turnId: string;
    boundary: 'start' | 'end';
    initialX: number;
    initialTime: number;
  } | null>(null);

  // Total width of the timeline canvas based on duration and zoom
  const totalWidth = Math.max(900, (duration || 1) * zoomLevel);
  const cursorX = duration > 0 ? (currentTime / duration) * totalWidth : 0;

  // 1. Draw Waveform Track
  useEffect(() => {
    const canvas = waveformCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = totalWidth;
    const height = 64;

    canvas.width = width;
    canvas.height = height;

    ctx.clearRect(0, 0, width, height);

    // Center baseline
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, height / 2);
    ctx.lineTo(width, height / 2);
    ctx.stroke();

    // Speaker background color zones underneath waveform
    turns.forEach((turn) => {
      const spk = speakers.find((s) => s.id === turn.speaker_id);
      const startX = (turn.start / (duration || 1)) * width;
      const endX = (turn.end / (duration || 1)) * width;
      const segWidth = Math.max(2, endX - startX);

      ctx.fillStyle = spk?.color ? `${spk.color}15` : 'rgba(56, 189, 248, 0.08)';
      ctx.fillRect(startX, 0, segWidth, height);

      // Top color indicator
      ctx.fillStyle = spk?.color || '#38bdf8';
      ctx.fillRect(startX, 0, segWidth, 2);
    });

    // Draw amplitude peak bars
    const numBars = Math.max(300, Math.floor(width / 3));
    const barWidth = width / numBars;
    const centerY = height / 2;

    for (let i = 0; i < numBars; i++) {
      const peakIdx = peaks.length > 0 ? Math.floor((i / numBars) * peaks.length) : 0;
      const peakVal = peaks.length > 0 ? peaks[peakIdx] : Math.sin(i * 0.12) * 0.45 + 0.25;
      const barHeight = Math.max(3, peakVal * (height - 12));
      const x = i * barWidth;

      const timeAtBar = (i / numBars) * (duration || 1);
      const isPlayed = timeAtBar <= currentTime;

      ctx.fillStyle = isPlayed ? '#38bdf8' : '#334155';
      ctx.fillRect(x, centerY - barHeight / 2, Math.max(1.2, barWidth - 1), barHeight);
    }
  }, [totalWidth, peaks, currentTime, duration, turns, speakers]);

  // 2. Playhead Scrubbing & Boundary Dragging Listeners
  const seekToX = (clientX: number) => {
    if (!containerRef.current || duration <= 0) return;
    const rect = containerRef.current.getBoundingClientRect();
    const scrollLeft = containerRef.current.scrollLeft;
    const trackX = clientX - rect.left + scrollLeft - 140; // 140px is track label column
    const clampedX = Math.max(0, Math.min(trackX, totalWidth));
    const newTime = (clampedX / totalWidth) * duration;
    setCurrentTime(newTime);
  };

  const handleTimelineMouseDown = (e: React.MouseEvent) => {
    // Only seek if clicking track area (not left labels)
    if (e.clientX - (containerRef.current?.getBoundingClientRect().left || 0) > 140) {
      isDraggingPlayhead.current = true;
      seekToX(e.clientX);
    }
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (isDraggingPlayhead.current) {
        seekToX(e.clientX);
      } else if (draggingBoundary) {
        if (!containerRef.current || duration <= 0) return;
        const rect = containerRef.current.getBoundingClientRect();
        const scrollLeft = containerRef.current.scrollLeft;
        const trackX = e.clientX - rect.left + scrollLeft - 140;
        const targetTime = Math.max(0, Math.min((trackX / totalWidth) * duration, duration));

        const turn = turns.find(t => t.id === draggingBoundary.turnId);
        if (turn) {
          if (draggingBoundary.boundary === 'start' && targetTime < turn.end - 0.1) {
            updateTurn(turn.id, { start: Math.round(targetTime * 100) / 100 });
          } else if (draggingBoundary.boundary === 'end' && targetTime > turn.start + 0.1) {
            updateTurn(turn.id, { end: Math.round(targetTime * 100) / 100 });
          }
        }
      }
    };

    const handleMouseUp = () => {
      isDraggingPlayhead.current = false;
      setDraggingBoundary(null);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [draggingBoundary, duration, totalWidth, turns]);

  // Calculate dynamic ruler ticks based on zoom level (Section 8 of ui.md)
  const rulerTicks = useMemo(() => {
    const totalSecs = Math.ceil(duration || 1);
    let step = 10;
    if (zoomLevel < 35) step = 30;
    else if (zoomLevel < 65) step = 10;
    else if (zoomLevel < 120) step = 5;
    else if (zoomLevel < 180) step = 2;
    else step = 1;

    const ticks: Array<{ sec: number; label: string }> = [];
    for (let s = 0; s <= totalSecs; s += step) {
      const mins = Math.floor(s / 60);
      const secs = s % 60;
      const label = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
      ticks.push({ sec: s, label });
    }
    return ticks;
  }, [duration, zoomLevel]);

  // Format speaking time
  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}m ${s}s`;
  };

  return (
    <div className="timeline-viewport">
      {/* Scrollable Container covering Ruler, Waveform & Speaker Lanes */}
      <div
        ref={containerRef}
        onMouseDown={handleTimelineMouseDown}
        className="overflow-x-auto select-none relative bg-slate-950/95"
      >
        <div style={{ width: `${totalWidth + 140}px` }} className="relative flex flex-col">
          {/* 1. Time Ruler Row */}
          <div className="flex h-7 border-b border-white/10 sticky top-0 z-30 bg-[#090d16]">
            {/* Corner header */}
            <div className="w-[140px] min-w-[140px] px-3 flex items-center justify-between text-[10px] text-slate-500 font-mono border-r border-white/10 sticky left-0 z-40 bg-[#090d16]">
              <span>TRACKS</span>
              <span>TIME</span>
            </div>

            {/* Ruler Ticks */}
            <div className="relative flex-1 h-full">
              {rulerTicks.map((tick) => {
                const leftPos = (tick.sec / (duration || 1)) * totalWidth;
                return (
                  <div
                    key={tick.sec}
                    style={{ left: `${leftPos}px` }}
                    className="absolute top-0 bottom-0 flex flex-col justify-end text-[10px] font-mono text-slate-400 pl-1 border-l border-white/15 pointer-events-none"
                  >
                    <span>{tick.label}</span>
                  </div>
                );
              })}

              {/* Marker Flags (Section 26 of ui.md) */}
              {markers.map((m) => {
                const mLeft = (m.time / (duration || 1)) * totalWidth;
                return (
                  <div
                    key={m.id}
                    style={{ left: `${mLeft}px` }}
                    className="absolute top-0 z-40 flex items-center gap-1 bg-amber-500/90 text-slate-950 font-bold text-[9px] px-1.5 py-0.5 rounded-sm shadow-md cursor-pointer -translate-x-1/2"
                    title={`Marker: ${m.label} at ${m.time.toFixed(2)}s`}
                    onClick={(e) => {
                      e.stopPropagation();
                      setCurrentTime(m.time);
                    }}
                  >
                    <Bookmark size={10} fill="currentColor" />
                    <span>{m.label}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 2. Audio Waveform Track Row */}
          <div className="flex h-16 border-b border-white/10 relative">
            {/* Master Track Header */}
            <div className="w-[140px] min-w-[140px] bg-[#0c111c] border-r border-white/10 px-3 py-2 flex flex-col justify-center gap-1 text-xs sticky left-0 z-20 shadow-md">
              <span className="font-semibold text-slate-200 text-[11px] truncate">Master Audio</span>
              <span className="text-[10px] font-mono text-slate-400">16kHz PCM</span>
            </div>

            {/* Waveform Canvas */}
            <div className="relative flex-1 bg-slate-950/70">
              <canvas
                ref={waveformCanvasRef}
                className="block h-16 w-full cursor-crosshair"
              />
            </div>
          </div>

          {/* 3. Speaker Tracks (Multi-Lane Diarization) */}
          {speakers.length === 0 ? (
            <div className="flex items-center justify-center p-6 text-xs text-slate-500 italic">
              No diarization speakers detected yet. Upload audio or start live streaming.
            </div>
          ) : (
            speakers.map((spk) => {
              const speakerTurns = turns.filter((t) => t.speaker_id === spk.id);
              const isMuted = mutedSpeakers[spk.id];

              return (
                <div key={spk.id} className="flex h-10 border-b border-white/5 relative">
                  {/* Speaker Track Label (Left Sticky Column) */}
                  <div className="w-[140px] min-w-[140px] bg-[#0c111c] border-r border-white/10 px-3 py-1.5 flex items-center justify-between sticky left-0 z-20 shadow-md text-xs">
                    <div className="flex items-center gap-1.5 truncate">
                      <span
                        className="w-2.5 h-2.5 rounded-full shrink-0 shadow-sm"
                        style={{ backgroundColor: spk.color }}
                      />
                      <span className="font-medium text-slate-200 text-[11px] truncate" title={spk.display_name}>
                        {spk.display_name}
                      </span>
                    </div>

                    {/* Quick Mute Toggle */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setMutedSpeakers((prev) => ({ ...prev, [spk.id]: !prev[spk.id] }));
                      }}
                      className={`p-1 rounded hover:bg-slate-800 ${isMuted ? 'text-rose-400' : 'text-slate-500 hover:text-slate-300'}`}
                      title={isMuted ? 'Unmute Speaker' : 'Mute Speaker'}
                    >
                      {isMuted ? <VolumeX size={12} /> : <Volume2 size={12} />}
                    </button>
                  </div>

                  {/* Speaker Lane Track with Diarization Segment Blocks */}
                  <div className="relative flex-1 bg-slate-900/20">
                    {speakerTurns.map((turn) => {
                      const left = (turn.start / (duration || 1)) * totalWidth;
                      const right = (turn.end / (duration || 1)) * totalWidth;
                      const width = Math.max(12, right - left);
                      const isSelected = selectedTurnId === turn.id;

                      return (
                        <div
                          key={turn.id}
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedTurnId(turn.id);
                            setCurrentTime(turn.start);
                          }}
                          style={{
                            left: `${left}px`,
                            width: `${width}px`,
                            backgroundColor: `${spk.color}35`,
                            borderColor: isSelected ? '#ffffff' : spk.color
                          }}
                          className={`timeline-segment-block ${isSelected ? 'selected' : ''} ${turn.overlap ? 'overlap' : ''}`}
                          title={`${spk.display_name}: "${turn.text}" (${turn.start.toFixed(2)}s – ${turn.end.toFixed(2)}s)`}
                        >
                          {/* Drag Handle: Start Boundary */}
                          <div
                            onMouseDown={(e) => {
                              e.stopPropagation();
                              setDraggingBoundary({
                                turnId: turn.id,
                                boundary: 'start',
                                initialX: e.clientX,
                                initialTime: turn.start
                              });
                            }}
                            className="segment-drag-handle-left"
                            title="Drag to adjust start timestamp"
                          />

                          {/* Segment Content */}
                          <span className="truncate text-slate-100 font-medium select-none pr-1">
                            {turn.text}
                          </span>

                          {/* Overlap Collision Flag (Section 12 of ui.md) */}
                          {turn.overlap && (
                            <span
                              className="px-1 py-0.2 rounded bg-rose-500 text-white font-bold text-[9px] shrink-0 ml-1 flex items-center gap-0.5"
                              title="Barge-in / Overlapping speech detected"
                            >
                              <AlertTriangle size={9} />
                              <span>OVERLAP</span>
                            </span>
                          )}

                          {/* Drag Handle: End Boundary */}
                          <div
                            onMouseDown={(e) => {
                              e.stopPropagation();
                              setDraggingBoundary({
                                turnId: turn.id,
                                boundary: 'end',
                                initialX: e.clientX,
                                initialTime: turn.end
                              });
                            }}
                            className="segment-drag-handle-right"
                            title="Drag to adjust end timestamp"
                          />
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })
          )}

          {/* 4. Full-Height Playhead Needle across all tracks */}
          <div
            style={{ left: `${cursorX + 140}px` }}
            className="playhead-line"
          >
            {/* Top Playhead Drag Handle */}
            <div
              className="playhead-handle"
              onMouseDown={(e) => {
                e.stopPropagation();
                isDraggingPlayhead.current = true;
              }}
              title="Drag playhead"
            />
          </div>
        </div>
      </div>
    </div>
  );
};
