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
  │ Mono 16kHz PCM    │        │ VAD + embeddings  │       │ Svanita / Whisper │
  │ + peak pyramid    │        │ + clustering      │       │ / Sarvam Saaras  │
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
* Decodes every supported container through PyAV (AAC, M4A, MP4, AMR, 3GP, Opus, OGG, MP3, FLAC,
  WAV, WMA, WebM, CAF, AIFF) with a `soundfile`/`librosa` fallback.
* **Channels are averaged explicitly** rather than letting the resampler downmix: PyAV's default
  stereo→mono matrix is `[0.707, 0.707]`, which is RMS-preserving and leaves a dual-mic call
  recording with speech on one channel 3 dB quiet.
* `_condition` removes DC offset and peak-normalises anything that would clip.
* Computes RMS and peak dBFS plus a **mip-mapped peak pyramid** (512 → 2048 buckets) so the timeline
  draws from the resolution that matches its zoom instead of resampling one fixed envelope, while
  the JSON payload stays bounded regardless of recording length.

### 3.2 Diarization Provider Interface (`providers/diarization/`)
* **`DiarizationProvider` (Base ABC)**:
  - `process_file(audio: AudioInput, options: DiarizationOptions) -> DiarizationResult`
  - `start_stream(options: DiarizationOptions) -> DiarizationStream`
* **`LocalDiarizationProvider`** (default, CPU):
  - `vad.detect_speech` — 25 ms frame / 10 ms hop, adaptive noise floor from the quietest decile,
    hysteresis enter/exit thresholds, minimum speech and minimum silence durations, padded edges.
  - `embedding.SpeakerEmbedder` — ECAPA-TDNN (`speechbrain/spkrec-ecapa-voxceleb`, the pyannote
    standard), falling back to WavLM base+ x-vector and then MFCC statistics. Window embeddings are
    averaged per region so memory stays bounded.
  - Within-region speaker-change detection splits long VAD regions at the strongest embedding
    discontinuity.
  - `mean_normalize` removes the shared component of self-supervised embeddings; `auto_cluster_threshold`
    places the speech/speech boundary with Otsu's method on the off-diagonal cosine distances, bounded
    to 70%..150% of the configured threshold. The lower bound is tight on purpose: a loose one splits
    one person across two clusters and each phantom cluster becomes a timeline lane.
  - `agglomerative_cosine` — average linkage on cosine distance, then enforcement of `max_speakers`.
  - A run too short to be a turn is absorbed into the run before it **only when its embedding
    matches that speaker**. A 200 ms "yeah" from the other person is both a short run and a genuine
    speaker change, and absorbing it by length alone silently relabels the interjection.
  - Speakers are renumbered by first appearance so `speaker_0` is always the first voice heard.
  - Emits **no** segments when there is no voice activity, and reports overlap only when a model that
    predicts overlapped speech produced it.
* **`NemotronDiarizationProvider`**:
  - Remote NIM / REST endpoint when `NEMOTRON_ENDPOINT` is set (honours `max_speakers` and `threshold`).
  - Otherwise local NVIDIA Sortformer (`nvidia/diar_sortformer_4spk-v1`) via `nemo_toolkit`, parsing
    the RTTM output. The caller's `max_speakers` is passed through (clamped to the checkpoint's four
    classes) rather than the ceiling being hard-coded.
  - Raises an explanatory error when neither backend is usable, rather than substituting a heuristic.
