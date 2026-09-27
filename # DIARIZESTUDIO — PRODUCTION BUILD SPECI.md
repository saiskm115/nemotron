# DIARIZESTUDIO — PRODUCTION BUILD SPECIFICATION

Build a production-quality desktop/web application called **DiarizeStudio** for:

* Telugu speech
* Telugu + English code-mixed speech
* Indian English
* English
* multilingual Indian speech
* multi-speaker meetings
* phone/call recordings
* live microphone/audio streams
* uploaded audio/video

The application must combine:

1. **NVIDIA Nemotron 3 Diarization** — speaker activity / who spoke when
2. **Sarvam Saaras V4** — primary ASR for Telugu, Indian English and code-mixed speech
3. **Timestamp alignment engine** — connects ASR words/phrases to diarization speaker activity
4. **Translation engine** — optional per-turn translation
5. **Editable unified transcript model**
6. **Timeline + transcript + speaker management UI**

The goal is NOT merely to create a demo.

Build the application as a modular, testable production system where ASR, diarization and translation engines can be replaced independently.

---

# 1. PRIMARY PRODUCT REQUIREMENT

The application must answer:

> "Who said what, exactly when, in which language, and what is the translation?"

Example:

Speaker 0:

```text
నేను meeting కి 10 minutes late అవుతాను.
```

Speaker 1:

```text
Okay, no problem. మీరు వచ్చిన తర్వాత start చేద్దాం.
```

The UI must understand that:

* Telugu words remain Telugu
* English words remain English
* code-mixed speech is NOT translated unnecessarily
* speaker identity is preserved
* timestamps remain accurate
* corrections propagate throughout the application

---

# 2. ASR STRATEGY

## Primary ASR

Use:

**Sarvam Saaras V4**

Use it as the primary transcription engine for:

* Telugu
* Indian English
* Telugu-English code-mixing
* multilingual Indian speech
* noisy/telephony audio where applicable

Saaras supports:

* transcription
* translation
* verbatim transcription
* transliteration
* code-mixed transcription
* language detection
* streaming
* keyterm prompting

Do NOT blindly force the audio language to Telugu.

For mixed speech:

```text
language = auto / unknown
```

when supported.

Allow explicit language selection when the user knows the source language.

---

# 3. ASR OUTPUT MODES

Implement three application modes.

## MODE A — Normal transcription

Use when the user wants a readable transcript.

Example:

```text
నేను రేపు office కి వస్తాను.
```

## MODE B — Code-mixed transcription

Prefer preserving the language actually spoken.

Example:

```text
నేను రేపు office కి వస్తాను.
```

Do NOT transform this into:

```text
నేను రేపు ఆఫీసుకు వస్తాను.
```

unless the user explicitly requests transliteration/localization.

## MODE C — Verbatim

Preserve:

* fillers
* repetitions
* false starts
* spoken numbers
* hesitations

Example:

```text
అది... actually నేను... అంటే రేపు వస్తాను.
```

The user must be able to switch between readable and verbatim representations.

---

# 4. IMPORTANT TELUGU + ENGLISH RULE

The application must treat these as different concepts:

### Language

```text
te
en
```

### Script

```text
Telugu
Latin
```

### Code-mixing

```text
Telugu + English
```

Example:

```text
నాకు project deadline గురించి clarity లేదు.
```

This is:

```json
{
  "language": "te-IN",
  "is_code_mixed": true,
  "segments": [
    {
      "text": "నాకు",
      "language": "te"
    },
    {
      "text": "project deadline",
      "language": "en"
    },
    {
      "text": "గురించి clarity లేదు",
      "language": "te"
    }
  ]
}
```

Do not assume that English words inside a Telugu sentence mean the user wants English translation.

---

# 5. DIARIZATION ENGINE

Primary diarization:

```text
NVIDIA Nemotron 3 Diarization
```

Input:

```text
16kHz
mono
PCM
```

Support:

```text
speaker_0
speaker_1
...
speaker_7
```

Do not permanently couple speaker IDs to names.

Example:

```json
{
  "speaker_id": "speaker_0",
  "display_name": "Mohan"
}
```

The model's speaker IDs are session-local.

---

# 6. AUDIO PIPELINE

Build:

