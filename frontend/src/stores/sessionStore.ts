import { create } from 'zustand';
import { Session, Turn, Speaker, SessionSettings } from '../types';
import { api } from '../services/api';

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

  // Live recording state
  isRecordingLive: boolean;

  // Actions
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

export const useSessionStore = create<SessionState>((set, get) => ({
  session: null,
  isLoading: false,
  error: null,

  currentTime: 0,
  duration: 0,
  isPlaying: false,
  playbackRate: 1.0,

  zoomLevel: 60, // 60px per second default
  selectedTurnId: null,
  selectedSpeakerId: null,
  searchQuery: '',
  activeTab: 'transcript',
  activeTool: 'select',
  isSidebarOpen: true,
  sidebarTab: 'speakers',
  volume: 1.0,
  isMuted: false,
  isLooping: false,
  saveStatus: 'saved',
  markers: [],
  translitMode: 'script',
  displayMode: 'both',
  isRecordingLive: false,

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
      set({ error: e.message || 'Failed to load session', isLoading: false });
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
    if (!sess) return;
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
      set({ error: e.message });
    }
  },

  splitTurn: async (turnId: string, timestamp: number, before: string, after: string) => {
    const sess = get().session;
    if (!sess) return;
    try {
      const res = await api.splitTurn(sess.id, turnId, timestamp, before, after);
      // Reload session to sync state perfectly
      await get().loadSession(sess.id);
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  mergeTurns: async (t1: string, t2: string) => {
    const sess = get().session;
    if (!sess) return;
    try {
      await api.mergeTurns(sess.id, t1, t2);
      await get().loadSession(sess.id);
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  deleteTurn: async (turnId: string) => {
    const sess = get().session;
    if (!sess) return;
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
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  resetTurn: async (turnId: string) => {
    const sess = get().session;
    if (!sess) return;
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
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  resetSession: async () => {
    const sess = get().session;
    if (!sess) return;
    try {
      const reset = await api.resetSession(sess.id);
      set({ session: reset });
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  undo: async () => {
    const sess = get().session;
    if (!sess) return;
    try {
      const undone = await api.undoSession(sess.id);
      set({ session: undone });
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  redo: async () => {
    const sess = get().session;
    if (!sess) return;
    try {
      const redone = await api.redoSession(sess.id);
      set({ session: redone });
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  updateSpeaker: async (speakerId: string, updates: Partial<Speaker>) => {
    const sess = get().session;
    if (!sess) return;
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
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  mergeSpeakers: async (sourceId: string, targetId: string) => {
    const sess = get().session;
    if (!sess) return;
    try {
      const merged = await api.mergeSpeakers(sess.id, sourceId, targetId);
      set({ session: merged });
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  translateTurn: async (turnId: string) => {
    const sess = get().session;
    if (!sess) return;
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
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  translateAll: async () => {
    const sess = get().session;
    if (!sess) return;
    try {
      set({ isLoading: true });
      const targetLang = sess.settings.target_language || 'en-IN';
      await api.translateAll(sess.id, targetLang);
      await get().loadSession(sess.id);
    } catch (e: any) {
      set({ error: e.message, isLoading: false });
    }
  },

  addKeyterm: async (term: string) => {
    const sess = get().session;
    if (!sess || !term.trim()) return;
    const current = sess.settings.keyterms || [];
    if (current.includes(term.trim())) return;
    const nextKeyterms = [...current, term.trim()];
    await get().updateSettings({ keyterms: nextKeyterms });
  },

  removeKeyterm: async (term: string) => {
    const sess = get().session;
    if (!sess) return;
    const nextKeyterms = (sess.settings.keyterms || []).filter(k => k !== term);
    await get().updateSettings({ keyterms: nextKeyterms });
  },

  updateSettings: async (settingsUpdate: Partial<SessionSettings>) => {
    const sess = get().session;
    if (!sess) return;
    const mergedSettings = { ...sess.settings, ...settingsUpdate };
    try {
      const updated = await api.updateSession(sess.id, { settings: mergedSettings as any });
      set({ session: updated });
    } catch (e: any) {
      set({ error: e.message });
    }
  }
}));
