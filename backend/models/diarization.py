from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class DiarizationSegment(BaseModel):
    speaker_id: str
    start: float
    end: float
    confidence: Optional[float] = None
    # True only when a real overlapped-speech model reported this segment as part
    # of concurrent speech. Never synthesised from turn-taking alone.
    is_overlap: bool = False
    overlap_speakers: List[str] = Field(default_factory=list)

class DiarizationOptions(BaseModel):
    # Hard ceiling on how many distinct voices the result may contain. Backends
    # that are power-set or embedding-clustered treat this as a capacity, not a
    # prediction, so it is enforced again downstream by speaker-count estimation.
    max_speakers: int = 8
    # Floor. Set this when the recording is known to have at least N voices (a
    # two-handset call, say) so estimation is never allowed to report fewer.
    min_speakers: int = 1
    # Re-cluster the result to the number of voices actually measured, merging
    # labels the backend split one person across. Turn off only to see the raw
    # backend output.
    auto_speaker_count: bool = True
    latency_profile: str = "offline" # "offline" (30.4s), "low_latency" (0.32s), "ultra_low" (0.08s)
    # Decision threshold forwarded to a remote Nemotron endpoint (0..1).
    threshold: float = 0.5

    # ── Local acoustic diarisation (VAD + speaker embeddings + clustering) ──
    # Backchannel-aware by default: "avunu", "yeah", "ah" are 150-300 ms of
    # speech between two turns, and the previous 0.25 s floor deleted them before
    # they were ever embedded. A floor that low costs a little noise, which the
    # clustering absorbs; a floor that high loses real speech permanently.
    min_speech_duration: float = 0.12
    min_silence_duration: float = 0.15
    speech_pad: float = 0.10
    # Cosine distance above which two segments are treated as different speakers.
    # Used as the fallback and as the +/-50% bound around the automatically
    # detected boundary (Otsu on the off-diagonal distance distribution).
    cluster_threshold: float = 0.90
    # Segments shorter than this are candidates for absorption into a neighbour.
    # Absorption is only applied when the embedding says it is the same voice,
    # so a genuine short interjection from the other person survives.
    min_turn_duration: float = 0.25
    # Cosine similarity above which a too-short run is treated as the same
    # speaker as the run before it. Below it, the short run keeps its own label.
    short_turn_similarity: float = 0.62
    # Longest VAD region handed to the speaker embedder before change detection splits it.
    max_segment_duration: float = 12.0
    embedding_model: str = "microsoft/wavlm-base-plus-sv"

class DiarizationResult(BaseModel):
    segments: List[DiarizationSegment] = Field(default_factory=list)
    speakers: List[str] = Field(default_factory=list)
    overlap_count: int = 0
    latency_sec: float = 0.0
    # How the segments were produced, e.g. "nemotron_endpoint", "sortformer", "acoustic_xvector".
    method: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