```text
INPUT
 ↓
Audio Decoder
 ↓
Resampler
 ↓
Mono conversion
 ↓
16kHz PCM
 ↓
Audio buffering
 ├───────────────┐
 ↓               ↓
Diarization      ASR
 ↓               ↓
Speaker          Text
activity         + timestamps
 └───────┬───────┘
         ↓
    ALIGNMENT ENGINE
         ↓
      TURN STORE
         ↓
 ┌───────┼─────────┐
 ↓       ↓         ↓
UI    Translation Export
```

The audio preprocessing layer must be shared.

Do NOT independently decode/resample the same audio multiple times.

---

# 7. TIMESTAMP ALIGNMENT ENGINE

This is one of the most important components.

Never simply assign an entire ASR chunk to whichever speaker was active at its beginning.

Instead:

1. Receive diarization activity intervals.
2. Receive ASR timestamped words/phrases.
3. Calculate temporal overlap.
4. Assign each ASR unit to the speaker with the strongest valid overlap.
5. Detect ambiguous overlap.
6. Preserve overlapping speakers.
7. Build speaker turns from consecutive compatible ASR units.

Conceptually:

```text
Diarization:

0.0 ───── 2.4 speaker_0
2.4 ───── 4.8 speaker_1
4.8 ───── 7.1 speaker_0
```

ASR:

```text
0.2 ─ 1.1 "నమస్కారం"
1.2 ─ 2.2 "ఎలా ఉన్నారు"
2.5 ─ 3.4 "I am fine"
3.6 ─ 4.5 "thank you"
```

Alignment:

```text
speaker_0:
0.2 → 2.2
"నమస్కారం ఎలా ఉన్నారు"

speaker_1:
2.5 → 4.5
"I am fine thank you"
```

---

# 8. WORD/PHRASE ALIGNMENT

Create an internal normalized representation:

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

If the upstream ASR only provides phrase/chunk timestamps:

```typescript
interface ASRChunk {
  id: string;
  text: string;
  start: number;
  end: number;
  confidence?: number;
  language?: string;
  is_final: boolean;
}
```

The alignment engine must support both.

Do not assume that the ASR provider always returns word-level timestamps.

---

# 9. TURN DATA MODEL

Create a canonical shared turn object.

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

  status:
    | "interim"
    | "final"
    | "edited";

  overlap?: boolean;

  overlap_speakers?: string[];

  source:
    | "model"
    | "user_edit";

  original_model_text?: string;

  original_model_speaker_id?: string;

  original_start?: number;

  original_end?: number;

  translation_status?:
    | "not_requested"
    | "pending"
    | "complete"
    | "failed";

  created_at: string;

  updated_at: string;
}
```

This object is the central source of truth.

---

# 10. NEVER DUPLICATE STATE

The following must NOT have independent copies of transcript state:

```text
Timeline
Transcript
Speaker panel
Search
Translation
Export
```

Everything must read/write from the same session store.

Recommended frontend:

```text
Zustand
```

or Redux Toolkit.

Recommended structure:

```text
SessionStore
 ├── audio
 ├── speakers
 ├── turns
 ├── selection
 ├── playback
 ├── settings
 ├── translations
 └── editHistory
```

---

# 11. SPEAKER MANAGEMENT

Each speaker:

```typescript
interface Speaker {
  id: string;

  display_name: string;

  color: string;

  total_speaking_time: number;

  turn_count: number;

  first_seen: number;

  last_seen: number;

  model_label: string;
}
```

Allow:

* rename
* color change
* merge speakers
* reassign turns
* split speaker identity
* delete/restore
* listen to speaker audio sample

Example:

```text
speaker_0 → Mohan
speaker_1 → Priya
```

---

# 12. SPEAKER MERGING

If:

```text
speaker_2
speaker_5
```

are actually the same person:

```text
Merge speaker_5 → speaker_2
```

All affected turns must immediately update.

Do not rewrite raw model output.

Store:

```text
model speaker identity
+
user speaker identity
```

separately.

---

# 13. RAW MODEL OUTPUT

Persist raw outputs independently.

Example:

```text
/raw
   diarization.json
   asr.json
   audio metadata
   model metadata

/processed
   turns.json

/edits
   history.json
