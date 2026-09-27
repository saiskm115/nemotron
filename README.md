# DiarizeStudio

> **Production-Quality Audio Intelligence Platform for Telugu, Telugu + English Code-Mixed ("Tenglish"), and Indian Multilingual Speech.**

Powered by:
- **AutoTinglishSub — Whisper Telugu Small (Quantized INT8)** (Primary ASR engine for Telugu and code-mixed Tenglish speech with millisecond word timestamps)
- **NVIDIA Nemotron 3 Diarization** (who spoke when, up to 8 speakers, overlapping speech / barge-in detection)
- **Timestamp Alignment Engine** (temporal overlap matching, barge-in flagging, turn builder)
- **Sarvam Translate Engine & Saaras V4 Fallback** (per-turn and batch translation to English)
- **Unified Session Store** (central single-source-of-truth with command-based Undo/Redo)
- **Multi-Lane Interactive Timeline & Waveform** (WaveSurfer / custom canvas scrubber, 60 FPS)

---

## Quick Start

### 1. Requirements
- **Python**: 3.11+
- **Node.js**: 18+ (tested on Node v24)
- **NVIDIA GPU**: RTX 3050+ recommended (CPU supported via REST/NIM endpoints)

### 2. Configure Environment (`.env`)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Fill in your API credentials:
```env
# Sarvam AI API Key (Saaras v4 STT & Sarvam Translate)
SARVAM_API_KEY=your_sarvam_api_key

# NVIDIA Nemotron 3 Diarization Endpoint & Key (Optional remote NIM)
NEMOTRON_ENDPOINT=
NEMOTRON_API_KEY=
```
*(If no API keys are provided, DiarizeStudio automatically runs high-fidelity offline simulation fixtures with real Telugu-English test suites so you can develop and test immediately!)*

---

### 3. Launch DiarizeStudio

#### Option A: One-click Launchers
- **Windows PowerShell**:
  ```powershell
  .\run_dev.ps1
  ```
- **Windows Command Prompt**:
  ```cmd
  run_dev.bat
  ```

#### Option B: Manual Launch
1. **Start Backend**:
   ```bash
   py -3.11 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
   ```
2. **Start Frontend**:
   ```bash
   cd frontend
   npm run dev
   ```
3. Open `http://localhost:5173` in your browser.

---

## Automated Test Suite

Run the full pytest suite:
```bash
py -3.11 -m pytest backend/tests -v
```

Includes test coverage for:
- 16kHz mono audio preprocessing & peak computation
- Temporal overlap alignment with barge-in / overlapping speech detection
- Telugu script vs English Latin script code-mixing segmentation
- Streaming interim-to-final reconciliation and user edit protection
- Speaker renaming, speaker merging, and undo/redo history
- Full offline pipeline integration
- SRT, VTT, JSON, TXT, and DOCX document exports

---

## Architectural Highlights

### The Telugu + English Code-Mixed Rule
DiarizeStudio strictly separates:
- **Language**: `te`, `en`
- **Script**: Telugu (`\u0C00-\u0C7F`), Latin (`A-Za-z`)
- **Code-mixing**: Spoken Telugu with embedded English words (e.g. `నేను meeting కి 10 minutes late అవుతాను.`)

Code-mixed sentences are never forced into unnecessary translation or unwanted transliteration unless explicitly toggled by the user.

### Raw Model Immutability
User edits never overwrite raw model outputs. DiarizeStudio preserves:
- `/raw/diarization.json`
- `/raw/asr.json`
- `/processed/turns.json`
- `/edits/history.json`

Users can click **"Reset to Model Output"** at any time to recover the original model predictions.
