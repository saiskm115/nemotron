import { create } from 'zustand';
import { Session, Turn, Speaker, SessionSettings } from '../types';
import { api } from '../services/api';
import { toast } from './toastStore';

interface SessionState {
  // Primary session state
  session: Session | null;
  isLoading: boolean;
  error: string | null;

  // Playback & cursor state
  currentTime: number;
  duration: number;
  isPlaying: boolean;
  playbackRate: number;

  // View & selection state
  zoomLevel: number; // pixels per second
  selectedTurnId: string | null;
  selectedSpeakerId: string | null;
  searchQuery: string;
  activeTab: 'transcript' | 'speakers' | 'vocabulary' | 'benchmark' | 'observability';
  activeTool: 'select' | 'hand' | 'split' | 'merge' | 'speaker' | 'text' | 'marker';
  isSidebarOpen: boolean;
  sidebarTab: 'speakers' | 'properties' | 'live';
  volume: number;
  isMuted: boolean;
  isLooping: boolean;
  saveStatus: 'saved' | 'saving' | 'unsaved';
  markers: Array<{ id: string; time: number; label: string; color: string }>;
  translitMode: 'script' | 'roman' | 'codemix';
  displayMode: 'original' | 'translation' | 'both';

  // Workspace & timeline layout state (Section 1-10 of ui.md)
  timelineMode: 'normal' | 'expanded' | 'focus';
  timelineHeight: number;

  // Live recording state
  isRecordingLive: boolean;

  // Actions
  setTimelineMode: (mode: 'normal' | 'expanded' | 'focus') => void;
  toggleTimelineFocus: () => void;
  toggleTimelineExpand: () => void;
  setTimelineHeight: (height: number) => void;
  setSession: (session: Session) => void;
  loadSession: (sessionId: string) => Promise<void>;
  setCurrentTime: (time: number) => void;
  setIsPlaying: (isPlaying: boolean) => void;
  setPlaybackRate: (rate: number) => void;
  setZoomLevel: (zoom: number) => void;
  setSelectedTurnId: (id: string | null) => void;
  setSelectedSpeakerId: (id: string | null) => void;
  setSearchQuery: (query: string) => void;
  setActiveTab: (tab: 'transcript' | 'speakers' | 'vocabulary' | 'benchmark' | 'observability') => void;
  setActiveTool: (tool: 'select' | 'hand' | 'split' | 'merge' | 'speaker' | 'text' | 'marker') => void;
  setIsSidebarOpen: (isOpen: boolean) => void;
  setSidebarTab: (tab: 'speakers' | 'properties' | 'live') => void;
  setVolume: (vol: number) => void;
  setIsMuted: (muted: boolean) => void;
  setIsLooping: (looping: boolean) => void;
  setSaveStatus: (status: 'saved' | 'saving' | 'unsaved') => void;
  addMarker: (time: number, label: string) => void;
  deleteMarker: (id: string) => void;
  setTranslitMode: (mode: 'script' | 'roman' | 'codemix') => void;
  setDisplayMode: (mode: 'original' | 'translation' | 'both') => void;
  setIsRecordingLive: (isRecording: boolean) => void;

  // Session mutations
  retranscribingTurnId: string | null;
  retranscribeTurn: (turnId: string, start: number, end: number) => Promise<void>;
  updateTurn: (turnId: string, updates: Partial<Turn>) => Promise<void>;
  splitTurn: (turnId: string, timestamp: number, before: string, after: string) => Promise<void>;
  mergeTurns: (t1: string, t2: string) => Promise<void>;
  deleteTurn: (turnId: string) => Promise<void>;
  resetTurn: (turnId: string) => Promise<void>;
  resetSession: () => Promise<void>;
  undo: () => Promise<void>;
  redo: () => Promise<void>;
  updateSpeaker: (speakerId: string, updates: Partial<Speaker>) => Promise<void>;
  mergeSpeakers: (sourceId: string, targetId: string) => Promise<void>;
  translateTurn: (turnId: string) => Promise<void>;
  translateAll: () => Promise<void>;
  addKeyterm: (term: string) => Promise<void>;
  removeKeyterm: (term: string) => Promise<void>;
  updateSettings: (settings: Partial<SessionSettings>) => Promise<void>;
}

const getStoredTimelineHeight = (): number => {
  if (typeof window !== 'undefined') {
    try {
      const saved = localStorage.getItem('diarizestudio.timelineHeight');
      if (saved) {
        const val = parseInt(saved, 10);
        if (!isNaN(val) && val >= 250) return val;
      }
      return Math.max(320, Math.floor(window.innerHeight * 0.48));
    } catch (e) {}
  }
  return 380;
};