* **`speaker_count.estimate_and_merge` (shared by every backend)**:
  - A diarisation backend's speaker limit is a *capacity*, not a prediction. Sortformer is a power-set
    model and will label a two-voice call `speaker_0..speaker_3`; a remote endpoint echoes whatever it
    felt like; embedding clustering with a loose threshold splits one person in two. Left alone, every
    phantom label becomes a permanent speaker lane.
  - So every result is re-clustered against measured speaker embeddings. `S(k)` is the within-cluster
    scatter for `k` clusters; the cut that produces the k-th cluster removes `d(k) = S(k-1) - S(k)`, and
    the reported count is the largest `k` whose removal clears both a share of the largest removal and
    a share of the total scatter. Two distinct voices collapse the scatter hard on the first cut and
    leave nothing after it, so the first cut wins and nothing else does. The absolute term is what
    stops a single-voice recording from being carved into every cluster on offer.
  - `min_speakers` and `max_speakers` bound the answer from both sides; the score trace is kept in the
    result metadata so a surprising count can be explained rather than guessed at.
  - Speakers are renumbered by first appearance, and when two overlapping labels turn out to be one
    voice the overlap reference follows the merge instead of leaving a segment overlapping itself.

### 3.3 ASR Provider Interface (`providers/asr/`)
* **`ASRProvider` (Base ABC)**:
  - `transcribe_file(audio: AudioInput, options: ASROptions) -> ASRResult`
  - `transcribe_interval(audio_file_path, start, end, options) -> ASRResult`
  - `start_stream(options: ASROptions) -> ASRStream`
* **`registry.py`** — the single source of truth for which models exist, which languages each
  supports, whether it can run here, and how to build it. `GET /api/audio/models` serves the
  catalogue; `SessionSettings.asr_model` carries the per-session choice through the pipeline.
* **`SvanitaParakeetProvider`** (default):
  - `prasadvittaldev/svanita-0.6b` — Parakeet-TDT, fp32 (int8 costs ~30 WER points on this checkpoint).
  - **Script lock**: when the session states a language, vocabulary pieces containing the *other*
    Indic script are banned before decoding, which is worth ~2 WER points on Telugu.
  - Greedy TDT decoding over the model's own modules so per-token frame durations survive;
    word timings are real measurements, with sub-word pieces merged into words.
  - Long audio is decoded in 30 s windows with 1.5 s overlap; each word is kept by exactly one window.
  - `detect_output_language` reports the script actually produced.
* **`IndicConformerProvider`** (all 22 scheduled Indian languages):
  - AI4Bharat's IndicConformer 600M, a Conformer-CTC with per-language token sets. The INT8 ONNX
    export is used rather than the fp32 `.nemo` archive: same weights and same 22 language heads
    through onnxruntime, at roughly 1.1 GB of CPU RAM instead of 2.6 GB.
  - The checkpoint shares one 5633-token output space across all 22 languages, so decoding is
    restricted to the caller-stated language's 257 tokens. An unmasked decode answers in whichever
    language happened to score highest in a space it was never meant to use.
  - CTC greedy decoding is the default: one label per 80 ms encoder frame, so collapsing the path
    gives genuine per-word boundaries rather than a uniform split of a chunk. The RNNT head is wired
    up and selectable with `INDIC_CONFORMER_DECODER=rnnt`.
  - Decoded in **10 s** overlapping windows, not 30 s. Measured on a 71 s Telugu call, the INT8
    encoder emits a non-blank CTC path 47-79% of the time over 10 s windows but collapses to an
    all-blank path over 30 s ones (0.0% at offset 0). A silently blank window reads as "nobody spoke".
* **`WhisperASRProvider`**:
  - CTranslate2 (`faster-whisper`) for `small` / `large-v3`, or a fine-tuned HF checkpoint.
  - The requested language is honoured; *unknown* means auto-detect, never "assume Telugu".
  - Never receives a language-specific prompt (measured: a Telugu-script prompt causes a repetition
    loop); only keyterm vocabulary is injected.
  - Greedy decoding, with `is_degenerate` dropping repetition loops by unique-token ratio.
  - `_repair_generation_config` rebuilds `lang_to_id` / `task_to_id` on fine-tuned checkpoints that
    ship a pre-2024 generation config.
* **`SarvamSaarasProvider`** (cloud):
  - Sarvam Saaras V4 REST API with `normal` / `codemix` / `verbatim` output modes and keyterm prompting.
  - `transcribe_interval` uploads only the requested slice and rebases the returned timestamps.
