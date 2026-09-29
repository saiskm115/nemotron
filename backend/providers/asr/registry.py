"""
ASR model registry and factory.

One place that knows which transcription models exist, which languages each one
actually supports, whether it can run in this deployment, and how to construct it.
The upload dialog, the settings modal and the pipeline all read from here, so the
model the operator picks is the model that runs.
"""
import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from .auto_tinglish_whisper import WhisperASRProvider
from .base import ASRProvider
from .indic_conformer import IndicConformerProvider, model_available as indic_conformer_available
from .sarvam_saaras import SarvamSaarasProvider
from .svanita import DEFAULT_MODEL_ID as SVANITA_MODEL_ID
from .svanita import SvanitaParakeetProvider

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "svanita_0_6b"


@dataclass(frozen=True)
class ASRModelSpec:
    id: str
    label: str
    description: str
    languages: List[str]
    local: bool
    builder: Optional[object] = field(default=None, repr=False, compare=False)
    requires_api_key: Optional[str] = None
    recommended: bool = False
    notes: str = ""
    # Optional callable returning (ok, reason). Lets a model that needs weights on
    # disk report as unavailable before anything tries to load a 600M checkpoint.
    probe: Optional[object] = field(default=None, repr=False, compare=False)


def _svanita() -> SvanitaParakeetProvider:
    return SvanitaParakeetProvider(SVANITA_MODEL_ID)


def _svanita_telugu() -> SvanitaParakeetProvider:
    """Telugu-only checkpoint: 1-3 WER points better on Telugu than the bilingual one."""
    return SvanitaParakeetProvider(SVANITA_MODEL_ID, revision="v0.1")


def _whisper_small() -> WhisperASRProvider:
    return WhisperASRProvider(model_size_or_path=os.environ.get("WHISPER_MODEL_SIZE", "small"), compute_type="int8")


def _whisper_large() -> WhisperASRProvider:
    return WhisperASRProvider(model_size_or_path="large-v3", compute_type="int8")


def _vasista22() -> WhisperASRProvider:
    return WhisperASRProvider(hf_model_id="vasista22/whisper-telugu-base")


def _sarvam_v4() -> SarvamSaarasProvider:
    return SarvamSaarasProvider()


def _indic_conformer() -> IndicConformerProvider:
    return IndicConformerProvider()


def _indic_conformer_probe() -> tuple:
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        return False, "onnxruntime is not installed"
    if indic_conformer_available():
        return True, ""
    return False, "model weights are not in the local Hugging Face cache"


INDIC_LANGUAGES = [
    "as", "bn", "brx", "doi", "gu", "hi", "kn", "kok", "ks", "mai", "ml",
    "mni", "mr", "ne", "or", "pa", "sa", "sat", "sd", "ta", "te", "ur",
]


