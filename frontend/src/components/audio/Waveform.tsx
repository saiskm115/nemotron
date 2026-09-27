import React, { useRef, useEffect } from 'react';
import { useSessionStore } from '../../stores/sessionStore';

export const Waveform: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const { session, currentTime, duration, zoomLevel, setCurrentTime, setSelectedTurnId } = useSessionStore();

  const peaks = session?.metadata?.audio?.peaks || [];

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = Math.max(containerRef.current?.clientWidth || 800, (duration || 1) * zoomLevel);
    const height = 90;

    canvas.width = width;
    canvas.height = height;

    ctx.clearRect(0, 0, width, height);

    // 1. Draw Speaker Background Zones
    if (session?.turns) {
      session.turns.forEach(turn => {
        const spk = session.speakers.find(s => s.id === turn.speaker_id);
        const startX = (turn.start / (duration || 1)) * width;
        const endX = (turn.end / (duration || 1)) * width;
        const segWidth = Math.max(2, endX - startX);

        ctx.fillStyle = spk?.color ? `${spk.color}18` : 'rgba(56, 189, 248, 0.08)';
        ctx.fillRect(startX, 0, segWidth, height);

        // Top speaker color accent line
        ctx.fillStyle = spk?.color || '#38bdf8';
        ctx.fillRect(startX, 0, segWidth, 3);
      });
    }

    // 2. Draw Waveform Peaks
    const numBars = peaks.length > 0 ? peaks.length : 300;
    const barWidth = width / numBars;
    const centerY = height / 2;

    for (let i = 0; i < numBars; i++) {
      const peak = peaks.length > 0 ? peaks[i] : Math.sin(i * 0.15) * 0.5 + 0.2;
      const barHeight = Math.max(4, peak * (height - 20));
      const x = i * barWidth;

      const timeAtBar = (i / numBars) * duration;
      const isPlayed = timeAtBar <= currentTime;

      ctx.fillStyle = isPlayed ? '#38bdf8' : '#334155';
      ctx.fillRect(x, centerY - barHeight / 2, Math.max(1.5, barWidth - 1), barHeight);
    }

    // 3. Playback Cursor
    const cursorX = duration > 0 ? (currentTime / duration) * width : 0;
    ctx.strokeStyle = '#f43f5e';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(cursorX, 0);
    ctx.lineTo(cursorX, height);
    ctx.stroke();

    // Cursor head
    ctx.fillStyle = '#f43f5e';
    ctx.beginPath();
    ctx.arc(cursorX, 6, 5, 0, Math.PI * 2);
    ctx.fill();

  }, [peaks, currentTime, duration, zoomLevel, session]);

  const isDraggingRef = useRef(false);

  const seekFromMouseEvent = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || duration <= 0) return;
    const rect = canvas.getBoundingClientRect();
    const clickX = Math.max(0, Math.min(e.clientX - rect.left, canvas.width));
    const newTime = (clickX / canvas.width) * duration;
    setCurrentTime(newTime);

    // Find and select turn at this timestamp
    if (session?.turns) {
      const matched = session.turns.find(t => newTime >= t.start && newTime <= t.end);
      if (matched) {
        setSelectedTurnId(matched.id);
      }
    }
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    isDraggingRef.current = true;
    seekFromMouseEvent(e);
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (isDraggingRef.current) {
      seekFromMouseEvent(e);
    }
  };

  const handleMouseUp = () => {
    isDraggingRef.current = false;
  };

  useEffect(() => {
    const handleGlobalMouseUp = () => {
      isDraggingRef.current = false;
    };
    window.addEventListener('mouseup', handleGlobalMouseUp);
    return () => window.removeEventListener('mouseup', handleGlobalMouseUp);
  }, []);

  return (
    <div
      ref={containerRef}
      className="relative overflow-x-auto overflow-y-hidden bg-slate-950/70 rounded-lg border border-white/5 h-[92px] cursor-crosshair select-none"
    >
      <canvas
        ref={canvasRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        className="block"
      />
    </div>
  );
};
