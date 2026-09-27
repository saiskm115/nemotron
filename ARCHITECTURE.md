# DiarizeStudio — Architecture & Technical Design Document

## 1. System Overview
**DiarizeStudio** is an enterprise-grade audio intelligence platform engineered for multi-speaker multilingual audio analysis, with first-class specialization in:
* Telugu (`te-IN`)
* Telugu + English Code-Mixed speech ("Tenglish")
* Indian English (`en-IN`)
* Multi-speaker meetings, telephony recordings, and live microphone audio streams.

The core product mission is answering with millisecond precision:
> **"Who said what, exactly when, in which language, and what is the translation?"**

---

## 2. High-Level Architecture

```
                          ┌───────────────────────────┐
                          │   Frontend (React + TS)   │
                          │   WaveSurfer + Timeline   │
                          │   Zustand Unified Store   │
                          └─────────────┬─────────────┘
                                        │ HTTP / REST & WebSocket
                                        ▼
                          ┌───────────────────────────┐
                          │  Backend (FastAPI Engine) │
                          │  Session Store & History  │
                          └─────────────┬─────────────┘
                                        │
           ┌────────────────────────────┼───────────────────────────┐
           ▼                            ▼                           ▼
 ┌───────────────────┐        ┌───────────────────┐       ┌───────────────────┐
 │ Audio Preprocessor│        │ Diarization Engine│       │    ASR Engine     │
 │ Mono 16kHz PCM    │        │ NVIDIA Nemotron 3 │       │ Sarvam Saaras V4  │
 └─────────┬─────────┘        └─────────┬─────────┘       └─────────┬─────────┘
           │                            │                           │
           └────────────────────────────┼───────────────────────────┘
                                        ▼
                          ┌───────────────────────────┐
                          │ Timestamp Alignment Engine│
                          │ Temporal Overlap & Turn   │
                          │      Reconciliation       │
                          └─────────────┬─────────────┘
                                        │
                         ┌──────────────┴──────────────┐
                         ▼                             ▼
              ┌───────────────────┐         ┌───────────────────┐
              │Translation Engine │         │   Export Engine   │
              │(Sarvam / LLM/NLLB)│         │(SRT/VTT/DOCX/JSON)│
              └───────────────────┘         └───────────────────┘
```

---

## 3. Component Architecture & Responsibility

### 3.1 Audio Preprocessing (`pipeline/audio_preprocessor.py`)
* Standardizes all input audio (file uploads, mic chunks, raw PCM) into **16kHz 16-bit mono PCM**.
* Single-decode architecture: prevents redundant decoding between diarization and ASR.
* Computes RMS loudness normalization, durations, sample counts, and waveform peaks for high-speed client-side visual timeline rendering without loading multi-megabyte files into browser memory.

### 3.2 Diarization Provider Interface (`providers/diarization/`)
* **`DiarizationProvider` (Base ABC)**:
  - `process_file(audio: AudioInput, options: DiarizationOptions) -> DiarizationResult`
  - `start_stream(options: DiarizationOptions) -> DiarizationStream`
* **`NemotronDiarizationProvider`**:
  - Targets **NVIDIA Nemotron 3 Diarization**.
  - Operates on 10ms frame resolution, outputting speaker activity intervals `[start, end, speaker_id, confidence]`.
  - Supports up to 8 simultaneous speakers and native overlapping speech detection.
  - Pluggable backend: connects to remote NIM / HTTP endpoint (`NEMOTRON_ENDPOINT`) or local PyTorch/NeMo inference when CUDA is provisioned.
  - Fallback deterministic offline simulator for test fixtures and uncredentialed environments.

### 3.3 ASR Provider Interface (`providers/asr/`)
* **`ASRProvider` (Base ABC)**:
  - `transcribe_file(audio: AudioInput, options: ASROptions) -> ASRResult`
  - `start_stream(options: ASROptions) -> ASRStream`
* **`AutoTinglishWhisperProvider` (PRIMARY ENGINE)**:
  - Implements **AutoTinglishSub Whisper Telugu Small (Quantized INT8)** via CTranslate2 (`faster-whisper`).
  - Specialized in bilingual Telugu (`te-IN`) and Telugu + English code-mixed speech ("Tenglish").
  - Produces millisecond-accurate word timestamps with VAD filtering and keyterm prompts.
  - Supports:
    * `MODE A`: Normal transcription
    * `MODE B`: Code-mixed transcription (preserves Telugu in Telugu script and English in Latin script)
    * `MODE C`: Verbatim transcription (preserves spoken hesitations and fillers)
