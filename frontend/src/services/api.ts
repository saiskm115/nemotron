import { Session, Turn, Speaker, SessionSettings } from '../types';

const API_BASE = '/api';

async function handleResponse<T>(res: Response, defaultError: string): Promise<T> {
  if (!res.ok) {
    let message = defaultError;
    try {
      const data = await res.json();
      if (data?.detail) {
        if (typeof data.detail === 'string') {
          message = data.detail;
        } else if (Array.isArray(data.detail)) {
          message = data.detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ');
        } else {
          message = JSON.stringify(data.detail);
        }
      } else if (data?.message) {
        message = data.message;
      }
    } catch (e) {
      // response not JSON
      if (res.statusText) {
        message = `${defaultError}: ${res.status} ${res.statusText}`;
      }
    }
    throw new Error(message);
  }
  return res.json();
}

export interface UploadProgress {
  stage: 'uploading' | 'preprocessing' | 'diarizing' | 'transcribing' | 'aligning' | 'finalizing' | 'complete' | 'failed';
  stageIndex: number;
  percent: number;
  detail: string;
}

export const api = {
  // Sessions
  async listSessions(): Promise<Session[]> {
    const res = await fetch(`${API_BASE}/sessions`);
    return handleResponse<Session[]>(res, 'Failed to list sessions');
  },

  async getSession(sessionId: string): Promise<Session> {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}`);
    return handleResponse<Session>(res, 'Failed to fetch session');
  },

  async updateSession(sessionId: string, updates: Partial<Session>): Promise<Session> {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates)
    });
    return handleResponse<Session>(res, 'Failed to update session');
  },

  async resetSession(sessionId: string): Promise<Session> {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/reset`, { method: 'POST' });
    return handleResponse<Session>(res, 'Failed to reset session');
  },

  async undoSession(sessionId: string): Promise<Session> {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/undo`, { method: 'POST' });
    return handleResponse<Session>(res, 'Failed to undo');
  },

  async redoSession(sessionId: string): Promise<Session> {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/redo`, { method: 'POST' });
    return handleResponse<Session>(res, 'Failed to redo');
  },

  // Audio Upload
  async uploadAudio(formData: FormData): Promise<Session> {
    const res = await fetch(`${API_BASE}/audio/upload`, {
      method: 'POST',
      body: formData
    });
    return handleResponse<Session>(res, 'Failed to upload audio');
  },

  uploadAudioWithProgress(
    formData: FormData,
    onProgress: (progress: UploadProgress) => void
  ): Promise<Session> {
    return new Promise<Session>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${API_BASE}/audio/upload`);

      let currentPercent = 10;
      let currentStageIndex = 1;
      let currentStage: UploadProgress['stage'] = 'uploading';
      let currentDetail = 'Uploading audio stream to backend server...';

      onProgress({
        stage: currentStage,
        stageIndex: currentStageIndex,
        percent: currentPercent,
        detail: currentDetail
      });

      // Track true network upload progress (0% - 25%)
      if (xhr.upload) {
        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable && e.total > 0) {
            const rawUpload = Math.round((e.loaded / e.total) * 25);
            currentPercent = Math.max(currentPercent, Math.min(25, rawUpload));
            const loadedMB = (e.loaded / (1024 * 1024)).toFixed(2);
            const totalMB = (e.total / (1024 * 1024)).toFixed(2);
            currentDetail = `Transmitting audio payload (${loadedMB} MB / ${totalMB} MB)...`;
            onProgress({
              stage: 'uploading',
              stageIndex: 1,
              percent: currentPercent,
              detail: currentDetail
            });
          }
        });
      }

      // Progression ticker for the subsequent backend pipeline processing phases
      const ticker = setInterval(() => {
        if (currentPercent < 95) {
          // Increment smoothly
          if (currentPercent < 30) {
            currentPercent += 3;
            currentStageIndex = 1;
            currentStage = 'uploading';
            currentDetail = 'Finalizing audio transmission...';
          } else if (currentPercent < 45) {
            currentPercent += 2;
            currentStageIndex = 2;
            currentStage = 'preprocessing';
            currentDetail = '16kHz Audio Preprocessing: Normalization & Spectrogram feature extraction';
          } else if (currentPercent < 70) {
            currentPercent += 1.8;
            currentStageIndex = 3;
            currentStage = 'diarizing';
            currentDetail = 'Nemotron-3 Speaker Diarization: Neural speaker segmentation & VAD';
          } else if (currentPercent < 88) {
            currentPercent += 1.5;
            currentStageIndex = 4;
            currentStage = 'transcribing';
            currentDetail = 'Speech Recognition: AutoTinglish Telugu-English code-mixed Whisper';
          } else {
            currentPercent += 0.8;
            currentStageIndex = 5;
            currentStage = 'aligning';
            currentDetail = 'Temporal Alignment: Assembling turns & Sarvam translation graph';
          }

          onProgress({
            stage: currentStage,
            stageIndex: currentStageIndex,
            percent: Math.min(96, Math.round(currentPercent)),
            detail: currentDetail
          });
        }
      }, 350);

      xhr.onload = () => {
        clearInterval(ticker);
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const session = JSON.parse(xhr.responseText) as Session;
            onProgress({
              stage: 'complete',
              stageIndex: 5,
              percent: 100,
              detail: 'Diarization & Transcription Complete!'
            });
            resolve(session);
          } catch (e) {
            const err = new Error('Failed to parse backend session response');
            onProgress({
              stage: 'failed',
              stageIndex: currentStageIndex,
              percent: currentPercent,
              detail: err.message
            });
            reject(err);
          }
        } else {
          let errorMsg = `Server returned HTTP ${xhr.status}: ${xhr.statusText}`;
          try {
            const json = JSON.parse(xhr.responseText);
            if (json.detail) {
              errorMsg = typeof json.detail === 'string'
                ? json.detail
                : Array.isArray(json.detail)
                ? json.detail.map((d: any) => d.msg || JSON.stringify(d)).join(', ')
                : JSON.stringify(json.detail);
            }
          } catch {
            // Keep default errorMsg
          }
          onProgress({
            stage: 'failed',
            stageIndex: currentStageIndex,
            percent: currentPercent,
            detail: errorMsg
          });
          reject(new Error(errorMsg));
        }
      };

      xhr.onerror = () => {
        clearInterval(ticker);
        const err = new Error('Network error: Unable to connect to backend audio service');
        onProgress({
          stage: 'failed',
          stageIndex: currentStageIndex,
          percent: currentPercent,
          detail: err.message
        });
        reject(err);
      };

      xhr.ontimeout = () => {
        clearInterval(ticker);
        const err = new Error('Upload request timed out after extended processing');
        onProgress({
          stage: 'failed',
          stageIndex: currentStageIndex,
          percent: currentPercent,
          detail: err.message
        });
        reject(err);
      };

      xhr.send(formData);
    });
  },

  // Turn Operations
  async updateTurn(sessionId: string, turnId: string, update: Partial<Turn>): Promise<Turn> {
    const res = await fetch(`${API_BASE}/transcription/${sessionId}/turns/${turnId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(update)
    });
    return handleResponse<Turn>(res, 'Failed to update segment');
  },

  async retranscribeTurn(sessionId: string, turnId: string, start: number, end: number, speakerId?: string): Promise<Turn> {
    const res = await fetch(`${API_BASE}/transcription/${sessionId}/turns/${turnId}/retranscribe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ start, end, speaker_id: speakerId })
    });
    return handleResponse<Turn>(res, 'Failed to retranscribe segment');
  },

  async splitTurn(sessionId: string, turnId: string, splitTimestamp: number, textBefore: string, textAfter: string) {
    const res = await fetch(`${API_BASE}/transcription/${sessionId}/turns/split`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ turn_id: turnId, split_timestamp: splitTimestamp, text_before: textBefore, text_after: textAfter })
    });
    return handleResponse<any>(res, 'Failed to split segment');
  },

  async mergeTurns(sessionId: string, firstTurnId: string, secondTurnId: string): Promise<Turn> {
    const res = await fetch(`${API_BASE}/transcription/${sessionId}/turns/merge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ first_turn_id: firstTurnId, second_turn_id: secondTurnId })
    });
    return handleResponse<Turn>(res, 'Failed to merge segments');
  },

  async deleteTurn(sessionId: string, turnId: string) {
    const res = await fetch(`${API_BASE}/transcription/${sessionId}/turns/${turnId}`, { method: 'DELETE' });
    return handleResponse<any>(res, 'Failed to delete segment');
  },

  async resetTurn(sessionId: string, turnId: string): Promise<Turn> {
    const res = await fetch(`${API_BASE}/transcription/${sessionId}/turns/${turnId}/reset`, { method: 'POST' });
    return handleResponse<Turn>(res, 'Failed to reset segment');
  },

  // Speakers
  async updateSpeaker(sessionId: string, speakerId: string, update: Partial<Speaker>): Promise<Speaker> {
    const res = await fetch(`${API_BASE}/speakers/${sessionId}/${speakerId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(update)
    });
    return handleResponse<Speaker>(res, 'Failed to update speaker');
  },

  async mergeSpeakers(sessionId: string, sourceSpeakerId: string, targetSpeakerId: string): Promise<Session> {
    const res = await fetch(`${API_BASE}/speakers/${sessionId}/merge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_speaker_id: sourceSpeakerId, target_speaker_id: targetSpeakerId })
    });
    return handleResponse<Session>(res, 'Failed to merge speakers');
  },

  // Translation
  async translateTurn(sessionId: string, turnId: string, targetLanguage: string = 'en-IN'): Promise<Turn> {
    const res = await fetch(`${API_BASE}/translations/${sessionId}/turns/${turnId}?target_language=${targetLanguage}`, {
      method: 'POST'
    });
    return handleResponse<Turn>(res, 'Failed to translate segment');
  },

  async translateAll(sessionId: string, targetLanguage: string = 'en-IN') {
    const res = await fetch(`${API_BASE}/translations/${sessionId}/translate_all?target_language=${targetLanguage}`, {
      method: 'POST'
    });
    return handleResponse<any>(res, 'Failed to translate transcript');
  },

  // Exports URLs
  getExportUrl(sessionId: string, format: 'srt' | 'vtt' | 'txt' | 'json' | 'docx', includeTranslation: boolean = true): string {
    return `${API_BASE}/exports/${sessionId}/${format}?include_translation=${includeTranslation}`;
  }
};
