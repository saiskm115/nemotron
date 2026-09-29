import React, { useRef, useEffect, useCallback } from 'react';
import { useSessionStore, SpeakerGainState } from '../../stores/sessionStore';
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Repeat,
  Volume2,
  VolumeX
} from 'lucide-react';

/** True when the playhead falls inside any diarised turn. */
function isInsideAnyTurn(time: number, turns: { start: number; end: number }[]): boolean {
  return turns.some((turn) => time >= turn.start && time <= turn.end);
}

export const AudioPlayer: React.FC = () => {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const masterGainRef = useRef<GainNode | null>(null);
  const speakerGainRef = useRef<GainNode | null>(null);
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
    speakerGains,
    setCurrentTime,
    setIsPlaying,
    setPlaybackRate,
    setVolume,
    setIsMuted,
    setIsLooping,
    setSelectedTurnId
  } = useSessionStore();

  // Capture real duration from HTML audio element
  const handleLoadedMetadata = () => {
    const el = audioRef.current;
    if (!el) return;
    const realDuration = el.duration;
    if (realDuration && isFinite(realDuration) && realDuration > 0) {
      // Update store duration from actual audio element (fixes 00:00.000 / 00:00.000)
      useSessionStore.setState({ duration: realDuration });
    }
  };

  const audioSrc = session?.id ? `/api/audio/${session.id}/stream` : '';
  const turns = session?.turns || [];

  /* ── Per-speaker gain graph ────────────────────────────────────────────
   * The single <audio> element is routed through a Web Audio graph with one gain
   * node, and each speaker's node is opened only while the playhead sits inside one
   * of that speaker's turns. That makes the timeline's mute/solo controls actually
   * change what you hear, which is what every editor's per-track controls do.
   */
  const ensureAudioGraph = useCallback(() => {
    const el = audioRef.current;
    if (!el || ctxRef.current) return;

    const AudioCtx: typeof AudioContext =
      window.AudioContext ?? (window as any).webkitAudioContext;
    if (!AudioCtx) return;

    try {
      const ctx = new AudioCtx();
      const source = ctx.createMediaElementSource(el);
      const speakerGain = ctx.createGain();
      const masterGain = ctx.createGain();
      source.connect(speakerGain);
      speakerGain.connect(masterGain);
      masterGain.connect(ctx.destination);
      ctxRef.current = ctx;
      speakerGainRef.current = speakerGain;
      masterGainRef.current = masterGain;
    } catch {
      // Browsers refuse a second MediaElementSource for the same element; without
      // a graph the transport still works, just without per-speaker mute/solo.
      ctxRef.current = null;
    }
  }, []);

  useEffect(() => {
    ensureAudioGraph();
  }, [ensureAudioGraph, audioSrc]);

  useEffect(() => {
    if (isPlaying && ctxRef.current?.state === 'suspended') {
      ctxRef.current.resume().catch(() => {});
    }
  }, [isPlaying]);

  useEffect(() => {
    const master = masterGainRef.current;
    if (!master) return;
    const target = isMuted ? 0 : volume;
    master.gain.setTargetAtTime(target, ctxRef.current?.currentTime ?? 0, 0.02);
  }, [volume, isMuted]);

  // Open the speaker bus only while the playhead sits inside an audible speaker's turn.
  // Solo takes precedence over mute, exactly like a mixer: soloing any track silences
  // the others, and mute only applies when nothing is soloed.
  useEffect(() => {
    const gain = speakerGainRef.current;
    if (!gain) return;
    const config = speakerGains;
    const now = ctxRef.current?.currentTime ?? 0;

    if (!config) {
      gain.gain.setTargetAtTime(1, now, 0.02);
      return;
    }

    const soloIds = Object.entries(config.solo).filter(([, on]) => on).map(([id]) => id);
    let audible = false;
    for (const turn of turns) {
      if (currentTime < turn.start || currentTime > turn.end) continue;
      const allowed = config.soloActive
        ? soloIds.includes(turn.speaker_id)
        : !config.muted[turn.speaker_id];
      if (allowed) {
        audible = true;
        break;
      }
    }

    // Between turns (silence) nothing is suppressed: the audio there is not speech
    // we are asked to hear selectively.
    if (!isInsideAnyTurn(currentTime, turns)) {
      audible = true;
    }

    gain.gain.setTargetAtTime(audible ? 1 : 0, now, 0.02);
  }, [speakerGains, currentTime, turns]);

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
    const safe = Math.max(0, secs || 0);
    const h = Math.floor(safe / 3600);
    const m = Math.floor((safe % 3600) / 60);
    const s = Math.floor(safe % 60);
    const ms = Math.floor((safe - Math.floor(safe)) * 1000);
    const pad = (n: number, w = 2) => n.toString().padStart(w, '0');
    return h > 0
      ? `${pad(h)}:${pad(m)}:${pad(s)}.${pad(ms, 3)}`
      : `${pad(m)}:${pad(s)}.${pad(ms, 3)}`;
  };

  return (
    <div className="transport-bar">
      <audio
        ref={audioRef}
        src={audioSrc}
        onTimeUpdate={handleTimeUpdate}
        onEnded={handleEnded}
        onLoadedMetadata={handleLoadedMetadata}
        onDurationChange={handleLoadedMetadata}
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