export const useSessionStore = create<SessionState>((set, get) => ({
  session: null,
  isLoading: false,
  error: null,

  currentTime: 0,
  duration: 0,
  isPlaying: false,
  playbackRate: 1.0,

  // Workspace & timeline layout
  timelineMode: 'normal',
  timelineHeight: getStoredTimelineHeight(),

  zoomLevel: 60, // 60px per second default
  selectedTurnId: null,
  selectedSpeakerId: null,
  searchQuery: '',
  activeTab: 'transcript',
  activeTool: 'select',
  isSidebarOpen: true,
  sidebarTab: 'speakers' as const,
  volume: 1.0,
  isMuted: false,
  isLooping: false,
  saveStatus: 'saved',
  markers: [],
  translitMode: 'script' as const,
  displayMode: 'both' as const,
  isRecordingLive: false,
  retranscribingTurnId: null,

  setTimelineMode: (mode) => set({ timelineMode: mode }),
  toggleTimelineFocus: () => set(state => ({
    timelineMode: state.timelineMode === 'focus' ? 'normal' : 'focus'
  })),
  toggleTimelineExpand: () => set(state => ({
    timelineMode: state.timelineMode === 'expanded' ? 'normal' : 'expanded'
  })),
  setTimelineHeight: (height) => {
    if (typeof window !== 'undefined') {
      try {
        localStorage.setItem('diarizestudio.timelineHeight', height.toString());
      } catch (e) {}
    }
    set({ timelineHeight: height });
  },

  setSession: (session) => set({
    session,
    duration: session.duration || 0,
    currentTime: 0
  }),

  loadSession: async (sessionId: string) => {
    set({ isLoading: true, error: null });
    try {
      const session = await api.getSession(sessionId);
      set({ session, duration: session.duration || 0, isLoading: false });
    } catch (e: any) {
      const msg = e.message || 'Failed to load session';
      set({ error: msg, isLoading: false });
      toast.error(msg, 'Load Session');
    }
  },

  setCurrentTime: (time: number) => {
    const dur = get().duration;
    const clamped = Math.max(0, dur > 0 ? Math.min(time, dur) : time);
    set({ currentTime: clamped });
  },

  setIsPlaying: (isPlaying: boolean) => set({ isPlaying }),
  setPlaybackRate: (playbackRate: number) => set({ playbackRate }),
  setZoomLevel: (zoomLevel: number) => set({ zoomLevel: Math.max(20, Math.min(zoomLevel, 250)) }),
  setSelectedTurnId: (selectedTurnId: string | null) => set({ selectedTurnId }),
  setSelectedSpeakerId: (selectedSpeakerId: string | null) => set({ selectedSpeakerId }),
  setSearchQuery: (searchQuery: string) => set({ searchQuery }),
  setActiveTab: (activeTab) => set({ activeTab }),
  setActiveTool: (activeTool) => set({ activeTool }),
  setIsSidebarOpen: (isSidebarOpen) => set({ isSidebarOpen }),
  setSidebarTab: (sidebarTab) => set({ sidebarTab }),
  setVolume: (volume) => set({ volume }),
  setIsMuted: (isMuted) => set({ isMuted }),
  setIsLooping: (isLooping) => set({ isLooping }),
  setSaveStatus: (saveStatus) => set({ saveStatus }),
  addMarker: (time, label) => set((state) => ({
    markers: [...state.markers, { id: `m_${Date.now()}`, time, label, color: '#38bdf8' }]
  })),
  deleteMarker: (id) => set((state) => ({
    markers: state.markers.filter(m => m.id !== id)
  })),
  setTranslitMode: (translitMode) => set({ translitMode }),
  setDisplayMode: (displayMode) => set({ displayMode }),
  setIsRecordingLive: (isRecordingLive: boolean) => set({ isRecordingLive }),

  // Turn mutations
  updateTurn: async (turnId: string, updates: Partial<Turn>) => {
    const sess = get().session;
    if (!sess) {
      toast.error('No active session found to edit.', 'Edit Segment');
      return;
    }
    const previousTurns = sess.turns;
    // 1. Optimistic local update for instantaneous 60fps UX
    set((state) => {
      if (!state.session) return state;
      const newTurns = state.session.turns.map(t =>
        t.id === turnId ? { ...t, ...updates, status: 'edited' as const, source: 'user_edit' as const } : t
      );
      return { session: { ...state.session, turns: newTurns } };
    });
    try {
      const updatedTurn = await api.updateTurn(sess.id, turnId, updates);
      set((state) => {
        if (!state.session) return state;
        const newTurns = state.session.turns.map(t => t.id === turnId ? updatedTurn : t);
        return { session: { ...state.session, turns: newTurns } };
      });
    } catch (e: any) {
      // Revert optimistic update
      set((state) => ({
        session: state.session ? { ...state.session, turns: previousTurns } : null,
        error: e.message
      }));
      toast.error(e.message || 'Failed to update segment', 'Edit Error');
    }
  },

  retranscribeTurn: async (turnId: string, start: number, end: number) => {
    const sess = get().session;
    if (!sess) return;
    const previousTurns = sess.turns;
    set({ retranscribingTurnId: turnId });
    // Optimistic local update
    set((state) => {
      if (!state.session) return state;
      const newTurns = state.session.turns.map(t =>
        t.id === turnId ? { ...t, start, end, status: 'edited' as const, source: 'user_edit' as const } : t
      );
      return { session: { ...state.session, turns: newTurns } };
    });

    try {
      const updatedTurn = await api.retranscribeTurn(sess.id, turnId, start, end);
      set((state) => {
        if (!state.session) return state;
        const newTurns = state.session.turns.map(t => t.id === turnId ? updatedTurn : t);
        return { session: { ...state.session, turns: newTurns }, retranscribingTurnId: null };
      });
      const previewText = updatedTurn.text.length > 40 ? updatedTurn.text.slice(0, 40) + '...' : updatedTurn.text;
      toast.success(`Re-transcribed: "${previewText}"`, 'Section Updated');
    } catch (e: any) {
      set((state) => ({
        session: state.session ? { ...state.session, turns: previousTurns } : null,
        retranscribingTurnId: null,
        error: e.message
      }));
      toast.error(e.message || 'Failed to retranscribe segment', 'Retranscription Error');
    }
  },

  splitTurn: async (turnId: string, timestamp: number, before: string, after: string) => {
    const sess = get().session;
    if (!sess) {
      toast.error('No active session to perform split.', 'Split Action');
      return;
    }
    try {
      await api.splitTurn(sess.id, turnId, timestamp, before, after);
      await get().loadSession(sess.id);
      toast.success('Segment split successfully', 'Split Segment');
    } catch (e: any) {
      set({ error: e.message });
      toast.error(e.message || 'Failed to split segment', 'Split Error');
    }
  },

  mergeTurns: async (t1: string, t2: string) => {
    const sess = get().session;
    if (!sess) {
      toast.error('No active session to perform merge.', 'Merge Action');
      return;
    }
    try {
      await api.mergeTurns(sess.id, t1, t2);
      await get().loadSession(sess.id);
      toast.success('Segments merged successfully', 'Merge Segments');
    } catch (e: any) {
      set({ error: e.message });
      toast.error(e.message || 'Failed to merge segments', 'Merge Error');
    }
  },

  deleteTurn: async (turnId: string) => {
    const sess = get().session;
    if (!sess) {
      toast.error('No active session to delete segment.', 'Delete Action');
      return;
    }
    try {
      await api.deleteTurn(sess.id, turnId);
      set((state) => {
        if (!state.session) return state;
        return {
          session: {
            ...state.session,
            turns: state.session.turns.filter(t => t.id !== turnId)
          },
          selectedTurnId: state.selectedTurnId === turnId ? null : state.selectedTurnId
        };
      });
      toast.success('Segment deleted', 'Delete Segment');
    } catch (e: any) {
      set({ error: e.message });
      toast.error(e.message || 'Failed to delete segment', 'Delete Error');
    }
  },

  resetTurn: async (turnId: string) => {
    const sess = get().session;
    if (!sess) {
      toast.error('No active session to reset segment.', 'Reset Action');
      return;
    }
    try {
      const restored = await api.resetTurn(sess.id, turnId);
      set((state) => {
        if (!state.session) return state;
        return {
          session: {
            ...state.session,
            turns: state.session.turns.map(t => t.id === turnId ? restored : t)
          }
        };
      });
      toast.success('Segment restored to model output', 'Reset Segment');
    } catch (e: any) {
      set({ error: e.message });
      toast.error(e.message || 'Failed to reset segment', 'Reset Error');
    }
  },

  resetSession: async () => {
    const sess = get().session;
    if (!sess) {
      toast.error('No active session to reset.', 'Reset Action');
      return;
    }
    try {
      const reset = await api.resetSession(sess.id);
      set({ session: reset });
      toast.success('All edits reset to raw model output', 'Session Reset');
    } catch (e: any) {
      set({ error: e.message });
      toast.error(e.message || 'Failed to reset session', 'Reset Error');
    }
  },

  undo: async () => {
    const sess = get().session;
    if (!sess) {
      toast.warning('No active session to undo.', 'Undo');
      return;
    }
    try {
      const undone = await api.undoSession(sess.id);
      set({ session: undone });
      toast.info('Reverted last edit', 'Undo');
    } catch (e: any) {
      set({ error: e.message });
      toast.warning(e.message || 'Nothing more to undo', 'Undo');
    }
  },

  redo: async () => {
    const sess = get().session;
    if (!sess) {
      toast.warning('No active session to redo.', 'Redo');
      return;
    }
    try {
      const redone = await api.redoSession(sess.id);
      set({ session: redone });
      toast.info('Restored next edit', 'Redo');
    } catch (e: any) {
      set({ error: e.message });
      toast.warning(e.message || 'Nothing more to redo', 'Redo');
    }
  },

  updateSpeaker: async (speakerId: string, updates: Partial<Speaker>) => {
    const sess = get().session;
    if (!sess) {
      toast.error('No active session to update speaker.', 'Speaker Action');
      return;
    }
    try {
      const updatedSpk = await api.updateSpeaker(sess.id, speakerId, updates);
      set((state) => {
        if (!state.session) return state;
        return {
          session: {
            ...state.session,
            speakers: state.session.speakers.map(s => s.id === speakerId ? updatedSpk : s)
          }
        };
      });
      toast.success('Speaker details updated', 'Speaker Saved');
    } catch (e: any) {
      set({ error: e.message });
      toast.error(e.message || 'Failed to update speaker', 'Speaker Error');
    }
  },

  mergeSpeakers: async (sourceId: string, targetId: string) => {
    const sess = get().session;
    if (!sess) {
      toast.error('No active session to merge speakers.', 'Merge Action');
      return;
    }
    try {
      const merged = await api.mergeSpeakers(sess.id, sourceId, targetId);
      set({ session: merged });
      toast.success('Speakers merged successfully', 'Speakers Merged');
    } catch (e: any) {
      set({ error: e.message });
      toast.error(e.message || 'Failed to merge speakers', 'Merge Error');
    }
  },

  translateTurn: async (turnId: string) => {
    const sess = get().session;
    if (!sess) {
      toast.error('No active session to translate segment.', 'Translation Action');
      return;
    }
    try {
      const targetLang = sess.settings.target_language || 'en-IN';
      const updatedTurn = await api.translateTurn(sess.id, turnId, targetLang);
      set((state) => {
        if (!state.session) return state;
        return {
          session: {
            ...state.session,
            turns: state.session.turns.map(t => t.id === turnId ? updatedTurn : t)
          }
        };
      });
      toast.success('Segment translated', 'Translation Complete');
    } catch (e: any) {
      set({ error: e.message });
      toast.error(e.message || 'Failed to translate segment', 'Translation Error');
    }
  },

  translateAll: async () => {
    const sess = get().session;
    if (!sess) {
      toast.error('No active session to translate.', 'Translation Action');
      return;
    }
    try {
      set({ isLoading: true });
      const targetLang = sess.settings.target_language || 'en-IN';
      await api.translateAll(sess.id, targetLang);
      await get().loadSession(sess.id);
      toast.success('Complete transcript translated', 'Translation Complete');
    } catch (e: any) {
      set({ error: e.message, isLoading: false });
      toast.error(e.message || 'Failed to translate transcript', 'Translation Error');
    }
  },

  addKeyterm: async (term: string) => {
    const sess = get().session;
    if (!sess) {
      toast.error('No active session found.', 'Vocabulary Action');
      return;
    }
    const clean = term.trim();
    if (!clean) {
      toast.warning('Please enter a non-empty keyterm.', 'Vocabulary');
      return;
    }
    const current = sess.settings.keyterms || [];
    if (current.includes(clean)) {
      toast.warning(`Keyterm "${clean}" is already in vocabulary.`, 'Duplicate Keyterm');
      return;
    }
    const nextKeyterms = [...current, clean];
    await get().updateSettings({ keyterms: nextKeyterms });
    toast.success(`Keyterm "${clean}" added to vocabulary`, 'Vocabulary Updated');
  },

  removeKeyterm: async (term: string) => {
    const sess = get().session;
    if (!sess) return;
    const nextKeyterms = (sess.settings.keyterms || []).filter(k => k !== term);
    await get().updateSettings({ keyterms: nextKeyterms });
    toast.info(`Keyterm "${term}" removed`, 'Vocabulary Updated');
  },

  updateSettings: async (settingsUpdate: Partial<SessionSettings>) => {
    const sess = get().session;
    if (!sess) {
      toast.error('No active session to update settings.', 'Settings Action');
      return;
    }
    const mergedSettings = { ...sess.settings, ...settingsUpdate };
    try {
      const updated = await api.updateSession(sess.id, { settings: mergedSettings as any });
      set({ session: updated });
      toast.success('Session settings updated', 'Settings Saved');
    } catch (e: any) {
      set({ error: e.message });
      toast.error(e.message || 'Failed to save settings', 'Settings Error');
    }
  }
}));