```

The user must always be able to:

```text
Reset to model output
```

without losing the original model result.

---

# 14. LIVE STREAMING

Support:

```text
Microphone
System audio
WebRTC audio
WebSocket PCM
Uploaded file
```

Live pipeline:

```text
Audio frame
 ↓
Audio buffer
 ↓
Nemotron streaming diarization
 ↓
Saaras streaming ASR
 ↓
Incremental alignment
 ↓
Interim Turn
 ↓
UI
 ↓
Final ASR result
 ↓
Turn reconciliation
 ↓
Final Turn
```

Do NOT permanently append every interim ASR result.

Use:

```text
temporary/interim state
```

and replace it when final results arrive.

---

# 15. LIVE TRANSCRIPT UX

Interim:

```text
grey / italic
```

Final:

```text
normal
```

Edited:

```text
small edited indicator
```

Low confidence:

```text
underline
```

Speaker overlap:

```text
overlap indicator
```

Never silently hide uncertainty.

---

# 16. LATENCY REQUIREMENT

Optimize for:

```text
time-to-first-transcript
```

rather than waiting for complete sentences.

Target architecture:

```text
audio
 ↓
stream
 ↓
partial diarization
 +
partial ASR
 ↓
partial turn
```

The application should remain responsive even if final reconciliation occurs later.

---

# 17. BARge-IN / OVERLAPPING SPEECH

Nemotron can represent simultaneous speaker activity.

If:

```text
speaker_0 active
speaker_1 active
```

at the same time:

```text
overlap = true
```

Do not force a single speaker.

UI:

```text
Speaker 0 ███████████
Speaker 1       █████████
              ↑ overlap
```

Transcript should display:

```text
⚠ Overlapping speech
```

where appropriate.

---

# 18. TELUGU-SPECIFIC UX

Support all of these representations:

### Telugu script

```text
మీరు ఎక్కడికి వెళ్తున్నారు?
```

### Roman Telugu

```text
Meeru ekkadiki velthunnaru?
```

### Code-mixed

```text
మీరు office కి ఎప్పుడు వస్తారు?
```

### English translation

```text
When are you coming to the office?
```

Allow the user to switch between them.

Do NOT automatically transliterate Telugu unless requested.

---

# 19. TRANSLATION ENGINE

Translation must be a separate module.

Interface:

```typescript
interface TranslationProvider {
  translate(
    text: string,
    sourceLanguage: string,
    targetLanguage: string
  ): Promise<TranslationResult>;
}
```

Possible providers:

```text
Sarvam Translate
LLM translator
NLLB
other provider
```

Never mix translation logic into the ASR service.

---

# 20. TRANSLATION MODES

Global:

```text
Translate entire transcript
```

Per turn:

```text
Translate this turn
```

Live:

```text
Automatically translate finalized turns
```

On-demand:

```text
Translate only when user clicks
```

Recommended default:

```text
Do not translate interim ASR.
Translate only finalized turns.
```

---

# 21. TRANSLATION DISPLAY

Support:

### Original only

```text
Mohan
మీరు ఎప్పుడు వస్తారు?
```

### Translation only

```text
Mohan
When are you coming?
```

### Both

```text
Mohan
మీరు ఎప్పుడు వస్తారు?

When are you coming?
```

---

# 22. CUSTOM VOCABULARY

This is especially important for Telugu-English business conversations.

Support:

```text
names
companies
products
technical terms
medical terms
locations
Indian names
Telugu names
English jargon
```

Example:

```text
Ramesh
HustleLabs
Oracle Fusion HCM
Sarvam
Nemotron
NVIDIA
Dhan
Upstox
```

For Saaras V4, expose keyterm prompting where supported.

UI:

```text
Custom vocabulary
+
Add term
+
Import CSV
```

---

# 23. ASR PROVIDER INTERFACE

Do NOT hard-code Sarvam directly into the application.

Create:

```typescript
interface ASRProvider {

  transcribeFile(
    audio: AudioInput,
    options: ASROptions
  ): Promise<ASRResult>;

  startStream(
    options: ASROptions
  ): Promise<ASRStream>;

