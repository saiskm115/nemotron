# DiarizeStudio

> **Audio intelligence for Telugu, Telugu + English code-mixed ("Tenglish"), and Indian multilingual speech.**

Engines:
- **Svanita 0.6B** (Parakeet-TDT, on-device, default) — Telugu in Telugu script with borrowed English
  words kept in Latin, in one pass, with real word-level timestamps
- **Speaker diarisation on CPU** — energy VAD → ECAPA-TDNN speaker embeddings → average-linkage
  clustering on cosine distance; overlapping speech is labelled only when a model predicts it
- **Selectable transcription models** — Svanita (Telugu-only and bilingual), Whisper Small/Large V3
  (CTranslate2), a Telugu-fine-tuned Whisper, and Sarvam Saaras V4 (cloud)
- **Timestamp alignment engine** — temporal overlap matching and turn assembly
- **Sarvam translation**, unified session store with undo/redo
- **Multi-lane interactive timeline** with canvas waveform, speaker lanes, caption track and minimap

---

## Quick Start

### 1. Requirements
- **Python**: 3.11+ (the launchers use `py -3.11`)
- **Node.js**: 18+
- No GPU required. Everything below runs on CPU.

Install the backend dependencies:
```bash
py -3.11 -m pip install fastapi uvicorn pydantic python-multipart pyyaml httpx \
    numpy soundfile librosa av torch torchaudio transformers faster-whisper speechbrain \
    scikit-learn python-docx pytest pytest-asyncio
```

### 2. Configure (optional)
Copy `.env.example` to `.env`. Everything has a working on-device default, so this is only needed
for the cloud model, remote diarisation, or translation:
```bash
cp .env.example .env
```
```env
# Transcription model to use when a session does not pick one
PRIMARY_ASR_MODEL=svanita_0_6b

# Sarvam (translation, and the sarvam_saaras_v4 model)
SARVAM_API_KEY=

# Route diarisation to a remote NVIDIA Nemotron / Sortformer service instead of local
NEMOTRON_ENDPOINT=
```

### 3. Generate the test corpus (optional, needs network once)
```bash
py -3.11 -m backend.tests.make_telugu_fixture
```
Renders a two-speaker Telugu + English call with neural voices into
`data/fixtures/telugu_call_2spk.wav` plus a JSON sidecar holding the exact turn boundaries.
Tests that need real speech are skipped when this file is absent.

### 4. Launch
```powershell
.\run_dev.ps1
```
or manually:
```bash
py -3.11 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
cd frontend && npm run dev
```
Open <http://localhost:5173>.

---

## Choosing a transcription model

The upload dialog and the settings modal both read `GET /api/audio/models`, so the list always
reflects what the deployment can actually run.

| id | What it is | Use it for |
|---|---|---|
| `svanita_0_6b` | Parakeet-TDT 0.6B, Telugu + Hindi + code-mixed English | **Default.** Telugu call recordings |
| `svanita_0_6b_telugu` | Same model, Telugu-only checkpoint (v0.1) | Telugu-only audio; 1–3 WER points better |
| `whisper_small_int8` | Quantized multilingual Whisper | Non-Indic audio, or language auto-detection |
| `vasista22_whisper_telugu` | Whisper base fine-tuned on Telugu | Pure Telugu without code-mixing |
| `whisper_large_v3` | Whisper Large V3 (INT8) | Clean studio audio, latency not a concern |
| `sarvam_saaras_v4` | Sarvam hosted STT | Needs `SARVAM_API_KEY`; 22 Indian languages |

### Measured on this repository's Telugu fixture

`POST /api/benchmark/run` runs each available model on the same audio and reference transcript:

| model | WER ↓ | CER ↓ | RTF ↓ | output |
|---|---|---|---|---|
| `svanita_0_6b` | **7.7%** | 7.2% | 0.61× | Telugu script + Latin English |
| `vasista22_whisper_telugu` | 66.7% | 63.6% | 1.50× | Telugu script, English transliterated |
| `whisper_small_int8` | 102.6% | 100.0% | 0.57× | **Devanagari** — wrong script |

Whisper's Telugu prior is weak: it writes `home loan` as `होम लोंवूरिंची` and `documents` as
`डाक्युमेंच`. A score above 100% means substitutions plus extra words. The Benchmark panel shows
these as *measured*, and separately shows each author's *published* figures with the dataset named —
those two columns are never mixed.

---

## Language handling

The spoken language chosen for a session is passed through to the model, not guessed:

- **Telugu** → Svanita locks its vocabulary to the Telugu block, which removes the ~8% of clips it
  would otherwise answer in Devanagari.
- **Telugu + English** → Svanita writes the Telugu in Telugu script and the borrowed English in
  Latin, as one transcript. Nothing is transliterated.
- **Auto-detect** → no script lock; the decoder picks freely and the app reports the script it
  actually produced.

`GET /api/audio/models` and the UI label a model as *unavailable* rather than silently substituting
a different one. Whisper never receives a language-specific prompt: measured on this corpus, a
Telugu-script prompt sends it straight into a repetition loop.

---

## Diarisation

Local CPU path (the default):

```
16 kHz mono  ->  energy VAD (25 ms frame / 10 ms hop, adaptive noise floor, hysteresis)
             ->  speaker embeddings (ECAPA-TDNN; WavLM x-vector, then MFCC, as fallbacks)
             ->  within-region speaker-change detection
             ->  mean-normalised embeddings
             ->  average-linkage clustering on cosine distance (Otsu-placed boundary)
             ->  speaker_0, speaker_1, ... numbered by first appearance
```

Notes on correctness:
- Nothing is invented. Silence produces **no** segments rather than fabricated alternating blocks,
  and no overlapping speech is reported unless a model that predicts overlap (Sortformer or a remote
  Nemotron endpoint) produced it.
- Speaker names are neutral (`Speaker 1`), never invented identities.
- Set `NEMOTRON_ENDPOINT` to route diarisation to a remote NVIDIA endpoint, or install
  `nemo_toolkit` for local `nvidia/diar_sortformer_4spk-v1`.

---

## Automated Test Suite

```bash
py -3.11 -m pytest backend/tests -q
```

Covers 16 kHz mono preprocessing and the peak pyramid, DC removal and stereo downmix, VAD,
embedding normalisation, cluster thresholding, diarisation against ground-truth speaker turns,
Svanita script locking and word timestamps, code-mixed Latin preservation, language reporting,
ASR model registry and selection wiring, alignment and speech-only coverage, retranscription,
speaker merging, undo/redo, exports, and end-to-end pipeline runs.

---

## Architectural Highlights

### The Telugu + English code-mixed rule
Language, script and code-mixing are tracked separately:
- **Language**: `te`, `hi`, `en`
- **Script**: Telugu (U+0C00–U+0C7F), Devanagari (U+0900–U+097F), Latin
- **Code-mixing**: Telugu speech with embedded English words, preserved rather than translated or
  transliterated unless the operator asks for it

Word-level script detection labels each recognised word, so a turn can be `te / en / te / en`
without any guessing.

### Raw model immutability
User edits never overwrite raw model output. Preserved under each session directory:
- `raw/diarization.json`, `raw/asr.json`
- `processed/turns.json`
- `edits/history.json`

**Reset to Model Output** restores the original prediction for any turn.
