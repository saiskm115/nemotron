"""
ASR benchmark endpoint.

Two separate things, deliberately kept apart:

* **Reference figures** — error rates published by each model's authors, on that
  author's own test set, returned with the dataset named. They are not comparable
  across rows and are never presented as measurements of this deployment.
* **Measured results** — real WER/CER, latency and real-time factor computed on
  this machine by actually running each selected model over an audio file and a
  reference transcript.

Nothing in this module invents a number.
"""
import os
import time
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..metrics import cer, error_counts, latin_word_ratio, wer
from ..providers.asr.registry import get_asr_provider, list_asr_models, model_is_available

router = APIRouter(prefix="/api/benchmark", tags=["benchmark"])

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "fixtures"
FIXTURE_WAV = FIXTURE_DIR / "telugu_call_2spk.wav"
FIXTURE_TRUTH = FIXTURE_DIR / "telugu_call_2spk.truth.json"

# Error rates as published by each model's authors, with the evaluation set named.
# `localised` marks figures that require script locking or a post-hoc rewrite.
REFERENCE_FIGURES = {
    "svanita_0_6b": {
        "dataset": "IndicVoices Telugu, held-out speakers (model card v0.2)",
        "wer": "37.7",
        "cer": "17.0",
        "latin_preservation": "74% of English words kept in Latin script",
        "real_time_factor": "0.05-0.08x on a 6-core desktop CPU (model card)",
        "caveat": "Without a script lock the model answers Telugu audio in Devanagari ~8% of the time; "
                  "this app passes the language through, which removes that.",
    },
    "svanita_0_6b_telugu": {
        "dataset": "IndicVoices Telugu, held-out speakers (model card v0.1)",
        "wer": "36.5",
        "cer": "16.4",
        "latin_preservation": "76% of English words kept in Latin script",
        "real_time_factor": "0.05-0.08x on a 6-core desktop CPU (model card)",
        "caveat": "Telugu-only checkpoint; no Hindi support.",
    },
    "whisper_small_int8": {
        "dataset": "Whisper paper test suites (large-v2 numbers, multilingual prior)",
        "wer": "n/a for Telugu in the paper",
        "cer": "n/a",
        "latin_preservation": "Multilingual Whisper transliterates borrowed words into the target script",
        "real_time_factor": "Depends on hardware; run the measurement below for this machine",
        "caveat": "The paper does not report Telugu WER, so no figure is quoted.",
    },
    "vasista22_whisper_telugu": {
        "dataset": "Whisper fine-tuning sprint Telugu evaluation",
        "wer": "44.0 (large-v2 Telugu fine-tune, same evaluation as Svanita's)",
        "cer": "32.0",
        "latin_preservation": "0% - borrowed words are written in Telugu script",
        "real_time_factor": "Slower than Small",
        "caveat": "Telugu-only output; cannot represent code-mixed English.",
    },
    "whisper_large_v3": {
        "dataset": "Whisper paper, multilingual average",
        "wer": "2.0 (multilingual average, not Telugu)",
        "cer": "4.0 (multilingual average, not Telugu)",
        "latin_preservation": "Multilingual Whisper transliterates borrowed words into the target script",
        "real_time_factor": "Roughly 10x slower than Small on CPU",
        "caveat": "Multilingual averages are not comparable with the Telugu-specific rows above.",
    },
    "sarvam_saaras_v4": {
        "dataset": "Vendor-stated figures (Sarvam Saaras V4 announcement, Aug 2026)",
        "wer": "not published per-language",
        "cer": "not published",
        "latin_preservation": "Native code-mixing with 5 output formats",
        "real_time_factor": "<150 ms time-to-first-token (streaming)",
        "caveat": "Vendor-reported; no per-language error rates were published.",
    },
}

# CPU-friendly ordering: the cheap local models first so a run gives partial results fast.
DEFAULT_BENCHMARK_MODELS = ["svanita_0_6b", "whisper_small_int8", "vasista22_whisper_telugu"]


class BenchmarkRequest(BaseModel):
    model_ids: List[str] = Field(default_factory=lambda: list(DEFAULT_BENCHMARK_MODELS))
    audio_path: Optional[str] = None
    reference_text: Optional[str] = None
    language_code: str = "te-IN"


def _load_fixture() -> tuple:
    import json

    if not FIXTURE_WAV.exists() or not FIXTURE_TRUTH.exists():
        raise HTTPException(
            status_code=400,
            detail=(
                "No benchmark corpus is available. Generate one with "
                "`python -m backend.tests.make_telugu_fixture`, or POST audio_path and "
                "reference_text explicitly."
            ),
        )
    turns = json.loads(FIXTURE_TRUTH.read_text(encoding="utf-8"))
    reference = " ".join(turn["text"] for turn in turns)
    return str(FIXTURE_WAV), reference


@router.get("/reference")
async def reference_figures():
    """Published error rates, labelled with the evaluation set each came from."""
    out = []
    for model in list_asr_models():
        figures = dict(REFERENCE_FIGURES.get(model["id"], {}))
        out.append({**model, "reference": figures or None})
    return {"models": out}


@router.post("/run")
async def run_benchmark(req: BenchmarkRequest):
    """
    Transcribes the corpus with each selected model and scores it for real.
    """
    import asyncio


    if req.audio_path and req.reference_text:
        audio_path, reference = req.audio_path, req.reference_text
        if not os.path.exists(audio_path):
            raise HTTPException(status_code=400, detail=f"Audio file not found: {audio_path}")
    else:
        audio_path, reference = _load_fixture()

    import soundfile as sf

    try:
        duration = sf.info(audio_path).duration
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Could not read audio: {exc}")

    results = []
    for model_id in req.model_ids:
        if not model_is_available(model_id):
            results.append({
                "model_id": model_id,
                "status": "unavailable",
                "error": "Model is not installed or its API key is missing",
            })
            continue
        try:
            provider = get_asr_provider(model_id)
            started = time.time()
            result = await asyncio.to_thread(
                _transcribe, provider, audio_path, req.language_code
            )
            wall = time.time() - started

            transcript = result.transcript
            latin_words, total_words = latin_word_ratio(transcript)
            results.append({
                "model_id": model_id,
                "status": "ok",
                "wer": round(wer(reference, transcript), 4),
                "cer": round(cer(reference, transcript), 4),
                "errors": error_counts(reference, transcript),
                "latency_sec": round(wall, 3),
                "real_time_factor": round(wall / duration, 4) if duration else None,
                "audio_duration_sec": round(duration, 3),
                "token_count": len(result.tokens),
                "script": result.language_code,
                "latin_word_ratio": round(latin_words / total_words, 3) if total_words else 0.0,
                "transcript": transcript,
            })
        except Exception as exc:  # noqa: BLE001 - one bad model must not kill the run
            results.append({"model_id": model_id, "status": "error", "error": str(exc)})

    return {
        "audio_path": audio_path,
        "audio_duration_sec": round(duration, 3),
        "reference_text": reference,
        "results": results,
    }


def _transcribe(provider, audio_path: str, language_code: str):
    import asyncio

    from ..models.asr import ASRMode, ASROptions
    from ..models.audio import AudioInput

    return asyncio.run(
        provider.transcribe_file(
            AudioInput(file_path=audio_path),
            ASROptions(mode=ASRMode.CODEMIXED, language_code=language_code, with_timestamps=True),
        )
    )