  stopStream(): Promise<void>;
}
```

Implement:

```text
SarvamSaarasProvider
```

first.

Prepare interfaces for:

```text
WhisperProvider
IndicConformerProvider
FutureProvider
```

This allows benchmarking providers later.

---

# 24. DIARIZATION PROVIDER INTERFACE

```typescript
interface DiarizationProvider {

  processFile(
    audio: AudioInput,
    options: DiarizationOptions
  ): Promise<DiarizationResult>;

  startStream(
    options: DiarizationOptions
  ): Promise<DiarizationStream>;

  stopStream(): Promise<void>;
}
```

Implement:

```text
NemotronDiarizationProvider
```

first.

---

# 25. TRANSLATION PROVIDER INTERFACE

```typescript
interface TranslationProvider {

  translate(
    request: TranslationRequest
  ): Promise<TranslationResult>;
}
```

---

# 26. AUDIO PROVIDER INTERFACE

```typescript
interface AudioSource {

  start(): Promise<void>;

  stop(): Promise<void>;

  onAudio(
    callback: (frame: AudioFrame) => void
  ): void;
}
```

Implement:

```text
MicrophoneSource
FileSource
SystemAudioSource
WebRTCAudioSource
WebSocketAudioSource
```

---

# 27. BACKEND ARCHITECTURE

Use:

```text
Python
FastAPI
WebSocket
asyncio
```

Recommended structure:

```text
backend/

  api/
    sessions.py
    audio.py
    transcription.py
    speakers.py
    translations.py
    exports.py

  providers/
    asr/
      base.py
      sarvam_saaras.py

    diarization/
      base.py
      nemotron.py

    translation/
      base.py
      sarvam.py

  pipeline/
    audio_preprocessor.py
    streaming_pipeline.py
    offline_pipeline.py
    alignment.py
    turn_builder.py
    reconciliation.py

  models/
    audio.py
    speaker.py
    asr.py
    diarization.py
    turn.py
    translation.py

  storage/
    session_store.py
    audio_store.py
    edit_store.py

  exports/
    srt.py
    vtt.py
    json.py
    txt.py
    docx.py
```

---

# 28. FRONTEND ARCHITECTURE

Use:

```text
React
TypeScript
Vite
Zustand
WaveSurfer.js
WebSocket
```

Structure:

```text
frontend/

  components/

    audio/
      AudioPlayer
      Waveform
      LiveRecorder

    timeline/
      SpeakerTimeline
      SpeakerLane
      Segment
      OverlapIndicator

    transcript/
      TranscriptPanel
      TranscriptTurn
      TranscriptWord
      SearchTranscript

    speakers/
      SpeakerList
      SpeakerEditor
      MergeSpeakers

    translation/
      TranslationPanel
      TranslationTurn

    editor/
      TurnEditor
      SplitTurn
      MergeTurns
      BoundaryEditor

    export/
      ExportMenu

  stores/
    sessionStore
    transcriptStore
    speakerStore
    audioStore
    settingsStore
    historyStore

  services/
    websocket.ts
    api.ts

  types/
```

---

# 29. MAIN SCREEN

Create a professional audio intelligence UI.

Layout:

```text
┌──────────────────────────────────────────────────────┐
│ DiarizeStudio     Session     Language     Export   │
├──────────────────────────────────────────────────────┤
│                                                      │
│                AUDIO WAVEFORM                        │
│                                                      │
├──────────────────────────────────────────────────────┤
│ S0 █████████████                                     │
│ S1           █████████████                           │
│ S2                      █████                        │
├──────────────────────────────────────────────────────┤
│                                                      │
│ TRANSCRIPT                       SPEAKERS             │
│                                                      │
│ Mohan  00:12                                      │
│ నేను office కి వస్తాను.                             │
│ I will come to the office.                         │
│                                                      │
│ Priya  00:17                                        │
│ Okay, మీరు వచ్చిన తర్వాత call చేద్దాం.              │
│ Okay, let's call after you come.                    │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

# 30. TIMELINE

Use a horizontally scrollable timeline.

Features:

* zoom
* pan
* playback cursor
* speaker colors
* segment boundaries
* overlap visualization
* click-to-seek
* drag boundaries
* split
* merge

Timeline and transcript selection must be synchronized.

Click transcript:

```text
→ timeline jumps
→ audio seeks
```

