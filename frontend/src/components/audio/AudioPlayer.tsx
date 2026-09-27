import React, { useRef, useEffect } from 'react';
import { useSessionStore } from '../../stores/sessionStore';
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Repeat,
  Volume2,
  VolumeX
} from 'lucide-react';

export const AudioPlayer: React.FC = () => {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const {
    session,
    currentTime,
    duration,
    isPlaying,
    playbackRate,
    volume,
    isMuted,
    isLooping,
    selectedTurnId,
    setCurrentTime,
    setIsPlaying,
    setPlaybackRate,
    setVolume,
    setIsMuted,
    setIsLooping,
    setSelectedTurnId
  } = useSessionStore();

  const audioSrc = session?.id ? `/api/audio/${session.id}/stream` : '';
  const turns = session?.turns || [];

  // Play / Pause audio element sync
  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;

    if (isPlaying && el.paused) {
      el.play().catch(() => setIsPlaying(false));
    } else if (!isPlaying && !el.paused) {
      el.pause();
    }
  }, [isPlaying]);

  // Synchronize currentTime without jitter
  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;
    if (Math.abs(el.currentTime - currentTime) > 0.15) {
      el.currentTime = currentTime;
    }
  }, [currentTime]);

  // Playback rate
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.playbackRate = playbackRate;
    }
  }, [playbackRate]);

  // Volume & Mute
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = isMuted ? 0 : volume;
    }
  }, [volume, isMuted]);

  // Keyboard transport shortcuts (Space, Left/Right arrows, J/K/L)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes((e.target as HTMLElement).tagName)) return;

      if (e.code === 'Space') {
        e.preventDefault();
        setIsPlaying(!isPlaying);
      } else if (e.code === 'ArrowLeft' || e.key.toLowerCase() === 'j') {
        e.preventDefault();
        const delta = e.shiftKey ? 0.2 : 2.0;
        setCurrentTime(Math.max(0, currentTime - delta));
      } else if (e.code === 'ArrowRight' || e.key.toLowerCase() === 'l') {
        e.preventDefault();
        const delta = e.shiftKey ? 0.2 : 2.0;
        setCurrentTime(Math.min(duration, currentTime + delta));
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isPlaying, currentTime, duration]);

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  };

  const handleEnded = () => {
    if (isLooping && audioRef.current) {
      audioRef.current.currentTime = 0;
      audioRef.current.play();
    } else {
      setIsPlaying(false);
    }
  };

  const handlePrevTurn = () => {
    if (turns.length === 0) return;
    const curIdx = turns.findIndex(t => currentTime >= t.start && currentTime <= t.end);
    if (curIdx > 0) {
      const prevTurn = turns[curIdx - 1];
      setCurrentTime(prevTurn.start);
      setSelectedTurnId(prevTurn.id);
    } else {
      setCurrentTime(0);
    }
  };

  const handleNextTurn = () => {
    if (turns.length === 0) return;
    const curIdx = turns.findIndex(t => currentTime >= t.start && currentTime <= t.end);
    if (curIdx >= 0 && curIdx < turns.length - 1) {
      const nextTurn = turns[curIdx + 1];
      setCurrentTime(nextTurn.start);
      setSelectedTurnId(nextTurn.id);
    }
  };

  // High-precision time format: 00:12.430
  const formatTimecode = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    const ms = Math.floor((secs - Math.floor(secs)) * 1000);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}.${ms.toString().padStart(3, '0')}`;
  };

  return (
    <div className="transport-bar">
      <audio
        ref={audioRef}
        src={audioSrc}
        onTimeUpdate={handleTimeUpdate}
        onEnded={handleEnded}
        preload="metadata"
      />

      {/* Left: Transport Buttons */}
      <div className="flex items-center gap-1.5">
        <button
          onClick={handlePrevTurn}
          className="tool-btn !px-2"
          title="Previous Turn (J or ←)"
        >
          <SkipBack size={15} />
        </button>

        <button
          onClick={() => setIsPlaying(!isPlaying)}
          className="w-9 h-9 rounded-full bg-sky-500 hover:bg-sky-400 text-slate-950 flex items-center justify-center font-bold transition shadow-lg shadow-sky-500/25"
          title="Play / Pause (Space)"
        >
          {isPlaying ? <Pause size={17} fill="currentColor" /> : <Play size={17} fill="currentColor" className="ml-0.5" />}
        </button>

        <button
          onClick={handleNextTurn}
          className="tool-btn !px-2"
          title="Next Turn (L or →)"
        >
          <SkipForward size={15} />
        </button>

        <button
          onClick={() => setIsLooping(!isLooping)}
          className={`tool-btn !px-2 ${isLooping ? 'active' : ''}`}
          title="Loop Playback"
        >
          <Repeat size={14} />
        </button>
      </div>

      {/* Center: Large High-Precision Timecode Display */}
      <div className="flex items-center gap-2 bg-slate-950 px-4 py-1.5 rounded-lg border border-white/10 font-mono tracking-wider shadow-inner">
        <span className="text-cyan-400 font-semibold text-sm">
          {formatTimecode(currentTime)}
        </span>
        <span className="text-slate-600 text-xs font-normal">/</span>
        <span className="text-slate-400 text-xs">
          {formatTimecode(duration)}
        </span>
      </div>

      {/* Right: Playback Speed & Volume */}
      <div className="flex items-center gap-3">
        {/* Speed Selector Presets */}
        <div className="flex items-center gap-0.5 bg-slate-950 p-0.5 rounded-md border border-white/5 text-[11px]">
          {[0.5, 0.75, 1.0, 1.25, 1.5, 2.0].map((rate) => (
            <button
              key={rate}
              onClick={() => setPlaybackRate(rate)}
              className={`px-1.5 py-0.5 rounded font-mono transition ${
                playbackRate === rate
                  ? 'bg-sky-500/20 text-sky-300 font-bold border border-sky-500/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {rate}x
            </button>
          ))}
        </div>

        <div className="h-4 w-[1px] bg-white/10" />

        {/* Volume Slider & Mute Toggle */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setIsMuted(!isMuted)}
            className="p-1 text-slate-400 hover:text-white rounded"
            title={isMuted ? 'Unmute' : 'Mute'}
          >
            {isMuted || volume === 0 ? <VolumeX size={15} className="text-rose-400" /> : <Volume2 size={15} />}
          </button>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={isMuted ? 0 : volume}
            onChange={(e) => {
              setVolume(parseFloat(e.target.value));
              if (isMuted) setIsMuted(false);
            }}
            className="w-16 accent-cyan-400 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
            title={`Volume: ${Math.round(volume * 100)}%`}
          />
        </div>
      </div>
    </div>
  );
};