* **`SarvamSaarasProvider` (SECONDARY / CLOUD ENGINE)**:
  - Implements **Sarvam Saaras V4** REST API (`https://api.sarvam.ai/speech-to-text`) and WebSocket streaming.
  - Extracts word-level or chunk-level timestamps:
    ```typescript
    interface ASRToken {
      id: string;
      text: string;
      start: number;
      end: number;
      confidence?: number;
      language?: string;
      is_final: boolean;
    }
    ```
  - Exposes keyterm prompting for custom domain vocabulary (Telugu/English business names, tech jargon).

### 3.4 Timestamp Alignment & Turn Reconciliation Engine (`pipeline/alignment.py`)
* **Core Rule**: Never blindly attribute an entire ASR token/phrase to whichever speaker spoke first.
* Calculates exact temporal overlap between ASR word intervals $[w_{start}, w_{end}]$ and Diarization intervals $[d_{start}, d_{end}, S_k]$.
* Flags speech collisions / barge-ins where multiple speakers are concurrently active ($overlap = true, overlap\_speakers = [S_0, S_1]$).
* Groups consecutive compatible tokens into cohesive conversational `Turn` objects.
* Supports **Interim vs. Final Turn Reconciliation** for live streaming: interim tokens are tagged `status="interim"`, replaced atomically when final ASR chunks arrive without overwriting manual user corrections.

### 3.5 Unified Session & Turn Store (`storage/session_store.py`)
* Canonical single source of truth:
  ```typescript
  interface Turn {
    id: string;
    speaker_id: string;
    start: number;
    end: number;
    text: string;
    translated_text?: string;
    source_language?: string;
    language_segments?: LanguageSegment[];
    confidence?: number;
    status: "interim" | "final" | "edited";
    overlap?: boolean;
    overlap_speakers?: string[];
    source: "model" | "user_edit";
    original_model_text?: string;
    original_model_speaker_id?: string;
    original_start?: number;
    original_end?: number;
    translation_status?: "not_requested" | "pending" | "complete" | "failed";
    created_at: string;
    updated_at: string;
  }
  ```
* Raw model outputs (`/raw/diarization.json`, `/raw/asr.json`) are preserved immutably.
* User modifications (text edits, boundary adjustments, speaker reassignments, merges, splits) are stored in an incremental command history stack (`/edits/history.json`), enabling unlimited Undo/Redo and "Reset to Model Output".

### 3.6 Translation Engine (`providers/translation/`)
* **`TranslationProvider` (Base ABC)**:
  - `translate(text: string, source_lang: string, target_lang: string) -> TranslationResult`
* **`SarvamTranslationProvider`**:
  - Calls `https://api.sarvam.ai/translate` (`sarvam-translate:v1`).
  - Supports Telugu $\leftrightarrow$ English, Tamil, Hindi, etc.
  - Translates finalized turns on-demand or automatically upon turn finalization. Original transcript is never overwritten.

### 3.7 Export Engine (`exports/`)
* **SRT**: Standard SubRip format with speaker tags `[Mohan]`.
* **VTT**: WebVTT format with standard cues.
* **JSON**: Complete schema including words, speakers, overlap flags, edits, translations, and timestamps.
* **TXT**: Plain readable dialog transcript.
* **DOCX**: Formatted Microsoft Word meeting transcript document with metadata, speaker color accents, and translation tables.

---

## 4. Frontend Architecture (`frontend/`)

* **Framework**: React 18 + TypeScript + Vite.
* **State Management**: Zustand store (`SessionStore`) ensuring a single shared state across:
  - Waveform canvas & audio scrubber
  - Multi-lane speaker timeline (zoomable, pannable, draggable segment boundaries)
  - Virtualized transcript list (60 FPS rendering on hours-long audio)
  - Speaker management panel (rename, merge, color picker, speaking time analytics)
  - Custom vocabulary editor & prompt injector
  - Real-time live audio recorder & WebSocket client
* **Design Aesthetic**: Premium dark glassmorphism (slate/zinc palette, neon teal & amber accents, HSL color tokens, micro-animations, Inter/JetBrains Mono typography).

---

## 5. Security, Privacy & Configuration
* Sensitive provider credentials (`SARVAM_API_KEY`, `NEMOTRON_API_KEY`, `NEMOTRON_ENDPOINT`) stay exclusively server-side.
* File uploads are validated (MIME types, headers, maximum size limits).
* Local processing option vs. Cloud processing indicator visibly badged on every session.
* Automated file cleanup for temporary audio artifacts.
