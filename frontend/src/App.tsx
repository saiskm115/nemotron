import React, { useEffect, useState } from 'react';
import { useSessionStore } from './stores/sessionStore';
import { api } from './services/api';
import { Header } from './components/navigation/Header';
import { EditorToolbar } from './components/editor/EditorToolbar';
import { SpeakerTimeline } from './components/timeline/SpeakerTimeline';
import { AudioPlayer } from './components/audio/AudioPlayer';
import { TranscriptPanel } from './components/transcript/TranscriptPanel';
import { RightSidebar } from './components/inspector/RightSidebar';

// Modals for secondary tools
import { UploadModal } from './components/audio/UploadModal';
import { ExportMenu } from './components/export/ExportMenu';
import { SettingsModal } from './components/modals/SettingsModal';
import { VocabularyModal } from './components/modals/VocabularyModal';
import { BenchmarkModal } from './components/modals/BenchmarkModal';
import { ObservabilityModal } from './components/modals/ObservabilityModal';

export const App: React.FC = () => {
  const { session, setSession } = useSessionStore();

  // Modals state
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [isExportOpen, setIsExportOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isVocabularyOpen, setIsVocabularyOpen] = useState(false);
  const [isBenchmarkOpen, setIsBenchmarkOpen] = useState(false);
  const [isObservabilityOpen, setIsObservabilityOpen] = useState(false);

  // Initialize or fetch initial session
  useEffect(() => {
    const initSession = async () => {
      try {
        const sessions = await api.listSessions();
        if (sessions.length > 0) {
          setSession(sessions[0]);
        } else {
          // Upload initial test session if none exists
          const dummyWavBlob = new Blob([new Uint8Array(44)], { type: 'audio/wav' });
          const formData = new FormData();
          formData.append('file', dummyWavBlob, 'telugu_meeting.wav');
          formData.append('title', 'Telugu + English Executive Standup');
          formData.append('asr_mode', 'codemix');
          formData.append('auto_translate', 'true');
          const sess = await api.uploadAudio(formData);
          setSession(sess);
        }
      } catch (e) {
        console.error('Failed to init session:', e);
      }
    };
    initSession();
  }, []);

  return (
    <div className="editor-shell">
      {/* 1. Top Navigation Bar (Logo | Session Name | Save Status | Search | Tools | Export) */}
      <Header
        onOpenUpload={() => setIsUploadOpen(true)}
        onOpenExport={() => setIsExportOpen(true)}
        onOpenVocabulary={() => setIsVocabularyOpen(true)}
        onOpenBenchmark={() => setIsBenchmarkOpen(true)}
        onOpenObservability={() => setIsObservabilityOpen(true)}
        onOpenSettings={() => setIsSettingsOpen(true)}
      />

      {/* 2. Secondary Editor Toolbar (Select, Split, Merge, Marker, Zoom, Script Toggles) */}
      <EditorToolbar />

      {/* 3. Main Workspace Area (Timeline & Transcript on Left, Collapsible Inspector on Right) */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left & Center Main Editor */}
        <div className="flex-1 flex flex-col overflow-hidden bg-slate-950">
          {/* Synchronized Multi-Track Timeline (Ruler + Waveform + Speaker Lanes + Playhead) */}
          <SpeakerTimeline />

          {/* Transport Bar (Play/Pause, Monospace Timecode, Speed, Volume) */}
          <AudioPlayer />

          {/* Editor-Style Transcript Panel directly below timeline */}
          <TranscriptPanel onOpenUpload={() => setIsUploadOpen(true)} />
        </div>

        {/* Collapsible Right Sidebar (Speakers List, Turn Inspector Properties) */}
        <RightSidebar />
      </div>

      {/* Dialog Modals */}
      <UploadModal isOpen={isUploadOpen} onClose={() => setIsUploadOpen(false)} />
      <ExportMenu isOpen={isExportOpen} onClose={() => setIsExportOpen(false)} />
      <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
      <VocabularyModal isOpen={isVocabularyOpen} onClose={() => setIsVocabularyOpen(false)} />
      <BenchmarkModal isOpen={isBenchmarkOpen} onClose={() => setIsBenchmarkOpen(false)} />
      <ObservabilityModal isOpen={isObservabilityOpen} onClose={() => setIsObservabilityOpen(false)} />
    </div>
  );
};