* Transcript modes (`normal`, `codemix`, `verbatim`) are carried through to providers that support
  them; all providers return `ASRToken` records with `id`, `text`, `start`, `end`, `confidence`,
  `language` and `is_final`.

### 3.4 Timestamp Alignment & Turn Reconciliation Engine (`pipeline/alignment.py`)
* **Core Rule**: Never blindly attribute an entire ASR token/phrase to whichever speaker spoke first.
* Calculates exact temporal overlap between ASR word intervals $[w_{start}, w_{end}]$ and Diarization intervals $[d_{start}, d_{end}, S_k]$.
* Flags speech collisions / barge-ins where multiple speakers are concurrently active ($overlap = true, overlap\_speakers = [S_0, S_1]$).
* Groups consecutive compatible tokens into cohesive conversational `Turn` objects.
* Supports **Interim vs. Final Turn Reconciliation** for live streaming: interim tokens are tagged `status="interim"`, replaced atomically when final ASR chunks arrive without overwriting manual user corrections.
* **Speech-only units** mark diarised speech the recogniser returned no text for. Their floor is
  deliberately conservative: a gap between two words is either a missed interjection or an ordinary
  pause, and duration alone cannot tell them apart, so a low enough floor to catch a 250 ms "ah" would
  turn every hesitation into an empty row.
* **Backchannel rescue** (`pipeline/backchannel_rescue.py`) is what actually recovers the
  interjection. The offline pipeline runs the recogniser once over the whole file, which is right for
  accuracy and speed but has one blind spot: a 200-350 ms "avunu" between two longer turns can be
  swallowed, and one missing token removes the region from the transcript. Diarised regions that are
  short and came back empty are re-decoded **in isolation**, with acoustic context either side, through
  the same `transcribe_interval` path the timeline's re-transcribe button uses. That measures the
  content of the region rather than guessing from its length, so a pause stays empty and a real
  interjection comes back with text. The pass is bounded (short regions only, 24 decodes maximum) and
  any provider failure is contained rather than failing the run.

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
* **`Annotation`** — a manual label a reviewer drew on the timeline:
  ```typescript
  interface Annotation {
    id: string;
    start: number;
    end: number;
    text: string;
    label: "note" | "important" | "question" | "action_item" | "review"
         | "backchannel" | "speaker_label" | "error";
    speaker_id?: string | null;   // which voice this label is about
    turn_id?: string | null;
    source: "manual" | "model";
    author?: string | null;
    created_at: string;
    updated_at: string;
  }
  ```
  Annotations are human judgements rather than model output, so unlike raw diarisation they are
  **not** discarded when a session is re-processed. Ranges are clamped to the recording on write, so
  a drag that runs off either end of the viewport still produces a valid annotation.
  A `speaker_label` annotation can be **applied** to the transcript
  (`POST /api/annotations/{sid}/{aid}/apply`): every turn the region covers is re-assigned to the named
  speaker. Coverage is measured against the *turn*, not the annotation, so a half-second label inside
  a four-second turn does not drag the whole turn with it. The change joins the undo history like any
  other edit. This is the manual answer to a model that split one person into four speakers.

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
  - Manual annotation lane and reviewer panel (draw a region, tag it, apply a speaker label)
  - Custom vocabulary editor & prompt injector
  - Real-time live audio recorder & WebSocket client
* **Design Aesthetic**: Premium dark glassmorphism (slate/zinc palette, neon teal & amber accents, HSL color tokens, micro-animations, Inter/JetBrains Mono typography).

---

## 5. Security, Privacy & Configuration
* Sensitive provider credentials (`SARVAM_API_KEY`, `NEMOTRON_API_KEY`, `NEMOTRON_ENDPOINT`) stay exclusively server-side.
* File uploads are validated (MIME types, headers, maximum size limits).
* Local processing option vs. Cloud processing indicator visibly badged on every session.
* Automated file cleanup for temporary audio artifacts.