Click timeline:

```text
→ transcript scrolls
→ turn becomes selected
```

---

# 31. EDITING

Every turn must support:

```text
Edit text
Change speaker
Change start
Change end
Split
Merge
Translate
Delete
Restore original
```

Keyboard shortcuts:

```text
Space      play/pause
E          edit
S          split
M          merge
R          reassign speaker
Ctrl+Z     undo
Ctrl+Shift+Z redo
←/→        seek
Shift+←/→  fine timestamp adjustment
```

---

# 32. EDIT HISTORY

Implement command-based history.

Example:

```typescript
interface EditCommand {
  id: string;
  type: string;
  timestamp: string;

  before: unknown;
  after: unknown;
}
```

Support:

```text
undo
redo
reset turn
reset session
```

---

# 33. AUTOSAVE

Autosave:

```text
after every meaningful edit
```

but debounce writes.

Never save every mouse movement.

Use:

```text
300–1000ms debounce
```

depending on operation.

---

# 34. EXPORT

Support:

### JSON

Include:

```text
speakers
turns
timestamps
language
translations
confidence
edit metadata
```

### TXT

```text
[Mohan] [00:00:04]

నమస్కారం అందరికీ.
```

### SRT

```text
1
00:00:04,000 --> 00:00:06,500
[Mohan] నమస్కారం అందరికీ.
```

### VTT

Same concept using WebVTT.

### DOCX

Create a readable meeting transcript.

---

# 35. SEARCH

Search must work across:

```text
original transcript
translation
speaker
language
```

Example:

```text
Search: "office"
```

Results:

```text
Mohan — 00:12
నేను office కి వస్తాను.
```

Click result:

```text
→ seek audio
→ select turn
→ highlight text
```

---

# 36. SESSION MODEL

```typescript
interface Session {

  id: string;

  title: string;

  created_at: string;

  duration: number;

  audio_source: string;

  source_languages: string[];

  target_language?: string;

  speakers: Speaker[];

  turns: Turn[];

  processing_status:
    | "uploading"
    | "processing"
    | "complete"
    | "failed";

  mode:
    | "live"
    | "offline";

  settings: SessionSettings;
}
```

---

# 37. PRIVACY

Support:

```text
Local processing
Cloud processing
```

Show clearly:

```text
Audio uploaded to cloud
```

or:

```text
Audio processed locally
```

Allow:

```text
Delete audio after processing
```

If cloud APIs are used:

* never expose API keys in frontend
* store keys only server-side
* use environment variables
* redact keys from logs

---

# 38. SECURITY

Implement:

```text
authentication
session authorization
file type validation
file size limits
rate limiting
WebSocket authentication
CORS restrictions
CSRF protection where applicable
secure temporary file handling
automatic cleanup
```

Never allow arbitrary filesystem paths from the frontend.

---

# 39. ERROR HANDLING

The UI must never silently fail.

If:

```text
ASR unavailable
```

show:

```text
ASR unavailable — diarization completed.
```

If:

```text
Diarization unavailable
```

show:

```text
Transcript available, speaker attribution unavailable.
```

If:

```text
Translation fails
```

preserve the original transcript.

The application must degrade gracefully.

---

# 40. MODEL FAILURE VISIBILITY

Display processing quality information.

Example:

```text
Transcript confidence: 87%

Speaker overlap detected: 12 times

Low-confidence regions: 7

Unresolved alignment: 2
```

Do not invent confidence values.

Only display confidence when the underlying provider supplies meaningful confidence information.

---

# 41. OFFLINE PROCESSING

For uploaded files:

```text
Decode
 ↓
Normalize audio
 ↓
Diarize
 ↓
ASR
 ↓
Align
 ↓
Build turns
 ↓
Translate if requested
 ↓
Save
```

Run expensive processing asynchronously.

Use:

```text
job_id
```

and expose:

```text
queued
processing
completed
failed
```

---

# 42. LIVE PROCESSING

Use WebSocket:

```text
client
 ↕
backend
 ↕
ASR
 ↕
diarization
```

Messages must be typed.

Example:

```json
{
  "type": "transcript.interim",
  "turn_id": "turn_123",
  "speaker_id": "speaker_0",
  "text": "నేను office...",
  "start": 12.31,
  "end": 13.42
}
```

