import { Session, Turn, Speaker, SessionSettings } from '../types';

const API_BASE = '/api';

export const api = {
  // Sessions
  async listSessions(): Promise<Session[]> {
    const res = await fetch(`${API_BASE}/sessions`);
    if (!res.ok) throw new Error('Failed to list sessions');
    return res.json();
  },

  async getSession(sessionId: string): Promise<Session> {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}`);
    if (!res.ok) throw new Error('Failed to fetch session');
    return res.json();
  },

  async updateSession(sessionId: string, updates: Partial<Session>): Promise<Session> {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates)
    });
    if (!res.ok) throw new Error('Failed to update session');
    return res.json();
  },

  async resetSession(sessionId: string): Promise<Session> {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/reset`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to reset session');
    return res.json();
  },

  async undoSession(sessionId: string): Promise<Session> {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/undo`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to undo');
    return res.json();
  },

  async redoSession(sessionId: string): Promise<Session> {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/redo`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to redo');
    return res.json();
  },

  // Audio Upload
  async uploadAudio(formData: FormData): Promise<Session> {
    const res = await fetch(`${API_BASE}/audio/upload`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(err.detail || 'Upload failed');
    }
    return res.json();
  },

  // Turn Operations
  async updateTurn(sessionId: string, turnId: string, update: Partial<Turn>): Promise<Turn> {
    const res = await fetch(`${API_BASE}/transcription/${sessionId}/turns/${turnId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(update)
    });
    if (!res.ok) throw new Error('Failed to update turn');
    return res.json();
  },

  async splitTurn(sessionId: string, turnId: string, splitTimestamp: number, textBefore: string, textAfter: string) {
    const res = await fetch(`${API_BASE}/transcription/${sessionId}/turns/split`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ turn_id: turnId, split_timestamp: splitTimestamp, text_before: textBefore, text_after: textAfter })
    });
    if (!res.ok) throw new Error('Failed to split turn');
    return res.json();
  },

  async mergeTurns(sessionId: string, firstTurnId: string, secondTurnId: string): Promise<Turn> {
    const res = await fetch(`${API_BASE}/transcription/${sessionId}/turns/merge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ first_turn_id: firstTurnId, second_turn_id: secondTurnId })
    });
    if (!res.ok) throw new Error('Failed to merge turns');
    return res.json();
  },

  async deleteTurn(sessionId: string, turnId: string) {
    const res = await fetch(`${API_BASE}/transcription/${sessionId}/turns/${turnId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete turn');
    return res.json();
  },

  async resetTurn(sessionId: string, turnId: string): Promise<Turn> {
    const res = await fetch(`${API_BASE}/transcription/${sessionId}/turns/${turnId}/reset`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to reset turn');
    return res.json();
  },

  // Speakers
  async updateSpeaker(sessionId: string, speakerId: string, update: Partial<Speaker>): Promise<Speaker> {
    const res = await fetch(`${API_BASE}/speakers/${sessionId}/${speakerId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(update)
    });
    if (!res.ok) throw new Error('Failed to update speaker');
    return res.json();
  },

  async mergeSpeakers(sessionId: string, sourceSpeakerId: string, targetSpeakerId: string): Promise<Session> {
    const res = await fetch(`${API_BASE}/speakers/${sessionId}/merge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_speaker_id: sourceSpeakerId, target_speaker_id: targetSpeakerId })
    });
    if (!res.ok) throw new Error('Failed to merge speakers');
    return res.json();
  },

  // Translation
  async translateTurn(sessionId: string, turnId: string, targetLanguage: string = 'en-IN'): Promise<Turn> {
    const res = await fetch(`${API_BASE}/translations/${sessionId}/turns/${turnId}?target_language=${targetLanguage}`, {
      method: 'POST'
    });
    if (!res.ok) throw new Error('Failed to translate turn');
    return res.json();
  },

  async translateAll(sessionId: string, targetLanguage: string = 'en-IN') {
    const res = await fetch(`${API_BASE}/translations/${sessionId}/translate_all?target_language=${targetLanguage}`, {
      method: 'POST'
    });
    if (!res.ok) throw new Error('Failed to translate transcript');
    return res.json();
  },

  // Exports URLs
  getExportUrl(sessionId: string, format: 'srt' | 'vtt' | 'txt' | 'json' | 'docx', includeTranslation: boolean = true): string {
    return `${API_BASE}/exports/${sessionId}/${format}?include_translation=${includeTranslation}`;
  }
};