MODELS: Dict[str, ASRModelSpec] = {
    spec.id: spec
    for spec in [
        ASRModelSpec(
            id="svanita_0_6b",
            label="Svanita 0.6B — Parakeet TDT (Telugu + Hindi + English)",
            description=(
                "0.6B FastConformer/TDT recogniser trained on Telugu and Hindi conversation. "
                "Writes Telugu in Telugu script and the English mixed into it in Latin script, "
                "in a single pass. Runs faster than real time on CPU."
            ),
            languages=["te", "hi", "en"],
            local=True,
            builder=_svanita,
            recommended=True,
            notes=(
                "Recommended for Telugu call recordings. Measured 7.7% WER on this repo's Telugu "
                "fixture, keeping borrowed English words in Latin script."
            ),
        ),
        ASRModelSpec(
            id="svanita_0_6b_telugu",
            label="Svanita 0.6B — Telugu-only checkpoint (v0.1)",
            description=(
                "The Telugu-only revision of the same model. 1-3 WER points better than the "
                "bilingual checkpoint on every Telugu test set, at the cost of Hindi support."
            ),
            languages=["te", "en"],
            local=True,
            builder=_svanita_telugu,
            notes="Best accuracy when the recording is Telugu only.",
        ),
        ASRModelSpec(
            id="indic_conformer_600m",
            label="IndicConformer 600M multilingual (INT8 ONNX)",
            description=(
                "AI4Bharat's IndicConformer covering all 22 scheduled Indian languages in one "
                "model, so a multilingual recording does not need a per-language recogniser. "
                "Conformer-CTC with per-language token sets, run through onnxruntime on CPU. "
                "Word timestamps come from the CTC frame path, so diarisation alignment and "
                "short backchannels both get real boundaries."
            ),
            languages=INDIC_LANGUAGES,
            local=True,
            builder=_indic_conformer,
            probe=_indic_conformer_probe,
            notes=(
                "Best choice for anything outside Telugu/Hindi/English. The INT8 encoder holds up "
                "to about 10 s of audio per window, which the provider handles by decoding in "
                "overlapping 10 s windows. Decodes Telugu in Telugu script; use Svanita 0.6B for "
                "Telugu call recordings, which is tuned for code-mixed Telugu-English."
            ),
        ),
        ASRModelSpec(
            id="whisper_small_int8",
            label="Whisper Small (INT8, CTranslate2)",
            description=(
                "Quantized multilingual Whisper. General purpose: handles Telugu, English, Hindi "
                "and other Indian languages, with automatic language detection."
            ),
            languages=["te", "hi", "kn", "ta", "ml", "mr", "bn", "gu", "ur"],
            local=True,
            builder=_whisper_small,
            notes=(
                "General purpose, but multilingual Whisper transliterates borrowed Telugu-English words "
                "into the target script and is prone to repetition loops on this content. Measured 103% "
                "WER on this repo's Telugu fixture — use it for non-Indic audio."
            ),
        ),
        ASRModelSpec(
            id="vasista22_whisper_telugu",
            label="Whisper Telugu Base (fine-tuned)",
            description=(
                "Whisper base fine-tuned on Telugu. Produces Telugu script reliably, but writes borrowed "
                "English words phonetically in Telugu, so code-mixed transcripts are not usable downstream."
            ),
            languages=["te"],
            local=True,
            builder=_vasista22,
            notes="Measured 67% WER on this repo's Telugu fixture; English terms come back transliterated.",
        ),
        ASRModelSpec(
            id="whisper_large_v3",
            label="Whisper Large V3 (INT8, CTranslate2)",
            description="Highest-accuracy local Whisper. Slower and memory hungry; best for clean studio audio.",
            languages=["te", "en", "hi", "kn", "ta", "ml", "mr", "bn", "gu", "ur"],
            local=True,
            builder=_whisper_large,
            notes="Roughly 10x slower than Small on CPU, and shares its script-mixing limitations.",
        ),
        ASRModelSpec(
            id="sarvam_saaras_v4",
            label="Sarvam Saaras V4 (cloud API)",
            description=(
                "Sarvam's hosted speech-to-text. 22 Indian languages plus English, native "
                "code-mixing, verbatim/normalized output modes and key-term prompting."
            ),
            languages=["te", "hi", "en", "ta", "kn", "bn", "gu", "mr", "ml", "pa", "ur"],
            local=False,
            builder=_sarvam_v4,
            requires_api_key="SARVAM_API_KEY",
            notes="Requires SARVAM_API_KEY and outbound network access.",
        ),
    ]
}

_instances: Dict[str, ASRProvider] = {}


def get_asr_provider(model_id: Optional[str] = None) -> ASRProvider:
    """
    Returns a provider instance for ``model_id`` (cached, models are heavy).

    Falls back to the configured default, then to the default again, so an unknown
    id from a stale client still produces a working provider instead of an error.
    """
    resolved = model_id if model_id in MODELS else DEFAULT_MODEL
    if resolved in _instances:
        return _instances[resolved]

    spec = MODELS[resolved]
    if spec.requires_api_key and not os.environ.get(spec.requires_api_key):
        raise RuntimeError(
            f"ASR model '{spec.id}' requires the {spec.requires_api_key} environment variable."
        )

    provider = spec.builder()
    _instances[resolved] = provider
    return provider


def model_is_available(model_id: str) -> bool:
    spec = MODELS.get(model_id)
    if spec is None:
        return False
    if spec.requires_api_key and not os.environ.get(spec.requires_api_key):
        return False
    if spec.probe is not None:
        ok, _reason = spec.probe()
        return bool(ok)
    return True


def model_unavailable_reason(model_id: str) -> str:
    """Why a model cannot run here, or '' when it can."""
    spec = MODELS.get(model_id)
    if spec is None:
        return "unknown model"
    if spec.requires_api_key and not os.environ.get(spec.requires_api_key):
        return f"{spec.requires_api_key} is not set"
    if spec.probe is not None:
        ok, reason = spec.probe()
        if not ok:
            return reason
    return ""


def list_asr_models() -> List[dict]:
    """Model catalogue for the UI, with availability resolved for this deployment."""
    catalogue = []
    for spec in MODELS.values():
        entry = asdict(spec)
        entry.pop("builder", None)
        entry.pop("probe", None)
        entry["available"] = model_is_available(spec.id)
        entry["selected"] = spec.id == DEFAULT_MODEL
        if not entry["available"]:
            entry["unavailable_reason"] = model_unavailable_reason(spec.id)
        catalogue.append(entry)
    return catalogue


def primary_model_id() -> str:
    configured = os.environ.get("PRIMARY_ASR_MODEL", "").strip()
    return configured if configured in MODELS else DEFAULT_MODEL