Final:

```json
{
  "type": "transcript.final",
  "turn_id": "turn_123",
  "speaker_id": "speaker_0",
  "text": "నేను office కి వస్తాను.",
  "start": 12.31,
  "end": 14.21
}
```

---

# 43. LIVE RECONCILIATION

Do not assume:

```text
interim turn ID == final turn ID
```

Create a reconciliation layer.

When final ASR arrives:

```text
find matching interim turn
→ update
→ preserve user edits if already made
→ recalculate alignment if required
```

---

# 44. PERFORMANCE

Target:

```text
UI remains 60 FPS
```

Do not rerender the entire transcript for every audio frame.

Use:

```text
memoized components
virtualized transcript
batched WebSocket updates
debounced persistence
incremental timeline rendering
```

For long recordings:

```text
10 minutes
30 minutes
1 hour
3 hours+
```

must remain usable.

Virtualize transcript rows.

---

# 45. LARGE FILE SUPPORT

Do not load entire audio files into browser memory.

Use:

```text
streaming/chunked upload
```

Show:

```text
upload progress
processing progress
```

---

# 46. OBSERVABILITY

Every processing session should record:

```text
audio duration
ASR latency
diarization latency
alignment latency
translation latency
total processing time
number of speakers
number of turns
overlap count
low-confidence count
ASR errors
provider errors
```

For live sessions:

```text
time-to-first-transcript
average interim latency
finalization latency
WebSocket reconnect count
buffer underruns
dropped audio frames
```

Never log raw sensitive audio/transcripts by default.

---

# 47. TESTING

Create automated tests for:

## Alignment

```text
single speaker
two speakers
three speakers
overlapping speech
speaker changes mid-sentence
ASR chunk crossing speaker boundary
```

## Telugu

```text
pure Telugu
Telugu + English
English + Telugu
Roman Telugu
Telugu names
English technical terms
```

## Live

```text
interim → final replacement
speaker correction
ASR correction
reconnect
duplicate events
out-of-order WebSocket events
```

## Editing

```text
split
merge
reassign
rename
undo
redo
reset
```

## Export

Validate:

```text
SRT
VTT
JSON
TXT
DOCX
```

---

# 48. TELUGU TEST DATA

Create a built-in development test suite with examples such as:

```text
నాకు రేపు office కి వెళ్లాలి.

నేను meeting కి late అవుతాను.

Actually నాకు ఆ విషయం తెలియదు.

మీరు report send చేశారా?

Yes, నేను already పంపించాను.

Project deadline ఎప్పుడు?

రేపు morning లో complete చేస్తాను.

నిన్న manager నాకు call చేశారు.

Okay, మనం తర్వాత discuss చేద్దాం.
```

Also test:

```text
Indian English
Telugu names
Hyderabad place names
company names
technical vocabulary
numbers
dates
currency
URLs
email addresses
```

---

# 49. ASR BENCHMARK MODE

Build an optional benchmarking screen.

Allow the same audio to be processed through:

```text
Saaras V4
Saaras V3
IndicConformer
Whisper
```

when configured.

Display:

```text
WER
CER
latency
language detection
code-mix preservation
timestamp quality
proper noun accuracy
```

Do not declare a provider "best" from a tiny local sample.

Allow users to compare results against their own representative Telugu recordings.

---

# 50. PROVIDER CONFIGURATION

Environment variables:

```env
SARVAM_API_KEY=

NEMOTRON_ENDPOINT=
NEMOTRON_API_KEY=

TRANSLATION_PROVIDER=
TRANSLATION_API_KEY=

DATABASE_URL=

STORAGE_PATH=
```

Never put provider secrets in frontend environment variables.

---

# 51. CONFIGURATION FILE

Create:

```text
config/providers.yaml
```

with:

```yaml
asr:
  primary: sarvam_saaras_v4

diarization:
  primary: nemotron_3_diarization

translation:
  primary: sarvam

audio:
  sample_rate: 16000
  channels: 1
```

Allow providers to be changed without modifying business logic.

---

# 52. DEVELOPMENT PHASES

Do NOT attempt to build everything blindly in one step.

Build in these phases.

## PHASE 1

Create:

