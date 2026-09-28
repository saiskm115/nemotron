import React, { useState, useRef } from 'react';
import { useSessionStore } from '../../stores/sessionStore';
import { toast } from '../../stores/toastStore';
import { Mic, Square, Radio, AlertCircle } from 'lucide-react';

export const LiveRecorder: React.FC = () => {
  const { session, setSession, isRecordingLive, setIsRecordingLive } = useSessionStore();
  const [liveLog, setLiveLog] = useState<Array<{ id: string; speaker: string; text: string; status: string }>>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);

  const startLiveRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;

      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${wsProtocol}//${window.location.host}/ws/live/${session?.id || 'live_session'}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsRecordingLive(true);
        toast.success('Live microphone streaming started.', 'Live Mic Active');
        // Start streaming audio
        const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 });
        audioContextRef.current = audioCtx;
        const source = audioCtx.createMediaStreamSource(stream);
        const processor = audioCtx.createScriptProcessor(4096, 1, 1);

        processor.onaudioprocess = (e) => {
          if (ws.readyState === WebSocket.OPEN) {
            const inputData = e.inputBuffer.getChannelData(0);
            // Convert Float32 to Int16 PCM
            const pcmBuffer = new Int16Array(inputData.length);
            for (let i = 0; i < inputData.length; i++) {
              pcmBuffer[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32767));
            }
            ws.send(pcmBuffer.buffer);
          }
        };

        source.connect(processor);
        processor.connect(audioCtx.destination);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'transcript.interim' || data.type === 'transcript.final') {
            setLiveLog(prev => {
              const existingIdx = prev.findIndex(item => item.id === data.turn_id);
              const newItem = {
                id: data.turn_id,
                speaker: data.speaker_id,
                text: data.text,
                status: data.type === 'transcript.final' ? 'final' : 'interim'
              };
              if (existingIdx >= 0) {
                const next = [...prev];
                next[existingIdx] = newItem;
                return next;
              }
              return [...prev, newItem];
            });
          }
        } catch (e) {
          console.error('WS message error:', e);
        }
      };

      ws.onerror = (err) => {
        console.error('WS error:', err);
        toast.error('WebSocket live audio connection failed.', 'Live Mic Error');
      };

      ws.onclose = () => {
        setIsRecordingLive(false);
      };
    } catch (err: any) {
      toast.error(`Could not access microphone: ${err.message}`, 'Microphone Error');
    }
  };

  const stopLiveRecording = () => {
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ action: 'stop' }));
      wsRef.current.close();
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop());
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
    }
    setIsRecordingLive(false);
    toast.info('Live stream recording stopped.', 'Live Mic');
  };

  return (
    <div className="glass-panel p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between border-b border-white/5 pb-2">
        <div className="flex items-center gap-2">
          <Radio size={16} className={isRecordingLive ? 'text-rose-500 animate-pulse' : 'text-cyan-400'} />
          <span className="font-semibold text-xs text-slate-200">Live Streaming Transcription</span>
        </div>

        {!isRecordingLive ? (
          <button
            onClick={startLiveRecording}
            className="btn btn-danger px-3 py-1.5 text-xs flex items-center gap-1.5"
          >
            <Mic size={14} />
            <span>Start Live Mic</span>
          </button>
        ) : (
          <button
            onClick={stopLiveRecording}
            className="btn bg-rose-600 hover:bg-rose-700 text-white px-3 py-1.5 text-xs flex items-center gap-1.5 animate-pulse"
          >
            <Square size={14} fill="currentColor" />
            <span>Stop Stream</span>
          </button>
        )}
      </div>

      {isRecordingLive && (
        <div className="flex flex-col gap-2 p-3 bg-slate-950/80 rounded-lg border border-white/5 max-h-48 overflow-y-auto">
          {liveLog.length === 0 ? (
            <span className="text-xs text-slate-500 italic">Listening for speech...</span>
          ) : (
            liveLog.map(item => (
              <div key={item.id} className="text-xs flex items-start gap-2">
                <span className="font-semibold text-cyan-400 shrink-0">{item.speaker}:</span>
                <span className={item.status === 'interim' ? 'text-slate-400 italic' : 'text-slate-100 font-medium'}>
                  {item.text}
                </span>
                {item.status === 'interim' && (
                  <span className="text-[10px] text-slate-500 bg-slate-900 px-1 rounded ml-auto">Interim</span>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};