```text
project structure
backend
frontend
session model
provider interfaces
database/storage
```

Run tests.

---

## PHASE 2

Implement:

```text
audio upload
audio preprocessing
Saaras ASR
```

Verify real transcription.

Do not continue until transcription is actually working.

---

## PHASE 3

Implement:

```text
Nemotron diarization
```

Verify speaker timestamps independently.

---

## PHASE 4

Implement:

```text
ASR + diarization alignment
```

Use deterministic test fixtures.

---

## PHASE 5

Implement:

```text
Turn store
Timeline
Transcript UI
```

---

## PHASE 6

Implement:

```text
speaker editing
turn editing
split
merge
reassign
undo/redo
```

---

## PHASE 7

Implement:

```text
translation
```

---

## PHASE 8

Implement:

```text
live WebSocket streaming
interim results
final reconciliation
```

---

## PHASE 9

Implement:

```text
exports
search
session persistence
```

---

## PHASE 10

Implement:

```text
benchmarking
performance optimization
security
observability
production hardening
```

---

# 53. CRITICAL AGENT BEHAVIOR

The coding agent MUST NOT:

* assume an API exists
* invent model capabilities
* invent timestamps
* fake diarization results
* fake ASR results
* use mock data after the real provider is configured
* silently fall back to a different provider
* claim a test passed without actually running it
* claim an integration works without making a real request
* implement only the UI and call the backend "complete"
* implement only diarization and call it transcription
* assume word timestamps exist when only chunk timestamps exist
* silently discard overlapping speakers
* overwrite raw model output with user edits

---

# 54. TASK EXECUTION RULE

The coding agent must work sequentially.

For every task:

```text
1. Inspect existing implementation.
2. Identify dependencies.
3. Implement the smallest complete change.
4. Run relevant tests.
5. Run type checks.
6. Run lint.
7. Run integration test where applicable.
8. Verify actual output.
9. Report exactly what changed.
10. Only then move to the next task.
```

Never mark a task complete because code was written.

A task is complete only when:

```text
implementation exists
+
tests pass
+
integration verified
+
no known blocking errors
```

---

# 55. STOP CONDITIONS

Stop and report instead of guessing if:

* provider API differs from documentation
* model access is unavailable
* credentials are missing
* Nemotron endpoint is unavailable
* Saaras API schema differs
* timestamps are unavailable
* streaming API behaves differently than expected
* dependency versions conflict
* licensing prevents deployment

Clearly report:

```text
BLOCKED:
Reason:
Evidence:
What is required:
```

Do not fabricate a workaround.

---

# 56. FIRST TASK

Before writing application code:

1. Inspect the repository.
2. Inspect existing package files.
3. Inspect installed dependencies.
4. Determine whether frontend/backend already exist.
5. Determine runtime versions.
6. Verify available GPU/CPU resources.
7. Verify Sarvam API availability/configuration.
8. Verify Nemotron model/API access.
9. Verify current API contracts from official documentation.
10. Produce a short implementation assessment.

Then create:

```text
ARCHITECTURE.md
```

containing the final architecture.

Do not begin mass implementation until the architecture is understood.

---

# 57. ACCEPTANCE CRITERIA

The project is considered production-ready only when the following works end-to-end:

```text
Upload Telugu + English recording
        ↓
Audio preprocessing
        ↓
Nemotron diarization
        ↓
Saaras V4 transcription
        ↓
Timestamp alignment
        ↓
Speaker-attributed transcript
        ↓
Translation
        ↓
Editable transcript
        ↓
Timeline synchronization
        ↓
Speaker correction
        ↓
Text correction
        ↓
Undo/redo
        ↓
Export SRT/VTT/JSON/TXT/DOCX
```

And live:

```text
Microphone
 ↓
streaming audio
 ↓
Nemotron
 +
Saaras
 ↓
interim transcript
 ↓
speaker attribution
 ↓
final transcript
 ↓
optional translation
```

Every stage must produce observable, testable output.

# FINAL REQUIREMENT

Prioritize **correctness of Telugu + English code-mixed transcription and speaker attribution** over visual complexity.

A beautiful UI with incorrect transcripts is a failed product.

Build the system around the real model outputs and real timestamps, not simulated/demo data.